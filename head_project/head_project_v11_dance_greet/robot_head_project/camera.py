import json
import os
import time

import cv2
import numpy as np


class Camera:
    """Camera input plus calibrated fisheye correction.

    The geometry methods accept pixel coordinates from the final displayed frame.
    Horizontal and vertical image flips are undone internally before a ray is
    calculated, so physical pan/tilt directions remain correct.
    """

    def __init__(
        self,
        backend="opencv",
        profile="usb_webcam",
        camera_index=0,
        width=640,
        height=480,
        flip_horizontal=False,
        flip_vertical=False,
        fisheye_correction_mode="none",
        calibration_file=None,
        fisheye_balance=0.0,
        require_calibration=False,
    ):
        self.backend = backend
        self.profile = profile
        self.camera_index = camera_index
        self.width = int(width)
        self.height = int(height)
        self.flip_horizontal = bool(flip_horizontal)
        self.flip_vertical = bool(flip_vertical)

        self.fisheye_correction_mode = fisheye_correction_mode
        self.calibration_file = calibration_file
        self.fisheye_balance = float(fisheye_balance)
        self.require_calibration = bool(require_calibration)

        self.cap = None
        self.picam2 = None

        self.calibration_matrix = None
        self.dist_coeffs = None
        self.calibration_image_size = None
        self.calibration_rms_error = None

        self.rectified_camera_matrix = None
        self.undistort_map1 = None
        self.undistort_map2 = None
        self.map_size = None

        if self.fisheye_correction_mode == "calibrated":
            self._load_calibration(self.calibration_file)
            self._build_fisheye_maps(self.width, self.height)

        if self.backend == "opencv":
            self._init_opencv_camera()
        elif self.backend == "picamera2":
            self._init_picamera2()
        else:
            raise ValueError("Unknown camera backend: " + str(self.backend))

    # =====================================================
    # Initialization
    # =====================================================

    def _load_calibration(self, path):
        if path is None or not os.path.exists(path):
            message = "Camera calibration file not found: {}".format(path)
            if self.require_calibration:
                raise FileNotFoundError(message)
            print(message)
            return

        with open(path, "r", encoding="utf-8") as calibration_file:
            data = json.load(calibration_file)

        self.calibration_matrix = np.asarray(
            data["camera_matrix"], dtype=np.float64
        )
        self.dist_coeffs = np.asarray(
            data["dist_coeffs"], dtype=np.float64
        ).reshape(-1, 1)
        self.calibration_image_size = tuple(int(v) for v in data["image_size"])
        self.calibration_rms_error = data.get("rms_error")

        print("Calibration loaded:", path)
        print("Calibration resolution:", self.calibration_image_size)
        print("Calibration RMS error:", self.calibration_rms_error)

    def _scaled_calibration_matrix(self, output_size):
        if self.calibration_matrix is None or self.calibration_image_size is None:
            return None

        output_width, output_height = output_size
        calibration_width, calibration_height = self.calibration_image_size

        scale_x = output_width / float(calibration_width)
        scale_y = output_height / float(calibration_height)

        if abs(scale_x - scale_y) > 1e-3:
            raise ValueError(
                "Requested camera aspect ratio differs from the calibration "
                "aspect ratio. Recalibrate at the requested resolution."
            )

        scaled = self.calibration_matrix.copy()
        scaled[0, 0] *= scale_x
        scaled[0, 2] *= scale_x
        scaled[1, 1] *= scale_y
        scaled[1, 2] *= scale_y
        return scaled

    def _build_fisheye_maps(self, width, height):
        if self.calibration_matrix is None or self.dist_coeffs is None:
            if self.require_calibration:
                raise RuntimeError("Calibrated mode requires valid K and D values.")
            return

        output_size = (int(width), int(height))
        scaled_k = self._scaled_calibration_matrix(output_size)

        new_k = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            scaled_k,
            self.dist_coeffs,
            output_size,
            np.eye(3),
            balance=self.fisheye_balance,
        )

        map1, map2 = cv2.fisheye.initUndistortRectifyMap(
            scaled_k,
            self.dist_coeffs,
            np.eye(3),
            new_k,
            output_size,
            cv2.CV_16SC2,
        )

        self.rectified_camera_matrix = new_k
        self.undistort_map1 = map1
        self.undistort_map2 = map2
        self.map_size = output_size

        print("Calibrated fisheye maps created.")
        print("Output resolution:", output_size)
        print("Balance:", self.fisheye_balance)
        print("Rectified K:\n", new_k)

    def _init_opencv_camera(self):
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            print("OpenCV camera could not be opened.")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        print("OpenCV camera initialized at {}x{}".format(self.width, self.height))

    def _init_picamera2(self):
        try:
            from picamera2 import Picamera2
        except Exception as exc:
            print("Picamera2 import error:", exc)
            print("Create the venv with --system-site-packages if required.")
            return

        try:
            self.picam2 = Picamera2()
            configuration = self.picam2.create_preview_configuration(
                main={
                    "size": (self.width, self.height),
                    "format": "RGB888",
                }
            )
            self.picam2.configure(configuration)
            self.picam2.start()
            time.sleep(0.8)
            print("Picamera2 initialized at {}x{}".format(self.width, self.height))
        except Exception as exc:
            print("Picamera2 init error:", exc)
            self.picam2 = None

    # =====================================================
    # Public camera API
    # =====================================================

    def is_opened(self):
        if self.backend == "opencv":
            return self.cap is not None and self.cap.isOpened()
        if self.backend == "picamera2":
            return self.picam2 is not None
        return False

    def toggle_horizontal_flip(self):
        self.flip_horizontal = not self.flip_horizontal
        print("Camera horizontal flip:", self.flip_horizontal)

    def toggle_vertical_flip(self):
        self.flip_vertical = not self.flip_vertical
        print("Camera vertical flip:", self.flip_vertical)

    def read(self):
        if self.backend == "opencv":
            ret, frame = self._read_opencv()
        elif self.backend == "picamera2":
            ret, frame = self._read_picamera2()
        else:
            return False, None

        if not ret or frame is None:
            return False, None

        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))

        frame = self._apply_distortion_correction(frame)

        if self.flip_horizontal:
            frame = cv2.flip(frame, 1)
        if self.flip_vertical:
            frame = cv2.flip(frame, 0)

        return True, frame

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        if self.picam2 is not None:
            try:
                self.picam2.stop()
            except Exception:
                pass
            try:
                self.picam2.close()
            except Exception:
                pass
            self.picam2 = None

    # =====================================================
    # Geometry API
    # =====================================================

    def get_rectified_camera_matrix(self):
        if self.rectified_camera_matrix is None:
            return None
        return self.rectified_camera_matrix.copy()

    def get_output_size(self):
        return self.width, self.height

    def get_focal_lengths_pixels(self):
        if self.rectified_camera_matrix is None:
            return None, None
        return (
            float(self.rectified_camera_matrix[0, 0]),
            float(self.rectified_camera_matrix[1, 1]),
        )

    def final_pixel_to_rectified_pixel(self, pixel_x, pixel_y):
        """Undo display flips while staying in the rectified image coordinates."""
        x = float(pixel_x)
        y = float(pixel_y)

        if self.flip_horizontal:
            x = (self.width - 1) - x
        if self.flip_vertical:
            y = (self.height - 1) - y

        return x, y

    def pixel_to_ray(self, pixel_x, pixel_y):
        """Return the rectified pinhole ray (x/z, y/z, 1) for a final-frame pixel."""
        if self.rectified_camera_matrix is None:
            raise RuntimeError("pixel_to_ray requires calibrated fisheye mode.")

        x, y = self.final_pixel_to_rectified_pixel(pixel_x, pixel_y)
        fx = float(self.rectified_camera_matrix[0, 0])
        fy = float(self.rectified_camera_matrix[1, 1])
        cx = float(self.rectified_camera_matrix[0, 2])
        cy = float(self.rectified_camera_matrix[1, 2])

        ray_x = (x - cx) / fx
        ray_y = (y - cy) / fy
        return ray_x, ray_y, 1.0

    # =====================================================
    # Internal frame functions
    # =====================================================

    def _read_opencv(self):
        if self.cap is None:
            return False, None
        return self.cap.read()

    def _read_picamera2(self):
        if self.picam2 is None:
            return False, None
        try:
            return True, self.picam2.capture_array()
        except Exception as exc:
            print("Picamera2 frame read error:", exc)
            return False, None

    def _apply_distortion_correction(self, frame):
        if self.fisheye_correction_mode == "none":
            return frame

        if self.fisheye_correction_mode != "calibrated":
            raise ValueError(
                "v6 supports fixed-camera calibrated correction or 'none'."
            )

        frame_size = (frame.shape[1], frame.shape[0])
        if self.map_size != frame_size:
            self._build_fisheye_maps(*frame_size)

        return cv2.remap(
            frame,
            self.undistort_map1,
            self.undistort_map2,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
        )

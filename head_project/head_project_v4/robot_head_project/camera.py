import cv2
import numpy as np


class Camera:
    def __init__(
        self,
        backend="opencv",
        profile="usb_webcam",
        camera_index=0,
        width=640,
        height=480,
        flip_horizontal=True,
        flip_vertical=False,

        fisheye_correction_mode="none",
        fisheye_crop_scale=0.75,

        defish_input_diagonal_fov_deg=200.0,
        defish_output_diagonal_fov_deg=165.0,
        defish_strength=0.65,
        defish_zoom=1.0,

        fisheye_camera_matrix=None,
        fisheye_dist_coeffs=None,
        fisheye_balance=1.0
    ):
        self.backend = backend
        self.profile = profile

        self.camera_index = camera_index
        self.width = width
        self.height = height

        self.flip_horizontal = flip_horizontal
        self.flip_vertical = flip_vertical

        self.fisheye_correction_mode = fisheye_correction_mode
        self.fisheye_crop_scale = fisheye_crop_scale

        self.defish_input_diagonal_fov_deg = defish_input_diagonal_fov_deg
        self.defish_output_diagonal_fov_deg = defish_output_diagonal_fov_deg
        self.defish_strength = defish_strength
        self.defish_zoom = defish_zoom

        self.fisheye_camera_matrix = fisheye_camera_matrix
        self.fisheye_dist_coeffs = fisheye_dist_coeffs
        self.fisheye_balance = fisheye_balance

        self.cap = None
        self.picam2 = None

        self.undistort_map1 = None
        self.undistort_map2 = None

        self.defish_map_x = None
        self.defish_map_y = None
        self.defish_map_params = None

        self.warned_missing_calibration = False

        if self.backend == "opencv":
            self._init_opencv_camera()

        elif self.backend == "picamera2":
            self._init_picamera2()

        else:
            raise ValueError("Unknown camera backend: " + str(self.backend))

    # =====================================================
    # Initialization
    # =====================================================

    def _init_opencv_camera(self):
        self.cap = cv2.VideoCapture(self.camera_index)

        if self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            print("OpenCV camera initialized.")
            print("Camera index:", self.camera_index)
            print("Resolution:", self.width, "x", self.height)
        else:
            print("OpenCV camera could not be opened.")

    def _init_picamera2(self):
        try:
            from picamera2 import Picamera2
        except Exception as e:
            print("Picamera2 import error:")
            print(e)
            print("If rpicam-hello works but this fails, recreate venv with --system-site-packages.")
            self.picam2 = None
            return

        try:
            self.picam2 = Picamera2()

            # BGR888 seçiyoruz ki OpenCV ile renkler doğru gelsin.
            # RGB2BGR dönüşümü yapmayacağız.
            config = self.picam2.create_preview_configuration(
                main={
                    "size": (self.width, self.height),
                    "format": "BGR888"
                }
            )

            self.picam2.configure(config)
            self.picam2.start()

            print("Picamera2 camera initialized.")
            print("Profile:", self.profile)
            print("Resolution:", self.width, "x", self.height)

        except Exception as e:
            print("Picamera2 init error:")
            print(e)
            self.picam2 = None

    # =====================================================
    # Public API
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
    # Read functions
    # =====================================================

    def _read_opencv(self):
        if self.cap is None:
            return False, None

        ret, frame = self.cap.read()

        if not ret:
            return False, None

        return True, frame

    def _read_picamera2(self):
        if self.picam2 is None:
            return False, None

        try:
            # BGR888 istediğimiz için OpenCV formatında gelir.
            frame = self.picam2.capture_array()
            return True, frame

        except Exception as e:
            print("Picamera2 frame read error:", e)
            return False, None

    # =====================================================
    # Distortion correction router
    # =====================================================

    def _apply_distortion_correction(self, frame):
        mode = self.fisheye_correction_mode

        if mode is None or mode == "none":
            return frame

        if mode == "crop":
            return self._center_crop_and_resize(frame, self.fisheye_crop_scale)

        if mode == "defish":
            return self._apply_manual_defish(frame)

        if mode == "calibrated":
            return self._apply_calibrated_fisheye_undistort(frame)

        print("Unknown FISHEYE_CORRECTION_MODE:", mode)
        return frame

    # =====================================================
    # Simple crop mode
    # =====================================================

    def _center_crop_and_resize(self, frame, scale):
        if scale is None:
            return frame

        scale = max(0.3, min(1.0, float(scale)))

        h, w = frame.shape[:2]

        crop_w = int(w * scale)
        crop_h = int(h * scale)

        x1 = (w - crop_w) // 2
        y1 = (h - crop_h) // 2

        cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]

        resized = cv2.resize(
            cropped,
            (w, h),
            interpolation=cv2.INTER_LINEAR
        )

        return resized

    # =====================================================
    # Manual defish mode
    # =====================================================

    def _apply_manual_defish(self, frame):
        h, w = frame.shape[:2]

        params = (
            w,
            h,
            float(self.defish_input_diagonal_fov_deg),
            float(self.defish_output_diagonal_fov_deg),
            float(self.defish_strength),
            float(self.defish_zoom)
        )

        if (
            self.defish_map_x is None or
            self.defish_map_y is None or
            self.defish_map_params != params
        ):
            self._build_manual_defish_maps(w, h)
            self.defish_map_params = params

        if self.defish_map_x is None or self.defish_map_y is None:
            return frame

        corrected = cv2.remap(
            frame,
            self.defish_map_x,
            self.defish_map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT
        )

        return corrected

    def _build_manual_defish_maps(self, w, h):
        print("Building manual defish maps...")

        input_diag_fov = max(1.0, min(220.0, float(self.defish_input_diagonal_fov_deg)))
        output_diag_fov = max(1.0, min(175.0, float(self.defish_output_diagonal_fov_deg)))

        strength = max(0.0, min(1.0, float(self.defish_strength)))
        zoom = max(0.3, min(3.0, float(self.defish_zoom)))

        cx = (w - 1) / 2.0
        cy = (h - 1) / 2.0

        x, y = np.meshgrid(
            np.arange(w, dtype=np.float32),
            np.arange(h, dtype=np.float32)
        )

        dx = x - cx
        dy = y - cy

        r_out = np.sqrt(dx * dx + dy * dy)

        r_diag = np.sqrt(cx * cx + cy * cy)

        theta_in_max = np.deg2rad(input_diag_fov / 2.0)
        theta_out_max = np.deg2rad(output_diag_fov / 2.0)

        # Rectilinear virtual focal length.
        # Output FOV cannot reach 180 degrees in rectilinear projection.
        f_rect = r_diag / np.tan(theta_out_max)

        # Destination pixel angle in rectilinear model.
        theta = np.arctan(r_out / f_rect)

        # Equidistant fisheye model:
        # r_src is proportional to angle theta.
        r_src_defish = (theta / theta_in_max) * r_diag

        # Identity mapping keeps the original fisheye image.
        r_src_identity = r_out

        # Blend identity and defish.
        # strength=0 -> original image
        # strength=1 -> stronger defish
        r_src = (1.0 - strength) * r_src_identity + strength * r_src_defish

        r_src = r_src * zoom

        scale = np.ones_like(r_out, dtype=np.float32)
        mask = r_out > 1e-6
        scale[mask] = r_src[mask] / r_out[mask]

        map_x = cx + dx * scale
        map_y = cy + dy * scale

        # Pixels outside source image become black.
        map_x = map_x.astype(np.float32)
        map_y = map_y.astype(np.float32)

        self.defish_map_x = map_x
        self.defish_map_y = map_y

        print("Manual defish maps created.")
        print("Input diagonal FOV:", input_diag_fov)
        print("Output diagonal FOV:", output_diag_fov)
        print("Strength:", strength)
        print("Zoom:", zoom)

    # =====================================================
    # Calibrated fisheye mode
    # =====================================================

    def _apply_calibrated_fisheye_undistort(self, frame):
        if self.fisheye_camera_matrix is None or self.fisheye_dist_coeffs is None:
            if not self.warned_missing_calibration:
                print("Calibrated fisheye mode selected, but calibration values are missing.")
                print("Falling back to manual defish.")
                self.warned_missing_calibration = True

            return self._apply_manual_defish(frame)

        h, w = frame.shape[:2]

        if self.undistort_map1 is None or self.undistort_map2 is None:
            self._build_fisheye_maps(w, h)

        if self.undistort_map1 is None or self.undistort_map2 is None:
            return frame

        undistorted = cv2.remap(
            frame,
            self.undistort_map1,
            self.undistort_map2,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT
        )

        return undistorted

    def _build_fisheye_maps(self, w, h):
        try:
            K = np.array(self.fisheye_camera_matrix, dtype=np.float64)
            D = np.array(self.fisheye_dist_coeffs, dtype=np.float64)

            D = D.reshape(-1, 1)

            dim = (w, h)

            new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K,
                D,
                dim,
                np.eye(3),
                balance=float(self.fisheye_balance)
            )

            map1, map2 = cv2.fisheye.initUndistortRectifyMap(
                K,
                D,
                np.eye(3),
                new_K,
                dim,
                cv2.CV_16SC2
            )

            self.undistort_map1 = map1
            self.undistort_map2 = map2

            print("Calibrated fisheye undistortion maps created.")

        except Exception as e:
            print("Could not build calibrated fisheye maps:")
            print(e)
            self.undistort_map1 = None
            self.undistort_map2 = None
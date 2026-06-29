"""
camera.py — Camera abstraction with fisheye undistortion.

Loads calibration from config, builds undistort maps once at startup,
then returns corrected BGR frames on every read() call.
"""

import cv2
import numpy as np
import time
import config


class Camera:
    def __init__(self):
        self._backend   = config.CAMERA_BACKEND
        self._index     = config.CAMERA_INDEX
        self._width     = config.FRAME_WIDTH
        self._height    = config.FRAME_HEIGHT

        self._cap       = None   # opencv
        self._picam2    = None   # picamera2

        self._map1      = None
        self._map2      = None

        self._build_undistort_maps()
        self._open_camera()

    # ── Setup ─────────────────────────────────

    def _build_undistort_maps(self):
        """Build remap tables from calibration.json. Called once at init."""
        try:
            K, D, image_size = config.load_calibration()
        except FileNotFoundError as e:
            print(f"[camera] WARNING: {e}")
            print("[camera] Running WITHOUT fisheye correction.")
            return

        new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
            K, D, image_size, np.eye(3),
            balance=config.UNDISTORT_BALANCE
        )
        self._map1, self._map2 = cv2.fisheye.initUndistortRectifyMap(
            K, D, np.eye(3), new_K, image_size, cv2.CV_16SC2
        )
        print("[camera] Undistortion maps ready.")

    def _open_camera(self):
        if self._backend == "picamera2":
            self._init_picamera2()
        else:
            self._init_opencv()

    def _init_picamera2(self):
        try:
            from picamera2 import Picamera2
            self._picam2 = Picamera2()
            cfg = self._picam2.create_preview_configuration(
                main={
                    "size":   (self._width, self._height),
                    "format": "RGB888"   # gives BGR-ordered bytes for OpenCV
                }
            )
            self._picam2.configure(cfg)
            self._picam2.start()
            time.sleep(1.0)
            print(f"[camera] picamera2 started ({self._width}x{self._height})")
        except Exception as e:
            print(f"[camera] picamera2 init failed: {e}")
            self._picam2 = None

    def _init_opencv(self):
        self._cap = cv2.VideoCapture(self._index)
        if self._cap.isOpened():
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print(f"[camera] OpenCV camera {self._index} opened.")
        else:
            print(f"[camera] ERROR: could not open camera index {self._index}")

    # ── Public API ────────────────────────────

    def is_opened(self):
        if self._backend == "picamera2":
            return self._picam2 is not None
        return self._cap is not None and self._cap.isOpened()

    def read(self):
        """
        Capture one frame and apply fisheye undistortion.
        Returns (success: bool, frame: np.ndarray BGR).
        """
        ret, frame = self._raw_read()
        if not ret or frame is None:
            return False, None

        if self._map1 is not None and self._map2 is not None:
            frame = cv2.remap(
                frame, self._map1, self._map2,
                interpolation=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT
            )

        return True, frame

    def release(self):
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
            self._picam2 = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # ── Internal ──────────────────────────────

    def _raw_read(self):
        if self._backend == "picamera2":
            if self._picam2 is None:
                return False, None
            try:
                frame = self._picam2.capture_array()
                return True, frame
            except Exception as e:
                print(f"[camera] read error: {e}")
                return False, None
        else:
            if self._cap is None:
                return False, None
            return self._cap.read()

"""
live_calibrate.py — Live fisheye calibration with real-time side-by-side preview

Left  : original fisheye feed with ChArUco marker overlay + ready indicator
Right : undistorted output using the latest calibration

Controls:
    SPACE   : capture frame (only when READY shown) → recalibrate → update right side
    Q / ESC : quit and save calibration.json
"""

import cv2
import numpy as np
import json
import os
import threading
import time

# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────
CAMERA_BACKEND  = "picamera2"       # "picamera2" or "opencv"
CAMERA_INDEX    = 0
FRAME_WIDTH     = 1296
FRAME_HEIGHT    = 972

SQUARES_X       = 11
SQUARES_Y       = 8
SQUARE_LENGTH   = 16.75             # mm
MARKER_LENGTH   = 13.3             # mm
ARUCO_DICT_ID   = cv2.aruco.DICT_4X4_50

MIN_MARKERS     = 6                 # minimum markers to allow capture
MIN_FRAMES_CAL  = 5                 # minimum captured frames before calibration starts
DETECT_EVERY    = 3                 # run marker detection every N frames (CPU saving)

BALANCE         = 0.0               # undistortion FOV balance: 0=full crop, 1=full FOV

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE     = os.path.join(SCRIPT_DIR, "calibration.json")

DISPLAY_HEIGHT  = 540               # each panel height in the window
# ─────────────────────────────────────────────


# ── Camera ────────────────────────────────────

def init_camera():
    if CAMERA_BACKEND == "picamera2":
        from picamera2 import Picamera2
        cam = Picamera2()
        cfg = cam.create_preview_configuration(
            main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(1.0)
        return ("picamera2", cam)
    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return ("opencv", cap)


def read_frame(backend):
    kind, cam = backend
    if kind == "picamera2":
        frame = cam.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        return True, frame
    return cam.read()


def release_camera(backend):
    kind, cam = backend
    if kind == "picamera2":
        cam.stop()
        cam.close()
    else:
        cam.release()


# ── Board & detection ─────────────────────────

def build_board():
    aruco_dict       = cv2.aruco.getPredefinedDictionary(ARUCO_DICT_ID)
    board            = cv2.aruco.CharucoBoard(
        (SQUARES_X, SQUARES_Y), SQUARE_LENGTH, MARKER_LENGTH, aruco_dict
    )
    # CharucoDetector (OpenCV 4.7+) — robust under fisheye distortion
    charuco_detector = cv2.aruco.CharucoDetector(board)
    # Plain ArucoDetector only for the marker overlay drawing
    aruco_detector   = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())
    return board, charuco_detector, aruco_detector


def detect(gray, board, charuco_detector, aruco_detector):
    """
    Detect ChArUco corners using CharucoDetector API (OpenCV 4.7+).
    Much more robust under fisheye distortion than interpolateCornersCharuco.
    """
    # Marker overlay for display only
    mcorners, mids, _ = aruco_detector.detectMarkers(gray)
    n_markers = len(mids) if mids is not None else 0

    n_charuco  = 0
    obj_pts    = None
    img_pts    = None
    ch_corners = None
    ch_ids     = None

    try:
        ch_corners, ch_ids, _, _ = charuco_detector.detectBoard(gray)

        if ch_corners is not None and ch_ids is not None and len(ch_corners) >= 4:
            n_charuco = len(ch_corners)
            try:
                all_obj_3d = board.getChessboardCorners()
                obj_3d     = all_obj_3d[ch_ids.flatten()]
                obj_pts    = obj_3d.reshape(-1, 1, 3).astype(np.float32)
                img_pts    = ch_corners.reshape(-1, 1, 2).astype(np.float32)
            except Exception as e:
                print(f"  [detect] 3D point error: {e}")
    except Exception as e:
        print(f"  [detect] detectBoard failed: {e}")

    return n_markers, n_charuco, obj_pts, img_pts, mcorners, mids, ch_corners, ch_ids


# ── Calibration (runs in background thread) ───

class Calibrator:
    def __init__(self):
        self.lock         = threading.Lock()
        self.all_obj      = []          # list of obj_pts per frame
        self.all_img      = []          # list of img_pts per frame
        self.image_size   = None        # (width, height)

        self.map1         = None
        self.map2         = None
        self.rms          = None
        self.K            = None
        self.D            = None

        self.is_running   = False       # calibration thread active?
        self.status_msg   = "Waiting for frames..."

    def add_frame(self, obj_pts, img_pts, image_size):
        """Add a detected frame and trigger recalibration in background."""
        with self.lock:
            self.all_obj.append(obj_pts)
            self.all_img.append(img_pts)
            self.image_size = image_size
            n = len(self.all_obj)

        print(f"  Frame added: {n} total")

        if n >= MIN_FRAMES_CAL and not self.is_running:
            t = threading.Thread(target=self._run, daemon=True)
            t.start()

    def _run(self):
        self.is_running = True

        with self.lock:
            obj  = list(self.all_obj)
            img  = list(self.all_img)
            size = self.image_size

        n = len(obj)
        self._set_status(f"Calibrating with {n} frames...")
        print(f"  Calibration started with {n} frames...")

        K = np.zeros((3, 3))
        D = np.zeros((4, 1))

        flags = (
            cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC |
            cv2.fisheye.CALIB_CHECK_COND           |
            cv2.fisheye.CALIB_FIX_SKEW
        )
        criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 200, 1e-7)

        try:
            rms, K, D, _, _ = cv2.fisheye.calibrate(
                obj, img, size, K, D, flags=flags, criteria=criteria
            )

            # Build undistortion maps
            new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
                K, D, size, np.eye(3), balance=BALANCE
            )
            map1, map2 = cv2.fisheye.initUndistortRectifyMap(
                K, D, np.eye(3), new_K, size, cv2.CV_16SC2
            )

            with self.lock:
                self.rms  = rms
                self.K    = K.copy()
                self.D    = D.copy()
                self.map1 = map1
                self.map2 = map2

            self._set_status(f"RMS: {rms:.3f}  |  {n} frames")
            print(f"  Calibration done. RMS={rms:.4f}")

        except cv2.error as e:
            self._set_status(f"Cal failed ({n} frames) — add more variety")
            print(f"  Calibration error: {e}")

        self.is_running = False

    def _set_status(self, msg):
        with self.lock:
            self.status_msg = msg

    def get_maps(self):
        with self.lock:
            return self.map1, self.map2

    def get_status(self):
        with self.lock:
            return self.status_msg, len(self.all_obj), self.rms

    def save(self, path):
        with self.lock:
            if self.K is None:
                print("No calibration to save.")
                return False
            data = {
                "note": "Fisheye calibration — cv2.fisheye model",
                "board": {
                    "squares_x": SQUARES_X,
                    "squares_y": SQUARES_Y,
                    "square_length_mm": SQUARE_LENGTH,
                    "marker_length_mm": MARKER_LENGTH
                },
                "image_size":   list(self.image_size),
                "rms_error":    round(float(self.rms), 5),
                "camera_matrix": self.K.tolist(),
                "dist_coeffs":   self.D.flatten().tolist()
            }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Saved: {path}")
        return True


# ── Drawing helpers ───────────────────────────

def draw_left(frame, n_markers, n_charuco, mcorners, mids, ch_corners,
              captured_count, ready):
    out = frame.copy()
    h, w = out.shape[:2]

    # Marker overlays
    if mcorners and mids is not None:
        cv2.aruco.drawDetectedMarkers(out, mcorners, mids)
    if ch_corners is not None:
        cv2.aruco.drawDetectedCornersCharuco(out, ch_corners,
                                              cornerColor=(0, 255, 80))

    # Top bar
    cv2.rectangle(out, (0, 0), (w, 55), (0, 0, 0), -1)
    cv2.putText(out, "ORIGINAL", (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (160, 160, 160), 1)
    cv2.putText(out, f"Captured: {captured_count}  |  Markers: {n_markers}  Corners: {n_charuco}",
                (10, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 220, 0) if ready else (80, 80, 220), 2)

    # Bottom status
    if ready:
        label = "READY  ->  SPACE to capture"
        color = (0, 230, 0)
    else:
        label = f"Show board  (need >= {MIN_MARKERS} markers)"
        color = (80, 80, 220)

    (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.95, 2)
    cv2.rectangle(out, (0, h - 48), (w, h), (0, 0, 0), -1)
    cv2.putText(out, label, ((w - tw) // 2, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.95, color, 2)

    return out


def draw_right(frame, map1, map2, cal_status, n_frames, rms):
    h, w = frame.shape[:2]

    if map1 is not None and map2 is not None:
        out = cv2.remap(frame, map1, map2,
                        interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT)
    else:
        out = frame.copy()
        # Dim + placeholder text
        out = (out * 0.35).astype(np.uint8)
        msg = f"Need {MIN_FRAMES_CAL} frames to start"
        (tw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.putText(out, msg, ((w - tw) // 2, h // 2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 180, 180), 2)

    # Top bar
    rms_str = f"RMS: {rms:.3f}" if rms is not None else "RMS: ---"
    rms_color = (0, 220, 0) if rms is not None and rms < 1.0 else \
                (0, 165, 255) if rms is not None else (160, 160, 160)

    cv2.rectangle(out, (0, 0), (w, 55), (0, 0, 0), -1)
    cv2.putText(out, "UNDISTORTED", (10, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (160, 160, 160), 1)
    cv2.putText(out, rms_str, (10, 46),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, rms_color, 2)

    # Bottom: calibration status
    cv2.rectangle(out, (0, h - 48), (w, h), (0, 0, 0), -1)
    cv2.putText(out, cal_status, (10, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 180, 180), 1)

    return out


def scale_to_height(img, target_h):
    h, w = img.shape[:2]
    scale = target_h / h
    return cv2.resize(img, (int(w * scale), target_h), interpolation=cv2.INTER_LINEAR)


# ── Main loop ─────────────────────────────────

def main():
    print("Initializing camera...")
    backend = init_camera()
    board, charuco_detector, aruco_detector = build_board()
    calibrator = Calibrator()

    cv2.namedWindow("Live Calibration", cv2.WINDOW_NORMAL)

    frame_idx    = 0
    n_markers    = 0
    n_charuco    = 0
    last_mcorners  = None
    last_mids      = None
    last_chcorners = None
    last_obj_pts   = None
    last_img_pts   = None

    print("Ready.")
    print(f"  SPACE to capture (when READY shown)  |  Q/ESC to quit & save")
    print()

    while True:
        ret, frame = read_frame(backend)
        if not ret or frame is None:
            continue

        frame_idx += 1
        h, w = frame.shape[:2]
        image_size = (w, h)

        # Detection every N frames
        if frame_idx % DETECT_EVERY == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            n_markers, n_charuco, obj_pts, img_pts, \
                last_mcorners, last_mids, last_chcorners, _ = \
                detect(gray, board, charuco_detector, aruco_detector)
            last_obj_pts = obj_pts
            last_img_pts = img_pts

        ready = (n_markers >= MIN_MARKERS and last_obj_pts is not None)

        # Get calibration state
        map1, map2      = calibrator.get_maps()
        cal_status, n_captured, rms = calibrator.get_status()

        # Build display
        left  = draw_left(frame, n_markers, n_charuco,
                          last_mcorners, last_mids, last_chcorners,
                          n_captured, ready)
        right = draw_right(frame, map1, map2, cal_status, n_captured, rms)

        left_s  = scale_to_height(left,  DISPLAY_HEIGHT)
        right_s = scale_to_height(right, DISPLAY_HEIGHT)

        combined = np.hstack([left_s, right_s])

        # Divider line
        mid_x = left_s.shape[1]
        cv2.line(combined, (mid_x, 0), (mid_x, DISPLAY_HEIGHT), (60, 60, 60), 2)

        cv2.imshow("Live Calibration", combined)

        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):
            break

        if key == ord(' '):
            if n_markers < MIN_MARKERS:
                print(f"  Skipped: only {n_markers} markers (need {MIN_MARKERS})")
            elif last_obj_pts is None:
                print(f"  Skipped: {n_markers} markers found but ChArUco interpolation failed")
                print(f"           n_charuco={n_charuco} — check board params or image quality")
            elif calibrator.is_running:
                print("  Skipped: calibration in progress, wait a moment")
            else:
                calibrator.add_frame(last_obj_pts, last_img_pts, image_size)

                # Flash feedback
                flash = combined.copy()
                flash[:] = (255, 255, 255)
                cv2.imshow("Live Calibration", flash)
                cv2.waitKey(100)

    # Quit: save calibration
    print("\nSaving calibration...")
    saved = calibrator.save(OUTPUT_FILE)
    if saved:
        print(f"Done. Calibration saved to {OUTPUT_FILE}")
    else:
        print("No calibration was completed (not enough frames).")

    release_camera(backend)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
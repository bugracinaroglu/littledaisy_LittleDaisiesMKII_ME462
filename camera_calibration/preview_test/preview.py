"""
preview.py  —  Validate calibration result with live side-by-side preview

Left  : RAW fisheye frame straight from camera (no processing)
Right : Undistorted output using calibration.json

Usage:
    python preview.py                   # live camera, full FOV (no crop)
    python preview.py --balance 0.5     # compromise: less black border, some crop
    python preview.py --balance 0.0     # no black borders, FOV is cropped
    python preview.py --image foto.jpg  # single image mode
"""

import cv2
import numpy as np
import json
import sys
import os
import argparse
import time

SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
CALIB_FILE     = os.path.join(SCRIPT_DIR, "calibration.json")

CAMERA_BACKEND = "picamera2"    # "picamera2" or "opencv"
CAMERA_INDEX   = 0

# balance controls how much of the undistorted image is visible:
#   0.0 -> crop to valid pixels only  (no black borders, narrower FOV)
#   0.5 -> compromise
#   1.0 -> full original FOV preserved (black borders at edges, no crop)
BALANCE        = 0


# ── Calibration ───────────────────────────────

def load_calibration(path):
    if not os.path.exists(path):
        print(f"ERROR: '{path}' not found. Run live_calibrate.py first.")
        sys.exit(1)

    with open(path) as f:
        data = json.load(f)

    K          = np.array(data["camera_matrix"], dtype=np.float64)
    D          = np.array(data["dist_coeffs"],   dtype=np.float64).reshape(-1, 1)
    image_size = tuple(data["image_size"])   # (width, height)
    rms        = data.get("rms_error", "?")

    print(f"Calibration loaded: {path}")
    print(f"  Image size : {image_size[0]}x{image_size[1]}")
    print(f"  RMS error  : {rms}")
    print(f"  K =\n{K}")
    print(f"  D = {D.flatten()}")
    return K, D, image_size


def build_undistort_maps(K, D, image_size, balance):
    """Build remap lookup tables once; apply to every frame cheaply."""
    new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(
        K, D, image_size, np.eye(3), balance=balance
    )
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(
        K, D, np.eye(3), new_K, image_size, cv2.CV_16SC2
    )
    return map1, map2


def undistort(frame, map1, map2):
    return cv2.remap(
        frame, map1, map2,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT
    )


# ── Display ───────────────────────────────────

def side_by_side(raw, fixed):
    """Stack two frames horizontally with labels."""
    h = max(raw.shape[0], fixed.shape[0])

    def pad(img):
        dh = h - img.shape[0]
        return cv2.copyMakeBorder(img, 0, dh, 0, 0, cv2.BORDER_CONSTANT) if dh > 0 else img

    left  = pad(raw.copy())
    right = pad(fixed.copy())

    cv2.putText(left,  "RAW",      (15, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 80, 255),  2)
    cv2.putText(right, "FIXED",    (15, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 60),  2)

    return np.hstack([left, right])


# ── Camera ────────────────────────────────────

def init_camera(width, height):
    if CAMERA_BACKEND == "picamera2":
        from picamera2 import Picamera2
        cam = Picamera2()
        # Use RGB888 — picamera2 outputs this in BGR memory order,
        # which is exactly what OpenCV expects. No cvtColor needed.
        cfg = cam.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        cam.configure(cfg)
        cam.start()
        time.sleep(1.0)
        return ("picamera2", cam)
    else:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return ("opencv", cap)


def read_frame(backend_tuple):
    kind, cam = backend_tuple
    if kind == "picamera2":
        # RGB888 from picamera2 is already in BGR memory order for OpenCV.
        frame = cam.capture_array()
        return True, frame
    return cam.read()


def release_camera(backend_tuple):
    kind, cam = backend_tuple
    if kind == "picamera2":
        cam.stop()
        cam.close()
    else:
        cam.release()


# ── Single image mode ─────────────────────────

def run_image_mode(image_path, map1, map2):
    img = cv2.imread(image_path)
    if img is None:
        print(f"ERROR: could not read '{image_path}'")
        sys.exit(1)

    fixed    = undistort(img, map1, map2)
    combined = side_by_side(img, fixed)

    max_w = 1800
    if combined.shape[1] > max_w:
        scale    = max_w / combined.shape[1]
        combined = cv2.resize(combined, None, fx=scale, fy=scale)

    cv2.imshow("Fisheye Calibration Preview", combined)
    print("Press any key to close.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# ── Live camera mode ──────────────────────────

def run_live_mode(map1, map2, image_size):
    width, height = image_size
    print(f"\nStarting live mode ({CAMERA_BACKEND})...")
    print("Q / ESC : quit   |   S : save snapshot")

    backend = init_camera(width, height)
    cv2.namedWindow("Fisheye Calibration Preview", cv2.WINDOW_NORMAL)

    display_h = 540
    display_w = int(width * (display_h / height) * 2)   # two panels side by side
    cv2.resizeWindow("Fisheye Calibration Preview", display_w, display_h)

    snap_dir   = SCRIPT_DIR
    snap_count = 0

    while True:
        ret, frame = read_frame(backend)
        if not ret or frame is None:
            continue

        fixed    = undistort(frame, map1, map2)
        combined = side_by_side(frame, fixed)

        cv2.putText(combined, "S: snapshot   Q: quit",
                    (15, combined.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (180, 180, 180), 1)

        cv2.imshow("Fisheye Calibration Preview", combined)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord('q'), 27):
            break
        if key == ord('s'):
            fname = os.path.join(snap_dir, f"preview_snap_{snap_count:03d}.jpg")
            cv2.imwrite(fname, combined)
            snap_count += 1
            print(f"Saved: {fname}")

    release_camera(backend)
    cv2.destroyAllWindows()


# ── Main ──────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fisheye calibration preview")
    parser.add_argument("--image",   type=str,   default=None,
                        help="Single image mode: --image path/to/photo.jpg")
    parser.add_argument("--balance", type=float, default=BALANCE,
                        help="FOV balance: 0.0=crop to valid, 0.5=compromise, 1.0=full FOV (default: 1.0)")
    args = parser.parse_args()

    K, D, image_size = load_calibration(CALIB_FILE)

    print(f"\nBuilding undistortion maps (balance={args.balance})...")
    map1, map2 = build_undistort_maps(K, D, image_size, args.balance)
    print("Ready.\n")

    if args.image:
        run_image_mode(args.image, map1, map2)
    else:
        run_live_mode(map1, map2, image_size)


if __name__ == "__main__":
    main()
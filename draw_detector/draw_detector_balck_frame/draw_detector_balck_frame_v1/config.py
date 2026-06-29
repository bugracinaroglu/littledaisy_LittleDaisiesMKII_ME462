"""
config.py — Central configuration for the drawing detector pipeline.

All tunable parameters live here. Import this module everywhere instead
of hard-coding values in individual files.
"""

import os
import json
import numpy as np

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
CALIBRATION_FILE = os.path.join(SCRIPT_DIR, "calibration.json")
OUTPUT_DIR      = os.path.join(SCRIPT_DIR, "output")

# ─────────────────────────────────────────────
# Camera
# ─────────────────────────────────────────────
CAMERA_BACKEND  = "picamera2"   # "picamera2" or "opencv"
CAMERA_INDEX    = 0             # opencv only
FRAME_WIDTH     = 1296
FRAME_HEIGHT    = 972

# Fisheye undistortion FOV balance:
#   0.0 = crop to valid pixels (no black borders)
#   1.0 = keep full original FOV (black borders at edges)
UNDISTORT_BALANCE = 0.0

# ─────────────────────────────────────────────
# Frame detector  (white surface finder)
# ─────────────────────────────────────────────

# Minimum brightness to consider a pixel "white" (0-255 grayscale)
WHITE_THRESHOLD     = 180

# The white surface must cover at least this fraction of the frame
MIN_AREA_RATIO      = 0.05

# Polygon approximation tolerance (fraction of contour perimeter)
POLY_APPROX_EPS     = 0.02

# How many consecutive frames without detection before the lock is released
LOCK_TIMEOUT_FRAMES = 30

# Output size of the warped (flattened) surface in pixels (width, height)
SURFACE_OUTPUT_SIZE = (800, 600)

# ─────────────────────────────────────────────
# Drawing detector  (stroke finder)
# ─────────────────────────────────────────────

# Pixels darker than this are considered "drawn" on the white surface
DRAW_THRESHOLD      = 100

# Morphological kernel size for noise removal
MORPH_KERNEL_SIZE   = 3

# Minimum contour area to count as a stroke (ignore dust/noise)
MIN_STROKE_AREA     = 20

# How much to simplify stroke polylines (Douglas-Peucker epsilon, pixels)
STROKE_SIMPLIFY_EPS = 2.0

# ─────────────────────────────────────────────
# Calibration loader
# ─────────────────────────────────────────────

def load_calibration():
    """
    Load camera_matrix (K) and dist_coeffs (D) from calibration.json.
    Returns (K, D, image_size) as numpy arrays.
    Exits with a clear message if the file is missing.
    """
    if not os.path.exists(CALIBRATION_FILE):
        raise FileNotFoundError(
            f"Calibration file not found: {CALIBRATION_FILE}\n"
            "Run live_calibrate.py first."
        )

    with open(CALIBRATION_FILE) as f:
        data = json.load(f)

    K          = np.array(data["camera_matrix"], dtype=np.float64)
    D          = np.array(data["dist_coeffs"],   dtype=np.float64).reshape(-1, 1)
    image_size = tuple(data["image_size"])  # (width, height)

    print(f"[config] Calibration loaded — RMS: {data.get('rms_error', '?')}")
    return K, D, image_size

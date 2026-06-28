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
# Frame detector — general
# ─────────────────────────────────────────────

# The detected surface must cover at least this fraction of the frame
MIN_AREA_RATIO        = 0.04

# Polygon approximation tolerance (fraction of contour perimeter)
POLY_APPROX_EPS       = 0.02

# Minimum convexity (area / hull_area) for a valid quad
MIN_QUAD_SOLIDITY     = 0.80

# Output size of the warped (flattened) surface in pixels (width, height)
SURFACE_OUTPUT_SIZE   = (800, 600)

# ─────────────────────────────────────────────
# Frame detector — "white interior + dark border" (PRIMARY strategy)
# ─────────────────────────────────────────────

# Pixels brighter than this are candidates for "paper interior" (0-255).
# Lower if the white area looks dim on camera. Raise if the table is bright.
WHITE_THRESHOLD       = 170

# Pixels darker than this are considered "border" (paper edge / tablet bezel).
# Doesn't have to be pure black — anything noticeably darker than the paper.
BORDER_DARK_THRESH    = 110

# Quad validation: minimum mean brightness INSIDE the detected quad.
# (Filters out detections that wrap around dark areas.)
MIN_INNER_BRIGHTNESS  = 150

# Quad validation: maximum brightness std-dev INSIDE the detected quad.
# (Paper interior should be fairly uniform, not chaotic.)
MAX_INNER_STDDEV      = 60

# Quad validation: mean brightness in the OUTER border ring must be
# at least this much DARKER than the inner mean.
# (Ensures the white blob is actually framed by a dark border.)
MIN_BORDER_CONTRAST   = 25

# Width of the outer "border ring" used to verify dark surroundings
# (as a fraction of the quad's average edge length).
BORDER_RING_FRACTION  = 0.10

# Morphological cleanup kernel sizes
MORPH_CLOSE_K         = 15   # closes small gaps inside the white region
MORPH_OPEN_K          = 9    # removes small bright noise

# ─────────────────────────────────────────────
# Frame detector — fallback strategies
# ─────────────────────────────────────────────

# Hough lines parameters (only used by hough fallback)
HOUGH_THRESHOLD       = 60
HOUGH_MIN_LINE_FRAC   = 0.15   # min line length as fraction of min(h,w)
HOUGH_MAX_LINE_GAP    = 20

# CLAHE (local contrast enhancement)
CLAHE_CLIP            = 3.0
CLAHE_GRID            = (8, 8)

# Adaptive threshold block size divisor (block = frame_width // this, made odd)
ADAPTIVE_BLOCK_DIV    = 10
ADAPTIVE_C            = -5     # adaptive threshold offset

# HSV white range (sat <= S_MAX, val >= V_MIN)
HSV_SAT_MAX           = 50
HSV_VAL_MIN           = 160

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
"""
config.py — Central configuration for the draw server.

All tunable parameters live here. Edit values here, not in other files.
"""

import os

# ─────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR  = os.path.join(SCRIPT_DIR, "static")
OUTPUT_DIR  = os.path.join(SCRIPT_DIR, "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─────────────────────────────────────────────
# Server
# ─────────────────────────────────────────────
HOST = "0.0.0.0"   # listen on all interfaces (so tablet can reach Pi)
PORT = 8000

# ─────────────────────────────────────────────
# Processor — drawing post-processing on "Detect"
# ─────────────────────────────────────────────

# Smoothing — light 3-point moving average pass to reduce shake.
# 0 = disabled, 1 = one pass, 2 = two passes (smoother but more lag).
SMOOTHING_PASSES        = 1

# Douglas-Peucker simplification epsilon (in normalized canvas units, 0..1).
# Smaller = more points preserved, larger = more aggressive simplification.
# 0.002 ≈ ~1 px on a 500 px canvas — a good light default.
SIMPLIFY_EPSILON        = 0.002

# Minimum points per stroke. Strokes shorter than this are dropped
# (filters out accidental taps / single-point artifacts).
MIN_STROKE_POINTS       = 3

# Minimum total stroke length (normalized 0..1). Strokes shorter than this
# (in total path length) are dropped. 0.01 ≈ 1% of canvas width.
MIN_STROKE_LENGTH       = 0.01

# Save raw strokes alongside processed strokes in the JSON output.
# Set False if you only want the processed version.
SAVE_RAW_STROKES        = True

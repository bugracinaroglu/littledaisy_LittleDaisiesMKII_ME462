"""Central configuration for the LittleDaisy drawing server."""

import os

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Server
HOST = "0.0.0.0"
PORT = 8000

# Native Raspberry Pi preview
PREVIEW_PANEL_SIZE = 560
PREVIEW_HEADER_HEIGHT = 42
PREVIEW_FOOTER_HEIGHT = 58
PREVIEW_REFRESH_MS = 16
PREVIEW_LINE_THICKNESS = 2
# Turn this on only while checking sample density; dots can make dense drawings look noisy.
PREVIEW_SHOW_SAMPLE_POINTS = False

# Processing mode used when Detect is pressed.
# "raw" preserves the incoming tablet path and point order as closely as possible.
# "filtered" enables the optional smoothing/simplification settings below.
PROCESSING_MODE = "raw"

# Optional filtered mode settings
SMOOTHING_PASSES = 0
SIMPLIFY_EPSILON = 0.0002
MIN_STROKE_POINTS = 1
MIN_STROKE_LENGTH = 0.0

# Save raw strokes alongside detected/output strokes.
SAVE_RAW_STROKES = True

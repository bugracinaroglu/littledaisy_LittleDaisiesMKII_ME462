"""Central configuration for the LittleDaisy drawing server."""

from __future__ import annotations

import os

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
COMPARISON_STATE_DIR = os.path.join(SCRIPT_DIR, "comparison_state")
ROBOT_JOBS_DIR = os.path.join(SCRIPT_DIR, "robot_jobs")
ROBOT_COMMITTED_STATE_FILE = os.path.join(
    COMPARISON_STATE_DIR, "robot_committed_state.json"
)
LATEST_ROBOT_JOB_FILE = os.path.join(ROBOT_JOBS_DIR, "latest_job.json")

for directory in (OUTPUT_DIR, COMPARISON_STATE_DIR, ROBOT_JOBS_DIR):
    os.makedirs(directory, exist_ok=True)

# Server
HOST = "0.0.0.0"
PORT = 8000

# Native Raspberry Pi preview
PREVIEW_PANEL_SIZE = 440
PREVIEW_HEADER_HEIGHT = 50
PREVIEW_FOOTER_HEIGHT = 72
PREVIEW_REFRESH_MS = 16
PREVIEW_LINE_THICKNESS = 2
PREVIEW_SHOW_SAMPLE_POINTS = False

# Processing mode used when Detect is pressed.
# "raw" preserves the incoming tablet path and point order as closely as possible.
# "filtered" enables the optional smoothing/simplification settings below.
PROCESSING_MODE = "raw"
SMOOTHING_PASSES = 0
SIMPLIFY_EPSILON = 0.0002
MIN_STROKE_POINTS = 1
MIN_STROKE_LENGTH = 0.0

# Coordinate convention written to every output drawing JSON.
OUTPUT_COORDINATE_SYSTEM = "normalized_bottom_left_origin"

# Robot job planning
# Can be changed at runtime with: set_mode difference / set_mode full_redraw
DEFAULT_ROBOT_JOB_MODE = "difference"
STROKE_SAME_TOLERANCE = 1e-8

# Until a physical robot transport is connected, the terminal command simulates
# a successful robot acknowledgement and commits the target drawing state.
SIMULATE_ROBOT_ACK = True

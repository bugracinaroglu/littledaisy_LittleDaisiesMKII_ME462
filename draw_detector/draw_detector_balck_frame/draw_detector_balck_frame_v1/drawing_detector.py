"""
drawing_detector.py — Detects drawn strokes on the flat (warped) surface.

Input  : warped BGR image from frame_detector (white background, dark drawing)
Output : list of strokes, each stroke being an (N, 2) int array of points
         + a rendered visualization image

Stroke storage format (JSON-serializable):
    {
        "surface_size": [width, height],
        "strokes": [
            [[x, y], [x, y], ...],   # stroke 1
            [[x, y], [x, y], ...],   # stroke 2
            ...
        ]
    }
"""

import cv2
import numpy as np
import json
import os
import time
import config


class DrawingDetector:
    """
    Extracts strokes from a perspective-corrected white surface image.

    Usage:
        dd = DrawingDetector()
        strokes, vis = dd.process(warped)
        # strokes : List[np.ndarray shape (N,2)]
        # vis     : BGR image with drawing highlighted on white background
    """

    def __init__(self):
        self._kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (config.MORPH_KERNEL_SIZE, config.MORPH_KERNEL_SIZE)
        )

    def process(self, warped):
        """
        Detect strokes in the warped surface.
        Returns (strokes, vis).
        strokes : list of (N, 2) int32 arrays  — empty list if nothing found
        vis     : BGR visualization on white canvas
        """
        if warped is None:
            return [], None

        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)

        # Threshold: dark pixels on white background
        _, mask = cv2.threshold(
            gray, config.DRAW_THRESHOLD, 255, cv2.THRESH_BINARY_INV
        )

        # Remove noise
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  self._kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self._kernel)

        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        strokes = []
        for cnt in contours:
            if cv2.contourArea(cnt) < config.MIN_STROKE_AREA:
                continue

            # Simplify the contour polyline
            eps      = config.STROKE_SIMPLIFY_EPS
            approx   = cv2.approxPolyDP(cnt, eps, closed=False)
            pts      = approx.reshape(-1, 2).astype(np.int32)
            strokes.append(pts)

        vis = self._render(warped.shape, strokes)
        return strokes, vis

    def _render(self, shape, strokes):
        """Render strokes as black lines on a white canvas."""
        h, w = shape[:2]
        canvas = np.full((h, w, 3), 255, dtype=np.uint8)

        for stroke in strokes:
            if len(stroke) < 2:
                # Single point — draw a dot
                cv2.circle(canvas, tuple(stroke[0]), 3, (0, 0, 0), -1)
            else:
                cv2.polylines(canvas, [stroke], isClosed=False,
                              color=(0, 0, 0), thickness=2)

        return canvas

    # ── Persistence ───────────────────────────

    def save(self, strokes, path=None):
        """
        Save strokes to a JSON file.
        Default path: output/drawing_<timestamp>.json
        """
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)

        if path is None:
            ts   = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(config.OUTPUT_DIR, f"drawing_{ts}.json")

        w, h = config.SURFACE_OUTPUT_SIZE
        data = {
            "surface_size": [w, h],
            "strokes": [pts.tolist() for pts in strokes]
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        print(f"[drawing_detector] Saved {len(strokes)} strokes -> {path}")
        return path

    @staticmethod
    def load(path):
        """
        Load strokes from a previously saved JSON file.
        Returns List[np.ndarray shape (N, 2)].
        """
        with open(path) as f:
            data = json.load(f)

        strokes = [np.array(s, dtype=np.int32) for s in data["strokes"]]
        print(f"[drawing_detector] Loaded {len(strokes)} strokes from {path}")
        return strokes

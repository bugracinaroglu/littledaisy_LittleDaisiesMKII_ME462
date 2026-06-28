"""
visualizer.py — Three-panel display for the drawing detector pipeline.

Left   : undistorted camera frame + surface outline overlay
Middle : perspective-corrected (warped) surface
Right  : detected drawing on white canvas
"""

import cv2
import numpy as np
import config

PANEL_HEIGHT  = 480     # display height for each panel (pixels)
LABEL_H       = 32      # height of the label bar above each panel
DIVIDER_COLOR = (50, 50, 50)
DIVIDER_W     = 2


def _scale_to_height(img, target_h):
    h, w  = img.shape[:2]
    scale = target_h / h
    new_w = max(1, int(w * scale))
    return cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_LINEAR)


def _add_label(img, text, color=(200, 200, 200)):
    """Add a dark label bar on top of a panel."""
    h, w = img.shape[:2]
    bar  = np.zeros((LABEL_H, w, 3), dtype=np.uint8)
    cv2.putText(bar, text, (10, LABEL_H - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1)
    return np.vstack([bar, img])


def _placeholder(width, height, text):
    """Grey panel shown when a stage has no output yet."""
    panel = np.full((height, width, 3), 40, dtype=np.uint8)
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.75, 1)
    tx = (width  - tw) // 2
    ty = (height + th) // 2
    cv2.putText(panel, text, (tx, ty),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75, (120, 120, 120), 1)
    return panel


class Visualizer:
    """
    Builds and displays the three-panel view each frame.

    Usage:
        vis = Visualizer()
        vis.show(raw_annotated, warped, drawing_vis)
        # Returns the key pressed (cv2.waitKey result) so main can handle it.
    """

    def __init__(self):
        cv2.namedWindow("Drawing Detector", cv2.WINDOW_NORMAL)

        # Estimate a reasonable window width from config surface size
        sw, sh   = config.SURFACE_OUTPUT_SIZE
        cam_w    = int(config.FRAME_WIDTH  * (PANEL_HEIGHT / config.FRAME_HEIGHT))
        surf_w   = int(sw * (PANEL_HEIGHT / sh))
        total_w  = cam_w + surf_w + surf_w + DIVIDER_W * 2
        cv2.resizeWindow("Drawing Detector", total_w, PANEL_HEIGHT + LABEL_H)

        self._cam_w  = cam_w
        self._surf_w = surf_w

    def show(self, raw_annotated, warped, drawing_vis, n_strokes=0, locked=False, status=""):
        """
        Compose and display one frame.

        raw_annotated : BGR frame with surface outline drawn on it
        warped        : warped surface BGR image or None
        drawing_vis   : drawing-on-white BGR image or None
        n_strokes     : number of detected strokes (for HUD)
        locked        : whether frame_detector is using a locked homography
        """
        # ── Left panel ────────────────────────
        left = _scale_to_height(raw_annotated, PANEL_HEIGHT)
        left = _add_label(left, "RAW  (undistorted + surface overlay)")

        # ── Middle panel ──────────────────────
        if warped is not None:
            mid = _scale_to_height(warped, PANEL_HEIGHT)
        else:
            mid = _placeholder(self._surf_w, PANEL_HEIGHT, "Searching for surface...")
        mid = _add_label(mid, f"SURFACE  {status}",
                         color=(0, 160, 255) if locked else (0, 220, 0))

        # ── Right panel ───────────────────────
        if drawing_vis is not None:
            right = _scale_to_height(drawing_vis, PANEL_HEIGHT)
        else:
            right = _placeholder(self._surf_w, PANEL_HEIGHT, "No surface yet")
        right = _add_label(right, f"DRAWING  ({n_strokes} stroke{'s' if n_strokes != 1 else ''})")

        # ── Compose ───────────────────────────
        divider = np.full((PANEL_HEIGHT + LABEL_H, DIVIDER_W, 3),
                          DIVIDER_COLOR, dtype=np.uint8)

        # Pad panels to equal height (label bar may differ if resized)
        def eq_h(a, b):
            ha, hb = a.shape[0], b.shape[0]
            if ha < hb:
                a = np.vstack([a, np.zeros((hb - ha, a.shape[1], 3), dtype=np.uint8)])
            elif hb < ha:
                b = np.vstack([b, np.zeros((ha - hb, b.shape[1], 3), dtype=np.uint8)])
            return a, b

        left, mid   = eq_h(left,  mid)
        mid,  right = eq_h(mid,   right)

        combined = np.hstack([left, divider, mid, divider, right])

        # ── HUD bottom bar ────────────────────
        hud = f"S: save drawing   R: reset surface lock   Q/ESC: quit"
        cv2.putText(combined, hud,
                    (15, combined.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)

        cv2.imshow("Drawing Detector", combined)
        return cv2.waitKey(1) & 0xFF

    def close(self):
        cv2.destroyAllWindows()
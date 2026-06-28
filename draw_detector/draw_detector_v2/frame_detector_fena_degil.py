"""
frame_detector.py — Robust white surface detector with perspective correction.

Detection strategies (tried in order):
  1. Hough Lines  : 4 dominant lines -> intersect -> quad corners.
  2. LAB + morph  : luminance gradient on LAB-L channel.
  3. Adaptive thr : local adaptive threshold.
  4. Edge / Canny : Canny + contour with CLAHE.
  5. HSV white    : low-saturation + high-value mask.
  6. Brightness   : simple global threshold (last resort).
  7. Manual       : user clicks 4 corners with the mouse (M key).

NO LOCKING: detection runs on every frame so the surface tracks live.
If a frame fails detection, the previous corners are kept on screen only
for visual continuity (not as a "lock") and the next frame retries fresh.

Controls:
  R : clear current corners and manual selection
  M : enter manual corner-click mode (corners stay until R or new M)
"""

import cv2
import numpy as np
import config


# ─────────────────────────────────────────────────────────────────────────────
# Corner helpers
# ─────────────────────────────────────────────────────────────────────────────

def _order_corners(pts):
    pts  = np.array(pts, dtype=np.float32).reshape(4, 2)
    rect = np.zeros((4, 2), dtype=np.float32)
    s       = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff    = np.diff(pts, axis=1).flatten()
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _quad_area(corners):
    return cv2.contourArea(corners.reshape(-1, 1, 2).astype(np.float32))


def _valid_quad(corners, frame_area):
    area = _quad_area(corners)
    if area < frame_area * config.MIN_AREA_RATIO:
        return False
    hull_area = cv2.contourArea(
        cv2.convexHull(corners.reshape(-1, 1, 2).astype(np.float32))
    )
    return hull_area > 0 and (area / hull_area) > 0.7


def _build_homography(corners, output_size):
    w, h = output_size
    dst  = np.array([[0,0],[w-1,0],[w-1,h-1],[0,h-1]], dtype=np.float32)
    H, _ = cv2.findHomography(corners, dst, method=0)
    return H


def _contour_to_quad(cnt):
    hull = cv2.convexHull(cnt)
    peri = cv2.arcLength(hull, True)
    for eps in [0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20]:
        approx = cv2.approxPolyDP(hull, eps * peri, True)
        if len(approx) == 4:
            return _order_corners(approx)
        if len(approx) < 4:
            break
    if len(hull) >= 4:
        h    = hull.reshape(-1, 2).astype(np.float32)
        s    = h.sum(axis=1)
        diff = np.diff(h, axis=1).flatten()
        return _order_corners([h[np.argmin(s)], h[np.argmin(diff)],
                                h[np.argmax(s)], h[np.argmax(diff)]])
    return None


def _best_quad_from_contours(contours, frame_area):
    best, best_area = None, 0
    for cnt in contours:
        if cv2.contourArea(cnt) < frame_area * config.MIN_AREA_RATIO:
            continue
        corners = _contour_to_quad(cnt)
        if corners is None or not _valid_quad(corners, frame_area):
            continue
        area = _quad_area(corners)
        if area > best_area:
            best, best_area = corners, area
    return best


def _morph_clean(mask, close_k=15, open_k=9):
    kc = cv2.getStructuringElement(cv2.MORPH_RECT, (close_k, close_k))
    ko = cv2.getStructuringElement(cv2.MORPH_RECT, (open_k,  open_k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kc)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  ko)
    return mask


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1: Hough Lines
# ─────────────────────────────────────────────────────────────────────────────

def _line_angle(x1, y1, x2, y2):
    return np.degrees(np.arctan2(y2-y1, x2-x1)) % 180


def _line_to_params(x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1
    length = np.hypot(dx, dy)
    if length < 1e-6:
        return None
    nx, ny = -dy/length, dx/length
    return nx*x1+ny*y1, np.arctan2(ny, nx)


def _intersect_lines(l1, l2):
    r1, t1 = l1; r2, t2 = l2
    A = np.array([[np.cos(t1), np.sin(t1)],
                  [np.cos(t2), np.sin(t2)]])
    b = np.array([r1, r2])
    det = A[0,0]*A[1,1] - A[0,1]*A[1,0]
    if abs(det) < 1e-6: return None
    return ((A[1,1]*b[0]-A[0,1]*b[1])/det,
            (A[0,0]*b[1]-A[1,0]*b[0])/det)


def _detect_hough(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe   = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray    = clahe.apply(gray)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    median  = np.median(blurred)
    lo      = int(max(0,   0.67 * median))
    hi      = int(min(255, 1.33 * median))
    edges   = cv2.Canny(blurred, lo, hi)
    edges   = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    h, w   = frame.shape[:2]
    segments = cv2.HoughLinesP(edges, 1, np.pi/180, 60,
                                minLineLength=min(h, w)*0.15, maxLineGap=20)
    if segments is None or len(segments) < 4:
        return None

    segs   = [tuple(s[0]) for s in segments]
    angles = [_line_angle(*s) for s in segs]
    params = [_line_to_params(*s) for s in segs]

    a0 = angles[0]
    diffs = [min(abs(a-a0), 180-abs(a-a0)) for a in angles]
    pivot = int(np.argmax(diffs))
    if diffs[pivot] < 10:
        return None
    a1 = angles[pivot]

    groups = [[], []]
    for a, p in zip(angles, params):
        if p is None: continue
        d0 = min(abs(a-a0), 180-abs(a-a0))
        d1 = min(abs(a-a1), 180-abs(a-a1))
        groups[0 if d0 < d1 else 1].append(p)

    def dominant(g):
        if len(g) < 2: return g
        s = sorted(g, key=lambda x: x[0])
        return [s[0], s[-1]]

    la, lb = dominant(groups[0]), dominant(groups[1])
    if len(la) < 2 or len(lb) < 2:
        return None

    corners = []
    for l1 in la:
        for l2 in lb:
            pt = _intersect_lines(l1, l2)
            if pt is None: continue
            x, y = pt
            if -w*0.3 <= x <= w*1.3 and -h*0.3 <= y <= h*1.3:
                corners.append([x, y])

    if len(corners) != 4:
        return None

    ordered = _order_corners(np.array(corners, dtype=np.float32))
    return ordered if _valid_quad(ordered, h*w) else None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2: LAB + morph gradient
# ─────────────────────────────────────────────────────────────────────────────

def _detect_lab_morph(frame):
    L    = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)[:, :, 0]
    k5   = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    grad = cv2.morphologyEx(L, cv2.MORPH_GRADIENT, k5)
    _, mask = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = _morph_clean(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3: Adaptive threshold
# ─────────────────────────────────────────────────────────────────────────────

def _detect_adaptive(frame):
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray  = clahe.apply(gray)
    block = max(51, (gray.shape[1] // 10) | 1)
    mask  = cv2.adaptiveThreshold(gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block, -5)
    mask  = _morph_clean(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 4: Edge / Canny
# ─────────────────────────────────────────────────────────────────────────────

def _detect_edge(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe   = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray    = clahe.apply(gray)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    median  = np.median(blurred)
    edges   = cv2.Canny(blurred, int(max(0, 0.67*median)),
                                  int(min(255, 1.33*median)))
    edges   = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 5: HSV white
# ─────────────────────────────────────────────────────────────────────────────

def _detect_hsv(frame):
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 0, 160]), np.array([180, 50, 255]))
    mask = _morph_clean(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 6: Brightness
# ─────────────────────────────────────────────────────────────────────────────

def _detect_brightness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, config.WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    mask = _morph_clean(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


_STRATEGIES = [
    ("hough",       _detect_hough),
    ("lab+morph",   _detect_lab_morph),
    ("adaptive",    _detect_adaptive),
    ("edge",        _detect_edge),
    ("hsv",         _detect_hsv),
    ("brightness",  _detect_brightness),
]


# ─────────────────────────────────────────────────────────────────────────────
# Manual corner picker
# ─────────────────────────────────────────────────────────────────────────────

class _ManualSelector:
    LABELS = ["TL", "TR", "BR", "BL"]

    def __init__(self):
        self._pts = []
        self.is_active = False
        self.is_done = False

    def start(self, window_name):
        self._pts = []; self.is_active = True; self.is_done = False
        cv2.setMouseCallback(window_name, self._on_click)
        print("[frame_detector] Manual: click TL, TR, BR, BL")

    def stop(self, window_name):
        cv2.setMouseCallback(window_name, lambda *_: None)
        self.is_active = False

    def _on_click(self, ev, x, y, *_):
        if ev == cv2.EVENT_LBUTTONDOWN and self.is_active:
            self._pts.append([x, y])
            print(f"  {self.LABELS[len(self._pts)-1]}: ({x}, {y})")
            if len(self._pts) == 4:
                self.is_done = True; self.is_active = False

    def get_corners(self):
        return _order_corners(np.array(self._pts, dtype=np.float32)) if self.is_done else None

    def draw_progress(self, frame):
        out = frame.copy()
        for i, pt in enumerate(self._pts):
            cv2.circle(out, tuple(pt), 10, (0, 200, 255), -1)
            cv2.putText(out, self.LABELS[i], (pt[0]+12, pt[1]+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        nxt = self.LABELS[len(self._pts)] if len(self._pts) < 4 else "done"
        cv2.putText(out, f"MANUAL: click {nxt}  ({4-len(self._pts)} left)",
                    (15, out.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.85, (0, 200, 255), 2)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Main class — NO LOCKING
# ─────────────────────────────────────────────────────────────────────────────

class FrameDetector:
    """
    Per-frame surface detection. Detection runs every frame; there is no lock.
    If a frame fails detection, the last successful result is kept on screen
    purely for visual continuity, but the next frame retries fresh.

    process(frame) -> (warped, corners, locked, status)
        locked is always False (kept for visualizer signature compatibility).
    """

    def __init__(self):
        self._H            = None
        self._corners      = None
        self._last_method  = None
        self._manual       = _ManualSelector()
        self._manual_corners = None   # set when user finishes manual selection

    def process(self, frame):
        # ── Manual selection in progress ──
        if self._manual.is_active:
            return None, None, False, "manual: selecting corners"

        # ── Manual selection just finished ──
        if self._manual.is_done:
            c = self._manual.get_corners()
            self._manual.stop("Drawing Detector")
            if c is not None:
                self._manual_corners = c
                self._set_corners(c, method="manual")

        # ── If manual corners are active, use them; otherwise auto-detect ──
        if self._manual_corners is not None:
            self._set_corners(self._manual_corners, method="manual")
        else:
            corners = self._auto_detect(frame)
            if corners is not None:
                self._set_corners(corners)
            # If detection failed: keep previous self._corners / self._H as a
            # visual fallback. Next frame will re-detect fresh — NOT locked.

        if self._H is None:
            return None, None, False, "searching..."

        w, h   = config.SURFACE_OUTPUT_SIZE
        warped = cv2.warpPerspective(frame, self._H, (w, h))
        return warped, self._corners, False, f"live [{self._last_method}]"

    def start_manual(self, window_name="Drawing Detector"):
        self._clear()
        self._manual.start(window_name)

    def reset(self):
        self._clear()
        print("[frame_detector] State cleared.")

    def draw_overlay(self, frame):
        out = frame.copy()

        if self._manual.is_active:
            return self._manual.draw_progress(frame)

        if self._corners is None:
            cv2.putText(out, "Searching...  (M: manual select)",
                        (15, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 220), 2)
            return out

        color = (0, 220, 255) if self._last_method == "manual" else (0, 220, 0)
        pts   = self._corners.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [pts], isClosed=True, color=color, thickness=3)

        for i, pt in enumerate(self._corners):
            cv2.circle(out, tuple(pt.astype(int)), 8, color, -1)
            cv2.putText(out, ["TL","TR","BR","BL"][i],
                        (int(pt[0])+10, int(pt[1])-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

        cv2.putText(out, f"Surface: LIVE [{self._last_method}]",
                    (15, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        return out

    # ── Internal ──────────────────────────────

    def _auto_detect(self, frame):
        for name, fn in _STRATEGIES:
            try:
                c = fn(frame)
                if c is not None:
                    self._last_method = name
                    return c
            except Exception as e:
                print(f"  [frame_detector] {name}: {e}")
        return None

    def _set_corners(self, corners, method=None):
        self._H       = _build_homography(corners, config.SURFACE_OUTPUT_SIZE)
        self._corners = corners
        if method:
            self._last_method = method

    def _clear(self):
        self._H              = None
        self._corners        = None
        self._last_method    = None
        self._manual_corners = None
"""
frame_detector.py — Robust white surface detector with perspective correction.

Detection strategies (tried in order):
  1. Hough Lines   : finds 4 dominant lines -> intersect -> quad corners.
                     Works even when corners are outside the frame or occluded.
  2. LAB + morph   : luminance gradient on LAB-L channel. Lighting-independent.
  3. Adaptive thr  : local adaptive threshold, handles uneven lighting well.
  4. Edge / Canny  : classic contour approach with CLAHE.
  5. HSV white     : low-saturation + high-value mask.
  6. Brightness    : simple global threshold, last resort.
  7. Manual        : user clicks 4 corners with the mouse (M key).

Controls:
  R : force-release homography lock
  M : enter manual corner-click mode
"""

import cv2
import numpy as np
import config


# ─────────────────────────────────────────────────────────────────────────────
# Corner helpers
# ─────────────────────────────────────────────────────────────────────────────

def _order_corners(pts):
    """Order 4 points as [TL, TR, BR, BL]."""
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
    """Return True if the quad is large enough and reasonably convex."""
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
    """Reduce a contour to 4 corners via progressive polygon simplification."""
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
        if corners is None:
            continue
        if not _valid_quad(corners, frame_area):
            continue
        area = _quad_area(corners)
        if area > best_area:
            best, best_area = corners, area
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1: Hough Lines
# ─────────────────────────────────────────────────────────────────────────────

def _line_angle(x1, y1, x2, y2):
    """Angle of a line segment in degrees [0, 180)."""
    return np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180


def _line_to_params(x1, y1, x2, y2):
    """Convert two-point line to (rho, theta) normal form."""
    dx, dy = x2 - x1, y2 - y1
    length = np.hypot(dx, dy)
    if length < 1e-6:
        return None
    nx, ny = -dy / length, dx / length   # normal
    rho    = nx * x1 + ny * y1
    theta  = np.arctan2(ny, nx)
    return rho, theta


def _intersect_lines(l1, l2):
    """Intersect two lines each given as (rho, theta). Returns (x, y) or None."""
    r1, t1 = l1
    r2, t2 = l2
    A = np.array([[np.cos(t1), np.sin(t1)],
                  [np.cos(t2), np.sin(t2)]], dtype=np.float64)
    b = np.array([r1, r2], dtype=np.float64)
    det = A[0,0]*A[1,1] - A[0,1]*A[1,0]
    if abs(det) < 1e-6:
        return None   # parallel
    x = (A[1,1]*b[0] - A[0,1]*b[1]) / det
    y = (A[0,0]*b[1] - A[1,0]*b[0]) / det
    return x, y


def _cluster_lines_by_angle(segments, n_clusters=2, angle_tol=20):
    """
    Cluster line segments into n_clusters groups by angle.
    Returns list of groups, each group is a list of (rho, theta) params.
    """
    if not segments:
        return []

    angles = np.array([_line_angle(*s) for s in segments])

    # Simple greedy clustering: seed on the two most different angles
    groups  = [[] for _ in range(n_clusters)]
    centers = [None] * n_clusters

    # Seed: find the first seed, then find the angle most different from it
    centers[0] = angles[0]
    best_diff, best_idx = 0, 0
    for i, a in enumerate(angles):
        diff = min(abs(a - centers[0]), 180 - abs(a - centers[0]))
        if diff > best_diff:
            best_diff, best_idx = diff, i
    centers[1] = angles[best_idx]

    # If the two seed angles are too similar, clustering won't help
    if best_diff < 10:
        return []

    # Assign each segment to nearest center (angle distance, mod 180)
    for i, (seg, angle) in enumerate(zip(segments, angles)):
        params = _line_to_params(*seg)
        if params is None:
            continue
        dists = [min(abs(angle - c), 180 - abs(angle - c)) for c in centers]
        groups[np.argmin(dists)].append(params)

    return groups


def _dominant_lines_in_group(group, n=2):
    """
    From a group of (rho, theta) lines, pick n lines that are most
    spread apart (i.e. the two 'sides' of the rectangle).
    """
    if len(group) < 2:
        return group

    rhos = np.array([r for r, t in group])

    # Sort by rho (distance from origin)
    order = np.argsort(rhos)
    sorted_group = [group[i] for i in order]

    if n == 2:
        # Take the first and last (most spread)
        return [sorted_group[0], sorted_group[-1]]

    return sorted_group[:n]


def _detect_hough(frame):
    """
    Strategy 1: Hough line detection.
    Finds 4 dominant lines (2 pairs of parallel sides), intersects them.
    Robust when corners are not visible or image is noisy.
    """
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe   = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray    = clahe.apply(gray)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Auto Canny
    median = np.median(blurred)
    lo     = int(max(0,   0.67 * median))
    hi     = int(min(255, 1.33 * median))
    edges  = cv2.Canny(blurred, lo, hi)
    edges  = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    h, w   = frame.shape[:2]
    min_line_len = min(h, w) * 0.15   # at least 15% of the shorter side

    segments = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=60,
        minLineLength=min_line_len,
        maxLineGap=20
    )

    if segments is None or len(segments) < 4:
        return None

    segs = [tuple(s[0]) for s in segments]   # (x1,y1,x2,y2)

    # Cluster into 2 angle groups (the two edge directions of the rectangle)
    groups = _cluster_lines_by_angle(segs, n_clusters=2)
    if len(groups) < 2 or len(groups[0]) < 1 or len(groups[1]) < 1:
        return None

    # Pick 2 dominant lines per group
    lines_a = _dominant_lines_in_group(groups[0], n=2)
    lines_b = _dominant_lines_in_group(groups[1], n=2)

    if len(lines_a) < 2 or len(lines_b) < 2:
        return None

    # 4 corners = intersections of the 4 lines
    # (a0∩b0), (a0∩b1), (a1∩b0), (a1∩b1)
    corners = []
    for la in lines_a:
        for lb in lines_b:
            pt = _intersect_lines(la, lb)
            if pt is None:
                continue
            x, y = pt
            # Allow corners slightly outside the frame (perspective can push them out)
            if -w * 0.3 <= x <= w * 1.3 and -h * 0.3 <= y <= h * 1.3:
                corners.append([x, y])

    if len(corners) != 4:
        return None

    ordered = _order_corners(np.array(corners, dtype=np.float32))
    frame_area = h * w
    return ordered if _valid_quad(ordered, frame_area) else None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2: LAB L-channel + morphological gradient
# ─────────────────────────────────────────────────────────────────────────────

def _detect_lab_morph(frame):
    """
    Strategy 2: Extract luminance (LAB L-channel), apply morphological gradient
    to get local edge response independent of absolute brightness.
    """
    lab  = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    L    = lab[:, :, 0]

    k5   = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    k15  = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))

    # Morphological gradient = local edge map
    grad = cv2.morphologyEx(L, cv2.MORPH_GRADIENT, k5)

    _, mask = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k15)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k5)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3: Adaptive threshold
# ─────────────────────────────────────────────────────────────────────────────

def _detect_adaptive(frame):
    """
    Strategy 3: Adaptive (local) threshold — handles uneven lighting well.
    Each pixel is compared to its local neighbourhood, not a global value.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray  = clahe.apply(gray)

    # Block size should be large enough to span the surface interior
    block = max(51, (gray.shape[1] // 10) | 1)   # must be odd
    mask  = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block, -5
    )

    k = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 4: Edge-based (Canny + contour)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_edge(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe   = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray    = clahe.apply(gray)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    median  = np.median(blurred)
    lo      = int(max(0,   0.67 * median))
    hi      = int(min(255, 1.33 * median))
    edges   = cv2.Canny(blurred, lo, hi)
    edges   = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 5: HSV white
# ─────────────────────────────────────────────────────────────────────────────

def _detect_hsv(frame):
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 0, 160]), np.array([180, 50, 255]))
    k    = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_quad_from_contours(contours, frame.shape[0] * frame.shape[1])


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 6: Brightness threshold
# ─────────────────────────────────────────────────────────────────────────────

def _detect_brightness(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, config.WHITE_THRESHOLD, 255, cv2.THRESH_BINARY)
    k    = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
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
        self._pts      = []
        self.is_active = False
        self.is_done   = False

    def start(self, window_name):
        self._pts      = []
        self.is_active = True
        self.is_done   = False
        cv2.setMouseCallback(window_name, self._on_click)
        print("[frame_detector] Manual: click 4 corners — TL, TR, BR, BL")

    def stop(self, window_name):
        cv2.setMouseCallback(window_name, lambda *_: None)
        self.is_active = False

    def _on_click(self, event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN and self.is_active:
            self._pts.append([x, y])
            print(f"  {self.LABELS[len(self._pts)-1]}: ({x}, {y})")
            if len(self._pts) == 4:
                self.is_done   = True
                self.is_active = False

    def get_corners(self):
        return _order_corners(np.array(self._pts, dtype=np.float32)) if self.is_done else None

    def draw_progress(self, frame):
        out = frame.copy()
        for i, pt in enumerate(self._pts):
            cv2.circle(out, tuple(pt), 10, (0, 200, 255), -1)
            cv2.putText(out, self.LABELS[i], (pt[0]+12, pt[1]+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
        next_label = self.LABELS[len(self._pts)] if len(self._pts) < 4 else "done"
        cv2.putText(out, f"MANUAL: click {next_label}  ({4-len(self._pts)} left)",
                    (15, out.shape[0] - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 200, 255), 2)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────────────────────────────────────

class FrameDetector:
    """
    Detects the white drawing surface and returns a perspective-corrected view.

    process(frame) -> (warped, corners, locked, status)
    draw_overlay(frame) -> annotated frame for left panel
    start_manual(window_name) -> enter click-to-select mode
    reset() -> force-release homography lock
    """

    def __init__(self):
        self._H           = None
        self._corners     = None
        self._miss_count  = 0
        self._locked      = False
        self._last_method = None
        self._manual      = _ManualSelector()

    def process(self, frame):
        if self._manual.is_active:
            return None, None, False, "manual: selecting corners"

        if self._manual.is_done:
            corners = self._manual.get_corners()
            self._manual.stop("Drawing Detector")
            if corners is not None:
                self._accept(corners, method="manual")

        if not self._locked:
            corners = self._auto_detect(frame)
            if corners is not None:
                self._accept(corners)
            else:
                self._miss_count += 1
                if self._miss_count > config.LOCK_TIMEOUT_FRAMES:
                    self._locked = (self._H is not None)

        if self._H is None:
            return None, None, False, "searching..."

        w, h   = config.SURFACE_OUTPUT_SIZE
        warped = cv2.warpPerspective(frame, self._H, (w, h))
        state  = "locked" if self._locked else "live"
        return warped, self._corners, self._locked, f"{state} [{self._last_method}]"

    def start_manual(self, window_name="Drawing Detector"):
        self._release()
        self._manual.start(window_name)

    def reset(self):
        self._release()
        print("[frame_detector] Lock released — searching again.")

    def draw_overlay(self, frame):
        out = frame.copy()

        if self._manual.is_active:
            return self._manual.draw_progress(frame)

        if self._corners is None:
            cv2.putText(out, "Searching...  (M: manual select)",
                        (15, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (80, 80, 220), 2)
            return out

        color = (0, 140, 255) if self._locked else (0, 220, 0)
        pts   = self._corners.astype(np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [pts], isClosed=True, color=color, thickness=3)

        for i, pt in enumerate(self._corners):
            cv2.circle(out, tuple(pt.astype(int)), 8, color, -1)
            cv2.putText(out, ["TL","TR","BR","BL"][i],
                        (int(pt[0])+10, int(pt[1])-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

        state = "LOCKED" if self._locked else "LIVE"
        cv2.putText(out, f"Surface: {state} [{self._last_method}]",
                    (15, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        return out

    def _auto_detect(self, frame):
        for name, fn in _STRATEGIES:
            try:
                corners = fn(frame)
                if corners is not None:
                    self._last_method = name
                    return corners
            except Exception as e:
                print(f"  [frame_detector] {name} failed: {e}")
        return None

    def _accept(self, corners, method=None):
        self._H          = _build_homography(corners, config.SURFACE_OUTPUT_SIZE)
        self._corners    = corners
        self._miss_count = 0
        self._locked     = False
        if method:
            self._last_method = method

    def _release(self):
        self._H           = None
        self._corners     = None
        self._miss_count  = 0
        self._locked      = False
        self._last_method = None

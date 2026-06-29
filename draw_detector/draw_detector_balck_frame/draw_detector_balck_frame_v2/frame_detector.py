"""
frame_detector.py — White-interior surface detector with dark-border verification.

PRIMARY strategy: "white_with_dark_border"
  1. Mask bright pixels (paper interior).
  2. Find largest contours → reduce each to a 4-corner quad.
  3. For each candidate quad, verify:
       a. Quad is large enough (MIN_AREA_RATIO)
       b. Quad is convex enough (MIN_QUAD_SOLIDITY)
       c. Interior is bright (MIN_INNER_BRIGHTNESS)
       d. Interior is uniform (MAX_INNER_STDDEV)
       e. A ring just OUTSIDE the quad is significantly darker
          (MIN_BORDER_CONTRAST) — this proves there is a dark border / edge.
  4. Pick the best candidate by area × contrast.

If primary fails, fall back through: hough → lab+morph → adaptive → edge → hsv.

NO LOCKING. Detection runs every frame. The last good result is shown only
for visual continuity when one frame happens to fail.

Controls:
  R : clear state (corners + manual selection)
  M : enter manual corner-click mode
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
    rect[0] = pts[np.argmin(s)]      # TL
    rect[2] = pts[np.argmax(s)]      # BR
    diff    = np.diff(pts, axis=1).flatten()
    rect[1] = pts[np.argmin(diff)]   # TR
    rect[3] = pts[np.argmax(diff)]   # BL
    return rect


def _quad_area(corners):
    return cv2.contourArea(corners.reshape(-1, 1, 2).astype(np.float32))


def _quad_solidity(corners):
    area = _quad_area(corners)
    hull = cv2.contourArea(cv2.convexHull(corners.reshape(-1, 1, 2).astype(np.float32)))
    return (area / hull) if hull > 0 else 0.0


def _quad_avg_edge(corners):
    """Average edge length of the quadrilateral (px)."""
    c = corners
    edges = [np.linalg.norm(c[(i+1) % 4] - c[i]) for i in range(4)]
    return float(np.mean(edges))


def _build_homography(corners, output_size):
    w, h = output_size
    dst  = np.array([[0,0],[w-1,0],[w-1,h-1],[0,h-1]], dtype=np.float32)
    H, _ = cv2.findHomography(corners, dst, method=0)
    return H


def _contour_to_quad(cnt):
    """Reduce a contour to 4 corners via progressive polygon simplification."""
    hull = cv2.convexHull(cnt)
    peri = cv2.arcLength(hull, True)
    for eps in [config.POLY_APPROX_EPS, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20]:
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


def _morph_clean(mask, close_k=None, open_k=None):
    ck = close_k if close_k is not None else config.MORPH_CLOSE_K
    ok = open_k  if open_k  is not None else config.MORPH_OPEN_K
    kc = cv2.getStructuringElement(cv2.MORPH_RECT, (ck, ck))
    ko = cv2.getStructuringElement(cv2.MORPH_RECT, (ok, ok))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kc)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  ko)
    return mask


# ─────────────────────────────────────────────────────────────────────────────
# Quad verification (the heart of the new approach)
# ─────────────────────────────────────────────────────────────────────────────

def _make_quad_mask(corners, shape):
    """Solid mask of the quad interior, 255 inside / 0 outside."""
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [corners.astype(np.int32)], 255)
    return mask


def _make_ring_mask(corners, shape, ring_px):
    """
    Mask of the OUTER ring just outside the quad — used to check
    if a darker border surrounds the bright interior.
    """
    inner = _make_quad_mask(corners, shape)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ring_px, ring_px))
    dilated = cv2.dilate(inner, kernel)
    ring = cv2.subtract(dilated, inner)
    return ring


def _verify_quad(corners, gray, frame_area):
    """
    Verify a candidate quad meets the "white interior + dark border" criteria.
    Returns (passed: bool, score: float, info: dict).
    """
    info = {}

    # 1. Size
    area = _quad_area(corners)
    info["area_ratio"] = area / frame_area
    if area < frame_area * config.MIN_AREA_RATIO:
        return False, 0.0, info

    # 2. Convexity
    solidity = _quad_solidity(corners)
    info["solidity"] = solidity
    if solidity < config.MIN_QUAD_SOLIDITY:
        return False, 0.0, info

    # 3. Interior brightness + uniformity
    inner_mask = _make_quad_mask(corners, gray.shape)
    inner_pixels = gray[inner_mask > 0]
    if inner_pixels.size == 0:
        return False, 0.0, info

    inner_mean = float(inner_pixels.mean())
    inner_std  = float(inner_pixels.std())
    info["inner_mean"] = inner_mean
    info["inner_std"]  = inner_std

    if inner_mean < config.MIN_INNER_BRIGHTNESS:
        return False, 0.0, info
    if inner_std > config.MAX_INNER_STDDEV:
        return False, 0.0, info

    # 4. Outer ring contrast (the key "dark border" check)
    ring_px = max(5, int(_quad_avg_edge(corners) * config.BORDER_RING_FRACTION))
    ring_mask = _make_ring_mask(corners, gray.shape, ring_px)
    ring_pixels = gray[ring_mask > 0]

    if ring_pixels.size == 0:
        # Quad is at the very edge of the frame; assume border check OK.
        outer_mean = 0.0
    else:
        outer_mean = float(ring_pixels.mean())
    info["outer_mean"] = outer_mean
    contrast = inner_mean - outer_mean
    info["contrast"] = contrast

    if contrast < config.MIN_BORDER_CONTRAST:
        return False, 0.0, info

    # 5. Compute final score (used to pick the best of multiple candidates)
    # Higher = better. Factors: area, contrast, uniformity.
    score = (
        area
        * (contrast / 255.0)
        * (1.0 - inner_std / 255.0)
        * solidity
    )
    info["score"] = score
    return True, score, info


# ─────────────────────────────────────────────────────────────────────────────
# PRIMARY: white interior + dark border verification
# ─────────────────────────────────────────────────────────────────────────────

def _detect_white_with_dark_border(frame):
    """
    Find the largest bright quadrilateral whose surroundings are dark.

    Steps:
      1. Threshold bright pixels (paper interior candidates).
      2. Morphologically clean to merge interior with itself.
      3. Find external contours, reduce each to a quad.
      4. For each candidate, run _verify_quad() and keep the best score.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Bright mask = paper interior candidates
    _, bright = cv2.threshold(blurred, config.WHITE_THRESHOLD, 255,
                              cv2.THRESH_BINARY)
    bright = _morph_clean(bright)

    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    frame_area = frame.shape[0] * frame.shape[1]
    best_corners, best_score = None, 0.0

    for cnt in contours:
        if cv2.contourArea(cnt) < frame_area * config.MIN_AREA_RATIO:
            continue
        quad = _contour_to_quad(cnt)
        if quad is None:
            continue
        passed, score, _info = _verify_quad(quad, gray, frame_area)
        if passed and score > best_score:
            best_corners, best_score = quad, score

    return best_corners


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACKS: previous strategies, but each result also goes through _verify_quad
# ─────────────────────────────────────────────────────────────────────────────

def _best_verified_quad_from_contours(contours, gray, frame_area):
    """Like _best_quad_from_contours but uses _verify_quad scoring."""
    best, best_score = None, 0.0
    for cnt in contours:
        if cv2.contourArea(cnt) < frame_area * config.MIN_AREA_RATIO:
            continue
        quad = _contour_to_quad(cnt)
        if quad is None:
            continue
        passed, score, _ = _verify_quad(quad, gray, frame_area)
        if passed and score > best_score:
            best, best_score = quad, score
    return best


def _detect_hough(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe   = cv2.createCLAHE(clipLimit=config.CLAHE_CLIP, tileGridSize=config.CLAHE_GRID)
    enhanced= clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    median  = np.median(blurred)
    edges   = cv2.Canny(blurred, int(max(0, 0.67*median)),
                                  int(min(255, 1.33*median)))
    edges   = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    h, w   = frame.shape[:2]
    segs   = cv2.HoughLinesP(edges, 1, np.pi/180, config.HOUGH_THRESHOLD,
                              minLineLength=min(h, w)*config.HOUGH_MIN_LINE_FRAC,
                              maxLineGap=config.HOUGH_MAX_LINE_GAP)
    if segs is None or len(segs) < 4:
        return None

    def line_angle(x1,y1,x2,y2):
        return np.degrees(np.arctan2(y2-y1, x2-x1)) % 180

    def to_params(x1,y1,x2,y2):
        dx, dy = x2-x1, y2-y1
        L = np.hypot(dx, dy)
        if L < 1e-6: return None
        nx, ny = -dy/L, dx/L
        return nx*x1+ny*y1, np.arctan2(ny, nx)

    def intersect(l1, l2):
        r1,t1 = l1; r2,t2 = l2
        A = np.array([[np.cos(t1), np.sin(t1)],
                      [np.cos(t2), np.sin(t2)]])
        b = np.array([r1, r2])
        d = A[0,0]*A[1,1] - A[0,1]*A[1,0]
        if abs(d) < 1e-6: return None
        return ((A[1,1]*b[0]-A[0,1]*b[1])/d,
                (A[0,0]*b[1]-A[1,0]*b[0])/d)

    raw_segs = [tuple(s[0]) for s in segs]
    angles   = [line_angle(*s) for s in raw_segs]
    params   = [to_params(*s)  for s in raw_segs]

    a0 = angles[0]
    diffs = [min(abs(a-a0), 180-abs(a-a0)) for a in angles]
    pivot = int(np.argmax(diffs))
    if diffs[pivot] < 10: return None
    a1 = angles[pivot]

    groups = [[], []]
    for a, p in zip(angles, params):
        if p is None: continue
        d0 = min(abs(a-a0), 180-abs(a-a0))
        d1 = min(abs(a-a1), 180-abs(a-a1))
        groups[0 if d0 < d1 else 1].append(p)

    def dom(g):
        if len(g) < 2: return g
        s = sorted(g, key=lambda x: x[0])
        return [s[0], s[-1]]

    la, lb = dom(groups[0]), dom(groups[1])
    if len(la) < 2 or len(lb) < 2: return None

    corners = []
    for l1 in la:
        for l2 in lb:
            pt = intersect(l1, l2)
            if pt is None: continue
            x, y = pt
            if -w*0.3 <= x <= w*1.3 and -h*0.3 <= y <= h*1.3:
                corners.append([x, y])
    if len(corners) != 4: return None

    quad = _order_corners(np.array(corners, dtype=np.float32))
    passed, _, _ = _verify_quad(quad, gray, h*w)
    return quad if passed else None


def _detect_lab_morph(frame):
    L    = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)[:, :, 0]
    k5   = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    grad = cv2.morphologyEx(L, cv2.MORPH_GRADIENT, k5)
    _, mask = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = _morph_clean(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return _best_verified_quad_from_contours(contours, gray, frame.shape[0]*frame.shape[1])


def _detect_adaptive(frame):
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=config.CLAHE_CLIP, tileGridSize=config.CLAHE_GRID)
    enhanced = clahe.apply(gray)
    block = max(51, (gray.shape[1] // config.ADAPTIVE_BLOCK_DIV) | 1)
    mask  = cv2.adaptiveThreshold(enhanced, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
                block, config.ADAPTIVE_C)
    mask  = _morph_clean(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return _best_verified_quad_from_contours(contours, gray, frame.shape[0]*frame.shape[1])


def _detect_edge(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    clahe   = cv2.createCLAHE(clipLimit=config.CLAHE_CLIP, tileGridSize=config.CLAHE_GRID)
    enhanced= clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    median  = np.median(blurred)
    edges   = cv2.Canny(blurred, int(max(0, 0.67*median)),
                                  int(min(255, 1.33*median)))
    edges   = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return _best_verified_quad_from_contours(contours, gray, frame.shape[0]*frame.shape[1])


def _detect_hsv(frame):
    hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv,
                        np.array([0, 0, config.HSV_VAL_MIN]),
                        np.array([180, config.HSV_SAT_MAX, 255]))
    mask = _morph_clean(mask)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return _best_verified_quad_from_contours(contours, gray, frame.shape[0]*frame.shape[1])


_STRATEGIES = [
    ("white+border", _detect_white_with_dark_border),  # PRIMARY
    ("hough",        _detect_hough),
    ("lab+morph",    _detect_lab_morph),
    ("adaptive",     _detect_adaptive),
    ("edge",         _detect_edge),
    ("hsv",          _detect_hsv),
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
            print(f"  {self.LABELS[len(self._pts)-1]}: ({x},{y})")
            if len(self._pts) == 4:
                self.is_done = True; self.is_active = False

    def get_corners(self):
        return _order_corners(np.array(self._pts, dtype=np.float32)) if self.is_done else None

    def draw_progress(self, frame):
        out = frame.copy()
        for i, pt in enumerate(self._pts):
            cv2.circle(out, tuple(pt), 10, (0,200,255), -1)
            cv2.putText(out, self.LABELS[i], (pt[0]+12, pt[1]+5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,200,255), 2)
        nxt = self.LABELS[len(self._pts)] if len(self._pts) < 4 else "done"
        cv2.putText(out, f"MANUAL: click {nxt} ({4-len(self._pts)} left)",
                    (15, out.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX,
                    0.85, (0,200,255), 2)
        return out


# ─────────────────────────────────────────────────────────────────────────────
# Main class — NO LOCKING
# ─────────────────────────────────────────────────────────────────────────────

class FrameDetector:
    """
    Per-frame surface detection. No locking.
    All candidates pass through _verify_quad() which checks for a bright
    interior AND a dark surrounding border.

    process(frame) -> (warped, corners, locked, status)
        locked is always False (kept for compatibility).
    """

    def __init__(self):
        self._H              = None
        self._corners        = None
        self._last_method    = None
        self._manual         = _ManualSelector()
        self._manual_corners = None

    def process(self, frame):
        if self._manual.is_active:
            return None, None, False, "manual: selecting corners"

        if self._manual.is_done:
            c = self._manual.get_corners()
            self._manual.stop("Drawing Detector")
            if c is not None:
                self._manual_corners = c
                self._set_corners(c, method="manual")

        if self._manual_corners is not None:
            self._set_corners(self._manual_corners, method="manual")
        else:
            corners = self._auto_detect(frame)
            if corners is not None:
                self._set_corners(corners)
            # else: keep previous corners on screen for visual continuity

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
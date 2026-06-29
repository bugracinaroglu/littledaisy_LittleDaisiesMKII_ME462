"""
processor.py — Drawing post-processing.

Takes raw stroke data from the tablet and produces a clean version
ready for the robot arm:

  1. Drop strokes that are too short (taps, artifacts)
  2. Smooth each stroke (light moving average, optional)
  3. Simplify each stroke (Douglas-Peucker)

All thresholds live in config.py.

Input/output stroke format (both):
  strokes = [
    {"points": [[x, y], [x, y], ...]},   # x, y in 0..1 normalized canvas coords
    ...
  ]
"""

from typing import List, Dict, Any
import math

import config


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _stroke_length(points: List[List[float]]) -> float:
    """Total path length of a stroke in normalized units."""
    total = 0.0
    for i in range(1, len(points)):
        dx = points[i][0] - points[i - 1][0]
        dy = points[i][1] - points[i - 1][1]
        total += math.hypot(dx, dy)
    return total


def _moving_average(points: List[List[float]], window: int = 3) -> List[List[float]]:
    """3-point moving average that keeps endpoints fixed."""
    if len(points) < 3:
        return points

    smoothed = [points[0]]
    half = window // 2

    for i in range(1, len(points) - 1):
        lo = max(0, i - half)
        hi = min(len(points), i + half + 1)
        sx = sum(p[0] for p in points[lo:hi]) / (hi - lo)
        sy = sum(p[1] for p in points[lo:hi]) / (hi - lo)
        smoothed.append([sx, sy])

    smoothed.append(points[-1])
    return smoothed


def _perp_distance(p, a, b) -> float:
    """Perpendicular distance from p to segment a-b."""
    ax, ay = a
    bx, by = b
    px, py = p

    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)

    # Closest point on the infinite line
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx = ax + t * dx
    cy = ay + t * dy
    return math.hypot(px - cx, py - cy)


def _douglas_peucker(points: List[List[float]], eps: float) -> List[List[float]]:
    """Iterative Douglas-Peucker. Returns simplified polyline."""
    if len(points) < 3:
        return points[:]

    # Iterative version to avoid Python recursion limits on long strokes.
    keep = [False] * len(points)
    keep[0] = True
    keep[-1] = True

    stack = [(0, len(points) - 1)]

    while stack:
        start, end = stack.pop()
        if end - start < 2:
            continue

        max_d = -1.0
        max_i = -1
        a = points[start]
        b = points[end]
        for i in range(start + 1, end):
            d = _perp_distance(points[i], a, b)
            if d > max_d:
                max_d = d
                max_i = i

        if max_d > eps:
            keep[max_i] = True
            stack.append((start, max_i))
            stack.append((max_i, end))

    return [points[i] for i in range(len(points)) if keep[i]]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def process_strokes(strokes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Clean a list of strokes per config.py settings.
    Returns a new list — does not mutate the input.
    """
    out: List[Dict[str, Any]] = []

    for stroke in strokes:
        pts = stroke.get("points", [])

        # 1. Drop tiny strokes
        if len(pts) < config.MIN_STROKE_POINTS:
            continue
        if _stroke_length(pts) < config.MIN_STROKE_LENGTH:
            continue

        # 2. Smooth
        smoothed = pts
        for _ in range(config.SMOOTHING_PASSES):
            smoothed = _moving_average(smoothed)

        # 3. Simplify
        simplified = _douglas_peucker(smoothed, config.SIMPLIFY_EPSILON)

        out.append({"points": simplified})

    return out

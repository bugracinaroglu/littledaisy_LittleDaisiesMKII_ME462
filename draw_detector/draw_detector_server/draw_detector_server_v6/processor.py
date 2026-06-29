"""Drawing path preparation and coordinate conversion.

The tablet sends normalized coordinates with a top-left origin because that is
HTML canvas' natural coordinate system. Saved drawing JSON files use a
bottom-left origin: +X right, +Y up.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import config

Point = List[float]
Stroke = Dict[str, Any]


def _sanitize_points(points: List[List[float]]) -> List[Point]:
    """Validate, clamp and copy points without changing order or density."""
    clean: List[Point] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(x) or not math.isfinite(y):
            continue

        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        if clean and clean[-1][0] == x and clean[-1][1] == y:
            continue
        clean.append([x, y])
    return clean


def convert_top_left_to_bottom_left(strokes: List[Stroke]) -> List[Stroke]:
    """Copy strokes and transform [x, y] into [x, 1-y]."""
    converted: List[Stroke] = []
    for stroke in strokes:
        points = _sanitize_points(stroke.get("points", []))
        if not points:
            continue
        item: Stroke = {
            "stroke_id": str(stroke.get("stroke_id") or ""),
            "points": [[x, round(1.0 - y, 12)] for x, y in points],
        }
        parent_id = stroke.get("parent_stroke_id")
        if parent_id:
            item["parent_stroke_id"] = str(parent_id)
        converted.append(item)
    return converted


def _stroke_length(points: List[Point]) -> float:
    return sum(
        math.hypot(
            points[index][0] - points[index - 1][0],
            points[index][1] - points[index - 1][1],
        )
        for index in range(1, len(points))
    )


def _moving_average(points: List[Point], window: int = 3) -> List[Point]:
    if len(points) < 3:
        return [point[:] for point in points]
    result = [points[0][:]]
    half = window // 2
    for index in range(1, len(points) - 1):
        low = max(0, index - half)
        high = min(len(points), index + half + 1)
        count = high - low
        result.append([
            sum(point[0] for point in points[low:high]) / count,
            sum(point[1] for point in points[low:high]) / count,
        ])
    result.append(points[-1][:])
    return result


def _perpendicular_distance(point: Point, start: Point, end: Point) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx == 0.0 and dy == 0.0:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (
        dx * dx + dy * dy
    )
    t = min(1.0, max(0.0, t))
    closest_x = start[0] + t * dx
    closest_y = start[1] + t * dy
    return math.hypot(point[0] - closest_x, point[1] - closest_y)


def _douglas_peucker(points: List[Point], epsilon: float) -> List[Point]:
    if len(points) < 3 or epsilon <= 0.0:
        return [point[:] for point in points]
    keep = [False] * len(points)
    keep[0] = True
    keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start_index, end_index = stack.pop()
        if end_index - start_index < 2:
            continue
        maximum_distance = -1.0
        maximum_index = -1
        for index in range(start_index + 1, end_index):
            distance = _perpendicular_distance(
                points[index], points[start_index], points[end_index]
            )
            if distance > maximum_distance:
                maximum_distance = distance
                maximum_index = index
        if maximum_distance > epsilon:
            keep[maximum_index] = True
            stack.append((start_index, maximum_index))
            stack.append((maximum_index, end_index))
    return [points[index][:] for index, selected in enumerate(keep) if selected]


def process_strokes(strokes: List[Stroke]) -> List[Stroke]:
    """Return the saved/output stroke representation.

    In raw mode the valid points, IDs and ordering are preserved. In filtered
    mode only point geometry changes; stroke identity remains stable.
    """
    output: List[Stroke] = []
    for stroke in strokes:
        points = _sanitize_points(stroke.get("points", []))
        if not points:
            continue

        if config.PROCESSING_MODE == "raw":
            filtered = points
        else:
            if len(points) < config.MIN_STROKE_POINTS:
                continue
            if _stroke_length(points) < config.MIN_STROKE_LENGTH:
                continue
            filtered = points
            for _ in range(config.SMOOTHING_PASSES):
                filtered = _moving_average(filtered)
            filtered = _douglas_peucker(filtered, config.SIMPLIFY_EPSILON)

        item: Stroke = {
            "stroke_id": str(stroke.get("stroke_id") or ""),
            "points": filtered,
        }
        parent_id = stroke.get("parent_stroke_id")
        if parent_id:
            item["parent_stroke_id"] = str(parent_id)
        output.append(item)
    return output

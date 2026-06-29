"""Drawing path preparation.

Default behaviour is pass-through: preserve all valid tablet points in order.
An optional filtered mode is retained for later robot-path experiments.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import config


Point = List[float]
Stroke = Dict[str, Any]


def _sanitize_points(points: List[List[float]]) -> List[Point]:
    """Validate, clamp and copy points without changing their order or density."""
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

        # Remove only exact consecutive duplicates. No geometric decimation.
        if clean and clean[-1][0] == x and clean[-1][1] == y:
            continue
        clean.append([x, y])

    return clean


def _stroke_length(points: List[Point]) -> float:
    total = 0.0
    for index in range(1, len(points)):
        total += math.hypot(
            points[index][0] - points[index - 1][0],
            points[index][1] - points[index - 1][1],
        )
    return total


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

    t = (
        (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
    ) / (dx * dx + dy * dy)
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
    output: List[Stroke] = []

    for stroke in strokes:
        points = _sanitize_points(stroke.get("points", []))
        if not points:
            continue

        if config.PROCESSING_MODE == "raw":
            output.append({"points": points})
            continue

        if len(points) < config.MIN_STROKE_POINTS:
            continue
        if _stroke_length(points) < config.MIN_STROKE_LENGTH:
            continue

        filtered = points
        for _ in range(config.SMOOTHING_PASSES):
            filtered = _moving_average(filtered)
        filtered = _douglas_peucker(filtered, config.SIMPLIFY_EPSILON)
        output.append({"points": filtered})

    return output

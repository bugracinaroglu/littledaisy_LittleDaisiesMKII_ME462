"""Preview one saved output drawing JSON.

The output schema stores only `strokes` in normalized bottom-left coordinates.
Legacy raw_strokes/processed_strokes files are also accepted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import cv2
import numpy as np

import config

WINDOW_NAME = "LittleDaisy Saved Drawing JSON"
Stroke = Dict[str, Any]


def _valid_strokes(value: Any) -> List[Stroke]:
    if not isinstance(value, list):
        return []
    result: List[Stroke] = []
    for index, stroke in enumerate(value):
        if not isinstance(stroke, dict) or not isinstance(stroke.get("points"), list):
            continue
        result.append({
            "stroke_id": str(stroke.get("stroke_id") or f"legacy-{index}"),
            "points": stroke["points"],
        })
    return result


def load_drawing(path: Path) -> Tuple[Dict[str, Any], List[Stroke]]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    strokes = _valid_strokes(payload.get("strokes"))
    if not strokes:
        strokes = _valid_strokes(payload.get("processed_strokes"))
    if not strokes:
        strokes = _valid_strokes(payload.get("raw_strokes"))
    # Empty drawings are valid snapshots.
    return payload, strokes


def _to_pixels(
    stroke: Stroke,
    panel_size: int,
    *,
    bottom_left_origin: bool,
) -> np.ndarray | None:
    result: List[Tuple[int, int]] = []
    maximum = panel_size - 1
    for point in stroke.get("points", []):
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x = min(1.0, max(0.0, float(point[0])))
            y = min(1.0, max(0.0, float(point[1])))
        except (TypeError, ValueError):
            continue
        screen_y = 1.0 - y if bottom_left_origin else y
        result.append((round(x * maximum), round(screen_y * maximum)))
    if not result:
        return None
    return np.asarray(result, dtype=np.int32).reshape(-1, 1, 2)


def build_frame(
    payload: Dict[str, Any],
    strokes: Sequence[Stroke],
    *,
    show_points: bool,
) -> np.ndarray:
    size = config.PREVIEW_PANEL_SIZE + 100
    image = np.full((size, size, 3), 255, dtype=np.uint8)
    coordinate_system = str(payload.get("coordinate_system", "unknown"))
    bottom_left = "bottom_left" in coordinate_system

    for index, stroke in enumerate(strokes):
        points = _to_pixels(stroke, size, bottom_left_origin=bottom_left)
        if points is None:
            continue
        if len(points) == 1:
            cv2.circle(image, tuple(points[0, 0]), 2, (0, 0, 0), -1, cv2.LINE_AA)
        else:
            cv2.polylines(
                image, [points], False, (0, 0, 0),
                config.PREVIEW_LINE_THICKNESS, cv2.LINE_AA,
            )
        if show_points:
            for point in points[:, 0, :]:
                cv2.circle(image, tuple(point), 1, (110, 110, 110), -1)
        start = tuple(points[0, 0])
        end = tuple(points[-1, 0])
        cv2.circle(image, start, 5, (0, 170, 0), 1, cv2.LINE_AA)
        cv2.circle(image, end, 5, (0, 0, 220), 1, cv2.LINE_AA)
        cv2.putText(
            image, str(index + 1), (start[0] + 6, max(13, start[1] - 5)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (50, 50, 50), 1, cv2.LINE_AA,
        )

    header_height = 76
    header = np.full((header_height, size, 3), 30, dtype=np.uint8)
    point_count = sum(len(stroke.get("points", [])) for stroke in strokes)
    cv2.putText(
        header, "SAVED OUTPUT STROKES", (12, 25), cv2.FONT_HERSHEY_SIMPLEX,
        0.62, (240, 240, 240), 1, cv2.LINE_AA,
    )
    cv2.putText(
        header,
        f"{len(strokes)} strokes | {point_count} points | {coordinate_system}",
        (12, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.44,
        (175, 175, 175), 1, cv2.LINE_AA,
    )
    cv2.putText(
        header, "Green=start/pen down | Red=end/pen up | P=points | Q=quit",
        (12, 69), cv2.FONT_HERSHEY_SIMPLEX, 0.36,
        (135, 135, 135), 1, cv2.LINE_AA,
    )
    return np.vstack((header, image))


def newest_output() -> Path:
    files = list(Path(config.OUTPUT_DIR).glob("drawing_*.json"))
    if not files:
        raise FileNotFoundError("No drawing JSON exists in output/")
    return max(files, key=lambda path: path.stat().st_mtime_ns)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview saved LittleDaisy points")
    parser.add_argument("json_file", nargs="?")
    parser.add_argument("--points", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.json_file).expanduser().resolve() if args.json_file else newest_output()
    show_points = bool(args.points)
    payload, strokes = load_drawing(path)
    frame = build_frame(payload, strokes, show_points=show_points)
    print(f"[json_preview] {path}")
    print(f"[json_preview] strokes={len(strokes)} points={sum(len(s['points']) for s in strokes)}")

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, frame.shape[1], frame.shape[0])
    while True:
        cv2.imshow(WINDOW_NAME, frame)
        key = cv2.waitKey(30) & 0xFF
        if key in (ord("q"), 27):
            break
        if key == ord("p"):
            show_points = not show_points
            frame = build_frame(payload, strokes, show_points=show_points)
        try:
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

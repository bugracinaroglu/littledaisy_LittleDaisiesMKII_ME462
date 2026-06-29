"""Preview saved LittleDaisy drawing JSON files without starting the web server.

Usage:
    python json_preview.py
    python json_preview.py output/drawing_20260629_123456_789.json

Controls:
    Q / ESC : close
    P       : toggle sample points
    L       : toggle connecting lines
    R       : reload current JSON from disk
    N       : load newer JSON file
    B       : load older JSON file
    S       : save current preview as PNG next to the JSON file
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import cv2
import numpy as np

import config


WINDOW_NAME = "LittleDaisy Saved JSON Preview"
Point = Tuple[float, float]
Stroke = Dict[str, Any]


@dataclass
class DrawingFile:
    path: Path
    raw_strokes: List[Stroke]
    processed_strokes: List[Stroke]
    coordinate_system: str
    processing_mode: str
    timestamp: str


def _valid_point(point: Any) -> Point | None:
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    try:
        x = float(point[0])
        y = float(point[1])
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return min(1.0, max(0.0, x)), min(1.0, max(0.0, y))


def _clean_strokes(value: Any) -> List[Stroke]:
    if not isinstance(value, list):
        return []

    output: List[Stroke] = []
    for stroke in value:
        if not isinstance(stroke, dict):
            continue
        points: List[List[float]] = []
        for raw_point in stroke.get("points", []):
            point = _valid_point(raw_point)
            if point is not None:
                points.append([point[0], point[1]])
        if points:
            output.append({"points": points})
    return output


def load_drawing(path: Path) -> DrawingFile:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON: {error}") from error

    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object.")

    raw = _clean_strokes(payload.get("raw_strokes", []))
    processed = _clean_strokes(payload.get("processed_strokes", []))

    # Support a future robot-only file that may contain a generic `strokes` key.
    if not processed:
        processed = _clean_strokes(payload.get("strokes", []))

    if not raw and processed:
        raw = processed

    if not raw and not processed:
        raise ValueError(
            "No valid strokes found. Expected raw_strokes, processed_strokes or strokes."
        )

    return DrawingFile(
        path=path,
        raw_strokes=raw,
        processed_strokes=processed,
        coordinate_system=str(payload.get("coordinate_system", "unknown")),
        processing_mode=str(payload.get("processing_mode", "unknown")),
        timestamp=str(payload.get("timestamp", "unknown")),
    )


def _count_points(strokes: Iterable[Stroke]) -> int:
    return sum(len(stroke.get("points", [])) for stroke in strokes)


def _count_segments(strokes: Iterable[Stroke]) -> int:
    return sum(max(0, len(stroke.get("points", [])) - 1) for stroke in strokes)


def _normalised_to_pixels(stroke: Stroke, panel_size: int) -> np.ndarray | None:
    points = stroke.get("points", [])
    pixel_points: List[Tuple[int, int]] = []
    maximum = panel_size - 1

    for raw_point in points:
        point = _valid_point(raw_point)
        if point is None:
            continue
        x, y = point
        pixel_points.append((round(x * maximum), round(y * maximum)))

    if not pixel_points:
        return None
    return np.asarray(pixel_points, dtype=np.int32).reshape(-1, 1, 2)


def render_strokes(
    strokes: Sequence[Stroke],
    panel_size: int,
    *,
    show_points: bool,
    show_lines: bool,
) -> np.ndarray:
    image = np.full((panel_size, panel_size, 3), 255, dtype=np.uint8)

    for stroke_index, stroke in enumerate(strokes):
        points = _normalised_to_pixels(stroke, panel_size)
        if points is None:
            continue

        if show_lines:
            if len(points) == 1:
                cv2.circle(image, tuple(points[0, 0]), 2, (0, 0, 0), -1, cv2.LINE_AA)
            else:
                cv2.polylines(
                    image,
                    [points],
                    isClosed=False,
                    color=(0, 0, 0),
                    thickness=config.PREVIEW_LINE_THICKNESS,
                    lineType=cv2.LINE_AA,
                )

        if show_points:
            for point in points[:, 0, :]:
                cv2.circle(image, tuple(point), 1, (110, 110, 110), -1, cv2.LINE_AA)

        # Mark pen-down start and pen-up end for robot-path inspection.
        start = tuple(points[0, 0])
        end = tuple(points[-1, 0])
        cv2.circle(image, start, 5, (0, 180, 0), 1, cv2.LINE_AA)
        cv2.circle(image, end, 5, (0, 0, 220), 1, cv2.LINE_AA)
        cv2.putText(
            image,
            str(stroke_index + 1),
            (start[0] + 6, max(12, start[1] - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            (40, 40, 40),
            1,
            cv2.LINE_AA,
        )

    return image


def _header(panel: np.ndarray, title: str, strokes: Sequence[Stroke]) -> np.ndarray:
    header_height = 54
    header = np.full((header_height, panel.shape[1], 3), 32, dtype=np.uint8)
    cv2.putText(
        header,
        title,
        (12, 22),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (240, 240, 240),
        1,
        cv2.LINE_AA,
    )
    details = (
        f"{len(strokes)} strokes | {_count_points(strokes)} points | "
        f"{_count_segments(strokes)} segments"
    )
    cv2.putText(
        header,
        details,
        (12, 43),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.43,
        (170, 170, 170),
        1,
        cv2.LINE_AA,
    )
    return np.vstack((header, panel))


def build_frame(
    drawing: DrawingFile,
    *,
    show_points: bool,
    show_lines: bool,
) -> np.ndarray:
    size = config.PREVIEW_PANEL_SIZE
    raw_image = render_strokes(
        drawing.raw_strokes,
        size,
        show_points=show_points,
        show_lines=show_lines,
    )
    processed_image = render_strokes(
        drawing.processed_strokes,
        size,
        show_points=show_points,
        show_lines=show_lines,
    )

    left = _header(raw_image, "RAW STROKES", drawing.raw_strokes)
    right = _header(processed_image, "ROBOT / PROCESSED STROKES", drawing.processed_strokes)
    divider = np.full((left.shape[0], 10, 3), 18, dtype=np.uint8)
    body = np.hstack((left, divider, right))

    footer_height = 84
    footer = np.full((footer_height, body.shape[1], 3), 27, dtype=np.uint8)
    filename = drawing.path.name
    status = (
        f"{filename} | mode={drawing.processing_mode} | "
        f"coords={drawing.coordinate_system}"
    )
    cv2.putText(
        footer,
        status,
        (14, 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.49,
        (225, 225, 225),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        footer,
        "Green=start / pen down, red=end / pen up",
        (14, 47),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.46,
        (175, 175, 175),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        footer,
        "P: points  L: lines  R: reload  N/B: next/previous JSON  S: save PNG  Q/ESC: quit",
        (14, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.43,
        (145, 145, 145),
        1,
        cv2.LINE_AA,
    )
    return np.vstack((body, footer))


def _json_files(output_dir: Path) -> List[Path]:
    return sorted(
        output_dir.glob("drawing_*.json"),
        key=lambda path: path.stat().st_mtime,
    )


def _select_initial_path(argument: str | None, files: List[Path]) -> Path:
    if argument:
        path = Path(argument).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"JSON file not found: {path}")
        return path
    if not files:
        raise FileNotFoundError(
            f"No drawing JSON files found in: {Path(config.OUTPUT_DIR).resolve()}"
        )
    return files[-1]


def _save_png(frame: np.ndarray, json_path: Path) -> Path:
    png_path = json_path.with_name(f"{json_path.stem}_preview.png")
    if not cv2.imwrite(str(png_path), frame):
        raise OSError(f"Could not save PNG: {png_path}")
    return png_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview saved LittleDaisy drawing JSON points."
    )
    parser.add_argument(
        "json_file",
        nargs="?",
        help="Drawing JSON path. If omitted, the newest output/drawing_*.json is used.",
    )
    parser.add_argument(
        "--points",
        action="store_true",
        help="Show every sampled point when the window opens.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(config.OUTPUT_DIR).resolve()
    files = _json_files(output_dir)
    current_path = _select_initial_path(args.json_file, files)

    # Explicit paths outside output/ are allowed; add them for navigation.
    if current_path not in files:
        files.append(current_path)
        files.sort(key=lambda path: path.stat().st_mtime)

    current_index = files.index(current_path)
    show_points = bool(args.points)
    show_lines = True

    drawing = load_drawing(current_path)
    frame = build_frame(drawing, show_points=show_points, show_lines=show_lines)

    print(f"[json_preview] Loaded: {current_path}")
    print(f"[json_preview] Raw points: {_count_points(drawing.raw_strokes)}")
    print(f"[json_preview] Processed points: {_count_points(drawing.processed_strokes)}")

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, frame.shape[1], frame.shape[0])

    while True:
        cv2.imshow(WINDOW_NAME, frame)
        key = cv2.waitKey(30) & 0xFF

        if key in (ord("q"), 27):
            break
        if key == ord("p"):
            show_points = not show_points
        elif key == ord("l"):
            show_lines = not show_lines
        elif key == ord("r"):
            pass
        elif key == ord("n"):
            files = _json_files(output_dir)
            if not files:
                continue
            current_index = min(current_index + 1, len(files) - 1)
            current_path = files[current_index]
        elif key == ord("b"):
            files = _json_files(output_dir)
            if not files:
                continue
            current_index = max(current_index - 1, 0)
            current_path = files[current_index]
        elif key == ord("s"):
            saved_path = _save_png(frame, current_path)
            print(f"[json_preview] Preview saved: {saved_path}")
            continue
        else:
            try:
                if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
            continue

        try:
            drawing = load_drawing(current_path)
            current_index = files.index(current_path) if current_path in files else current_index
            frame = build_frame(
                drawing,
                show_points=show_points,
                show_lines=show_lines,
            )
            print(f"[json_preview] Loaded: {current_path.name}")
            print(
                f"[json_preview] {_count_points(drawing.raw_strokes)} raw -> "
                f"{_count_points(drawing.processed_strokes)} processed points"
            )
        except (OSError, ValueError) as error:
            print(f"[json_preview] Could not load file: {error}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

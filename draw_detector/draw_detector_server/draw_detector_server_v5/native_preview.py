"""Three-panel native OpenCV preview on the Raspberry Pi desktop."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

import cv2
import numpy as np

import config
from preview_state import PreviewSnapshot, preview_state

WINDOW_NAME = "LittleDaisy Drawing / Robot Job Preview"


def _count_points(items: Iterable[Dict[str, Any]]) -> int:
    return sum(len(item.get("points", [])) for item in items)


def _normalised_points(
    item: Dict[str, Any], panel_size: int, *, bottom_left_origin: bool
) -> np.ndarray | None:
    points = item.get("points", [])
    if not points:
        return None
    pixel_points: List[Tuple[int, int]] = []
    maximum = panel_size - 1
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x = float(point[0])
            y = float(point[1])
        except (TypeError, ValueError):
            continue
        if not np.isfinite(x) or not np.isfinite(y):
            continue
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        pixel_y = (1.0 - y) if bottom_left_origin else y
        pixel_points.append((round(x * maximum), round(pixel_y * maximum)))
    if not pixel_points:
        return None
    return np.asarray(pixel_points, dtype=np.int32).reshape(-1, 1, 2)


def render_strokes(
    strokes: List[Dict[str, Any]],
    panel_size: int,
    *,
    bottom_left_origin: bool,
    show_points: bool = False,
) -> np.ndarray:
    image = np.full((panel_size, panel_size, 3), 255, dtype=np.uint8)
    for stroke in strokes:
        points = _normalised_points(
            stroke, panel_size, bottom_left_origin=bottom_left_origin
        )
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
                cv2.circle(image, tuple(point), 1, (120, 120, 120), -1)
    return image


def render_robot_actions(actions: List[Dict[str, Any]], panel_size: int) -> np.ndarray:
    image = np.full((panel_size, panel_size, 3), 255, dtype=np.uint8)
    # BGR: erase red, draw green, same gray.
    colors = {
        "erase": (30, 30, 220),
        "draw": (30, 150, 30),
        "same": (150, 150, 150),
    }
    if any(action.get("type") == "erase_all" for action in actions):
        cv2.putText(
            image, "ERASE ALL", (18, 34), cv2.FONT_HERSHEY_SIMPLEX,
            0.85, (30, 30, 220), 2, cv2.LINE_AA,
        )

    for action in actions:
        action_type = str(action.get("type", ""))
        if action_type not in colors:
            continue
        points = _normalised_points(
            action, panel_size, bottom_left_origin=True
        )
        if points is None:
            continue
        color = colors[action_type]
        thickness = 3 if action_type in ("erase", "draw") else 1
        if len(points) == 1:
            cv2.circle(image, tuple(points[0, 0]), thickness + 1, color, -1, cv2.LINE_AA)
        else:
            cv2.polylines(image, [points], False, color, thickness, cv2.LINE_AA)
    return image


def _header(panel: np.ndarray, title: str, details: str) -> np.ndarray:
    header = np.full((config.PREVIEW_HEADER_HEIGHT, panel.shape[1], 3), 34, dtype=np.uint8)
    cv2.putText(header, title, (10, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.58,
                (238, 238, 238), 1, cv2.LINE_AA)
    cv2.putText(header, details, (10, 41), cv2.FONT_HERSHEY_SIMPLEX, 0.41,
                (165, 165, 165), 1, cv2.LINE_AA)
    return np.vstack((header, panel))


def _action_counts(actions: List[Dict[str, Any]]) -> str:
    counts = {"erase_all": 0, "erase": 0, "draw": 0, "same": 0}
    for action in actions:
        action_type = str(action.get("type", ""))
        if action_type in counts:
            counts[action_type] += 1
    return (
        f"erase_all={counts['erase_all']} erase={counts['erase']} "
        f"draw={counts['draw']} same={counts['same']}"
    )


def build_preview_frame(snapshot: PreviewSnapshot) -> np.ndarray:
    size = config.PREVIEW_PANEL_SIZE
    live = render_strokes(
        snapshot.live_strokes, size, bottom_left_origin=False,
        show_points=config.PREVIEW_SHOW_SAMPLE_POINTS,
    )
    detected = render_strokes(
        snapshot.detected_strokes, size, bottom_left_origin=True,
        show_points=config.PREVIEW_SHOW_SAMPLE_POINTS,
    )
    job = render_robot_actions(snapshot.robot_actions, size)

    left = _header(
        live, "LIVE TABLET",
        f"{len(snapshot.live_strokes)} strokes | {_count_points(snapshot.live_strokes)} points",
    )
    middle = _header(
        detected, "LAST DETECTED (BOTTOM-LEFT ORIGIN)",
        f"{len(snapshot.detected_strokes)} strokes | {_count_points(snapshot.detected_strokes)} points",
    )
    right = _header(
        job, f"ROBOT JOB [{snapshot.robot_job_mode or '-'}]",
        _action_counts(snapshot.robot_actions),
    )
    divider = np.full((left.shape[0], 8, 3), 18, dtype=np.uint8)
    body = np.hstack((left, divider, middle, divider, right))

    footer = np.full((config.PREVIEW_FOOTER_HEIGHT, body.shape[1], 3), 28, dtype=np.uint8)
    line1 = f"Live: {snapshot.live_status} | Detect: {snapshot.detected_status}"
    if snapshot.saved_to:
        line1 += f" ({snapshot.saved_to})"
    line2 = f"Job: {snapshot.job_status}"
    if snapshot.robot_job_file:
        line2 += f" ({snapshot.robot_job_file})"
    cv2.putText(footer, line1, (12, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (220, 220, 220), 1, cv2.LINE_AA)
    cv2.putText(footer, line2, (12, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (190, 190, 190), 1, cv2.LINE_AA)
    cv2.putText(
        footer,
        "Terminal: send_data2robot_arm | send_full_erase | set_mode difference/full_redraw | show_state",
        (12, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.40,
        (145, 145, 145), 1, cv2.LINE_AA,
    )
    return np.vstack((body, footer))


def run_native_preview() -> None:
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        WINDOW_NAME,
        config.PREVIEW_PANEL_SIZE * 3 + 16,
        config.PREVIEW_PANEL_SIZE + config.PREVIEW_HEADER_HEIGHT + config.PREVIEW_FOOTER_HEIGHT,
    )
    last_version = -1
    frame: np.ndarray | None = None
    while True:
        snapshot = preview_state.snapshot()
        if snapshot.version != last_version or frame is None:
            frame = build_preview_frame(snapshot)
            last_version = snapshot.version
        cv2.imshow(WINDOW_NAME, frame)
        key = cv2.waitKey(config.PREVIEW_REFRESH_MS) & 0xFF
        if key in (ord("q"), 27):
            break
        try:
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break
    cv2.destroyAllWindows()

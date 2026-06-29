"""Native OpenCV preview shown directly on the Raspberry Pi desktop."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple

import cv2
import numpy as np

import config
from preview_state import PreviewSnapshot, preview_state


WINDOW_NAME = "LittleDaisy Drawing Preview"


def _count_points(strokes: Iterable[Dict[str, Any]]) -> int:
    return sum(len(stroke.get("points", [])) for stroke in strokes)


def _normalised_points(
    stroke: Dict[str, Any], panel_size: int
) -> np.ndarray | None:
    points = stroke.get("points", [])
    if not points:
        return None

    pixel_points: List[Tuple[int, int]] = []
    max_index = panel_size - 1

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
        pixel_points.append((round(x * max_index), round(y * max_index)))

    if not pixel_points:
        return None

    return np.asarray(pixel_points, dtype=np.int32).reshape(-1, 1, 2)


def render_strokes(
    strokes: List[Dict[str, Any]],
    panel_size: int,
    show_points: bool = False,
) -> np.ndarray:
    """Render normalized strokes to a white BGR image."""
    image = np.full((panel_size, panel_size, 3), 255, dtype=np.uint8)

    for stroke in strokes:
        pts = _normalised_points(stroke, panel_size)
        if pts is None:
            continue

        if len(pts) == 1:
            cv2.circle(image, tuple(pts[0, 0]), 2, (0, 0, 0), -1, cv2.LINE_AA)
        else:
            cv2.polylines(
                image,
                [pts],
                isClosed=False,
                color=(0, 0, 0),
                thickness=config.PREVIEW_LINE_THICKNESS,
                lineType=cv2.LINE_AA,
            )

        if show_points:
            for point in pts[:, 0, :]:
                cv2.circle(image, tuple(point), 1, (120, 120, 120), -1)

    return image


def _add_panel_header(
    panel: np.ndarray,
    title: str,
    strokes: List[Dict[str, Any]],
) -> np.ndarray:
    header = np.full(
        (config.PREVIEW_HEADER_HEIGHT, panel.shape[1], 3),
        34,
        dtype=np.uint8,
    )

    cv2.putText(
        header,
        title,
        (12, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (235, 235, 235),
        1,
        cv2.LINE_AA,
    )
    count_text = f"{len(strokes)} strokes | {_count_points(strokes)} points"
    text_size = cv2.getTextSize(
        count_text, cv2.FONT_HERSHEY_SIMPLEX, 0.46, 1
    )[0]
    cv2.putText(
        header,
        count_text,
        (max(12, panel.shape[1] - text_size[0] - 12), 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.46,
        (165, 165, 165),
        1,
        cv2.LINE_AA,
    )
    return np.vstack((header, panel))


def build_preview_frame(snapshot: PreviewSnapshot) -> np.ndarray:
    size = config.PREVIEW_PANEL_SIZE
    raw = render_strokes(
        snapshot.raw_strokes,
        size,
        show_points=config.PREVIEW_SHOW_SAMPLE_POINTS,
    )
    processed = render_strokes(
        snapshot.processed_strokes,
        size,
        show_points=config.PREVIEW_SHOW_SAMPLE_POINTS,
    )

    left = _add_panel_header(raw, "ORIGINAL / TABLET DATA", snapshot.raw_strokes)
    right = _add_panel_header(
        processed,
        "DETECTED / OUTPUT DATA",
        snapshot.processed_strokes,
    )

    divider = np.full((left.shape[0], 10, 3), 18, dtype=np.uint8)
    body = np.hstack((left, divider, right))

    footer = np.full(
        (config.PREVIEW_FOOTER_HEIGHT, body.shape[1], 3),
        28,
        dtype=np.uint8,
    )
    status = snapshot.status
    if snapshot.saved_to:
        status += f" | {snapshot.saved_to}"
    cv2.putText(
        footer,
        status,
        (14, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.56,
        (220, 220, 220),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        footer,
        "Q / ESC: close application",
        (14, config.PREVIEW_FOOTER_HEIGHT - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.46,
        (145, 145, 145),
        1,
        cv2.LINE_AA,
    )

    return np.vstack((body, footer))


def run_native_preview() -> None:
    """Blocking OpenCV UI loop. Run this on the main thread."""
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(
        WINDOW_NAME,
        config.PREVIEW_PANEL_SIZE * 2 + 10,
        config.PREVIEW_PANEL_SIZE
        + config.PREVIEW_HEADER_HEIGHT
        + config.PREVIEW_FOOTER_HEIGHT,
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

        # Closing the window using its title-bar X should also terminate.
        try:
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break

    cv2.destroyAllWindows()

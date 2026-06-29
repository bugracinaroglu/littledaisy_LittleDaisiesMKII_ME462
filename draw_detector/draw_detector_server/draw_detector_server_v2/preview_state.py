"""Thread-safe shared state between FastAPI and the native Pi preview window."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List


StrokeList = List[Dict[str, Any]]


@dataclass(frozen=True)
class PreviewSnapshot:
    raw_strokes: StrokeList
    processed_strokes: StrokeList
    status: str
    saved_to: str
    canvas_size_px: int
    version: int


class PreviewState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._raw_strokes: StrokeList = []
        self._processed_strokes: StrokeList = []
        self._status = "Waiting for tablet..."
        self._saved_to = ""
        self._canvas_size_px = 0
        self._version = 0

    def update_raw(self, strokes: StrokeList, canvas_size_px: int = 0) -> None:
        with self._lock:
            self._raw_strokes = deepcopy(strokes)
            # A new/editing drawing means the old detection is stale.
            self._processed_strokes = []
            self._status = "Live drawing received - press Detect on tablet"
            self._saved_to = ""
            self._canvas_size_px = int(canvas_size_px or 0)
            self._version += 1

    def update_detected(
        self,
        raw_strokes: StrokeList,
        processed_strokes: StrokeList,
        saved_to: str,
        canvas_size_px: int = 0,
    ) -> None:
        with self._lock:
            self._raw_strokes = deepcopy(raw_strokes)
            self._processed_strokes = deepcopy(processed_strokes)
            self._status = "Detected drawing ready"
            self._saved_to = saved_to
            self._canvas_size_px = int(canvas_size_px or 0)
            self._version += 1

    def clear(self) -> None:
        with self._lock:
            self._raw_strokes = []
            self._processed_strokes = []
            self._status = "Tablet canvas cleared"
            self._saved_to = ""
            self._canvas_size_px = 0
            self._version += 1

    def snapshot(self) -> PreviewSnapshot:
        with self._lock:
            return PreviewSnapshot(
                raw_strokes=deepcopy(self._raw_strokes),
                processed_strokes=deepcopy(self._processed_strokes),
                status=self._status,
                saved_to=self._saved_to,
                canvas_size_px=self._canvas_size_px,
                version=self._version,
            )


preview_state = PreviewState()

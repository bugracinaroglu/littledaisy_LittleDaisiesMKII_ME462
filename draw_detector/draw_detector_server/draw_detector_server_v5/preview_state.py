"""Thread-safe state shared by FastAPI, terminal commands and native preview."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List

StrokeList = List[Dict[str, Any]]
ActionList = List[Dict[str, Any]]


@dataclass(frozen=True)
class PreviewSnapshot:
    live_strokes: StrokeList
    detected_strokes: StrokeList
    robot_actions: ActionList
    live_status: str
    detected_status: str
    job_status: str
    saved_to: str
    robot_job_file: str
    robot_job_mode: str
    canvas_size_px: int
    version: int


class PreviewState:
    def __init__(self) -> None:
        self._lock = Lock()
        self._live_strokes: StrokeList = []
        self._detected_strokes: StrokeList = []
        self._robot_actions: ActionList = []
        self._live_status = "Waiting for tablet..."
        self._detected_status = "No Detect snapshot yet"
        self._job_status = "No robot job yet"
        self._saved_to = ""
        self._robot_job_file = ""
        self._robot_job_mode = ""
        self._canvas_size_px = 0
        self._version = 0


    def reset_runtime(self) -> None:
        """Clear only in-memory preview/session state for a new program run."""
        with self._lock:
            self._live_strokes = []
            self._detected_strokes = []
            self._robot_actions = []
            self._live_status = "Waiting for tablet..."
            self._detected_status = "No Detect snapshot in this run"
            self._job_status = "No robot job in this run"
            self._saved_to = ""
            self._robot_job_file = ""
            self._robot_job_mode = ""
            self._canvas_size_px = 0
            self._version += 1

    def update_live(self, strokes: StrokeList, canvas_size_px: int = 0) -> None:
        with self._lock:
            self._live_strokes = deepcopy(strokes)
            self._live_status = "Live tablet data"
            self._canvas_size_px = int(canvas_size_px or 0)
            self._version += 1

    def clear_live(self) -> None:
        with self._lock:
            self._live_strokes = []
            self._live_status = "Tablet canvas cleared"
            self._canvas_size_px = 0
            self._version += 1

    def update_detected(
        self,
        detected_strokes: StrokeList,
        saved_to: str,
        canvas_size_px: int = 0,
    ) -> None:
        with self._lock:
            self._detected_strokes = deepcopy(detected_strokes)
            self._detected_status = "Latest Detect snapshot"
            self._saved_to = saved_to
            self._canvas_size_px = int(canvas_size_px or 0)
            self._version += 1

    def update_robot_job(
        self,
        actions: ActionList,
        job_file: str,
        mode: str,
        status: str,
    ) -> None:
        with self._lock:
            self._robot_actions = deepcopy(actions)
            self._robot_job_file = job_file
            self._robot_job_mode = mode
            self._job_status = status
            self._version += 1

    def update_job_status(self, status: str) -> None:
        with self._lock:
            self._job_status = status
            self._version += 1

    def snapshot(self) -> PreviewSnapshot:
        with self._lock:
            return PreviewSnapshot(
                live_strokes=deepcopy(self._live_strokes),
                detected_strokes=deepcopy(self._detected_strokes),
                robot_actions=deepcopy(self._robot_actions),
                live_status=self._live_status,
                detected_status=self._detected_status,
                job_status=self._job_status,
                saved_to=self._saved_to,
                robot_job_file=self._robot_job_file,
                robot_job_mode=self._robot_job_mode,
                canvas_size_px=self._canvas_size_px,
                version=self._version,
            )


preview_state = PreviewState()

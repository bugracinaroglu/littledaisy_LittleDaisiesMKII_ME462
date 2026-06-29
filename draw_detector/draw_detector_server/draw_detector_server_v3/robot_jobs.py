"""Create robot jobs only when the explicit terminal send command is issued."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Literal, Tuple

import config
from preview_state import preview_state

Drawing = Dict[str, Any]
Stroke = Dict[str, Any]
Action = Dict[str, Any]
RobotMode = Literal["difference", "full_redraw"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def _atomic_json_write(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temp:
        json.dump(payload, temp, indent=2)
        temp_path = Path(temp.name)
    os.replace(temp_path, path)


def load_json(path: Path) -> Drawing:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def newest_detected_drawing() -> Tuple[Path, Drawing]:
    files = list(Path(config.OUTPUT_DIR).glob("drawing_*.json"))
    if not files:
        raise FileNotFoundError("No Detect snapshot exists in output/.")
    path = max(files, key=lambda item: item.stat().st_mtime_ns)
    return path, load_json(path)


def empty_committed_state() -> Drawing:
    return {
        "drawing_id": "robot-empty-state",
        "timestamp": None,
        "coordinate_system": config.OUTPUT_COORDINATE_SYSTEM,
        "strokes": [],
    }


def load_committed_state() -> Drawing:
    path = Path(config.ROBOT_COMMITTED_STATE_FILE)
    if not path.is_file():
        return empty_committed_state()
    payload = load_json(path)
    drawing = payload.get("drawing")
    return drawing if isinstance(drawing, dict) else empty_committed_state()


def _stroke_map(drawing: Drawing) -> Dict[str, Stroke]:
    result: Dict[str, Stroke] = {}
    for index, stroke in enumerate(drawing.get("strokes", [])):
        if not isinstance(stroke, dict):
            continue
        stroke_id = str(stroke.get("stroke_id") or f"legacy-{index}")
        item = deepcopy(stroke)
        item["stroke_id"] = stroke_id
        result[stroke_id] = item
    return result


def _points_same(a: Stroke, b: Stroke, tolerance: float) -> bool:
    points_a = a.get("points", [])
    points_b = b.get("points", [])
    if len(points_a) != len(points_b):
        return False
    for point_a, point_b in zip(points_a, points_b):
        if len(point_a) < 2 or len(point_b) < 2:
            return False
        if math.hypot(
            float(point_a[0]) - float(point_b[0]),
            float(point_a[1]) - float(point_b[1]),
        ) > tolerance:
            return False
    return True


def build_difference_actions(previous: Drawing, current: Drawing) -> List[Action]:
    """Compare committed and target drawings by stable stroke identity.

    Pixel erasing intentionally replaces a modified stroke with new segment IDs.
    Therefore the old committed stroke becomes an `erase`, and surviving new
    segments become `draw` actions. This avoids ambiguous partial mutations.
    """
    old_map = _stroke_map(previous)
    new_map = _stroke_map(current)
    same: List[Action] = []
    erase: List[Action] = []
    draw: List[Action] = []

    for stroke_id, old_stroke in old_map.items():
        new_stroke = new_map.get(stroke_id)
        if new_stroke is None:
            erase.append({
                "type": "erase",
                "stroke_id": stroke_id,
                "points": deepcopy(old_stroke.get("points", [])),
                "reason": "removed_or_replaced",
            })
        elif _points_same(old_stroke, new_stroke, config.STROKE_SAME_TOLERANCE):
            same.append({
                "type": "same",
                "stroke_id": stroke_id,
                "points": deepcopy(new_stroke.get("points", [])),
            })
        else:
            erase.append({
                "type": "erase",
                "stroke_id": stroke_id,
                "points": deepcopy(old_stroke.get("points", [])),
                "reason": "geometry_modified",
            })
            draw.append({
                "type": "draw",
                "stroke_id": stroke_id,
                "points": deepcopy(new_stroke.get("points", [])),
                "reason": "geometry_modified",
            })

    for stroke_id, new_stroke in new_map.items():
        if stroke_id in old_map:
            continue
        action: Action = {
            "type": "draw",
            "stroke_id": stroke_id,
            "points": deepcopy(new_stroke.get("points", [])),
            "reason": "new_or_replacement_segment",
        }
        parent_id = new_stroke.get("parent_stroke_id")
        if parent_id:
            action["parent_stroke_id"] = parent_id
        draw.append(action)

    # Physical execution should erase before drawing. `same` is retained only
    # for logging and the right-hand preview; it is not a robot movement.
    return erase + draw + same


def build_full_redraw_actions(current: Drawing) -> List[Action]:
    actions: List[Action] = [{"type": "erase_all"}]
    for stroke_id, stroke in _stroke_map(current).items():
        actions.append({
            "type": "draw",
            "stroke_id": stroke_id,
            "points": deepcopy(stroke.get("points", [])),
            "reason": "full_redraw",
        })
    return actions


def _job_stats(actions: Iterable[Action]) -> Dict[str, int]:
    counts = {"erase_all": 0, "erase": 0, "draw": 0, "same": 0}
    for action in actions:
        action_type = str(action.get("type", ""))
        if action_type in counts:
            counts[action_type] += 1
    return counts


class RobotJobManager:
    def __init__(self) -> None:
        self._lock = Lock()
        self._mode: RobotMode = config.DEFAULT_ROBOT_JOB_MODE  # type: ignore[assignment]

    @property
    def mode(self) -> RobotMode:
        with self._lock:
            return self._mode

    def set_mode(self, mode: str) -> RobotMode:
        if mode not in ("difference", "full_redraw"):
            raise ValueError("mode must be 'difference' or 'full_redraw'")
        with self._lock:
            self._mode = mode  # type: ignore[assignment]
            selected = self._mode
        preview_state.update_job_status(f"Robot mode selected: {selected}")
        return selected

    def send_latest_to_robot(self) -> Dict[str, Any] | None:
        """Build exactly one job from committed state to newest Detect snapshot.

        In the current project this method simulates the robot transport. The
        comparison state is committed only after a successful simulated ACK.
        """
        with self._lock:
            target_path, target = newest_detected_drawing()
            previous = load_committed_state()

            target_id = str(target.get("drawing_id") or target_path.stem)
            previous_id = str(previous.get("drawing_id") or "")
            if target_id == previous_id:
                message = "Latest Detect snapshot is already committed; no new job."
                preview_state.update_job_status(message)
                print(f"[robot] {message}")
                return None

            mode = self._mode
            if mode == "difference":
                actions = build_difference_actions(previous, target)
            else:
                actions = build_full_redraw_actions(target)

            job_id = f"job_{_timestamp_for_filename()}"
            job: Dict[str, Any] = {
                "job_id": job_id,
                "created_at": _now_iso(),
                "mode": mode,
                "coordinate_system": config.OUTPUT_COORDINATE_SYSTEM,
                "source_drawing_id": previous_id,
                "target_drawing_id": target_id,
                "target_file": target_path.name,
                "stats": _job_stats(actions),
                "actions": actions,
                "status": "created",
            }

            job_path = Path(config.ROBOT_JOBS_DIR) / f"{job_id}.json"
            _atomic_json_write(job_path, job)
            shutil.copyfile(job_path, config.LATEST_ROBOT_JOB_FILE)

            preview_state.update_robot_job(
                actions=actions,
                job_file=job_path.name,
                mode=mode,
                status="Robot job created; waiting for acknowledgement",
            )

            success = self._send_to_transport(job)
            if success:
                job["status"] = "acknowledged"
                job["acknowledged_at"] = _now_iso()
                _atomic_json_write(job_path, job)
                shutil.copyfile(job_path, config.LATEST_ROBOT_JOB_FILE)
                committed = {
                    "committed_at": job["acknowledged_at"],
                    "source_job": job_path.name,
                    "source_output_file": target_path.name,
                    "drawing": target,
                }
                _atomic_json_write(Path(config.ROBOT_COMMITTED_STATE_FILE), committed)
                preview_state.update_robot_job(
                    actions=actions,
                    job_file=job_path.name,
                    mode=mode,
                    status="Robot job acknowledged; comparison state committed",
                )
                print(f"[robot] Job acknowledged and committed: {job_path}")
            else:
                job["status"] = "failed"
                job["failed_at"] = _now_iso()
                _atomic_json_write(job_path, job)
                shutil.copyfile(job_path, config.LATEST_ROBOT_JOB_FILE)
                preview_state.update_robot_job(
                    actions=actions,
                    job_file=job_path.name,
                    mode=mode,
                    status="Robot send failed; committed state unchanged",
                )
                print("[robot] Send failed; committed state was not changed.")
            return job

    @staticmethod
    def _send_to_transport(job: Dict[str, Any]) -> bool:
        if config.SIMULATE_ROBOT_ACK:
            stats = job.get("stats", {})
            print(
                "[robot simulation] send_data2robot_arm -> "
                f"mode={job.get('mode')} stats={stats}"
            )
            return True
        raise NotImplementedError(
            "Connect the physical robot transport here and return True only "
            "after receiving a robot ACK."
        )

    def describe_state(self) -> str:
        committed = load_committed_state()
        try:
            newest_path, newest = newest_detected_drawing()
            newest_text = f"{newest.get('drawing_id', newest_path.stem)} ({newest_path.name})"
        except FileNotFoundError:
            newest_text = "none"
        return (
            f"mode={self.mode} | committed="
            f"{committed.get('drawing_id', 'robot-empty-state')} | latest_detected={newest_text}"
        )


robot_job_manager = RobotJobManager()

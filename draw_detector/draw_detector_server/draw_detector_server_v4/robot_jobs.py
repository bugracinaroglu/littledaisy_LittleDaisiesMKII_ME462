"""Create robot jobs only when explicit send commands are issued.

Historical Detect snapshots remain in output/. Runtime comparison state and old
robot jobs are cleared on every program start. A one-shot startup erase-all job
can optionally be sent so the physical surface and empty comparison state agree.
"""

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


def _delete_json_files(directory: Path) -> int:
    """Delete runtime JSON files while leaving .gitkeep and other files alone."""
    if not directory.exists():
        return 0
    count = 0
    for path in directory.glob("*.json"):
        if path.is_file():
            path.unlink()
            count += 1
    return count


def reset_runtime_storage() -> Dict[str, int]:
    """Clear old comparison/job runtime files but preserve output snapshots."""
    removed_comparison = 0
    removed_jobs = 0
    if config.RESET_COMPARISON_STATE_ON_START:
        removed_comparison = _delete_json_files(Path(config.COMPARISON_STATE_DIR))
    if config.RESET_ROBOT_JOBS_ON_START:
        removed_jobs = _delete_json_files(Path(config.ROBOT_JOBS_DIR))
    return {
        "comparison_files_removed": removed_comparison,
        "robot_job_files_removed": removed_jobs,
    }


def current_run_detected_drawing() -> Tuple[Path, Drawing]:
    """Return only the Detect snapshot created in this process run.

    output/ may contain historical drawings. They are intentionally ignored until
    the tablet presses Detect during the current run, preventing an old drawing
    from being sent accidentally after startup.
    """
    filename = preview_state.snapshot().saved_to
    if not filename:
        raise FileNotFoundError(
            "No Detect snapshot exists in the current program run. Press Detect first."
        )
    if Path(filename).name != filename:
        raise ValueError("Invalid active Detect filename.")
    path = Path(config.OUTPUT_DIR) / filename
    if not path.is_file():
        raise FileNotFoundError(f"Current-run Detect snapshot is missing: {path}")
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


def clear_committed_state() -> None:
    """Represent a physically empty robot surface by removing committed JSON."""
    path = Path(config.ROBOT_COMMITTED_STATE_FILE)
    if path.exists():
        path.unlink()


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

    Pixel erasing replaces a modified stroke with new segment IDs. Therefore the
    old committed stroke becomes `erase`, and surviving segments become `draw`.
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
    # for logging/preview and need not be sent as a motion command.
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


def build_full_erase_actions() -> List[Action]:
    """Return a path-free full-clean command for the robot controller."""
    return [{"type": "erase_all"}]


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
        self._surface_ready = not config.STARTUP_FULL_ERASE_ENABLED
        self._startup_erase_status = "not-run"

    @property
    def mode(self) -> RobotMode:
        with self._lock:
            return self._mode

    def reset_for_program_start(self) -> Dict[str, int]:
        """Reset runtime state, preserving only timestamped output snapshots."""
        with self._lock:
            stats = reset_runtime_storage()
            preview_state.reset_runtime()
            self._mode = config.DEFAULT_ROBOT_JOB_MODE  # type: ignore[assignment]
            self._surface_ready = not config.STARTUP_FULL_ERASE_ENABLED
            self._startup_erase_status = "disabled" if self._surface_ready else "pending"
        print(
            "[startup] runtime state reset: "
            f"comparison={stats['comparison_files_removed']} files, "
            f"robot_jobs={stats['robot_job_files_removed']} files; output preserved"
        )
        return stats

    def set_mode(self, mode: str) -> RobotMode:
        if mode not in ("difference", "full_redraw"):
            raise ValueError("mode must be 'difference' or 'full_redraw'")
        with self._lock:
            self._mode = mode  # type: ignore[assignment]
            selected = self._mode
        preview_state.update_job_status(f"Robot mode selected: {selected}")
        return selected

    def send_startup_full_erase_if_enabled(self) -> Dict[str, Any] | None:
        if not config.STARTUP_FULL_ERASE_ENABLED:
            print(
                "[startup] STARTUP_FULL_ERASE_ENABLED=False. "
                "Comparison starts empty; ensure the physical surface is empty."
            )
            return None
        return self.send_full_erase(reason="startup")

    def send_full_erase(self, reason: str = "manual") -> Dict[str, Any]:
        """Send a path-free erase-all job and clear committed state on ACK."""
        with self._lock:
            actions = build_full_erase_actions()
            job_id = f"job_{_timestamp_for_filename()}"
            job: Dict[str, Any] = {
                "job_id": job_id,
                "created_at": _now_iso(),
                "mode": "full_erase",
                "reason": reason,
                "coordinate_system": config.OUTPUT_COORDINATE_SYSTEM,
                "source_drawing_id": load_committed_state().get("drawing_id"),
                "target_drawing_id": "robot-empty-state",
                "stats": _job_stats(actions),
                "actions": actions,
                "status": "created",
            }
            job_path = self._write_new_job(job)
            preview_state.update_robot_job(
                actions=actions,
                job_file=job_path.name,
                mode="full_erase",
                status=f"Full erase job created ({reason}); waiting for acknowledgement",
            )

            success = self._send_to_transport(job)
            if success:
                job["status"] = "acknowledged"
                job["acknowledged_at"] = _now_iso()
                self._rewrite_job(job_path, job)
                clear_committed_state()
                self._surface_ready = True
                if reason == "startup":
                    self._startup_erase_status = "acknowledged"
                preview_state.update_robot_job(
                    actions=actions,
                    job_file=job_path.name,
                    mode="full_erase",
                    status=f"Full erase acknowledged ({reason}); robot state is empty",
                )
                print(f"[robot] Full erase acknowledged ({reason}): {job_path}")
            else:
                job["status"] = "failed"
                job["failed_at"] = _now_iso()
                self._rewrite_job(job_path, job)
                if reason == "startup":
                    self._startup_erase_status = "failed"
                    self._surface_ready = False
                preview_state.update_robot_job(
                    actions=actions,
                    job_file=job_path.name,
                    mode="full_erase",
                    status=f"Full erase failed ({reason}); comparison remains empty",
                )
                print(f"[robot] Full erase failed ({reason}).")
            return job

    def send_latest_to_robot(self) -> Dict[str, Any] | None:
        """Build one job from empty/committed state to current-run Detect snapshot."""
        with self._lock:
            if not self._surface_ready:
                raise RuntimeError(
                    "Startup full erase was not acknowledged. The physical surface state "
                    "is unknown, so drawing send is blocked."
                )

            target_path, target = current_run_detected_drawing()
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

            job_path = self._write_new_job(job)
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
                self._rewrite_job(job_path, job)
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
                self._rewrite_job(job_path, job)
                preview_state.update_robot_job(
                    actions=actions,
                    job_file=job_path.name,
                    mode=mode,
                    status="Robot send failed; committed state unchanged",
                )
                print("[robot] Send failed; committed state was not changed.")
            return job

    @staticmethod
    def _write_new_job(job: Dict[str, Any]) -> Path:
        job_path = Path(config.ROBOT_JOBS_DIR) / f"{job['job_id']}.json"
        _atomic_json_write(job_path, job)
        shutil.copyfile(job_path, config.LATEST_ROBOT_JOB_FILE)
        return job_path

    @staticmethod
    def _rewrite_job(job_path: Path, job: Dict[str, Any]) -> None:
        _atomic_json_write(job_path, job)
        shutil.copyfile(job_path, config.LATEST_ROBOT_JOB_FILE)

    @staticmethod
    def _send_to_transport(job: Dict[str, Any]) -> bool:
        """Robot integration point.

        For `erase_all`, the robot controller defines its own complete cleaning
        path. This project intentionally sends no erase trajectory coordinates.
        """
        if config.SIMULATE_ROBOT_ACK:
            stats = job.get("stats", {})
            print(
                "[robot simulation] send -> "
                f"mode={job.get('mode')} reason={job.get('reason', '-')} stats={stats}"
            )
            return True
        raise NotImplementedError(
            "Connect the physical robot transport here and return True only "
            "after receiving a robot ACK. The robot controller must implement "
            "the path for the erase_all action."
        )

    def describe_state(self) -> str:
        committed = load_committed_state()
        try:
            current_path, current = current_run_detected_drawing()
            detected_text = f"{current.get('drawing_id', current_path.stem)} ({current_path.name})"
        except FileNotFoundError:
            detected_text = "none in current run"
        return (
            f"mode={self.mode} | committed={committed.get('drawing_id', 'robot-empty-state')} "
            f"| current_detected={detected_text} | surface_ready={self._surface_ready} "
            f"| startup_erase={self._startup_erase_status}"
        )


robot_job_manager = RobotJobManager()

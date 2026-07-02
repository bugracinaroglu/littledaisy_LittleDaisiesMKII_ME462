"""Timestamped robot jobs plus a single ordered ``latest_job.json`` manifest.

Storage layout::

    robot_jobs/
    ├── jobs/
    │   ├── job_<timestamp>_full_erase.json
    │   ├── job_<timestamp>_difference.json
    │   └── job_<timestamp>_full_redraw.json
    └── latest_job.json

Each robot operation is stored once in its own timestamped JSON file.  The
``latest_job.json`` file is an ordered queue manifest: it does not duplicate the
large action/point arrays.  Instead, it lists each job file, queue position and
status.  A ROS node can therefore watch/publish one small manifest, then load or
publish the referenced executable job JSON when its turn arrives.

Drawing comparison is intentionally delayed until a pending drawing job reaches
the front of the queue.  This guarantees that back-to-back jobs are compared
against the state committed by the previously completed job.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from typing import Any, Dict, Iterable, List, Literal, Tuple

import config
from preview_state import preview_state

Drawing = Dict[str, Any]
Stroke = Dict[str, Any]
Action = Dict[str, Any]
Point = List[float]
RobotMode = Literal["difference", "full_redraw"]
JobStatus = Literal["pending", "processing", "completed", "failed"]

_MANIFEST_SCHEMA_VERSION = 1
_VALID_STATUSES = ("pending", "processing", "completed", "failed")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")


def _timestamp_token() -> str:
    # Microseconds preserve lexical FIFO order and avoid filename collisions.
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


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


def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _jobs_dir() -> Path:
    # Derive dynamically so tests/runtime path overrides only need ROBOT_JOBS_DIR.
    return Path(config.ROBOT_JOBS_DIR) / "jobs"


def _manifest_path() -> Path:
    return Path(config.ROBOT_JOBS_DIR) / "latest_job.json"


def _empty_manifest() -> Dict[str, Any]:
    now = _now_iso()
    return {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "queue": [],
        "active_job_id": None,
        "last_completed_job_id": None,
    }


def ensure_job_storage() -> None:
    Path(config.ROBOT_JOBS_DIR).mkdir(parents=True, exist_ok=True)
    _jobs_dir().mkdir(parents=True, exist_ok=True)
    keep = _jobs_dir() / ".gitkeep"
    if not keep.exists():
        keep.touch()
    if not _manifest_path().is_file():
        _atomic_json_write(_manifest_path(), _empty_manifest())


def _load_manifest() -> Dict[str, Any]:
    ensure_job_storage()
    manifest = load_json(_manifest_path())
    queue = manifest.get("queue")
    if not isinstance(queue, list):
        raise ValueError("latest_job.json must contain a 'queue' list.")
    return manifest


def _write_manifest(manifest: Dict[str, Any]) -> None:
    manifest = deepcopy(manifest)
    manifest["schema_version"] = _MANIFEST_SCHEMA_VERSION
    manifest["updated_at"] = _now_iso()
    _atomic_json_write(_manifest_path(), manifest)


def _delete_json_files(directory: Path, *, recursive: bool = False) -> int:
    """Delete JSON files while preserving directories and non-JSON files."""
    if not directory.exists():
        return 0
    paths = directory.rglob("*.json") if recursive else directory.glob("*.json")
    count = 0
    for path in list(paths):
        if path.is_file():
            path.unlink()
            count += 1
    return count


def reset_runtime_storage() -> Dict[str, int]:
    """Apply startup cleanup policy and recreate the job manifest."""
    removed_output = 0
    removed_comparison = 0
    removed_jobs = 0
    if config.STARTUP_OUTPUT_ERASE_ENABLED:
        removed_output = _delete_json_files(Path(config.OUTPUT_DIR))
    if config.RESET_COMPARISON_STATE_ON_START:
        removed_comparison = _delete_json_files(Path(config.COMPARISON_STATE_DIR))
    if config.RESET_ROBOT_JOBS_ON_START:
        removed_jobs = _delete_json_files(Path(config.ROBOT_JOBS_DIR), recursive=True)
    ensure_job_storage()
    # Always start this program run with an explicit, valid queue manifest.
    if config.RESET_ROBOT_JOBS_ON_START:
        _atomic_json_write(_manifest_path(), _empty_manifest())
    return {
        "output_files_removed": removed_output,
        "comparison_files_removed": removed_comparison,
        "robot_job_files_removed": removed_jobs,
    }


def current_run_detected_drawing() -> Tuple[Path, Drawing]:
    """Return only the Detect snapshot created during this process run."""
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


def _pt_close(p: Point, q: Point, tolerance: float) -> bool:
    if len(p) < 2 or len(q) < 2:
        return False
    return math.hypot(
        float(p[0]) - float(q[0]),
        float(p[1]) - float(q[1]),
    ) <= tolerance


def _point_key(point: Point) -> Tuple[float, float]:
    """Quantized key for fast first-point lookup (raw mode coords are exact)."""
    return (round(float(point[0]), 9), round(float(point[1]), 9))


def _first_point_index(points: List[Point]) -> Dict[Tuple[float, float], List[int]]:
    """Map each point key to the indices where it occurs, for fast matching."""
    index: Dict[Tuple[float, float], List[int]] = {}
    for i, point in enumerate(points):
        if len(point) < 2:
            continue
        index.setdefault(_point_key(point), []).append(i)
    return index


def _subsequence_start(
    fragment: List[Point],
    parent_points: List[Point],
    parent_index: Dict[Tuple[float, float], List[int]],
    tolerance: float,
) -> int | None:
    """Return the start index if ``fragment`` is a contiguous run inside
    ``parent_points`` (within ``tolerance``), else ``None``.

    Identity does not rely on stroke ids. A pixel-eraser only deletes points,
    so any surviving piece is still an ordered, contiguous slice of the stroke
    it came from, regardless of how many erase passes (and id regenerations)
    happened. Matching by geometry therefore stays correct even when the
    ``parent_stroke_id`` chain points at intermediate ids that were never
    committed.
    """
    frag_len = len(fragment)
    parent_len = len(parent_points)
    if frag_len == 0 or frag_len > parent_len:
        return None
    candidates = parent_index.get(_point_key(fragment[0]), [])
    for start in candidates:
        if start + frag_len > parent_len:
            continue
        if all(
            _pt_close(fragment[k], parent_points[start + k], tolerance)
            for k in range(frag_len)
        ):
            return start
    return None


def build_difference_actions(previous: Drawing, current: Drawing) -> List[Action]:
    """Build erase/draw/same actions using geometric stroke identity.

    Surviving pixel-eraser fragments are detected by geometry, not by stroke
    id: a new stroke that is a contiguous slice of a committed stroke is a
    survivor of that stroke. Survivors are already on the surface, so they are
    kept (``same``) instead of redrawn, and only the uncovered gap(s) of the
    committed stroke are erased. A new stroke that matches no committed stroke
    is genuinely new and is drawn; a committed stroke with no surviving slice
    is fully erased.
    """
    old_map = _stroke_map(previous)
    new_map = _stroke_map(current)
    same: List[Action] = []
    erase: List[Action] = []
    draw: List[Action] = []
    tolerance = config.STROKE_SAME_TOLERANCE

    # Precompute a first-point index per committed stroke for fast matching.
    old_points = {oid: o.get("points", []) for oid, o in old_map.items()}
    old_index = {oid: _first_point_index(pts) for oid, pts in old_points.items()}

    # coverage[old_id] = list of (start_index, fragment_length, new_stroke)
    coverage: Dict[str, List[Tuple[int, int, Stroke]]] = {}
    unmatched_new: List[Stroke] = []

    for new_id, new_stroke in new_map.items():
        new_points = new_stroke.get("points", [])
        matched_old: str | None = None
        matched_start: int | None = None

        # Fast path: a stroke that kept its id and is still a slice of itself.
        if new_id in old_map:
            start = _subsequence_start(
                new_points, old_points[new_id], old_index[new_id], tolerance
            )
            if start is not None:
                matched_old, matched_start = new_id, start

        # General path: find any committed stroke that contains this slice.
        if matched_old is None:
            for old_id, parent_points in old_points.items():
                start = _subsequence_start(
                    new_points, parent_points, old_index[old_id], tolerance
                )
                if start is not None:
                    matched_old, matched_start = old_id, start
                    break

        if matched_old is None or matched_start is None:
            unmatched_new.append(new_stroke)
        else:
            coverage.setdefault(matched_old, []).append(
                (matched_start, len(new_points), new_stroke)
            )

    handled_old: set[str] = set()

    # Committed strokes that have at least one surviving slice.
    for old_id, covers in coverage.items():
        handled_old.add(old_id)
        parent_points = old_points[old_id]
        covered = [False] * len(parent_points)
        for start, length, new_stroke in covers:
            for i in range(start, min(start + length, len(covered))):
                covered[i] = True
            full = length == len(parent_points) and start == 0
            same.append({
                "type": "same",
                "stroke_id": new_stroke["stroke_id"],
                "points": deepcopy(new_stroke.get("points", [])),
                "reason": "unchanged" if full else "surviving_fragment",
                "origin_stroke_id": old_id,
            })
        # Each maximal run of uncovered committed points is an erased gap.
        gap: List[Point] = []
        for i, is_covered in enumerate(covered):
            if not is_covered:
                gap.append(parent_points[i])
            elif gap:
                erase.append({
                    "type": "erase",
                    "stroke_id": old_id,
                    "points": deepcopy(gap),
                    "reason": "partial_erase",
                })
                gap = []
        if gap:
            erase.append({
                "type": "erase",
                "stroke_id": old_id,
                "points": deepcopy(gap),
                "reason": "partial_erase",
            })

    # Committed strokes with no surviving slice at all -> fully erased.
    for old_id, old_stroke in old_map.items():
        if old_id in handled_old:
            continue
        erase.append({
            "type": "erase",
            "stroke_id": old_id,
            "points": deepcopy(old_stroke.get("points", [])),
            "reason": "removed_or_replaced",
        })

    # Genuinely new strokes (no committed stroke contains them).
    for new_stroke in unmatched_new:
        action: Action = {
            "type": "draw",
            "stroke_id": new_stroke["stroke_id"],
            "points": deepcopy(new_stroke.get("points", [])),
            "reason": "new_or_replacement_segment",
        }
        parent_id = new_stroke.get("parent_stroke_id")
        if parent_id:
            action["parent_stroke_id"] = parent_id
        draw.append(action)

    # Erase first, then draw. `same` is retained for preview/logging only.
    smart_erase = _smart_erase_consolidation(erase, draw, same)
    return smart_erase + draw + same

def _smart_erase_consolidation(erase: List[Action], draw: List[Action], same: List[Action]) -> List[Action]:
    if not erase:
        return []
        
    import math
    try:
        from shapely.geometry import Point, LineString, Polygon
        from shapely.ops import unary_union
    except ImportError:
        print("[WARNING] 'shapely' is not installed! pip install shapely to enable the Delete Solver.")
        return erase # Return raw erase actions without consolidation
        
    # Gather all surviving points into a Shapely Obstacle geometry
    obstacle_geoms = []
    for action in draw + same:
        pts = action.get("points", [])
        if len(pts) >= 2:
            physical_pts = [(p[0] * config.BOARD_WIDTH_M, p[1] * config.BOARD_HEIGHT_M) for p in pts]
            obstacle_geoms.append(LineString(physical_pts))
        elif len(pts) == 1:
            p = pts[0]
            obstacle_geoms.append(Point(p[0] * config.BOARD_WIDTH_M, p[1] * config.BOARD_HEIGHT_M))
            
    if obstacle_geoms:
        # Buffer by 2.5mm to represent 5mm pen thickness footprint
        obstacles = unary_union(obstacle_geoms).buffer(0.0025)
    else:
        obstacles = Polygon() # Empty
        
    # Helper to calculate the exact swept volume convex hull of a moving rectangle
    def swept_poly(p1x, p1y, p2x, p2y, w, t):
        dx = p2x - p1x
        dy = p2y - p1y
        angle = math.atan2(dy, dx) if (dx!=0 or dy!=0) else 0
        pa = angle + math.pi/2
        hl = w/2.0
        ht = t/2.0
        v_px, v_py = math.cos(pa)*hl, math.sin(pa)*hl
        v_nx, v_ny = math.cos(angle)*ht, math.sin(angle)*ht
        r1 = Polygon([(p1x+v_px+v_nx, p1y+v_py+v_ny), (p1x-v_px+v_nx, p1y-v_py+v_ny), (p1x-v_px-v_nx, p1y-v_py-v_ny), (p1x+v_px-v_nx, p1y+v_py-v_ny)])
        r2 = Polygon([(p2x+v_px+v_nx, p2y+v_py+v_ny), (p2x-v_px+v_nx, p2y-v_py+v_ny), (p2x-v_px-v_nx, p2y-v_py-v_ny), (p2x+v_px-v_nx, p2y+v_py-v_ny)])
        return unary_union([r1, r2]).convex_hull
        
    smart_erase_actions: List[Action] = []
    
    for e_action in erase:
        pts = e_action.get("points", [])
        if len(pts) < 2:
            smart_erase_actions.append(e_action)
            continue
            
        xs = [p[0] * config.BOARD_WIDTH_M for p in pts]
        ys = [p[1] * config.BOARD_HEIGHT_M for p in pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Tool Dimensions
        squeegee_width = 0.15 # 15cm wide tool
        squeegee_thick = 0.02 # 2cm thick
        
        # STRATEGY 1 & 2: Macro Lawnmower Sweeps
        # ONLY trigger if the deleted area is a MASSIVE 2D block (both width and height are large).
        # We do not use this for straight lines! Straight lines must be cross-hatched.
        if width > config.MACRO_WIPE_THRESHOLD_M and height > config.MACRO_WIPE_THRESHOLD_M:
            
            # STRATEGY 1: Horizontal Squeegee Lawnmower
            num_h_sweeps = max(1, int(math.ceil(height / 0.14)))
            h_safe = True
            h_actions = []
            
            for j in range(num_h_sweeps):
                # Start the center so the edge hits min_y exactly
                sweep_y = min_y + 0.075 + (j * 0.14)
                # Cap the last sweep so we don't go unnecessarily far out of bounds
                if sweep_y > max_y - 0.075 and j > 0:
                    sweep_y = max_y - 0.075
                    
                p1x, p1y = min_x, sweep_y
                p2x, p2y = max_x, sweep_y
                
                hsweep = swept_poly(p1x, p1y, p2x, p2y, squeegee_width, squeegee_thick)
                if hsweep.intersects(obstacles):
                    h_safe = False
                    break
                    
                norm_y = sweep_y / config.BOARD_HEIGHT_M
                norm_x1 = min_x / config.BOARD_WIDTH_M
                norm_x2 = max_x / config.BOARD_WIDTH_M
                
                # Alternate direction to optimize robot travel
                pts = [[norm_x1, norm_y], [norm_x2, norm_y]] if j % 2 == 0 else [[norm_x2, norm_y], [norm_x1, norm_y]]
                
                h_actions.append({
                    "type": "erase_squeegee",
                    "stroke_id": e_action.get("stroke_id", "") + f"_macro_h_{j}",
                    "points": pts,
                    "reason": "shapely_safe_macro_horizontal"
                })
                
            if h_safe and len(h_actions) > 0:
                smart_erase_actions.extend(h_actions)
                continue
                
            # STRATEGY 2: Vertical Squeegee Lawnmower
            num_v_sweeps = max(1, int(math.ceil(width / 0.14)))
            v_safe = True
            v_actions = []
            
            for j in range(num_v_sweeps):
                sweep_x = min_x + 0.075 + (j * 0.14)
                if sweep_x > max_x - 0.075 and j > 0:
                    sweep_x = max_x - 0.075
                    
                p1x, p1y = sweep_x, min_y
                p2x, p2y = sweep_x, max_y
                
                vsweep = swept_poly(p1x, p1y, p2x, p2y, squeegee_width, squeegee_thick)
                if vsweep.intersects(obstacles):
                    v_safe = False
                    break
                    
                norm_x = sweep_x / config.BOARD_WIDTH_M
                norm_y1 = min_y / config.BOARD_HEIGHT_M
                norm_y2 = max_y / config.BOARD_HEIGHT_M
                
                # Alternate direction
                pts = [[norm_x, norm_y1], [norm_x, norm_y2]] if j % 2 == 0 else [[norm_x, norm_y2], [norm_x, norm_y1]]
                
                v_actions.append({
                    "type": "erase_squeegee",
                    "stroke_id": e_action.get("stroke_id", "") + f"_macro_v_{j}",
                    "points": pts,
                    "reason": "shapely_safe_macro_vertical"
                })
                
            if v_safe and len(v_actions) > 0:
                smart_erase_actions.extend(v_actions)
                continue
                
        # STRATEGY 3: Hybrid Adaptive Trace (Squeegee Sliding Trick -> Finger Auto-Shifting)
        # This unified loop elegantly downshifts from Squeegee to Finger based on local collisions!
        
        # Calculate Straightness Ratio
        total_path_length = 0.0
        for i in range(1, len(xs)):
            total_path_length += math.hypot(xs[i] - xs[i-1], ys[i] - ys[i-1])
            
        euclidean_dist = math.hypot(xs[-1] - xs[0], ys[-1] - ys[0])
        straightness = euclidean_dist / total_path_length if total_path_length > 0 else 1.0
        
        # Unconditional Squeegee Stepping (4cm as requested)
        sq_step_dist = 0.04
        
        # Resample entire path to 2cm resolution for finger zigzag step distance
        step_size = 0.02
        resampled_pts = [(xs[0], ys[0])]
        current_dist = 0.0
        target_dist = step_size
        
        for i in range(1, len(xs)):
            p1x, p1y = xs[i-1], ys[i-1]
            p2x, p2y = xs[i], ys[i]
            segment_len = math.hypot(p2x - p1x, p2y - p1y)
            
            while current_dist + segment_len >= target_dist:
                overshoot = target_dist - current_dist
                t = overshoot / segment_len if segment_len > 0 else 0
                nx = p1x + t * (p2x - p1x)
                ny = p1y + t * (p2y - p1y)
                resampled_pts.append((nx, ny))
                target_dist += step_size
            
            current_dist += segment_len
            
        # Ensure the tail end is covered
        last_rx, last_ry = resampled_pts[-1]
        if math.hypot(xs[-1] - last_rx, ys[-1] - last_ry) > 0.005:
            resampled_pts.append((xs[-1], ys[-1]))
            
        # Tool specs
        finger_width = 0.02
        finger_thick = 0.005
        sweep_radius_sq = 0.03 # 3cm radius -> 6cm total squeegee sweep
        sweep_radius_fg = 0.02 # 2cm radius -> 4cm total finger sweep
        
        sq_step_points = max(1, int(sq_step_dist / step_size))
        
        # We group the actions by tool to minimize physical tool changes on the UR5e!
        hybrid_sq_actions = []
        hybrid_fg_actions = []
        
        i = 0
        while i < len(resampled_pts) - 1:
            # 1. ATTEMPT SQUEEGEE FOR THIS BLOCK
            end_idx_sq = min(i + sq_step_points, len(resampled_pts) - 1)
            p_start_sq = resampled_pts[i]
            p_end_sq = resampled_pts[end_idx_sq]
            
            seg_dx = p_end_sq[0] - p_start_sq[0]
            seg_dy = p_end_sq[1] - p_start_sq[1]
            seg_length = math.hypot(seg_dx, seg_dy)
            
            cx = (p_start_sq[0] + p_end_sq[0]) / 2.0
            cy = (p_start_sq[1] + p_end_sq[1]) / 2.0
            
            ux = seg_dx / seg_length if seg_length > 0 else 0
            uy = seg_dy / seg_length if seg_length > 0 else 0
            
            # The distance to shift the squeegee center to perfectly align its edges
            shift_dist = (squeegee_width - seg_length) / 2.0
            if shift_dist < 0: shift_dist = 0
            
            # 3 Possible Squeegee Placements (Sliding Trick)
            test_centers = [
                (cx, cy), # Centered (equally distributed overhang)
                (cx + ux * shift_dist, cy + uy * shift_dist), # Shifted Forward (back edge aligned)
                (cx - ux * shift_dist, cy - uy * shift_dist)  # Shifted Backward (front edge aligned)
            ]
            
            angle = math.atan2(seg_dy, seg_dx) if (seg_dx!=0 or seg_dy!=0) else 0
            perp_angle = angle + math.pi / 2
            v_px_sq = math.cos(perp_angle) * sweep_radius_sq
            v_py_sq = math.sin(perp_angle) * sweep_radius_sq
            
            sq_safe = False
            for tcx, tcy in test_centers:
                start_x_sq = tcx + v_px_sq
                start_y_sq = tcy + v_py_sq
                end_x_sq = tcx - v_px_sq
                end_y_sq = tcy - v_py_sq
                
                ssweep = swept_poly(start_x_sq, start_y_sq, end_x_sq, end_y_sq, squeegee_width, squeegee_thick)
                if not ssweep.intersects(obstacles):
                    norm_sx = start_x_sq / config.BOARD_WIDTH_M
                    norm_sy = start_y_sq / config.BOARD_HEIGHT_M
                    norm_ex = end_x_sq / config.BOARD_WIDTH_M
                    norm_ey = end_y_sq / config.BOARD_HEIGHT_M
                    
                    hybrid_sq_actions.append({
                        "type": "erase_squeegee",
                        "stroke_id": e_action.get("stroke_id", "") + f"_hybrid_sq_{i}",
                        "segment_idx": i,
                        "points": [[norm_sx, norm_sy], [norm_ex, norm_ey]],
                        "yaw": angle,
                        "reason": "shapely_hybrid_squeegee"
                    })
                    sq_safe = True
                    break
                    
            if sq_safe:
                i = end_idx_sq
                continue
                
            # 2. ALL 3 SQUEEGEE POSITIONS FAILED! FALLBACK TO FINGER FOR THIS 1CM SEGMENT
            p_start_fg = resampled_pts[i]
            p_end_fg = resampled_pts[i+1]
            
            cx = (p_start_fg[0] + p_end_fg[0]) / 2.0
            cy = (p_start_fg[1] + p_end_fg[1]) / 2.0
            dx = p_end_fg[0] - p_start_fg[0]
            dy = p_end_fg[1] - p_start_fg[1]
            
            angle = math.atan2(dy, dx) if (dx!=0 or dy!=0) else 0
            perp_angle = angle + math.pi / 2
            
            v_px_fg = math.cos(perp_angle) * sweep_radius_fg
            v_py_fg = math.sin(perp_angle) * sweep_radius_fg
            
            start_x_fg = cx + v_px_fg
            start_y_fg = cy + v_py_fg
            end_x_fg = cx - v_px_fg
            end_y_fg = cy - v_py_fg
            
            # Note: We execute the finger even if it technically hits obstacles, 
            # because the finger is the ultimate fallback tool and must erase the sand.
            norm_sx = start_x_fg / config.BOARD_WIDTH_M
            norm_sy = start_y_fg / config.BOARD_HEIGHT_M
            norm_ex = end_x_fg / config.BOARD_WIDTH_M
            norm_ey = end_y_fg / config.BOARD_HEIGHT_M
            
            hybrid_fg_actions.append({
                "type": "erase_finger",
                "stroke_id": e_action.get("stroke_id", "") + f"_hybrid_fg_{i}",
                "segment_idx": i,
                "points": [[norm_sx, norm_sy], [norm_ex, norm_ey]],
                "yaw": angle,
                "reason": "shapely_hybrid_finger"
            })
            i += 1
            
        def zigzag_group(actions, step_jump):
            if not actions: return []
            grouped = []
            current_group = [actions[0]]
            for k in range(1, len(actions)):
                if actions[k]["segment_idx"] == actions[k-1]["segment_idx"] + step_jump:
                    current_group.append(actions[k])
                else:
                    grouped.append(current_group)
                    current_group = [actions[k]]
            grouped.append(current_group)
            
            final_actions = []
            for g in grouped:
                zz_points = []
                for idx, act in enumerate(g):
                    pts = act["points"]
                    if idx % 2 == 1:
                        zz_points.extend(pts[::-1]) # Reverse for zig-zag
                    else:
                        zz_points.extend(pts)
                
                first_act = g[0]
                first_act.pop("segment_idx", None)
                final_actions.append({
                    "type": first_act["type"],
                    "stroke_id": first_act["stroke_id"] + "_zigzag",
                    "points": zz_points,
                    "yaw": first_act.get("yaw", 0.0),
                    "reason": first_act["reason"]
                })
            return final_actions

        # Group contiguous sweeps into massive zig-zag paths to prevent hovers!
        hybrid_fg_actions = zigzag_group(hybrid_fg_actions, 1)
        hybrid_sq_actions = zigzag_group(hybrid_sq_actions, sq_step_points)

        smart_erase_actions.extend(hybrid_sq_actions)
        smart_erase_actions.extend(hybrid_fg_actions)
            
    return smart_erase_actions


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
    return [{"type": "erase_all"}]


def _job_stats(actions: Iterable[Action]) -> Dict[str, int]:
    counts = {"erase_all": 0, "erase": 0, "draw": 0, "same": 0}
    for action in actions:
        action_type = str(action.get("type", ""))
        if action_type in counts:
            counts[action_type] += 1
    return counts


class RobotJobManager:
    """Manage timestamped job files through an ordered latest_job manifest."""

    def __init__(self) -> None:
        self._state_lock = Lock()
        self._queue_lock = Lock()
        self._mode: RobotMode = config.DEFAULT_ROBOT_JOB_MODE  # type: ignore[assignment]
        self._surface_ready = not config.STARTUP_FULL_ERASE_ENABLED
        self._startup_erase_status = "not-run"
        self._active_job_file = ""
        self._last_completed_job_file = ""
        self._stop_event = Event()
        self._worker_thread: threading.Thread | None = None

    @property
    def mode(self) -> RobotMode:
        with self._state_lock:
            return self._mode

    def reset_for_program_start(self) -> Dict[str, int]:
        self.stop_worker()
        stats = reset_runtime_storage()
        preview_state.reset_runtime()
        with self._state_lock:
            self._mode = config.DEFAULT_ROBOT_JOB_MODE  # type: ignore[assignment]
            self._surface_ready = not config.STARTUP_FULL_ERASE_ENABLED
            self._startup_erase_status = "disabled" if self._surface_ready else "pending"
            self._active_job_file = ""
            self._last_completed_job_file = ""
        output_status = (
            f"output={stats['output_files_removed']} files removed"
            if config.STARTUP_OUTPUT_ERASE_ENABLED
            else "output preserved"
        )
        print(
            "[startup] storage reset: "
            f"{output_status}, "
            f"comparison={stats['comparison_files_removed']} files removed, "
            f"robot_jobs={stats['robot_job_files_removed']} files removed"
        )
        return stats

    def start_worker(self) -> None:
        with self._state_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                return
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="little-daisy-robot-job-worker",
                daemon=True,
            )
            self._worker_thread.start()

    def stop_worker(self) -> None:
        self._stop_event.set()
        thread = self._worker_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._worker_thread = None

    def set_mode(self, mode: str) -> RobotMode:
        if mode not in ("difference", "full_redraw"):
            raise ValueError("mode must be 'difference' or 'full_redraw'")
        with self._state_lock:
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
        job = {
            "job_id": "",
            "created_at": _now_iso(),
            "mode": "full_erase",
            "reason": reason,
            "coordinate_system": config.OUTPUT_COORDINATE_SYSTEM,
            "status": "pending",
            "actions": build_full_erase_actions(),
        }
        path = self._enqueue(job)
        job = load_json(path)
        if reason == "startup":
            with self._state_lock:
                self._startup_erase_status = "queued"
        preview_state.update_robot_job(
            actions=job["actions"],
            job_file=path.name,
            mode="full_erase",
            status=f"Full erase queued ({reason})",
        )
        print(f"[queue] Enqueued full erase: {path.name}")
        return job

    def send_latest_to_robot(self) -> Dict[str, Any]:
        """Enqueue the current-run Detect snapshot; compare only at execution."""
        target_path, target = current_run_detected_drawing()
        mode = self.mode
        job = {
            "job_id": "",
            "created_at": _now_iso(),
            "mode": mode,
            "coordinate_system": config.OUTPUT_COORDINATE_SYSTEM,
            "target_drawing_id": str(target.get("drawing_id") or target_path.stem),
            "target_file": target_path.name,
            "status": "pending",
            "actions": [],
        }
        path = self._enqueue(job)
        job = load_json(path)
        preview_state.update_robot_job(
            actions=[],
            job_file=path.name,
            mode=mode,
            status=f"Queued {mode} job; comparison deferred until execution",
        )
        print(f"[queue] Enqueued drawing job: {path.name} -> {target_path.name}")
        return job

    def _enqueue(self, job: Dict[str, Any]) -> Path:
        ensure_job_storage()
        mode = str(job.get("mode") or "unknown")
        with self._queue_lock:
            filename = f"job_{_timestamp_token()}_{mode}.json"
            path = _jobs_dir() / filename
            while path.exists():
                time.sleep(0.000001)
                filename = f"job_{_timestamp_token()}_{mode}.json"
                path = _jobs_dir() / filename

            job = deepcopy(job)
            job["job_id"] = path.stem
            job["job_file"] = f"jobs/{filename}"
            _atomic_json_write(path, job)

            manifest = _load_manifest()
            queue = manifest["queue"]
            queue.append({
                "sequence": len(queue) + 1,
                "job_id": job["job_id"],
                "job_file": job["job_file"],
                "mode": mode,
                "status": "pending",
                "created_at": job["created_at"],
                "started_at": None,
                "finished_at": None,
            })
            _write_manifest(manifest)
        return path

    def _job_path_from_entry(self, entry: Dict[str, Any]) -> Path:
        relative = str(entry.get("job_file") or "")
        path = Path(config.ROBOT_JOBS_DIR) / relative
        root = Path(config.ROBOT_JOBS_DIR).resolve()
        resolved = path.resolve()
        if root not in resolved.parents or resolved.suffix.lower() != ".json":
            raise ValueError(f"Invalid job_file in latest_job.json: {relative}")
        return resolved

    def _claim_next_job(self) -> Tuple[Path, str] | None:
        """Mark the next eligible manifest entry as processing."""
        with self._queue_lock:
            manifest = _load_manifest()
            pending_entries = [
                entry for entry in manifest["queue"]
                if entry.get("status") == "pending"
            ]
            if not pending_entries:
                return None

            with self._state_lock:
                ready = self._surface_ready

            if ready:
                selected = pending_entries[0]
            else:
                selected = next(
                    (entry for entry in pending_entries if entry.get("mode") == "full_erase"),
                    None,
                )
                if selected is None:
                    return None

            selected["status"] = "processing"
            selected["started_at"] = _now_iso()
            manifest["active_job_id"] = selected["job_id"]
            _write_manifest(manifest)

            path = self._job_path_from_entry(selected)
            with self._state_lock:
                self._active_job_file = path.name
            return path, str(selected["job_id"])

    def _finish_manifest_job(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error: str | None = None,
    ) -> None:
        with self._queue_lock:
            manifest = _load_manifest()
            for entry in manifest["queue"]:
                if entry.get("job_id") != job_id:
                    continue
                entry["status"] = status
                entry["finished_at"] = _now_iso()
                if error:
                    entry["error"] = error
                elif "error" in entry:
                    entry.pop("error", None)
                break
            manifest["active_job_id"] = None
            if status == "completed":
                manifest["last_completed_job_id"] = job_id
            _write_manifest(manifest)

    def process_next_job(self) -> Dict[str, Any] | None:
        """Process one manifest job. Public primarily for deterministic tests."""
        claimed = self._claim_next_job()
        if claimed is None:
            return None
        job_path, claimed_job_id = claimed

        try:
            job = load_json(job_path)
            job["status"] = "processing"
            job["started_at"] = _now_iso()
            mode = str(job.get("mode", ""))

            target: Drawing | None = None
            target_path: Path | None = None
            previous = load_committed_state()

            if mode == "full_erase":
                actions = build_full_erase_actions()
                job["source_drawing_id"] = previous.get("drawing_id")
                job["target_drawing_id"] = "robot-empty-state"
            elif mode in ("difference", "full_redraw"):
                target_file = str(job.get("target_file") or "")
                if not target_file or Path(target_file).name != target_file:
                    raise ValueError("Queued drawing job has an invalid target_file.")
                target_path = Path(config.OUTPUT_DIR) / target_file
                if not target_path.is_file():
                    raise FileNotFoundError(f"Queued target drawing is missing: {target_path}")
                target = load_json(target_path)
                target_id = str(target.get("drawing_id") or target_path.stem)
                previous_id = str(previous.get("drawing_id") or "")
                job["source_drawing_id"] = previous_id
                job["target_drawing_id"] = target_id
                actions = (
                    build_difference_actions(previous, target)
                    if mode == "difference"
                    else build_full_redraw_actions(target)
                )
            else:
                raise ValueError(f"Unsupported queued robot mode: {mode}")

            job["actions"] = actions
            job["stats"] = _job_stats(actions)
            _atomic_json_write(job_path, job)
            preview_state.update_robot_job(
                actions=actions,
                job_file=job_path.name,
                mode=mode,
                status="Queue job processing; waiting for robot acknowledgement",
            )

            success = self._send_to_transport(job)
            if success:
                job["status"] = "completed"
                job["acknowledged_at"] = _now_iso()
                if mode == "full_erase":
                    clear_committed_state()
                    with self._state_lock:
                        self._surface_ready = True
                        if job.get("reason") == "startup":
                            self._startup_erase_status = "acknowledged"
                elif target is not None and target_path is not None:
                    committed = {
                        "committed_at": job["acknowledged_at"],
                        "source_job": job_path.name,
                        "source_output_file": target_path.name,
                        "drawing": target,
                    }
                    _atomic_json_write(Path(config.ROBOT_COMMITTED_STATE_FILE), committed)

                _atomic_json_write(job_path, job)
                self._finish_manifest_job(claimed_job_id, "completed")
                with self._state_lock:
                    self._active_job_file = ""
                    self._last_completed_job_file = job_path.name
                preview_state.update_robot_job(
                    actions=actions,
                    job_file=job_path.name,
                    mode=mode,
                    status="Queue job completed and robot state committed",
                )
                print(f"[queue] Completed: {job_path.name}")
            else:
                job["status"] = "failed"
                job["failed_at"] = _now_iso()
                if mode == "full_erase" and job.get("reason") == "startup":
                    with self._state_lock:
                        self._startup_erase_status = "failed"
                        self._surface_ready = False
                _atomic_json_write(job_path, job)
                self._finish_manifest_job(claimed_job_id, "failed")
                with self._state_lock:
                    self._active_job_file = ""
                preview_state.update_robot_job(
                    actions=actions,
                    job_file=job_path.name,
                    mode=mode,
                    status="Queue job failed; committed state unchanged",
                )
                print(f"[queue] Failed: {job_path.name}")
            return job

        except Exception as error:
            try:
                job = load_json(job_path)
            except Exception:
                job = {"job_id": claimed_job_id, "mode": "unknown"}
            job["status"] = "failed"
            job["failed_at"] = _now_iso()
            job["error"] = str(error)
            _atomic_json_write(job_path, job)
            self._finish_manifest_job(claimed_job_id, "failed", error=str(error))
            with self._state_lock:
                self._active_job_file = ""
            preview_state.update_job_status(f"Queue job failed: {error}")
            print(f"[queue] Job error ({job_path.name}): {error}")
            return job

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            processed = self.process_next_job()
            if processed is None:
                self._stop_event.wait(config.ROBOT_QUEUE_POLL_INTERVAL_SEC)

    @staticmethod
    def _send_to_transport(job: Dict[str, Any]) -> bool:
        """Physical robot/ROS integration point."""
        if config.SIMULATE_ROBOT_ACK:
            print(
                "[robot simulation] send -> "
                f"job={job.get('job_id')} mode={job.get('mode')} stats={job.get('stats', {})}"
            )
            return True
            
        import socket
        HOST = '127.0.0.1'
        PORT = 9090
        try:
            print(f"[tcp] Sending job {job.get('job_id')} to {HOST}:{PORT}...")
            with socket.create_connection((HOST, PORT), timeout=10.0) as sock:
                sock.settimeout(3600.0) # Wait up to 1 hour for robot to physically finish
                payload = json.dumps(job) + "\n"
                sock.sendall(payload.encode('utf-8'))
                
                response = sock.recv(1024).decode('utf-8').strip()
                if response == "SUCCESS":
                    print(f"[tcp] Job {job.get('job_id')} executed successfully by robot.")
                    return True
                else:
                    print(f"[tcp] Robot returned failure: {response}")
                    return False
        except Exception as e:
            print(f"[tcp] Failed to communicate with robot on {HOST}:{PORT}: {e}")
            return False


    def queue_counts(self) -> Dict[str, int]:
        with self._queue_lock:
            manifest = _load_manifest()
            counts = {status: 0 for status in _VALID_STATUSES}
            for entry in manifest["queue"]:
                status = str(entry.get("status", ""))
                if status in counts:
                    counts[status] += 1
            return counts

    def describe_state(self) -> str:
        committed = load_committed_state()
        try:
            current_path, current = current_run_detected_drawing()
            detected_text = f"{current.get('drawing_id', current_path.stem)} ({current_path.name})"
        except FileNotFoundError:
            detected_text = "none in current run"
        counts = self.queue_counts()
        with self._state_lock:
            surface_ready = self._surface_ready
            startup_status = self._startup_erase_status
            active = self._active_job_file or "none"
            completed = self._last_completed_job_file or "none"
        return (
            f"mode={self.mode} | committed={committed.get('drawing_id', 'robot-empty-state')} "
            f"| current_detected={detected_text} | surface_ready={surface_ready} "
            f"| startup_erase={startup_status} | queue={counts} "
            f"| active={active} | last_completed={completed} "
            f"| manifest={_manifest_path().name}"
        )


robot_job_manager = RobotJobManager()
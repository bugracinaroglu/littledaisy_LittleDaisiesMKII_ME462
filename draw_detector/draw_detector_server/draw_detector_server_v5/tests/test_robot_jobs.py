from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from preview_state import preview_state
from processor import convert_top_left_to_bottom_left, process_strokes
from robot_jobs import (
    build_difference_actions,
    build_full_erase_actions,
    build_full_redraw_actions,
    current_run_detected_drawing,
    reset_runtime_storage,
)


def drawing(drawing_id, strokes):
    return {
        "drawing_id": drawing_id,
        "coordinate_system": "normalized_bottom_left_origin",
        "strokes": strokes,
    }


def stroke(stroke_id, points, parent=None):
    value = {"stroke_id": stroke_id, "points": points}
    if parent:
        value["parent_stroke_id"] = parent
    return value


class CoordinateTests(unittest.TestCase):
    def test_top_left_to_bottom_left(self):
        converted = convert_top_left_to_bottom_left([
            stroke("a", [[0.25, 0.20], [0.75, 0.90]])
        ])
        self.assertEqual(converted[0]["points"], [[0.25, 0.8], [0.75, 0.1]])

    def test_raw_processing_preserves_id_and_points(self):
        source = [stroke("a", [[0.1, 0.2], [0.3, 0.4]])]
        self.assertEqual(process_strokes(source), source)


class DifferenceTests(unittest.TestCase):
    def test_new_stroke_draw(self):
        actions = build_difference_actions(
            drawing("old", []),
            drawing("new", [stroke("a", [[0.1, 0.1], [0.2, 0.2]])]),
        )
        self.assertEqual([item["type"] for item in actions], ["draw"])

    def test_removed_stroke_erases(self):
        actions = build_difference_actions(
            drawing("old", [stroke("a", [[0.1, 0.1], [0.2, 0.2]])]),
            drawing("new", []),
        )
        self.assertEqual([item["type"] for item in actions], ["erase"])

    def test_untouched_stroke_same(self):
        points = [[0.1, 0.1], [0.2, 0.2]]
        actions = build_difference_actions(
            drawing("old", [stroke("a", points)]),
            drawing("new", [stroke("a", points)]),
        )
        self.assertEqual([item["type"] for item in actions], ["same"])

    def test_pixel_erase_replaces_old_stroke_with_segments(self):
        old = drawing("old", [stroke("a", [[0.1, 0.5], [0.5, 0.5], [0.9, 0.5]])])
        new = drawing("new", [
            stroke("b", [[0.1, 0.5], [0.3, 0.5]], parent="a"),
            stroke("c", [[0.7, 0.5], [0.9, 0.5]], parent="a"),
        ])
        actions = build_difference_actions(old, new)
        self.assertEqual([item["type"] for item in actions], ["erase", "draw", "draw"])
        self.assertEqual(actions[0]["stroke_id"], "a")
        self.assertEqual(
            {actions[1]["parent_stroke_id"], actions[2]["parent_stroke_id"]},
            {"a"},
        )

    def test_full_redraw(self):
        actions = build_full_redraw_actions(
            drawing("new", [stroke("a", [[0.1, 0.1], [0.2, 0.2]])])
        )
        self.assertEqual([item["type"] for item in actions], ["erase_all", "draw"])

    def test_full_erase_contains_no_path(self):
        self.assertEqual(build_full_erase_actions(), [{"type": "erase_all"}])


class StartupStateTests(unittest.TestCase):
    def tearDown(self):
        preview_state.reset_runtime()

    def test_startup_reset_preserves_output_and_clears_runtime_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_dir = root / "output"
            comparison_dir = root / "comparison_state"
            jobs_dir = root / "robot_jobs"
            output_dir.mkdir()
            comparison_dir.mkdir()
            jobs_dir.mkdir()

            output_file = output_dir / "drawing_old.json"
            output_file.write_text("{}", encoding="utf-8")
            (comparison_dir / "robot_committed_state.json").write_text("{}", encoding="utf-8")
            (jobs_dir / "job_old.json").write_text("{}", encoding="utf-8")
            (jobs_dir / "latest_job.json").write_text("{}", encoding="utf-8")
            (jobs_dir / ".gitkeep").write_text("", encoding="utf-8")

            with (
                patch.object(config, "OUTPUT_DIR", str(output_dir)),
                patch.object(config, "STARTUP_OUTPUT_ERASE_ENABLED", False),
                patch.object(config, "COMPARISON_STATE_DIR", str(comparison_dir)),
                patch.object(config, "ROBOT_JOBS_DIR", str(jobs_dir)),
                patch.object(config, "RESET_COMPARISON_STATE_ON_START", True),
                patch.object(config, "RESET_ROBOT_JOBS_ON_START", True),
            ):
                result = reset_runtime_storage()

            self.assertTrue(output_file.exists())
            self.assertEqual(list(comparison_dir.glob("*.json")), [])
            self.assertEqual(list(jobs_dir.glob("*.json")), [])
            self.assertTrue((jobs_dir / ".gitkeep").exists())
            self.assertEqual(result["output_files_removed"], 0)
            self.assertEqual(result["comparison_files_removed"], 1)
            self.assertEqual(result["robot_job_files_removed"], 2)

    def test_startup_output_erase_deletes_only_output_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output_dir = root / "output"
            comparison_dir = root / "comparison_state"
            jobs_dir = root / "robot_jobs"
            output_dir.mkdir()
            comparison_dir.mkdir()
            jobs_dir.mkdir()

            (output_dir / "drawing_1.json").write_text("{}", encoding="utf-8")
            (output_dir / "drawing_2.json").write_text("{}", encoding="utf-8")
            keep_file = output_dir / ".gitkeep"
            keep_file.write_text("", encoding="utf-8")
            non_json = output_dir / "preview.png"
            non_json.write_bytes(b"png")

            with (
                patch.object(config, "OUTPUT_DIR", str(output_dir)),
                patch.object(config, "STARTUP_OUTPUT_ERASE_ENABLED", True),
                patch.object(config, "COMPARISON_STATE_DIR", str(comparison_dir)),
                patch.object(config, "ROBOT_JOBS_DIR", str(jobs_dir)),
                patch.object(config, "RESET_COMPARISON_STATE_ON_START", False),
                patch.object(config, "RESET_ROBOT_JOBS_ON_START", False),
            ):
                result = reset_runtime_storage()

            self.assertEqual(list(output_dir.glob("*.json")), [])
            self.assertTrue(keep_file.exists())
            self.assertTrue(non_json.exists())
            self.assertEqual(result["output_files_removed"], 2)
            self.assertEqual(result["comparison_files_removed"], 0)
            self.assertEqual(result["robot_job_files_removed"], 0)

    def test_old_output_is_not_active_before_current_run_detect(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            old_file = output_dir / "drawing_old.json"
            old_file.write_text(json.dumps(drawing("old", [])), encoding="utf-8")
            preview_state.reset_runtime()

            with patch.object(config, "OUTPUT_DIR", str(output_dir)):
                with self.assertRaises(FileNotFoundError):
                    current_run_detected_drawing()

    def test_current_run_detect_filename_selects_active_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            active = output_dir / "drawing_new.json"
            active.write_text(json.dumps(drawing("new", [])), encoding="utf-8")
            preview_state.reset_runtime()
            preview_state.update_detected([], "drawing_new.json")

            with patch.object(config, "OUTPUT_DIR", str(output_dir)):
                path, payload = current_run_detected_drawing()

            self.assertEqual(path, active)
            self.assertEqual(payload["drawing_id"], "new")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from processor import convert_top_left_to_bottom_left, process_strokes
from robot_jobs import build_difference_actions, build_full_redraw_actions


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
        self.assertEqual({actions[1]["parent_stroke_id"], actions[2]["parent_stroke_id"]}, {"a"})

    def test_full_redraw(self):
        actions = build_full_redraw_actions(
            drawing("new", [stroke("a", [[0.1, 0.1], [0.2, 0.2]])])
        )
        self.assertEqual([item["type"] for item in actions], ["erase_all", "draw"])


if __name__ == "__main__":
    unittest.main()

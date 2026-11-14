"""A hostile milestone state or tile outline (a list or dict where a word belongs) must not break publish. Fictional data only.

Run: python3 dev/run_tests.py test_hostile_milestone_state_outline
"""
import unittest

import _publish_fixture as fx
from clark import glance, milestones, publish

HOSTILE = ([], ["Late"], {}, {"a": 1}, 5, None)


class HostileState(unittest.TestCase):
    def test_client_word_of_a_non_word_is_empty(self):
        for v in HOSTILE:
            with self.subTest(v=v):
                self.assertEqual(milestones.client_word(v), "")
        self.assertEqual(milestones.client_word("Slipped"), "Expected later")

    def test_milestone_state_ignores_a_non_word_state(self):
        for v in HOSTILE:
            with self.subTest(v=v):
                row = {"status": "Planned", "state_set": 1, "state": v, "baseline_date": "2026-10-15", "forecast_date": "2026-10-15"}
                self.assertIn(milestones.milestone_state(row, "2026-10-01"), milestones.MS_RANK)

    def test_publish_survives_a_hostile_milestone_state(self):
        for v in HOSTILE:
            with self.subTest(v=v):
                plant = fx.load()
                plant["data"]["milestones"][0]["state"] = v
                out = publish.select(fx.inputs(plant))
                self.assertTrue(out["data"]["milestones"])

    def test_tiles_survive_a_hostile_outline(self):
        for v in ([], ["R"], {}, {"R": 1}):
            with self.subTest(v=v):
                got = glance.tiles({}, "2026-10-28", outlines={"overdue": v})
                self.assertTrue(got)


if __name__ == "__main__":
    unittest.main()

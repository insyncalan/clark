"""#136: the planted Movement histories (tests/fixtures/movement_events.py) hold what the Movement tests rely on.

Run: python3 dev/run_tests.py test_movement_fixtures
"""
import importlib.util
import unittest
from pathlib import Path

import _paths  # noqa: F401

_spec = importlib.util.spec_from_file_location("movement_events", Path(__file__).resolve().parent / "fixtures" / "movement_events.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)


class Fixtures(unittest.TestCase):
    def test_every_case_the_design_asks_for_is_planted(self):
        evs, rows = fx.events(), {r["id"]: r for r in fx.rows()}
        rebased = evs[fx.M_REBASED]
        note = [e["after"] for e in rebased if e["field"] == "note"][0]
        self.assertIn("ABC-D-004", note)
        self.assertIn("ABC-D-011", note)                                         # two decisions cited, the last is the store's
        fc = [e for e in evs[fx.M_FORECAST_BACK] if e["field"] == "forecast_date"]
        self.assertEqual((fc[0]["before"], fc[0]["after"], fc[1]["after"]), ("2026-11-10", "2026-11-17", "2026-11-10"))
        self.assertTrue(any(not e["in_force"] for e in evs[fx.M_UNDONE]))
        self.assertTrue(any(e["is_undo"] for e in evs[fx.M_UNDONE]))
        self.assertEqual(evs[fx.M_QUIET], [])
        self.assertEqual(len(evs[fx.M_MANY]), 120)
        self.assertEqual(rows[fx.M_ARCHIVED]["archived"], 1)
        self.assertTrue(any(e["field"] == "internal_note" and fx.INTERNAL_MARKER in e["after"] for e in rebased))
        self.assertEqual(rows[fx.M_REBASED]["internal_note"], fx.INTERNAL_MARKER)

    def test_event_ids_are_unique_and_rise(self):
        ids = [e["event_id"] for items in fx.events().values() for e in items]
        self.assertEqual(ids, sorted(set(ids)))

    def test_the_reply_has_the_read_shape(self):
        reply = fx.reply()
        self.assertEqual(set(reply), {"project", "milestones", "truncated"})
        self.assertNotIn(fx.M_ARCHIVED, reply["milestones"])                     # an archived milestone is never read
        self.assertEqual(reply["milestones"][fx.M_MANY]["total"], 120)
        self.assertEqual(len(reply["milestones"][fx.M_MANY]["events"]), 50)
        self.assertEqual(reply["milestones"][fx.M_REBASED]["original"], "2026-11-03")
        self.assertIsNone(reply["milestones"][fx.M_QUIET]["original"])
        for block in reply["milestones"].values():
            self.assertEqual(set(block), {"original", "total", "events"})
            ids = [e["event_id"] for e in block["events"]]
            self.assertEqual(ids, sorted(ids, reverse=True))                     # newest first, as the read gives them

    def test_markers_are_distinct_and_made_up(self):
        self.assertEqual(len(set(fx.MARKERS)), len(fx.MARKERS))
        self.assertTrue(all(m.startswith("PLANTED-") for m in fx.MARKERS))


if __name__ == "__main__":
    unittest.main()

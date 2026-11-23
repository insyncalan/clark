"""Row 1508: the project's own data may take up to half of the 300,000-token ask clark request.

Run: python3 dev/run_tests.py test_ask_project_share_300k_td
Logic only (1400 and 900 give the same result). Fictional data only (the publish plant).
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
import test_ask_route as route
from clark import ask, ask_data, ask_service, publish


def read(rows, size, budget, limit=None):
    """project_data over `rows` extra actions of about `size` characters each, with `budget` characters allowed."""
    given = plant.inputs()
    given["as_at"] = "2026-11-17"
    given["data"]["actions"] = list(given["data"]["actions"]) + [
        {"id": f"PUB-A-{900 + i}", "project": "PUB", "archived": 0, "description": f"ZQ-ROW-{i} " + "fiction " * (size // 8), "owner": "Site manager",
         "status": "Open", "due_date": "2026-12-01"} for i in range(rows)]
    with mock.patch.object(publish, "read_inputs", return_value=given):
        return ask_data.project_data(object(), "PUB", "what is there?", budget, as_at="2026-11-17", limit=limit)


def size_of(got):
    return sum(len(p.text) for p in got.passages)


class ShareOfTheRequest(unittest.TestCase):
    def test_project_share_is_half_the_budget(self):
        self.assertEqual(ask_service.PROJECT_SHARE, ask.BUDGET // 2)
        self.assertEqual(ask_service.PROJECT_SHARE, 600000)

    def test_the_whole_request_stays_300000_tokens(self):
        self.assertEqual(ask.BUDGET, 1200000)
        self.assertEqual(ask.MAX_REQUEST, 1230000)
        self.assertEqual(ask.BUDGET // 4, 300000)

    def test_a_project_of_100000_characters_is_sent_whole(self):
        got = read(30, 3500, ask_service.PROJECT_SHARE)
        self.assertGreater(size_of(got), 100000)
        self.assertEqual((got.left_out, got.counts and sum(s == t for _k, s, t in got.counts) == len(got.counts)), (0, True))
        self.assertIn("ZQ-ROW-29", "\n".join(p.text for p in got.passages))
        self.assertEqual(ask_data.partial_lines(got.counts), [])

    def test_a_project_of_100000_characters_reaches_the_data_read_through_the_route(self):
        class Through(route.Base):
            def runTest(self):
                pass
        case = Through()
        case.setUp()
        try:
            with mock.patch.object(ask_data, "project_data", wraps=ask_data.project_data) as spy:
                status, got = case.question("what is late?")
            self.assertEqual(status, 200, got)
            self.assertEqual(spy.call_args[0][3], min(600000, ask.BUDGET))
        finally:
            case.tearDown()

    def test_over_the_share_is_cut_and_the_note_is_true(self):
        got = read(250, 3500, ask_service.PROJECT_SHARE, limit=10000)     # about 900000 characters of rows
        self.assertLessEqual(size_of(got), 600000)
        self.assertGreater(size_of(got), 590000)
        self.assertGreater(got.left_out, 0)
        lines = ask_data.partial_lines(got.counts)
        actions = [c for c in got.counts if c[0] == "actions"][0]
        self.assertLess(actions[1], actions[2])
        self.assertEqual(len([ln for ln in lines if "actions" in ln]), 1)
        self.assertIn(f"actions: {actions[1]} of {actions[2]} rows sent", lines)
        self.assertTrue(ask_data.left_out_lines([("actions", actions[1], actions[2])])[0].startswith(f"Sent {actions[1]} of {actions[2]} actions"))


if __name__ == "__main__":
    unittest.main()

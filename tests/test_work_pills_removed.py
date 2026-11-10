"""Row 1059: the type pills (All, Actions, Risks and issues, Decisions) and the status pills (Open, Closed, All) are gone from the
Work items page in the app. Type and status stay reachable through the filter line (type:, status:, is:open, is:closed).

Run: python3 dev/run_tests.py test_work_pills_removed
"""
import unittest

from _paths import ROOT, SRC  # noqa: F401
import test_filter_line_page as _base  # noqa: E402
from test_filter_line_page import wait  # noqa: E402
from test_work_filters import expect, set_line  # noqa: E402
from test_server import chrome  # noqa: E402


class PillsRemoved(_base.Line):
    def test_no_type_or_status_pills_are_drawn(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-type][aria-pressed], [data-show]').length", sid), 0)
            self.assertEqual(cdp.js("document.querySelectorAll('.wbar [aria-label=Type], .wbar [aria-label=\"Open or closed\"]').length", sid), 0)
            self.assertEqual(cdp.js("document.querySelectorAll('#fline-input').length", sid), 1)

    def test_type_and_status_are_still_reachable_through_the_line(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            rows = self.rows(cdp, sid)
            set_line(cdp, sid, "type:action is:closed")
            want = expect(rows, "closed", "action")
            self.assertTrue(wait(lambda: self.shown(cdp, sid) == want), f"{self.shown(cdp, sid)} != {want}")


if __name__ == "__main__":
    unittest.main()

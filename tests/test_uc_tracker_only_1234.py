"""Row 1234 (c): a click on the Status tracker position writes only the tracker, so the list the Edit page draws is the list the published
file draws, and the section still counts as "no number chosen". At 1400 and 900 px.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_tracker_only_1234
"""
import json
import unittest

from _publish import PublishedFile
from test_glance_page import Setup, USER, tearDownModule  # noqa: F401
from test_server import chrome, wait

from _uc_view import put_view

ROWS = "[...document.querySelectorAll('.ucrows > .ucrow .uctitle')].map(e => e.textContent)"


class TrackerOnly(PublishedFile, Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            for n in range(3, 9):
                st.create("use_cases", {"project": "ABC", "title": f"Case {n}", "status": "On track", "ref": f"1.{n}", "headline": "", "commitment": "", "source": "demo"})

    def stored(self):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
        return json.loads(row["body"]) if row["body"] else None

    def click_tracker(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('#ucAdd')", "Edit")
        p.js("document.querySelector('[data-uc-configure]').click()")
        p.until("!!document.querySelector('[data-uc-tracker]')", "tracker control")
        p.js("document.querySelector('[data-tracker=bottom]').click()")
        self.assertTrue(wait(self.stored), "the tracker choice was not saved")

    def test_a_tracker_click_writes_the_tracker_alone_and_edit_rows_equal_published_rows(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, None)
                p = self.show(cdp, width)
                before = p.js(ROWS)
                self.assertEqual(len(before), 5, "the default count shows five of the eight")
                self.click_tracker(p)
                self.assertEqual(self.stored(), {"tracker": "bottom"}, "no number and no scroll written")
                p.reload()
                p.until("!!document.querySelector('.uc')", "the summary drew again")
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('#ucAdd')", "Edit")
                edit_rows = p.js(ROWS)
                path = self.publish()
                q = self.draw(cdp, path, width)
                q.until("!!document.querySelector('.uc')", "the file drew the summary")
                self.assertEqual(edit_rows, q.js(ROWS), "Edit rows are the published rows")
                self.assertEqual(edit_rows, before, "and the tracker click changed no row")


if __name__ == "__main__":
    unittest.main()

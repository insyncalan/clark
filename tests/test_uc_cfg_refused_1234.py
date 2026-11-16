"""Row 1234: a refused save in the Configure panel must not become the base of a save made while it was in flight, at 1400 and 900 px.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_cfg_refused_1234
"""
import json
import unittest

from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

from _uc_view import put_view

CFG = "document.querySelector('[data-uc-configure]')"
START = {"n": 2, "scroll": False, "tracker": "top"}
# The number goes to 1 and, in the same turn of the page, the tracker goes Off: two saves, the first one refused (or rejected).
BOTH = ("(() => { const s = document.querySelector('#ucCfgN'); s.value = '1'; s.dispatchEvent(new Event('change', {bubbles: true}));"
        " document.querySelector('[data-tracker=off]').click(); })()")


class Refused(Setup):
    def stored(self):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
        return json.loads(row["body"]) if row["body"] else None

    def open_panel(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('#ucAdd')", "Edit")
        p.js(f"{CFG}.click()")
        p.until("!!document.querySelector('[data-uc-tracker]')", "tracker control")

    def first_only(self, answer):
        """Make the first request the page sends come back as `answer`; every later one is the real one."""
        def failure(req):
            self.failure = None
            return answer
        self.failure = failure

    def stored_tracker(self, p, want):
        """The page's own signal that the second save landed: the stored body holds `want` (the saves are queued, so the first has settled by then)."""
        p.until(f"[...document.querySelectorAll('[data-uc-tracker] button')].some(b => b.dataset.tracker === '{want}' && b.getAttribute('aria-pressed') === 'true')", f"{want} drawn")
        return self.stored()

    def test_a_refused_first_save_is_not_in_the_second(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, START)
                p = self.show(cdp, width)
                self.open_panel(p)
                self.first_only((400, {"ok": False, "message": "no", "code": "refused"}))
                p.js(BOTH)
                self.assertEqual(self.stored_tracker(p, "off"), {"n": 2, "scroll": False, "tracker": "off"}, "the refused number 1 was not written by the second save")

    def test_a_rejected_first_save_does_not_block_the_next(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, START)
                p = self.show(cdp, width)
                self.open_panel(p)
                self.first_only((200, {"ok": True, "sections": [None]}))       # the page cannot read this reply: its promise rejects
                p.js(BOTH)
                self.assertEqual(self.stored_tracker(p, "off"), {"n": 2, "scroll": False, "tracker": "off"}, "the second save still ran, without the first value")
                p.js("document.querySelector('[data-tracker=bottom]').click()")
                self.assertEqual(self.stored_tracker(p, "bottom"), {"n": 2, "scroll": False, "tracker": "bottom"}, "a third change is built on what is stored")


if __name__ == "__main__":
    unittest.main()

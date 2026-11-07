"""Row 823: the Milestones page has no View | Edit mode. In View the page has Add milestone and the eye on each row (and Movement's
choices, see test_movement_in_view); the Dashboard's Milestones section keeps its mode test, so in View it has neither.

Run: CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_milestones_inline
At 1400 and 900 px, light and dark (headless Chrome, required).
"""
import json
import unittest

from test_movement_page import Base
from test_server import chrome

PAGE_EYE = ".msv[data-place=page] .msl-row button[data-ms-eye]"
DASH_EYE = ".msv:not([data-place=page]) .msl-row button[data-ms-eye]"


class Inline(Base):
    def go(self, p, hash_):
        p.js(f"location.hash = {json.dumps(hash_)}")

    def test_view_page_has_add_milestone_and_the_eye_at_1400_and_900_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit(cdp, width=width, theme=theme)
                    p.until("!!document.querySelector('.msv .msl-row')", "the list drew")
                    self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch off the Dashboard: the page is always editable")
                    p.until("!!document.querySelector('#addMs')", "View has Add milestone")
                    self.assertGreater(p.js("document.querySelectorAll('%s').length" % PAGE_EYE), 0, "View has the eye on the page")
                    self.assertEqual(p.js("document.querySelector('%s').disabled" % PAGE_EYE), False)

    def test_view_eye_on_the_page_leaves_a_milestone_out(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('%s')" % PAGE_EYE, "the eye is there in View")
            ident = p.js("document.querySelector('%s').closest('.msl-row').dataset.ms" % PAGE_EYE)
            p.js("document.querySelector('.msl-row[data-ms=\"%s\"] button[data-ms-eye]').click()" % ident)
            p.until("!!document.querySelector('.toast')", "a toast")
            self.assertIn(ident, self.store.data_for("ABC")["report_hidden"])

    def test_view_add_milestone_adds_one(self):
        before = {r["id"] for r in self.store.read("milestones")}
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#addMs')", "View has Add milestone")
            p.js("document.querySelector('#addMs').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Milestone added. Undo.'", "the toast")
        self.assertEqual(len({r["id"] for r in self.store.read("milestones")} - before), 1)

    def test_view_dashboard_section_still_has_neither(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit(cdp, width=width, theme=theme)
                    self.go(p, "#dashboard&p=ABC")
                    p.until("!!document.querySelector('.msv[data-place^=sec-] .msl-row')", "the Dashboard's Milestones drew")
                    self.assertEqual(p.js("document.querySelector('[data-mode=view]').getAttribute('aria-pressed')"), "true")
                    self.assertEqual(p.js("document.querySelectorAll('[data-ms-eye], #addMs, [data-ms-back]').length"), 0, "View on the Dashboard has none")
                    p.js("document.querySelector('[data-mode=edit]').click()")
                    p.until("!!document.querySelector('%s')" % DASH_EYE, "Edit gives the Dashboard its eye")


if __name__ == "__main__":
    unittest.main()

"""Row 1234: pins for the Configure panel that the first test file left open (each fails on one change to the source), at 1400 and 900 px.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_configure_survivors_1234
"""
import json

from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

from _uc_view import put_view

CLICK_CONFIGURE = "document.querySelector('[data-uc-configure]').click()"


def choose(value):
    return ("(s => { s.value = %s; s.dispatchEvent(new Event('change', {bubbles: true})); })(document.querySelector('#ucCfgN'))" % json.dumps(value))


class ConfigureSurvivors(Setup):
    def open_panel(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('[data-uc-configure]')", "Edit")
        p.js(CLICK_CONFIGURE)
        p.until("!!document.querySelector('#ucCfgN')", "panel")

    def stored(self):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
        return json.loads(row["body"])

    def test_a_number_change_keeps_the_tracker_and_the_scroll_as_stored(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, {"n": 3, "scroll": False, "tracker": "off"})
                p = self.show(cdp, width)
                self.open_panel(p)
                p.js(choose("1"))
                # The help line is drawn from the saved view, so it changes only after the server has the body.
                p.until("document.querySelector('[data-uc-cfg-help]').textContent.includes('the list is 1 rows tall')", "saved and drawn")
                self.assertEqual(self.stored(), {"n": 1, "scroll": False, "tracker": "off"})

    def test_a_switched_off_use_case_is_not_counted_in_of_n(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, {"n": 1, "scroll": False, "tracker": "top"})
                self.store.con.execute("UPDATE use_cases SET client_visible = 0 WHERE id = ?", (self.uc2,))
                self.store.con.commit()
                p = self.show(cdp, width)
                self.open_panel(p)
                self.assertEqual(p.js("document.querySelector('[data-uc-of]').textContent"), "of 1")
                self.assertEqual(p.js("[...document.querySelectorAll('#ucCfgN option')].map(o => o.value)"), ["1", "all"])

    def test_a_saved_change_says_saved(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, None)
                p = self.show(cdp, width)
                self.open_panel(p)
                p.js(choose("1"))
                p.until("/^Saved\\.$/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the toast says Saved.")

    def test_the_button_and_the_panel_are_edit_only(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.open_panel(p)
                self.assertTrue(p.js("document.querySelector('[data-uc-configure]').hasAttribute('data-edit-only')"))
                self.assertTrue(p.js("!!document.querySelector('#ucCfg').closest('[data-edit-only]')"))

    def test_the_done_button_closes_the_panel_and_gives_focus_back(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('[data-uc-configure]')", "Edit")
                p.js("document.querySelector('[data-uc-configure]').focus(); " + CLICK_CONFIGURE)
                p.until("!!document.querySelector('#ucCfg')", "panel")
                p.js("document.querySelector('#ucCfg [data-cancel]').click()")
                p.until("!document.querySelector('#ucCfg')", "closed")
                self.assertTrue(p.js("document.activeElement === document.querySelector('[data-uc-configure]')"))


if __name__ == "__main__":
    import unittest
    unittest.main()

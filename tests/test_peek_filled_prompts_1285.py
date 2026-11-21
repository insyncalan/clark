"""Row 1285, author mutation sweep: (1) in Classic Edit a decision that already has a Revisit and a Replaces shows those words, not the "Add ..." prompts; (2) the client line's switch (.pk-sw) is drawn in Classic and not in Cards, on an item peek and on a milestone peek.
Run: python3 dev/run_tests.py test_peek_filled_prompts_1285
"""
import unittest
from unittest import mock

import _testpage
from clark import page, theme as themes

import test_peek_latest
import test_server  # noqa: F401  (a test that drives Chrome carries this import)
from test_server import chrome, wait
import test_milestone_peek_1078 as _m

_B = test_peek_latest.Browser
del test_peek_latest
JS = "[...document.querySelectorAll('#peek [data-ms-row=revisit] dd, #peek [data-ms-row=replaces] dd')].map(e => e.textContent.trim())"


class FilledPrompts(unittest.TestCase):
    load, refused = _B.load, _B.refused
    _base_setup = _B.setUp
    _base_fresh = _B.fresh

    def fresh(self):          # load() makes a fresh demo database, so the two values are written there
        self._base_fresh()
        with self.store.step("dashboard", "Demo User") as st:
            st.update("decisions", "TUL-D-016", {"revisit": "2027-03-01", "replaces": "TUL-D-015"})

    def setUp(self):
        self._base_setup()
        real = _testpage.html
        p = mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0")))
        p.start()
        self.addCleanup(p.stop)

    def test_a_filled_revisit_and_replaces_show_their_words_and_no_prompt(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-D-016", edit=True)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ms-row=revisit]')", sid)))
                got = cdp.js(JS, sid)
                self.assertEqual(len(got), 2, got)
                self.assertNotIn("—", got, "both have a value")
                self.assertFalse(any(w.startswith("Add ") for w in got), got)
                self.assertIn("TUL-D-015", got[1])
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-prompt]').length", sid), 0)


SW = "(() => { const b = document.querySelector('#peek [data-pk-client]'); return b ? b.querySelectorAll('.pk-sw').length : -1; })()"
OPEN = "(() => { const h = document.querySelector('#peek [data-pk-details]'); if (h && h.getAttribute('aria-expanded') === 'false') h.click(); })()"


class SwitchItem(unittest.TestCase):
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    _base_setup = _B.setUp
    classic_on = True

    def setUp(self):
        self._base_setup()
        if self.classic_on:
            real = _testpage.html
            p = mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0")))
            p.start()
            self.addCleanup(p.stop)

    def test_the_item_client_line_has_the_switch_in_classic_only(self):
        for width in (1400, 900):
            with self.subTest(width=width, classic=self.classic_on), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-A-002", edit=True)
                cdp.js(OPEN, sid)
                self.assertTrue(wait(lambda: cdp.js(SW, sid) >= 0))
                self.assertEqual(cdp.js(SW, sid), 1 if self.classic_on else 0)


class SwitchItemCards(SwitchItem):
    classic_on = False


class SwitchMilestone(_m.Base):
    cur = _m.GO_LIVE
    visit_peek = _m.Fields.visit_peek
    theme = "prototype-2.0"

    def setUp(self):
        real = page.page_html
        if self.theme:
            p = mock.patch.object(page, "page_html", lambda *a, **k: real(*a, **({"theme": self.theme} if not k.get("view") else {}), **k))
            p.start()
            self.addCleanup(p.stop)
        super().setUp()

    def test_the_milestone_client_line_has_the_switch_in_classic_only(self):
        for width in (1400, 900):
            with self.subTest(width=width, theme=self.theme), chrome() as cdp:
                p = self.visit_peek(cdp, width=width, view="milestones")
                p.js(OPEN)
                p.until("document.querySelector('#peek [data-pk-client]') !== null", "the client line is drawn")
                self.assertEqual(p.js(SW), 1 if self.theme else 0)


class SwitchMilestoneCards(SwitchMilestone):
    theme = None


del _m, _B


if __name__ == "__main__":
    unittest.main()

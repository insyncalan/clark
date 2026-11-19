"""Row 1285 (v1.3), the parts that need no new words: the peek's focus on open, the milestone header tiles and the decision chips' small words, measured at 1400 and 900.
Run: python3 dev/run_tests.py test_peek_gaps_1285

1. Opening a peek with the mouse (no key pressed) draws no focus ring on its first toolbar button (the focus stays inside the dialog; the ring is for keys).
2. The milestone header line's owner and progress are never cut: no ellipsis and the text fits its own box (scrollWidth not above clientWidth).
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
ITEMS = (("TUL-A-002", "action"), ("TUL-007", "risk"), ("TUL-010", "issue"))
RING = ("(() => { const a = document.activeElement; if (!a || !a.closest('#peek')) return {inside: false};"
        " const c = getComputedStyle(a); return {inside: true, tag: a.tagName, cls: a.className, vis: a.matches(':focus-visible'),"
        " outline: c.outlineStyle, w: c.outlineWidth, shadow: c.boxShadow}; })()")


def classic():
    """The test page with the Classic theme layered on, as the served page draws it (Classic only: Cards is unmaintained)."""
    real = _testpage.html
    return mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0")))


class Focus(unittest.TestCase):
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    _base_setup = _B.setUp

    def setUp(self):
        self._base_setup()
        p = classic()
        p.start()
        self.addCleanup(p.stop)

    def test_opening_a_peek_by_the_mouse_shows_no_ring_on_the_first_toolbar_button(self):
        for width in (1400, 900):
            for ref, kind in ITEMS:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    got = cdp.js(RING, sid)
                    if got["inside"]:       # the focus may sit in the dialog; then no ring on it
                        ringed = got["vis"] and got["outline"] != "none" and got["w"] != "0px"
                        self.assertFalse(ringed, f"a ring on open: {got}")
                        self.assertNotIn("rgb(", got["shadow"] if got["vis"] else "", f"a ring on open: {got}")
                    first = cdp.js("(() => { const b = document.querySelector('#peek .pk-tb button, #peek .pk-tb [role=button]'); if (!b) return null;"
                                   " const c = getComputedStyle(b); return {vis: b.matches(':focus-visible'), outline: c.outlineStyle, w: c.outlineWidth, shadow: c.boxShadow}; })()", sid)
                    self.assertIsNotNone(first, "the toolbar has a first button")
                    self.assertEqual(first["outline"], "none", f"the first toolbar button draws no ring on a mouse open: {first}")
                    self.assertEqual(first["shadow"], "none", f"no ring drawn as a shadow either: {first}")


class DecisionChips(unittest.TestCase):
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    setUp = _B.setUp

    def test_a_decision_peek_names_its_owner_and_date_chips_under_their_values(self):
        """The approved mock-up's decision chips say "made by" under the owner and "needed by" under the date of a Pending decision (TUL-D-016); an action's chips keep no such word."""
        for width in (1400, 900):
            for ref, owner, date in (("TUL-D-016", "made by", "needed by"), ("TUL-A-002", "", "overdue 6 days")):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    got = cdp.js("(() => { const g = (r) => { const s = document.querySelector('#peek .pk-chips > [data-row=' + r + '] .pk-chip-sub'); return s ? s.textContent.trim() : ''; };"
                                 " return {owner: g('owner'), due: g('due')}; })()", sid)
                    self.assertEqual(got, {"owner": owner, "due": date})


_Fields = _m.Fields


class Milestone(_Fields):

    def test_owner_and_progress_in_the_header_line_are_not_cut(self):
        for width, VIEW in ((1400, "dashboard"), (900, "dashboard"), (1400, "milestones"), (900, "milestones")):
            with self.subTest(width=width, view=VIEW), chrome() as cdp:
                p = self.visit_peek(cdp, width=width, view=VIEW)
                got = p.js("[...document.querySelectorAll('#peek [data-ms-head] [data-ms-head=owner], #peek [data-ms-head] [data-ms-head=progress], #peek .pk-chips > [data-row]')].map(e => { const c = getComputedStyle(e);"
                           " return {k: e.dataset.msHead || e.dataset.row, cut: e.scrollWidth > e.clientWidth + 1, ell: c.textOverflow, ov: c.overflowX}; })")
                self.assertTrue(got, "the header line draws an owner or a progress")
                for g in got:
                    self.assertFalse(g["cut"], f"cut text: {g}")
                    self.assertNotEqual(g["ell"], "ellipsis", f"an ellipsis: {g}")


for _n in [n for n in dir(_Fields) if n.startswith('test')]:
    setattr(Milestone, _n, None)      # only this file's own test runs, not the base class's


del _m, _B, _Fields


if __name__ == "__main__":
    unittest.main()

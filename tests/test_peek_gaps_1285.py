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
    _base_setup = _B.setUp

    def setUp(self):
        self._base_setup()
        p = classic()
        p.start()
        self.addCleanup(p.stop)

    def test_a_decision_peek_names_its_owner_and_date_chips_under_their_values(self):
        """The approved mock-up's decision chips say "made by" under the owner and "needed by" under the date of a Pending decision (TUL-D-016); an action's chips keep no such word."""
        for width in (1400, 900):
            for ref, owner, date in (("TUL-D-016", "made by", "needed by"), ("TUL-A-002", "", "overdue 6 days")):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    got = cdp.js("(() => { const g = (r) => { const s = document.querySelector('#peek .pk-chips > [data-row=' + r + '] .pk-chip-sub'); return s ? s.textContent.trim() : ''; };"
                                 " return {owner: g('owner'), due: g('due')}; })()", sid)
                    self.assertEqual(got, {"owner": owner, "due": date})

    def test_an_overdue_actions_status_chip_says_open_with_needed_by_passed_under_it(self):
        """Row 1285 AP16: the overdue action's Status chip keeps Open and gains the sub "needed by passed" in the "needed by" word style; an action not overdue has none."""
        for width in (1400, 900):
            for ref, sub in (("TUL-A-002", "needed by passed"), ("TUL-A-001", "")):
                with self.subTest(width=width, ref=ref), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    got = cdp.js("(() => { const c = document.querySelector('#peek .pk-chips > [data-row=status]'), s = c.querySelector('.pk-chip-sub');"
                                 " return {value: c.querySelector('.pkc-v').textContent.trim(), sub: s ? s.textContent.trim() : '', word: !!(s && s.classList.contains('word'))}; })()", sid)
                    self.assertEqual(got["sub"], sub, got)
                    if sub:
                        self.assertEqual(got["value"], "Open")
                        self.assertTrue(got["word"], got)


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


class Warnbar(unittest.TestCase):
    """Row 1285 ruling: the overdue bar keeps its two move buttons but is a quiet 13px muted note with text links, no amber border or tint (Classic only)."""
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    _base_setup = _B.setUp

    def setUp(self):
        self._base_setup()
        p = classic()
        p.start()
        self.addCleanup(p.stop)

    def test_the_overdue_bar_is_a_quiet_note_with_text_links(self):
        self.note("TUL-A-002", "overdue")

    def test_the_weekend_line_is_the_same_quiet_note_with_text_links(self):
        """Row 1285 AP4: the weekend line (TUL-A-006, due on a Saturday) is drawn as the .sub note too: 13px muted, no fill, no border, two text-link moves."""
        self.note("TUL-A-006", "weekend")

    def note(self, ref, kind):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True, dark=dark)
                    self.assertEqual(cdp.js("document.querySelector('#peek .pk-warnbar').dataset.pkWarn", sid), kind)
                    got = cdp.js("(() => { const b = document.querySelector('#peek .pk-warnbar'), w = b.querySelector('.pk-warn'), m = [...b.querySelectorAll('[data-pk-move]')], g = (e, p) => getComputedStyle(e)[p];"
                                 " const tok = (v) => { const i = document.createElement('i'); i.style.color = v; document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; };"
                                 " return {moves: m.length, border: g(b, 'borderTopWidth'), bg: g(b, 'backgroundColor'), size: g(w, 'fontSize'), ink: g(w, 'color'), muted: tok('var(--text-muted)'),"
                                 " link: m.map(e => [g(e, 'borderTopWidth'), g(e, 'backgroundColor'), g(e, 'textDecorationLine'), g(e, 'color'), g(e, 'fontWeight'), g(e, 'fontSize')]), marginBottom: g(b, 'marginBottom'), blue: tok('var(--brand-blue)')}; })()", sid)
                    self.assertEqual(got["moves"], 2, "the function stays: two move buttons")
                    self.assertEqual((got["border"], got["bg"]), ("0px", "rgba(0, 0, 0, 0)"), got)
                    self.assertEqual(got["size"], "13px")
                    self.assertEqual(got["ink"], got["muted"])
                    self.assertEqual(got["marginBottom"], "12px", "the approved spec: 12px under the note")
                    for border, bg, line, colour, weight, size in got["link"]:
                        self.assertEqual((border, bg, line, colour, weight, size), ("0px", "rgba(0, 0, 0, 0)", "underline", got["blue"], "600", "13px"))


class Prompts(unittest.TestCase):
    """Row 1285 ruling: an empty Revisit and Replaces say what to add in Edit; the view keeps the dash."""
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    _base_setup = _B.setUp
    JS = "[...document.querySelectorAll('#peek [data-ms-row=revisit] dd, #peek [data-ms-row=replaces] dd')].map(e => e.textContent.trim())"

    def setUp(self):
        self._base_setup()
        p = classic()          # the prompts are Classic only: the page needs the Theme layered on, as in the Focus class
        p.start()
        self.addCleanup(p.stop)
        with self.store.step("dashboard", "Demo User") as st:
            st.update("decisions", "TUL-D-016", {"revisit": "", "replaces": ""})

    def test_edit_says_what_to_add_and_the_view_keeps_the_dash(self):
        for width in (1400, 900):
            for edit, want in ((True, ["Add when to look at this again.", "Add the decision this replaces."]), (False, ["—", "—"])):
                with self.subTest(width=width, edit=edit), chrome() as cdp:
                    sent, sid = self.load(cdp, width, "TUL-D-016", edit=edit)
                    if not edit:        # the Dashboard in View is the one place that is not Edit (row 824): open the same peek from there
                        cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-mode=view][aria-pressed=true]')", sid)))
                        cdp.js("clarkPage.openPeek('TUL-D-016')", sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ms-row=revisit]')", sid)))
                    self.assertEqual(cdp.js(self.JS, sid), want)


for _n in [n for n in dir(_Fields) if n.startswith('test')]:
    setattr(Milestone, _n, None)      # only this file's own test runs, not the base class's


del _m, _Fields


if __name__ == "__main__":
    unittest.main()



class LatestValues(unittest.TestCase):
    """Row 1285, the approved peek mock-up's measured values for the Latest update (Classic): label 18px above, Draft with AI padding 4px 8px, footer gap 10 and right padding 10, key 11px / 600 / radius 5 / padding 0 5px."""
    load, fresh, refused = _B.load, _B.fresh, _B.refused
    _base_setup = _B.setUp

    def setUp(self):
        self._base_setup()
        p = classic()
        p.start()
        self.addCleanup(p.stop)

    def test_the_latest_update_label_button_footer_and_key_match_the_mock_up(self):
        for width in (1400, 900):
            for ref, kind in ITEMS:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ref, edit=True)
                    got = cdp.js("(() => { const g = (s, ps) => { const e = document.querySelector(s); if (!e) return null; const c = getComputedStyle(e); return ps.map(p => c[p]); };"
                                 " return {lab: g('#peek .pk-lab', ['marginTop', 'marginBottom']), ai: g('#peek .pk-ai', ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft']),"
                                 " foot: g('#peek .pk-lfoot', ['columnGap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft']),"
                                 " key: g('#peek .pk-key', ['fontSize', 'fontWeight', 'borderTopLeftRadius', 'paddingLeft', 'paddingRight'])}; })()", sid)
                    self.assertEqual(got["lab"], ["18px", "8px"], got)
                    self.assertEqual(got["ai"], ["4px", "8px", "4px", "8px"], got)
                    self.assertEqual(got["foot"], ["10px", "8px", "10px", "8px", "14px"], got)
                    self.assertEqual(got["key"], ["11px", "600", "5px", "5px", "5px"], got)

    def test_the_label_is_bold_13px_and_the_client_value_is_grey_not_green(self):
        """Row 1285 (peek frame): the Latest update label is 13px / 700 (the mock-up's bold) and 'Shown to the client' is the muted grey, never the status green."""
        shown = next(a["id"] for a in self.store.read("actions") if a.get("client_visible"))
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, shown, edit=True)
                got = cdp.js("(() => { const c = s => getComputedStyle(document.querySelector(s));"
                             " const m = document.createElement('i'); m.style.color = 'var(--text-muted)'; document.body.append(m); const muted = getComputedStyle(m).color; m.remove();"
                             " return {size: c('#peek .pk-lab').fontSize, weight: c('#peek .pk-lab').fontWeight, client: c('#peek [data-pk-latest-client]').color, muted}; })()", sid)
                self.assertEqual((got["size"], got["weight"]), ("13px", "700"), got)
                self.assertEqual(got["client"], got["muted"], got)


del _B

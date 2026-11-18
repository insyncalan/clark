"""Row 1314: the Classic Work items page as the prototype draws it, in the Classic theme layer only.

Run: python3 dev/run_tests.py test_work_items_classic_1314
Covers the filter underline, the joined square layout pair with a grey chosen half, and the heading hairlines. Cards (shell.css) must not carry any of it.
"""
import re
import unittest

from clark import page, theme
from _real_server import real_server
from test_server import chrome
from test_work_board_page import Base
from _paths import ROOT

RULES = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def block(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{(.*?)\}$", RULES, re.M)
    assert m, selector
    return m.group(1)


class ClassicRules(unittest.TestCase):
    def test_filter_line_is_underline_only(self):
        b = block(".fline")
        self.assertIn("border: 0;", b)
        self.assertIn("border-bottom: 1px solid var(--grey-200)", b)
        self.assertIn("border-radius: 0", b)
        self.assertIn("background: none", b)
        self.assertIn("margin-right: 0", block(".fline-tail"))

    def test_layout_pair_is_square_and_chosen_half_is_grey_not_aqua(self):
        self.assertIn("border-radius: var(--radius-sm)", block(".vicons .lsw, .vicons .btn.sm.vgb"))
        b = block('.vicons .lsw button[aria-pressed="true"]')
        self.assertIn("background-color: var(--grey-100)", b)
        self.assertIn("background-image: none", b)
        self.assertIn("outline-offset: -2px", block('.vicons .lsw button[aria-pressed="true"]:focus-visible'))

    def test_heading_has_hairlines_between_columns_only(self):
        b = block("table.items thead th + th, .wil-table thead th + th")
        self.assertIn("border-left: 1px solid var(--grey-200)", b)

    def test_only_tokens(self):
        for sel in (".fline", ".fline-tail", ".vicons .lsw, .vicons .btn.sm.vgb", "table.items thead th + th, .wil-table thead th + th"):
            self.assertNotRegex(block(sel), r"#[0-9a-fA-F]{3,6}\b")

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("Row 1314", SHELL)
        self.assertNotIn("table.items thead th + th", SHELL)


# The Row 1314 block, at the end of rules.css: three gaps, each pinned by what the browser draws, not by the text.
MARK = RULES.index("/* Row 1314")
OWN = RULES[MARK:]


class ClassicBlock(unittest.TestCase):
    def test_the_block_is_last_and_holds_the_three_rules(self):
        self.assertEqual(RULES.count("/* Row 1314"), 1)
        self.assertIn('.fline-tail .vicons .seg.lsw button[aria-pressed="true"]:focus-visible { outline-color: var(--brand-blue); outline-offset: -2px; }', OWN)
        self.assertIn("@media (max-width: 900px) { .vtabs { flex-wrap: wrap; overflow-x: visible; } }", OWN)
        self.assertIn(".fline.bad, .fline.bad:focus-within { border-bottom-color: var(--status-red); box-shadow: 0 1px 0 var(--status-red); }", OWN)
        self.assertNotIn("!important", OWN)
        self.assertNotRegex(OWN, r"#[0-9a-fA-F]{3,6}\b")


class Browser(Base):
    """The Classic Work items page in Chrome (the page with the Classic theme layered), at 1400 and 900."""
    classic = True

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0") if self.classic else None
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(__import__("tempfile").mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def ring(self, cdp, sid):
        cdp.js("document.querySelector('#work [data-lay=table]').focus()", sid)
        self.until(cdp, sid, "document.activeElement.dataset.lay === 'table'", "focus on the pressed tile")
        return cdp.js("(() => { const b = document.querySelector('#work [data-lay=table]'), s = getComputedStyle(b); return {pressed: b.getAttribute('aria-pressed'), focus: b.matches(':focus-visible'), color: s.outlineColor, offset: s.outlineOffset, style: s.outlineStyle}; })()", sid)

    def test_the_pressed_layout_tile_draws_the_classic_focus_ring(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
                want = cdp.js("(() => { const e = document.createElement('i'); e.style.color = 'var(--brand-blue)'; document.body.append(e); const c = getComputedStyle(e).color; e.remove(); return c; })()", sid)
                got = self.ring(cdp, sid)
                self.assertEqual(got["pressed"], "true")
                self.assertTrue(got["focus"], got)
                self.assertEqual(got["offset"], "-2px", got)
                self.assertEqual(got["color"], want, got)
                self.assertNotEqual(got["style"], "none", got)

    def test_the_view_tabs_wrap_at_900_and_never_scroll_sideways(self):
        probe = ("(() => { const t = document.querySelector('#work .vtabs'), s = getComputedStyle(t); return {wrap: s.flexWrap, ox: s.overflowX, "
                 "scrolls: t.scrollWidth > t.clientWidth, page: document.documentElement.scrollWidth > innerWidth}; })()")
        with chrome() as cdp:
            sid = self.visit(cdp, width=900)
            got = cdp.js(probe, sid)
            self.assertEqual(got["wrap"], "wrap", got)
            self.assertFalse(got["scrolls"], got)
            self.assertFalse(got["page"], got)
            cdp.js("document.querySelector('#work .vtabs').style.maxWidth = '260px'", sid)
            rows = cdp.js("new Set([...document.querySelectorAll('#work .vtabs > *')].map(e => Math.round(e.getBoundingClientRect().top))).size", sid)
            self.assertGreater(rows, 1, "squeezed, the tabs go to a second line")
            self.assertFalse(cdp.js(probe, sid)["scrolls"])
        with chrome() as cdp:
            sid = self.visit(cdp, width=1400)
            self.assertEqual(cdp.js(probe, sid)["wrap"], "nowrap", "above 900 the tabs keep the shared single line")

    def test_a_line_the_filter_cannot_read_is_a_red_underline_not_a_red_box(self):
        look = ("(() => { const s = getComputedStyle(document.querySelector('#work .fline')); return {bottom: s.borderBottomColor, w: s.borderBottomWidth, top: s.borderTopWidth, left: s.borderLeftWidth, shadow: s.boxShadow}; })()")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                red = cdp.js("(() => { const e = document.createElement('i'); e.style.color = 'var(--status-red)'; document.body.append(e); const c = getComputedStyle(e).color; e.remove(); return c; })()", sid)
                for focused in (False, True):
                    if focused:
                        cdp.js("document.querySelector('#fline-input').focus()", sid)
                    else:
                        self.line(cdp, sid, "zzqq:nope")
                        cdp.js("document.activeElement.blur()", sid)
                    self.until(cdp, sid, "document.querySelector('#work .fline').classList.contains('bad')", "the line is marked bad")
                    got = cdp.js(look, sid)
                    self.assertEqual(got["bottom"], red, got)
                    self.assertEqual((got["top"], got["left"]), ("0px", "0px"), got)
                    self.assertEqual(got["shadow"], red + " 0px 1px 0px 0px", f"an underline 1 px thicker, no frame: {got}")


if __name__ == "__main__":
    unittest.main()

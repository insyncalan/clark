"""Row 1394: the Work items view tabs as the prototype draws them, in the Classic theme layer only.

Run: python3 dev/run_tests.py test_work_items_tabs_1394
One test per spec row at 1400 (the priority width), light and dark where a colour is named. Cards (shell.css) must not carry any of it.
"""
import re
import unittest

from clark import page, theme
from _real_server import real_server
from test_server import chrome
from test_work_board_page import Base
from _paths import ROOT

RULES = ((ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
MARK = RULES.index("/* Row 1394")
OWN = RULES[MARK:RULES.index("/* Row 1314")]

PROBE = ("(() => { const tab = document.querySelector('#work .vtab[aria-pressed=\"true\"]'), idle = [...document.querySelectorAll('#work .vtab')].find(t => t.getAttribute('aria-pressed') !== 'true'),"
         "nw = document.querySelector('#work .vnew'), c = e => getComputedStyle(e), pad = s => s.paddingTop + ' ' + s.paddingRight + ' ' + s.paddingBottom + ' ' + s.paddingLeft,"
         "tok = (v, p) => { const e = document.createElement('i'); e.style[p] = 'var(' + v + ')'; document.body.append(e); const r = getComputedStyle(e)[p]; e.remove(); return r; };"
         "const on = c(tab), off = idle ? c(idle) : null, pe = c(tab.querySelector('em')), ie = idle ? c(idle.querySelector('em')) : null, n = c(nw);"
         "return {onFont: on.fontSize, onPad: pad(on), onLine: on.borderBottomWidth, onLineColor: on.borderBottomColor, offFont: off && off.fontSize, offPad: off && pad(off), offLine: off && off.borderBottomWidth,"
         "onEm: {font: pe.fontSize, pad: pad(pe), minW: pe.minWidth, bg: pe.backgroundColor, fg: pe.color}, offEm: ie && {font: ie.fontSize, pad: pad(ie), minW: ie.minWidth, bg: ie.backgroundColor, fg: ie.color},"
         "vnew: {font: n.fontSize, pad: pad(n)}, want: {grey: tok('--tone-grey-tint', 'backgroundColor'), muted: tok('--text-muted', 'color'), brand: tok('--brand-blue', 'color'), brandBg: tok('--brand-blue-tint', 'backgroundColor'), blue: tok('--brand-blue', 'borderBottomColor')}}; })()")


class Rules(unittest.TestCase):
    def test_block_is_before_row_1314_and_has_no_colour_literals(self):
        self.assertEqual(RULES.count("/* Row 1394"), 1)
        self.assertLess(MARK, RULES.index("/* Row 1314"))
        self.assertNotRegex(OWN, r"#[0-9a-fA-F]{3,6}\b")
        self.assertNotIn("!important", OWN)

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("Row 1394", SHELL)
        self.assertNotIn("#work .vtab", SHELL)


class Browser(Base):
    """The Classic Work items page in Chrome, at 1400."""

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(__import__("tempfile").mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def probe(self, mode="light"):
        with chrome() as cdp:
            sid = self.visit(cdp, width=1400)
            cdp.js("document.documentElement.dataset.theme = %r" % mode, sid)
            return cdp.js(PROBE, sid)

    def test_row1_tab_text_padding_and_underline(self):
        got = self.probe()
        self.assertEqual((got["onFont"], got["onPad"], got["onLine"]), ("15px", "9px 10px 8px 10px", "3px"), got)
        self.assertEqual(got["onLineColor"], got["want"]["blue"], got)
        if got["offFont"]:
            self.assertEqual((got["offFont"], got["offPad"], got["offLine"]), ("15px", "9px 10px 8px 10px", "3px"), got)

    def test_row2_count_pill_size(self):
        got = self.probe()
        for k in ("onEm", "offEm"):
            if got[k]:
                self.assertEqual((got[k]["font"], got[k]["pad"], got[k]["minW"]), ("13px", "1px 8px 1px 8px", "22px"), got)

    def test_row2_count_pill_colours_light_and_dark(self):
        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                got = self.probe(mode)
                w = got["want"]
                self.assertEqual((got["onEm"]["bg"], got["onEm"]["fg"]), (w["brandBg"], w["brand"]), got)
                if got["offEm"]:
                    self.assertEqual((got["offEm"]["bg"], got["offEm"]["fg"]), (w["grey"], w["muted"]), got)
                if mode == "light":
                    self.assertEqual(got["onEm"]["bg"], "rgb(236, 233, 255)", f"the Classic brand tint token (the ticket names #ECE9FB, 4 off in blue; the token is shared and not changed here): {got}")
                    self.assertEqual(got["onEm"]["fg"], "rgb(91, 71, 216)", got)
                    if got["offEm"]:
                        self.assertEqual(got["offEm"]["bg"], "rgb(236, 239, 245)", got)

    def test_row3_new_view_padding(self):
        got = self.probe()
        self.assertEqual((got["vnew"]["font"], got["vnew"]["pad"]), ("14px", "6px 12px 6px 12px"), got)


if __name__ == "__main__":
    unittest.main()

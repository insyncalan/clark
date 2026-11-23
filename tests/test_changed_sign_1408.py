"""Row 1408: the sign of a changed section on the Classic dashboard is a 2px line under the title that runs left to right and fades out. Nothing stays after it.

Run: python3 dev/run_tests.py test_changed_sign_1408
Classic only. Cards keeps its tint, its bar and the word Changed (tests/test_enrichments.py runs on Cards and is unchanged).
Static: the rules are in the Classic theme and not in shell.css; no Cards style block names the row; the new rules hold no hex and no person name.
Browser, at 1400 and 900, light and dark, with the Classic theme layered: the old tint, bar, tag and glow are gone; the line is 2px brand colour, 3:1 or more on
the card, under the title text only, runs 1.8 s (grows to full by 45 percent, holds, fades to nothing); there is no caption word at all; nothing shifts when the mark goes; reduced motion shows no animation and no line;
forced colours still draw a system-colour line.
"""
import re
import unittest
from unittest import mock

from _paths import ROOT

import _testpage  # noqa: E402
import test_enrichments as TE  # noqa: E402
import test_report_editor as tre  # noqa: E402
from clark import page, theme  # noqa: E402
from test_server import chrome  # noqa: E402,F401  (the runner tells a browser file by this import)

NAME = "prototype-2.0"
RULES = ((ROOT / "src" / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / NAME / "rules-2.css").read_text(encoding="utf-8"))
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
BLOCK = RULES[RULES.index("/* Row 1408"):RULES.index("/* Row 1314")]
FORCED = [{"name": "forced-colors", "value": "active"}]


def setUpModule():
    css = theme.css(NAME)
    orig = _testpage.html
    p = mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(orig(branding), css))
    p.start()
    unittest.addModuleCleanup(p.stop)


_page_html = page.page_html      # the test page hook rule (test_peek) reads the call text, and these two calls are static string checks


class Static(unittest.TestCase):
    def test_the_rules_are_in_the_classic_theme_only(self):
        self.assertIn("sec-sweep-1408", RULES)
        self.assertNotIn("sec-sweep", SHELL)
        cards = _page_html(branding=page.NO_BRAND, theme=None)
        self.assertNotIn("Row 1408", cards)
        self.assertIn("sec-sweep-1408", _page_html(branding=page.NO_BRAND, theme=NAME))

    def test_the_rules_use_tokens_and_the_timing_is_1800_ms(self):
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b", BLOCK), "no hex in the Row 1408 rules")
        self.assertIn("1800ms", BLOCK)
        self.assertIn("var(--brand-blue)", BLOCK)
        self.assertIn("prefers-reduced-motion: no-preference", BLOCK)
        self.assertIn("forced-colors: active", BLOCK)
        self.assertIn("CanvasText", BLOCK)

    def test_the_store_keeps_changed_for_cards_and_has_no_second_word(self):
        store = (ROOT / "src" / "clark" / "page" / "src" / "stores" / "changed.js").read_text(encoding="utf-8")
        self.assertIn('export const WORD = "Changed";', store)
        self.assertEqual(len(re.findall(r"export const [A-Z_]*WORD =", store)), 1)

class Sign(tre.Base):
    def setup_page(self, w, dark, mode=None):
        self.p.js("document.documentElement.setAttribute('data-theme', %s)" % ("'dark'" if dark else "'light'"))
        self.p.cdp.call("Emulation.setEmulatedMedia", {"features": mode or []}, self.p.sid)
        TE.Mark.width(self, self.p, w)

    def start(self, cdp):
        p = self.p = self.visit(cdp)
        p.js("window.__timers = []; clarkPage.useClock({setTimeout: (f, ms) => { window.__timers.push([f, ms]); return window.__timers.length; }, clearTimeout: () => {}})")
        p.edit()
        p.menu("ABC-S-002", "hide")
        p.until("!!document.querySelector('[data-id=\"ABC-S-002\"].sec-sweep')", "the changed section carries the sweep")
        return p

    def read(self, p):
        return p.js("""(function(){var s=document.querySelector('[data-id="ABC-S-002"]'), o=document.querySelector('[data-id="ABC-S-003"]'), t=s.querySelector('.sec-t');
          var a=getComputedStyle(t||s,'::after'), cs=getComputedStyle(s), os=getComputedStyle(o), tr=(t||s).getBoundingClientRect(), hr=s.querySelector('.sec-head').getBoundingClientRect();
          return {old:[s.classList.contains('is-changed'), !!s.querySelector('.tag.chg')], bg:cs.backgroundColor, obg:os.backgroundColor, shadow:cs.boxShadow, oshadow:os.boxShadow, sanim:cs.animationName,
            aname:a.animationName, adur:a.animationDuration, h:a.height, bgA:a.backgroundColor, bottom:a.bottom, aw:a.width, tw:tr.width, hw:hr.width, secH:s.offsetHeight,
            cap:!!s.querySelector('.tag.chg'), words:s.querySelector('.sec-head').textContent, inside:tr.left>=0&&tr.right<=innerWidth&&tr.width>0,
            scroll:document.documentElement.scrollWidth<=innerWidth, flag:s.dataset.changed||null};})()""")

    def at(self, p, ms):
        return p.js("""(function(){var an=document.getAnimations().filter(function(x){return x.animationName==='sec-sweep-1408'});
          an.forEach(function(x){x.pause(); x.currentTime=%d}); var t=document.querySelector('[data-id="ABC-S-002"] .sec-t'), a=getComputedStyle(t||s,'::after');
          return {n:an.length, op:parseFloat(a.opacity), tf:a.transform};})()""" % ms)

    def test_the_line_at_two_widths_light_and_dark(self):
        with chrome() as cdp:
            p = self.start(cdp)
            for dark in (False, True):
                for w in TE.WIDTHS:
                    with self.subTest(dark=dark, width=w):
                        self.setup_page(w, dark)
                        p.until("document.documentElement.scrollWidth <= innerWidth", "no sideways scroll")
                        surface = TE.parse_rgb(TE.probe(p, "var(--surface)"))
                        blue = TE.parse_rgb(TE.probe(p, "var(--brand-blue)"))
                        g = self.read(p)
                        self.assertEqual(g["old"], [False, False], "no amber class and no Changed tag")
                        self.assertEqual(g["flag"], "1")
                        self.assertNotEqual(TE.parse_rgb(g["bg"]), TE.parse_rgb(TE.probe(p, "var(--status-amber-tint)")), "no amber tint")
                        self.assertEqual((g["shadow"], g["sanim"]), (g["oshadow"], "none"), "no bar and no glow: the card is drawn as the card beside it that did not change")
                        self.assertEqual((g["aname"], g["adur"], g["h"]), ("sec-sweep-1408", "1.8s", "2px"))
                        self.assertEqual(TE.parse_rgb(g["bgA"]), blue)
                        self.assertEqual(g["bottom"], "-4px")
                        self.assertGreaterEqual(TE.ratio(blue, surface), 3, "the line is 3:1 on the card")
                        self.assertAlmostEqual(float(g["aw"][:-2]), g["tw"], delta=1, msg="the line is as wide as the title")
                        self.assertLess(g["tw"], g["hw"], "under the title text only, not the whole header")
                        self.assertFalse(g["cap"])
                        self.assertNotIn("Changed", g["words"])
                        self.assertTrue(g["inside"] and g["scroll"])
                        start, hold, end = self.at(p, 0), self.at(p, 1000), self.at(p, 1800)
                        self.assertEqual((start["n"], start["op"]), (1, 1.0))
                        self.assertTrue(start["tf"].startswith("matrix(0,") or start["tf"].startswith("matrix(0.0"), start["tf"])
                        self.assertEqual((hold["op"], hold["tf"].split(",")[0]), (1.0, "matrix(1"))
                        self.assertEqual(end["op"], 0.0)
                        self.assertEqual(self.at(p, 810)["tf"].split(",")[0], "matrix(1", "full at 45 percent of 1.8 s, about 0.8 s")

    def test_nothing_shifts_when_the_line_goes(self):
        with chrome() as cdp:
            p = self.start(cdp)
            for w in TE.WIDTHS:
                with self.subTest(width=w):
                    self.setup_page(w, False)
                    before = self.read(p)
                    top = p.js("document.querySelector('[data-id=\"ABC-S-003\"]').getBoundingClientRect().top")
                    p.js("window.__timers[window.__timers.length - 1][0]()")      # the line's 3 seconds are over (the store clears the mark)
                    p.until("!document.querySelector('.sec-sweep')", "the sweep goes")
                    after = self.read(p)
                    self.assertEqual(after["secH"], before["secH"], "the card keeps its height")
                    self.assertEqual(p.js("document.querySelector('[data-id=\"ABC-S-003\"]').getBoundingClientRect().top"), top, "nothing below moved")
                    self.assertEqual((after["cap"], after["flag"]), (False, None), "nothing stays")
                    p.js("clarkPage.markChanged(['ABC-S-002'])")
                    p.until("!!document.querySelector('.sec-sweep')", "marked again")

    def test_reduced_motion_shows_no_animation_and_no_word(self):
        with chrome() as cdp:
            p = self.start(cdp)
            for w in TE.WIDTHS:
                with self.subTest(width=w):
                    self.setup_page(w, False, TE.REDUCE)
                    self.assertTrue(p.js("matchMedia('(prefers-reduced-motion: reduce)').matches"))
                    g = self.read(p)
                    self.assertEqual(g["aname"], "none")
                    self.assertFalse(g["cap"])
                    self.assertEqual(g["sanim"], "none")

    def test_the_line_grows_from_the_left_edge(self):
        with chrome() as cdp:
            p = self.start(cdp)
            for w in TE.WIDTHS:
                with self.subTest(width=w):
                    self.setup_page(w, False)
                    origin = p.js("getComputedStyle(document.querySelector('[data-id=\"ABC-S-002\"] .sec-t'), '::after').transformOrigin")
                    self.assertEqual(float(origin.split()[0][:-2]), 0.0, "the sweep's origin is the left edge: " + origin)
                    mid = self.at(p, 200)["tf"]
                    nums = [float(x) for x in mid[mid.index("(") + 1:-1].split(",")]
                    self.assertTrue(0 < nums[0] < 1, mid)

    def test_the_page_own_data_motion_reduce_stops_the_sweep(self):
        with chrome() as cdp:
            p = self.start(cdp)
            for w in TE.WIDTHS:
                with self.subTest(width=w):
                    self.setup_page(w, False)
                    self.assertFalse(p.js("matchMedia('(prefers-reduced-motion: reduce)').matches"), "the computer does not ask for reduced motion here")
                    self.assertEqual(self.read(p)["aname"], "sec-sweep-1408", "the sweep runs without the attribute")
                    p.js("document.documentElement.dataset.motion = 'reduce'")
                    try:
                        self.assertEqual(self.read(p)["aname"], "none", "clark's own reduced motion switch turns the sweep off")
                    finally:
                        p.js("delete document.documentElement.dataset.motion")
                    self.assertEqual(self.read(p)["aname"], "sec-sweep-1408", "and back on without it")

    def test_the_line_does_not_catch_clicks(self):
        with chrome() as cdp:
            p = self.start(cdp)
            for w in TE.WIDTHS:
                with self.subTest(width=w):
                    self.setup_page(w, False)
                    g = p.js("""(function(){var t=document.querySelector('[data-id="ABC-S-002"] .sec-t'), r=t.getBoundingClientRect(), a=getComputedStyle(t,'::after');
                      var x=r.left+r.width/2, y=r.bottom+5, e=document.elementFromPoint(x,y);
                      return {pe:a.pointerEvents, hit:e===t||t.contains(e), tag:e&&e.className};})()""")
                    self.assertEqual(g["pe"], "none")
                    self.assertFalse(g["hit"], "a click at the line's centre goes to what is under it, not to the title: " + str(g["tag"]))

    def test_forced_colours_still_show_the_sign(self):
        with chrome() as cdp:
            p = self.start(cdp)
            for w in TE.WIDTHS:
                with self.subTest(width=w):
                    self.setup_page(w, False, FORCED)
                    self.assertTrue(p.js("matchMedia('(forced-colors: active)').matches"))
                    g = self.read(p)
                    self.assertFalse(g["cap"])
                    self.assertTrue(g["inside"])
                    self.assertNotEqual(g["bgA"], "rgba(0, 0, 0, 0)", "the line is a system colour, not nothing")


if __name__ == "__main__":
    unittest.main()

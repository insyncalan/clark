"""Row 1312: the Classic section gutter (2px --gutter-rule, 20px padding) shows on Work items, Milestones, Use cases and Settings.

Run: python3 dev/run_tests.py test_theme_gutter_1312
Chrome computes the left border of the one element that carries the gutter on each page (.frame.work, .frame.milestones, .frame.ucl,
.set-layout), at 1400 and 900, light and dark, over the demo data (fictional). The Dashboard has none of it; Cards (no Theme layer)
is the page byte for byte. Fails, never skips, without Chrome.
"""
import json
import re
import time
import unittest

from _paths import ROOT
from test_server import chrome
from test_work_board_page import Base, page_target

from clark import page

NAME = "prototype-2.0"
RULES = ROOT / "src" / "clark" / "themes" / NAME / "rules.css"
LIGHT, DARK = "rgb(238, 235, 251)", "rgb(42, 38, 80)"      # --gutter-rule #EEEBFB and #2A2650, as the Theme's tokens set them
PAGES = (("work", "#work&p=ABC", "#work", ".frame.work"),
         ("milestones", "#milestones&p=ABC", "#milestones", ".frame.milestones"),
         ("usecases", "#usecases&p=ABC", "#usecases", ".frame.ucl"),
         ("settings", "#settings", "#projects", ".set-layout"))
READ = """(sel) => { const e = document.querySelector(sel); const c = getComputedStyle(e);
    return JSON.stringify([c.borderLeftWidth, c.borderLeftStyle, c.borderLeftColor, c.paddingLeft, c.borderTopWidth, c.borderRightWidth, c.transitionProperty, c.transitionDuration]); }"""


def block():
    """The text of the marked Row 1312 block: from its comment to the next row's comment (later rows are appended after it)."""
    text = RULES.read_text(encoding="utf-8")
    text = text[text.index("/* Row 1312"):]
    nxt = text.find("\n/* Row ", 1)
    return text if nxt < 0 else text[:nxt]


class Source(unittest.TestCase):
    def test_the_block_is_last_and_names_no_dashboard_or_published_frame(self):
        b = block()
        self.assertEqual(b.count("/* Row 1312"), 1)
        rules = re.sub(r"/\*.*?\*/", "", b, flags=re.S)
        self.assertNotIn(".sec", rules)
        self.assertNotIn(".report", rules)
        self.assertNotIn(".ucpage", rules)
        self.assertEqual(len(re.findall(r"\.frame\.work:not\(\.pub\)", rules)), 4)      # base, hover, focus, print: the editor frame only

    def test_the_milestones_and_work_frames_are_the_editor_ones_in_every_rule(self):
        rules = re.sub(r"/\*.*?\*/", "", block(), flags=re.S)
        for name in ("work", "milestones"):
            self.assertEqual(len(re.findall(r"\.frame\.%s(?!:not\(\.pub\))\b" % name, rules)), 0, name)
        self.assertEqual(len(re.findall(r"\.frame\.ucl\b", rules)), 4)
        self.assertEqual(len(re.findall(r"\.set-layout\b", rules)), 4)
        self.assertEqual(rules.count(":hover"), 4)
        self.assertEqual(rules.count(":focus-within"), 4)

    def test_the_values_are_the_sec_rules_values(self):
        b = re.sub(r"/\*.*?\*/", "", block(), flags=re.S)
        self.assertIn("border-left: 2px solid var(--gutter-rule); padding-left: 20px;", b)
        self.assertIn("color-mix(in srgb, var(--brand-blue) 35%, var(--gutter-rule))", b)
        self.assertIn("@media print", b)
        self.assertIn("border-left: 0; padding-left: 0;", b)

    def test_cards_is_not_touched(self):
        plain = page.page_html(branding=page.NO_BRAND)
        self.assertNotIn("Row 1312", plain)
        self.assertNotIn('id="theme"', plain)
        self.assertNotIn("--gutter-rule: #", plain)


class Computed(Base):
    def setUp(self):
        super().setUp()
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=NAME)

    def load(self, hash_, wait_for, width, scheme, cdp):
        try:
            sid = self.visit(cdp, width=width, hash_=hash_, wait_for=wait_for)
        except AssertionError:                          # the Dashboard has its View | Edit switch
            sid = page_target(cdp)
        cdp.js("document.documentElement.setAttribute('data-theme', %r)" % scheme, sid)
        time.sleep(0.4)                                 # the .2s border-color transition
        return sid

    def read(self, cdp, sid, sel):
        return json.loads(cdp.js("(%s)(%r)" % (READ, sel), sid))

    def test_each_page_shows_the_two_pixel_rule_in_both_widths_and_schemes(self):
        for width in (1400, 900):
            for scheme, colour in (("light", LIGHT), ("dark", DARK)):
                for name, hash_, wait_for, sel in PAGES:
                    with self.subTest(page=name, width=width, scheme=scheme), chrome() as cdp:
                        sid = self.load(hash_, wait_for, width, scheme, cdp)
                        w, style, col, pad, top, right, tp, td = self.read(cdp, sid, sel)
                        self.assertEqual((w, style, col, pad), ("2px", "solid", colour, "20px"))
                        self.assertEqual((tp, td), ("border-color", "0.2s"))
                        self.assertEqual((top, right), ("0px", "0px"), "only the left side")

    def blend(self, cdp, sid):
        """The computed colour of the rule's hover blend (35% --brand-blue into --gutter-rule), read off a probe in the same scheme."""
        return cdp.js("""(() => { const p = document.createElement('i'); p.style.color = 'color-mix(in srgb, var(--brand-blue) 35%, var(--gutter-rule))';
            document.body.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; })()""", sid)

    def rule_colour(self, cdp, sid, sel):
        return cdp.js("getComputedStyle(document.querySelector(%r)).borderLeftColor" % sel, sid)

    def test_a_pointer_over_the_element_blends_the_brand_in_and_leaving_restores_it(self):
        for scheme, colour in (("light", LIGHT), ("dark", DARK)):
            for name, hash_, wait_for, sel in PAGES:
                with self.subTest(page=name, scheme=scheme), chrome() as cdp:
                    sid = self.load(hash_, wait_for, 1400, scheme, cdp)
                    want = self.blend(cdp, sid)
                    self.assertNotEqual(want, colour, "the blend differs from the plain rule")
                    self.assertFalse(cdp.js("document.querySelector(%r).contains(document.activeElement)" % sel, sid), "no focus inside: hover alone")
                    self.assertEqual(self.rule_colour(cdp, sid, sel), colour)
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1, "y": 1}, sid)
                    time.sleep(0.4)
                    self.assertEqual(self.rule_colour(cdp, sid, sel), colour, "pointer elsewhere: plain rule")
                    x, y = cdp.js("""((sel) => { const r = document.querySelector(sel).getBoundingClientRect();
                        const top = Math.max(r.top, 0), bottom = Math.min(r.bottom, innerHeight);
                        return [Math.round(r.left + 10), Math.round((top + bottom) / 2)]; })(%r)""" % sel, sid)
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
                    time.sleep(0.5)
                    self.assertTrue(cdp.js("document.querySelector(%r).matches(':hover')" % sel, sid), "the pointer is over %s" % sel)
                    self.assertEqual(self.rule_colour(cdp, sid, sel), want, "hover blends 35% brand into the rule")
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1, "y": 1}, sid)
                    time.sleep(0.5)
                    self.assertEqual(self.rule_colour(cdp, sid, sel), colour, "pointer left: plain rule again")

    def test_focus_inside_blends_the_brand_in_without_a_pointer(self):
        for scheme, colour in (("light", LIGHT), ("dark", DARK)):
            for name, hash_, wait_for, sel in PAGES:
                with self.subTest(page=name, scheme=scheme), chrome() as cdp:
                    sid = self.load(hash_, wait_for, 1400, scheme, cdp)
                    want = self.blend(cdp, sid)
                    cdp.js("(() => { const e = document.querySelector(%r); const t = document.createElement('button'); e.appendChild(t); t.focus(); })()" % sel, sid)
                    time.sleep(0.5)
                    self.assertTrue(cdp.js("document.querySelector(%r).matches(':focus-within') && !document.querySelector(%r).matches(':hover')" % (sel, sel), sid))
                    self.assertEqual(self.rule_colour(cdp, sid, sel), want, "focus inside blends 35% brand into the rule")
                    self.assertNotEqual(want, colour)

    def test_print_has_no_rule_and_no_padding(self):
        for name, hash_, wait_for, sel in PAGES:
            with self.subTest(page=name), chrome() as cdp:
                sid = self.load(hash_, wait_for, 1400, "light", cdp)
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
                time.sleep(0.4)
                w, style, col, pad, top, right, tp, td = self.read(cdp, sid, sel)
                self.assertEqual((w, pad), ("0px", "0px"))

    def test_the_dashboard_carries_none_of_it(self):
        for width in (1400, 900):
            for scheme, colour in (("light", LIGHT), ("dark", DARK)):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.load("#dashboard&p=ABC", "#report", width, scheme, cdp)
                    for sel in ("#report", "#report .sec"):
                        if cdp.js("!!document.querySelector(%r)" % sel, sid):
                            w, style, col, pad, top, right, tp, td = self.read(cdp, sid, sel)
                            self.assertFalse(w == "2px" and col == colour, sel)
                    self.assertEqual(cdp.js("document.querySelectorAll('.set-layout, .frame.work, .frame.milestones, .frame.ucl').length", sid), 0)


if __name__ == "__main__":
    unittest.main()

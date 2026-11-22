"""Row 1348 (Tech Debt): in Classic the Ask clark panel opens from the right edge and leaves to it, as the prototype's does; Cards keeps its rise from the bottom.
Run: python3 dev/run_tests.py test_ask_slide_1348

The page is the real edit page (the committed test build) with the Classic Theme layered in, as the server layers it. As Chrome computes it at 1400 and 900 px,
light and dark: the opening animation moves the panel along x only, from 104 percent of its width to rest, over --dur-layout with --ease-enter; the closing one
moves it back along x over exactly 200 ms with --ease-exit and the panel is removed afterwards; under reduced motion nothing animates. The Cards page (no Theme) still
rises along y, and its stylesheet is the one main has. The prototype's text and data are test content here, only its motion is the reference."""
import hashlib
import re
import unittest
from unittest import mock

import _testpage as testpage
from _paths import ROOT

from clark import page
from clark import theme as themes
from test_ask_panel import Stub
from test_report_editor import Base

NAME = "prototype-2.0"
RULES = (ROOT / "src/clark/themes/prototype-2.0/rules.css").read_text(encoding="utf-8")
CARDS_STYLE_MD5 = ["7195b3107c3b5022f3b40ad1dfbbe484"]        # page_html(branding=NO_BRAND, theme=None) on origin/main d3724869, before this row
# keyframes of the panel's running animation, the end positions, the timing, and the panel's width
PROBE = """(() => { const el = document.querySelector('#ask-panel'), a = el.getAnimations()[0]; if (!a) return null;
  const k = a.effect.getKeyframes(), t = a.effect.getComputedTiming(), w = el.getBoundingClientRect().width;
  return { name: a.animationName, from: k[0].transform, to: k[k.length - 1].transform, dur: t.duration, ease: getComputedStyle(el).animationTimingFunction, w: Math.round(w) }; })()"""
TOKENS = """(() => { const s = getComputedStyle(document.documentElement); return { layout: s.getPropertyValue('--dur-layout').trim(), state: s.getPropertyValue('--dur-state').trim(),
  enter: s.getPropertyValue('--ease-enter').trim(), exit: s.getPropertyValue('--ease-exit').trim() }; })()"""
# mid-flight sample: pause the animation at half its time and read the matrix the panel is drawn with
HALF = """(() => { const el = document.querySelector('#ask-panel'), a = el.getAnimations()[0]; a.pause(); a.currentTime = a.effect.getComputedTiming().duration * 0.5;
  const m = new DOMMatrix(getComputedStyle(el).transform); return { x: m.m41, y: m.m42, w: el.getBoundingClientRect().width }; })()"""


def ms(v):
    return float(v[:-2])


def eased(v):
    return re.sub(r"(?<![\d])0\.", ".", re.sub(r"\s+", "", v))


class Slide(Base):
    theme = NAME

    def setUp(self):
        full = testpage.html()
        html = page.layer_theme(full, themes.css(self.theme)) if self.theme else full
        p = mock.patch.object(testpage, "html", lambda branding=None: html)
        p.start()
        self.addCleanup(p.stop)
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def run_both(self, check):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for scheme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{scheme}'")
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, p.sid)
                    p.js("delete document.documentElement.dataset.motion")
                    with self.subTest(width=width, scheme=scheme):
                        check(p, cdp)

    def open_close(self, p):
        tok = p.js(TOKENS)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel') && document.querySelector('#ask-panel').getAnimations().length > 0", "opened")
        opening = p.js(PROBE)
        half = p.js(HALF)
        p.js("document.querySelector('#ask-panel').getAnimations().forEach((a) => a.finish())")
        p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "settled")
        p.key("Escape", code="Escape", vk=27)
        p.until("document.querySelector('#ask-panel') && document.querySelector('#ask-panel').classList.contains('leaving')", "leaving")
        closing = p.js(PROBE)
        p.js("document.querySelector('#ask-panel').getAnimations().forEach((a) => a.finish())")
        p.until("document.querySelector('#ask-panel') === null", "gone", seconds=15)
        return tok, opening, half, closing

    def test_classic_opens_and_closes_along_x_with_the_panels_own_timing(self):
        def check(p, cdp):
            tok, o, h, c = self.open_close(p)
            self.assertEqual((o["name"], c["name"]), ("ask-up", "ask-down"), "the panel's code still waits for ask-down")
            self.assertEqual((o["from"], o["to"]), ("translateX(104%)", "none"), "opens from the right edge to rest")
            self.assertEqual((c["from"], c["to"]), ("none", "translateX(104%)"), "leaves to the right edge")
            self.assertEqual((o["dur"], c["dur"]), (ms(tok["layout"]), 200), "380 ms in (the layout token), exactly 200 ms out")
            self.assertEqual((eased(o["ease"]), eased(c["ease"])), (eased(tok["enter"]), eased(tok["exit"])), "ease-enter in, ease-exit out")
            self.assertEqual((eased(o["ease"]), eased(c["ease"])), ("cubic-bezier(.16,1,.3,1)", "cubic-bezier(.7,0,.84,0)"), "the prototype's curves, spelled out")
            self.assertEqual(o["w"], 420, "the panel keeps its 420 px")
            self.assertGreater(h["x"], 0, "half way it is still right of its place")
            self.assertAlmostEqual(h["x"], h["w"] * 1.04 * 0.5, delta=h["w"] * 0.5, msg="and moved by less than the full 104 percent")
            self.assertEqual(h["y"], 0, "it does not rise: no vertical move")
        self.run_both(check)

    def test_classic_still_under_reduced_motion(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
                with self.subTest(width=width):
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-panel')", "opened")
                    self.assertEqual(p.js("document.querySelector('#ask-panel').getAnimations().length"), 0)
                    p.key("Escape", code="Escape", vk=27)
                    p.until("document.querySelector('#ask-panel') === null", "gone", seconds=15)

    def test_the_rule_is_in_the_theme_file_only_and_moves_transform_on_x(self):
        i = RULES.index("Row 1348")
        block = RULES[i:]
        self.assertRegex(block, r"@media \(prefers-reduced-motion: no-preference\)")
        for name in ("ask-up", "ask-down"):
            body = re.search(r"@keyframes " + name + r" \{(.*?)\}\s*\}", block).group(0)
            self.assertIn("translateX(104%)", body)
            self.assertNotRegex(body, r"translateY|height|margin|padding|top|left|width|bottom")
        edit = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
        self.assertIn("@keyframes ask-up { from { transform: translateY(100%); }", edit, "the shared rule is untouched")


class CardsStill(Slide):
    theme = None

    def test_classic_opens_and_closes_along_x_with_the_panels_own_timing(self):
        def check(p, cdp):
            tok, o, h, c = self.open_close(p)
            self.assertEqual((o["from"], c["to"]), ("translateY(100%)", "translateY(100%)"), "Cards still rises from the bottom")
            self.assertEqual(h["x"], 0)
            self.assertGreater(h["y"], 0)
        self.run_both(check)

    test_classic_still_under_reduced_motion = None
    test_the_rule_is_in_the_theme_file_only_and_moves_transform_on_x = None

    def test_the_cards_page_style_is_the_one_main_has(self):
        html = page.page_html(branding=page.NO_BRAND, theme=None)
        got = [hashlib.md5(b.encode("utf-8")).hexdigest() for b in re.findall(r"<style[^>]*>(.*?)</style>", html, re.S)]
        self.assertEqual(got, CARDS_STYLE_MD5)
        classic = page.page_html(branding=page.NO_BRAND, theme=NAME)
        self.assertEqual(classic.count("@keyframes ask-up"), html.count("@keyframes ask-up") + 1, "only the Classic page lays the side keyframes")


if __name__ == "__main__":
    unittest.main()

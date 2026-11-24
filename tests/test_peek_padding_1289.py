"""Row 1289 AP7 (PM ruling): Classic peek padding equals the prototype (app.css .pk-top 10px 16px 6px 20px, .pk-scroll 4px 24px 24px), at 1400 and 900;
Classic only (rules-2.css), the shared frame in shell.css is untouched and Cards keeps its own. The toolbar is the .pk-top, the rest the .pk-scroll.
The words box (a foot band the full width of the peek) is pulled out to the peek's edges by a negative margin equal to the 24 px body inset:
it reaches the peek's inner edges and no further, at 1400 and 900.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_peek_padding_1289.py
"""
import json
import re
import unittest

import _testpage as testpage
from _editor_checks import for_url
from _paths import ROOT
from _real_server import real_server
from clark import page, theme
from test_peek_ruled_1077 import ACTION, Peeks
from test_server import chrome, wait
from test_work_items import FIXED_DATE, page_target

T = ROOT / "src" / "clark" / "themes" / "prototype-2.0"
R2 = (T / "rules-2.css").read_text(encoding="utf-8")
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
GEO = """(() => { const p = document.querySelector('#peek'), w = p.querySelector('.wordsbox'), pr = p.getBoundingClientRect(), wr = w.getBoundingClientRect(), c = getComputedStyle(p),
  tb = p.querySelector('.pk-tb'), tbr = tb.getBoundingClientRect(), bd = p.querySelector('.pk-body'), f = p.querySelector('.pk-fields, .pk-title, h2, h3'), fr = f.getBoundingClientRect(), wc = getComputedStyle(w);
  return { padL: c.paddingLeft, padR: c.paddingRight, inL: pr.left + p.clientLeft, inR: pr.left + p.clientLeft + p.clientWidth, boxL: wr.left, boxR: wr.right,
           textL: wr.left + parseFloat(wc.paddingLeft), contentL: fr.left,
           tb: (t => ({ pad: t.paddingTop + ' ' + t.paddingRight + ' ' + t.paddingBottom + ' ' + t.paddingLeft, mb: t.marginBottom, L: tbr.left, R: tbr.right, top: tbr.top }))(getComputedStyle(tb)),
           bodyPad: c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft, bodyL: bd.getBoundingClientRect().left, bodyR: bd.getBoundingClientRect().right, peekTop: pr.top + p.clientTop }; })()"""


class Padding(unittest.TestCase):
    def test_classic_peek_rules_are_the_prototype_values(self):
        self.assertRegex(R2, r"(?m)^\.peek \{ padding: 0 24px 24px; \}")
        self.assertRegex(R2, r"(?m)^\.peek \.pk-tb \{ margin: 0 -24px 4px; padding: 10px 16px 6px 20px; top: 0; \}")

    def test_the_shared_frame_keeps_its_rule(self):
        self.assertIn("padding: var(--space-3) var(--space-5) var(--space-5); }", SHELL)
        self.assertNotIn("padding", " ".join(re.findall(r"(?m)^\.peek \{[^}]*\}", (T / "rules.css").read_text(encoding="utf-8"))))


class WordsBox(Peeks):
    def geo(self, classic, width):
        html = testpage.html()
        if classic:
            html = page.layer_theme(html, theme.css("prototype-2.0"))
        projects = self.store.read("projects")
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: projects, page_html=lambda: html)
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#work&p={self.code}")}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1", 30), "the page drew")
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), "the list drew")
            self.assertEqual(cdp.js("!!document.getElementById('theme')", sid), classic)
            self.open_peek(cdp, sid, ACTION, "item")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations({subtree: true}).every(a => a.playState !== 'running')", sid)))
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid)))
            for _ in range(2):
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "/", "code": "Slash", "windowsVirtualKeyCode": 191}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .wordsbox')", sid)), "two slashes open the box")
            return cdp.js(GEO, sid)

    def test_classic_peek_padding_is_the_prototype_and_words_box_reaches_the_edges_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.geo(True, width)
                # .pk-top: the toolbar, full width of the peek, padding 10px 16px 6px 20px, at the top
                self.assertEqual(g["tb"]["pad"], "10px 16px 6px 20px", g)
                self.assertAlmostEqual(g["tb"]["L"], g["inL"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["tb"]["R"], g["inR"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["tb"]["top"], g["peekTop"], delta=1, msg=str(g))
                # .pk-scroll: 4 above (the toolbar's bottom margin), 24 left and right, 24 below
                self.assertEqual(g["tb"]["mb"], "4px", g)
                self.assertEqual(g["bodyPad"], "0px 24px 24px 24px", g)
                self.assertAlmostEqual(g["bodyL"], g["inL"] + 24, delta=1, msg=str(g))
                self.assertAlmostEqual(g["bodyR"], g["inR"] - 24, delta=1, msg=str(g))
                self.assertAlmostEqual(g["contentL"], g["inL"] + 24, delta=1, msg=str(g))
                # the words box reaches the peek's edges and no further
                self.assertAlmostEqual(g["boxL"], g["inL"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["boxR"], g["inR"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["textL"], g["contentL"], delta=1, msg="the box's words line up with the peek's content: " + str(g))

    def test_cards_words_box_is_unchanged_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.geo(False, width)
                self.assertEqual((g["padL"], g["padR"]), ("24px", "24px"), g)
                self.assertEqual(g["bodyPad"], "12px 24px 24px 24px", g)   # the shared frame, measured on main
                self.assertEqual(g["tb"]["pad"], "12px 0px 12px 0px", g)
                self.assertEqual(g["tb"]["mb"], "0px", g)
                self.assertAlmostEqual(g["boxL"], g["inL"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["boxR"], g["inR"], delta=1, msg=str(g))


if __name__ == "__main__":
    unittest.main()

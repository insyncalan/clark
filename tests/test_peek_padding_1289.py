"""Row 1289: the peek's side padding is 20 px (the final mock-up), Classic only (rules-2.css); the shared frame in shell.css is untouched.
The words box (a foot band the full width of the peek) is pulled out to the peek's edges by a negative margin, so in Classic it is pulled
out by the same 20 px: it reaches the peek's inner edges and no further, at 1400 and 900. Cards keeps its 24 px.
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
  f = p.querySelector('.pk-fields, .pk-title, h2, h3'), fr = f.getBoundingClientRect(), wc = getComputedStyle(w);
  return { padL: c.paddingLeft, padR: c.paddingRight, inL: pr.left + p.clientLeft, inR: pr.left + p.clientLeft + p.clientWidth, boxL: wr.left, boxR: wr.right,
           textL: wr.left + parseFloat(wc.paddingLeft), contentL: fr.left }; })()"""


class Padding(unittest.TestCase):
    def test_classic_peek_side_padding_is_20(self):
        m = re.search(r"(?m)^\.peek \{[^}]*padding:\s*var\(--space-3\) 20px var\(--space-5\);[^}]*\}", R2)
        self.assertTrue(m, "rules-2.css needs .peek { padding: var(--space-3) 20px var(--space-5); }")

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

    def test_classic_words_box_reaches_the_peek_edges_and_no_further_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.geo(True, width)
                self.assertEqual((g["padL"], g["padR"]), ("20px", "20px"), g)
                self.assertAlmostEqual(g["boxL"], g["inL"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["boxR"], g["inR"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["textL"], g["contentL"], delta=1, msg="the box's words line up with the peek's content: " + str(g))

    def test_cards_words_box_is_unchanged_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                g = self.geo(False, width)
                self.assertEqual((g["padL"], g["padR"]), ("24px", "24px"), g)
                self.assertAlmostEqual(g["boxL"], g["inL"], delta=1, msg=str(g))
                self.assertAlmostEqual(g["boxR"], g["inR"], delta=1, msg=str(g))


if __name__ == "__main__":
    unittest.main()

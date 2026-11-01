"""Prototype parity on the Milestones view: C-M5, the Timeline / Calendar switcher shows an icon and a word.

Run: python3 dev/run_tests.py test_milestones_parity
The committed page runs from the real server on the demo database (fixed CLARK_NOW) in headless Chrome (required: it fails, never
skips, without Chrome) at 1400 and 900 px, in light and dark. Laptop widths only. It checks that each switch button shows its icon
and its word, keeps its name, its pressed state and its keys, measures at least 24 px, stays on the screen and clear of the bars
beside it, reads at 4.5:1 or better, and that the choice is still remembered for each place. A published file shows the same
buttons and remembers nothing. Every new string is plain words.
"""
import json
import shutil
import tempfile
import unittest

from _paths import SRC

from clark import page
from test_milestones_page import publish_with_plants
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

SWITCH_WORDS = ["Timeline", "Calendar"]        # the strings C-M5 adds to the page
NEW_STRINGS = list(SWITCH_WORDS)

# Colours go through a canvas, so any colour syntax (rgb, oklch, color-mix) is read as plain sRGB.
SEE = """(() => {
  const px = (c) => { const k = document.createElement('canvas').getContext('2d', {willReadFrequently: true}); k.clearRect(0, 0, 1, 1); k.fillStyle = c; k.fillRect(0, 0, 1, 1); return [...k.getImageData(0, 0, 1, 1).data]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const back = (e) => { for (; e; e = e.parentElement) { const c = px(getComputedStyle(e).backgroundColor); if (c[3] === 255) return c; } return [255, 255, 255, 255]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const sw = document.querySelector('.msv-sw'), s = sw.getBoundingClientRect();
  const bar = document.querySelector('.mv-bar, .cal-bar');
  const clear = [...bar.children].every((e) => { const r = e.getBoundingClientRect(); return !r.width || r.right <= s.left + 0.5 || r.left >= s.right - 0.5 || r.bottom <= s.top + 0.5 || r.top >= s.bottom - 0.5; });
  return {buttons: [...sw.querySelectorAll('button')].map((b) => { const r = b.getBoundingClientRect(), t = b.querySelector('span'), c = getComputedStyle(b);
      return {view: b.dataset.msvb, word: t && t.textContent, svg: !!b.querySelector('svg'), label: b.getAttribute('aria-label'), name: b.textContent.trim(),
              current: b.getAttribute('aria-current'), w: r.width, h: r.height, tag: b.tagName, tab: b.tabIndex, shown: r.width > 0 && getComputedStyle(t).display !== 'none',
              ratio: ratio(px(c.color), back(b)), onScreen: r.left >= 0 && r.right <= window.innerWidth, wordFits: t.scrollWidth <= t.clientWidth + 1}; }),
    clear, group: sw.getAttribute('role') + '|' + sw.getAttribute('aria-label'), noScroll: document.documentElement.scrollWidth <= window.innerWidth};
})()"""


class Switcher(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s.port

    def visit(self, cdp, width, hash_, port=None, ready=".mv-wrap", theme=None):
        port = port or self.serve()
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{ready}')", sid)), "the block drew")
        if theme:
            cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        return sid

    def test_each_switch_shows_its_icon_and_its_word_and_keeps_its_name(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with chrome() as cdp:
                    sid = self.visit(cdp, width, "#milestones&p=TUL", theme=theme)
                    for view in ("line", "cal"):
                        with self.subTest(width=width, theme=theme, view=view):
                            if view == "cal":
                                cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
                                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)))
                            seen = cdp.js(SEE, sid)
                            self.assertEqual(seen["group"], "group|Milestone view")
                            self.assertEqual([b["view"] for b in seen["buttons"]], ["line", "cal"])
                            for b, word in zip(seen["buttons"], SWITCH_WORDS):
                                self.assertEqual((b["tag"], b["word"], b["label"], b["name"]), ("BUTTON", word, word, word), "a real button, named by its word")
                                self.assertTrue(b["svg"] and b["shown"] and b["wordFits"], f"{word}: the icon and the whole word show")
                                self.assertGreaterEqual(min(b["w"], b["h"]), 24, f"{word} is at least 24 px")
                                self.assertEqual(b["tab"], 0, f"{word} is reached with the Tab key")
                                self.assertTrue(b["onScreen"], word)
                                self.assertGreaterEqual(b["ratio"], 4.5, f"{word} reads at 4.5:1")
                            self.assertEqual([b["current"] for b in seen["buttons"]], ["true", "false"] if view == "line" else ["false", "true"])
                            self.assertTrue(seen["clear"], "the switch does not sit over the bar beside it")
                            self.assertTrue(seen["noScroll"], "no page-wide scroll")

    def test_the_choice_is_still_remembered_for_each_place_and_the_keys_work(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port)
            cdp.js("document.querySelector('[data-msvb=cal]').focus()", sid)
            self.assertEqual(cdp.js("document.activeElement.dataset.msvb", sid), "cal", "it takes focus")
            for key, code, text in (("Enter", "Enter", "\r"), (" ", "Space", " ")):
                cdp.js("document.querySelector('[data-msvb=line]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
                cdp.js("document.querySelector('[data-msvb=cal]').focus()", sid)
                for kind in ("keyDown", "keyUp"):
                    cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "text": text if kind == "keyDown" else ""}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)), f"{code} on Calendar opens it")
            self.assertEqual(json.loads(cdp.js("localStorage.getItem('clark.msv.page')", sid)), "cal", "remembered for this place")
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port, ready=".cal")
            self.assertTrue(cdp.js("document.querySelector('[data-msvb=cal]').getAttribute('aria-current') === 'true'", sid), "back on Calendar")
            cdp.js("document.querySelector('[data-msvb=line]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
            self.assertEqual(json.loads(cdp.js("localStorage.getItem('clark.msv.page')", sid)), "line")

    def test_a_published_file_shows_the_same_two_switches_and_remembers_nothing(self):
        demo, folder, path, _ids = publish_with_plants()
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
            self.assertEqual(cdp.js("[...document.querySelectorAll('.msv-sw button')].map(b => b.textContent.trim())", sid), SWITCH_WORDS)
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal')", sid)))
            self.assertIsNone(cdp.js("localStorage.getItem('clark.msv.page')", sid), "a file remembers nothing")

    def test_every_new_string_is_plain_words(self):
        built = (SRC / "clark" / "page" / "page.html").read_text(encoding="utf-8")
        for text in NEW_STRINGS:
            with self.subTest(text=text):
                self.assertIn(text, built, "the string is in the built page")
                self.assertFalse(text.lower().startswith("clark"), "no sentence starts with the product name")
                self.assertNotRegex(text, r"\d|!|[A-Z]{2,}|Error|JSON", "no digits, dates, shouting or code words")        # and, being two plain words each, no names
                self.assertRegex(text, r"^[A-Z][a-z]+( [a-z]+)*$", "plain words")


if __name__ == "__main__":
    unittest.main()

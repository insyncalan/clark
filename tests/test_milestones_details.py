"""Prototype parity on the Milestones view: C-M6, a "Hide milestone details" / "Show milestone details" toggle above the list.

Run: python3 dev/run_tests.py test_milestones_details
The committed page runs from the real server on the demo database (fixed CLARK_NOW) in headless Chrome (required: it fails, never
skips, without Chrome) at 1400 and 900 px, in light and dark. Laptop widths only. It checks that the toggle is a real button with
aria-expanded and a visible label, at least 24 px, reachable by keyboard, readable at 4.5:1; that it starts open (as the prototype
does); that hiding takes the rows and Show all out of sight but never the marks, the switch or the Legend; that the choice is
remembered for each place; and that a published file has no toggle and shows its list as it is. Every new string is plain words.
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



HIDE, SHOW = "Hide milestone details", "Show milestone details"
NEW_STRINGS = [HIDE, SHOW]        # the strings C-M6 adds to the page

# Colours go through a canvas, so any colour syntax (rgb, oklch, color-mix) is read as plain sRGB.
LOOK = """(() => {
  const px = (c) => { const k = document.createElement('canvas').getContext('2d', {willReadFrequently: true}); k.clearRect(0, 0, 1, 1); k.fillStyle = c; k.fillRect(0, 0, 1, 1); return [...k.getImageData(0, 0, 1, 1).data]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const back = (e) => { for (; e; e = e.parentElement) { const c = px(getComputedStyle(e).backgroundColor); if (c[3] === 255) return c; } return [255, 255, 255, 255]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const t = document.querySelector('.msl-det'), r = t.getBoundingClientRect(), row = document.querySelector('.msl-row'), c = getComputedStyle(t);
  return {tag: t.tagName, type: t.type, expanded: t.getAttribute('aria-expanded'), controls: t.getAttribute('aria-controls'), text: t.textContent.trim(),
    svg: !!t.querySelector('svg'), w: r.width, h: r.height, tab: t.tabIndex, ratio: ratio(px(c.color), back(t)), onScreen: r.left >= 0 && r.right <= window.innerWidth,
    above: !row || r.bottom <= row.getBoundingClientRect().top + 1, target: !!document.getElementById(t.getAttribute('aria-controls')),
    noScroll: document.documentElement.scrollWidth <= window.innerWidth};
})()"""
# What stays when the details are hidden, and what goes.
STATE = """(() => {
  const seen = (e) => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden';
  return {rows: [...document.querySelectorAll('.msl-row')].filter(seen).length, all: [...document.querySelectorAll('.msl-all')].filter(seen).length,
    marks: [...document.querySelectorAll('.mv-mk, .cal-ms')].filter(seen).length, legend: seen(document.querySelector('.mlg-b')), sw: seen(document.querySelector('.msv-sw')),
    focusable: [...document.querySelectorAll('.msl-box [tabindex], .msl-box .msl-all')].filter(seen).length, toggle: seen(document.querySelector('.msl-det')),
    label: (document.querySelector('.msl-det') || {}).textContent, expanded: (document.querySelector('.msl-det') || {getAttribute() {}}).getAttribute('aria-expanded')};
})()"""


class Details(unittest.TestCase):
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

    def press(self, cdp, sid, key, code, text):
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "text": text if kind == "keyDown" else ""}, sid)

    def test_the_toggle_is_a_real_button_above_the_list_and_starts_open(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.visit(cdp, width, "#milestones&p=MOSS", theme=theme)
                    look = cdp.js(LOOK, sid)
                    self.assertEqual((look["tag"], look["type"]), ("BUTTON", "button"))
                    self.assertEqual((look["text"], look["expanded"]), (HIDE, "true"), "open to begin with, as the prototype has it")
                    self.assertTrue(look["svg"] and look["target"] and look["above"] and look["onScreen"] and look["noScroll"], look)
                    self.assertGreaterEqual(min(look["w"], look["h"]), 24, "at least 24 px")
                    self.assertEqual(look["tab"], 0, "reached with the Tab key")
                    self.assertGreaterEqual(look["ratio"], 4.5, "reads at 4.5:1")
                    self.assertEqual(cdp.js(STATE, sid)["rows"], 5, "the first five rows show")

    def test_hiding_takes_the_rows_away_and_never_the_marks_the_switch_or_the_legend(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.visit(cdp, width, "#milestones&p=MOSS", theme=theme)
                    for view in ("line", "cal"):
                        cdp.js(f"document.querySelector('[data-msvb={view}]').click()", sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap, .cal')", sid)))
                        before = cdp.js(STATE, sid)
                        self.assertEqual((before["rows"], before["all"]), (5, 1))
                        self.assertGreater(before["marks"], 0)
                        cdp.js("document.querySelector('.msl-det').click()", sid)
                        after = cdp.js(STATE, sid)
                        self.assertEqual((after["label"], after["expanded"]), (SHOW, "false"))
                        self.assertEqual((after["rows"], after["all"], after["focusable"]), (0, 0, 0), "no row, no Show all, nothing to tab to")
                        self.assertEqual((after["marks"], after["legend"], after["sw"], after["toggle"]), (before["marks"], True, True, True),
                                         "the marks, the Legend, the switch and the toggle stay")
                        cdp.js("document.querySelector('.msl-det').click()", sid)
                        again = cdp.js(STATE, sid)
                        self.assertEqual((again["label"], again["expanded"], again["rows"], again["all"]), (HIDE, "true", 5, 1), "Show brings the same list back")

    def test_the_keys_work_and_the_choice_is_remembered_for_the_place(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port)
            self.assertIsNone(cdp.js("localStorage.getItem('clark.msDet.page')", sid), "nothing stored until it is used")
            cdp.js("document.querySelector('.msl-det').focus()", sid)
            self.assertEqual(cdp.js("document.activeElement.className", sid), "msl-det", "it takes focus")
            self.press(cdp, sid, "Enter", "Enter", "\r")
            self.assertTrue(wait(lambda: cdp.js(STATE, sid)["rows"] == 0), "Enter hides")
            self.assertEqual(cdp.js("document.activeElement.className", sid), "msl-det", "focus stays on the toggle")
            self.press(cdp, sid, " ", "Space", " ")
            self.assertTrue(wait(lambda: cdp.js(STATE, sid)["rows"] == 5), "Space shows")
            self.press(cdp, sid, "Enter", "Enter", "\r")
            self.assertTrue(wait(lambda: cdp.js(STATE, sid)["rows"] == 0))
            self.assertIs(json.loads(cdp.js("localStorage.getItem('clark.msDet.page')", sid)), False, "remembered for this place")
            sid = self.visit(cdp, 1400, "#milestones&p=MOSS", port)
            state = cdp.js(STATE, sid)
            self.assertEqual((state["rows"], state["label"], state["expanded"]), (0, SHOW, "false"), "still hidden on the next visit")
            self.assertGreater(state["marks"], 0)
            cdp.js("document.querySelector('.msl-det').click()", sid)
            self.assertTrue(wait(lambda: cdp.js(STATE, sid)["rows"] == 5))
            self.assertIs(json.loads(cdp.js("localStorage.getItem('clark.msDet.page')", sid)), True)
            keys = cdp.js("Object.keys(localStorage).filter(k => /msDet/.test(k))", sid)
            self.assertEqual(keys, ["clark.msDet.page"], "one key for this place, none for another")

    def test_a_published_file_has_no_toggle_and_shows_its_list_as_it_is(self):
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
            state = cdp.js(STATE, sid)
            self.assertEqual(cdp.js("document.querySelectorAll('.msl-det').length", sid), 0, "no toggle")
            self.assertGreater(state["rows"], 0, "the list shows")
            self.assertTrue(state["legend"] and state["sw"])
            self.assertEqual(cdp.js("[...document.querySelectorAll('button')].filter(b => /milestone details/.test(b.textContent)).length", sid), 0)
            cdp.js("localStorage.setItem('clark.msDet.page', 'false')", sid)       # a stored choice from elsewhere changes nothing in a file
            cdp.js("[...document.querySelectorAll('.tab')][0].click()", sid)
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
            self.assertGreater(cdp.js(STATE, sid)["rows"], 0, "still shown")

    def test_every_new_string_is_plain_words(self):
        built = (SRC / "clark" / "page" / "page.html").read_text(encoding="utf-8")
        for text in NEW_STRINGS:
            with self.subTest(text=text):
                self.assertIn(text, built, "the string is in the built page")
                self.assertFalse(text.lower().startswith("clark"), "no sentence starts with the product name")
                self.assertNotRegex(text, r"\d|!|[A-Z]{2,}|Error|JSON", "no digits, dates, shouting or code words")        # and, being plain words, no names
                self.assertRegex(text, r"^[A-Z][a-z]+( [a-z]+)*$", "plain words")


if __name__ == "__main__":
    unittest.main()

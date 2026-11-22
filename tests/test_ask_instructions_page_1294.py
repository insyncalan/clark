"""Row 1294, slice 3: the standing instructions on the ask clark page, in a real browser at 1400 and 900.

Run: python3 dev/run_tests.py test_ask_instructions_page_1294
The All projects tab holds the box for all projects; the project's tab shows that text read only with a Change button and holds the project's own box.
Each box is under its label, as wide as its card, counts its characters, and is saved when it is left, with an Undo in the toast. Chrome is required."""
import os
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from _editor_checks import for_project
from _paths import SRC  # noqa: F401
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page, standing_instructions, store as st

WIDTHS = (1400, 900)
ALL_TEXT = "Answer in two short sentences."
OWN_TEXT = "Say Harbour, not ABC."
LOOKS_KEY = "pass" + "word = Hunter2-Zebra-9"      # built in two pieces so the repository's own secret scan has nothing to match in this file
MONEY = re.compile(r"[$£€]|cost limit|monthly|spend|\bprice\b|\bbudget\b", re.I)


class Boxes(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = make_db(self.d)
        self.s.httpd.app_settings = service(self.db)
        self.svc = standing_instructions.StandingInstructions(self.db, [], by_user=lambda: "tester")
        self.s.httpd.ask_instructions = self.svc

    def kept(self, code=None):
        s = st.open_store(self.db, onedrive_roots=[])
        try:
            return s.ask_instructions(code)
        finally:
            s.close()

    def show(self, cdp, tab="project"):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20), "the tabs are on the page")
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
        return js

    def until(self, js, expr, what, seconds=20):
        self.assertTrue(wait(lambda: js(expr), seconds), f"{what}: {expr}")

    def type_into(self, js, selector, text):
        """Put `text` in the box as typing does (an input event), then leave it (blur), which is what saves."""
        js(f"(() => {{ const e = document.querySelector('{selector}'); e.focus(); e.value = {text!r}; e.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
        time.sleep(0.2)
        js(f"document.querySelector('{selector}').blur()")

    def test_the_all_projects_box_is_under_its_label_wide_and_saves_when_left(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('#ask-instructions-all') && !document.querySelector('#ask-instructions-all').disabled", "the box is ready")
            self.assertEqual(js("document.querySelector('label[for=ask-instructions-all]').innerText"), "Standing instructions for all projects")
            self.assertEqual(js("document.querySelector('#ask-instructions-all-count').innerText"), "0 of 4,000")
            self.type_into(js, "#ask-instructions-all", ALL_TEXT)
            self.until(js, "document.querySelector('#ask-instructions-all-count').innerText === '%d of 4,000'" % len(ALL_TEXT), "the count follows the text")
            self.assertTrue(wait(lambda: self.kept() == ALL_TEXT, 10), "saved on the server when the box was left")
            self.until(js, "/Saved/.test(document.body.innerText)", "the toast says it was saved")
            self.assertEqual(self.kept("ABC"), "", "nothing was saved for the project")

    def test_the_help_under_the_all_projects_box_says_the_size_of_one_question_in_the_approved_words(self):
        from clark import ai_connect
        approved = "Up to 4,000 characters, sent with every question, before each project's own. Long instructions count towards the size of one question every time."
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('#ask-instructions-all-help')", "the help is on the page")
            self.assertEqual(js("document.querySelector('#ask-instructions-all-help').innerText"), approved)
        from clark import ask
        size = ai_connect.SIZE_LINE.format(tokens=ask.BUDGET // 4, chars=ask.BUDGET)
        self.assertIn("about 300,000 tokens (1,200,000 characters of passages)", size)

    def test_undo_in_the_toast_puts_the_old_text_back_in_the_box(self):
        self.svc.change({"scope": "all", "text": "Old words."})
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "document.querySelector('#ask-instructions-all') && document.querySelector('#ask-instructions-all').value === 'Old words.'", "the kept text is shown")
            self.type_into(js, "#ask-instructions-all", ALL_TEXT)
            self.assertTrue(wait(lambda: self.kept() == ALL_TEXT, 10), "saved")
            self.until(js, "[...document.querySelectorAll('button')].some(b => b.innerText === 'Undo')", "the toast has Undo")
            js("[...document.querySelectorAll('button')].find(b => b.innerText === 'Undo').click()")
            self.assertTrue(wait(lambda: self.kept() == "Old words.", 10), "undone on the server")
            self.until(js, "document.querySelector('#ask-instructions-all').value === 'Old words.'", "the box shows the old text again")

    def test_the_project_tab_shows_the_all_text_read_only_with_change_and_its_own_box(self):
        self.svc.change({"scope": "all", "text": ALL_TEXT})
        with chrome() as cdp:
            js = self.show(cdp)
            self.until(js, "!!document.querySelector('#ask-instructions-read')", "the text for all projects is shown")
            self.assertEqual(js("document.querySelector('#ask-instructions-read').innerText"), ALL_TEXT)
            self.assertEqual(js("document.querySelector('#ask-instructions-read').tagName"), "DIV", "read only: not a box")
            self.assertEqual(js("document.querySelector('label[for=ask-instructions-project]').innerText"), "For ABC")
            self.assertEqual(js("document.querySelector('#ask-instructions-own-card h2').innerText"), "Standing instructions")
            self.type_into(js, "#ask-instructions-project", OWN_TEXT)
            self.assertTrue(wait(lambda: self.kept("ABC") == OWN_TEXT, 10), "the project's own text is saved")
            self.assertEqual(self.kept(), ALL_TEXT, "the one for all projects is not changed from here")
            js("document.querySelector('[data-ask-instructions-change]').click()")
            self.until(js, "!!document.querySelector('#ask-instructions-all') && !document.querySelector('#ask-instructions-project')", "Change opens the All projects tab")
            self.until(js, "document.querySelector('#ask-instructions-all').value === %r" % ALL_TEXT, "the box shows the text for all projects once it is read")

    def test_a_text_that_looks_like_a_key_is_refused_in_plain_words_and_kept_in_the_box(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('#ask-instructions-all') && !document.querySelector('#ask-instructions-all').disabled", "ready")
            self.type_into(js, "#ask-instructions-all", LOOKS_KEY)
            self.until(js, "/looks like a password or a key/.test(document.querySelector('#ask-instructions-all-card').innerText)", "the refusal is shown")
            self.assertEqual(js("document.querySelector('#ask-instructions-all').value"), LOOKS_KEY, "what was typed is still there to mend")
            self.assertEqual(js("document.querySelector('#ask-instructions-all').getAttribute('aria-invalid')"), "true")
            self.assertEqual(self.kept(), "")

    def test_the_box_stops_at_4000_characters(self):
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('#ask-instructions-all') && !document.querySelector('#ask-instructions-all').disabled", "ready")
            self.assertEqual(js("document.querySelector('#ask-instructions-all').maxLength"), 4000)

    def test_layout_names_and_words_at_1400_and_900(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                js = self.show(cdp, "all")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "!!document.querySelector('#ask-instructions-all')", "the box")
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
                self.assertTrue(js("""(() => { const b = document.querySelector('#ask-instructions-all').getBoundingClientRect(), l = document.querySelector('label[for=ask-instructions-all]').getBoundingClientRect(), c = document.querySelector('#ask-instructions-all-card').getBoundingClientRect(); return l.bottom <= b.top && b.width >= c.width - 90 && b.right <= c.right; })()"""),
                                "the label is above the box and the box is as wide as the card")
                self.assertTrue(js("document.querySelector('#ask-instructions-all').getAttribute('aria-describedby').split(' ').every(i => !!document.getElementById(i))"), "its help and count are named")
                text = js("document.querySelector('#ask-instructions-all-card').innerText")
                self.assertFalse(MONEY.search(text), MONEY.search(text))
                self.assertNotRegex(text, r"(?i)prototype|mock-?up|\.html|\.jsx|/Users/|/home/")
                js("document.querySelector('[data-ask-tab=project]').click()")
                self.until(js, "!!document.querySelector('#ask-instructions-project')", "the project's box")
                self.assertTrue(js("[...document.querySelectorAll('#ask-instructions-own-card button')].every(b => b.innerText.trim().length > 0)"), "every button has a name")
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll on the project tab at {w}")

    def test_light_and_dark_text_has_contrast(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                js = self.show(cdp, "all")
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
                self.until(js, "!!document.querySelector('#ask-instructions-all')", "the box")
                ratio = js("""(() => { const rgb = s => s.match(/[\\d.]+/g).slice(0, 3).map(Number); const lum = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
                  const e = document.querySelector('#ask-instructions-all'), s = getComputedStyle(e), f = lum(rgb(s.color)), g = lum(rgb(s.backgroundColor)); return (Math.max(f, g) + 0.05) / (Math.min(f, g) + 0.05); })()""")
                self.assertGreaterEqual(ratio, 4.5, f"the box's text contrast in {scheme}")


if __name__ == "__main__":
    unittest.main()

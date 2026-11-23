"""Tech debt 1572 (parent row 1295), acceptance points 10, 11 and 13 of the slash commands editor, in Chrome in Classic, against the real server with a FAKE provider.

Run: python3 dev/run_tests.py test_slash_gaps_1572
AP10: Write it sends the person's own words and one fixed instruction, never project data (what the page posts and what the provider receives). AP11: one Undo step restores one
change, and a second Undo has nothing to undo. AP13: the whole editor reads in light and dark at 1400 and 900 (contrast measured from the computed styles). Chrome is required."""
import json
import re
import time

from test_dark_primary import MEASURE
from test_page import DATA, navigate
from test_server import chrome
from test_slash_ai_1295 import AiBase, MENU
from test_slash_editor_1295 import EDITOR

PROJECT_DATA = ["Example Programme", "Pilot live", "Agree the cut-over plan", "ABC-M-001", "ABC-A-001"]
BODY_KEYS = ["instruction", "option", "place", "text"]
SPY = """(() => { window.__posts = []; const f = window.fetch; window.fetch = function (u, o) {
  if (String(u).indexOf('/api/ai/suggest') >= 0) window.__posts.push(String(o && o.body)); return f.apply(this, arguments); }; })()"""


class NoProjectData(AiBase):
    def test_write_it_posts_the_instructions_and_one_fixed_task_and_nothing_of_the_project(self):
        for word in PROJECT_DATA:
            self.assertIn(word, json.dumps(DATA["ABC"]), "the project the editor is opened on really holds this")
        with chrome() as cdp:
            js = self.new_form(cdp)
            js(SPY)
            self.type_into(js, "#sl-text", "Tell me who owns {item}. Today is {today}.")
            self.click(js, "#slash-ai-write")
            self.until(js, f"document.querySelector('#sl-menu').value === {MENU!r}", "the menu line is written")
            posts = js("window.__posts")
            self.assertEqual(len(posts), 1)
            body = json.loads(posts[0])
            self.assertEqual(sorted(body), BODY_KEYS)                      # no project, no passages, no ids
            self.assertEqual(body["text"], "Tell me who owns {item}. Today is {today}.")
            self.assertEqual(len(self.provider.requests), 1)
            got = self.provider.requests[0]
            self.assertEqual(got.passages, ())                             # no passage of the project goes to the provider
            for word in PROJECT_DATA:
                self.assertNotIn(word, got.text)
                self.assertNotIn(word, got.system)
            self.assertIn("Tell me who owns {item}. Today is {today}.", got.text)


class OneUndo(AiBase):
    def test_one_undo_restores_one_change_and_a_second_undo_has_nothing_left(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Please list everything that is overdue, grouped by owner, oldest first")
            self.click(js, "#slash-ai-shorter")
            self.until(js, "document.querySelector('#sl-text').value === 'Overdue by owner'", "change one: shorter")
            self.done(js)
            self.click(js, "#slash-ai-clearer")
            self.until(js, "document.querySelector('#sl-text').value.includes('Dates as DD-MM-YYYY')", "change two: clearer")
            self.done(js)
            self.click(js, "#slash-ai-undo")
            self.until(js, "document.querySelector('#sl-text').value === 'Overdue by owner'", "one Undo gives back change two only")
            self.assertEqual(js("document.querySelectorAll('#slash-ai-undo').length"), 0, "no second Undo step is offered")
            self.assertTrue(self.val(js, "#sl-text").startswith("Overdue"), "change one stays")

    def test_removing_a_command_is_one_undo_that_brings_back_one_command(self):
        svc = self.s.httpd.ask_commands
        rec = {"menu": "Line", "text": "Overdue by owner", "scope": "anywhere", "result": "answer"}
        svc.change({"scope": "project", "project": "ABC", "action": "save", "record": {**rec, "name": "monday"}})
        svc.change({"scope": "project", "project": "ABC", "action": "save", "record": {**rec, "name": "friday"}})
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&name=monday")
            self.until(js, "!!document.querySelector('#slash-remove')", "monday is open")
            self.click(js, "#slash-remove")
            self.until(js, "!!document.querySelector('#slash-undo')", "Undo is offered")
            self.assertEqual(self.files("ABC"), ["friday.json"])
            self.click(js, "#slash-undo")
            self.until(js, "!!document.querySelector('.slash-side [data-pick=monday]')", "monday is back")
            self.assertEqual(self.files("ABC"), ["friday.json", "monday.json"])
            self.assertEqual(js("document.querySelectorAll('#slash-undo').length"), 0, "a second Undo has nothing to undo")


class LightAndDark(AiBase):
    PARTS = ["#slash-page", ".slash-side h2", ".slash-side button", "#sl-name", "#sl-menu", "#sl-text", "#slash-ai-write", "#slash-ai-describe"]

    def test_the_editor_reads_in_light_and_dark_at_1400_and_900(self):
        seen = {}
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = navigate(cdp, self.s.port, "")
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}{EDITOR}&new=1"}, sid)
                    js = lambda e: cdp.js(e, sid)          # noqa: E731
                    self.until(js, "!!document.querySelector('#slash-ai-write') && !!document.querySelector('.slash-side button')", "the editor is on the page", 30)
                    self.ready(js)
                    js(f"document.documentElement.setAttribute('data-theme', {scheme!r})")
                    time.sleep(0.4)                                # the theme's colour transition
                    self.assertFalse(js("document.querySelector('#slash-ai-write').disabled"), "the buttons are measured enabled")
                    measure = js(f"(window.__m = {MEASURE}, 1)")
                    for sel in self.PARTS:
                        r = js(f"window.__m({sel!r})")
                        self.assertGreaterEqual(r["text"], 4.5, f"{sel} text on its fill, {scheme}, {width}")
                    seen[(width, scheme)] = js("getComputedStyle(document.querySelector('#slash-page')).backgroundColor + '|' + getComputedStyle(document.querySelector('#sl-text')).color")
                    self.assertFalse(re.search(r"#[0-9a-f]{3,6}\b", str(measure)), "no pin")
        for width in (1400, 900):
            if len(seen) == 4:
                self.assertNotEqual(seen[(width, "light")], seen[(width, "dark")], "the editor follows the theme tokens")

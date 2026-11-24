"""Row 1572 AP3 (row 1295 AP10): while the AI writes a slash command, no project data goes: every request to the AI route has exactly the four keys option, place, text and instruction.

Run: python3 dev/run_tests.py test_slash_nodata_1295
The page's own requests are recorded in the browser (fetch), so the check sees the body as sent, for all five buttons, at 1400 and 900. Chrome is required: fails, never skips."""
import json

from test_server import chrome, wait
from test_slash_ai_1295 import AiBase, EDITOR
from test_slash_editor_1295 import EditorStates

TITLES = ("Pilot live", "Agree the cut-over plan", "Example Programme")
RECORD = """(() => { window.__sent = []; const f = window.fetch.bind(window);
  window.fetch = (u, o) => { if (String(u).includes('/api/ai/suggest')) window.__sent.push(String((o && o.body) || '')); return f(u, o); }; })()"""


class SlashNoData(AiBase):
    def test_no_project_data_goes_to_the_ai_route_while_writing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                js = EditorStates.open_at(self, cdp, width, False, EDITOR + "&new=1")
                self.ready(js)
                js(RECORD)
                self.type_into(js, "#slash-ai-describe-in", "Overdue by owner sentence")
                for button in ("#slash-ai-describe", "#slash-ai-write", "#slash-ai-clearer", "#slash-ai-shorter", "#slash-check-run"):
                    before = js("window.__sent.length")
                    self.type_into(js, "#sl-text", "Overdue by owner")
                    self.click(js, button)
                    self.until(js, f"window.__sent.length > {before}", button)
                    self.done(js)
                bodies = [json.loads(b) for b in js("window.__sent")]
                self.assertEqual(len(bodies), 5)
                for body in bodies:
                    self.assertEqual(sorted(body), ["instruction", "option", "place", "text"])
                    for title in TITLES:
                        self.assertNotIn(title, json.dumps(body))
                self.assertEqual({b["text"] for b in bodies}, {"Overdue by owner", "Overdue by owner sentence"})

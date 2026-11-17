"""Row 1251, slice 1: Edit draws the starting text of an empty template part; View never does.
Run: python3 dev/run_tests.py test_starting_text_1251_page
Needs Chrome (the harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

from _demo import USER
from test_report_editor import Base
from test_server import chrome

# type, title, the words Edit shows somewhere in the section (text, placeholder or a field's empty line)
CASES = [
    ("text", "Fictional plain", ["Write here."]),
    ("text", "Header", ["Say where the project stands."]),
    ("textimage", "Fictional ti", ["Write here.", "Add a picture.", "Say what the picture shows."]),
    ("gallery", "Fictional gal", ["Add a picture.", None]),
    ("imagecap", "Fictional cap", ["Add a picture.", None]),
    ("quote", "Fictional quote", ["Write what they said.", "Say who said it."]),
    ("callout", "Fictional callout", ["Write the one thing the reader must see."]),
    ("contacts", "Fictional contacts", ["Add a person."]),
    ("onedoc", "Fictional doc", ["Add the file."]),
    # slice 2
    ("figures4", "Fictional fig4", ["Pick what each number shows."]),
    ("figures3", "Fictional fig3", ["Pick what each number shows."]),
    ("table", "Fictional table", ["Add the first row."]),
    ("raid3", "Fictional raid3", ["Choose the items to show."]),
    ("raid4", "Fictional raid4", ["Choose the items to show."]),
    ("workitems", "Fictional wi", ["Set a filter to choose the rows.", "Say what the list shows."]),
    ("doclinks", "Fictional dl", ["Add a file or a link."]),
    ("checklist", "Fictional check", ["Link the work items to tick off."]),
    ("linkcard", "Fictional link", ["Paste the link.", "Write what the reader will find there."]),
    ("keydates", "Fictional kd", ["No milestones to show yet."]),
    ("gantt", "Fictional gantt", ["No Gantt lines in the client view yet."]),
    ("gantttable", "Fictional gt", ["No Gantt lines in the client view yet."]),
]
ALL = sorted({w for _, _, ws in CASES for w in ws if w})
SEEN = "(function(sel){var s=document.querySelector(sel);if(!s)return null;var t=s.innerText+'\\n';s.querySelectorAll('[placeholder]').forEach(function(e){t+=e.getAttribute('placeholder')+'\\n'});return t})"


class Page(Base):
    def make(self, typ, title):
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": typ, "title": title, "sort_order": 999 + len(title)})

    def test_edit_draws_the_words_and_view_draws_none_of_them(self):
        refs = [(self.make(t, ti), ws) for t, ti, ws in CASES]
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for ref, ws in refs:
                sel = f"[data-id={json.dumps(ref)}]"
                p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
                text = p.js(f"{SEEN}({json.dumps(sel)})")
                for w in ws:
                    if w:
                        self.assertIn(w, text, f"{ref}: {w}")
            p.view()
            body = p.js("document.body.innerText + [...document.querySelectorAll('[placeholder]')].map(e => e.placeholder).join('\\n')")
            for w in ALL:
                self.assertNotIn(w, body, f"View shows {w!r}")

    def test_plan_summary_prompts_sit_under_the_empty_paragraph_and_list_item(self):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Plan summary", "sort_order": 1999,
                                                "body": "<h2>Where we are</h2><p></p><h2>What is next</h2><ul><li></li></ul>"})
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector({json.dumps(sel)})", "the section is drawn")
            got = p.js("(function(s){var r=document.querySelector(s);return JSON.stringify([...r.querySelectorAll('[data-tpl-prompt]')].map(function(e){return [e.tagName,e.getAttribute('data-tpl-prompt'),e.textContent]}))})(" + json.dumps(sel) + ")")
            self.assertEqual(json.loads(got), [["P", "paragraph", "Write here."], ["LI", "item", "Add a step."]])
            p.view()
            body = p.js("document.body.innerText")
            self.assertNotIn("Add a step.", body)


if __name__ == "__main__":
    unittest.main()

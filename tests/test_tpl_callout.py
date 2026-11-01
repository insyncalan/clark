"""#96 G5, Callout: the content rules (section_kinds/callout.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_callout
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n

GOOD = {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": ["Fictional words about the budget.", "A second fictional line."]}
HOSTILE = {"v": 1, "tone": "warning", "title": n.HOSTILE, "paras": [n.HOSTILE]}


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "callout", GOOD, "Fictional words about the budget.", HOSTILE
    LIMIT_BODY = {"v": 1, "title": "x" * 121}
    BAD = ({"v": 1, "tone": "loud"}, {"v": 1, "title": 5}, {"v": 1, "paras": "one"}, {"v": 1, "paras": [{"a": 1}]},
           {"v": 1, "paras": ["x"] * 7}, {"v": 1, "paras": ["x" * 601]})

    def test_the_tone_and_empty_paragraphs(self):
        ref = self.section()
        self.write(ref, {"v": 1, "title": "Fictional", "paras": ["", "  ", "Kept"]})
        self.assertEqual(json.loads(self.stored(ref)), {"paras": ["Kept"], "title": "Fictional", "tone": "info", "v": 1})

    def test_a_tone_alone_is_not_content(self):
        ref = self.section()
        self.write(ref, {"v": 1, "tone": "warning"})
        self.assertNotIn(ref, self.file_sections())


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "callout", GOOD, HOSTILE
    SHOWS = ("Decision needed", "Fictional decision", "Fictional words about the budget.", "A second fictional line.")
    FIELD, TYPED = "Callout title", "Fictional new title"
    CHANGED = lambda self, body: json.loads(body)["title"] == "Fictional new title"

    def test_the_tone_is_a_word_and_not_colour_alone(self):
        from test_server import chrome
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout-tone').textContent"), "Decision needed")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout').getAttribute('role')"), "note")


if __name__ == "__main__":
    unittest.main()

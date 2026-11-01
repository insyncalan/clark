"""#96 G5, Callout: the content rules (section_kinds/callout.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_callout
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from test_server import chrome

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
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout-tone').textContent"), "Decision needed")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-callout').getAttribute('role')"), "note")

    def test_two_quick_saves_both_keep_their_words(self):
        ref = self.make(self.GOOD)
        n.slow_saves(self)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!{n.field_js(ref, 'Callout words')}", "the fields")
            n.fill(p, n.field_js(ref, "Callout title"), "Fictional first title")
            n.fill(p, n.field_js(ref, "Callout words"), "Fictional second words")       # the first save has not landed yet
            from test_server import wait
            self.assertTrue(wait(lambda: json.loads(self.body_of(ref)).get("paras") == ["Fictional second words"], 10), self.body_of(ref))
            got = json.loads(self.body_of(ref))
            self.assertEqual(got["title"], "Fictional first title", "the second save kept the first one's words")

    def test_a_refused_save_puts_the_saved_words_back_and_the_page_says_what_to_do(self):
        ref = self.make(self.GOOD)
        before = self.body_of(ref)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!{n.field_js(ref, 'Callout title')}", "the fields")
            n.fill(p, n.field_js(ref, "Callout title"), "bad\u202ewords")                  # an invisible direction mark: the store refuses it
            p.until("!!document.querySelector('.toast')", "the page said something")
            p.until(f"{n.field_js(ref, 'Callout title')}.value === 'Fictional decision'", "the saved title is back in the field")
            self.assertEqual(self.body_of(ref), before)
            self.assertTrue(p.toast().endswith((".", "?")), p.toast())


if __name__ == "__main__":
    unittest.main()

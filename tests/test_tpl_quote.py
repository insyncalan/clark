"""#96 G5, Quote: the content rules (section_kinds/quote.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_quote
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from test_server import chrome

GOOD = {"v": 1, "quote": "Fictional words of thanks.", "by": "Sam Example", "role": "Fictional sponsor"}
HOSTILE = {"v": 1, "quote": n.HOSTILE, "by": n.HOSTILE, "role": n.HOSTILE}


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "quote", GOOD, "Fictional words of thanks.", HOSTILE
    LIMIT_BODY = {"v": 1, "quote": "x" * 601}
    BAD = ({"v": 1, "quote": 5}, {"v": 1, "by": ["a"]}, {"v": 1, "role": "x" * 121}, {"v": 1, "by": "x" * 121})

    def test_who_said_it_alone_is_not_a_quote(self):
        ref = self.section()
        self.write(ref, {"v": 1, "by": "Sam Example"})
        self.assertNotIn(ref, self.file_sections())


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "quote", GOOD, HOSTILE
    SHOWS = ("Fictional words of thanks.", "Sam Example, Fictional sponsor")
    FIELD, TYPED = "Quote words", "Fictional new words"
    CHANGED = lambda self, body: json.loads(body)["quote"] == "Fictional new words"

    def test_the_quote_is_a_blockquote_with_who_said_it_under_it(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            base = f"[data-id={json.dumps(ref)}]"
            self.assertEqual(p.js(f"document.querySelector('{base} blockquote').textContent"), "Fictional words of thanks.")
            self.assertEqual(p.js(f"document.querySelector('{base} figcaption').textContent"), "Sam Example, Fictional sponsor")


if __name__ == "__main__":
    unittest.main()

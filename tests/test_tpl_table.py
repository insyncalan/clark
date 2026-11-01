"""#96 G5, Table: the content rules (section_kinds/table.py), the file, and the page's View and Edit parts.
Run: python3 dev/run_tests.py test_tpl_table
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import unittest

import _tpl_notes as n
from test_server import chrome

GOOD = {"v": 1, "cols": ["Item", "Owner"], "rows": [["Fictional scope", "Sam Example"], ["Fictional budget", "Alex Example"]], "caption": "Fictional table."}
HOSTILE = {"v": 1, "cols": [n.HOSTILE, "B"], "rows": [[n.HOSTILE, n.HOSTILE]], "caption": n.HOSTILE}


class Data(n.DataChecks):
    TYPE, GOOD, WORDS, HOSTILE_BODY = "table", GOOD, "Fictional scope", HOSTILE
    LIMIT_BODY = {"v": 1, "cols": ["A"], "rows": [["x" * 201]]}
    BAD = ({"v": 1, "cols": "A"}, {"v": 1, "cols": ["A"], "rows": "x"}, {"v": 1, "cols": ["A"], "rows": ["x"]},
           {"v": 1, "cols": ["A"], "rows": [["a", "b"]]}, {"v": 1, "cols": [str(i) for i in range(9)]}, {"v": 1, "cols": ["A"], "rows": [["a"]] * 31},
           {"v": 1, "rows": [["a"]]}, {"v": 1, "cols": [5]}, {"v": 1, "cols": ["A"], "caption": "x" * 201})

    def test_a_short_row_is_padded_and_a_blank_row_is_kept_in_the_store_but_not_in_the_file(self):
        ref = self.section()
        self.write(ref, {"v": 1, "cols": ["A", "B"], "rows": [["one"], ["", ""], ["x", "y"]]})
        self.assertEqual(json.loads(self.stored(ref))["rows"], [["one", ""], ["", ""], ["x", "y"]])
        self.assertEqual(self.file_sections()[ref]["content"]["rows"], [["one", ""], ["x", "y"]])

    def test_headings_alone_are_content_and_blank_cells_alone_are_not(self):
        ref = self.section()
        self.write(ref, {"v": 1, "cols": ["", ""], "rows": [["", ""]], "caption": "Only a caption"})
        self.assertNotIn(ref, self.file_sections())
        self.write(ref, {"v": 1, "cols": ["A", ""], "rows": []})
        self.assertIn(ref, self.file_sections())


class Page(n.PageChecks):
    TYPE, GOOD, HOSTILE_BODY = "table", GOOD, HOSTILE
    SHOWS = ("Item", "Owner", "Fictional scope", "Alex Example", "Fictional table.")
    FIELD, TYPED = "Row 1 column 1", "Fictional changed scope"
    CHANGED = lambda self, body: json.loads(body)["rows"][0][0] == "Fictional changed scope"

    def test_view_draws_a_real_table_with_column_headings(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            base = f"[data-id={json.dumps(ref)}]"
            self.assertEqual(p.js(f"[...document.querySelectorAll('{base} th[scope=col]')].map(e => e.textContent)"), ["Item", "Owner"])
            self.assertEqual(p.js(f"document.querySelectorAll('{base} tbody tr').length"), 2)

    def test_a_new_table_starts_with_two_columns_and_nothing_is_saved_until_it_has_words(self):
        ref = self.make(None)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            base = f"[data-id={json.dumps(ref)}]"
            p.until(f"document.querySelectorAll('{base} th[scope=col] input').length === 2", "two columns")
            p.js("[...document.querySelectorAll('" + base + " .btn')].find(b => b.textContent === 'Add a row').click()")
            self.assertEqual(self.body_of(ref), "")
            n.fill(p, n.field_js(ref, "Column 1 heading"), "Fictional heading")
            p.saved()
            self.assertEqual(json.loads(self.body_of(ref))["cols"], ["Fictional heading", ""])

    def test_add_a_column_and_a_row_each_one_step(self):
        ref = self.make(self.GOOD)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            base = f"[data-id={json.dumps(ref)}]"
            p.until(f"document.querySelectorAll('{base} tbody tr').length === 2", "the rows")
            p.js("[...document.querySelectorAll('" + base + " .btn')].find(b => b.textContent === 'Add a column').click()")
            p.saved()
            self.assertEqual(len(json.loads(self.body_of(ref))["cols"]), 3)
            self.assertTrue(all(len(r) == 3 for r in json.loads(self.body_of(ref))["rows"]))
            p.clear_toast()
            p.js("[...document.querySelectorAll('" + base + " .btn')].find(b => b.textContent === 'Add a row').click()")
            p.saved()
            self.assertEqual(len(json.loads(self.body_of(ref))["rows"]), 3)


if __name__ == "__main__":
    unittest.main()

"""Row 1060: no HTML in an Excel cell. Every rich field that reaches a cell (Latest update, milestone Description and Internal note,
a use case's Where it stands, and the History sheet's old and new values) shows its words, never its markup. Fictional data only.

Run: python3 dev/run_tests.py test_excel_plain_1060
"""
import unittest

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)

from clark import excel, history

HOSTILE = {
    "nested": ("<p>one <strong>two <em>three</em></strong></p>", "one two three"),
    "entities": ("<p>300 pilots &amp; 2 &lt;b&gt; &quot;x&quot;</p>", '300 pilots & 2 <b> "x"'),
    "script": ("<p>safe</p><script>alert(1)</script>", "safe"),
    "empty_p": ("<p></p><p>kept</p><p><br></p>", "kept"),
    "list": ("<ul><li>a</li><li>b</li></ul>", "a\nb"),
    "link": ('<p>see <a href="https://example.com/x">the plan</a></p>', "see the plan"),
}
NOT_MARKUP = ("<p", "</", "<ul", "<li", "<a ", "<strong", "<script", "&amp;", "&lt;")


def _cells(wb, sheet):
    return [c.value for row in wb[sheet].iter_rows() for c in row if isinstance(c.value, str)]


class ExcelPlainWords(unittest.TestCase):
    def _book(self, html):
        rows = {
            "actions": [{"id": "a1", "description": "act", "latest_update": html}],
            "milestones": [{"id": "m1", "name": "ms", "description": html, "internal_note": html, "status": "Planned"}],
            "use_cases": [{"id": "u1", "title": "uc", "headline": "h", "standing": html, "status": "Planned"}],
        }
        return excel.workbook("Demo", rows, on="2030-06-01")

    def test_each_rich_field_is_its_words_in_the_cell(self):
        want = (("Actions", "Latest update"), ("Milestones", "Description"), ("Milestones", "Internal note"), ("Use cases", "Where it stands"))
        for name, (html, words) in HOSTILE.items():
            wb = self._book(html)
            for sheet, label in want:
                with self.subTest(name=name, sheet=sheet, column=label):
                    ws = wb[sheet]
                    col = [c.value for c in ws[1]].index(label) + 1
                    self.assertEqual(ws.cell(row=2, column=col).value, words)

    def test_use_case_standing_is_in_the_rich_words_list(self):
        self.assertIn(("use_cases", "standing"), excel.RICH_WORDS)

    def test_history_values_are_words(self):
        for name, (html, words) in HOSTILE.items():
            for table, field in (("actions", "latest_update"), ("milestones", "description"), ("milestones", "internal_note"),
                                 ("projects", "current_state"), ("projects", "health_reason"), ("use_cases", "standing")):
                with self.subTest(name=name, field=field):
                    shown = history.shown_value(table, field, html)
                    self.assertEqual(shown, words)
                    cell = excel.history_cell(shown)
                    self.assertFalse(any(b in cell for b in NOT_MARKUP[:7]))


if __name__ == "__main__":
    unittest.main()

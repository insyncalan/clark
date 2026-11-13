"""Row 875: the Use cases sheet exports no Owner column, but a column named owner added by hand is read. Its text goes through the checks
the change route makes on a use case's owner (plain one line, 200 characters): hidden characters or a long text refuse the row with the
usual per-row message; a normal owner text still imports."""
import unittest

import _workbook as wbk
from test_excel_import import ImportCase


class UseCaseOwnerColumn(ImportCase):
    def with_owner(self, text):
        wbk.edit(self.path, "Use cases", self.demo.use_case, owner=text)       # the test workbook has the column; the real export leaves it out
        return self.plan()

    def refused(self, p):
        self.assertEqual([c for c in p.changes if c.after.get("owner")], [])
        self.assertTrue(any("Owner must be plain text" in x.message and "the row was left out" in x.message for x in p.problems), p.problems)

    def test_hidden_characters_are_refused_like_the_change_route_does(self):
        for text in ("Sam\u202eExample", "Sam\u200bExample"):
            self.refused(self.with_owner(text))

    def test_a_long_owner_text_is_refused(self):
        self.refused(self.with_owner("a" * 201))

    def test_a_normal_owner_text_is_read(self):
        p = self.with_owner("Sam Example")
        (c,) = p.changes
        self.assertEqual((c.table, c.after.get("owner")), ("use_cases", "Sam Example"))


if __name__ == "__main__":
    unittest.main()

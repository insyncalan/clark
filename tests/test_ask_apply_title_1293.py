"""Row 1293, test 40: a change with no current_title is refused; a made-up ID is refused. Real ask_apply, nothing mocked.

Run: python3 dev/run_tests.py test_ask_apply_title_1293
The check is in AskApply.check_data (guarded ask path). Fictional data only.
"""
import unittest

from _demo import USER
from test_ask_apply import Base

TITLE = "Draft the cut-over plan"


class NoTitle(Base):
    def refused_no_title(self, change):
        body = self.refused(change, "no_title")
        self.assertEqual(body["message"], ask_apply_words().NOT_A_CHANGE)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")
        return body

    def test_a_change_with_no_current_title_is_refused_and_nothing_is_saved(self):
        self.refused_no_title({"op": "change", "id": self.action, "status": "Closed"})

    def test_a_change_with_a_null_title_is_refused(self):
        self.refused_no_title({"op": "change", "id": self.action, "current_title": None, "status": "Closed"})

    def test_a_change_with_an_empty_or_blank_title_is_refused(self):
        for blank in ("", " ", "  \t ", "\n", "<p></p>", "<p> </p>"):
            with self.subTest(title=blank):
                self.refused_no_title({"op": "change", "id": self.action, "current_title": blank, "status": "Closed"})

    def test_an_owner_alone_does_not_stand_in_for_the_title(self):
        self.refused_no_title({"op": "change", "id": self.action, "current_owner": "Sam Lee", "status": "Closed"})

    def test_the_title_under_another_key_does_not_count(self):
        for key in ("title", "Current_Title", "currentTitle", "current_owner_title"):
            with self.subTest(key=key):
                body = self.ask.plan("ABC", {"op": "change", "id": self.action, key: TITLE, "status": "Closed"})[1]
                self.assertFalse(body["ok"])
                self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_a_non_text_title_is_refused(self):
        for bad in (5, True, ["x"], {"a": 1}):
            with self.subTest(title=bad):
                self.refused({"op": "change", "id": self.action, "current_title": bad, "status": "Closed"}, "not_a_change")

    def test_with_the_right_title_the_change_goes_through(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": TITLE, "status": "Closed"})
        self.applied(plan["offer"])
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Closed")

    def test_every_kind_of_item_needs_the_title(self):
        ms = self.demo.milestone
        self.refused({"op": "change", "id": ms, "status": "Done"}, "no_title")
        self.refused({"op": "change", "id": self.demo.use_case, "status": "Flag"}, "no_title")

    def test_a_title_for_another_item_is_still_a_wrong_title(self):
        self.refused({"op": "change", "id": self.action, "current_title": "Pay the supplier", "status": "Closed"}, "wrong_title")


class MadeUpId(Base):
    def test_a_made_up_id_with_or_without_a_title_is_refused_as_unknown(self):
        for claim in ({}, {"current_title": TITLE}, {"current_title": ""}):
            with self.subTest(claim=claim):
                self.refused({"op": "change", "id": "ABC-A-099", "status": "Closed", **claim}, "unknown_id")

    def test_an_archived_item_is_refused_as_unknown_before_the_title_is_looked_at(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.action)
        self.refused({"op": "change", "id": self.action, "status": "Closed"}, "unknown_id")

    def test_another_projects_item_is_refused_before_the_title_is_looked_at(self):
        self.refused({"op": "change", "id": self.other, "current_title": "Order the badges", "status": "Closed"}, "other_project")


def ask_apply_words():
    from clark import ask_apply
    return ask_apply


if __name__ == "__main__":
    unittest.main()

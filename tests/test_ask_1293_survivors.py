"""Row 1293, the cases a mutation sweep of the PR found no test for: the reply cut by one character, the cut flag on an unreadable
reply, every plain field name, a new milestone's duplicate warning, a blank title, and owners inside one reply.

Run: python3 dev/run_tests.py test_ask_1293_survivors
Fictional data only.
"""
import unittest
from unittest import mock

from _demo import USER
from test_ask_apply import Base as ApplyBase
from clark import ask, ask_apply, ask_words

TITLE = "Draft the cut-over plan"


class ReplyCut(unittest.TestCase):
    def test_the_last_character_inside_the_limit_is_kept(self):
        text = "x" * (ask.MAX_REPLY - 1) + "Z"
        got = ask.read_reply(text)
        self.assertEqual(len(got.answer), ask.MAX_REPLY)
        self.assertTrue(got.answer.endswith("Z"))
        self.assertFalse(got.reply_cut)

    def test_an_unreadable_reply_over_the_limit_still_says_it_was_cut(self):
        got = ask.read_reply("CITE: not an id!\n" + "x" * (ask.MAX_REPLY + 1))
        self.assertFalse(got.parsed)
        self.assertTrue(got.reply_cut)
        self.assertFalse(ask.read_reply("CITE: not an id!\nshort").reply_cut)


class FieldNames(unittest.TestCase):
    def test_every_column_has_its_plain_words(self):
        want = {"description": "title", "decision": "title", "name": "title", "due_date": "due date", "made_by": "owner",
                "baseline_date": "agreed date", "forecast_date": "forecast date", "actual_date": "achieved date",
                "needed_by": "needed by", "headline": "headline", "standing": "where it stands"}
        for column, words in want.items():
            self.assertEqual(ask_words.field_name(column), words, column)
            self.assertIn(f"{words} changed when", ask_words.stale(column), column)


class NewItems(ApplyBase):
    def said(self, change):
        return self.planned(change).get("duplicate")

    def test_a_new_milestone_with_the_title_of_a_stored_one_is_warned_about(self):
        got = self.said({"op": "new", "kind": "milestone", "title": "pilot  LIVE"})
        self.assertEqual(got, 'There is already a milestone called "pilot LIVE". Apply to add another.')
        self.assertIsNone(self.said({"op": "new", "kind": "milestone", "title": "Pilot live again"}))

    def test_a_new_decision_with_the_title_of_a_stored_one_is_warned_about_with_a(self):
        with self.s.step("dashboard", USER) as st:
            st.create("decisions", {"project": "ABC", "decision": "Use the shared drive", "status": "Pending", "source": "demo"})
        got = self.said({"op": "new", "kind": "decision", "title": "use the SHARED drive"})
        self.assertEqual(got, 'There is already a decision called "use the SHARED drive". Apply to add another.')

    def test_two_new_items_of_one_reply_with_two_owners_are_not_duplicates(self):
        one = {"op": "new", "kind": "risk", "title": "Supplier may slip", "owner": "Kit Moss"}
        two = dict(one, owner="Sam Lee")
        plans = self.ask.plan_all("ABC", [one, two, dict(one, owner="kit  MOSS")])[1]["plans"]
        self.assertNotIn("duplicate", plans[1])
        self.assertIn("duplicate", plans[2])

    def test_a_blank_title_has_no_duplicate(self):
        self.demo.action(description="<p> </p>")
        for title in ("<p> </p>", "&nbsp;"):
            status, body = self.ask.plan("ABC", {"op": "new", "kind": "action", "title": title})
            self.assertNotIn("duplicate", body, (title, body))

    def test_a_stored_item_with_no_owner_matches_any_owner(self):
        self.demo.action(owner="TBC", description="Ring the supplier")
        self.assertIsNotNone(self.said({"op": "new", "kind": "action", "title": "Ring the supplier", "owner": "Kit Moss"}))

    def test_an_earlier_new_item_with_no_owner_matches_any_owner(self):
        one = {"op": "new", "kind": "action", "title": "Ring the supplier"}
        two = dict(one, owner="Kit Moss")
        plans = self.ask.plan_all("ABC", [one, two])[1]["plans"]
        self.assertNotIn("duplicate", plans[0])
        self.assertIn("duplicate", plans[1])

    def test_a_store_that_cannot_be_opened_for_the_warning_gives_no_warning(self):
        plan = ask_apply.read_suggestion("ABC", {"op": "new", "kind": "action", "title": TITLE})
        after = {"description": TITLE, "owner": "TBC"}
        with mock.patch.object(self.ask, "reader", side_effect=TypeError("no store")):
            self.assertEqual(self.ask.duplicate_of(plan, after, ()), "")
        self.assertIn("already", self.ask.duplicate_of(plan, after, ()))

    def test_the_store_read_for_the_warning_is_closed_whether_or_not_the_read_works(self):
        plan = ask_apply.read_suggestion("ABC", {"op": "new", "kind": "action", "title": TITLE})
        after = {"description": TITLE, "owner": "TBC"}
        for read in (mock.Mock(return_value=[]), mock.Mock(side_effect=ValueError("unreadable"))):
            store = mock.Mock(read=read)
            with mock.patch.object(self.ask, "reader", return_value=store):
                self.assertEqual(self.ask.duplicate_of(plan, after, ()), "")
            store.close.assert_called_once_with()


class Stale(ApplyBase):
    def two(self, first, second):
        a = self.planned({"op": "change", "id": self.action, "current_title": TITLE, **first})
        b = self.planned({"op": "change", "id": self.action, "current_title": TITLE, **second})
        return a, b

    def test_the_field_named_is_the_one_the_first_moved_when_the_second_was_about_another(self):
        a, b = self.two({"status": "Closed"}, {"priority": "Low"})
        self.assertEqual(self.applied(a["offer"])["stale"], [{"offer": b["offer"], "message": ask_words.stale("status")}])
        self.assertEqual(self.ask.apply(b["offer"], "ABC")[1]["message"], ask_words.stale("status"))

    def test_the_field_named_is_the_first_of_the_second_changes_own_fields_the_first_moved(self):
        a, b = self.two({"status": "Closed", "priority": "High"}, {"owner": "Kit Moss", "priority": "Low", "status": "Delayed"})
        self.assertEqual(self.applied(a["offer"])["stale"][0]["message"], ask_words.stale("priority"))

    def test_an_offer_already_stale_is_not_marked_again_by_a_later_save(self):
        a, b = self.two({"status": "Closed"}, {"status": "Delayed"})
        self.assertEqual(len(self.applied(a["offer"])["stale"]), 1)
        d = self.planned({"op": "change", "id": self.action, "current_title": TITLE, "priority": "High"})
        self.assertEqual(self.applied(d["offer"])["stale"], [])
        self.assertEqual(self.ask.apply(b["offer"], "ABC")[1]["message"], ask_words.stale("status"))


if __name__ == "__main__":
    unittest.main()

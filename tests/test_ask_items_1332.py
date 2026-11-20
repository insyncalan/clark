"""Row 1332 (rows 9-13 of the plan, server side): the ask reply carries `items`, the item IDs the answer names, each with its state.

Run: python3 dev/run_tests.py test_ask_items_1332
Quick tier: a real server on a free port, a stub provider, no Chrome. Draft killers: they fail while the reply has no `items`.
Assumed contract (to be ruled): "items" is a list of {"id", "state"}, in the order the answer first names them, each once, only
for an ID the report holds (the same `_known` check as the claims flags), taken from the ANSWER text and not from the question.
"state" is a list of words from overdue / red / no_owner read from the row, [] when none applies. Nothing else rides on an item.
Fictional data only.
"""
import dataclasses
import unittest
from unittest import mock

import test_ask_route as R
from clark import ask_service

A1, A2 = "PUB-A-001", "PUB-A-002"
HIDDEN = "PUB-A-011"
WORDS = {"overdue", "red", "no_owner"}


class Facts(dict):
    """The facts of one question; `broken` names a ref whose lookup raises (an item that cannot be looked up is not vouched for)."""

    def __init__(self, data, broken=()):
        super().__init__(data)
        self.broken = set(broken)

    def __contains__(self, ref):
        if ref in self.broken:
            raise RuntimeError("lookup failed")
        return super().__contains__(ref)


class Items(R.Base):
    def ask_with(self, reply, q="What about the plan?"):
        self.provider.reply = reply
        status, got = self.question(q)
        self.assertEqual(status, 200, got)
        return got

    def with_facts(self, extra, broken=()):
        """Run the next question with the real facts plus `extra` ({ref: {"state": [...]}}) merged in, so a test fixes the state."""
        real = R.ask_service.ask_data.project_data

        def wrapped(*a, **k):
            data = real(*a, **k)
            merged = {ref: {**f, **extra.get(ref, {})} for ref, f in data.facts.items()}
            return dataclasses.replace(data, facts=Facts(merged, broken))
        return mock.patch.object(R.ask_service.ask_data, "project_data", wrapped)

    # ----- row 9: the reply carries items (ids + state) -----
    def test_the_reply_carries_the_known_ids_the_answer_names_in_order_once_each(self):
        got = self.ask_with(f"{A2} is late and {A1} is fine. {A2} again.")
        self.assertEqual([i["id"] for i in got["items"]], [A2, A1])

    def test_an_item_holds_only_an_id_and_a_state_of_known_words(self):
        got = self.ask_with(f"{A1} is late.")
        (item,) = got["items"]
        self.assertEqual(set(item), {"id", "state"})
        self.assertIsInstance(item["state"], list)
        self.assertTrue(set(item["state"]) <= WORDS, item)

    def test_each_item_carries_its_own_state_not_a_neighbours(self):
        with self.with_facts({A1: {"state": ["overdue"]}, A2: {"state": ["red", "no_owner"]}}):
            got = self.ask_with(f"{A1} and {A2}.")
        self.assertEqual(got["items"], [{"id": A1, "state": ["overdue"]}, {"id": A2, "state": ["red", "no_owner"]}])

    def test_a_row_with_no_state_has_an_empty_list_not_a_missing_key(self):
        with self.with_facts({A1: {"state": []}}):
            got = self.ask_with(f"{A1} is fine.")
        self.assertEqual(got["items"], [{"id": A1, "state": []}])

    def test_overdue_and_red_are_not_swapped(self):
        for word in ("overdue", "red"):
            with self.with_facts({A1: {"state": [word]}}):
                self.assertEqual(self.ask_with(f"{A1}.")["items"][0]["state"], [word])

    def test_an_answer_naming_no_item_has_an_empty_list(self):
        got = self.ask_with("The plan is on track.\nCITE: P1")
        self.assertEqual(got["items"], [])

    def test_items_come_from_the_answer_not_from_the_question(self):
        got = self.ask_with("The plan is on track.", q=f"What is {A1}?")
        self.assertEqual(got["items"], [])

    def test_a_change_line_does_not_make_its_item_an_item(self):
        got = self.ask_with(f'Fine.\nCHANGE: {{"id": "{A1}", "status": "Closed"}}')
        self.assertEqual(got["items"], [])

    # ----- row 9: unknown ids are dropped (_known) -----
    def test_an_unknown_id_is_dropped_and_still_flagged(self):
        got = self.ask_with(f"PUB-A-999 and {A1} are late.")
        self.assertEqual([i["id"] for i in got["items"]], [A1])
        self.assertIn(("unknown_id", "PUB-A-999"), [(f["kind"], f["ref"]) for f in got["flags"]])

    def test_an_archived_row_is_never_an_item(self):      # row 1367: an archived row is not read
        got = self.ask_with("PUB-A-016 is late.")
        self.assertEqual(got["items"], [])

    def test_a_row_the_report_hides_is_an_item_for_the_owner(self):      # row 1367 (ruling 19-11): hidden rows are read
        got = self.ask_with(f"{HIDDEN} is late.")
        self.assertEqual([i["id"] for i in got["items"]], [HIDDEN])

    def test_an_id_that_cannot_be_looked_up_is_dropped(self):
        with self.with_facts({}, broken=(A2,)):
            got = self.ask_with(f"{A1} and {A2}.")
        self.assertEqual([i["id"] for i in got["items"]], [A1])

    def test_a_loosely_spelled_known_id_is_one_item_under_its_real_id(self):
        got = self.ask_with("pub-a-001 is late.")
        self.assertTrue(all(i["id"] == A1 for i in got["items"]), got["items"])
        self.assertLessEqual(len(got["items"]), 1)

    # ----- the reply as a whole is as before -----
    def test_an_unreadable_reply_carries_no_items(self):
        got = self.ask_with(f"{A1} is late.\nCITE: not-a-passage")
        self.assertFalse(got["parsed"])
        self.assertEqual(got.get("items", []), [])

    def test_the_other_fields_are_unchanged(self):
        got = self.ask_with("Fine.\nCITE: P1")
        for key in ("ok", "answer", "parsed", "cites", "sources", "flags", "changes", "notes", "reply", "draft", "left_out_for_safety"):
            self.assertIn(key, got)
        self.assertEqual(got["answer"], "Fine.")

    def test_a_failure_carries_no_items(self):
        self.provider.failure = "Took too long."
        status, got = self.question()
        self.assertEqual((status, got["ok"]), (200, False))
        self.assertNotIn("items", got)

    def test_nothing_is_written(self):
        before = self.counts()
        self.ask_with(f"{A1} and {A2}.")
        self.assertEqual(self.counts(), before)

    # ----- row 13: asking off is unchanged -----
    def test_asking_off_still_answers_409_with_no_items_and_asks_nobody(self):
        self.set_switch(False)
        status, got = self.question()
        self.assertEqual((status, got["ok"], got["code"]), (409, False, "asking_off"))
        self.assertNotIn("items", got)
        self.assertEqual(self.provider.sent, [])

    def test_a_switch_turned_off_while_the_question_is_prepared_still_wins(self):
        calls = iter((True, False))
        with mock.patch.object(ask_service.AskService, "enabled", lambda self: next(calls)):
            status, got = self.question()
        self.assertEqual((status, got["code"]), (409, "asking_off"))
        self.assertNotIn("items", got)
        self.assertEqual(self.provider.sent, [])


if __name__ == "__main__":
    unittest.main()

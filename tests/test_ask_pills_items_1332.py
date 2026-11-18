"""Row 1332 rows 3 and 11 (DRAFT contract): the suggestions that act on the items of the last answer.

Run: python3 dev/run_tests.py test_ask_pills_items_1332
Quick tier: no browser. askPills.js is bundled by the pinned esbuild and run in node (skips without node). The words are the words in askWords.js today.
"""
import json
import unittest

from test_ask_pills_killers_1332 import L, one, probe, reply, user

DUE, URGENCY, REPORT, OWNERS, LATE = "Change the due date", "Raise the urgency", "Add to the weekly report", "Who owns these?", "Why are these late?"
A, B = "PUB-A-001", "PUB-B-002"


def answer(*items, **extra):
    return {"role": "assistant", "text": "Here.", "items": [{"id": i, "state": s} for i, s in items], **extra}


def got(turns, view="dashboard", help_open=False, state=None):
    args = [json.dumps(view), json.dumps(turns), json.dumps(help_open)] + ([json.dumps(state)] if state else [])
    return one("K.pills(%s)" % ", ".join(args))


class Actions(unittest.TestCase):
    def test_an_answer_without_items_leaves_the_page_list_alone(self):
        for turn in (reply(), answer(), {"role": "assistant", "text": "x", "items": "no"}, {"role": "assistant", "text": "x", "items": [{"state": ["overdue"]}, None, {"id": ""}]}):
            self.assertEqual(got([user("Q"), turn]), L["dashboard"], turn)
        self.assertEqual(got([]), L["dashboard"])

    def test_the_action_is_built_from_the_item_it_is_true_of(self):
        # two items named, only B is overdue: the due date and the urgency name B and never A
        turns = [user("Q"), answer((A, []), (B, ["overdue"]))]
        have = got(turns)
        self.assertEqual(have[:4], [f"{DUE} ({B})", f"{URGENCY} ({B})", LATE, OWNERS])
        self.assertFalse([p for p in have if A in p], have)

    def test_every_overdue_item_is_named_in_order_and_a_red_one_is_not_raised(self):
        turns = [user("Q"), answer((A, ["overdue", "red"]), (B, ["overdue"]), ("PUB-C-003", ["overdue", "no_owner"]))]
        have = got(turns)
        self.assertEqual(have[:2], [f"{DUE} ({A}, {B}, PUB-C-003)", f"{URGENCY} ({B}, PUB-C-003)"])

    def test_the_state_words_decide_which_actions_are_offered(self):
        late_red = got([user("Q"), answer((A, ["overdue", "red"]))])
        self.assertEqual(late_red[:4], [f"{DUE} ({A})", LATE, OWNERS, REPORT])
        self.assertNotIn(URGENCY, " ".join(late_red))
        calm = got([user("Q"), answer((A, []), (B, ["red", "no_owner"]))])
        self.assertEqual(calm[:2], [OWNERS, REPORT])
        for p in calm:
            self.assertNotIn(DUE, p)
            self.assertNotIn(URGENCY, p)
            self.assertNotEqual(p, LATE)
        self.assertEqual(got([user("Q"), answer((A, ["secret", "late"]))])[:2], [OWNERS, REPORT], "only the three known words count")

    def test_the_plain_questions_carry_no_id(self):
        have = got([user("Q"), answer((A, ["overdue"]))])
        for plain in (LATE, OWNERS, REPORT):
            self.assertIn(plain, have)

    def test_at_most_six_with_the_actions_first_and_nothing_twice(self):
        turns = [user("Q"), answer((A, ["overdue"]))]
        have = got(turns)
        self.assertEqual(len(have), 6)
        self.assertEqual(len(set(have)), 6)
        self.assertEqual(have[:5], [f"{DUE} ({A})", f"{URGENCY} ({A})", LATE, OWNERS, REPORT])
        self.assertEqual(have[5], L["dashboard"][0], "the page's own list fills what is left")
        # the cap is exactly six: five actions and the whole page list would be eleven
        self.assertEqual(one("K.pills('dashboard', %s, false).length" % json.dumps(turns)), 6)

    def test_only_the_last_answer_counts_and_a_note_is_not_an_answer(self):
        old = answer((A, ["overdue"]))
        new = answer((B, []))
        self.assertEqual(got([user("Q"), old, user("R"), new])[:2], [OWNERS, REPORT])
        note = {"role": "assistant", "text": "A note.", "kind": "note"}
        self.assertEqual(got([user("Q"), old, note])[0], f"{DUE} ({A})")

    def test_help_beats_the_items(self):
        turns = [user("Q"), answer((A, ["overdue"]))]
        self.assertEqual(got(turns, help_open=True), got([], help_open=True))
        self.assertNotIn(DUE + f" ({A})", got(turns, help_open=True))

    def test_the_state_order_and_the_subject_still_apply_after_the_actions(self):
        turns = [user("Any risks?"), answer((A, []))]
        have = got(turns, "work", state={"overdue": 0, "red": 3, "noOwner": 0})
        self.assertEqual(have[:2], [OWNERS, REPORT])
        self.assertEqual(have[2], L["risks"][0])

    def test_the_input_is_not_changed(self):
        turns = [user("Q"), answer((A, ["overdue"]))]
        self.assertEqual(probe(["(function(){var t=%s;K.pills('work',t,false).push('x');return t})()" % json.dumps(turns)]), [turns])


if __name__ == "__main__":
    unittest.main()

"""Row 1332 rows 3 and 11 (DRAFT contract): the suggestions that act on the items of the last answer.

Run: python3 dev/run_tests.py test_ask_pills_items_1332
Quick tier: no browser. askPills.js is bundled by the pinned esbuild and run in node (skips without node). The words are the words in askWords.js today.
"""
import json
import unittest

from _paths import SRC
from test_ask_pills_killers_1332 import EDIT, L, one, probe, reply, user

DUE, URGENCY, REPORT, OWNERS, LATE = "Change the due date", "Raise the urgency", "Include in the weekly report", "Who owns these?", "Why are these late?"
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
        self.assertEqual(have[:4], [DUE, URGENCY, LATE, OWNERS])
        self.assertFalse([p for p in have if A in p], have)

    def test_every_overdue_item_is_named_in_order_and_a_red_one_is_not_raised(self):
        turns = [user("Q"), answer((A, ["overdue", "red"]), (B, ["overdue"]), ("PUB-C-003", ["overdue", "no_owner"]))]
        have = got(turns)
        self.assertEqual(have[:2], [DUE, URGENCY])

    def test_the_state_words_decide_which_actions_are_offered(self):
        late_red = got([user("Q"), answer((A, ["overdue", "red"]))])
        self.assertEqual(late_red[:4], [DUE, LATE, OWNERS, REPORT])
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
        self.assertEqual(have[:5], [DUE, URGENCY, LATE, OWNERS, REPORT])
        self.assertEqual(have[5], L["dashboard"][0], "the page's own list fills what is left")
        # the cap is exactly six: five actions and the whole page list would be eleven
        self.assertEqual(one("K.pills('dashboard', %s, false).length" % json.dumps(turns)), 6)

    def test_only_the_last_answer_counts_and_a_note_is_not_an_answer(self):
        old = answer((A, ["overdue"]))
        new = answer((B, []))
        self.assertEqual(got([user("Q"), old, user("R"), new])[:2], [OWNERS, REPORT])
        note = {"role": "assistant", "text": "A note.", "kind": "note"}
        self.assertEqual(got([user("Q"), old, note])[0], DUE)

    def test_help_beats_the_items(self):
        turns = [user("Q"), answer((A, ["overdue"]))]
        self.assertEqual(got(turns, help_open=True), got([], help_open=True))
        self.assertNotIn(DUE, got(turns, help_open=True))

    def test_the_state_order_and_the_subject_still_apply_after_the_actions(self):
        turns = [user("Any risks?"), answer((A, []))]
        have = got(turns, "work", state={"overdue": 0, "red": 3, "noOwner": 0})
        self.assertEqual(have[:2], [OWNERS, REPORT])
        self.assertEqual(have[2], L["risks"][0])

    def test_the_input_is_not_changed(self):
        turns = [user("Q"), answer((A, ["overdue"]))]
        self.assertEqual(probe(["(function(){var t=%s;K.pills('work',t,false).push('x');return t})()" % json.dumps(turns)]), [turns])

    def test_the_click_sends_the_ids_and_the_shown_words_carry_none(self):
        turns = [user("Q"), answer((A, ["overdue", "red"]), (B, ["overdue"]), ("PUB-C-003", []))]
        have = got(turns)
        for shown in have:
            self.assertNotRegex(shown, r"[()]|PUB-", shown)
        ask = lambda label: one("K.asking(%s, %s)" % (json.dumps(label), json.dumps(turns)))
        self.assertEqual(ask(DUE), f"{DUE} ({A}, {B})")
        self.assertEqual(ask(URGENCY), f"{URGENCY} ({B})")
        for plain in (LATE, OWNERS, REPORT, L["dashboard"][0], "Not a suggestion"):
            self.assertEqual(ask(plain), plain)
        self.assertEqual(one("K.asking(%s, 'no')" % json.dumps(DUE)), DUE, "no chat, no ids")

    def test_a_state_that_is_not_a_list_counts_as_none(self):
        for bad in ("overdue", 5, {"0": "overdue"}, None, True):
            turns = [user("Q"), {"role": "assistant", "text": "x", "items": [{"id": A, "state": bad}]}]
            self.assertEqual(got(turns)[:2], [OWNERS, REPORT], bad)
        for turns in ("Q", 5, {"role": "user"}, None):
            self.assertEqual(one("K.pills('dashboard', %s, false)" % json.dumps(turns)), L["dashboard"], turns)
        for counts in ("x", 5, [1, 2], True):
            self.assertEqual(one("K.pills('dashboard', [], false, %s)" % json.dumps(counts)), L["dashboard"], counts)

    def test_a_number_is_not_an_id(self):
        turns = [user("Q"), {"role": "assistant", "text": "x", "items": [{"id": 7, "state": ["overdue"]}, {"id": 0, "state": ["overdue"]}]}]
        self.assertEqual(got(turns), L["dashboard"])
        mixed = [user("Q"), {"role": "assistant", "text": "x", "items": [{"id": 7, "state": ["overdue"]}, {"id": A, "state": ["overdue"]}]}]
        self.assertEqual(one("K.asking(%s, %s)" % (json.dumps(DUE), json.dumps(mixed))), f"{DUE} ({A})")

    def test_a_newest_answer_without_items_clears_the_actions_of_the_one_before(self):
        old = answer((A, ["overdue"]))
        self.assertEqual(got([user("Q"), old, user("R"), reply()]), L["dashboard"])
        self.assertEqual(got([user("Q"), old, user("R"), answer()]), L["dashboard"])
        self.assertEqual(one("K.asking(%s, %s)" % (json.dumps(DUE), json.dumps([user("Q"), old, user("R"), reply()]))), DUE)

    def test_the_actions_come_first_then_the_state_order_with_the_larger_count_first(self):
        turns = [user("Any risks?"), answer((A, []))]
        have = got(turns, "work", state={"overdue": 1, "red": 2, "noOwner": 3})
        self.assertEqual(have[:2], [OWNERS, REPORT])
        self.assertEqual(have[2:4], [L["risks"][1], L["risks"][0]], "no owner (3) before red (2), both from the risks list")
        tie = got(turns, "work", state={"overdue": 0, "red": 3, "noOwner": 3})
        self.assertEqual(tie[2:4], [L["risks"][0], L["risks"][1]], "a tie: red before no owner")

    def test_six_at_most_with_the_state_and_the_actions_together(self):
        turns = [user("Q"), answer((A, ["overdue"]))]
        have = got(turns, "work", state={"overdue": 0, "red": 0, "noOwner": 4})
        self.assertEqual(len(have), 6)
        self.assertEqual(len(set(have)), 6)
        self.assertEqual(have[:5], [DUE, URGENCY, LATE, OWNERS, REPORT])
        self.assertEqual(have[5], "Which work items have no owner?", "the one the state puts first takes the last place")
        self.assertEqual(one("K.pills('work', %s, false, %s).length" % (json.dumps(turns), json.dumps({"overdue": 9, "red": 9, "noOwner": 9}))), 6)

class ReportWord(unittest.TestCase):
    def test_the_report_pill_says_the_ticket_words_exactly(self):
        self.assertEqual(REPORT, "Include in the weekly report")
        have = got([user("Q"), answer((A, ["overdue"]))])
        self.assertEqual(have.count("Include in the weekly report"), 1)
        self.assertIn('export const PILLS_ITEM_REPORT = "Include in the weekly report";', (EDIT / "askWords.js").read_text(encoding="utf-8"))

    def test_the_old_words_appear_nowhere_in_src(self):
        old = "Add to the " + "weekly report"
        for f in SRC.rglob("*"):
            if f.is_file() and f.suffix in (".js", ".jsx", ".json", ".py", ".css", ".html", ".md"):
                self.assertNotIn(old, f.read_text(encoding="utf-8", errors="ignore"), str(f))


if __name__ == "__main__":
    unittest.main()

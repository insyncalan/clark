"""Row 1332 (row 9, DRAFT contract): the words of an item's state read from a published row, and the cap of the items list.

Run: python3 dev/run_tests.py test_ask_item_state_1332
Quick tier, no server. Fictional data only.
"""
import unittest

from clark import ask, ask_data

TODAY = "2026-11-19"
CODES = ("PUB",)


def state(kind, **row):
    return ask_data.state_of(kind, row, TODAY)


class State(unittest.TestCase):
    def test_overdue_is_open_and_due_before_today(self):
        self.assertEqual(state("actions", status="Open", owner="Pat", due_date="2026-11-18"), ["overdue"])
        self.assertEqual(state("actions", status="Open", owner="Pat", due_date="2026-11-19"), [])
        self.assertEqual(state("actions", status="Open", owner="Pat", due_date="2026-11-20"), [])

    def test_a_finished_row_is_never_overdue_red_or_unowned(self):
        self.assertEqual(state("actions", status="Closed", owner="", due_date="2026-01-01", priority="High"), [])
        self.assertEqual(state("actions", status="Completed", owner="Pat", due_date="2026-01-01"), [])

    def test_red_is_urgent_or_high_and_open(self):
        for p, want in (("Urgent", ["red"]), ("High", ["red"]), ("Medium", []), ("Low", []), (None, [])):
            self.assertEqual(state("raid", status="Open", owner="Pat", priority=p), want, p)

    def test_no_owner_is_a_blank_owner_on_an_open_row(self):
        self.assertEqual(state("actions", status="Open", owner="", due_date=None), ["no_owner"])
        self.assertEqual(state("actions", status="Open", owner="  ", due_date=None), ["no_owner"])
        self.assertEqual(state("actions", status="Open", owner="Pat", due_date=None), [])

    def test_tbc_is_no_owner_as_the_page_reads_it(self):
        for tbc in ("TBC", "tbc", " Tbc "):
            self.assertEqual(state("actions", status="Open", owner=tbc, due_date=None), ["no_owner"], tbc)
        self.assertEqual(state("actions", status="Open", owner="Tbca", due_date=None), [])
        self.assertEqual(state("decisions", status="Pending", made_by="TBC", needed_by=None), ["no_owner"])

    def test_red_is_the_page_tile_rows_only(self):
        # the page counts open risks, issues, assumptions and dependencies rated Urgent or High: an action or a decision is never red
        self.assertEqual(state("actions", status="Open", owner="Pat", priority="High"), [])
        self.assertEqual(state("decisions", status="Pending", made_by="Pat", priority="Urgent"), [])
        self.assertEqual(state("raid", status="Closed", owner="Pat", priority="High"), [])

    def test_the_words_come_in_the_order_overdue_red_no_owner(self):
        self.assertEqual(state("raid", status="Open", owner="", due_date="2026-11-01", priority="High"), ["overdue", "red", "no_owner"])

    def test_a_milestone_reads_its_own_state(self):
        self.assertEqual(state("milestones", state="Overdue", owner="Pat"), ["overdue"])
        self.assertEqual(state("milestones", state="Slipped", owner="Pat"), [])
        self.assertEqual(state("milestones", state="On track", owner=""), ["no_owner"])
        self.assertEqual(state("milestones", state="Achieved", owner=""), [])

    def test_a_pending_decision_is_late_by_its_needed_by_date(self):
        self.assertEqual(state("decisions", status="Pending", made_by="Pat", needed_by="2026-11-01"), ["overdue"])
        self.assertEqual(state("decisions", status="Made", made_by="", needed_by="2026-11-01"), [])

    def test_a_use_case_has_no_owner_field_to_miss(self):
        self.assertEqual(state("use_cases", title="x"), [])

    def test_no_as_at_day_is_never_overdue(self):
        self.assertEqual(ask_data.state_of("actions", {"status": "Open", "owner": "Pat", "due_date": "2000-01-01"}, None), [])


class ItemsLimit(unittest.TestCase):
    def test_items_are_cut_at_the_cap_in_order(self):
        ids = [f"PUB-A-{n:03d}" for n in range(1, ask.MAX_ITEMS + 6)]
        r = ask.read_reply(" ".join(ids), (), CODES, lambda ref: True)
        self.assertEqual([i["id"] for i in r.items], ids[:ask.MAX_ITEMS])
        self.assertEqual(ask.MAX_ITEMS, 20)

    def test_a_loose_spelling_of_a_real_id_is_one_item_after_the_strict_ones(self):
        r = ask.read_reply("pub a 002 then PUB-A-001 then PUB-A-002", (), CODES, lambda ref: True)
        self.assertEqual([i["id"] for i in r.items], ["PUB-A-001", "PUB-A-002"])
        r = ask.read_reply("only pub a 002 here", (), CODES, lambda ref: True)
        self.assertEqual([i["id"] for i in r.items], ["PUB-A-002"])

    def test_a_state_word_outside_the_three_is_dropped(self):
        r = ask.read_reply("PUB-A-001", (), CODES, lambda ref: True, lambda ref: {"state": ["red", "secret", "overdue"]})
        self.assertEqual(r.items, ({"id": "PUB-A-001", "state": ["red", "overdue"]},))

    def test_facts_that_raise_leave_the_item_with_no_state(self):
        def boom(ref):
            raise RuntimeError("x")
        r = ask.read_reply("PUB-A-001", (), CODES, lambda ref: True, boom)
        self.assertEqual(r.items, ({"id": "PUB-A-001", "state": []},))


if __name__ == "__main__":
    unittest.main()

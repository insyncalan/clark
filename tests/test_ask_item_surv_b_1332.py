"""Row 1332 (killers, round b): the items of a reply and the state of a row, the cases the first tests left open.

Run: python3 dev/run_tests.py test_ask_item_surv_b_1332
Quick tier, no server, no Chrome. Fictional data only.

Not covered here, equivalent (file:line at the head these tests were made on):
- src/clark/ask.py:526  `(facts(ref) or {})` to `facts(ref)`: a None result raises AttributeError, the next line's except turns that into held None, and both give state [].
- src/clark/ask_data.py:155  `is_open(full)` to `is_open(row)`: is_open reads only the status, and `full` differs from `row` only by the added "kind".
- src/clark/ask_data.py:158  `.strip()` removed: `plain` already joins the words on single spaces and so trims the ends.
- src/clark/ask_data.py:221  `as_at` handed on without the `_is_day` check: glance.is_overdue reads the day through day_number, which gives None for a text that is not a day, so nothing is overdue either way.
- src/clark/ask_service.py:209  `list(i["state"])` to `i["state"]`: the only producer (ask._items_in) builds a list, and a tuple is written as the same JSON array.
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ask, ask_data, publish

CODES = ("PUB",)
YES = lambda ref: True  # noqa: E731


def items(text, facts=None):
    return ask.read_reply(text, (), CODES, YES, facts).items


def project(as_at):
    given = plant.inputs()
    given["as_at"] = as_at
    with mock.patch.object(publish, "read_inputs", return_value=given):
        return ask_data.project_data(object(), "PUB", "what is late?", as_at=as_at)


class Order(unittest.TestCase):
    def test_a_disguised_strict_id_keeps_its_place_among_the_strict_ones(self):
        # the dashes are non-breaking hyphens: normalised, the first id is PUB-A-002 and it comes before the plain PUB-A-001
        r = items("PUB‑A‑002 is late, then PUB-A-001.")
        self.assertEqual([i["id"] for i in r], ["PUB-A-002", "PUB-A-001"])

    def test_loose_spellings_come_sorted_whatever_the_order_named(self):
        text = " ".join(f"pub a {n:03d}" for n in range(9, 1, -1))
        r = items(text)
        self.assertEqual([i["id"] for i in r], [f"PUB-A-{n:03d}" for n in range(2, 10)])


class Held(unittest.TestCase):
    def test_no_facts_callable_gives_an_empty_state(self):
        self.assertEqual(items("PUB-A-001"), ({"id": "PUB-A-001", "state": []},))

    def test_a_state_held_as_a_tuple_is_read(self):
        self.assertEqual(items("PUB-A-001", lambda ref: {"state": ("red", "overdue")}), ({"id": "PUB-A-001", "state": ["red", "overdue"]},))

    def test_a_state_that_is_not_a_list_or_tuple_gives_an_empty_state(self):
        for held in ({"red": 1}, {"red"}, "red", 0):
            self.assertEqual(items("PUB-A-001", lambda ref, h=held: {"state": h}), ({"id": "PUB-A-001", "state": []},), held)

    def test_an_item_holds_exactly_an_id_and_a_state(self):
        (item,) = items("PUB-A-001", lambda ref: {"state": ["red"]})
        self.assertEqual(item, {"id": "PUB-A-001", "state": ["red"]})


class State(unittest.TestCase):
    def test_a_row_with_no_owner_field_at_all_has_no_owner(self):
        self.assertEqual(ask_data.state_of("actions", {"status": "Open"}, "2026-11-19"), ["no_owner"])

    def test_facts_carry_the_state_read_at_the_as_at_day(self):
        facts = project("2026-11-17").facts
        self.assertEqual(facts["PUB-A-001"]["state"], ["overdue"])
        self.assertEqual(facts["PUB-001"]["state"], ["overdue", "red"])

    def test_facts_before_every_due_day_are_not_overdue_but_the_risk_is_still_red(self):
        facts = project("2026-11-01").facts
        self.assertEqual(facts["PUB-A-001"]["state"], [])
        self.assertEqual(facts["PUB-001"]["state"], ["red"])

    def test_an_as_at_that_is_not_a_day_makes_nothing_overdue(self):
        facts = project("soon").facts
        self.assertEqual(facts["PUB-A-001"]["state"], [])
        self.assertEqual(facts["PUB-001"]["state"], ["red"])

    def test_facts_of_reads_each_row_by_its_own_kind(self):
        facts = ask_data.facts_of(publish.select(plant.inputs())["data"], "2026-11-17")
        self.assertEqual(facts["PUB-001"]["state"], ["overdue", "red"])
        self.assertEqual(facts["PUB-A-001"]["state"], ["overdue"])
        self.assertEqual(facts["PUB-M-001"]["state"], [])


if __name__ == "__main__":
    unittest.main()

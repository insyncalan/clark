"""#74 / #65: where a moved row goes (src/clark/order.py): documents and sections share it.

Run: python3 dev/run_tests.py test_order
Rows are plain dicts with an id and a sort_order, as any table with those two columns gives. A move writes one row only,
unless no whole number fits, and then the whole list is renumbered to GAP * n in the same step.
"""
import random
import unittest

from clark.order import GAP, end_slot, in_order, section_slot


def rows(*orders, prefix="R"):
    """Rows R1, R2 ... with these sort_orders."""
    return [{"id": f"{prefix}{n}", "sort_order": o} for n, o in enumerate(orders, 1)]


def seeded(n):
    return rows(*[GAP * i for i in range(1, n + 1)])


def apply(rs, writes):
    return [{**r, "sort_order": writes.get(r["id"], r["sort_order"])} for r in rs]


def ids(rs):
    return [r["id"] for r in in_order(rs)]


def moved(rs, moving, before):
    """The list after the move, as shown."""
    return in_order(apply(rs, section_slot(rs, moving, before)))


class Slots(unittest.TestCase):
    def test_gap_is_1024(self):
        self.assertEqual(GAP, 1024)

    def test_moving_up_takes_the_midpoint_of_its_neighbours(self):
        rs = seeded(4)                                   # 1024 2048 3072 4096
        self.assertEqual(section_slot(rs, "R3", "R2"), {"R3": 1536})
        self.assertEqual(ids(apply(rs, {"R3": 1536})), ["R1", "R3", "R2", "R4"])

    def test_moving_down_takes_the_midpoint_of_its_neighbours(self):
        rs = seeded(4)
        self.assertEqual(section_slot(rs, "R1", "R4"), {"R1": 3584})      # between R3 (3072) and R4 (4096)
        self.assertEqual(ids(apply(rs, {"R1": 3584})), ["R2", "R3", "R1", "R4"])

    def test_to_the_top_is_the_first_minus_a_gap(self):
        self.assertEqual(section_slot(seeded(3), "R3", "R1"), {"R3": 0})
        self.assertEqual(section_slot(rows(10, 20, 30), "R3", "R1"), {"R3": 10 - GAP})

    def test_to_the_end_is_the_last_plus_a_gap(self):
        self.assertEqual(section_slot(seeded(3), "R1", None), {"R1": 4096})
        self.assertEqual(section_slot(rows(10, 20, 30), "R1", None), {"R1": 30 + GAP})

    def test_the_moved_row_is_not_its_own_neighbour(self):
        rs = seeded(3)
        self.assertEqual(section_slot(rs, "R2", "R3"), {})                 # already just before R3
        self.assertEqual(section_slot(rs, "R1", "R3"), {"R1": 2560})       # between R2 (2048) and R3 (3072)
        self.assertEqual(section_slot(rs, "R3", "R2"), {"R3": 1536})

    def test_a_row_already_there_writes_nothing(self):
        rs = seeded(4)
        self.assertEqual(section_slot(rs, "R2", "R3"), {})                 # just before the one after it
        self.assertEqual(section_slot(rs, "R4", None), {})                 # last, to the end
        self.assertEqual(section_slot(rs, "R1", "R2"), {})                 # first, before the second
        self.assertEqual(section_slot(rs, "R2", "R2"), {})                 # before itself

    def test_one_row_cannot_move(self):
        one = rows(1024)
        self.assertEqual(section_slot(one, "R1", None), {})
        self.assertEqual(section_slot(one, "R1", "R1"), {})

    def test_two_rows(self):
        two = seeded(2)
        self.assertEqual(section_slot(two, "R2", "R1"), {"R2": 0})
        self.assertEqual(section_slot(two, "R1", None), {"R1": 3072})

    def test_rows_are_shown_by_sort_order_then_id_whatever_order_they_are_given_in(self):
        rs = [{"id": "B", "sort_order": 20}, {"id": "A", "sort_order": 20}, {"id": "C", "sort_order": 5}]
        self.assertEqual(ids(rs), ["C", "A", "B"])
        shuffled = [rs[2], rs[0], rs[1]]
        self.assertEqual(section_slot(rs, "B", "C"), section_slot(shuffled, "B", "C"))
        self.assertEqual(section_slot(rs, "B", "C"), {"B": 5 - GAP})

    def test_negative_and_zero_orders_work(self):
        rs = rows(-1024, 0, 1024)
        self.assertEqual(section_slot(rs, "R3", "R2"), {"R3": -512})
        self.assertEqual(section_slot(rows(-4, -1), "R1", None), {"R1": -1 + GAP})
        rs = rows(-4, -1, 5)
        self.assertEqual(section_slot(rs, "R3", "R2"), {"R3": -3})         # floor of -2.5 would be -3: strictly between -4 and -1
        self.assertTrue(-4 < -3 < -1)

    def test_end_slot(self):
        self.assertEqual(end_slot([]), GAP)
        self.assertEqual(end_slot(seeded(3)), 4096)
        self.assertEqual(end_slot(rows(7, 3)), 7 + GAP)
        self.assertEqual(end_slot(rows(-5)), -5 + GAP)


class Renumbering(unittest.TestCase):
    def test_no_whole_number_between_neighbours_renumbers_everything_in_one_step(self):
        rs = rows(1024, 1025, 1026, 5000)               # nothing fits between R1 and R2, or R2 and R3
        writes = section_slot(rs, "R4", "R2")
        self.assertEqual(writes, {"R4": 2048, "R2": 3072, "R3": 4096})
        self.assertEqual(ids(apply(rs, writes)), ["R1", "R4", "R2", "R3"])
        self.assertEqual([r["sort_order"] for r in in_order(apply(rs, writes))], [GAP * n for n in (1, 2, 3, 4)])

    def test_only_rows_whose_value_changes_are_written(self):
        rs = rows(1024, 1025, 1026, 5000)
        writes = section_slot(rs, "R4", "R2")
        self.assertNotIn("R1", writes)                  # already 1024
        self.assertEqual(set(writes), {"R4", "R2", "R3"})

    def test_a_tie_between_the_neighbours_renumbers(self):
        rs = rows(2048, 2048, 4096)
        writes = section_slot(rs, "R3", "R2")           # between two rows that tie
        self.assertEqual(ids(apply(rs, writes)), ["R1", "R3", "R2"])
        self.assertEqual(sorted(apply(rs, writes), key=lambda r: r["id"])[0]["sort_order"], GAP)

    def test_neighbours_one_apart_renumber_but_two_apart_do_not(self):
        self.assertGreater(len(section_slot(rows(10, 11, 99), "R3", "R2")), 1)
        self.assertEqual(section_slot(rows(10, 12, 99), "R3", "R2"), {"R3": 11})

    def test_a_tie_that_is_not_beside_the_slot_does_not_renumber(self):
        rs = rows(1024, 1024, 5000, 9000)               # R1 and R2 tie, far from where R4 goes
        self.assertEqual(section_slot(rs, "R4", "R3"), {"R4": 3012})       # (1024 + 5000) // 2

    def test_the_top_and_the_end_never_renumber(self):
        rs = rows(5, 5, 5)
        self.assertEqual(len(section_slot(rs, "R3", "R1")), 1)
        self.assertEqual(len(section_slot(rs, "R1", None)), 1)

    def test_a_renumber_after_it_keeps_the_order_and_leaves_a_gap_for_next_time(self):
        rs = rows(1, 2, 3, 4, 5)
        for _ in range(3):
            rs = apply(rs, section_slot(rs, "R5", "R2"))
        self.assertEqual(ids(rs), ["R1", "R5", "R2", "R3", "R4"])
        self.assertTrue(all(b["sort_order"] - a["sort_order"] >= 2 for a, b in zip(in_order(rs), in_order(rs)[1:])))

    def test_the_gap_runs_out_only_after_ten_halvings(self):
        rs = rows(0, 1024, *[2048 + 1024 * n for n in range(12)])
        previous, count = "R2", 0                        # each move goes just before the row moved last: the gap halves
        while count < 20:
            last = in_order(rs)[-1]["id"]
            writes = section_slot(rs, last, previous)
            if len(writes) != 1:
                break
            rs, previous, count = apply(rs, writes), last, count + 1
        self.assertEqual(count, 10)                      # 1024 apart halves to 1 in ten moves; the eleventh renumbers
        self.assertGreater(len(writes), 1)


class Refusals(unittest.TestCase):
    def test_unknown_ids_raise_value_error(self):
        rs = seeded(3)
        with self.assertRaises(ValueError):
            section_slot(rs, "NOPE", "R1")
        with self.assertRaises(ValueError):
            section_slot(rs, "R1", "NOPE")
        with self.assertRaises(ValueError):
            section_slot(rs, "NOPE", None)
        with self.assertRaises(ValueError):
            section_slot([], "R1", None)

    def test_duplicate_ids_and_odd_orders_raise_value_error(self):
        with self.assertRaises(ValueError) as caught:
            section_slot([{"id": "A", "sort_order": 1}, {"id": "A", "sort_order": 2}], "A", None)
        self.assertEqual(str(caught.exception), "Two rows in this list can't be told apart.")     # plain words, no column name
        for bad in (None, 1.5, "7", True):
            with self.subTest(bad=bad), self.assertRaises(ValueError) as caught:
                section_slot([{"id": "A", "sort_order": bad}, {"id": "B", "sort_order": 2}], "A", None)
            self.assertEqual(str(caught.exception), "A row in this list has a place that isn't a whole number.")
            self.assertNotIn("sort_order", str(caught.exception))

    def test_the_rows_passed_in_are_not_changed(self):
        rs = rows(1024, 1025, 1026)
        before = [dict(r) for r in rs]
        section_slot(rs, "R3", "R1")
        section_slot(rs, "R3", "R2")
        self.assertEqual(rs, before)

    def test_an_iterator_of_rows_is_read_once(self):
        self.assertEqual(section_slot(iter(seeded(3)), "R3", "R1"), {"R3": 0})

    def test_other_columns_do_not_matter(self):
        rs = [{"id": "D-1", "sort_order": 1024, "title": "Minutes", "url": "https://example.com/a"},
              {"id": "D-2", "sort_order": 2048, "title": "Plan", "url": "https://example.com/b"}]
        self.assertEqual(section_slot(rs, "D-2", "D-1"), {"D-2": 0})


class Properties(unittest.TestCase):
    """What the one-step undo relies on, over many random moves."""

    def run_moves(self, rs, seed, moves=400):
        rng = random.Random(seed)
        renumbers = 0
        for _ in range(moves):
            names = [r["id"] for r in in_order(rs)]
            moving = rng.choice(names)
            before = rng.choice(names + [None])
            expected = [n for n in names if n != moving]
            if before == moving:
                expected = names
            else:
                expected.insert(len(expected) if before is None else expected.index(before), moving)
            writes = section_slot(rs, moving, before)
            after = apply(rs, writes)
            self.assertEqual(ids(after), expected, (seed, moving, before))
            if expected == names:
                self.assertEqual(writes, {})
            elif len(writes) > 1:
                renumbers += 1
                self.assertEqual([r["sort_order"] for r in in_order(after)], [GAP * n for n in range(1, len(rs) + 1)])
            else:
                self.assertEqual(list(writes), [moving])        # exactly one row, the moved one
            for r in rs:                                         # a row not written is untouched
                if r["id"] not in writes:
                    self.assertEqual(after[rs.index(r)], r)
            rs = after
        return renumbers

    def test_a_move_changes_exactly_the_moved_row_except_when_renumbering(self):
        for seed in range(8):
            self.run_moves(seeded(6), seed)

    def test_the_order_is_right_after_every_move_even_from_a_squeezed_start(self):
        renumbers = 0
        for seed in range(8):
            renumbers += self.run_moves(rows(1, 2, 3, 4, 5, 6), seed)
        self.assertGreater(renumbers, 0)                         # the squeezed start did force renumbers

    def test_ties_everywhere_still_give_the_right_order(self):
        for seed in range(5):
            self.run_moves(rows(7, 7, 7, 7), seed, moves=100)

    def test_undo_is_one_write_back(self):
        """Putting the old value back for the one row written restores the list exactly."""
        rs = seeded(5)
        writes = section_slot(rs, "R5", "R2")
        self.assertEqual(len(writes), 1)
        after = apply(rs, writes)
        undone = apply(after, {k: next(r["sort_order"] for r in rs if r["id"] == k) for k in writes})
        self.assertEqual(undone, rs)

    def test_moving_back_and_forth_never_drifts_the_other_rows(self):
        rs = seeded(5)
        start = {r["id"]: r["sort_order"] for r in rs}
        for _ in range(5):
            rs = apply(rs, section_slot(rs, "R5", "R1"))
            rs = apply(rs, section_slot(rs, "R5", None))
        self.assertEqual({k: v for k, v in ((r["id"], r["sort_order"]) for r in rs) if k != "R5"},
                         {k: v for k, v in start.items() if k != "R5"})

    def test_the_seed_shape_survives_a_move_of_every_row_to_every_place(self):
        base = seeded(11)                                        # FR-10's eleven sections
        for moving in [r["id"] for r in base]:
            for before in [r["id"] for r in base] + [None]:
                with self.subTest(moving=moving, before=before):
                    names = ids(base)
                    after = moved(base, moving, before)
                    expected = [n for n in names if n != moving]
                    if before != moving:
                        expected.insert(len(expected) if before is None else expected.index(before), moving)
                    else:
                        expected = names
                    self.assertEqual([r["id"] for r in after], expected)


if __name__ == "__main__":
    unittest.main()

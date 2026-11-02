"""#136 G1: Store.milestone_moves, the Movement read. Owner only; it never reads the internal note and writes nothing."""
import inspect
import collections
import json
import sqlite3
import time
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import store as st_mod
from clark.store import MOVE_FIELDS, MOVE_SQL, connect

PLANTED = "PLANTED-INTERNAL-NOTE-2290 supplier wants more money"
REBASE = {"agreed_with": "Pat Placeholder", "reason": "Build ran long", "source": "Steering, 01-10-2026"}
REPLY_KEYS = {"project", "milestones", "truncated"}
BLOCK_KEYS = {"original", "total", "moves", "events"}
EVENT_KEYS = {"event_id", "at", "step", "by_user", "table", "ref", "field", "before", "after", "op", "route", "place", "origin",
              "actor", "src_ref", "decision", "undoes", "is_undo", "undone_by", "in_force"}


def add_milestone(demo, name, **values):
    with demo.store.step("dashboard", USER) as st:
        return st.create("milestones", {"project": "ABC", "name": name, "source": "demo", **values})


def bulk(demo, milestone, field, n, apply_id=None, rows_per_step=1):
    """n forecast moves for `milestone`, written straight into the log (fast): a step of its own for each (`rows_per_step` events
    each, so a test can make a step with several rows). The connection commits every statement unless told otherwise, so the
    rows go in one transaction (#357), unless the caller has one open already, which it then leaves to its caller to commit."""
    con = demo.store.con
    own = not con.in_transaction
    if own:
        con.execute("BEGIN")
    for i in range(n):
        con.execute("INSERT INTO applies (by_user, device) VALUES (?, 'demo')", (USER,))
        step = con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        for j in range(rows_per_step):
            cur = con.execute("INSERT INTO change_log (apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                              "VALUES (?, 'milestones', ?, ?, ?, ?, 'update', 'dashboard')",
                              (step, milestone, field, "2030-01-%02d" % (1 + i % 28), "2030-02-%02d" % (1 + i % 28)))
            con.execute("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, actor) "
                        "VALUES ('2026-10-01T00:00:00.000Z', ?, ?, ?, 'change', 'dashboard', 'you')", (step, milestone, cur.lastrowid))
    if own:
        con.execute("COMMIT")


class TheReply(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.m = self.demo.milestone

    def test_the_keys_are_exactly_the_documented_ones(self):
        self.demo.update("milestones", self.m, {"baseline_date": "2030-04-01"}, rebaseline=REBASE)
        got = self.s.milestone_moves("ABC")
        self.assertEqual(set(got), REPLY_KEYS)
        self.assertEqual(got["project"], "ABC")
        self.assertIs(got["truncated"], False)
        block = got["milestones"][self.m]
        self.assertEqual(set(block), BLOCK_KEYS)
        self.assertTrue(block["events"])
        for e in block["events"]:
            self.assertEqual(set(e), EVENT_KEYS)
            self.assertEqual((e["table"], e["ref"]), ("milestones", self.m))

    def test_the_store_counts_moves_with_the_same_function_as_the_view(self):
        from clark import milestone_rows, movement_view
        self.assertIs(movement_view.mr, milestone_rows, "the view and the store share one counting rule")
        for new in ("2030-04-01", "2030-05-01"):
            self.demo.update("milestones", self.m, {"forecast_date": new})
        block = self.s.milestone_moves("ABC")["milestones"][self.m]
        want = milestone_rows.moves(milestone_rows.movement(block["events"], self.m))
        self.assertEqual(block["moves"], want)
        self.assertGreater(want, 0)

    def test_a_missing_project_is_none(self):
        self.assertIsNone(self.s.milestone_moves("NOPE"))

    def test_a_milestone_nobody_changed_has_no_events_and_the_step_that_made_it_is_not_listed(self):
        got = self.s.milestone_moves("ABC")["milestones"][self.m]
        self.assertEqual((got["events"], got["total"]), ([], 0))
        self.assertEqual(got["original"], "2030-03-01", "the first agreed date still comes from the step that made it")

    def test_an_archived_milestone_and_another_projects_milestone_are_absent(self):
        other = add_milestone(self.demo, "Old workshop", baseline_date="2030-05-01")
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            mine = st.create("milestones", {"project": "XYZ", "name": "Elsewhere", "baseline_date": "2030-06-01", "source": "demo"})
        self.demo.update("milestones", mine, {"forecast_date": "2030-07-01"})
        self.demo.update("milestones", other, {"forecast_date": "2030-07-01"})
        with self.s.step("dashboard", USER) as st:
            st.archive("milestones", other)
        got = self.s.milestone_moves("ABC")
        self.assertEqual(sorted(got["milestones"]), [self.m])
        self.assertEqual(sorted(self.s.milestone_moves("XYZ")["milestones"]), [mine])
        self.assertNotIn(other, json.dumps(got))

    def test_newest_first_and_a_rebaseline_names_the_last_decision_cited(self):
        self.demo.update("milestones", self.m, {"forecast_date": "2030-03-10"})
        self.demo.update("milestones", self.m, {"baseline_date": "2030-04-01"}, rebaseline=REBASE,
                         note="Build ran long, see ABC-D-004")
        events = self.s.milestone_moves("ABC")["milestones"][self.m]["events"]
        ids = [e["event_id"] for e in events]
        self.assertEqual(ids, sorted(ids, reverse=True))
        moved = [e for e in events if e["field"] == "baseline_date"]
        self.assertEqual(len(moved), 1)
        self.assertRegex(moved[0]["decision"], r"^ABC-D-\d{3}$")
        self.assertNotEqual(moved[0]["decision"], "ABC-D-004", "the last ID in the note, which the store wrote")
        self.assertEqual({e["decision"] for e in events if e["step"] != moved[0]["step"]}, {""})

    def test_original_comes_from_every_row_not_only_the_kept_ones(self):
        bulk(self.demo, self.m, "forecast_date", 120)
        block = self.s.milestone_moves("ABC")["milestones"][self.m]
        self.assertEqual((block["original"], block["total"], len(block["events"])), ("2030-03-01", 120, 50))

    def test_the_original_skips_a_first_agreement_that_was_undone(self):
        m2 = add_milestone(self.demo, "Second")       # no agreed date at the start
        step = self.demo.update("milestones", m2, {"baseline_date": "2030-08-01"})
        self.s.undo(step, USER)
        self.assertIsNone(self.s.milestone_moves("ABC")["milestones"][m2]["original"])
        self.demo.update("milestones", m2, {"baseline_date": "2030-09-01"})
        self.assertEqual(self.s.milestone_moves("ABC")["milestones"][m2]["original"], "2030-09-01")


class TheLimits(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def test_fifty_a_milestone_with_the_total_and_the_flag(self):
        bulk(self.demo, self.demo.milestone, "forecast_date", 49)
        got = self.s.milestone_moves("ABC")
        self.assertEqual((got["milestones"][self.demo.milestone]["total"], len(got["milestones"][self.demo.milestone]["events"]),
                          got["truncated"]), (49, 49, False))
        bulk(self.demo, self.demo.milestone, "forecast_date", 2)
        got = self.s.milestone_moves("ABC")
        block = got["milestones"][self.demo.milestone]
        self.assertEqual((block["total"], len(block["events"]), got["truncated"]), (51, 50, True))
        newest = max(r[0] for r in self.s.con.execute("SELECT event_id FROM item_events"))
        self.assertEqual(block["events"][0]["event_id"], newest, "the latest 50 are kept")

    def test_a_thousand_a_project_keeps_the_newest_across_milestones(self):
        ms = [self.demo.milestone] + [add_milestone(self.demo, "M%d" % i) for i in range(1, 23)]
        for m in ms:
            bulk(self.demo, m, "forecast_date", 50)
        got = self.s.milestone_moves("ABC")
        kept = [e["event_id"] for b in got["milestones"].values() for e in b["events"]]
        self.assertEqual(len(kept), 1000)
        self.assertTrue(got["truncated"])
        every = sorted((r[0] for r in self.s.con.execute("SELECT event_id FROM item_events WHERE item_id LIKE '%-M-%' "
                                                         "AND change IN (SELECT rowid FROM change_log WHERE field = 'forecast_date')")),
                       reverse=True)
        self.assertEqual(sorted(kept, reverse=True), every[:1000])
        self.assertTrue(all(b["total"] == 50 for b in got["milestones"].values()))


class TheRecord(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.m = self.demo.milestone

    def test_after_an_undo_the_reversed_rows_are_not_in_force_and_the_undo_rows_say_so(self):
        step = self.demo.update("milestones", self.m, {"baseline_date": "2030-04-01"}, rebaseline=REBASE)
        undo = self.s.undo(step, USER)["step_id"]
        events = self.s.milestone_moves("ABC")["milestones"][self.m]["events"]
        was = [e for e in events if e["step"] == step]
        back = [e for e in events if e["step"] == undo]
        self.assertTrue(was and back)
        self.assertTrue(all(not e["in_force"] for e in was if e["field"] != "note"), "a note is history only, so never reversed")
        self.assertTrue(all(e["is_undo"] for e in back))
        self.assertTrue(all(e["undone_by"] for e in was if e["field"] == "baseline_date"))
        self.assertEqual(self.s.milestone_moves("ABC")["milestones"][self.m]["original"], "2030-03-01")

    def test_reverted_rowids_is_read_once_for_the_whole_project(self):
        for i in range(3):
            self.demo.update("milestones", add_milestone(self.demo, "M%d" % i), {"forecast_date": "2030-07-01"})
        with mock.patch.object(st_mod, "reverted_rowids", wraps=st_mod.reverted_rowids) as spy:
            self.s.milestone_moves("ABC")
        self.assertEqual(spy.call_count, 1)

    def test_a_note_written_alone_is_never_returned_but_a_reason_beside_a_change_is(self):
        self.demo.update("milestones", self.m, {"movement": "hold"}, note="PLANTED-ALONE dated line")
        self.demo.update("milestones", self.m, {"forecast_date": "2030-03-20"}, note="PLANTED-BESIDE build ran long")
        con = self.s.con                 # a step with only a note: the writer will not make one, so the log gets it directly
        con.execute("INSERT INTO applies (by_user, device) VALUES (?, 'demo')", (USER,))
        step = con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        cur = con.execute("INSERT INTO change_log (apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                          "VALUES (?, 'milestones', ?, 'note', NULL, 'PLANTED-LONE-NOTE nothing else', 'update', 'dashboard')",
                          (step, self.m))
        con.execute("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, actor) "
                    "VALUES ('2026-10-02T00:00:00.000Z', ?, ?, ?, 'change', 'dashboard', 'you')", (step, self.m, cur.lastrowid))
        text = json.dumps(self.s.milestone_moves("ABC"))
        self.assertIn("PLANTED-BESIDE", text)
        self.assertIn("PLANTED-ALONE", text, "a note beside the Movement choice is a reason")
        self.assertNotIn("PLANTED-LONE-NOTE", text)

    def test_the_internal_note_and_the_fields_outside_the_list_are_never_read(self):
        self.demo.update("milestones", self.m, {"internal_note": PLANTED})
        self.demo.update("milestones", self.m, {"name": "Renamed", "owner": "Someone Else"})
        self.demo.update("milestones", self.m, {"forecast_date": "2030-03-20"})
        got = self.s.milestone_moves("ABC")
        text = json.dumps(got)
        self.assertNotIn(PLANTED, text)
        self.assertNotIn("internal_note", text)
        self.assertNotIn("Renamed", text)
        self.assertEqual({e["field"] for e in got["milestones"][self.m]["events"]}, {"forecast_date"})

    def test_a_move_written_in_the_movement_place_says_so_and_nothing_else_in_src_ref_comes_out(self):
        with self.s.step("dashboard", USER, place="dashboard", src_ref="Movement") as st:
            st.update("milestones", self.m, {"forecast_date": "2030-03-20"})
        with self.s.step("dashboard", USER, place="dashboard", src_ref="PLANTED-SRC secret") as st:
            st.update("milestones", self.m, {"forecast_date": "2030-03-21"})
        events = self.s.milestone_moves("ABC")["milestones"][self.m]["events"]
        self.assertEqual([e["src_ref"] for e in events], [None, "Movement"])
        self.assertNotIn("PLANTED-SRC", json.dumps(events))


class TheRead(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def test_it_writes_nothing(self):
        self.demo.update("milestones", self.demo.milestone, {"forecast_date": "2030-03-20"})
        sql = "SELECT (SELECT count(*) FROM change_log), (SELECT count(*) FROM item_events), (SELECT count(*) FROM applies)"
        before = tuple(self.s.con.execute(sql).fetchone())
        version = self.s.con.execute("PRAGMA data_version").fetchone()[0]
        self.s.milestone_moves("ABC")
        self.s.milestone_moves("NOPE")
        self.assertEqual(tuple(self.s.con.execute(sql).fetchone()), before)
        self.assertEqual(self.s.con.execute("PRAGMA data_version").fetchone()[0], version)

    def test_it_reads_through_a_read_only_connection(self):
        seen = []
        real = st_mod.connect

        def spy(path, readonly=False):
            seen.append(readonly)
            return real(path, readonly)
        with mock.patch.object(st_mod, "connect", spy):
            self.s.milestone_moves("ABC")
        self.assertEqual(seen, [True])
        con = connect(self.s.path, readonly=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("INSERT INTO applies (by_user, device) VALUES ('x', 'y')")
        finally:
            con.close()

    def test_the_fixed_field_list_has_no_internal_note_and_the_source_never_names_it(self):
        self.assertNotIn("internal_note", MOVE_FIELDS)
        self.assertNotIn("internal_note", MOVE_SQL)
        self.assertNotIn("internal_note", inspect.getsource(st_mod.Store.milestone_moves))
        self.assertEqual(MOVE_FIELDS, ("id", "baseline_date", "forecast_date", "actual_date", "status", "state", "state_reason",
                                       "movement", "note"))

    def test_the_read_is_not_part_of_the_page_load_or_the_published_file(self):
        for fn in (st_mod.Store.data_for, st_mod.Store.publish_inputs):
            self.assertNotIn("milestone_moves", inspect.getsource(fn))
            self.assertNotIn("MOVE_", inspect.getsource(fn))

    def test_the_query_uses_the_item_index_and_a_big_project_is_quick_and_small(self):
        con = self.s.con
        plan = " ".join(str(tuple(r)) for r in con.execute("EXPLAIN QUERY PLAN " + MOVE_SQL % ", ".join("?" * len(MOVE_FIELDS)),
                                                          ("ABC-M-", "ABC-M.") + MOVE_FIELDS))
        self.assertIn("change_log_item", plan)
        ms = [add_milestone(self.demo, "Big %d" % i) for i in range(59)] + [self.demo.milestone]
        con.execute("BEGIN")
        for m in ms:
            bulk(self.demo, m, "forecast_date", 20)
        for i in range(5000):
            con.execute("INSERT INTO change_log (apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                        "VALUES (1, 'actions', ?, 'owner', 'a', 'b', 'update', 'dashboard')", ("ABC-A-%04d" % i,))
        con.execute("COMMIT")
        t = time.perf_counter()
        got = self.s.milestone_moves("ABC")
        took = time.perf_counter() - t
        self.assertEqual(sum(b["total"] for b in got["milestones"].values()), 1200)
        self.assertLess(len(json.dumps(got)), 400 * 1024)
        self.assertLess(took, 1.0)


    def test_the_move_count_is_made_before_the_cut(self):
        bulk(self.demo, self.demo.milestone, "forecast_date", 120)
        block = self.s.milestone_moves("ABC")["milestones"][self.demo.milestone]
        self.assertEqual((block["total"], len(block["events"]), block["moves"]), (120, 50, 120))

    def test_a_step_is_never_split_by_either_cut(self):
        bulk(self.demo, self.demo.milestone, "forecast_date", 30, rows_per_step=3)      # 90 rows in 30 steps of three
        block = self.s.milestone_moves("ABC")["milestones"][self.demo.milestone]
        self.assertEqual((block["total"], len(block["events"])), (90, 48))               # sixteen whole steps, not 50 rows
        per_step = collections.Counter(e["step"] for e in block["events"])
        self.assertEqual(set(per_step.values()), {3})
        ms = [self.demo.milestone] + [add_milestone(self.demo, "S%d" % i) for i in range(1, 12)]
        for m in ms:
            bulk(self.demo, m, "forecast_date", 16, rows_per_step=3)                     # 48 rows each: 576 + the 90 before the project cut
        for m in ms:
            bulk(self.demo, m, "forecast_date", 5, rows_per_step=3)
        got = self.s.milestone_moves("ABC")
        self.assertTrue(got["truncated"])
        total = sum(len(b["events"]) for b in got["milestones"].values())
        self.assertLessEqual(total, 1000)
        for mid, b in got["milestones"].items():
            self.assertTrue(all(n == 3 for n in collections.Counter(e["step"] for e in b["events"]).values()), mid)

    def test_a_count_over_a_thousand_rows_is_still_right(self):
        ms = [self.demo.milestone] + [add_milestone(self.demo, "C%d" % i) for i in range(1, 25)]
        for m in ms:
            bulk(self.demo, m, "forecast_date", 45)
        got = self.s.milestone_moves("ABC")
        self.assertTrue(got["truncated"])
        self.assertLess(sum(len(b["events"]) for b in got["milestones"].values()), sum(b["total"] for b in got["milestones"].values()))
        self.assertTrue(all(b["moves"] == 45 for b in got["milestones"].values()))


if __name__ == "__main__":
    unittest.main()

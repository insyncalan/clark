"""#31: undo, copied from creaite's undo-changes (Head ruling on #31): a new step of ordinary rows with via "revert:<rowids>";
the step it reverses keeps undone_at NULL; a row changed since, or a creation something refers to, is skipped and named."""
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark.history import original_date
from clark import store as store_module
from clark.store import Invalid, now, open_store, reverted_rowids

REBASE = {"agreed_with": "Sponsor", "reason": "Scope grew", "source": "Steering, 01-10-2026"}


class Undo(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def rows(self, step):
        return self.s.con.execute("SELECT rowid, * FROM change_log WHERE apply_id = ? ORDER BY rowid", (step,)).fetchall()

    def test_an_update_is_put_back_as_a_new_step_of_ordinary_rows(self):
        a = self.demo.action()
        step = self.demo.update("actions", a, {"owner": "Sam Example", "priority": "High"})
        out = self.s.undo(step, USER)
        row = self.s.read("actions", ref=a)
        self.assertEqual((row["owner"], row["priority"]), ("TBC", "Medium"))
        self.assertNotEqual(out["step_id"], step)
        self.assertIsNone(self.s.con.execute("SELECT undone_at FROM applies WHERE apply_id = ?", (step,)).fetchone()[0])
        new = self.rows(out["step_id"])
        self.assertTrue(all(r["op"] in ("update", "insert") for r in new))
        self.assertTrue(all(r["via"].startswith("revert:") for r in new))
        put_back = {r["rowid"] for r in self.rows(step) if r["field"] not in ("updated_at", "note")}      # only these
        self.assertEqual({int(x) for x in new[0]["via"][len("revert:"):].split(",")}, put_back)
        self.assertEqual({d["rowid"] for d in out["reversed"]}, put_back)
        self.assertTrue(put_back <= reverted_rowids(self.s.con))
        undoes = self.s.con.execute("SELECT e.undoes FROM item_events e WHERE e.apply_id = ? AND e.undoes IS NOT NULL",
                                    (out["step_id"],)).fetchall()
        self.assertEqual(len(undoes), 2)

    def test_the_header_says_plainly_that_undoing_your_own_create_removes_the_row(self):
        header = " ".join((store_module.__doc__ or "").split())
        self.assertIn("undoing your own create is not deleting a record", header)
        self.assertIn("takes that row back out", header)

    def test_a_creation_is_removed(self):
        a = self.demo.action()
        out = self.s.undo(self.demo.last_step(), USER)
        self.assertIsNone(self.s.read("actions", ref=a))
        self.assertEqual(out["skipped"], [])
        removed = self.rows(out["step_id"])
        self.assertEqual([(r["field"], r["op"]) for r in removed], [("(removed)", "update")])

    def test_a_creation_with_its_labels_and_links_in_the_same_step_is_removed_whole(self):
        with self.s.step("dashboard", USER) as st:
            a = st.create("actions", {"project": "ABC", "description": "d", "raised": "2026-10-01", "source": "demo",
                                      "labels": "Sensitive"})
            st.create("links", {"from_item": a, "to_item": self.demo.milestone, "source": "demo"})
        out = self.s.undo(self.demo.last_step(), USER)
        self.assertEqual(out["skipped"], [])
        self.assertIsNone(self.s.read("actions", ref=a))
        self.assertEqual((self.s.read("links"), self.s.read("item_labels")), ([], []))

    def test_an_undo_twice_is_refused_and_an_unknown_step_too(self):
        a = self.demo.action()
        step = self.demo.update("actions", a, {"owner": "Sam Example"})
        self.s.undo(step, USER)
        with self.assertRaises(Invalid):
            self.s.undo(step, USER)
        with self.assertRaises(Invalid):
            self.s.undo(999, USER)

    def test_a_row_changed_since_is_skipped_and_named_and_the_rest_reversed(self):
        a = self.demo.action()
        b = self.demo.action(description="Book the venue")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"owner": "Sam Example"})
            st.update("actions", b, {"owner": "Sam Example"})
        step = self.demo.last_step()
        later = self.demo.update("actions", a, {"owner": "Lee Example"})
        out = self.s.undo(step, USER)
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Lee Example")
        self.assertEqual(self.s.read("actions", ref=b)["owner"], "TBC")
        self.assertEqual([(x["ref"], x["why"], x["by_step"]) for x in out["skipped"]],
                         [(a, "has changed since: left as it is", later)])

    def test_a_change_between_reading_and_undoing_is_seen(self):
        # The check runs inside the undo's own lock: a write by another connection before it is never missed.
        a = self.demo.action()
        step = self.demo.update("actions", a, {"owner": "Sam Example"})
        from clark.store import open_store
        other = open_store(self.demo.dir / "clark.db", onedrive_roots=[])
        with other.step("excel", USER) as st:
            st.update("actions", a, {"owner": "Lee Example"})
        other.close()
        out = self.s.undo(step, USER)
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Lee Example")
        self.assertEqual([x["why"] for x in out["skipped"]], ["has changed since: left as it is"])

    def test_a_creation_something_refers_to_is_skipped_and_named(self):
        with self.s.step("dashboard", USER) as st:
            m = st.create("milestones", {"project": "ABC", "name": "Second", "source": "demo"})
        made = self.demo.last_step()
        self.demo.action(milestone=m)
        out = self.s.undo(made, USER)
        self.assertIsNotNone(self.s.read("milestones", ref=m))
        self.assertTrue(out["skipped"])
        self.assertTrue(all("something refers to it now (an action ABC-A-" in x["why"] for x in out["skipped"]))

    def test_a_new_label_still_on_an_item_is_skipped(self):
        with self.s.step("dashboard", USER) as st:
            st.create("labels", {"name": "Watch"})
        made = self.demo.last_step()
        self.demo.action(labels="Watch")
        out = self.s.undo(made, USER)
        self.assertIsNotNone(self.s.read("labels", ref="Watch"))
        self.assertTrue(all("a label on an item" in x["why"] for x in out["skipped"]))

    def test_links_and_labels_are_removed_and_put_back(self):
        a = self.demo.action(labels="Sensitive")
        with self.s.step("dashboard", USER) as st:
            st.create("links", {"from_item": a, "to_item": self.demo.milestone, "source": "demo"})
        with self.s.step("dashboard", USER) as st:
            st.cancel("links", f"{a}|{self.demo.milestone}|blocks")
            st.update("actions", a, {"labels": []})
        step = self.demo.last_step()
        self.assertEqual(self.s.read("links"), [])
        self.s.undo(step, USER)
        self.assertEqual(len(self.s.read("links")), 1)
        self.assertEqual(self.s.con.execute("SELECT label FROM item_labels WHERE item_id = ?", (a,)).fetchall()[0][0],
                         "Sensitive")

    def test_restores_go_through_the_checks(self):
        # Put back a workstream that has since been closed: the validated path refuses it, so the row is skipped and named.
        a = self.demo.action(workstream="Build")
        step = self.demo.update("actions", a, {"workstream": None})
        with self.s.step("dashboard", USER) as st:
            st.cancel("workstreams", self.s.read("workstreams", "ABC")[0]["id"])
        out = self.s.undo(step, USER)
        self.assertIsNone(self.s.read("actions", ref=a)["workstream"])
        self.assertIn("isn't an active workstream", out["skipped"][0]["why"])

    def test_a_derived_field_follows_the_others(self):
        a = self.demo.action()
        step = self.demo.update("actions", a, {"status": "Closed"})
        closed = self.s.read("actions", ref=a)["closed"]
        self.assertTrue(closed)
        out = self.s.undo(step, USER)
        row = self.s.read("actions", ref=a)
        self.assertEqual((row["status"], row["closed"]), ("Open", None))
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01",
                                   "source": "demo", "impact": "Low", "likelihood": "Low"})
        with self.s.step("dashboard", USER) as st:
            st.update("raid", r, {"impact": "High", "priority": "Low"})
        out = self.s.undo(self.demo.last_step(), USER)
        self.assertEqual(self.s.read("raid", ref=r)["priority"], "Low")      # worked out from impact Low, likelihood Low
        self.assertEqual(out["skipped"], [])

    def test_a_health_change_takes_its_reason_back_too(self):
        step = self.demo.update("projects", "ABC", {"health": "At risk", "health_reason": "Vendor late"})
        self.s.undo(step, USER)
        p = self.s.read("projects", ref="ABC")
        self.assertEqual((p["health"], p["health_reason"]), ("On track", None))

    def test_an_undo_of_an_undo_puts_the_change_back_in_force(self):
        m = self.demo.milestone
        change = self.demo.update("milestones", m, {"baseline_date": "2030-04-01"}, rebaseline=REBASE)
        first = self.s.undo(change, USER)
        self.assertEqual(self.s.read("milestones", ref=m)["baseline_date"], "2030-03-01")
        self.assertEqual(self.s.read("decisions", "ABC"), [])          # the rebaseline's decision goes with it
        self.s.undo(first["step_id"], USER)
        self.assertEqual(self.s.read("milestones", ref=m)["baseline_date"], "2030-04-01")
        self.assertEqual(len(self.s.read("decisions", "ABC")), 1)
        self.assertIsNone(self.s.con.execute("SELECT undone_at FROM applies WHERE apply_id = ?", (change,)).fetchone()[0])
        self.assertIsNotNone(self.s.con.execute("SELECT undone_at FROM applies WHERE apply_id = ?",
                                                (first["step_id"],)).fetchone()[0])
        self.assertEqual(original_date(self.s.con, m), "2030-03-01")
        events = [e for e in self.s.history(m) if e["field"] == "baseline_date"]
        original = next(e for e in events if e["step"] == change)
        self.assertTrue(original["in_force"])
        self.assertFalse(next(e for e in events if e["step"] == first["step_id"])["in_force"])
        self.assertEqual(events[0]["after"], "2030-04-01")
        self.assertTrue(events[0]["in_force"])

    def test_original_date_skips_a_creation_that_was_undone(self):
        with self.s.step("dashboard", USER) as st:
            m = st.create("milestones", {"project": "ABC", "name": "Second", "baseline_date": "2030-05-01", "source": "demo"})
        self.s.undo(self.demo.last_step(), USER)
        self.assertIsNone(original_date(self.s.con, m))

    # ---- Full review of #31 at 158eefe: the HIGH, the MEDIUM and the LOWs ----
    def milestone_step_then_reference(self):
        """A step that creates a milestone and an action; then a later action points at the milestone."""
        with self.s.step("dashboard", USER) as st:
            m = st.create("milestones", {"project": "ABC", "name": "Second", "baseline_date": "2030-05-01", "source": "demo"})
            first = st.create("actions", {"project": "ABC", "description": "d", "raised": "2026-10-01", "source": "demo"})
        step = self.demo.last_step()
        later = self.demo.action(milestone=m)
        return step, m, first, later

    def test_HIGH_a_partial_undo_names_only_the_rows_it_put_back(self):
        step, m, first, later = self.milestone_step_then_reference()
        out = self.s.undo(step, USER)
        self.assertIsNone(self.s.read("actions", ref=first))                    # put back (removed)
        self.assertIsNotNone(self.s.read("milestones", ref=m))                  # skipped: something refers to it
        self.assertEqual([x["ref"] for x in out["skipped"]], [m])               # one entry for the item, not one per field
        self.assertIn(f"an action {later}", out["skipped"][0]["why"])           # the referring row is named
        # the skipped milestone is still in force: its creation, its original date, and a second undo of the step
        self.assertEqual(original_date(self.s.con, m), "2030-05-01")
        created = [e for e in self.s.history(m) if e["field"] == "baseline_date" and not e["is_undo"]]
        self.assertTrue(created[0]["in_force"])
        self.s.con.execute("DELETE FROM actions WHERE id = ?", (later,))        # (test set-up only) the reference goes
        again = self.s.undo(step, USER)                                         # so the rest of the step can be undone now
        self.assertIsNone(self.s.read("milestones", ref=m))
        self.assertEqual({(x["ref"], x["why"]) for x in again["skipped"]}, {(first, "already undone")})   # put back the first time

    def test_MEDIUM_an_undo_that_puts_nothing_back_marks_nothing(self):
        step, m, first, later = self.milestone_step_then_reference()
        self.s.undo(step, USER)                                                 # puts the action back, skips the milestone
        before = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        a = self.demo.action()
        change = self.demo.update("actions", a, {"owner": "Sam Example"})
        self.demo.update("actions", a, {"owner": "Lee Example"})                # now the first change can't be put back
        out = self.s.undo(change, USER)
        self.assertEqual((out["step_id"], out["reversed"]), (None, []))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], before + 3)   # the three steps just made; the undo wrote none
        self.assertIsNone(self.s.con.execute("SELECT undone_at FROM applies WHERE apply_id = ?", (change,)).fetchone()[0])
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Lee Example")

    def test_MEDIUM_an_undo_of_an_undo_is_refused_a_third_time_and_history_stays_true(self):
        a = self.demo.action()
        change = self.demo.update("actions", a, {"owner": "Sam Example"})
        first = self.s.undo(change, USER)["step_id"]
        second = self.s.undo(first, USER)["step_id"]                            # the change is back
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Sam Example")
        with self.assertRaises(Invalid) as e:
            self.s.undo(second, USER)                                           # undoing the undo of an undo: refused
        self.assertIn("can't be undone again", str(e.exception))
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Sam Example")
        owner = [x for x in self.s.history(a) if x["field"] == "owner"]
        self.assertEqual([(x["step"], x["in_force"]) for x in owner if x["step"] == change], [(change, True)])
        self.assertTrue(all(x["in_force"] for x in owner if x["step"] in (change, second)))
        self.assertFalse(any(x["in_force"] for x in owner if x["step"] == first))
        # the change in force can be undone again, cleanly
        self.s.undo(change, USER)
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "TBC")

    def test_LOW_health_back_alone_still_needs_its_reason(self):
        step = self.demo.update("projects", "ABC", {"health": "At risk", "health_reason": "Vendor late"})
        con = self.s.con
        row = {"table": "projects", "op": "update", "id": "ABC", "changes": {"health": "On track"}, "revert": True}
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                store_module.write_item(con, row, st)
        self.assertEqual(self.s.read("projects", ref="ABC")["health"], "At risk")
        self.assertIsNotNone(step)

    def test_LOW_the_ids_run_out_with_a_plain_message(self):
        self.s.con.execute("INSERT INTO actions (id, project, description, raised, source) VALUES "
                           "('ABC-A-999', 'ABC', 'last', '2026-10-01', 'demo')")
        with self.assertRaises(Invalid) as e:
            self.demo.action()
        self.assertIn("used every number", str(e.exception))

    def test_LOW_a_database_rule_during_an_undo_skips_the_row_and_says_so(self):
        a = self.demo.action()
        b = self.demo.action(description="Book the venue")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"owner": "Sam Example"})
            st.update("actions", b, {"owner": "Sam Example"})
        step = self.demo.last_step()
        real = store_module.write_item

        def refuse_a(con, item, st):
            if item.get("id") == a:
                raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")
            return real(con, item, st)

        with mock.patch.object(store_module, "write_item", refuse_a):
            out = self.s.undo(step, USER)
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Sam Example")
        self.assertEqual(self.s.read("actions", ref=b)["owner"], "TBC")
        self.assertEqual([(x["ref"], x["why"]) for x in out["skipped"]], [(a, "other data depends on it: left as it is")])

    def test_LOW_times_are_utc_to_the_millisecond(self):
        from datetime import datetime, timedelta, timezone
        self.assertEqual(store_module.clock().utcoffset(), timedelta(0))           # the real clock is UTC
        at = datetime(2030, 1, 2, 3, 4, 5, 678901, tzinfo=timezone.utc)
        with mock.patch.object(store_module, "clock", lambda: at):                 # a fixed clock: no minute boundary to flake on
            self.assertEqual(now(), "2030-01-02 03:04:05.678")
            a = self.demo.action()
        row = self.s.con.execute("SELECT at FROM applies ORDER BY apply_id DESC LIMIT 1").fetchone()
        self.assertEqual(row["at"], "2030-01-02 03:04:05.678")
        self.assertEqual(self.s.con.execute("SELECT at FROM change_log WHERE item_id = ? LIMIT 1", (a,)).fetchone()["at"],
                         "2030-01-02 03:04:05.678")
        local = datetime(2030, 1, 2, 7, 4, 5, tzinfo=timezone(timedelta(hours=4)))      # a clock that isn't UTC is converted
        with mock.patch.object(store_module, "clock", lambda: local.astimezone(timezone.utc)):
            self.assertEqual(now(), "2030-01-02 03:04:05.000")

    def two_changes_in_one_step(self, kind, ref, field, values):
        with self.s.step("dashboard", USER) as st:
            for v in values:
                st.update(kind, ref, {field: v})
        return self.demo.last_step()

    def test_MEDIUM_an_owner_changed_twice_in_one_step_goes_back_to_the_original(self):
        a = self.demo.action()
        step = self.two_changes_in_one_step("actions", a, "owner", ["Sam Example", "Pat Example"])
        out = self.s.undo(step, USER)
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "TBC")
        self.assertEqual(out["skipped"], [])
        owner_rows = [r["rowid"] for r in self.rows(step) if r["field"] == "owner"]
        self.assertEqual({d["rowid"] for d in out["reversed"] if d["field"] == "owner"}, set(owner_rows))   # both rows named
        self.assertTrue(set(owner_rows) <= reverted_rowids(self.s.con))
        again = self.s.undo(out["step_id"], USER)                                # and undoing the undo puts Pat back
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Pat Example")
        self.assertEqual(again["skipped"], [])
        with self.assertRaises(Invalid):
            self.s.undo(again["step_id"], USER)                                  # a third time is refused
        self.s.undo(step, USER)                                                  # the change is in force, so it undoes cleanly
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "TBC")

    def test_MEDIUM_a_status_changed_twice_in_one_step_goes_back_to_the_original(self):
        a = self.demo.action()
        step = self.two_changes_in_one_step("actions", a, "status", ["Delayed", "Closed"])
        self.assertTrue(self.s.read("actions", ref=a)["closed"])
        out = self.s.undo(step, USER)
        row = self.s.read("actions", ref=a)
        self.assertEqual((row["status"], row["closed"]), ("Open", None))
        self.assertEqual(out["skipped"], [])
        again = self.s.undo(out["step_id"], USER)
        row = self.s.read("actions", ref=a)
        self.assertEqual((row["status"], bool(row["closed"])), ("Closed", True))
        self.assertEqual(again["skipped"], [])
        owner = [e for e in self.s.history(a) if e["field"] == "status" and e["step"] == step]
        self.assertTrue(all(e["in_force"] for e in owner))

    def test_a_field_changed_twice_and_then_changed_again_is_skipped_and_named(self):
        a = self.demo.action()
        step = self.two_changes_in_one_step("actions", a, "owner", ["Sam Example", "Pat Example"])
        later = self.demo.update("actions", a, {"owner": "Lee Example"})
        out = self.s.undo(step, USER)
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Lee Example")
        self.assertEqual([(x["ref"], x["field"], x["by_step"]) for x in out["skipped"]], [(a, "owner", later)])

    def test_health_changed_twice_in_one_step_takes_both_reasons_back(self):
        with self.s.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"health": "At risk", "health_reason": "Vendor late"})
            st.update("projects", "ABC", {"health": "Off track", "health_reason": "Vendor withdrew"})
        out = self.s.undo(self.demo.last_step(), USER)
        p = self.s.read("projects", ref="ABC")
        self.assertEqual((p["health"], p["health_reason"], out["skipped"]), ("On track", None, []))

    def test_LOW_a_group_rolled_back_leaves_no_stale_step_id(self):
        a = self.demo.action()
        b = self.demo.action(description="Book the venue")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"owner": "Sam Example"})
            st.update("actions", b, {"owner": "Sam Example"})
        step = self.demo.last_step()
        real, calls = store_module.write_item, []

        def fail_after_the_first_log(con, item, st):
            result = real(con, item, st)
            calls.append(item["id"])
            if len(calls) == 1:                                   # the first group has logged (and made the applies row)
                raise sqlite3.IntegrityError("FOREIGN KEY constraint failed")
            return result

        with mock.patch.object(store_module, "write_item", fail_after_the_first_log):
            out = self.s.undo(step, USER)
        self.assertEqual(len(out["skipped"]), 1)
        self.assertEqual(out["skipped"][0]["why"], "other data depends on it: left as it is")
        self.assertEqual(len(out["reversed"]) > 0, True)                                   # the other group was not wrongly skipped
        self.assertIsNotNone(out["step_id"])
        self.assertIsNotNone(self.s.con.execute("SELECT 1 FROM applies WHERE apply_id = ?", (out["step_id"],)).fetchone())
        self.assertEqual({self.s.read("actions", ref=x)["owner"] for x in (a, b)}, {"Sam Example", "TBC"})


class Opening(unittest.TestCase):
    def tearDown(self):
        self.demo.close()

    def setUp(self):
        self.demo = DemoStore()

    def test_a_file_that_is_not_a_database_is_refused_plainly(self):
        bad = self.demo.dir / "notes.db"
        bad.write_text("this is not a database, just some words " * 20, encoding="utf-8")
        with self.assertRaises(Invalid) as e:
            open_store(bad, onedrive_roots=[])
        self.assertIn("not a database clark can read", str(e.exception))

    def test_a_database_that_is_not_clarks_is_refused_plainly(self):
        other = self.demo.dir / "other.db"
        con = sqlite3.connect(other)
        con.execute("CREATE TABLE x (y)")
        con.commit()
        con.close()
        with self.assertRaises(Invalid) as e:
            open_store(other, onedrive_roots=[])
        self.assertIn("not one clark made", str(e.exception))

    def test_a_damaged_version_is_refused_plainly(self):
        self.demo.store.con.execute("UPDATE meta SET v = 'abc' WHERE k = 'schema_version'")
        with self.assertRaises(Invalid) as e:
            open_store(self.demo.dir / "clark.db", onedrive_roots=[])
        self.assertIn("no usable version", str(e.exception))

    def test_a_lock_held_too_long_is_said_plainly(self):
        holder = sqlite3.connect(self.demo.dir / "clark.db", isolation_level=None)
        holder.execute("BEGIN IMMEDIATE")
        self.addCleanup(holder.close)
        self.demo.store.con.execute("PRAGMA busy_timeout = 100")
        with self.assertRaises(Invalid) as e:
            with self.demo.store.step("dashboard", USER):
                pass
        self.assertIn("in use by something else", str(e.exception))


if __name__ == "__main__":
    unittest.main()

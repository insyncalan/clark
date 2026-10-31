"""#123 (guarded store side): every writer's history row carries who, how (route and place), field, from and to; the UTC offset is
written with each step; undo and undoing a create are recorded; the new places go through /api/change; the migration from
versions 1 and 2; history is never pruned.

Run: python3 dev/run_tests.py test_store_history_rows
"""
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

import _workbook as wbk
from _demo import USER, DemoStore
from clark import changes, store as store_module
from clark import excel_import as xi
from clark.store import Invalid, connect, migrate, open_store

from test_store_migration import make_v1, version

ROWS = ("SELECT a.by_user, a.utc_offset, e.route, e.place, e.src_ref, e.undoes, e.event_id, c.tbl, c.item_id, c.field, c.old_value, "
        "c.new_value FROM change_log c JOIN item_events e ON e.change = c.rowid JOIN applies a ON a.apply_id = c.apply_id "
        "WHERE c.apply_id = ? AND c.field NOT IN ('updated_at') ORDER BY c.rowid")
OFFSET = "[+-][0-9][0-9]:[0-9][0-9]"


class Rows(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.a = self.demo.action(owner="Sara Khan")

    def rows(self, step):
        return [dict(r) for r in self.s.con.execute(ROWS, (step,))]

    def item(self, place, **to):
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.a, "changes": to, "place": place})
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body["apply_id"]

    def only(self, step):
        (row,) = self.rows(step)
        return row

    def test_a_change_from_each_place_the_page_sends_is_kept_with_who_how_field_from_and_to(self):
        for n, place in enumerate(("cell", "peek", "board", "eye", "draft", "email", "text", "menu", "report")):
            with self.subTest(place=place):
                row = self.only(self.item(place, owner=f"Person {n}"))
                self.assertEqual((row["by_user"], row["route"], row["place"], row["tbl"], row["item_id"], row["field"], row["new_value"]),
                                 (USER, "dashboard", place, "actions", self.a, "owner", f"Person {n}"))
                self.assertEqual(row["old_value"], "Sara Khan" if n == 0 else f"Person {n - 1}")
                self.assertRegex(row["utc_offset"], "^" + OFFSET.replace("[0-9]", "[0-9]") + "$")

    def test_a_place_the_page_does_not_have_is_refused_and_writes_nothing(self):
        before = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        for place in ("ask", "bulk", "excel", "dashboard", "undo", "lobby"):
            with self.subTest(place=place):
                status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.a,
                                            "changes": {"owner": "X Y"}, "place": place})
                self.assertEqual((status, body["message"]), (400, changes.BAD_PLACE))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], before)

    def test_the_store_takes_all_the_places_and_refuses_others(self):
        for place in store_module.PLACES:
            with self.subTest(place=place):
                with self.s.step("dashboard", USER, place=place) as st:
                    st.update("actions", self.a, {"owner": f"At {place}"})
        for place in ("undo", "selection", "assistant", "Peek"):
            with self.subTest(place=place), self.assertRaises(Invalid):
                with self.s.step("dashboard", USER, place=place) as st:
                    st.update("actions", self.a, {"owner": "No one"})

    def test_a_new_item_is_one_insert_row_per_column_with_the_place(self):
        with self.s.step("dashboard", USER, place="peek") as st:
            ref = st.create("actions", {"project": "ABC", "description": "Order the laptops", "raised": "2026-10-01", "source": "demo"})
        rows = self.rows(self.demo.last_step())
        self.assertTrue(rows and all(r["item_id"] == ref and r["route"] == "dashboard" and r["place"] == "peek" and r["by_user"] == USER
                                     for r in rows))
        self.assertEqual([r["new_value"] for r in rows if r["field"] == "description"], ["Order the laptops"])
        self.assertEqual({r["old_value"] for r in rows if r["field"] == "description"}, {None})

    def test_a_report_section_new_update_and_delete_keep_their_rows(self):
        ok = lambda **r: self.change({"project": "ABC", "kind": "report_sections", "place": "report", **r})
        status, body = ok(op="new", values={"title": "Risks I watch"})
        self.assertEqual(status, 200, body)
        made = [r for r in self.rows(body["apply_id"]) if r["field"] == "title"]
        self.assertEqual((made[0]["new_value"], made[0]["place"], made[0]["route"], made[0]["by_user"]), ("Risks I watch", "report", "dashboard", USER))
        sid = made[0]["item_id"]
        status, body = ok(op="update", id=sid, changes={"title": "Renamed"})
        row = self.only(body["apply_id"])
        self.assertEqual((row["field"], row["old_value"], row["new_value"], row["place"]), ("title", "Risks I watch", "Renamed", "report"))
        status, body = ok(op="delete", id=sid)
        self.assertEqual(status, 200, body)
        gone = [r for r in self.rows(body["apply_id"]) if r["field"] == store_module.REMOVED]
        self.assertEqual((len(gone), gone[0]["place"], gone[0]["new_value"]), (1, "report", None))
        self.assertIn("Renamed", gone[0]["old_value"])

    def test_cancel_keeps_the_status_change_with_the_place(self):
        with self.s.step("dashboard", USER, place="menu") as st:
            st.cancel("actions", self.a)
        row = next(r for r in self.rows(self.demo.last_step()) if r["field"] == "status")
        self.assertEqual((row["new_value"], row["place"], row["route"]), ("Cancelled", "menu", "dashboard"))

    def test_archive_of_an_item_is_one_archived_row_with_the_place(self):
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "archive", "id": self.a, "place": "menu"})
        self.assertEqual(status, 200, body)
        row = next(r for r in self.rows(body["apply_id"]) if r["field"] == "archived")
        self.assertEqual((row["old_value"], row["new_value"], row["place"], row["by_user"]), ("0", "1", "menu", USER))

    def test_archiving_a_project_writes_one_archived_row_per_item_in_one_step(self):
        a2 = self.demo.action(description="Second")
        with self.s.step("dashboard", USER, place="menu") as st:
            st.archive("projects", "ABC")
        step = self.demo.last_step()
        rows = [r for r in self.rows(step) if r["field"] == "archived"]
        ids = {r["item_id"] for r in rows}
        self.assertTrue({self.a, a2, "ABC", self.demo.milestone, self.demo.use_case} <= ids, ids)
        self.assertEqual(len(rows), len(ids), "one row per item")
        self.assertTrue(all((r["old_value"], r["new_value"], r["place"], r["by_user"]) == ("0", "1", "menu", USER) for r in rows))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies WHERE apply_id = ?", (step,)).fetchone()[0], 1)

    def test_excel_import_keeps_route_place_file_name_and_each_field(self):
        tmp = Path(tempfile.mkdtemp(prefix="clark-xl-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        path = wbk.make_workbook(self.s, tmp / "plan.xlsx")
        wbk.edit(path, "Actions", self.a, description="Draft the cut-over plan v2", owner="Sam Example")
        plan = xi.read_workbook(self.s, path, "ABC", allow_unrecorded=True)
        plan.accept_all()
        res = xi.apply_import(self.s, plan, "Import Person")
        self.assertTrue(res.applied, res.message)
        rows = self.rows(res.step_id)
        self.assertEqual({(r["field"], r["old_value"], r["new_value"]) for r in rows},
                         {("description", "Draft the cut-over plan", "Draft the cut-over plan v2"), ("owner", "Sara Khan", "Sam Example")})
        self.assertTrue(all((r["by_user"], r["route"], r["place"]) == ("Import Person", "excel", "excel") for r in rows))
        self.assertTrue(all("plan.xlsx" in r["src_ref"] and "\n" not in r["src_ref"] for r in rows), rows[0]["src_ref"])   # as excel_import writes it today

    def test_undo_of_a_change_is_one_row_per_field_with_the_place_and_the_event_it_puts_back(self):
        first = self.item("cell", owner="Sam Example", priority="High")
        was = {r["field"]: r for r in self.rows(first)}
        status, body = self.undo({"project": "ABC", "apply_id": first, "place": "peek"})
        self.assertEqual(status, 200, body)
        rows = {r["field"]: r for r in self.rows(body["apply_id"])}
        self.assertEqual(set(rows), {"owner", "priority"})
        for f, r in rows.items():
            self.assertEqual((r["by_user"], r["route"], r["place"], r["old_value"], r["new_value"], r["undoes"]),
                             (USER, "undo", "peek", was[f]["new_value"], was[f]["old_value"], was[f]["event_id"]))

    def test_an_undo_with_no_place_keeps_none_and_an_unknown_place_is_refused(self):
        first = self.item("cell", owner="Sam Example")
        status, body = self.undo({"project": "ABC", "apply_id": first, "place": "lobby"})
        self.assertEqual((status, body["message"]), (400, changes.BAD_PLACE))
        status, body = self.undo({"project": "ABC", "apply_id": first})
        self.assertEqual(status, 200, body)
        self.assertEqual((self.only(body["apply_id"])["route"], self.only(body["apply_id"])["place"]), ("undo", None))

    def test_undoing_a_create_is_recorded_as_one_removed_row_that_points_at_the_create(self):
        with self.s.step("dashboard", USER, place="peek") as st:
            ref = st.create("actions", {"project": "ABC", "description": "Order the laptops", "raised": "2026-10-01", "source": "demo"})
        made = self.rows(self.demo.last_step())
        out = self.s.undo(self.demo.last_step(), USER, place="menu")
        rows = self.rows(out["step_id"])
        removed = [r for r in rows if r["field"] == store_module.REMOVED]
        self.assertEqual(len(removed), 1)
        r = removed[0]
        self.assertEqual((r["item_id"], r["by_user"], r["route"], r["place"], r["new_value"]), (ref, USER, "undo", "menu", None))
        self.assertIn("Order the laptops", r["old_value"])
        self.assertIn(r["undoes"], {m["event_id"] for m in made})

    def test_undo_of_an_undo_is_recorded_too(self):
        first = self.item("cell", owner="Sam Example")
        out = self.s.undo(first, USER, place="cell")
        again = self.s.undo(out["step_id"], USER, place="peek")
        row = self.only(again["step_id"])
        self.assertEqual((row["route"], row["place"], row["new_value"], row["by_user"]), ("undo", "peek", "Sam Example", USER))


class Offset(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.a = self.demo.action()
        self.had = os.environ.get("TZ")
        self.addCleanup(self.restore_zone)

    def restore_zone(self):
        if self.had is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.had
        time.tzset()

    def zone(self, name):
        os.environ["TZ"] = name
        time.tzset()

    def stamp(self, owner):
        with self.s.step("dashboard", USER) as st:
            st.update("actions", self.a, {"owner": owner})
        return self.s.con.execute("SELECT utc_offset FROM applies WHERE apply_id = ?", (self.demo.last_step(),)).fetchone()[0]

    def test_the_offset_is_the_machines_at_the_time_and_stays_when_the_zone_changes(self):
        got = {}
        for name, want in (("UTC0", "+00:00"), ("<+04>-4", "+04:00"), ("<+0530>-5:30", "+05:30"), ("<-0330>3:30", "-03:30")):
            self.zone(name)
            got[name] = (self.stamp(f"Owner in {name}"), want)
        self.assertTrue(all(a == b for a, b in got.values()), got)
        self.zone("<+12>-12")
        offsets = [r[0] for r in self.s.con.execute("SELECT utc_offset FROM applies ORDER BY apply_id DESC LIMIT 4")]
        self.assertEqual(offsets[::-1], ["+00:00", "+04:00", "+05:30", "-03:30"], "a row keeps the zone it was made in")

    def test_summer_time_is_the_offset_of_that_moment(self):
        self.zone("CET-1CEST,M3.5.0,M10.5.0/3")
        july, january = datetime(2026, 7, 1, 12, tzinfo=timezone.utc), datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        with mock.patch.object(store_module, "clock", return_value=july):
            self.assertEqual(store_module.local_offset(), "+02:00")
        with mock.patch.object(store_module, "clock", return_value=january):
            self.assertEqual(store_module.local_offset(), "+01:00")

    def test_a_step_is_written_with_the_function_the_test_replaces(self):
        with mock.patch.object(store_module, "local_offset", return_value="+09:00"):
            self.assertEqual(self.stamp("Someone Else"), "+09:00")

    def test_the_column_refuses_text_that_is_not_an_offset(self):
        for bad in ("UTC", "+4:00", "+04:0", "0400", "+04:00 ", "+0400x"):
            with self.subTest(bad=bad), self.assertRaises(sqlite3.IntegrityError):
                self.s.con.execute("UPDATE applies SET utc_offset = ? WHERE apply_id = 1", (bad,))


# A real offset: a sign, hours 00 to 14, minutes 00, 15, 30 or 45, at most +14:00 or -14:00. UTC is written as '+00:00' (local_offset
# never writes 'Z' or '-00:00', so neither is accepted). Shared by the column, the migrated column and the store's own check.
REAL_OFFSETS = ("+00:00", "+04:00", "-12:00", "+05:45", "+05:30", "-03:30", "+14:00", "-14:00", "+12:45", "-09:30")
NOT_OFFSETS = ("+99:99", "+14:30", "+14:15", "+15:00", "+24:00", "+23:59", "+04:10", "+04:60", "-00:00", "Z", "00:00", "+04:00\n",
               "+\u0664\u0664:00", "", "garbage", "+04.00", "++4:00")


def refuses_and_takes(case, con):
    """The applies.utc_offset CHECK on `con` takes every REAL_OFFSETS value and refuses every NOT_OFFSETS one."""
    for good in REAL_OFFSETS:
        with case.subTest(good=good):
            con.execute("UPDATE applies SET utc_offset = ? WHERE apply_id = 1", (good,))
    for bad in NOT_OFFSETS:
        with case.subTest(bad=bad), case.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE applies SET utc_offset = ? WHERE apply_id = 1", (bad,))


class RealOffset(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.a = self.demo.action()

    def test_the_column_takes_a_real_offset_and_refuses_one_beyond_14_hours_or_off_the_quarter_hour(self):
        refuses_and_takes(self, self.s.con)

    def test_the_store_check_agrees_with_the_column(self):
        for good in REAL_OFFSETS:
            self.assertEqual(store_module.checked_offset(good), good)
        for bad in NOT_OFFSETS + (None, 4, b"+04:00"):
            self.assertIsNone(store_module.checked_offset(bad), repr(bad))

    def test_an_odd_machine_offset_is_written_as_zone_not_recorded_and_the_step_still_goes_in(self):
        for odd in ("+99:99", "+14:15", "+05:20"):
            with self.subTest(odd=odd), mock.patch.object(store_module, "local_offset", return_value=odd):
                with self.s.step("dashboard", USER) as st:
                    st.update("actions", self.a, {"owner": f"Owner {odd}"})
                got = self.s.con.execute("SELECT utc_offset FROM applies WHERE apply_id = ?", (self.demo.last_step(),)).fetchone()[0]
                self.assertIsNone(got)


class NeverPruned(unittest.TestCase):
    def test_no_writer_deletes_a_history_row(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = demo.store
        a = demo.action(owner="Sara Khan")
        for table in ("change_log", "item_events", "applies"):
            s.con.execute(f"CREATE TRIGGER keep_{table} BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'history is never pruned'); END")
        change = changes.make_change(s.path, [], USER)
        undo = changes.make_undo(s.path, [], USER)
        counts = lambda: tuple(s.con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("change_log", "item_events", "applies"))
        seen = counts()
        steps = []
        def run(req):
            nonlocal seen
            status, body = change(req)
            self.assertEqual((status, body.get("message")), (200, None), body)
            steps.append(body["apply_id"])
            now = counts()
            self.assertTrue(all(n >= o for n, o in zip(now, seen)))
            seen = now
        run({"project": "ABC", "kind": "actions", "op": "update", "id": a, "changes": {"owner": "X Y"}, "place": "peek"})
        run({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"title": "Mine"}, "place": "report"})
        sid = s.read("report_sections", "ABC")[-1]["id"]
        run({"project": "ABC", "kind": "report_sections", "op": "delete", "id": sid, "place": "report"})
        run({"project": "ABC", "kind": "actions", "op": "archive", "id": a, "place": "menu"})
        run({"project": "ABC", "kind": "actions", "op": "restore", "id": a, "place": "menu"})
        with s.step("dashboard", USER, place="peek") as st:
            made = st.create("actions", {"project": "ABC", "description": "Another", "raised": "2026-10-01", "source": "demo"})
        steps.append(demo.last_step())
        for step in (steps[-1], steps[0], steps[2]):                 # a create, a change, a section's removal
            status, body = undo({"project": "ABC", "apply_id": step, "place": "cell"})
            self.assertIn(status, (200, 400, 409), body)
        with s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        with s.step("dashboard", USER) as st:
            st.restore("projects", "ABC")
        tmp = Path(tempfile.mkdtemp(prefix="clark-xl-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        path = wbk.make_workbook(s, tmp / "plan.xlsx")
        wbk.edit(path, "Actions", a, description="Changed in Excel")
        plan = xi.read_workbook(s, path, "ABC", allow_unrecorded=True)
        plan.accept_all()
        self.assertTrue(xi.apply_import(s, plan, USER).applied)
        self.assertEqual(s.con.execute("SELECT count(*) FROM change_log WHERE via LIKE 'revert:%'").fetchone()[0] > 0, True)
        self.assertGreaterEqual(counts()[0], seen[0])
        with self.assertRaises(sqlite3.DatabaseError):               # the guard itself is live
            s.con.execute("DELETE FROM item_events")
        self.assertEqual(counts()[1] > 0, True)


# item_events as version 3 (Word, #48) made it and version 4 kept it: the route 'word', the places before #123. Frozen here, so a
# file at version 3 or 4 is the one a released clark wrote, whatever schema.sql says today.
VERSION_3_ITEM_EVENTS = """CREATE TABLE item_events_old (
  event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  apply_id   INTEGER REFERENCES applies(apply_id),
  item_id    TEXT NOT NULL,
  change     INTEGER,
  kind       TEXT NOT NULL CHECK (kind IN ('change','reject')),
  route      TEXT NOT NULL CHECK (route IN ('dashboard','assistant','excel','undo','client','team','migrate','word')),
  place      TEXT CHECK (place IS NULL OR place IN ('peek','cell','bulk','menu','report','dashboard','excel','board')),
  origin     TEXT CHECK (origin IS NULL OR origin IN ('report','sneak')),
  actor      TEXT NOT NULL CHECK (actor IN ('you','clark')),
  src_ref    TEXT CHECK (src_ref IS NULL OR (length(src_ref) <= 300 AND instr(src_ref, char(10)) = 0)),
  undoes     INTEGER REFERENCES item_events(event_id)
)"""


def as_version_3_made_it(path):
    """Give the file at `path` (version 3 or 4, no rows yet) the item_events table a released version 3 or 4 made."""
    con = sqlite3.connect(str(path), isolation_level=None)
    try:
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("BEGIN")
        con.execute(VERSION_3_ITEM_EVENTS)
        con.execute("INSERT INTO item_events_old SELECT * FROM item_events")
        con.execute("DROP TABLE item_events")
        con.execute("ALTER TABLE item_events_old RENAME TO item_events")
        con.execute("CREATE INDEX IF NOT EXISTS item_events_item ON item_events(item_id)")
        con.execute("CREATE INDEX IF NOT EXISTS item_events_change ON item_events(change)")
        con.execute("COMMIT")
    finally:
        con.close()


class Migration(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def file_at(self, level, events=3):
        """A file at schema version `level` (1 to 4) holding steps and events, one of them an Undo that points at another."""
        path = make_v1(self.dir)
        con = connect(path)
        try:
            if level >= 2:
                with mock.patch.object(store_module, "SCHEMA_VERSION", level):
                    migrate(con, table=tuple(store_module.MIGRATIONS[:level - 1]))
        finally:
            con.close()
        if level >= 3:
            as_version_3_made_it(path)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO applies (apply_id, at, by_user, device) VALUES (1, '2026-10-01 10:00:00.000', 'Old Person', 'd1')")
        con.execute("INSERT INTO change_log (at, apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                    "VALUES ('2026-10-01 10:00:00.000', 1, 'projects', 'ABC', 'name', 'A', 'B', 'update', 'dashboard')")
        for i in range(1, events + 1):
            con.execute("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, place, actor, undoes) "
                        "VALUES ('2026-10-01', 1, 'ABC', 1, 'change', ?, ?, 'you', ?)",
                        ("undo" if i == 3 else "dashboard", "peek" if i == 1 else None, 1 if i == 3 else None))
        con.close()
        self.assertEqual(version(path), str(level))
        return path

    def check_migrated(self, path, events=3):
        s = open_store(path, onedrive_roots=[])
        try:
            con = s.con
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual(store_module.SCHEMA_VERSION, store_module.HISTORY_VERSION)
            self.assertIn("utc_offset", [r[1] for r in con.execute("PRAGMA table_info(applies)")])
            self.assertEqual(con.execute("SELECT utc_offset FROM applies WHERE apply_id = 1").fetchone()[0], None, "old rows: zone not recorded")
            self.assertEqual([r[0] for r in con.execute("SELECT event_id FROM item_events ORDER BY event_id")], list(range(1, events + 1)))
            self.assertEqual(con.execute("SELECT undoes FROM item_events WHERE event_id = 3").fetchone()[0], 1)
            self.assertEqual(con.execute("SELECT place FROM item_events WHERE event_id = 1").fetchone()[0], "peek")
            self.assertEqual({r[1] for r in con.execute("PRAGMA index_list(item_events)")} & {"item_events_item", "item_events_change"},
                             {"item_events_item", "item_events_change"})
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            for place in ("eye", "draft", "email", "text", "ask", "board"):          # the new CHECK, and a step after the migration
                with s.step("dashboard", USER, place=place) as st:
                    st.update("projects", "ABC", {"name": f"At {place}"})
            last = con.execute("SELECT a.utc_offset, e.event_id FROM applies a JOIN item_events e USING (apply_id) ORDER BY e.event_id DESC LIMIT 1").fetchone()
            self.assertRegex(last[0], "^[+-][0-9]{2}:[0-9]{2}$")
            self.assertEqual(last[1], events + 6, "ids carry on and are not reused")
        finally:
            s.close()

    def test_from_version_1(self):
        self.check_migrated(self.file_at(1))

    def test_from_version_2(self):
        self.check_migrated(self.file_at(2))

    def with_word_and_section_rows(self, level):
        """A file at `level` (3 or 4) holding a Word-route event (event 4) and, at 4, a section of type needs."""
        path = self.file_at(level)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, place, actor) "
                    "VALUES ('2026-10-02', 1, 'ABC', 1, 'change', 'word', NULL, 'you')")
        if level >= 4:
            con.execute("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) "
                        "VALUES ('ABC', 'needs-1', 'needs', 'What we need', 'A decision on the plan', 0, 0, 1)")
        con.close()
        self.assertEqual(version(path), str(level))
        return path

    def test_a_version_3_file_holding_a_word_row_migrates_keeps_it_and_opens(self):
        path = self.with_word_and_section_rows(3)
        self.check_migrated(path, events=4)
        self.check_word_row(path)

    def test_a_version_4_file_holding_a_word_row_and_a_section_body_migrates_keeps_both_and_opens(self):
        path = self.with_word_and_section_rows(4)
        self.check_migrated(path, events=4)
        self.check_word_row(path)
        con = sqlite3.connect(str(path))
        try:
            self.assertEqual(con.execute("SELECT type, title, body FROM report_sections WHERE id = 'needs-1'").fetchone(),
                             ("needs", "What we need", "A decision on the plan"))
        finally:
            con.close()

    def check_word_row(self, path):
        s = open_store(path, onedrive_roots=[])
        try:
            con = s.con
            self.assertEqual(con.execute("SELECT route FROM item_events WHERE event_id = 4").fetchone()[0], "word")
            sql = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'item_events'").fetchone()[0]
            for w in ("'word'", "'eye'", "'ask'", "'board'"):
                self.assertIn(w, sql)
            con.execute("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, place, actor) "
                        "VALUES ('2026-10-03', 1, 'ABC', 1, 'change', 'word', 'eye', 'you')")          # a Word row still goes in after the step
        finally:
            s.close()

    def test_the_migrated_offset_column_takes_only_a_real_offset(self):
        path = self.file_at(4)
        s = open_store(path, onedrive_roots=[])
        try:
            sql = s.con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'applies'").fetchone()[0]
            self.assertIn("utc_offset", sql)
            refuses_and_takes(self, s.con)
        finally:
            s.close()

    def test_a_second_open_changes_nothing(self):
        path = self.file_at(2)
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()

    def test_a_file_that_already_has_the_column_still_migrates(self):
        path = self.file_at(2)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("ALTER TABLE applies ADD COLUMN utc_offset TEXT")
        con.close()
        self.check_migrated(path)

    def test_a_failure_in_the_step_changes_nothing_and_the_file_opens_at_its_old_version(self):
        path = self.file_at(2)
        con = sqlite3.connect(str(path))
        before = list(con.iterdump())
        con.close()
        def late(c):
            store_module.migrate_to_history(c)
            raise RuntimeError("forced")
        table = tuple(store_module.MIGRATIONS[:-1]) + ((store_module.HISTORY_VERSION, late),)
        with mock.patch.object(store_module, "MIGRATIONS", table), self.assertRaises(Invalid):
            open_store(path, onedrive_roots=[])
        con = sqlite3.connect(str(path))
        self.assertEqual(list(con.iterdump()), before)
        con.close()
        self.assertEqual(version(path), "2")

    def test_the_step_does_not_read_the_live_schema(self):
        src = Path(store_module.__file__).read_text(encoding="utf-8")
        body = src[src.index("def migrate_to_history"):src.index("MIGRATIONS = (")]
        self.assertNotIn("schema.sql", body)
        self.assertNotIn("SCHEMA.", body)
        self.assertNotIn("_statements(", body)

    def test_a_safety_copy_is_taken_and_an_older_clark_refuses_the_newer_file(self):
        path = self.file_at(2)
        open_store(path, onedrive_roots=[]).close()
        self.assertTrue(list((self.dir / "backups").glob("*-migrate.db")))
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(store_module.SCHEMA_VERSION + 1),))
        con.close()
        with self.assertRaises(Invalid):
            open_store(path, onedrive_roots=[])

    def test_a_table_of_200000_events_migrates_quickly_and_both_lookups_use_their_index(self):
        path = self.file_at(2, events=3)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("BEGIN")
        con.executemany("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, place, actor) "
                        "VALUES ('2026-10-01', 1, ?, ?, 'change', 'dashboard', 'cell', 'you')",
                        ((f"ABC-A-{i % 500:03d}", i) for i in range(200_000)))
        con.execute("COMMIT")
        con.close()
        started = time.monotonic()
        s = open_store(path, onedrive_roots=[])
        took = time.monotonic() - started
        try:
            self.assertEqual(s.con.execute("SELECT count(*) FROM item_events").fetchone()[0], 200_003)
            self.assertLess(took, 30, f"the migration took {took:.1f} s")
            for sql in ("SELECT * FROM item_events WHERE change = 7", "SELECT * FROM item_events WHERE item_id = 'ABC-A-001'"):
                plan = " ".join(r[3] for r in s.con.execute("EXPLAIN QUERY PLAN " + sql))
                self.assertIn("USING INDEX item_events_", plan, plan)
        finally:
            s.close()


class Source(unittest.TestCase):
    def test_the_two_place_lists_agree_and_the_schema_check_names_the_same_places(self):
        sql = (Path(store_module.__file__).with_name("schema.sql")).read_text(encoding="utf-8")
        line = next(l for l in sql.splitlines() if l.lstrip().startswith("place") and "CHECK" in l)
        named = set(__import__("re").findall(r"'([a-z]+)'", line.split("IN (")[1].split(")")[0]))
        self.assertEqual(named, set(store_module.PLACES))
        frozen = set(__import__("re").findall(r"'([a-z]+)'", store_module.VERSION_5_ITEM_EVENTS.split("place      TEXT")[1].split("IN (")[1].split(")")[0]))
        self.assertEqual(frozen, set(store_module.PLACES))
        self.assertTrue(set(changes.PLACES) <= set(store_module.PLACES))
        routes = set(__import__("re").findall(r"'([a-z]+)'", store_module.VERSION_5_ITEM_EVENTS.split("route      TEXT")[1].split("IN (")[1].split(")")[0]))
        self.assertEqual(routes, set(store_module.ROUTES), "the rebuilt table keeps every route, 'word' among them")
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], [2, 3, 4, 5])
        self.assertEqual((store_module.SCHEMA_VERSION, store_module.HISTORY_VERSION), (5, 5))
        for p in ("peek", "board", "eye", "draft", "email", "text", "cell", "report", "menu"):
            self.assertIn(p, changes.PLACES)


if __name__ == "__main__":
    unittest.main()

"""dev/demo_data.py (#30): two fictional projects, every kind of item, every milestone state, the same data for the same
CLARK_NOW, only names from the script's own fictional list, and no overwriting a database that isn't a demo."""
import contextlib
import hashlib
import importlib.util
import io
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401  (puts src/ on the path)
from _paths import ROOT
from clark import store as clark_store

try:
    from clark.milestones import milestone_state          # #32, when it is merged
except ImportError:
    def milestone_state(row, on=None):
        """What clark.milestones.milestone_state returns (#32), from the store's own suggested_state until #32 is merged."""
        if row.get("status") == "Done":
            return "Achieved"
        if row.get("state_set") and row.get("state"):
            return row["state"]
        return clark_store.suggested_state(row, on)

_spec = importlib.util.spec_from_file_location("demo_data", str(ROOT / "dev" / "demo_data.py"))
demo_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo_data)

REAL_OPEN_STORE = clark_store.open_store
NOW = datetime(2026, 10, 28, 9, 0)
ALL_STATES = {"Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast"}


def dump(path):
    """Every row of every table in the database, in table and row order."""
    con = sqlite3.connect(str(path))
    try:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return {t: con.execute(f'SELECT * FROM "{t}" ORDER BY rowid').fetchall() for t in tables}
    finally:
        con.close()


def rows(path, sql):
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql)]
    finally:
        con.close()


class DemoCase(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-demo-test-"))
        self.addCleanup(shutil.rmtree, str(self.dir), True)

    def build(self, name="clark.db", now=NOW):
        path = self.dir / name
        demo_data.build(path, now, onedrive_roots=[])
        return path


class TestContents(DemoCase):
    def setUp(self):
        super().setUp()
        self.path = self.build()

    def test_two_projects(self):
        self.assertEqual({r["code"] for r in rows(self.path, "SELECT code FROM projects")}, {"TUL", "MOSS"})

    def test_each_kind_is_in_each_project(self):
        for code in ("TUL", "MOSS"):
            for table in ("actions", "milestones", "decisions", "use_cases", "workstreams", "updates"):
                self.assertTrue(rows(self.path, f"SELECT 1 FROM {table} WHERE project = '{code}'"), (code, table))
            for kind in ("Risk", "Assumption", "Issue", "Dependency"):
                self.assertTrue(rows(self.path, f"SELECT 1 FROM raid WHERE project = '{code}' AND type = '{kind}'"), (code, kind))

    def test_every_value_list_is_used(self):
        for table, column, values in (
                ("actions", "status", ("Open", "Delayed", "Closed", "Cancelled")),
                ("actions", "priority", ("Urgent", "High", "Medium", "Low")),
                ("raid", "status", ("Open", "Closed", "Cancelled")),
                ("decisions", "status", ("Pending", "Made", "Withdrawn")),
                ("use_cases", "status", ("On track", "Flag", "High risk")),
                ("milestones", "status", ("Planned", "Done", "Cancelled"))):
            got = {r[column] for r in rows(self.path, f"SELECT {column} FROM {table}")}
            self.assertEqual(got, set(values), (table, column))

    def test_every_milestone_state_is_present_in_each_project(self):
        for code in ("TUL", "MOSS"):
            ms = rows(self.path, f"SELECT * FROM milestones WHERE project = '{code}' AND status <> 'Cancelled'")
            self.assertEqual({milestone_state(m, NOW.date().isoformat()) for m in ms}, ALL_STATES, code)

    def test_a_user_set_at_risk_has_its_reason_and_forecast_has_no_agreed_date(self):
        ms = rows(self.path, "SELECT * FROM milestones")
        self.assertTrue([m for m in ms if m["state"] == "At risk" and m["state_set"] and m["state_reason"]])
        self.assertTrue([m for m in ms if m["state"] == "Forecast" and m["forecast_date"] and not m["baseline_date"]])

    def test_a_rebaseline_recorded_its_decision(self):
        self.assertTrue(rows(self.path, "SELECT 1 FROM decisions WHERE decision LIKE '%agreed date moves from%'"))

    def test_links_labels_and_history(self):
        self.assertTrue(rows(self.path, "SELECT 1 FROM links"))
        self.assertTrue(rows(self.path, "SELECT 1 FROM item_labels"))
        self.assertTrue(rows(self.path, "SELECT 1 FROM change_log"))
        self.assertEqual({r["by_user"] for r in rows(self.path, "SELECT by_user FROM applies")}, {demo_data.DEMO_USER})

    def test_every_date_is_relative_to_the_clock(self):
        stamps = [r["at"] for r in rows(self.path, "SELECT at FROM applies UNION SELECT at FROM change_log")]
        self.assertTrue(stamps and all(s.startswith("2026-10-28 09:00:0") for s in stamps), stamps[:3])

    def test_no_leftover_files(self):
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["backups", "clark.db"])      # #86: the first step took the day's copy
        self.assertEqual([p.name.rsplit("-", 1)[-1] for p in (self.dir / "backups").iterdir()], ["daily.db"], "only a finished copy")


class TestSameClock(DemoCase):
    def test_two_runs_with_the_same_clock_give_identical_tables(self):
        a, b = self.build("a.db"), self.build("b.db")
        self.assertEqual(dump(a), dump(b))

    def test_a_run_through_the_command_line_with_clark_now(self):
        a, b = self.dir / "a.db", self.dir / "b.db"
        with mock.patch.dict(os.environ, {"CLARK_NOW": "2026-10-28 09:00"}), \
                contextlib.redirect_stdout(io.StringIO()), \
                mock.patch.object(demo_data.clark_store, "open_store",
                                  side_effect=lambda p, onedrive_roots=None: REAL_OPEN_STORE(p, onedrive_roots=[])):
            self.assertEqual(demo_data.main(["--out", str(a)]), 0)
            self.assertEqual(demo_data.main(["--out", str(b)]), 0)
        self.assertEqual(dump(a), dump(b))
        self.assertEqual(dump(a), dump(self.build("c.db")))

    def test_the_real_clock_and_ids_are_put_back(self):
        saved = (clark_store.now, clark_store.today, clark_store.uuid)
        self.build()
        self.assertEqual((clark_store.now, clark_store.today, clark_store.uuid), saved)

    def test_a_different_clock_moves_every_date(self):
        a = self.build("a.db")
        later = self.build("b.db", NOW + timedelta(days=10))
        self.assertNotEqual(dump(a), dump(later))
        for table, column in (("milestones", "baseline_date"), ("milestones", "forecast_date"), ("actions", "due_date"),
                              ("actions", "raised"), ("raid", "raised"), ("decisions", "date"), ("updates", "week_ending")):
            sql = f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL ORDER BY rowid"
            first, second = [r[column] for r in rows(a, sql)], [r[column] for r in rows(later, sql)]
            self.assertTrue(first, (table, column))
            moved = [(datetime.strptime(y, "%Y-%m-%d") - datetime.strptime(x, "%Y-%m-%d")).days for x, y in zip(first, second)]
            self.assertEqual(set(moved), {10}, (table, column))
            self.assertEqual(len(first), len(second))

    def test_every_state_is_present_on_another_day_too(self):
        later = NOW + timedelta(days=10)
        path = self.build("b.db", later)
        ms = rows(path, "SELECT * FROM milestones WHERE status <> 'Cancelled'")
        self.assertEqual({milestone_state(m, later.date().isoformat()) for m in ms}, ALL_STATES)


def names_outside_the_list(path):
    """{name: [table.column, ...]} for every person, organisation, project or use case name in the database that is not in the
    script's fictional list; and the set of names seen."""
    allowed = {name for group in demo_data.FICTIONAL.values() for name in group}
    seen = {}
    for table, column in TestFictionalNames.NAME_COLUMNS:
        for r in rows(path, f"SELECT {column} AS v FROM {table} WHERE {column} IS NOT NULL"):
            seen.setdefault(r["v"], []).append(f"{table}.{column}")
    return {v: where for v, where in seen.items() if v not in allowed}, set(seen)


class TestFictionalNames(DemoCase):
    # Every column that holds a person's or an organisation's name, or a project's or use case's title.
    NAME_COLUMNS = (("projects", "name"), ("projects", "sponsor"), ("projects", "client_name"), ("milestones", "owner"),
                    ("workstreams", "lead"), ("actions", "owner"), ("raid", "owner"), ("decisions", "made_by"),
                    ("use_cases", "title"), ("applies", "by_user"), ("item_labels", "added_by"))

    def test_the_list_is_the_only_source_of_names(self):
        outside, seen = names_outside_the_list(self.build())
        self.assertTrue(seen)
        self.assertEqual(outside, {})
        for group in ("people", "organisations", "projects", "use_cases"):       # the data does use each part of the list
            self.assertTrue(set(demo_data.FICTIONAL[group]) & seen, group)

    def test_no_person_or_organisation_is_named_in_free_text_outside_the_list(self):
        # Free text names nobody: no e-mail address, link or "(Organisation)" tag anywhere in the data.
        for table, content in dump(self.build()).items():
            for row in content:
                for value in row:
                    if isinstance(value, str):
                        for bad in ("@", "http", "www."):
                            self.assertNotIn(bad, value, table)

    def test_the_check_catches_a_name_outside_the_list(self):
        path = self.build()
        con = clark_store.connect(path)
        con.execute("UPDATE actions SET owner = 'Someone Else' WHERE id = 'TUL-A-001'")      # tampering, to test the test
        con.close()
        self.assertEqual(names_outside_the_list(path)[0], {"Someone Else": ["actions.owner"]})

    def test_the_list_is_obviously_made_up(self):
        for group in demo_data.FICTIONAL.values():
            self.assertEqual(len(group), len(set(group)))
        self.assertEqual(len(demo_data.CODES), 2)


class TestOverwrite(DemoCase):
    def test_a_demo_database_is_replaced(self):
        path = self.build()
        before = dump(path)
        self.build()
        self.assertEqual(dump(path), before)

    def test_a_database_that_is_not_a_demo_is_refused_and_left_alone(self):
        path = self.dir / "clark.db"
        store = clark_store.open_store(path, onedrive_roots=[])
        with store.step("dashboard", "Real Person") as st:
            st.create("projects", {"code": "REAL", "name": "Not a demo"})
        store.close()
        before = dump(path)
        with self.assertRaises(demo_data.DemoError):
            demo_data.build(path, NOW, onedrive_roots=[])
        self.assertEqual(dump(path), before)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir() if not p.name.startswith("clark.db-")), ["backups", "clark.db"])

    def test_a_demo_project_code_with_another_author_is_refused(self):
        path = self.build()
        store = clark_store.open_store(path, onedrive_roots=[])
        with store.step("dashboard", "Real Person") as st:
            st.update("projects", "TUL", {"phase": "Closed"})
        store.close()
        with self.assertRaises(demo_data.DemoError):
            demo_data.build(path, NOW, onedrive_roots=[])

    def test_a_file_that_is_not_a_database_is_refused_and_left_alone(self):
        path = self.dir / "notes.db"
        path.write_text("my notes\n", encoding="utf-8")
        self.assertEqual(demo_data.main(["--out", str(path)]), 1)
        self.assertEqual(path.read_text(encoding="utf-8"), "my notes\n")

    def test_a_folder_is_refused(self):
        with self.assertRaises(demo_data.DemoError):
            demo_data.build(self.dir, NOW, onedrive_roots=[])

    def test_a_bad_clark_now_is_said_plainly(self):
        with mock.patch.dict(os.environ, {"CLARK_NOW": "next Tuesday"}):
            self.assertEqual(demo_data.main(["--out", str(self.dir / "x.db")]), 1)
        self.assertFalse((self.dir / "x.db").exists())


SYSTEM_PYTHON = "/usr/bin/python3"
INTERPRETERS = [sys.executable] + ([SYSTEM_PYTHON] if os.path.exists(SYSTEM_PYTHON) and
                                    os.path.realpath(SYSTEM_PYTHON) != os.path.realpath(sys.executable) else [])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TestAsAProcess(unittest.TestCase):
    """The script run as a command, under each interpreter: a second run onto its own earlier database must replace it
    (an in-process test missed that /usr/bin/python3's SQLite refuses a read-only open of a WAL database), and a refusal
    must exit 1 with its reason on stderr."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-demo-proc-"))
        self.addCleanup(shutil.rmtree, str(self.dir), True)
        self.env = dict(os.environ, CLARK_NOW="2026-10-28 09:00")

    def run_script(self, python, out):
        return subprocess.run([python, str(ROOT / "dev" / "demo_data.py"), "--out", str(out)], env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=120)

    def test_the_second_run_replaces_the_first(self):
        for python in INTERPRETERS:
            with self.subTest(python=python):
                out = self.dir / (Path(python).parent.name + "-" + str(INTERPRETERS.index(python)) + ".db")
                first = self.run_script(python, out)
                self.assertEqual((first.returncode, first.stderr), (0, ""), first.stderr)
                os.utime(str(out), (1, 1))                                # so a replacement shows
                second = self.run_script(python, out)
                self.assertEqual((second.returncode, second.stderr), (0, ""), second.stderr)
                self.assertIn("Built", second.stdout)
                self.assertGreater(out.stat().st_mtime, 1000)             # a new file was moved into place
                self.assertEqual(dump(out), dump_after_one_build(self.dir, python))

    def test_a_database_that_is_not_a_demo_is_refused(self):
        for python in INTERPRETERS:
            with self.subTest(python=python):
                out = self.dir / ("other-%d.db" % INTERPRETERS.index(python))
                con = sqlite3.connect(str(out))
                con.execute("CREATE TABLE notes (body TEXT)")
                con.execute("INSERT INTO notes VALUES ('mine')")
                con.commit()
                con.close()
                self.assert_refused(python, out)

    def test_a_clark_database_with_another_project_is_refused(self):
        out = self.dir / "real.db"
        store = clark_store.open_store(out, onedrive_roots=[])
        with store.step("dashboard", "Real Person") as st:
            st.create("projects", {"code": "REAL", "name": "Not a demo"})
        store.close()
        for python in INTERPRETERS:
            with self.subTest(python=python):
                self.assert_refused(python, out)

    def test_an_edited_demo_database_is_refused(self):
        for python in INTERPRETERS:
            with self.subTest(python=python):
                out = self.dir / ("edited-%d.db" % INTERPRETERS.index(python))
                self.assertEqual(self.run_script(python, out).returncode, 0)
                store = clark_store.open_store(out, onedrive_roots=[])
                with store.step("dashboard", "Real Person") as st:
                    st.update("projects", "TUL", {"phase": "Closed"})
                store.close()
                self.assert_refused(python, out)

    def test_a_folder_and_a_text_file_are_refused(self):
        notes = self.dir / "notes.db"
        notes.write_text("my notes\n", encoding="utf-8")
        for python in INTERPRETERS:
            with self.subTest(python=python):
                self.assert_refused(python, notes)
                folder = self.run_script(python, self.dir)
                self.assertEqual(folder.returncode, 1)
                self.assertIn("is a folder", folder.stderr)

    def assert_refused(self, python, out):
        before = sha(out)
        result = self.run_script(python, out)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not a demo database", result.stderr)
        self.assertNotIn("Built", result.stdout)
        self.assertEqual(sha(out), before)
        self.assertEqual(sorted(p.name for p in out.parent.iterdir() if p.name.startswith(out.name + ".")), [])


def dump_after_one_build(folder, python):
    """What one clean build under `python` holds (the same CLARK_NOW gives the same data, so a rebuild equals it)."""
    fresh = Path(folder) / "fresh-reference.db"
    if fresh.exists():
        fresh.unlink()
    result = subprocess.run([python, str(ROOT / "dev" / "demo_data.py"), "--out", str(fresh)],
                            env=dict(os.environ, CLARK_NOW="2026-10-28 09:00"), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, timeout=120)
    assert result.returncode == 0, result.stderr
    return dump(fresh)



class TestClockInput(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(demo_data.parse_now("2026-10-28"), datetime(2026, 10, 28, 9, 0))
        self.assertEqual(demo_data.parse_now("2026-10-28 14:30"), datetime(2026, 10, 28, 14, 30))
        self.assertEqual(demo_data.parse_now("2026-10-28T14:30:15"), datetime(2026, 10, 28, 14, 30, 15))
        self.assertIsInstance(demo_data.parse_now(""), datetime)


if __name__ == "__main__":
    unittest.main()

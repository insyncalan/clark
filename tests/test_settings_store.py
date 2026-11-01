"""#47: the store's one-writer path for app_settings.ask_enabled, and ask_enabled() never failing open.

Run: python3 dev/run_tests.py test_settings_store
The settings step is step 3 of MIGRATIONS, so a file made by open_store has the table and its row. Fictional data only.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import sqlite3

from clark import store as st

WHO = "Demo User"


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = st.open_store(self.dir / "clark.db", onedrive_roots=[])
        self.addCleanup(self.store.close)
        with self.store.step("dashboard", WHO, place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Example Programme", "health": "On track"})
            s.create("projects", {"code": "DEF", "name": "Other Programme", "health": "On track"})

    def last(self):
        return self.store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]

    def log_count(self):
        return self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]

    def set_ask(self, value):
        with self.store.step("dashboard", WHO, place="menu") as s:
            s.update("app_settings", "1", {"ask_enabled": value})
            return s.peek_apply_id()


class AskSwitch(Base):
    def test_on_to_start_with(self):
        self.assertTrue(self.store.ask_enabled())
        self.assertEqual(self.store.read("app_settings", ref="1")["ask_enabled"], 1)

    def test_off_and_on_again_each_one_step_with_who_how_and_when(self):
        off = self.set_ask(False)
        self.assertFalse(self.store.ask_enabled())
        on = self.set_ask(True)
        self.assertTrue(self.store.ask_enabled())
        self.assertNotEqual(off, on)
        rows = self.store.step_rows(off)
        self.assertEqual([(r["table"], r["key"], r["field"], r["via"]) for r in rows if r["field"] == "ask_enabled"],
                         [("app_settings", "1", "ask_enabled", "dashboard")])
        who = self.store.con.execute("SELECT by_user FROM applies WHERE apply_id = ?", (off,)).fetchone()[0]
        self.assertEqual(who, WHO)
        event = self.store.con.execute("SELECT route, place, actor FROM item_events WHERE apply_id = ? AND item_id = '1'", (off,)).fetchone()
        self.assertEqual(tuple(event), ("dashboard", "menu", "you"))
        history = self.store.history("1")
        self.assertEqual([(e["field"], e["before"], e["after"]) for e in history if e["field"] == "ask_enabled"],
                         [("ask_enabled", "0", "1"), ("ask_enabled", "1", "0")])

    def test_undo_puts_the_switch_back(self):
        off = self.set_ask(0)
        done = self.store.undo(off, WHO, place="menu")
        self.assertTrue(done["reversed"], done)
        self.assertTrue(self.store.ask_enabled())

    def test_undo_is_refused_once_a_later_change_stands(self):
        off = self.set_ask(0)
        self.set_ask(1)
        done = self.store.undo(off, WHO, place="menu")
        self.assertFalse(done["reversed"])
        self.assertTrue(self.store.ask_enabled())

    def test_only_true_false_0_and_1_are_taken(self):
        before = self.log_count()
        for bad in (2, -1, "1", "on", "false", None, "", 1.0, [1], {"a": 1}, 10 ** 30):
            with self.assertRaises(st.Invalid, msg=repr(bad)):
                self.set_ask(bad)
        self.assertEqual(self.log_count(), before)
        self.assertTrue(self.store.ask_enabled())

    def test_a_second_row_a_new_row_and_a_cancel_are_refused(self):
        before = self.log_count()
        for attempt in (lambda s: s.create("app_settings", {"id": 2}), lambda s: s.create("app_settings", {"id": 1}),
                        lambda s: s.cancel("app_settings", "1"), lambda s: s.update("app_settings", "2", {"ask_enabled": 0}),
                        lambda s: s.update("app_settings", "1", {"id": 2}), lambda s: s.update("app_settings", "1", {"colour": "red"}),
                        lambda s: s.update("app_settings", "1", {}), lambda s: s.archive("app_settings", "1")):
            with self.assertRaises(st.Invalid):
                with self.store.step("dashboard", WHO, place="menu") as s:
                    attempt(s)
        with self.assertRaises(st.Invalid) as caught:
            with self.store.step("dashboard", WHO, place="menu") as s:
                s.create("app_settings", {"id": 2})
        self.assertEqual(str(caught.exception), st.SETTINGS_ROW)
        self.assertEqual(self.log_count(), before)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM app_settings").fetchone()[0], 1)

    def test_a_change_to_the_value_it_already_has_writes_nothing(self):
        before = self.log_count()
        with self.store.step("dashboard", WHO, place="menu") as s:
            s.update("app_settings", "1", {"ask_enabled": True})
        self.assertEqual(self.log_count(), before)

    def test_a_file_without_the_step_reads_as_off_and_says_it_is_not_ready(self):
        """A file made before the settings step (version 5, held there for the test): no table; asking reads as off (never fails open)."""
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, True)
        with mock.patch.object(st, "SCHEMA_VERSION", 5), mock.patch.object(st, "MIGRATIONS", st.MIGRATIONS[:4]):
            path = folder / "clark.db"
            st.open_store(path, onedrive_roots=[]).close()
            con = sqlite3.connect(str(path), isolation_level=None)
            con.execute("DROP TABLE app_settings")
            con.execute("UPDATE meta SET v = '5' WHERE k = 'schema_version'")
            con.close()
            old = st.open_store(path, onedrive_roots=[])
        self.addCleanup(old.close)
        self.assertFalse(old.settings_ready())
        self.assertIs(old.ask_enabled(), False)
        self.assertIs(st.ASK_WHEN_MISSING, False)
        self.assertTrue(self.store.settings_ready())

    def test_a_missing_row_reads_as_off_and_says_it_is_not_ready(self):
        """The file has the table but not its one row (damaged or tampered): asking reads as off, not as an error and never as on."""
        self.store.con.execute("DELETE FROM app_settings")
        self.assertFalse(self.store.settings_ready())
        self.assertIs(self.store.ask_enabled(), False)

    def test_a_database_error_reads_as_off(self):
        class Broken:
            def execute(self, *a):
                raise sqlite3.OperationalError("disk I/O error")
        real, self.store.con = self.store.con, Broken()
        try:
            self.assertIs(self.store.ask_enabled(), False)
            self.assertFalse(self.store.settings_ready())
        finally:
            self.store.con = real


if __name__ == "__main__":
    unittest.main()

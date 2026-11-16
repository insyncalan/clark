"""Row 1269, slice A: the install's Theme in the store (app_settings.theme, migration step 27, Store.theme()).

A new file is Clark Classic; a file that already exists keeps today's look (Cards) and no existing value changes. Fictional data only.

Run: python3 dev/run_tests.py test_theme_setting_store
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import store as store_module
from clark.store import Invalid, open_store
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 27
WHO = "Demo User"


def settings_row(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT ask_enabled, updated_at FROM app_settings WHERE id = 1").fetchone()
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_at_its_number(self):
        self.assertIn((STEP, store_module.migrate_theme), store_module.MIGRATIONS)
        self.assertEqual(store_module.THEME_STEP, STEP)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_a_new_file_is_classic(self):
        s = open_store(self.dir / "clark.db", onedrive_roots=[])
        try:
            self.assertEqual(s.theme(), "classic")
            self.assertEqual(s.read("app_settings", ref="1")["theme"], "classic")
        finally:
            s.close()

    def test_a_file_made_before_the_step_keeps_cards_and_every_other_value(self):
        path = make_at(self.dir, STEP - 1)
        before = settings_row(path)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual(s.theme(), "cards")
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)      # a migration is not a step: no Undo
        finally:
            s.close()
        self.assertEqual(settings_row(path), before)

    def test_a_second_run_changes_nothing(self):
        path = make_at(self.dir, STEP - 1)
        open_store(path, onedrive_roots=[]).close()
        con = store_module.connect(path)
        try:
            con.execute("BEGIN IMMEDIATE")
            store_module.migrate_theme(con)
            con.execute("COMMIT")
            self.assertEqual(con.execute("SELECT theme FROM app_settings").fetchall()[0][0], "cards")
        finally:
            con.close()

    def test_a_file_older_than_the_settings_table_gets_the_column_when_the_table_is_made(self):
        path = make_at(self.dir, 5)
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(s.theme(), "cards")
        finally:
            s.close()


class Reading(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = open_store(self.dir / "clark.db", onedrive_roots=[])
        self.addCleanup(self.store.close)

    def set_theme(self, value):
        with self.store.step("dashboard", WHO, place="menu") as s:
            s.update("app_settings", "1", {"theme": value})
            return s.peek_apply_id()

    def test_a_change_is_one_step_and_undo_puts_it_back(self):
        step = self.set_theme("cards")
        self.assertEqual(self.store.theme(), "cards")
        self.assertEqual([(r["table"], r["field"]) for r in self.store.step_rows(step) if r["field"] == "theme"], [("app_settings", "theme")])
        self.store.undo(step, WHO, place="menu")
        self.assertEqual(self.store.theme(), "classic")

    def test_any_other_name_is_refused_and_nothing_is_written(self):
        for bad in ("Classic", "dark", "../x", 1, True):
            with self.assertRaises(Invalid, msg=repr(bad)):
                self.set_theme(bad)
        self.assertEqual(self.store.theme(), "classic")

    def test_the_theme_never_fails_toward_classic(self):
        self.store.con.execute("PRAGMA ignore_check_constraints = ON")
        self.store.con.execute("UPDATE app_settings SET theme = 'nonsense' WHERE id = 1")
        self.assertEqual(self.store.theme(), "cards")
        self.store.con.execute("DELETE FROM app_settings")
        self.assertEqual(self.store.theme(), "cards")
        self.store.con.execute("DROP TABLE app_settings")
        self.assertEqual(self.store.theme(), "cards")

    def test_the_asking_switch_still_works_beside_it(self):
        with self.store.step("dashboard", WHO, place="menu") as s:
            s.update("app_settings", "1", {"ask_enabled": False})
        self.assertFalse(self.store.ask_enabled())
        self.assertEqual(self.store.theme(), "classic")


if __name__ == "__main__":
    unittest.main()

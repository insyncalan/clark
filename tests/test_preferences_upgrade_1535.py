"""Row 1535 step 4 (AP13 to AP15): every preference kept in the database or the data folder has the same value after an upgrade, a
migration, a restart, a restore and an update that is rolled back. Quick tier (no browser), so it runs in every CI run and so in every release gate.

The browser's own preferences (localStorage) cannot be moved through these paths until step 3 (the data-folder file) exists: AP13 is
met here for the db and file entries of the registry only (see the last test).

Run: python3 dev/run_tests.py test_preferences_upgrade_1535
"""
import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401

from clark import backup, preferences, settings, store as store_module
from test_check_data import run
from test_store_migration import make_v1

SETTINGS = {"backups_kept": 21, "profile_name": "Example Person", "profile_email": "person@example.org", "profile_alias": "EP",
            "ai_model": "example-model", "ai_claude_off": True, "ai_chatgpt_on": True, "ai_accepted": ["example-weaker"], "backup_copy_folder": "COPYFOLDER"}
FILES = {"ask_folders_all.json": '["/example/one", "/example/two"]\n', "ask-commands/summary.json": '{"name": "summary", "text": "Summarise it"}\n',
         "clark-brand.json": '{"example": 1}\n', "excel-export-state.json": '{"example": 2}\n'}
DB_APP = {"ask_enabled": 0, "theme": "cards", "ask_instructions": "Example standing instructions", "ask_files": 0, "ask_new_projects": 0}


class Paths1535(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.db = make_v1(self.dir)
        for k, v in FILES.items():
            (self.dir / k).parent.mkdir(parents=True, exist_ok=True)
            (self.dir / k).write_text(v, encoding="utf-8")
        copy_to = Path(tempfile.mkdtemp(prefix="clark-test-copy-"))
        self.addCleanup(shutil.rmtree, copy_to, True)
        (self.dir / settings.FILE).write_text(json.dumps({**SETTINGS, "backup_copy_folder": str(copy_to)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(run(self.dir)[0], 0)               # the upgrade from the previous release's data
        con = sqlite3.connect(str(self.db))
        try:
            con.execute("UPDATE app_settings SET " + ", ".join(f"{k} = ?" for k in DB_APP) + " WHERE id = 1", tuple(DB_APP.values()))
            con.execute("UPDATE projects SET layout = 'spine', review_after_days = 9, client_name = 'Example Client', gantt_tab_name = 'Plan' WHERE code = 'ABC'")
            con.commit()
        finally:
            con.close()
        self.before = self.snapshot()

    def snapshot(self):
        con = sqlite3.connect(str(self.db))
        try:
            app = dict(zip(DB_APP, con.execute("SELECT " + ", ".join(DB_APP) + " FROM app_settings WHERE id = 1").fetchone()))
            proj = con.execute("SELECT layout, review_after_days, client_name, gantt_tab_name FROM projects WHERE code = 'ABC'").fetchone()
        finally:
            con.close()
        files = {k: (self.dir / k).read_text(encoding="utf-8") for k in [settings.FILE, *FILES]}
        return {"app": app, "project": proj, "files": files}

    def test_the_fixture_holds_a_non_default_value_for_every_db_and_file_entry(self):
        self.assertNotEqual(self.before["app"], {"ask_enabled": 1, "theme": "classic", "ask_instructions": "", "ask_files": 1, "ask_new_projects": 1})
        self.assertEqual(self.before["project"], ("spine", 9, "Example Client", "Plan"))
        saved = json.loads(self.before["files"][settings.FILE])
        for p in preferences.REGISTRY:
            if p.where == "file" and p.key.startswith("settings.json:"):
                self.assertIn(p.key.split(":", 1)[1], saved, p.key)
        for p in preferences.REGISTRY:
            if p.where == "db" and "." in p.key and not p.key.startswith("projects."):
                self.assertIn(p.key.split(".", 1)[1], DB_APP, p.key)

    def test_upgrade_keeps_every_preference(self):
        """AP13: a restart, a migration to a newer schema, an update rolled back (refused, nothing changed) and a restore."""
        # restart: the check runs again
        self.assertEqual(run(self.dir)[0], 0)
        self.assertEqual(self.snapshot(), self.before)
        # restore: the copy taken now is put back over a database that has since changed
        copy = backup.make(self.db, self.dir / "backups", [], tag="daily")
        con = sqlite3.connect(str(self.db))
        try:
            con.execute("UPDATE app_settings SET theme = 'classic' WHERE id = 1")
            con.execute("UPDATE projects SET layout = 'boxed', review_after_days = 14, client_name = NULL, gantt_tab_name = 'Gantt' WHERE code = 'ABC'")
            con.commit()
        finally:
            con.close()
        backup.restore_path(self.db, Path(copy).name, self.dir / "backups", [])
        self.assertEqual(self.snapshot(), self.before)
        # migration: the next release's schema step
        nxt = store_module.SCHEMA_VERSION + 1
        with mock.patch.object(store_module, "SCHEMA_VERSION", nxt), mock.patch.object(store_module, "MIGRATIONS", store_module.MIGRATIONS + ((nxt, lambda con: None),)):
            self.assertEqual(run(self.dir)[0], 0)
        self.assertEqual(self.snapshot(), self.before)
        # update and roll back: the older release is refused and changes nothing
        self.assertEqual(run(self.dir)[0], 2)
        self.assertEqual(self.snapshot(), self.before)

    def test_the_browser_entries_are_not_met_here(self):
        """AP13 is met for db and file entries only: say so, so the browser entries cannot be thought covered."""
        self.assertTrue(any(p.where == "browser" for p in preferences.REGISTRY))
        self.assertEqual(preferences.keys("browser") & {"clark.peekWidth"}, {"clark.peekWidth"})   # still the browser's own until step 3


class Gate1535(unittest.TestCase):
    def test_upgrade_test_is_in_release_gate(self):
        """AP14: this file never starts Chrome (quick tier), and CI runs the quick tier on every run, the release branch's included."""
        import run_support
        self.assertFalse(run_support.is_chrome(__file__))
        ci = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertRegex(ci, r"run_tests\.py")

    def test_releasing_names_the_gate(self):
        """AP15: dev/RELEASING.md step 3 names this test file as a gate."""
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        step3 = re.search(r"^3\. \*\*Gate green\.\*\*.*$", text, re.M).group(0)
        self.assertIn("test_preferences_upgrade_1535", step3)


class Registry1294(unittest.TestCase):
    GROUPS = {"models": "settings.json:ai_model", "connectors": "connector_switches", "standing instructions": "app_settings.ask_instructions",
              "folders": "ask_folders_all.json", "slash commands": "ask-commands/", "files and pictures": "app_settings.ask_files",
              "chats kept": "clark.askChatsKeep"}

    def test_1294_settings_registered(self):
        """AP18: the seven groups of the Settings page (row 1294) are in the registry, with a scope."""
        keys = preferences.keys()
        self.assertEqual(len(self.GROUPS), 7)
        for group, key in self.GROUPS.items():
            self.assertIn(key, keys, group)
        self.assertEqual({p.scope for p in preferences.REGISTRY if p.key in self.GROUPS.values()} - set(preferences.SCOPES), set())


if __name__ == "__main__":
    unittest.main()

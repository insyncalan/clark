"""An update that brings a newer data layout: it is installed, the new version migrates the data after a copy, and the update's
undo puts that copy back (saying that changes made after the update are lost). The old refusal is gone; the store's own refusals
(a gap, a newer file) are tested in test_migration_chain.
Run: python3 dev/run_tests.py test_update_migration
"""
import json
import shutil
import sqlite3
import unittest
from pathlib import Path
from unittest import mock

from clark import backup, store as store_module, update_helper as h, update_install as ui, updater as up
from clark.store import Invalid, open_store
from test_store_migration import make_v1, version
from test_updater import Rig


def rows(path, table):
    con = sqlite3.connect(str(path))
    try:
        return con.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
    finally:
        con.close()


class Migrated(Rig):
    """The fixture's data folder holds an older database (version 1); the update is installed, then the new version starts."""

    def setUp(self):
        super().setUp()
        self.db.unlink()
        make_v1(self.data)
        self.before = {t: rows(self.db, t) for t in ("projects", "documents")}

    def new_start(self):
        """What the new version does at start: opens the store (the migration, after a copy), then settles the update."""
        s = open_store(self.db, onedrive_roots=[])
        copy = s.migration_backup
        s.close()
        now = self.make(version="0.3.1", migration_backup=copy)
        now.settle()
        return now, copy

    def test_the_update_records_the_copy_the_migration_took(self):
        self.installed()
        now, copy = self.new_start()
        self.assertIsNotNone(copy)
        self.assertEqual(str(store_module.SCHEMA_VERSION), version(self.db))
        record = ui.last_update(self.data)[1]
        self.assertEqual({"backup": Path(copy).name, "from": 1, "to": store_module.SCHEMA_VERSION}, record["migration"])

    def test_the_copy_is_found_by_its_family_when_the_start_did_not_pass_it(self):
        self.installed()
        s = open_store(self.db, onedrive_roots=[])
        copy = s.migration_backup
        s.close()
        self.make(version="0.3.1").settle()
        self.assertEqual(Path(copy).name, ui.last_update(self.data)[1]["migration"]["backup"])

    def test_an_update_that_kept_the_layout_records_no_migration_and_keeps_the_old_undo(self):
        self.db.unlink()
        s = open_store(self.db, onedrive_roots=[])
        s.close()
        self.installed()
        self.make(version="0.3.1").settle()
        self.assertIsNone(ui.last_update(self.data)[1].get("migration"))

    def test_undo_puts_the_data_back_as_it_was_and_says_changes_after_the_update_are_lost(self):
        self.installed()
        now, _ = self.new_start()
        con = sqlite3.connect(str(self.db))
        con.execute("INSERT INTO projects (code, name) VALUES ('NEW', 'Added after the update')")
        con.commit()
        con.close()
        status, armed = now.arm_undo({})
        self.assertEqual((200, "full"), (status, armed["choice"]))
        self.assertIn("Changes made after the update will be lost.", armed["line"])
        self.assertNotIn("Put back the app and settings only", armed["line"])
        status, done = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        self.assertEqual("1", version(self.db))
        self.assertEqual(self.before, {t: rows(self.db, t) for t in ("projects", "documents")})       # the same rows as before the update
        self.assertEqual(h.OK, self.run_helper()[0])
        kept = list((self.data / "backups").glob("replaced-*"))
        self.assertEqual(1, len(kept))                           # the newer database is kept whole, not deleted
        self.assertTrue(any(rows(f, "projects")[-1][0] == "NEW" for f in kept[0].glob("clark.db")))

    def test_the_app_only_undo_is_not_offered_because_the_old_version_cannot_open_the_newer_data(self):
        self.installed()
        now, _ = self.new_start()
        armed = now.arm_undo({})[1]
        status, done = now.undo({"arm_id": armed["arm_id"], "app_only": True})
        self.assertEqual(200, status)
        self.assertEqual("1", version(self.db))                  # the data was still put back

    def test_a_copy_that_has_gone_refuses_the_undo_and_changes_nothing(self):
        self.installed()
        now, copy = self.new_start()
        Path(copy).unlink()
        after = {t: rows(self.db, t) for t in ("projects", "documents")}
        armed = now.arm_undo({})[1]
        status, said = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((409, "data_gone"), (status, said["code"]))
        self.assertEqual(backup.UPDATE_GONE, said["message"])
        self.assertEqual(str(store_module.SCHEMA_VERSION), version(self.db))
        self.assertEqual(after, {t: rows(self.db, t) for t in ("projects", "documents")})
        self.assertFalse(h.marker_path(self.data).exists())

    def test_a_restore_that_fails_after_the_hand_over_says_so_and_leaves_the_data_as_it_is(self):
        self.installed()
        now, _ = self.new_start()
        armed = now.arm_undo({})[1]
        with mock.patch.object(backup, "restore_path", side_effect=Invalid("could not be copied")):
            status, said = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((409, "data_restore"), (status, said["code"]))
        self.assertEqual(ui.MESSAGES["data_restore"], said["message"])
        self.assertEqual(str(store_module.SCHEMA_VERSION), version(self.db))
        self.assertFalse(now.installing())

    def test_a_name_that_is_not_a_copy_taken_before_an_update_is_refused(self):
        record = {"migration": {"backup": "clark-20260101T000000Z-daily.db", "from": 1, "to": 5}}
        with self.assertRaises(ui.InstallError) as said:
            ui.check_restore(self.db, record)
        self.assertEqual("data_gone", said.exception.key)
        self.assertIsNone(ui.check_restore(self.db, {}))


class TheWordsAreAlwaysPlain(unittest.TestCase):
    def test_the_new_sentences(self):
        for text in (up.ARMED_RESTORE, ui.MESSAGES["data_gone"], ui.MESSAGES["data_restore"]):
            self.assertFalse(text.startswith(("clark", "Clark")), text)
            self.assertTrue(text.rstrip().endswith("."), text)
            self.assertNotIn("/", text.replace("{", ""), "no file path on screen")
        self.assertIn("Changes made after the update will be lost.", up.ARMED_RESTORE)


if __name__ == "__main__":
    unittest.main()

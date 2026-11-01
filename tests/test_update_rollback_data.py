"""#280: when an update is rolled back after the new version migrated the data, the data goes back too.

The rig is test_updater's (a fake app folder, a real database, the helper run in this process with faked platform seams); the new
version's start is faked as "opens the store" (the real migration, after its real safety copy) and then does not answer.
Run: python3 dev/run_tests.py test_update_rollback_data
"""
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from clark import backup, store as store_module, update_helper as h, update_install as ui
from clark.store import open_store
from test_store_migration import make_v1, version
from test_update_helper import FakeSeams, snapshot, sentences
from test_updater import Rig
from test_update_migration import rows


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class MigratingSeams(FakeSeams):
    """The new version's start: it migrates the data (after its copy), may do something more, and then does not answer."""

    def __init__(self, rig, answers=False, after=None, migrate=True, **kw):
        super().__init__(**kw)
        self.rig, self.answers, self.after, self.migrate = rig, answers, after, migrate
        self.copy = None

    def start_server(self, app_dir, data_dir, port, log_path):
        if not self.started and self.migrate:
            s = open_store(self.rig.db, onedrive_roots=[])
            self.copy = s.migration_backup
            s.close()
            if self.after:
                self.after(self)
            self.now += 20                                      # a slow start: far past the 15 seconds
        return super().start_server(app_dir, data_dir, port, log_path)

    def server_answers(self, port, header, mark, timeout=2):
        return self.answers


class Rolled(Rig):
    """The data folder holds a version 1 database; the update is handed over and the helper runs against MigratingSeams."""

    def setUp(self):
        super().setUp()
        self.db.unlink()
        make_v1(self.data)
        self.before = {t: rows(self.db, t) for t in ("projects", "documents")}
        self.v1_bytes = digest(self.db)
        self.app_before = snapshot(self.app)

    def go(self, **kw):
        self.seams = MigratingSeams(self, **kw)
        body = self.reviewed()
        status, done = self.up.install({"review_id": body["review_id"]})
        self.assertEqual(200, status, done)
        self.marker = h.marker_path(self.data)
        self.marker_copy = self.root / "marker-copy.json"
        shutil.copyfile(self.marker, self.marker_copy)
        return self.run_helper()

    def asides(self):
        return sorted((self.data / "backups").glob("replaced-*"))

    def plain(self, text):
        for s in sentences(text):
            self.assertFalse(s.lower().startswith("clark"), s)
        self.assertNotIn(str(Path.home()), text)
        self.assertNotIn("Traceback", text)


class RestoredTest(Rolled):
    def test_the_new_version_not_answering_restores_the_data_and_the_old_app(self):
        code, result = self.go()
        self.assertEqual((h.ROLLED_BACK, "rolled_back", "restored"), (code, result["status"], result["data"]))
        self.assertEqual("1", version(self.db))
        self.assertEqual(self.before, {t: rows(self.db, t) for t in ("projects", "documents")})
        self.assertEqual(2, len(self.seams.started))                                # the new version, then the old one again
        self.assertEqual(str(self.app), self.seams.started[-1][0])
        self.assertIn("with your data as it was before the update", result["message"])
        self.plain(result["message"])
        self.assertFalse(h.marker_path(self.data).exists())
        asides = self.asides()
        self.assertEqual(1, len(asides))                                            # the newer file is kept whole, not deleted
        self.assertEqual(str(store_module.SCHEMA_VERSION), version(asides[0] / "clark.db"))
        self.assertEqual([], [n for n in os.listdir(self.data) if n.startswith("clark.db.restoring")])
        # the old version can open what was put back
        s = open_store(self.db, onedrive_roots=[])
        s.close()

    def test_changes_made_after_the_migration_are_kept_aside_and_reported(self):
        def write(seams):
            con = sqlite3.connect(str(self.db))
            con.execute("INSERT INTO projects (code, name) VALUES ('NEW', 'Added in the first seconds')")
            con.commit()
            con.close()
        code, result = self.go(after=write)
        self.assertEqual((h.ROLLED_BACK, "restored"), (code, result["data"]))
        self.assertEqual("1", version(self.db))
        self.assertNotIn("NEW", [r[0] for r in rows(self.db, "projects")])
        kept = self.asides()[0]
        self.assertIn("NEW", [r[0] for r in rows(kept / "clark.db", "projects")])  # the write is not lost
        self.assertIn("Changes made in the last few seconds are kept in the folder " + kept.name, result["message"])
        self.plain(result["message"])

    def test_nothing_changed_since_the_update_says_so_without_claiming_more(self):
        code, result = self.go()
        self.assertIn("kept in the folder " + self.asides()[0].name, result["message"])

    def test_a_slow_migration_stopped_part_way_leaves_the_old_layout_and_it_is_not_touched(self):
        """Stopping the new version in the middle of its migration: the migration is one transaction, so the file is at the old layout
        and the step has nothing to put back; the data is byte for byte what it was."""
        self.seams = MigratingSeams(self, migrate=False)
        con = {}

        def start(app_dir, data_dir, port, log_path, original=self.seams.start_server):
            c = sqlite3.connect(str(self.db), isolation_level=None)
            c.execute("BEGIN IMMEDIATE")
            c.execute("UPDATE meta SET v = '9' WHERE k = 'schema_version'")        # half way, not committed
            con["c"] = c
            return original(app_dir, data_dir, port, log_path)
        self.seams.start_server = start
        body = self.reviewed()
        self.assertEqual(200, self.up.install({"review_id": body["review_id"]})[0])
        self.seams.stop_process = lambda pid, ident=None: con["c"].close()           # the stop ends the transaction: it rolls back
        self.seams.now += 20
        code, result = self.run_helper()
        self.assertEqual(h.ROLLED_BACK, code)
        self.assertEqual(self.v1_bytes, digest(self.db))
        self.assertEqual("1", version(self.db))
        self.assertNotIn("data", result)
        self.assertEqual([], self.asides())

    def test_a_slow_migration_that_finished_after_the_stop_is_put_back(self):
        code, result = self.go()                       # the migration took 20 seconds of the fake clock and the new version never answered
        self.assertGreater(self.seams.now, 15)
        self.assertEqual((h.ROLLED_BACK, "restored"), (code, result["data"]))
        self.assertEqual("1", version(self.db))

    def test_no_migration_means_no_touch(self):
        code, result = self.go(migrate=False)
        self.assertEqual(h.ROLLED_BACK, code)
        self.assertEqual(self.v1_bytes, digest(self.db))
        self.assertNotIn("data", result)
        self.assertEqual([], self.asides())

    def test_the_helper_run_twice_is_safe_and_changes_nothing_the_second_time(self):
        code, result = self.go()
        after_first = (digest(self.db), [a.name for a in self.asides()])
        shutil.copyfile(self.marker_copy, self.marker)                                # as if the helper had stopped before it finished
        code2, result2 = h.finish(self.data, self.seams)
        self.assertEqual(h.ROLLED_BACK, code2)
        self.assertEqual(after_first, (digest(self.db), [a.name for a in self.asides()]))      # no second aside, the same bytes
        run = h.Run(self.marker_copy, self.seams)
        run.r_restore_data()                                                           # and called straight again
        self.assertEqual(after_first, (digest(self.db), [a.name for a in self.asides()]))


class RefusedTest(Rolled):
    def refused(self, why, **kw):
        code, result = self.go(**kw)
        self.assertEqual((h.ROLLED_BACK, "pending"), (code, result["data"]))
        self.assertEqual(self.app_before, snapshot(self.app))
        self.assertEqual([], self.asides())
        self.assertIn("Your data was not put back automatically because " + why, result["message"])
        self.plain(result["message"])
        self.assertEqual(2, len(self.seams.started))                                    # the old version was put back anyway
        self.assertEqual(str(self.app), self.seams.started[-1][0])
        # the update's backup set now says putting the data back is waiting, and the page offers the Undo
        folder, record = ui.last_update(self.data)
        self.assertFalse(record["installed"])
        self.assertIn("reason", record["data_restore_pending"])
        self.assertEqual(str(store_module.SCHEMA_VERSION), version(self.db))
        line = self.up.status()[1]["last"]["line"]
        self.assertIn("didn't install", line)
        return result

    def test_the_copy_missing_is_refused_and_the_live_data_is_untouched(self):
        seen = {}

        def remove(seams):
            Path(seams.copy).unlink()
            seen["live"] = digest(self.db)
        self.refused("the copy of your data kept from before the update couldn't be found", after=remove)
        self.assertEqual(seen["live"], digest(self.db))

    def test_a_corrupt_copy_is_refused_and_the_live_data_is_untouched(self):
        seen = {}

        def spoil(seams):
            Path(seams.copy).write_bytes(b"not a database at all" * 100)
            seen["live"] = digest(self.db)
        self.refused("the copy of your data kept from before the update didn't pass its checks", after=spoil)
        self.assertEqual(seen["live"], digest(self.db))

    def test_a_copy_of_another_layout_is_refused_and_the_live_data_is_untouched(self):
        seen = {}

        def other(seams):
            con = sqlite3.connect(str(seams.copy))
            con.execute("UPDATE meta SET v = '5' WHERE k = 'schema_version'")
            con.commit()
            con.close()
            seen["live"] = digest(self.db)
        self.refused("the copy of your data kept from before the update belongs to a different version", after=other)
        self.assertEqual(seen["live"], digest(self.db))

    def test_a_copy_of_another_database_is_refused(self):
        def other(seams):
            con = sqlite3.connect(str(seams.copy))
            con.execute("UPDATE meta SET v = 'someone-else' WHERE k = 'db_id'")
            con.commit()
            con.close()
        self.refused("the copy of your data kept from before the update belongs to a different version", after=other)

    def test_a_new_version_still_running_is_refused(self):
        orig = MigratingSeams.process_gone
        MigratingSeams.process_gone = lambda self, pid: pid != 4242 and orig(self, pid)
        self.addCleanup(setattr, MigratingSeams, "process_gone", orig)
        seen = {}
        self.refused("the new version was still running", after=lambda seams: seen.update(live=digest(self.db)))
        self.assertEqual(seen["live"], digest(self.db))

    def test_an_older_updates_copy_is_never_chosen(self):
        """A migrate copy that is older than this update (before it began) is not the one to put back."""
        def old_only(seams):
            os.utime(seams.copy, (1000000, 1000000))
        self.refused("the copy of your data kept from before the update couldn't be found", after=old_only)


class UndoAfterAStoppedUpdateTest(Rolled):
    def test_the_offered_undo_puts_the_data_back_from_the_copy(self):
        def spoil(seams):
            Path(seams.copy).rename(Path(seams.copy).with_name("kept.tmp"))        # the copy is "missing" for the helper only
        self.go(after=spoil)
        copy = next((self.data / "backups").glob("kept.tmp"))
        copy.rename(self.data / "backups" / Path(self.seams.copy).name)
        now = self.make(version="0.3.0")
        status, armed = now.arm_undo({})
        self.assertEqual((200, "full"), (status, armed["choice"]))
        self.assertIn("puts your data back as it was before the update", armed["line"])


class HandOverFailsAfterTheRestoreTest(Rolled):
    def test_a_failed_hand_over_after_the_data_was_put_back_puts_the_newer_data_back(self):
        """The LOW in #280: updater.undo restores the data and then hands over. If the hand-over fails, the data must not be left
        at the old layout with the store closed: the newer file is put back, and the person is told to restart."""
        self.seams = MigratingSeams(self, answers=True)
        body = self.reviewed()
        self.assertEqual(200, self.up.install({"review_id": body["review_id"]})[0])
        self.assertEqual(h.OK, self.run_helper()[0])
        s = open_store(self.db, onedrive_roots=[])
        copy = s.migration_backup
        s.close()
        now = self.make(version="0.3.1", migration_backup=copy)
        now.settle()
        con = sqlite3.connect(str(self.db))
        con.execute("INSERT INTO projects (code, name) VALUES ('NEW', 'Added after the update')")
        con.commit()
        con.close()
        newest = rows(self.db, "projects")
        failing = self.make(version="0.3.1", migration_backup=copy, start=lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
        status, armed = failing.arm_undo({})
        status, body = failing.undo({"arm_id": armed["arm_id"]})
        self.assertEqual(409, status)
        self.assertEqual(str(store_module.SCHEMA_VERSION), version(self.db))          # still the newer layout
        self.assertEqual(newest, rows(self.db, "projects"))                           # with the change made after the update
        self.assertEqual([], [n for n in os.listdir(self.data) if n.startswith("clark.db.restoring")])


class ParityTest(unittest.TestCase):
    """The helper's put-back and backup.restore_before_update leave the same files on the same input."""

    def build(self, root):
        data = Path(root) / "data"
        data.mkdir()
        db = make_v1(data)
        # the copy is the v1 file as the migration would have taken it
        copy = backup.make(db, data / "backups", [], "migrate")
        con = sqlite3.connect(str(db))
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(store_module.SCHEMA_VERSION),))
        con.execute("INSERT INTO projects (code, name) VALUES ('NEW', 'Added later')")
        con.commit()
        con.close()
        return db, copy

    def files(self, db):
        out = {}
        for p in sorted(db.parent.rglob("*")):
            rel = p.relative_to(db.parent).as_posix()
            if p.is_file() and not rel.endswith(".restore.lock") and "-restore.db" not in rel:
                out[rel.split("replaced-")[0] + ("replaced/" + p.name if "replaced-" in rel else "")] = digest(p)
        return out

    def test_same_live_file_same_aside_same_leftovers(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            db_a, copy_a = self.build(a)
            db_b, copy_b = self.build(b)
            con = sqlite3.connect(str(db_b))
            before = {t: v for t, v in h.table_stats(con).items()}
            con.close()
            backup.restore_before_update(db_a, copy_a.name, confirmed=True, folder=db_a.parent / "backups", onedrive_roots=[])
            aside, changed = h.put_back_database(db_b, copy_b, 1, "i1", before)
            self.assertTrue(changed)
            self.assertEqual(digest(db_a), digest(db_b))                    # the restored file is the copy, byte for byte
            self.assertEqual(digest(copy_a), digest(db_a))
            for db in (db_a, db_b):
                kept = sorted((db.parent / "backups").glob("replaced-*"))
                self.assertEqual(1, len(kept))
                self.assertEqual(["clark.db"], sorted(p.name for p in kept[0].iterdir() if not p.name.endswith(("-wal", "-shm"))))
                self.assertEqual(str(store_module.SCHEMA_VERSION), version(kept[0] / "clark.db"))
                self.assertEqual([], [p.name for p in db.parent.iterdir() if p.name.startswith("clark.db.restoring")])
                self.assertEqual(0o700, kept[0].stat().st_mode & 0o777)

    def test_the_helpers_names_are_the_backup_modules(self):
        self.assertEqual(backup.RESTORING, h.RESTORING)
        self.assertEqual(backup.MARKER, h.RESTORE_MARKER)
        self.assertEqual(backup.LOCK_SUFFIX, h.LOCK_SUFFIX)
        self.assertTrue(backup.ASIDE.fullmatch(h.new_aside(tempfile.mkdtemp()).name))
        self.assertTrue(h.MIGRATE_COPY.fullmatch("clark-20261029T120005Z-migrate.db") and backup.NAME.fullmatch("clark-20261029T120005Z-migrate.db"))
        self.assertTrue(h.MIGRATE_COPY.fullmatch("clark-20261029T120005Z-migrate-2.db") and backup.NAME.fullmatch("clark-20261029T120005Z-migrate-2.db"))
        for name in ("clark-20261029T120005Z-daily.db", "clark-20261029T120005Z-restore.db", "../clark-20261029T120005Z-migrate.db"):
            self.assertIsNone(h.MIGRATE_COPY.fullmatch(name))

    def test_a_put_back_that_stopped_between_the_moves_is_finished_like_finish_restore(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            db_a, copy_a = self.build(a)
            db_b, copy_b = self.build(b)
            for db, copy in ((db_a, copy_a), (db_b, copy_b)):                    # stop after the old file was moved, before the new went in
                restoring = db.with_name("clark.db.restoring")
                shutil.copyfile(copy, restoring)
                aside = db.parent / "backups" / "replaced-20261029T120005Z"
                aside.mkdir()
                h.write_json(db.with_name("clark.db.restoring.json"), {"aside": aside.name})
                os.rename(db, aside / "clark.db")
            backup.finish_restore(db_a)
            self.assertTrue(h.finish_put_back(db_b))
            self.assertEqual(digest(db_a), digest(db_b))
            self.assertFalse(db_b.with_name("clark.db.restoring.json").exists())


if __name__ == "__main__":
    unittest.main()

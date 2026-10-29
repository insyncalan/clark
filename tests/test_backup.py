"""#86: backups before every undo and import, and a daily one (src/clark/backup.py and the SQL in src/clark/store.py).

Run: python3 dev/run_tests.py test_backup      (also by hand on /usr/bin/python3, the Mac's 3.9: its SQLite leaves a -shm file
behind that Python 3.15's removes, which is why test 1 looks at the folder; no CI job runs 3.9 on this file's whole tier)
The numbers in the test names are the numbers of the design note (docs/handoff/design-86-backups.md, section 6). Fictional data
only, in temporary folders; the real data folder and OneDrive are never read.
"""
import ast
import errno
import inspect
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
import _workbook as wbk
from _demo import USER, DemoStore
from clark import backup, excel_import as xi, platform as pl, store as cs
from clark.store import Invalid, open_store

SRC = _paths.SRC / "clark"
FIXED = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
WINDOWS = os.name == "nt"


class Clock:
    """Stands in for store.clock: a fixed UTC time that a test moves."""

    def __init__(self, t=FIXED):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def dump(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return "\n".join(con.iterdump())
    finally:
        con.close()


def rows(path, sql, *args):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


class Backed(unittest.TestCase):
    """A demo store (project ABC) whose backups folder starts empty and whose clock is fixed."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.path = self.s.path
        self.folder = self.s.backups_dir
        self.clock = Clock()
        patch = mock.patch.object(cs, "clock", self.clock)
        patch.start()
        self.addCleanup(patch.stop)
        self.wipe()

    def wipe(self):
        if self.folder.is_dir():
            for p in self.folder.iterdir():
                shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()

    def names(self, tag=None):
        if not self.folder.exists():
            return []
        return sorted(p.name for p in self.folder.iterdir() if tag is None or p.name.endswith(f"-{tag}.db") or f"-{tag}-" in p.name)

    def copies(self):
        return [e.name for e in backup.entries(self.folder)]

    def edit(self, n=1):
        for _ in range(n):
            self.demo.action()

    def workbook(self, name="ABC.xlsx"):
        tmp = Path(tempfile.mkdtemp(prefix="clark-xlsx-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        return wbk.make_workbook(self.s, tmp / name)

    def plan(self, path):
        return xi.read_workbook(self.s, path, "ABC", allow_unrecorded=True)

    def accept_all(self, plan):
        for c in plan.changes:
            plan.accept(c.n)
        return plan


# ── 1 to 3: the copy ──────────────────────────────────────────────────────────

class TheCopy(Backed):
    def test_1_a_copy_is_a_valid_database_with_the_same_rows(self):
        self.edit(3)
        dest = pl.private_file(self.demo.dir / "copy.part")
        summary = cs.snapshot(self.path, dest)
        self.assertEqual(rows(dest, "PRAGMA integrity_check"), [("ok",)])
        self.assertEqual(rows(dest, "PRAGMA journal_mode"), [("delete",)])
        for table in cs.TABLES + tuple(cs.HISTORY_COUNTS):
            with self.subTest(table=table):
                live = self.s.con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                self.assertEqual(rows(dest, f"SELECT count(*) FROM {table}")[0][0], live)
                self.assertEqual(summary["rows"][table], live)
        self.assertEqual(rows(dest, "SELECT max(apply_id) FROM applies")[0][0], self.demo.last_step())
        self.assertEqual(summary["last_step"], self.demo.last_step())
        self.assertEqual(sorted(p.name for p in self.demo.dir.iterdir() if p.name.startswith("copy")), ["copy.part"],
                         "no -wal, -shm or -journal is left beside the copy (Python 3.9's SQLite leaves one)")

    def test_10_a_copy_whose_row_counts_differ_from_the_source_is_refused_and_removed(self):
        self.edit(2)
        real = cs._summary
        seen = []

        def lying(con):
            out = real(con)
            seen.append(out)
            if len(seen) == 2:                                    # the second look is the copy's
                out = {**out, "rows": {**out["rows"], "actions": out["rows"]["actions"] - 1}}
            return out

        dest = pl.private_file(self.demo.dir / "copy.part")
        with mock.patch.object(cs, "_summary", lying), self.assertRaisesRegex(Invalid, "^One was made, but clark could not confirm it is complete, so it was not kept\\.$"):
            cs.snapshot(self.path, dest)
        self.assertFalse(dest.exists(), "a copy that doesn't match is not kept")
        self.assertEqual(len(seen), 2, "the source was counted once and the copy once")
        self.assertEqual(real(self.s.con)["rows"]["actions"], 2)

    def test_1_a_finished_backup_folder_holds_only_finished_db_files(self):
        self.edit()
        backup.take(self.s, "undo")
        backup.take(self.s, "daily")
        self.assertTrue(self.names() and all(n.endswith(".db") and not n.startswith(".") for n in self.names()), self.names())

    def test_2_every_copy_taken_while_steps_commit_is_consistent(self):
        self.edit()
        stop, errors = threading.Event(), []

        def writer():
            try:
                other, n = open_store(self.path, onedrive_roots=[]), 0
                while not stop.is_set():
                    n += 1
                    with other.step("dashboard", USER) as st:          # two changes in one step
                        st.update("actions", "ABC-A-001", {"latest_update": f"update {n}", "owner": f"Owner {n}"})
                other.close()
            except BaseException as e:        # noqa: BLE001
                errors.append(e)

        thread = threading.Thread(target=writer)
        thread.start()
        copies, deadline = [], time.monotonic() + 3          # a few seconds of wall time, not a fixed number of steps
        try:
            while time.monotonic() < deadline or len(copies) < 10:
                dest = pl.private_file(self.demo.dir / f"c{len(copies)}.part")
                cs.snapshot(self.path, dest)
                copies.append(dest)
        finally:
            stop.set()
            thread.join(30)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(copies), 10)
        live = dict(rows(self.path, "SELECT apply_id, count(*) FROM change_log GROUP BY apply_id"))
        for dest in copies:
            with self.subTest(copy=dest.name):
                self.assertEqual(rows(dest, "SELECT count(*) FROM change_log WHERE apply_id NOT IN (SELECT apply_id FROM applies)"),
                                 [(0,)], "(a) no change without its step")
                self.assertEqual(rows(dest, "SELECT count(*) FROM applies WHERE apply_id NOT IN "
                                            "(SELECT apply_id FROM change_log WHERE apply_id IS NOT NULL)"), [(0,)],
                                 "(b) no step without its changes")
                for apply_id, n in rows(dest, "SELECT apply_id, count(*) FROM change_log GROUP BY apply_id"):
                    self.assertEqual(n, live[apply_id], f"(c) step {apply_id} is whole in the copy")

    def test_3_a_copy_is_a_whole_file_or_nothing(self):
        real_snapshot, seen = cs.snapshot, []

        def watching(path, dest):
            seen.extend(self.names())                  # a listing taken during the copy
            return real_snapshot(path, dest)

        with mock.patch.object(cs, "snapshot", watching):
            backup.take(self.s, "undo")
        self.assertEqual([n for n in seen if backup.NAME.fullmatch(n)], [], "no .db is visible until it is whole")
        self.wipe()

        def half(path, dest):
            Path(dest).write_bytes(b"SQLite format 3\0" + b"x" * 500)
            raise Invalid("The backup could not be saved.")

        with mock.patch.object(cs, "snapshot", half), self.assertRaises(Invalid):
            backup.take(self.s, "undo")
        self.assertEqual(self.names(), [])
        with mock.patch.object(pl, "move_unless_exists", side_effect=OSError(errno.EIO, "Input/output error")), \
                self.assertRaises(Invalid):
            backup.take(self.s, "undo")
        self.assertEqual(self.names(), [], "no .db, no .part, no sidecar")

    def test_3_a_working_name_that_is_taken_is_tried_again(self):
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        tokens = iter(["aaaaaaaa", "aaaaaaaa", "bbbbbbbb"])
        first = self.folder / f".clark-20300102T030405Z-undo.{os.getpid()}.aaaaaaaa.part"
        first.write_bytes(b"someone else's")
        with mock.patch.object(backup.secrets, "token_hex", lambda n: next(tokens)):
            made = backup.take(self.s, "undo")
        self.assertEqual(first.read_bytes(), b"someone else's", "never written into")
        self.assertTrue(made.is_file())


# ── 4 to 7: names, failure, daily, undo ───────────────────────────────────────

class Names(Backed):
    def test_4_names_are_utc_without_colons_and_never_overwrite(self):
        made = [backup.take(self.s, "undo") for _ in range(3)]
        self.assertEqual([p.name for p in made], ["clark-20300102T030405Z-undo.db", "clark-20300102T030405Z-undo-2.db",
                                                  "clark-20300102T030405Z-undo-3.db"])
        self.assertTrue(all(":" not in p.name and backup.NAME.fullmatch(p.name) for p in made))
        for tag in backup.TAGS:
            self.assertTrue(backup.NAME.fullmatch(f"clark-20300102T030405Z-{tag}.db"), tag)
        self.assertFalse(backup.NAME.fullmatch("clark-20300102T030405Z-other.db"))
        planted = self.folder / "clark-20300102T030405Z-import.db"
        planted.write_bytes(b"mine")
        again = backup.take(self.s, "import")
        self.assertEqual((planted.read_bytes(), again.name), (b"mine", "clark-20300102T030405Z-import-2.db"))

    def test_4_the_name_follows_the_utc_clock_not_the_local_one(self):
        self.clock.t = datetime(2030, 6, 30, 23, 59, 59, tzinfo=timezone(timedelta(hours=-5)))
        self.assertEqual(backup.take(self.s, "daily").name, "clark-20300630T235959Z-daily.db",
                         "the fixed clock is a UTC one; a store's clock always is")


class Failing(Backed):
    ENOSPC = OSError(errno.ENOSPC, "No space left on device")

    def full(self):
        return mock.patch.object(cs, "snapshot", side_effect=self.ENOSPC)

    def test_5_a_failed_backup_stops_an_undo_and_changes_nothing(self):
        self.edit()
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        self.wipe()
        before = dump(self.path)
        with self.full(), self.assertRaises(Invalid) as ctx:
            self.s.undo(step, USER)
        self.assertEqual(str(ctx.exception), f"A backup of your data must be made first, and it couldn't be. Nothing was changed. "
                                             f"The backups folder {self.folder} can't be written to (the disk is full). "
                                             "Check that the backups folder exists and has space, then try again.")
        self.assertEqual(dump(self.path), before)
        self.assertEqual(self.names(), [])

    def test_7b_whatever_goes_wrong_with_the_daily_copy_is_only_a_warning(self):
        for error in (RuntimeError("odd"), KeyError("k"), sqlite3.DatabaseError("x")):
            with self.subTest(error=type(error).__name__):
                self.wipe()
                with mock.patch.object(backup, "_write", side_effect=error), self.assertLogs("clark.backup", "WARNING"):
                    self.edit()
                self.assertIn("Your change was saved, but today's backup of your data couldn't be made.", self.s.backup_warning)
                self.assertNotIn("odd", self.s.backup_warning)

    def test_a_hard_linked_file_with_a_backup_name_is_not_a_backup(self):
        """A second name for a file elsewhere is not a copy clark made: it is not listed, not restored and prune never touches it."""
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        elsewhere = self.demo.dir / "someones-file.db"
        shutil.copyfile(backup.take(self.s, "daily"), elsewhere)
        self.wipe()
        link = self.folder / "clark-20200101T000000Z-daily.db"
        try:
            os.link(elsewhere, link)
        except (OSError, NotImplementedError, AttributeError):
            self.skipTest("hard links aren't available here")
        self.assertEqual(self.copies(), [])
        self.assertEqual(backup.listing(self.folder), [])
        with self.assertRaises(Invalid):
            backup.restore_path(self.path, link.name, self.folder, [])
        for i in range(15):
            self.clock.advance(days=1)
            backup.take(self.s, "daily")
        self.assertTrue(link.exists(), "never removed")
        self.assertTrue(elsewhere.exists())

    def test_5_the_same_for_a_team_step(self):
        before = dump(self.path)
        with self.full(), self.assertRaisesRegex(Invalid, "^The import was stopped, because a backup of your data must be made first"):
            with self.s.step("team", USER) as st:
                st.create("actions", {"project": "ABC", "description": "x", "raised": "2026-10-01", "source": "demo"})
        self.assertEqual(dump(self.path), before)
        self.assertFalse(self.s.con.in_transaction)

    def test_7_a_failed_daily_copy_only_warns_and_the_change_is_saved(self):
        self.assertIsNone(self.s.backup_warning)
        with self.full(), self.assertLogs("clark.backup", "WARNING"):
            self.edit()                                                      # no copy for today yet: the daily one is due
        self.assertEqual(len(self.s.read("actions", "ABC")), 1, "the change went in")
        self.assertEqual(self.names(), [], "and there is still no copy")
        self.assertEqual(self.s.backup_warning,
                         "Your change was saved, but today's backup of your data couldn't be made. A new try is made with your "
                         f"next change. The backups folder {self.folder} can't be written to (the disk is full). To keep "
                         "your backups up to date, check that the backups folder exists and has space.")
        with self.full(), self.assertLogs("clark.backup", "WARNING"):
            self.edit()                                                      # still full: warns again, still saved
        self.assertEqual(len(self.s.read("actions", "ABC")), 2)
        self.edit()                                                          # the disk is back: the daily copy is made and the warning goes
        self.assertEqual(len(self.copies()), 1)
        self.assertIsNone(self.s.backup_warning)

    def test_7_a_failed_undo_copy_still_stops_the_undo(self):
        self.edit()
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        before = dump(self.path)
        self.wipe()
        with self.full(), self.assertRaisesRegex(Invalid, "^A backup of your data must be made first, and it couldn't be"):
            self.s.undo(step, USER)
        self.assertEqual(dump(self.path), before)

    def test_7_a_failed_import_copy_still_refuses_the_import_and_nothing_turns_that_off(self):
        action = self.demo.action()
        path = self.workbook()
        wbk.edit(path, "Actions", action, owner="Sam Example")
        self.wipe()
        plan = self.accept_all(self.plan(path))
        before = dump(self.path)
        for _ in range(2):                                                   # the daily copy failing before it changes nothing here
            with self.full():
                res = xi.apply_import(self.s, plan, USER)
            self.assertFalse(res.applied)
            self.assertTrue(res.message.startswith("The import was stopped, because a backup of your data must be made first"))
            self.assertEqual(dump(self.path), before)

    def test_5_the_same_for_an_excel_import_and_14_the_gate_message_is_pinned(self):
        action = self.demo.action()
        path = self.workbook()
        wbk.edit(path, "Actions", action, owner="Sam Example")
        self.wipe()
        plan = self.accept_all(self.plan(path))
        before = dump(self.path)
        with self.full():
            res = xi.apply_import(self.s, plan, USER)
        self.assertFalse(res.applied)
        self.assertEqual(res.message, "The import was stopped, because a backup of your data must be made first and it couldn't "
                                      f"be. Nothing was imported. The backups folder {self.folder} can't be written to (the disk is "
                                      "full). Check that the backups folder exists and you can save files there, then "
                                      "import again.")
        self.assertEqual(dump(self.path), before)

    def test_14_the_gate_refuses_an_import_into_any_database_when_the_folder_cannot_be_written(self):
        action = self.demo.action()
        path = self.workbook()
        wbk.edit(path, "Actions", action, owner="Sam Example")
        shutil.rmtree(self.folder)
        self.folder.write_text("not a folder", encoding="utf-8")            # nothing can be made there
        plan = self.accept_all(self.plan(path))
        before = dump(self.path)
        res = xi.apply_import(self.s, plan, USER)
        self.assertFalse(res.applied)
        self.assertRegex(res.message, r"^The import was stopped, because a backup of your data must be made first and it "
                                      r"couldn't be\. Nothing was imported\. .*backups is a file, not a folder\. Rename or move "
                                      r"it, then try again\.$")
        self.assertEqual(dump(self.path), before)
        self.folder.unlink()
        self.assertTrue(xi.apply_import(self.s, self.accept_all(self.plan(path)), USER).applied, "and with the folder back it goes")

    @unittest.skipIf(WINDOWS or hasattr(os, "geteuid") and os.geteuid() == 0, "a folder that can't be written is by permission")
    def test_14_a_data_folder_that_cannot_be_written_refuses_the_import_too(self):
        action = self.demo.action()
        path = self.workbook()
        wbk.edit(path, "Actions", action, owner="Sam Example")
        plan = self.accept_all(self.plan(path))
        shutil.rmtree(self.folder)
        os.chmod(self.demo.dir, 0o500)
        self.addCleanup(os.chmod, self.demo.dir, 0o700)
        res = xi.apply_import(self.s, plan, USER)
        self.assertFalse(res.applied)
        self.assertIn("isn't allowed to use it", res.message)
        self.assertIn("Nothing was imported.", res.message)
        self.assertTrue(res.message.endswith("then import again."), res.message)

    def test_14_there_is_no_setting_or_environment_variable_that_turns_the_hook_off(self):
        text = (SRC / "backup.py").read_text(encoding="utf-8") + (SRC / "store.py").read_text(encoding="utf-8")
        self.assertNotIn("environ", (SRC / "backup.py").read_text(encoding="utf-8"))
        self.assertNotRegex(text, r"CLARK_NO_BACKUP|backups\.off|skip_backup")


class Daily(Backed):
    def test_6_the_first_step_of_a_day_makes_the_daily_copy_and_the_second_does_not(self):
        self.edit()
        self.assertEqual(self.copies(), ["clark-20300102T030405Z-daily.db"])
        self.edit()
        self.assertEqual(len(self.copies()), 1)

    def test_6_a_new_utc_day_makes_another(self):
        self.edit()
        self.clock.advance(hours=20)                 # 23:04 the same day
        self.edit()
        self.assertEqual(len(self.copies()), 1)
        self.clock.advance(hours=1)                  # 00:04 the next day
        self.edit()
        self.assertEqual([e.stamp[:8] for e in backup.entries(self.folder)], ["20300102", "20300103"])

    def test_6_an_undo_that_opens_the_day_is_the_days_copy(self):
        self.edit()
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        self.clock.advance(days=1)
        self.s.undo(step, USER)
        self.assertEqual([e.tag for e in backup.entries(self.folder)], ["daily", "undo"])
        self.edit()
        self.assertEqual(len(self.copies()), 2, "so no daily one follows it")

    def test_6_a_brand_new_store_decides_the_same_way_because_nothing_is_remembered(self):
        self.edit()
        self.assertEqual(len(self.copies()), 1)
        for _ in range(3):
            other = open_store(self.path, onedrive_roots=[])
            with other.step("dashboard", USER) as st:
                st.create("actions", {"project": "ABC", "description": "x", "raised": "2026-10-01", "source": "demo"})
            other.close()
        self.assertEqual(len(self.copies()), 1)
        self.clock.advance(days=1)
        other = open_store(self.path, onedrive_roots=[])
        with other.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": "x", "raised": "2026-10-01", "source": "demo"})
        other.close()
        self.assertEqual(len(self.copies()), 2)

    def test_6_backup_py_remembers_nothing_but_its_lock(self):
        tree = ast.parse((SRC / "backup.py").read_text(encoding="utf-8"))
        names = [t.id for node in tree.body if isinstance(node, ast.Assign) for t in node.targets if isinstance(t, ast.Name)]
        self.assertEqual([n for n in names if not n.isupper() and n != "_lock"], [], "only constants, and the lock")
        stores = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                  and isinstance(n.value, ast.Name) and n.value.id == "store"]
        self.assertEqual(sorted(set(stores)), ["_backup_hold", "backup_warning"],
                         "it sets the with-scoped flag and a warning for the person; it never reads the warning back")
        self.assertNotRegex((SRC / "backup.py").read_text(encoding="utf-8"), r"=\s*store\.backup_warning|if store\.backup_warning")
        self.assertFalse([n for n in ast.walk(tree) if isinstance(n, ast.Global)], "no `global` statement")
        self.assertTrue(isinstance(backup._lock, type(threading.Lock())))


class Undo(Backed):
    def test_7_undo_then_undo_again_takes_two_backups_both_valid(self):
        self.edit()
        one = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        two = self.demo.update("actions", "ABC-A-001", {"owner": "Alex Example"})
        self.wipe()
        self.s.undo(two, USER)
        self.s.undo(one, USER)
        undo = [e for e in backup.entries(self.folder) if e.tag == "undo"]
        self.assertEqual(len(undo), 2)
        for e in undo:
            cs.check_copy(e.path)

    def test_7_a_restore_then_two_edits_then_an_undo_takes_its_backup(self):
        self.edit()
        name = backup.take(self.s, "daily").name
        backup.restore_over(self.s, name)
        self.s = open_store(self.path, onedrive_roots=[])
        self.demo.store = self.s
        self.edit(2)
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        before = len(self.names("undo"))
        self.s.undo(step, USER)
        self.assertEqual(len(self.names("undo")), before + 1)

    def test_7_backup_once_over_three_steps_makes_one(self):
        self.edit()
        self.wipe()
        with self.s.backup_once("changes"):
            self.edit(3)
            self.assertFalse(self.s.con.in_transaction)
        self.assertEqual([e.tag for e in backup.entries(self.folder)], ["changes"])
        self.edit()
        self.assertEqual([e.tag for e in backup.entries(self.folder)], ["changes"], "the day already has a copy, and nothing outlives the with")
        with self.assertRaises(RuntimeError):
            with self.s.backup_once("changes"):
                raise RuntimeError("a failure inside")
        self.assertIsNone(self.s._backup_hold)
        self.assertEqual(len([e for e in backup.entries(self.folder) if e.tag == "changes"]), 2)

    def test_dry_takes_no_backup_and_an_unknown_tag_is_refused(self):
        self.wipe()
        with self.s.step("excel", USER, dry=True) as st:
            st.create("actions", {"project": "ABC", "description": "x", "raised": "2026-10-01", "source": "demo"})
        self.assertEqual(self.names(), [])
        with self.assertRaises(ValueError), self.s.backup_once("weekly"):
            pass

    def test_l3_a_dry_step_never_commits_whatever_it_wrote(self):
        """L3: dry=True used to skip the copy AND commit, so it was a silent way to write with no backup."""
        self.wipe()
        before = dump(self.path)
        for route in ("excel", "undo", "team", "dashboard"):
            with self.s.step(route, USER, dry=True) as st:
                st.create("actions", {"project": "ABC", "description": "dry", "raised": "2026-10-01", "source": "demo"})
                self.assertTrue(self.s.con.in_transaction)
            self.assertFalse(self.s.con.in_transaction)
            self.assertEqual(dump(self.path), before, f"nothing from a dry {route} step was kept")
        self.assertEqual(self.names(), [])

    def test_l3_the_gate_cannot_be_switched_off_by_a_caller(self):
        self.edit()
        self.wipe()
        other = open_store(self.path, onedrive_roots=[])
        self.addCleanup(other.close)
        self.assertFalse(hasattr(other, "backup_held"), "there is no public switch")
        self.s.backup_held = True                           # the old public name: now just an attribute nothing reads
        self.s._backup_hold = True                          # the private one, set to anything but the backup code's own mark
        self.s._backup_hold = object()
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        self.wipe()
        self.s.undo(step, USER)
        self.assertEqual([e.tag for e in backup.entries(self.folder)], ["undo"], "an undo still takes its copy")
        self.wipe()
        self.s._backup_hold = None
        with self.s.backup_once("changes"):
            self.assertIs(self.s._backup_hold, backup._HOLD)
        self.assertIsNone(self.s._backup_hold)
        self.assertNotIn("backup_held", inspect.signature(cs.Store.step).parameters)
        self.assertNotIn("backup_held", inspect.signature(cs.Store.__init__).parameters)


# ── 8, 19: retention ──────────────────────────────────────────────────────────

class Retention(Backed):
    def plant(self, tag, n, start=0, source=None):
        """n valid copies named for consecutive seconds, oldest first; their file times follow the names."""
        self.folder.mkdir(exist_ok=True)
        if source is None:
            source = self.demo.dir / "source.db"
            if not source.exists():
                shutil.copyfile(backup.take(self.s, "restore"), source)
                self.wipe()
                self.folder.mkdir(exist_ok=True)
        made = []
        for i in range(start, start + n):
            stamp = (FIXED + timedelta(seconds=i)).strftime("%Y%m%dT%H%M%SZ")
            p = self.folder / f"clark-{stamp}-{tag}.db"
            shutil.copyfile(source, p)
            os.utime(p, (1_900_000_000 + i, 1_900_000_000 + i))
            made.append(p.name)
        return made

    def test_l1_forty_copies_in_one_second_each_exist_when_made_and_the_newest_fourteen_stay(self):
        """L1: 15 same-kind copies in one second used to make the 16th reuse a freed name, sort as the oldest and be removed at once."""
        self.wipe()
        made = []
        for _ in range(40):
            path = backup.take(self.s, "undo")
            self.assertTrue(path.exists(), f"{path.name} was removed straight after it was made")
            made.append(path.name)
        self.assertEqual(len(set(made)), 40, "no name is used twice")
        self.assertEqual(self.names("undo"), sorted(made[-14:]), "the newest fourteen stay, the older ones go")
        counters = [backup.NAME.fullmatch(n).group(3) for n in made]
        self.assertEqual([int(c) if c else 1 for c in counters], list(range(1, 41)), "one more than the highest, never a freed number")

    def test_l1_three_programs_taking_twelve_copies_each_in_one_second_lose_none_when_made(self):
        self.wipe()
        script = (
            "import sys, os\n"
            "from datetime import datetime, timezone\n"
            "from clark import backup, store\n"
            "fixed = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)\n"
            "store.clock = lambda: fixed\n"
            "gone = 0\n"
            "for _ in range(12):\n"
            "    p = backup.make(sys.argv[1], sys.argv[2], [], 'undo')\n"
            "    gone += 0 if os.path.exists(p) else 1\n"
            "print(gone)\n")
        env = dict(os.environ, PYTHONPATH=str(SRC.parent))
        procs = [subprocess.Popen([sys.executable, "-c", script, str(self.path), str(self.folder)], env=env, cwd=str(self.demo.dir),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(3)]
        outs = [p.communicate(timeout=300) for p in procs]
        for p, (out, err) in zip(procs, outs):
            self.assertEqual((p.returncode, err), (0, ""))
        self.assertEqual([out.strip() for out, _ in outs], ["0", "0", "0"], "none of the 36 was gone when its maker looked")
        self.assertEqual(len(self.names("undo")), 14)
        for e in backup.entries(self.folder):
            cs.check_copy(e.path)

    def test_l1_prune_never_removes_what_it_is_told_to_protect(self):
        self.wipe()
        made = self.plant("undo", 20)
        removed = backup.prune(self.folder, 14, protect=(self.folder / made[0],))
        self.assertNotIn(made[0], removed)
        self.assertTrue((self.folder / made[0]).exists())

    def test_8_the_newest_n_of_each_family_are_kept(self):
        self.wipe()
        source = self.demo.dir / "source.db"
        shutil.copyfile(backup.take(self.s, "daily"), source)
        self.wipe()
        daily = self.plant("daily", 20, 0, source)
        undo = self.plant("undo", 20, 100, source)
        imports = self.plant("import", 10, 200, source) + self.plant("changes", 5, 300, source)
        restores = self.plant("restore", 5, 400, source)
        removed = backup.prune(self.folder, 14)
        left = set(self.names())
        self.assertEqual(left & set(daily), set(daily[-14:]))
        self.assertEqual(left & set(undo), set(undo[-14:]), "a flood of undos leaves the dailies alone")
        self.assertEqual(left & set(imports), set(imports[-14:]), "import and changes are counted together")
        self.assertEqual(left & set(imports[:1]), set(), "and the restores are not in that count")
        self.assertEqual(sorted(left & set(restores)), sorted(restores), "restores are a family of their own: five are all kept")
        self.assertEqual(len(removed), 6 + 6 + 1)

    def test_5_keep_is_a_plain_constant_of_14_that_the_approval_note_carries(self):
        self.assertEqual(backup.KEEP, 14)
        text = (SRC / "backup.py").read_text(encoding="utf-8")
        self.assertIn("A constant on purpose until Settings exist", text)
        self.assertNotRegex(text, r"KEEP\s*=\s*(?:int|os\.|.*environ)")

    def test_8_with_an_empty_newest_backup_the_newest_one_with_rows_is_still_kept(self):
        self.wipe()
        good = self.plant("daily", 3)
        empty_dir = Path(tempfile.mkdtemp(prefix="clark-empty-"))
        self.addCleanup(shutil.rmtree, empty_dir, True)
        empty = open_store(empty_dir / "clark.db", onedrive_roots=[])
        dest = pl.private_file(self.folder / "clark-20300102T030500Z-undo.db")
        cs.snapshot(empty.path, dest)
        empty.close()
        backup.prune(self.folder, 1, newest_has_rows=False)
        self.assertEqual(self.names(), [good[-1], dest.name], "the empty one is the newest; the newest with rows survives")
        backup.prune(self.folder, 1)
        self.assertEqual(len(self.names()), 2, "and a prune that sees rows in the newest one removes nothing more here")

    def test_8_files_that_are_not_backups_are_left_alone(self):
        self.wipe()
        outside = self.demo.dir / "precious.db"
        outside.write_bytes(b"keep me")
        made = self.plant("undo", 3)
        (self.folder / "notes.txt").write_text("mine", encoding="utf-8")
        (self.folder / "clark-x.db").write_bytes(b"x")
        (self.folder / "clark-20300102T030400Z-undo.db.old").write_bytes(b"x")
        (self.folder / "clark-20300102T030400Z-undo.db.bak").mkdir()
        (self.folder / "clark-20300101T000000Z-undo.db").mkdir()                       # a folder with a backup's name
        (self.folder / "clark-20300101T000001Z-undo.db").symlink_to(outside)           # a link with a backup's name
        part = self.folder / f".clark-20300102T030400Z-undo.{os.getpid() + 1}.ab12cd34.part"
        part.write_bytes(b"another process, still working")
        aside = self.folder / "replaced-20300101T000000Z"
        aside.mkdir()
        (aside / "clark.db").write_bytes(b"an old database")
        backup.prune(self.folder, 1)
        self.assertEqual(self.names("undo")[-1:], [made[-1]])
        for kept in ("notes.txt", "clark-x.db", "clark-20300102T030400Z-undo.db.old", "clark-20300102T030400Z-undo.db.bak",
                     "clark-20300101T000000Z-undo.db", "clark-20300101T000001Z-undo.db", part.name, "replaced-20300101T000000Z"):
            self.assertTrue(os.path.lexists(self.folder / kept), kept)
        self.assertEqual((outside.read_bytes(), (aside / "clark.db").read_bytes()), (b"keep me", b"an old database"))
        self.assertNotIn(made[0], self.names())

    def test_8_an_old_unfinished_working_file_is_removed(self):
        self.wipe()
        self.plant("undo", 1)
        old = self.folder / f".clark-20300102T030400Z-undo.{os.getpid()}.ab12cd34.part"
        old.write_bytes(b"x")
        long_ago = time.time() - 3 * 24 * 3600
        os.utime(old, (long_ago, long_ago))
        backup.prune(self.folder, 14)
        self.assertFalse(old.exists())

    def test_8_a_working_file_that_vanishes_while_the_folder_is_read_does_not_stop_the_clean_up(self):
        self.wipe()
        long_ago = time.time() - 3 * 24 * 3600
        gone = self.folder / f".clark-20300102T030400Z-undo.{os.getpid()}.ab12cd34.part"
        old = self.folder / f".clark-20300102T030401Z-undo.{os.getpid()}.ab12cd35.part"
        for p in (gone, old):
            p.write_bytes(b"x")
            os.utime(p, (long_ago, long_ago))
        scan = os.scandir

        class Vanishing:
            def __init__(self, entry):
                self.entry = entry
                self.name, self.path = entry.name, entry.path

            def is_file(self, **kw):
                return self.entry.is_file(**kw)

            def stat(self, **kw):
                if self.name == gone.name:
                    raise FileNotFoundError(errno.ENOENT, "No such file or directory")
                return self.entry.stat(**kw)

        class Scan:
            def __init__(self, folder):
                self.inner = scan(folder)

            def __enter__(self):
                return (Vanishing(e) for e in self.inner.__enter__())

            def __exit__(self, *a):
                return self.inner.__exit__(*a)

        with mock.patch.object(backup.os, "scandir", Scan):
            backup._clear_old_parts(self.folder)
        self.assertFalse(old.exists(), "the others are still cleaned up")
        self.assertTrue(gone.exists(), "and the one that could not be read is left alone")

    def test_8_the_newest_is_never_removed_and_a_failed_backup_prunes_nothing(self):
        self.wipe()
        made = self.plant("undo", 20)
        backup.prune(self.folder, 0)                                    # a nonsense count still keeps one
        self.assertEqual(self.names("undo"), [made[-1]])
        self.wipe()
        self.plant("undo", 20)
        with mock.patch.object(cs, "snapshot", side_effect=OSError(errno.EIO, "Input/output error")), self.assertRaises(Invalid):
            backup.take(self.s, "undo")
        self.assertEqual(len(self.names("undo")), 20)

    def test_8_a_backups_folder_that_is_a_link_to_elsewhere_is_refused(self):
        self.edit()
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        elsewhere = self.demo.dir / "elsewhere"
        elsewhere.mkdir()
        shutil.rmtree(self.folder)
        self.folder.symlink_to(elsewhere)
        before = dump(self.path)
        with self.assertRaisesRegex(Invalid, "^A backup of your data must be made first, and it couldn't be"):
            self.s.undo(step, USER)                          # an undo is stopped; a daily copy would only warn (test_7)
        self.assertEqual((list(elsewhere.iterdir()), dump(self.path)), ([], before))

    def test_19_newest_means_time_then_file_time_then_counter_as_a_number(self):
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        source = self.demo.dir / "source.db"
        shutil.copyfile(backup.take(self.s, "restore"), source)
        self.wipe()
        for name in ("clark-20300102T030405Z-undo.db", "clark-20300102T030405Z-undo-2.db",
                     "clark-20300102T030405Z-undo-10.db", "clark-20300102T030405Z-undo-9.db"):       # one file time: the counter decides
            shutil.copyfile(source, self.folder / name)
            os.utime(self.folder / name, (1_900_000_000, 1_900_000_000))
        backup.prune(self.folder, 1)
        self.assertEqual(self.names(), ["clark-20300102T030405Z-undo-10.db"], "-10 is newer than -9, which text order gets wrong")
        self.wipe()
        for name, when in (("clark-20300102T030405Z-undo-10.db", 1), ("clark-20300102T030405Z-undo-9.db", 2)):   # file time before counter
            shutil.copyfile(source, self.folder / name)
            os.utime(self.folder / name, (1_900_000_000 + when, 1_900_000_000 + when))
        backup.prune(self.folder, 1)
        self.assertEqual(self.names(), ["clark-20300102T030405Z-undo-9.db"], "the later file is the newer one, whatever its counter")
        self.wipe()
        for name, when in (("clark-20300102T030405Z-undo.db", 5), ("clark-20300102T030405Z-undo-2.db", 6)):      # the same pair, other order
            shutil.copyfile(source, self.folder / name)
            os.utime(self.folder / name, (1_900_000_000 + when, 1_900_000_000 + when))
        backup.prune(self.folder, 1)
        self.assertEqual(self.names(), ["clark-20300102T030405Z-undo-2.db"], "-2 is newer than none, which text order gets wrong")
        self.wipe()
        for name, when in (("clark-20300102T030406Z-undo.db", 1), ("clark-20300102T030405Z-undo-3.db", 9)):
            shutil.copyfile(source, self.folder / name)
            os.utime(self.folder / name, (1_900_000_000 + when, 1_900_000_000 + when))
        backup.prune(self.folder, 1)
        self.assertEqual(self.names(), ["clark-20300102T030405Z-undo-3.db"], "the file time comes first: the time in the name is a clock's word")


# ── 9, 10: where it writes ────────────────────────────────────────────────────

class Where(unittest.TestCase):
    def test_9_nothing_outside_backups_changes(self):
        base = Path(tempfile.mkdtemp(prefix="clark-where-")).resolve()
        self.addCleanup(shutil.rmtree, base, True)
        (base / "data").mkdir()
        (base / "sibling.txt").write_text("mine", encoding="utf-8")
        store = open_store(base / "data" / "clark.db", onedrive_roots=[])
        self.addCleanup(store.close)
        with store.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme"})

        def listing():
            return sorted(str(p.relative_to(base)) for p in base.rglob("*")
                          if "backups" not in p.relative_to(base).parts and p.name != "backups")

        before = listing()
        made = backup.take(store, "undo")
        backup.prune(store.backups_dir, 1)
        name = backup.take(store, "daily").name
        backup.restore_over(store, name)
        after = listing()
        db_files = {"data/clark.db", "data/clark.db-wal", "data/clark.db-shm", "data/clark.db.restoring.json"}
        self.assertEqual(sorted(set(after) - set(before) - db_files), [])
        self.assertEqual(sorted(set(before) - set(after) - db_files), [])
        self.assertTrue(made.parent.name == "backups")
        self.assertTrue((base / "sibling.txt").is_file())

    def test_10_a_data_folder_inside_onedrive_is_refused_and_so_is_a_backups_link_into_it(self):
        root = Path(tempfile.mkdtemp(prefix="clark-onedrive-")).resolve()
        self.addCleanup(shutil.rmtree, root, True)
        with self.assertRaises(pl.PlatformError):
            open_store(root / "data" / "clark.db", onedrive_roots=[root])
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.store.onedrive_roots = [root]
        demo.action()
        step = demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        (root / "synced").mkdir()
        shutil.rmtree(demo.store.backups_dir)
        demo.store.backups_dir.symlink_to(root / "synced")
        before = dump(demo.store.path)
        with self.assertRaises(Invalid) as ctx:
            demo.store.undo(step, USER)
        self.assertIn("Backups can't be kept in", str(ctx.exception))
        self.assertNotIn("backups can still go to OneDrive", str(ctx.exception))
        self.assertEqual((list((root / "synced").iterdir()), dump(demo.store.path)), ([], before), "refused before any write")


# ── 11 to 13, 20 to 24: restore ───────────────────────────────────────────────

class NoUserName(unittest.TestCase):
    """#86 review 6: a message that might be copied into a report or an email never carries the user's name (a path under the home
    folder is written from "~")."""

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        patch = mock.patch.object(Path, "home", return_value=self.home)
        patch.start()
        self.addCleanup(patch.stop)

    def test_6_the_onedrive_refusals_write_the_folder_from_the_home_folder(self):
        root = self.home / "OneDrive-DemoOrg"
        (root / "data").mkdir(parents=True)
        for what, words in (("backups", "Backups can't be kept in ~/OneDrive-DemoOrg/data because"),
                            ("data", "Your data can't be kept in ~/OneDrive-DemoOrg/data because")):
            with self.subTest(what=what), self.assertRaises(pl.PlatformError) as ctx:
                pl.check_data_dir(root / "data", [root], what=what)
            self.assertIn(words, str(ctx.exception))
            self.assertNotIn(str(self.home), str(ctx.exception))

    def test_6_the_causes_in_a_refusal_do_not_carry_it_either(self):
        (self.home / "real").mkdir()
        (self.home / "link").symlink_to(self.home / "real")
        locked = pl.PlatformError
        with self.assertRaises(locked) as shortcut:
            pl.private_folder(self.home / "link")
        with self.assertRaises(locked) as busy:
            pl.replace_file(self.home / "a", self.home / "b", attempts=1, replace=mock.Mock(side_effect=PermissionError(errno.EACCES, "x")))
        for ctx in (shortcut, busy):
            self.assertNotIn(str(self.home), str(ctx.exception))
            self.assertIn("~/", str(ctx.exception))
        (self.home / "backups").symlink_to(self.home / "real")
        with self.assertRaises(locked) as backups_link:
            pl.private_folder(self.home / "backups")
        said = backup.refusal("daily", self.home / "backups", backups_link.exception)
        self.assertNotIn(str(self.home), said)
        self.assertIn("~/backups", said)

    def test_l6_the_shortcut_refusal_names_the_folder_once_and_has_no_nested_brackets(self):
        """L6: it said the path twice and put brackets inside brackets."""
        (self.home / "real").mkdir()
        (self.home / "backups").symlink_to(self.home / "real")
        for tag, ending in (("undo", "Nothing was changed."), ("import", "Nothing was imported."), ("daily", "Nothing was changed.")):
            with self.assertRaises(pl.PlatformError) as ctx:
                pl.private_folder(self.home / "backups")
            said = backup.refusal(tag, self.home / "backups", ctx.exception)
            self.assertEqual(said.count("~/backups"), 1, said)
            self.assertNotIn("(", said)
            self.assertIn(ending, said)
            self.assertTrue(said.endswith(str(ctx.exception)), "the shortcut's own words, with what to do, come last")
        self.assertEqual(str(ctx.exception), "~/backups is a shortcut, not a real folder. Replace it with a real folder, then try "
                                             "again.")
        warning = backup.daily_warning(self.home / "backups", ctx.exception)
        self.assertEqual(warning.count("~/backups"), 1, warning)
        self.assertNotIn("(", warning)


class Restore(Backed):
    def setUp(self):
        super().setUp()
        self.edit(2)
        self.name = backup.take(self.s, "daily").name
        self.then = self.demo.last_step()

    def counts(self, path):
        return rows(path, "SELECT (SELECT count(*) FROM actions), (SELECT count(*) FROM applies)")[0]

    def test_l2_restoring_the_oldest_of_fourteen_restore_copies_does_not_delete_it_first(self):
        """L2: the copy a restore takes of what is there now made 15 restore copies, and retention removed the oldest, the one asked for."""
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        want = self.counts(self.path)
        chosen = self.folder / "clark-20290101T000000Z-restore.db"
        shutil.copyfile(backup.take(self.s, "daily"), chosen)
        for old in self.folder.glob("*-daily.db"):
            old.unlink()
        os.utime(chosen, (1_800_000_000, 1_800_000_000))
        for i in range(1, 14):
            other = self.folder / f"clark-2029010{1 + i // 10}T0000{i % 10:02d}Z-restore.db"
            shutil.copyfile(chosen, other)
            os.utime(other, (1_800_000_000 + i, 1_800_000_000 + i))
        self.assertEqual(len(self.names("restore")), 14)
        self.edit(3)
        backup.restore_over(self.s, chosen.name)
        self.assertEqual(self.counts(self.path), want, "the chosen copy was read and put back")
        self.assertEqual(len(self.names("restore")), 15, "and this once there are 15; the next retention trims them")
        self.assertTrue(chosen.exists())

    def test_l4_restore_says_whether_a_copy_of_what_was_there_was_taken(self):
        done = backup.restore_over(self.s, self.name)
        self.assertTrue(done["backed_up"])
        self.assertEqual(len(self.names("restore")), 1)
        for side in ("", "-wal", "-shm"):
            Path(str(self.path) + side).unlink(missing_ok=True)
        self.path.write_bytes(b"not a database" * 50)
        done = backup.restore_path(self.path, self.name, self.folder, [])
        self.assertFalse(done["backed_up"])
        self.assertEqual(len(self.names("restore")), 1, "no copy of the garbage was made")

    def test_l8_digits_of_other_scripts_are_not_a_backup_name(self):
        arabic = "".join(chr(0x0660 + int(c)) for c in "20300102") + "T" + "".join(chr(0x0660 + int(c)) for c in "030405") + "Z"
        self.assertTrue(arabic[0].isdigit() and not arabic[0].isascii())
        for name in (f"clark-{arabic}-undo.db", f"clark-20300102T030405Z-undo-{chr(0x0662)}.db"):
            self.assertIsNone(backup.NAME.fullmatch(name), name)
            (self.folder / name).write_bytes(b"x")
            with self.assertRaisesRegex(Invalid, "^No backup called .* is in "):
                backup.valid_name(self.folder, name)
        self.assertTrue(all(e.name.isascii() for e in backup.entries(self.folder)), "neither of them is listed")
        self.assertIsNone(backup.ASIDE.fullmatch(f"replaced-{arabic}"))
        self.assertIsNotNone(backup.ASIDE.fullmatch("replaced-20300102T030405Z-2"))

    def test_l8_a_second_restore_after_one_that_stopped_refuses_and_keeps_the_note(self):
        """The double fault: the second restore deleted the note and the waiting copy, failed, and clark then made a new empty database."""
        real = pl.replace_file

        def fail(src, dest, *a, **k):
            if Path(dest).name == "clark.db":
                raise pl.PlatformError("locked")
            return real(src, dest, *a, **k)

        with mock.patch.object(pl, "replace_file", fail), self.assertRaisesRegex(Invalid, "stopped part-way"):
            backup.restore_over(self.s, self.name)
        marker, waiting = self.path.with_name("clark.db.restoring.json"), self.path.with_name("clark.db.restoring")
        kept = (marker.read_bytes(), waiting.read_bytes())
        for _ in range(2):
            with self.assertRaisesRegex(Invalid, r"^An earlier restore stopped part-way, and clark\.db is missing\. Nothing was changed\. "
                                                 r"Start clark first: .* Then run restore again if you still want " + self.name):
                backup.restore_path(self.path, self.name, self.folder, [])
            self.assertEqual((marker.read_bytes(), waiting.read_bytes()), kept, "the note and the waiting copy are still there")
        self.assertFalse(self.path.exists())
        done = open_store(self.path, onedrive_roots=[])
        self.addCleanup(done.close)
        self.assertEqual(len(done.read("actions", "ABC")), 2, "starting clark finishes the first restore: the backup's rows, not an empty one")

    def test_l8_a_stray_working_file_of_the_note_is_cleaned_up(self):
        stray = self.path.with_name(".clark.db.restoring.json.4242.ab12cd34.part")
        fresh = self.path.with_name(".clark.db.restoring.json.4243.ab12cd35.part")
        other = self.path.with_name(".clark.db.restoring.json.notes.part")
        for p in (stray, fresh, other):
            p.write_bytes(b"{")
        os.utime(stray, (1_000_000_000, 1_000_000_000))
        self.s.close()
        open_store(self.path, onedrive_roots=[]).close()                      # starting clark: the old one goes, one being written stays
        self.assertEqual((stray.exists(), fresh.exists(), other.exists()), (False, True, True))
        backup.restore_path(self.path, self.name, self.folder, [])           # a restore holds the database, so none is being written
        self.assertEqual((fresh.exists(), other.exists()), (False, True))
        self.assertFalse(self.path.with_name("clark.db.restoring.json").exists())

    def test_11_restore_into_a_fresh_folder_reads_the_same_rows_and_history(self):
        want = self.counts(self.path)
        history = self.s.history("ABC-A-001")
        self.edit(3)
        fresh = Path(tempfile.mkdtemp(prefix="clark-fresh-")).resolve() / "data"
        self.addCleanup(shutil.rmtree, fresh.parent, True)
        dest = backup.restore_into(fresh, self.name, self.folder, onedrive_roots=[])
        other = open_store(dest, onedrive_roots=[])
        self.addCleanup(other.close)
        self.assertEqual(self.counts(dest), want)
        self.assertEqual(other.history("ABC-A-001"), history)
        self.assertEqual(len(other.read("actions", "ABC")), 2)
        with self.assertRaisesRegex(Invalid, "isn't an empty folder"):
            backup.restore_into(fresh, self.name, self.folder, onedrive_roots=[])

    def test_12_restore_refuses_while_another_connection_has_the_file_open(self):
        self.edit()
        other = open_store(self.path, onedrive_roots=[])
        self.addCleanup(other.close)
        before = dump(self.path)
        with self.assertRaisesRegex(Invalid, "^Another window or program has clark's data open"):
            backup.restore_over(self.s, self.name)
        with self.assertRaises(sqlite3.ProgrammingError):
            self.s.con.execute("SELECT 1")                       # the store is closed
        self.assertEqual(dump(self.path), before)
        self.assertEqual([p.name for p in self.folder.iterdir() if p.name.startswith("replaced")], [])
        self.assertFalse((self.demo.dir / "clark.db.restoring").exists())

    def test_12_it_refuses_a_truncated_file_another_database_and_a_newer_schema(self):
        data = (self.folder / self.name).read_bytes()
        (self.folder / "clark-20300102T030406Z-undo.db").write_bytes(data[:3000])
        other = Path(tempfile.mkdtemp(prefix="clark-other-")).resolve()
        self.addCleanup(shutil.rmtree, other, True)
        theirs = open_store(other / "clark.db", onedrive_roots=[])
        with theirs.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABC", "name": "Someone else's"})
        cs.snapshot(theirs.path, pl.private_file(self.folder / "clark-20300102T030407Z-undo.db"))
        theirs.close()
        newer = self.folder / "clark-20300102T030408Z-undo.db"
        shutil.copyfile(self.folder / self.name, newer)
        con = sqlite3.connect(newer)
        con.execute("UPDATE meta SET v = '99' WHERE k = 'schema_version'")
        con.commit()
        con.close()
        before = dump(self.path)
        for name, words in (("clark-20300102T030406Z-undo.db", "can't be used|damaged|isn't a database"),
                            ("clark-20300102T030407Z-undo.db", "backup of a different database"),
                            ("clark-20300102T030408Z-undo.db", "newer clark")):
            with self.subTest(name=name), self.assertRaisesRegex(Invalid, words):
                backup.restore_over(self.s, name)
            self.assertEqual(dump(self.path), before)
            self.assertEqual([p.name for p in self.folder.iterdir() if p.name.startswith("replaced")], [])
            self.s = open_store(self.path, onedrive_roots=[])

    def test_13_restore_keeps_the_replaced_database_and_a_stale_wal_is_not_replayed(self):
        self.edit(3)
        have = self.counts(self.path)
        self.s.close()
        wal = self.demo.dir / "clark.db-wal"
        wal.write_bytes(os.urandom(4096) * 4)                  # a stale -wal that must not be replayed into the restored copy
        result = backup.restore_over(self.s, self.name)
        aside = result["replaced"]
        self.assertTrue(aside.name.startswith("replaced-") and aside.parent == self.folder)
        self.assertEqual(self.counts(aside / "clark.db"), have)
        self.assertTrue((aside / "clark.db-wal").exists() or not wal.exists())
        self.assertFalse(wal.exists())
        restore_copies = [e for e in backup.entries(self.folder) if e.tag == "restore"]
        self.assertEqual(len(restore_copies), 1)
        self.assertEqual(self.counts(restore_copies[0].path), have, "a restore backup with the rows from before")
        again = open_store(self.path, onedrive_roots=[])
        self.addCleanup(again.close)
        self.assertEqual(len(again.read("actions", "ABC")), 2)
        backup.prune(self.folder, 1)
        self.assertTrue(aside.is_dir(), "a replaced- folder is never pruned")
        self.assertEqual(self.counts(self.path), (2, self.then))

    def test_20_restore_names_are_validated(self):
        outsider = self.demo.dir / "clark-20300102T030409Z-undo.db"
        shutil.copyfile(self.folder / self.name, outsider)
        (self.folder / "clark-20300102T030410Z-undo.db").symlink_to(outsider)
        (self.folder / "replaced-20300101T000000Z").mkdir()
        before = dump(self.path)
        bad = ("..", "../clark.db", str(outsider), "/etc/hosts", "clark-20300102T030410Z-undo.db", "replaced-20300101T000000Z",
               "notes.txt", "", f"../backups/{self.name}", self.name + "/", "clark-20300102T030409Z-undo.db")
        for name in bad:
            with self.subTest(name=name):
                with self.assertRaisesRegex(Invalid, r"^No backup called .* is in "):
                    backup.restore_over(self.s, name)
                self.s = open_store(self.path, onedrive_roots=[])
                fresh = self.demo.dir / "fresh"
                with self.assertRaisesRegex(Invalid, r"^No backup called .* is in "):
                    backup.restore_into(fresh, name, self.folder, onedrive_roots=[])
                self.assertFalse(fresh.exists())
                self.assertEqual(dump(self.path), before)
        self.assertEqual(backup.valid_name(self.folder, self.name), self.folder / self.name)

    def test_21_a_restore_that_stops_at_the_last_step_is_finished_on_the_next_start(self):
        self.edit(2)
        real = pl.replace_file
        calls = []

        def fail_once(src, dest, *a, **k):
            if Path(dest).name == "clark.db" and not calls:
                calls.append(1)
                raise pl.PlatformError("locked")
            return real(src, dest, *a, **k)

        with mock.patch.object(pl, "replace_file", fail_once), self.assertRaisesRegex(Invalid, "stopped part-way"):
            backup.restore_over(self.s, self.name)
        self.assertFalse(self.path.exists())
        self.assertTrue(self.path.with_name("clark.db.restoring").exists() and self.path.with_name("clark.db.restoring.json").exists())
        done = open_store(self.path, onedrive_roots=[])
        self.addCleanup(done.close)
        self.assertEqual(len(done.read("actions", "ABC")), 2, "the backup's rows, not an empty database")
        self.assertFalse(self.path.with_name("clark.db.restoring.json").exists())

    def _stopped_twice(self):
        """A restore that stopped at its last step, and then the copy waiting beside it was damaged: a crash and a second fault."""
        real = pl.replace_file

        def fail(src, dest, *a, **k):
            if Path(dest).name == "clark.db":
                raise pl.PlatformError("locked")
            return real(src, dest, *a, **k)

        with mock.patch.object(pl, "replace_file", fail), self.assertRaisesRegex(Invalid, "stopped part-way"):
            backup.restore_over(self.s, self.name)
        self.path.with_name("clark.db.restoring").write_bytes(b"not a database")

    def test_f1_a_restore_that_cannot_be_finished_says_where_the_database_is(self):
        """F1: startup said 'can't read the data' and the restore said 'start clark first': a loop, with the live data only in replaced-*."""
        self._stopped_twice()
        with self.assertRaises(cs.Unfinished) as ctx:
            open_store(self.path, onedrive_roots=[])
        self.assertRegex(str(ctx.exception), r"^clark\.db is missing from .*\. Your database is in .*replaced-[^ ]*\. Move clark\.db from there back into .*, then start clark\.$")
        self.assertNotIn("restore a backup", str(ctx.exception), "it never sends a person to the restore it refuses")
        self.assertFalse(self.path.exists(), "no new empty database was made")

    def test_f1_the_second_restore_names_the_way_out_and_the_way_out_works(self):
        self._stopped_twice()
        marker = self.path.with_name("clark.db.restoring.json")
        with self.assertRaises(Invalid) as ctx:
            backup.restore_path(self.path, self.name, self.folder, [])
        text = str(ctx.exception)
        self.assertIn("Your database is in", text)
        self.assertIn(f"is missing from {self.path.parent}.", text, "the data folder is named, not just called 'the data folder'")
        self.assertIn("Nothing was changed.", text)
        self.assertIn(f"To put {self.name} back instead, first delete the file clark.db.restoring.json in {self.path.parent}, then "
                      "run restore again.", text)
        self.assertNotIn("restore a backup", text)
        self.assertNotIn("Start clark first", text, "that advice only helps when starting clark can finish the restore")
        self.assertTrue(marker.exists())
        aside = [p for p in self.folder.iterdir() if p.name.startswith("replaced-")]
        self.assertEqual(len(aside), 1)
        marker.unlink()                                             # what the message says to do
        self.path.with_name("clark.db.restoring").unlink()
        backup.restore_path(self.path, self.name, self.folder, [])
        done = open_store(self.path, onedrive_roots=[])
        self.addCleanup(done.close)
        self.assertEqual(len(done.read("actions", "ABC")), 2, "the backup's rows (two edits were made before it was taken)")
        self.assertTrue((aside[0] / "clark.db").exists(), "the database you had is still where it was")

    def test_f2_copies_named_for_a_future_time_do_not_push_real_history_out(self):
        """F2: a clock that ran ahead left 14 daily copies named 2099; the copies made since fell out of the newest 14 by name."""
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        source = backup.take(self.s, "daily")
        planted = []
        for i in range(14):
            copy = self.folder / f"clark-2099010{1 + i // 10}T0000{i % 10:02d}Z-daily.db"
            shutil.copyfile(source, copy)
            os.utime(copy, (1_700_000_000 + i, 1_700_000_000 + i))
            planted.append(copy.name)
        source.unlink()
        real = []
        for _ in range(3):
            self.clock.advance(days=1)
            real.append(backup.take(self.s, "daily").name)
        self.assertEqual(len(set(real)), 3)
        for name in real:
            self.assertIn(name, self.copies(), "a copy made after the clock was right is still there")
        self.assertLessEqual(len(self.copies()), 14, "retention still keeps only the newest 14")

    def test_113_copies_whose_name_and_file_time_are_both_in_the_future_age_like_any_other(self):
        """
        they are removed when they are the oldest written. Here they were written before the real ones, so they go first anyway."""
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        source = backup.take(self.s, "daily")
        planted = []
        for i in range(14):
            copy = self.folder / f"clark-{(FIXED + timedelta(days=30 + i)).strftime('%Y%m%dT%H%M%SZ')}-daily.db"
            shutil.copyfile(source, copy)
            os.utime(copy, (1_700_000_000 + i, 1_700_000_000 + i))              # written earlier than anything made below
            planted.append(copy.name)
        source.unlink()
        real = []
        for _ in range(14):
            self.clock.advance(days=1)
            real.append(backup.take(self.s, "daily").name)
            self.assertIn(real[-1], self.copies(), "the copy just made is kept")
        self.assertEqual(self.copies(), real, "the oldest written went first, and these were the oldest written")

    def test_113_a_believed_name_with_a_future_file_time_is_not_believed(self):
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        early = backup.take(self.s, "daily")
        self.clock.advance(days=1)
        later = backup.take(self.s, "daily")
        future = (FIXED + timedelta(days=400)).timestamp()
        os.utime(later, (future, future))                                   # a file time a clock ahead gave it
        self.assertEqual([e.name for e in backup.entries(self.folder)], [early.name, later.name], "ordered by when written, not by a clock")
        self.assertEqual([e.ahead for e in backup.entries(self.folder)], [False, True], "but it is still known not to be believed")
        os.utime(later, (FIXED.timestamp() + 86400, FIXED.timestamp() + 86400))
        self.assertEqual([e.ahead for e in backup.entries(self.folder)], [False, False], "a day ahead at most is believed")

    def _113_entry(self, name_offset, file_offset):
        """One planted copy: its name time and file time are the store's clock plus the given seconds. Returns its Entry."""
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        source = backup.take(self.s, "daily")
        now = self.clock()
        copy = self.folder / f"clark-{(now + timedelta(seconds=name_offset)).strftime('%Y%m%dT%H%M%SZ')}-daily.db"
        source.rename(copy)
        when = int(now.timestamp()) + file_offset
        os.utime(copy, (when, when))
        found = [e for e in backup.entries(self.folder) if e.name == copy.name]
        self.assertEqual(len(found), 1)
        return found[0]

    def test_113_a_name_time_exactly_a_day_ahead_is_believed_and_a_second_more_is_not(self):
        self.assertFalse(self._113_entry(86400, 0).ahead, "exactly a day after the store's clock is believed")
        self.assertTrue(self._113_entry(86401, 0).ahead, "a second past a day after the store's clock is not")

    def test_113_a_file_time_exactly_a_day_ahead_is_believed_and_a_second_more_is_not(self):
        self.assertFalse(self._113_entry(0, 86400).ahead, "exactly a day after the store's clock is believed")
        self.assertTrue(self._113_entry(0, 86401).ahead, "a second past a day after the store's clock is not")

    def test_113_a_future_dated_copy_named_today_does_not_make_todays_copy_be_skipped(self):
        """#113: a copy made under a clock that ran ahead carries a date that, after the clock is put right, is today's. Its file
        time is far ahead, so it is not today's copy and a real one is still due."""
        entry = self._113_entry(0, 40 * 86400)              # named for now, file time forty days on
        self.assertTrue(entry.ahead)
        self.assertTrue(backup.due_today(self.folder), "a copy that is not believed does not stand in for today's")
        backup.take(self.s, "daily")
        self.assertFalse(backup.due_today(self.folder), "the real copy does")

    def test_113_a_file_time_that_cannot_be_turned_into_a_date_is_ahead_not_a_crash(self):
        entry = self._113_entry(0, 0)
        for error in (OverflowError, OSError, ValueError):
            with self.subTest(error=error.__name__):
                def failing(seconds=None, error=error):
                    raise error("out of range")
                with mock.patch.object(backup.time, "gmtime", failing):
                    found = backup.entries(self.folder)
                    self.assertEqual([e.name for e in found], [entry.name])
                    self.assertTrue(found[0].ahead)
                    self.assertTrue(backup.due_today(self.folder), "a copy that is not believed is not today's")
                    backup.prune(self.folder)               # never raises, and the only copy stays
                    self.assertEqual(self.copies(), [entry.name])

    def _set_back(self, follow_clock):
        """Fourteen daily copies, the clock put back 54 days, fourteen more. Returns (the 14 first written, the 14 written after)."""
        self.wipe()
        self.folder.mkdir(exist_ok=True)

        def take():
            copy = backup.take(self.s, "daily")
            if follow_clock:                                    # file times follow the store's clock
                when = self.clock().timestamp()
                os.utime(copy, (when, when))
            return copy.name
        first = []
        for _ in range(14):
            self.clock.advance(days=1)
            first.append(take())
        self.clock.advance(days=-54)
        second = []
        for _ in range(14):
            self.clock.advance(days=1)
            second.append(take())
            self.assertIn(second[-1], self.copies(), "the copy just made is kept")
            self.assertLessEqual(len(self.copies()), 15, "retention still holds the line")
            if not follow_clock:
                written = first + second
                self.assertEqual(sorted(self.copies()), sorted(written[-14:]),
                                 "exactly the 14 written last are kept: the oldest written is what goes, never a newer one")
        return first, second

    def test_a_backup_named_for_the_end_of_year_9999_is_listed_in_a_zone_east_of_utc(self):
        """Medium 4: restore listed every backup's local time, and one file name of year 9999 crashed the list east of UTC."""
        import time as _time
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        real = backup.take(self.s, "daily")
        odd = self.folder / "clark-99991231T235959Z-daily.db"
        shutil.copyfile(real, odd)
        old = os.environ.get("TZ")

        def put_back():
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            _time.tzset()
        self.addCleanup(put_back)
        for zone in ("Pacific/Kiritimati", "Asia/Dubai", "UTC"):
            os.environ["TZ"] = zone
            _time.tzset()
            names = [x["name"] for x in backup.listing(self.folder)]
            self.assertIn(odd.name, names, zone)

    def test_113_a_clock_set_back_keeps_the_newest_14_by_write_order(self):
        """#113: with real file times (the order the copies were written), the 14 written last are kept and the 14 written first go,
        one at a time, whatever the dates in their names say."""
        first, second = self._set_back(False)
        self.assertEqual(sorted(self.copies()), sorted(second))
        self.assertTrue(set(first).isdisjoint(self.copies()))

    def test_113_a_clock_set_back_with_file_times_that_follow_the_clock(self):
        """With file times that follow the clock, the file time is all the order there is: the 14 first copies carry the later file
        times, so they are the newest. The copy just made is still never removed, and a family never holds more than 15."""
        first, second = self._set_back(True)
        self.assertEqual(sorted(self.copies()), sorted(first[:14] + second[-1:]), "14 later file times, plus the newest of all")

    def test_113_a_family_can_hold_14_plus_the_newest_of_all(self):
        """The limit is 14, plus the newest of all: when the newest of all is in another family, a family keeps its 14 and 15 are there."""
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        source = backup.take(self.s, "daily")
        for i in range(14):
            copy = self.folder / f"clark-2030010{1 + i // 10}T0000{i % 10:02d}Z-daily.db"
            shutil.copyfile(source, copy)
            os.utime(copy, (1_700_000_000 + i, 1_700_000_000 + i))
        newest = self.folder / "clark-20300201T000000Z-undo.db"
        shutil.copyfile(source, newest)
        os.utime(newest, (1_700_001_000, 1_700_001_000))
        source.unlink()
        backup.prune(self.folder)
        self.assertEqual(len(self.copies()), 15)
        extra = self.folder / "clark-20300301T000000Z-daily.db"             # a 15th daily, the newest of all
        shutil.copyfile(newest, extra)
        os.utime(extra, (1_700_002_000, 1_700_002_000))
        backup.prune(self.folder)
        self.assertEqual(len([n for n in self.copies() if n.endswith("-daily.db")]), 14)
        self.assertIn(extra.name, self.copies())

    def test_113_a_copy_written_while_the_clock_ran_ahead_is_never_removed_first(self):
        """Simulation 2: fourteen daily copies, one written while the clock was 30 days ahead (the newest written), the clock put
        right, one more copy. The oldest written goes; the newest written, though dated 30 days ahead, stays."""
        for follow_file_time in (False, True):
            with self.subTest(file_times_ahead=follow_file_time):
                self.wipe()
                self.folder.mkdir(exist_ok=True)
                self.clock.t = FIXED
                names = []
                for _ in range(14):
                    self.clock.advance(days=1)
                    names.append(backup.take(self.s, "daily").name)
                self.clock.advance(days=30)
                ahead = backup.take(self.s, "daily")
                if follow_file_time:
                    when = self.clock().timestamp() + 365 * 86400       # the file time is far ahead as well
                    os.utime(ahead, (when, when))
                self.clock.advance(days=-30)
                self.assertNotIn(names[0], self.copies(), "the 15th copy took the oldest written")
                self.clock.advance(days=1)
                last = backup.take(self.s, "daily").name
                self.assertIn(ahead.name, self.copies(), "the newest written is not removed because of its date")
                self.assertIn(last, self.copies())
                self.assertNotIn(names[1], self.copies(), "the oldest written goes")
                self.assertEqual(sorted(self.copies()), sorted(names[2:] + [ahead.name, last]))

    def test_f3_a_backups_folder_that_is_a_file_is_named_before_the_copy_is(self):
        """F3: restore <real name> said the name 'isn't a backup clark made' when the folder itself was the trouble."""
        shutil.rmtree(self.folder)
        self.folder.write_text("not a folder", encoding="utf-8")
        for call in (lambda: backup.valid_name(self.folder, self.name), lambda: backup.restore_path(self.path, self.name, self.folder, [])):
            with self.assertRaises(Invalid) as ctx:
                call()
            self.assertRegex(str(ctx.exception), r"^The backups folder .*backups can't be read \(.*\)\. Check that it is a folder and that "
                                                 r"you can open it, then try again\.$")
            self.assertNotIn("directory", str(ctx.exception).lower())
            self.assertNotIn("isn't a backup", str(ctx.exception))
        with self.assertRaises(Invalid) as listed:
            backup.listing(self.folder)
        self.assertEqual(str(listed.exception), str(ctx.exception), "the same words as the list gives")

    def test_f3_a_missing_folder_still_says_the_name_is_not_a_copy(self):
        shutil.rmtree(self.folder)
        with self.assertRaisesRegex(Invalid, "^No backup called .* is in "):
            backup.valid_name(self.folder, self.name)

    def test_f4_a_file_where_the_folder_should_be_is_called_a_file(self):
        """F4: 'It couldn't write to ~/x/backups: File exists.' told nobody what was wrong."""
        shutil.rmtree(self.folder)
        self.folder.write_text("not a folder", encoding="utf-8")
        with self.assertRaises(Invalid) as ctx:
            backup.take(self.s, "undo")
        text = str(ctx.exception)
        self.assertIn(f"{self.folder} is a file, not a folder. Rename or move it, then try again.", text)
        self.assertNotIn("It couldn't", text)
        self.assertNotIn("File exists", text)
        self.assertIn("Nothing was changed.", text)

    def test_9_a_missing_replaced_folder_is_a_plain_refusal_not_a_crash(self):
        real = pl.replace_file

        def fail_once(src, dest, *a, **k):
            if Path(dest).name == "clark.db":
                raise pl.PlatformError("locked")
            return real(src, dest, *a, **k)

        with mock.patch.object(pl, "replace_file", fail_once), self.assertRaisesRegex(Invalid, "stopped part-way"):
            backup.restore_over(self.s, self.name)
        for aside in [p for p in self.folder.iterdir() if p.name.startswith("replaced-")]:
            shutil.rmtree(aside)                                  # moved or removed by hand
        (self.demo.dir / "clark.db-wal").write_bytes(b"stray")     # which also needs the folder
        with self.assertRaisesRegex(Invalid, r"^clark\.db is missing from .*, and the folder that held your database \(.*\) isn't there any more\. Look in "
                                             r".*backups for a folder whose name starts with replaced-, and move the clark\.db in it back "):
            open_store(self.path, onedrive_roots=[])
        self.assertFalse(self.path.exists(), "and no empty database is made")
        self.assertTrue(self.path.with_name("clark.db.restoring").exists(), "the waiting copy is left for a person to use")

    def test_21_with_the_waiting_copy_also_gone_it_refuses_and_makes_no_empty_database(self):
        real = pl.replace_file

        def fail(src, dest, *a, **k):
            if Path(dest).name == "clark.db":
                raise pl.PlatformError("locked")
            return real(src, dest, *a, **k)

        with mock.patch.object(pl, "replace_file", fail), self.assertRaises(Invalid):
            backup.restore_over(self.s, self.name)
        self.path.with_name("clark.db.restoring").unlink()
        with self.assertRaisesRegex(Invalid, r"^clark\.db is missing from .*\. Your database is in .*replaced-[^ ]*\. Move clark\.db from there back into .*, then start clark\.$"):
            open_store(self.path, onedrive_roots=[])
        self.assertFalse(self.path.exists())

    def test_21_a_stale_waiting_copy_never_brings_old_data_back(self):
        self.s.close()
        waiting = self.path.with_name("clark.db.restoring")
        shutil.copyfile(self.folder / self.name, waiting)
        for side in ("", "-wal", "-shm"):
            Path(str(self.path) + side).unlink(missing_ok=True)
        fresh = open_store(self.path, onedrive_roots=[])
        self.addCleanup(fresh.close)
        self.assertEqual(fresh.read("actions", "ABC"), [], "a new, empty database: no marker, so the waiting file is not used")

    def test_21_a_restore_that_fails_before_the_move_leaves_nothing_waiting(self):
        with mock.patch.object(cs, "check_copy", side_effect=[cs.check_copy(self.folder / self.name), Invalid("damaged")]), \
                self.assertRaises(Invalid):
            backup.restore_over(self.s, self.name)
        self.assertFalse(self.path.with_name("clark.db.restoring").exists())
        self.assertFalse(self.path.with_name("clark.db.restoring.json").exists())
        self.assertTrue(self.path.exists())

    def test_n4_a_working_copy_that_fails_its_check_names_the_backup_not_the_working_file(self):
        with mock.patch.object(cs, "check_copy", side_effect=[cs.check_copy(self.folder / self.name), Invalid("clark.db.restoring is damaged")]), \
                self.assertRaises(Invalid) as ctx:
            backup.restore_over(self.s, self.name)
        self.assertEqual(str(ctx.exception), f"{self.name} could not be copied correctly. Try again, or choose another backup.")
        self.assertNotIn("restoring", str(ctx.exception))

    def test_4_a_move_that_stops_before_anything_moved_says_nothing_was_changed(self):
        """What Windows would do if the open probe stopped the move: the old database is still in place, so the message must
        not promise that the next start will finish anything."""
        before = dump(self.path)
        with mock.patch.object(backup, "_move_aside", side_effect=PermissionError(errno.EACCES, "Access is denied")):
            with self.assertRaises(Invalid) as ctx:
                backup.restore_over(self.s, self.name)
        text = str(ctx.exception)
        self.assertIn("Nothing was changed.", text)
        self.assertIn("isn't allowed to use it", text)
        self.assertNotIn("Start clark again", text)
        self.assertNotIn("part-way", text)
        self.assertEqual(dump(self.path), before)
        self.assertEqual([p.name for p in self.folder.iterdir() if p.name.startswith("replaced")], [], "no empty folder is left")
        for left_over in ("clark.db.restoring", "clark.db.restoring.json"):
            self.assertFalse((self.demo.dir / left_over).exists())

    def test_4_a_stop_after_the_old_database_moved_still_points_at_the_start_that_finishes_it(self):
        real = pl.replace_file

        def stops_at_the_last_step(source, dest, *a, **kw):
            if Path(dest) == self.path:
                raise OSError(errno.EIO, "Input/output error")
            return real(source, dest, *a, **kw)                       # the note beside the database is written as usual

        with mock.patch.object(pl, "replace_file", stops_at_the_last_step):
            with self.assertRaisesRegex(Invalid, r"stopped part-way .*Start clark again and it will finish putting"):
                backup.restore_over(self.s, self.name)
        self.assertFalse(self.path.exists())
        self.assertTrue((self.demo.dir / "clark.db.restoring.json").exists())

    @unittest.skipIf(WINDOWS, "mode bits do nothing on Windows")
    def test_22_everything_is_private_even_at_umask_022(self):
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        shutil.rmtree(self.folder)
        self.folder.mkdir(mode=0o755)
        os.chmod(self.folder, 0o755)
        modes = {}
        real_snapshot, real_check = cs.snapshot, cs.check_copy

        def spy_snapshot(path, dest):
            modes["part"] = (mode(dest), Path(dest).stat().st_size)
            return real_snapshot(path, dest)

        def spy_check(path):
            if str(path).endswith(".restoring"):
                modes["restoring"] = mode(path)
            return real_check(path)

        with mock.patch.object(cs, "snapshot", spy_snapshot), mock.patch.object(cs, "check_copy", spy_check):
            made = backup.take(self.s, "undo")
            result = backup.restore_over(self.s, made.name)
        self.assertEqual(modes["part"], (0o600, 0), "0600 and empty before sqlite writes the first byte")
        self.assertEqual((mode(self.folder), mode(made), mode(result["replaced"]), modes["restoring"]),
                         (0o700, 0o600, 0o700, 0o600))
        self.assertEqual(mode(self.path), 0o600)

    def test_22_no_key_like_value_is_in_a_backup(self):
        keychain = {"ai": "sk-DEMO-NOT-A-REAL-KEY-0123456789"}          # the Keychain stand-in: keys live there, never in the database
        self.edit()
        backup.take(self.s, "undo")
        for p in self.folder.iterdir():
            self.assertNotIn(keychain["ai"].encode(), p.read_bytes())

    def damage_a_page(self, page=11):
        """Write garbage over one middle page of the live database (the table roots are listed in sqlite_master), once the store
        is closed and its -wal is folded in (checkpointed). The header and `meta` stay readable, so identity() still answers."""
        self.s.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")      # Python 3.9's SQLite leaves frames in the -wal when a store closes
        self.s.close()
        with open(self.path, "r+b") as f:
            f.seek((page - 1) * 4096)
            f.write(b"\xff" * 4096)

    def test_1_a_live_database_with_a_damaged_page_can_be_restored_without_a_copy_of_it(self):
        self.damage_a_page()
        self.assertIsNotNone(cs.identity(self.path), "the damage is in the middle: the database still says which one it is")
        with self.assertRaises(Invalid):
            cs.check_copy(self.path)
        damaged, have = self.path.read_bytes(), self.copies()
        done = backup.restore_path(self.path, self.name, self.folder, [])
        self.assertEqual(cs.check_copy(self.path)["rows"]["applies"], self.then)
        self.assertEqual(self.copies(), have, "no safety copy of a database that can't be copied")
        self.assertEqual((done["replaced"] / "clark.db").read_bytes(), damaged, "and the damaged file is moved aside whole")

    def test_1_a_good_database_that_cannot_be_copied_still_stops_the_restore(self):
        before = dump(self.path)
        with self.full(), self.assertRaisesRegex(Invalid, "^A backup of your data must be made first, and it couldn't be"):
            backup.restore_over(self.s, self.name)
        self.assertEqual(dump(self.path), before)
        self.assertEqual([p.name for p in self.folder.iterdir() if p.name.startswith("replaced")], [])

    def full(self):
        return mock.patch.object(cs, "snapshot", side_effect=OSError(errno.ENOSPC, "No space left on device"))

    def test_2_a_database_with_no_projects_and_no_steps_may_be_replaced_but_one_with_a_step_may_not(self):
        other = Path(tempfile.mkdtemp(prefix="clark-other-")).resolve()
        self.addCleanup(shutil.rmtree, other, True)
        theirs = open_store(other / "clark.db", onedrive_roots=[])
        theirs.close()
        self.assertTrue(backup._holds_nothing(other / "clark.db"))
        done = backup.restore_path(other / "clark.db", self.name, self.folder, [])
        self.assertEqual(cs.identity(other / "clark.db"), cs.identity(self.folder / self.name))
        self.assertTrue((done["replaced"] / "clark.db").exists())
        (other / "again").mkdir()
        stepped = open_store(other / "again" / "clark.db", onedrive_roots=[])
        with stepped.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Someone else's"})
        stepped.close()
        self.assertFalse(backup._holds_nothing(other / "again" / "clark.db"))
        with self.assertRaisesRegex(Invalid, "backup of a different database"):
            backup.restore_path(other / "again" / "clark.db", self.name, self.folder, [])

    def folder_state(self):
        return sorted((p.name, p.stat().st_mtime_ns, p.stat().st_size) for p in self.folder.rglob("*"))

    def test_3_a_refused_restore_leaves_the_backups_folder_exactly_as_it_was(self):
        other = open_store(self.path, onedrive_roots=[])                    # another program has the database open
        self.addCleanup(other.close)
        want = self.folder_state()
        with self.assertRaisesRegex(Invalid, "^Another window or program has clark's data open"):
            backup.restore_over(self.s, self.name)
        self.assertEqual(self.folder_state(), want)
        other.close()
        self.s = open_store(self.path, onedrive_roots=[])
        (self.folder / "clark-20300102T030406Z-undo.db").write_bytes((self.folder / self.name).read_bytes()[:3000])
        want = self.folder_state()
        with self.assertRaisesRegex(Invalid, "can't be used|damaged|isn't a database"):
            backup.restore_over(self.s, "clark-20300102T030406Z-undo.db")      # a damaged copy
        self.assertEqual(self.folder_state(), want)

    def test_3_restores_do_not_push_import_copies_out_of_the_folder(self):
        imports = [backup.take(self.s, "import").name]
        for _ in range(backup.KEEP + 2):
            self.clock.advance(seconds=1)
            backup.restore_over(self.s, self.name)                          # closes the store
            self.s = open_store(self.path, onedrive_roots=[])
        self.assertIn(imports[0], self.copies(), "the import copy is still there after more restores than are kept")

    def test_23_in_use_errors_each_refuse_with_the_store_closed_and_nothing_moved(self):
        before = dump(self.path)
        cases = []
        other = open_store(self.path, onedrive_roots=[])
        cases.append(("locked", "has clark's data open", other))
        for label, words, _ in cases:
            with self.subTest(case=label), self.assertRaisesRegex(Invalid, words):
                backup.restore_over(self.s, self.name)
            self.assertEqual(dump(self.path), before)
            self.assertEqual([p.name for p in self.folder.iterdir() if p.name.startswith("replaced")], [])
        other.close()
        self.s = open_store(self.path, onedrive_roots=[])
        if not WINDOWS and not (hasattr(os, "geteuid") and os.geteuid() == 0):
            self.s.close()
            os.chmod(self.path, 0o444)                          # a read-only file
            self.addCleanup(os.chmod, self.path, 0o600)
            with self.assertRaisesRegex(Invalid, "^clark\\.db can't be opened right now\\. Close any other window or program using clark"):
                backup.restore_over(self.s, self.name)
            self.assertTrue(self.path.exists())
            self.assertEqual([p.name for p in self.folder.iterdir() if p.name.startswith("replaced")], [])
            os.chmod(self.path, 0o000)                          # one that can't be opened at all
            with self.assertRaisesRegex(Invalid, "^clark\\.db can't be opened right now\\."):
                backup.restore_over(self.s, self.name)
            self.assertTrue(self.path.exists())
            os.chmod(self.path, 0o600)

    def test_23_the_probe_stays_open_until_after_the_move(self):
        seen = []
        real = backup._move_aside

        def spying(source, aside):
            if not seen:
                try:
                    con = sqlite3.connect(self.path, timeout=0)
                    con.execute("PRAGMA locking_mode = EXCLUSIVE")
                    con.execute("SELECT count(*) FROM sqlite_master").fetchone()
                    seen.append("opened")
                    con.close()
                except sqlite3.OperationalError as e:
                    seen.append(str(e))
            return real(source, aside)

        with mock.patch.object(backup, "_move_aside", spying):
            backup.restore_over(self.s, self.name)
        self.assertEqual(seen, ["database is locked"])

    def test_24_check_copy_refuses_a_foreign_key_violation_an_older_schema_and_another_db_id(self):
        broken = self.folder / "clark-20300102T030411Z-undo.db"
        shutil.copyfile(self.folder / self.name, broken)
        con = sqlite3.connect(broken)
        con.execute("PRAGMA foreign_keys = OFF")
        con.execute("INSERT INTO change_log (apply_id, tbl, item_id, field, via) VALUES (99999, 'actions', 'ABC-A-001', 'x', 'dashboard')")
        con.commit()
        con.close()
        with self.assertRaisesRegex(Invalid, "is damaged, so it can't be used\\. Choose another backup\\.$"):
            cs.check_copy(broken)
        old = self.folder / "clark-20300102T030412Z-undo.db"
        shutil.copyfile(self.folder / self.name, old)
        con = sqlite3.connect(old)
        con.execute("UPDATE meta SET v = '0' WHERE k = 'schema_version'")
        con.commit()
        con.close()
        with self.assertRaisesRegex(Invalid, "no usable version"):     # 0 is not a version; an older real one (1) is restorable, see Migrate
            backup.restore_over(self.s, old.name)
        self.s = open_store(self.path, onedrive_roots=[])
        other = self.folder / "clark-20300102T030413Z-undo.db"
        shutil.copyfile(self.folder / self.name, other)
        con = sqlite3.connect(other)
        con.execute("UPDATE meta SET v = 'another-database' WHERE k = 'db_id'")
        con.commit()
        con.close()
        with self.assertRaisesRegex(Invalid, "backup of a different database.*new, empty folder, rename it clark\\.db.*\n    python3 -m clark --data FOLDER$"):
            backup.restore_over(self.s, other.name)
        fresh = Path(tempfile.mkdtemp(prefix="clark-fresh-")).resolve() / "data"
        self.addCleanup(shutil.rmtree, fresh.parent, True)
        self.assertTrue(backup.restore_into(fresh, other.name, self.folder, onedrive_roots=[]).is_file(), "the way past it")


# ── 15 to 18, 26: size, source rules, two writers, imports ────────────────────

class Migrate(Backed):
    """The `migrate` family (#126's safety copy before it updates the data file) and restoring a copy of an older schema."""

    def setUp(self):
        super().setUp()
        self.edit(2)

    def test_the_migrate_copy_is_made_by_family_or_by_tag_and_is_listed_and_restorable(self):
        for call in (lambda: backup.make(self.path, self.folder, [], family="migrate"),
                     lambda: backup.make(self.path, self.folder, [], "migrate")):
            self.clock.advance(seconds=1)
            made = call()
            self.assertRegex(made.name, r"^clark-[0-9]{8}T[0-9]{6}Z-migrate\.db$")
            self.assertTrue(made.is_file())
        listed = backup.listing(self.folder)
        self.assertEqual([r["tag"] for r in listed if r["tag"] == "migrate"], ["migrate", "migrate"])
        with self.assertRaises(ValueError):
            backup.make(self.path, self.folder, [], "undo", family="migrate")
        before = dump(self.path)
        self.edit()
        backup.restore_over(self.s, made.name)
        self.assertEqual(dump(self.path), before)

    def test_a_version_1_file_without_the_report_tables_can_be_backed_up_checked_and_restored(self):
        con = sqlite3.connect(self.path, isolation_level=None)
        for table in ("report_sections", "glance_tiles", "report_hidden"):
            con.execute(f"DROP TABLE {table}")
        con.execute("UPDATE meta SET v = '1' WHERE k = 'schema_version'")          # a file made before schema version 2
        con.close()
        made = backup.make(self.path, self.folder, [], "migrate")
        self.assertTrue(made.is_file())
        checked = cs.check_copy(made)
        self.assertEqual(checked["schema_version"], 1)
        self.assertNotIn("report_sections", checked["rows"])
        before = dump(self.path)
        self.edit()
        backup.restore_over(self.s, made.name)
        self.assertEqual(dump(self.path), before)

    def test_the_list_gives_each_kind_in_plain_words_and_the_help_explains_the_name(self):
        for tag in backup.TAGS:
            self.clock.advance(seconds=1)
            backup.make(self.path, self.folder, [], tag)
        kinds = {r["tag"]: r["kind"] for r in backup.listing(self.folder)}
        self.assertEqual(kinds, {"daily": "daily", "undo": "before an undo", "import": "before an import",
                                 "changes": "before a change", "restore": "restored copy", "migrate": "before an update"})
        self.assertNotIn("migrate", " ".join(kinds.values()))
        self.assertIn("with \"migrate\" in it is a backup taken just before clark updated the database", backup.RESTORE_HELP)
        self.assertFalse(any(line.lower().startswith("clark") for line in backup.RESTORE_HELP.splitlines()))

    def test_retention_keeps_the_newest_migrate_copy_whatever_the_other_families_do(self):
        first = backup.make(self.path, self.folder, [], family="migrate")
        for tag in ("undo", "import", "daily", "restore"):
            for _ in range(backup.KEEP + 3):
                self.clock.advance(seconds=1)
                backup.make(self.path, self.folder, [], tag)
        self.assertTrue(first.is_file(), "14 copies of every other family did not push it out")
        self.clock.advance(seconds=1)
        newest = backup.make(self.path, self.folder, [], family="migrate")
        for _ in range(backup.KEEP + 3):
            self.clock.advance(seconds=1)
            backup.make(self.path, self.folder, [], "undo")
        self.assertTrue(newest.is_file())

    def test_a_failed_migrate_copy_refuses_in_words_and_the_gate_still_matches(self):
        err = OSError(errno.ENOSPC, "No space left on device")
        with mock.patch.object(cs, "snapshot", side_effect=err), self.assertRaises(Invalid) as ctx:
            backup.make(self.path, self.folder, [], family="migrate")
        self.assertEqual(str(ctx.exception), "The database could not be updated because a backup of your data must be made first, "
                                             "and it couldn't be. Nothing was changed. "
                                             f"The backups folder {self.folder} can't be written to (the disk is full). "
                                             "Check that the backups folder exists and has space, then try again.")
        checked = backup.refusal("migrate", self.folder, Invalid(cs.CHECK_FAILED))
        self.assertTrue(checked.startswith("The database could not be updated because a backup of your data must be made first. "))
        self.assertTrue(checked.endswith("Nothing was changed. Try again; if it happens again, check the disk has space."), checked)
        for text in (str(ctx.exception), checked, backup.refusal("undo", self.folder, err), backup.refusal("import", self.folder, err)):
            self.assertTrue(backup.is_refusal(text), text)
            self.assertFalse(text.lower().startswith("clark "))

    def test_a_copy_of_an_older_schema_is_restorable_and_a_newer_one_is_still_refused(self):
        old = backup.take(self.s, "migrate")
        con = sqlite3.connect(old, isolation_level=None)
        con.execute("UPDATE meta SET v = '1' WHERE k = 'schema_version'")           # made by an older clark
        con.close()
        self.assertEqual(cs.check_copy(old)["schema_version"], 1)
        self.edit()
        backup.restore_over(self.s, old.name)
        newer = self.folder / "clark-20300102T030409Z-migrate.db"
        shutil.copyfile(old, newer)
        con = sqlite3.connect(newer, isolation_level=None)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(cs.SCHEMA_VERSION + 1),))
        con.close()
        self.s = open_store(self.path, onedrive_roots=[])
        with self.assertRaisesRegex(Invalid, "newer clark"):
            backup.restore_over(self.s, newer.name)


class Rules(Backed):
    def test_15_a_database_of_the_brd_target_size_backs_up_in_under_a_second(self):
        with self.s.step("dashboard", USER) as st:
            for i in range(1, 20):
                st.create("projects", {"code": f"PR{i:02d}", "name": f"Programme {i}"})
            for i in range(500):
                st.create("milestones", {"project": f"PR{1 + i % 19:02d}", "name": f"Milestone {i}", "baseline_date": "2030-03-01",
                                         "source": "demo"})
        con = sqlite3.connect(self.path, isolation_level=None)
        con.execute("PRAGMA busy_timeout = 5000")
        con.execute("BEGIN IMMEDIATE")
        con.execute("INSERT INTO applies (by_user, device) VALUES ('Demo User', 'd')")
        step = con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        for i in range(5000):
            code = f"PR{1 + i % 19:02d}"
            item = f"{code}-A-{i // 19 + 1:03d}"
            con.execute("INSERT INTO actions (id, project, description, raised, source) VALUES (?, ?, ?, '2026-10-01', 'demo')",
                        (item, code, f"Work item {i} with a description of ordinary length"))
            for field in ("description", "owner", "status"):
                con.execute("INSERT INTO change_log (apply_id, tbl, item_id, field, new_value, via) "
                            "VALUES (?, 'actions', ?, ?, 'x', 'dashboard')", (step, item, field))
        con.execute("COMMIT")
        con.close()
        best = None
        for n in range(3):
            dest = pl.private_file(self.demo.dir / f"big{n}.part")
            started = time.perf_counter()
            summary = cs.snapshot(self.path, dest)
            took = time.perf_counter() - started
            best = took if best is None else min(best, took)
        print(f"\n#86: a {dest.stat().st_size / 1e6:.1f} MB database ({summary['rows']['actions']} work items, "
              f"{summary['rows']['change_log']} history rows) backed up in {best * 1000:.0f} ms", flush=True)
        self.assertEqual(summary["rows"]["actions"], 5000)
        self.assertLess(best, 1.0)

    def test_16_the_source_rules(self):
        for name in ("backup.py", "store.py"):
            tree = ast.parse((SRC / name).read_text(encoding="utf-8"))
            pages = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "pages"]
            self.assertEqual(pages, [], f"{name}: backup() is never given pages= (a positive count restarts on every write)")
        tree = ast.parse((SRC / "backup.py").read_text(encoding="utf-8"))
        imports = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names] + \
                  [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertNotIn("sqlite3", imports)
        self.assertEqual([n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "execute"], [])

    def test_17_two_writers_in_the_same_second_make_two_valid_files(self):
        planted = self.folder / "clark-20300102T030405Z-undo.db"
        self.folder.mkdir(exist_ok=True)
        planted.write_bytes(b"planted")
        other = open_store(self.path, onedrive_roots=[])
        self.addCleanup(other.close)
        gate, made, errors = threading.Barrier(2), [], []

        def run(store):
            try:
                gate.wait(10)
                made.append(backup.take(store, "undo"))
            except BaseException as e:        # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=run, args=(s,)) for s in (self.s, other)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(errors, [])
        self.assertEqual(sorted(p.name for p in made), ["clark-20300102T030405Z-undo-2.db", "clark-20300102T030405Z-undo-3.db"])
        self.assertEqual(planted.read_bytes(), b"planted", "a file with the first name is not overwritten")
        for p in made:
            cs.check_copy(p)
        self.assertEqual([n for n in self.names() if n.endswith(".part") or n.startswith(".")], [])

    def test_18_a_preview_takes_no_backup_and_the_apply_takes_one(self):
        action = self.demo.action()
        path = self.workbook()
        wbk.edit(path, "Actions", action, owner="Sam Example")
        self.wipe()
        for _ in range(10):
            plan = self.plan(path)
            self.assertEqual(len(plan.changes), 1)
        self.assertEqual(self.names(), [], "ten previews leave the folder as it was")
        self.assertTrue(xi.apply_import(self.s, self.accept_all(plan), USER).applied)
        self.assertEqual([e.tag for e in backup.entries(self.folder)], ["import"], "the day's copy: the import's own")

    def test_18_an_undo_of_a_missing_step_leaves_no_backup_behind(self):
        """Was "accepted noise"; now (L8) a failed undo removes its copy, so fourteen of them cannot push out fourteen good ones."""
        self.edit()
        self.wipe()
        with self.assertRaisesRegex(Invalid, "There's no step 9999 to undo"):
            self.s.undo(9999, USER)
        self.assertEqual([e.tag for e in backup.entries(self.folder)], [])

    def test_l8_failed_undo_attempts_do_not_burn_a_retention_slot(self):
        self.edit()
        self.wipe()
        for _ in range(14):
            self.clock.advance(seconds=1)
            backup.take(self.s, "undo")
        good = self.names("undo")
        self.assertEqual(len(good), 14)
        self.clock.advance(seconds=1)
        for _ in range(20):
            with self.assertRaises(Invalid):
                self.s.undo(9999, USER)
        self.assertEqual(self.names("undo"), good, "twenty failed undos took nothing from the fourteen")
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        self.s.undo(step, USER)
        after = self.names("undo")
        self.assertEqual(len(after), 14, "a real undo is pruned as before")
        self.assertNotIn(good[0], after)
        self.assertEqual(len(set(after) - set(good)), 1)
        for e in backup.entries(self.folder):
            cs.check_copy(e.path)

    def test_26_one_backup_per_import_however_many_sheets_and_rows(self):
        a = self.demo.action(description="Second action")
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-01",
                                   "impact": "High", "likelihood": "Medium", "source": "demo"})
            d = st.create("decisions", {"project": "ABC", "decision": "Use the shared drive", "date": "2026-10-02",
                                        "status": "Made", "source": "demo"})
        path = self.workbook()
        wbk.edit(path, "Actions", a, owner="Sam Example")
        wbk.edit(path, "Actions", "ABC-A-001", owner="Alex Example")
        wbk.edit(path, "RAID", r, owner="Sam Example")
        wbk.edit(path, "Decisions", d, decision="Use the team drive")
        for i in range(8):
            wbk.add_row(path, "Actions", description=f"New work {i}")
        self.wipe()
        plan = self.plan(path)
        self.assertGreater(len(plan.changes), 8)
        self.assertEqual(self.names(), [], "as a preview: none")
        res = xi.apply_import(self.s, self.accept_all(plan), USER)
        self.assertTrue(res.applied, res.message)
        self.assertEqual([e.tag for e in backup.entries(self.folder)], ["import"])

    def test_the_reuse_row_and_the_guarded_test_know_the_copy(self):
        text = (_paths.ROOT / "docs" / "REUSE-FROM-CREAITE.md").read_text(encoding="utf-8")
        row = next((line for line in text.splitlines() if "`system/scripts/backup.py`" in line and line.startswith("|")), "")
        for want in ("db5adb2", "Yes", "Full review (#86)", "src/clark/backup.py"):
            self.assertIn(want, row)
        self.assertIn("creaite", (SRC / "backup.py").read_text(encoding="utf-8"))


# ── Words ─────────────────────────────────────────────────────────────────────

class Words(Backed):
    def test_n2_a_file_problem_is_put_in_plain_words(self):
        cases = [(FileNotFoundError(errno.ENOENT, "No such file or directory"), "it isn't there"),
                 (PermissionError(errno.EACCES, "Permission denied"), "this account isn't allowed to use it"),
                 (OSError(errno.ENOSPC, "No space left on device"), "the disk is full"),
                 (OSError(errno.EROFS, "Read-only file system"), "the disk is read-only"),
                 (OSError(errno.EIO, "Input/output error"), "a file problem")]
        for err, words in cases:
            with self.subTest(words=words):
                self.assertEqual(backup.plain_reason(err), words)

    def test_the_refusals_are_plain_british_english_with_clark_in_lower_case(self):
        err = OSError(errno.EACCES, "Permission denied")
        for tag in backup.TAGS:
            text = backup.refusal(tag, self.folder, err)
            with self.subTest(tag=tag):
                self.assertFalse(text.lower().startswith("clark "), "no line starts with the product name")
                self.assertTrue(backup.is_refusal(text), text)
                self.assertNotIn("safety copy", text, "one word for it: backup")
                self.assertRegex(text, r"Check that the backups folder exists .*then (try|import) again\.$", "it says what to do")
                self.assertNotIn("Clark", text)
                self.assertNotRegex(text, r"Traceback|sqlite|OSError|Errno|errno")
                self.assertTrue(text.endswith("."))
        self.assertEqual(backup.shown(Path.home() / "x" / "backups"), "~/x/backups", "a message never carries the user name")

    def test_the_restore_text_says_copies_share_the_disk_and_replaced_folders_are_yours_to_remove(self):
        text = " ".join(backup.RESTORE_HELP.split())
        self.assertNotRegex(backup.RESTORE_HELP, r"(?m)^clark|wal|shm", "no line starts with the product name; no jargon")
        for words in ("on this computer's disk", "protect against losing the disk", "are never removed", 
                      "remove them yourself", "python3 -m clark restore", "Move every file whose name starts with clark.db out of the way",
                      "a folder called replaced-DATE", "a file's name carries UTC time"):
            self.assertIn(words, text)

    def test_the_stores_words_carry_no_system_text(self):
        """Plain-words round (HIGH): the system's own error text stays in the cause and never reaches what a person reads."""
        raw = "disk I/O error at page 7"
        dest = pl.private_file(self.demo.dir / "copy.part")
        with mock.patch.object(cs, "connect", side_effect=sqlite3.OperationalError(raw)), self.assertRaises(Invalid) as ctx:
            cs.snapshot(self.path, dest)
        self.assertEqual(str(ctx.exception), "The backup could not be saved.")
        self.assertIn(raw, str(ctx.exception.__cause__))
        junk = self.demo.dir / "clark-20300102T030405Z-undo.db"
        junk.write_bytes(b"not a database at all" * 100)
        with self.assertRaises(Invalid) as ctx:
            cs.check_copy(junk)
        self.assertEqual(str(ctx.exception), f"{junk.name} is damaged, so it can't be used. Choose another backup.")
        with mock.patch.object(cs.sqlite3, "connect", side_effect=sqlite3.OperationalError(raw)), self.assertRaises(Invalid) as ctx:
            cs.in_use(self.path)
        self.assertEqual(str(ctx.exception), "clark.db can't be opened right now. Close any other window or program using clark, "
                                             "then try again. Nothing was changed.")

    def test_a_copy_that_fails_its_check_is_not_said_to_be_unwritable(self):
        """Plain-words round (HIGH): the copy was written; its check failed. "couldn't write" would be wrong."""
        with mock.patch.object(cs, "snapshot", side_effect=Invalid(cs.CHECK_FAILED)), self.assertRaises(Invalid) as ctx:
            backup.take(self.s, "undo")
        self.assertEqual(str(ctx.exception), "A backup of your data must be made first. One was made, but clark could not confirm "
                         "it is complete, so it was not kept. Nothing was changed. Try again; if it happens again, check the "
                         "disk has space.")
        for old in ("couldn't write", "and it couldn't be", "The backup was made"):
            self.assertNotIn(old, str(ctx.exception))

    def test_an_import_copy_that_fails_its_check_reads_without_a_clash(self):
        """N1: the import's words say the same, with "imported"; no "must be made first, and it couldn't be" before "was made"."""
        with mock.patch.object(cs, "snapshot", side_effect=Invalid(cs.CHECK_FAILED)), self.assertRaises(Invalid) as ctx:
            backup.take(self.s, "import")
        self.assertEqual(str(ctx.exception), "The import was stopped, because a backup of your data must be made first. One was "
                         "made, but clark could not confirm it is complete, so it was not kept. Nothing was imported. Try again; "
                         "if it happens again, check the disk has space.")
        for old in ("and it couldn't be", "The backup was made"):
            self.assertNotIn(old, str(ctx.exception))

    def test_a_name_that_is_not_a_backup_is_said_plainly_and_cant_change_the_screen(self):
        """Plain-words round (LOW): no Python quote marks round the name, and a control character typed in it is not passed on."""
        with self.assertRaises(Invalid) as ctx:
            backup.valid_name(self.folder, "notes\x1b[2J.txt")
        self.assertEqual(str(ctx.exception), f"No backup called notes?[2J.txt is in {self.folder}. To see the backups, run:\n"
                                             "    python3 -m clark restore")

    def test_the_list_is_in_local_time(self):
        backup.take(self.s, "undo")
        (row,) = backup.listing(self.folder)
        self.assertEqual((row["name"], row["tag"]), ("clark-20300102T030405Z-undo.db", "undo"))
        self.assertRegex(row["when"], r"^\d\d-\d\d-\d{4} \d\d:\d\d$")


if __name__ == "__main__":
    unittest.main()

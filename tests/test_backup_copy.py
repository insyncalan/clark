"""#622: the optional folder each backup is also copied into (settings.py `backup_copy_folder`, backup.py `copy_out` and `bring_in`,
safety.py `copy_folder`, the restore command's --from). OneDrive is allowed for that folder and never for the live data folder. The
data is a DemoStore in a temporary folder with fictional data; a "OneDrive" here is a temporary folder given as the root.

Run: python3 dev/run_tests.py test_backup_copy
No Chrome is started. The Settings box itself is tests/test_safety_logic.py.

What is asserted, and what each safety test guards:
- the setting: off by default, an absolute path, saved beside the other settings, refused (and nothing written) when it is clark's own
  data or backups folder (also by a shortcut), a file, not writable, or not absolute; a missing folder is made;
- the copy: the same finished single file under the same name (never -wal or -shm), written under a temporary name and renamed into place,
  read back and compared, the same retention (the number kept), and only clark's own backup names are ever removed in that folder;
- failure: a missing, unwritable or full folder, or one the settings file points at the data folder, is a plain warning, the backup here
  and the save still succeed, a hung folder holds a save up for COPY_WAIT only, and a good copy clears the warning;
- restore: a copy is read from the folder onto a clean data folder, a corrupt, foreign or forged file there is refused, and a restore writes
  nothing into that folder; the live data folder in OneDrive is still refused, in words that say what to do.
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _demo import DemoStore
from clark import __main__ as launcher, backup, platform as pl, safety, settings, store as cs
from clark.store import Invalid, open_store

ROOT = os.geteuid() == 0 if hasattr(os, "geteuid") else False


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Rig(unittest.TestCase):
    """A demo store, its data folder, an empty copy folder, and the warning cleared before and after."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.data = self.s.path.parent
        self.live = self.s.backups_dir
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-copy-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.copy = self.tmp / "copies"
        self.copy.mkdir()
        self.clear()
        self.addCleanup(self.clear)
        if self.live.is_dir():
            shutil.rmtree(self.live)

    def clear(self):
        backup.set_copy_warning(None)
        backup._set_warning(None)

    def on(self, folder=None):
        return settings.set_backup_copy_folder(self.data, str(folder or self.copy))

    def names(self, folder):
        return sorted(p.name for p in Path(folder).iterdir())


class TheSetting(Rig):
    def test_off_by_default_and_saved_beside_the_other_settings(self):
        self.assertIsNone(settings.backup_copy_folder(self.data))
        settings.set_backups_kept(self.data, 21)
        self.assertEqual(self.on(), self.copy)
        self.assertEqual(settings.backup_copy_folder(self.data), self.copy)
        self.assertEqual(json.loads((self.data / settings.FILE).read_text()), {"backups_kept": 21, "backup_copy_folder": str(self.copy)})
        settings.set_profile(self.data, "Sam Lee", "")
        self.assertEqual(settings.backup_copy_folder(self.data), self.copy, "another setting saved later leaves it")

    def test_an_empty_text_turns_it_off_and_keeps_the_rest(self):
        settings.set_backups_kept(self.data, 9)
        self.on()
        self.assertIsNone(settings.set_backup_copy_folder(self.data, "  "))
        self.assertIsNone(settings.backup_copy_folder(self.data))
        self.assertEqual(settings.backups_kept(self.data), 9)

    def test_a_missing_folder_is_made_and_a_tilde_is_written_out(self):
        made = self.tmp / "new" / "deeper"
        self.assertEqual(self.on(made), made)
        self.assertTrue(made.is_dir())
        with mock.patch.dict(os.environ, {"HOME": str(self.tmp)}):
            self.assertEqual(settings.set_backup_copy_folder(self.data, "~/copies"), self.copy)

    def refused(self, text, message=None):
        before = (self.data / settings.FILE).read_bytes() if (self.data / settings.FILE).exists() else None
        with self.assertRaises(ValueError) as caught:
            settings.set_backup_copy_folder(self.data, text)
        said = str(caught.exception)
        self.assertTrue(said.endswith("Nothing was changed."), said)
        if message:
            self.assertEqual(said, message)
        after = (self.data / settings.FILE).read_bytes() if (self.data / settings.FILE).exists() else None
        self.assertEqual(after, before, "a refusal writes nothing")
        return said

    def test_not_absolute_or_odd_text_is_refused(self):
        for text in ("copies", "../copies", "a\nb", "x" * 1001, 5, ["/tmp"]):
            with self.subTest(text=text):
                self.refused(text, settings.COPY_BAD)

    def test_the_data_folder_the_backups_folder_and_anything_inside_either_is_refused(self):
        self.live.mkdir()
        for folder in (self.data, self.live, self.data / "inner", self.live / "inner", self.data / ".." / self.data.name):
            with self.subTest(folder=str(folder)):
                self.refused(str(folder), settings.COPY_IN_DATA)
        self.assertFalse((self.data / "inner").exists(), "a refused folder is not made")

    def test_a_shortcut_into_the_data_folder_does_not_get_round_it(self):
        link = self.tmp / "shortcut"
        link.symlink_to(self.data)
        self.refused(str(link), settings.COPY_IN_DATA)
        self.refused(str(link / "backups"), settings.COPY_IN_DATA)

    def test_a_file_a_folder_that_cannot_be_made_and_one_that_cannot_be_written_are_refused(self):
        file = self.tmp / "a-file"
        file.write_text("x", encoding="utf-8")
        self.refused(str(file), settings.COPY_NOT_FOLDER)
        self.refused(str(file / "under"), settings.COPY_CANT_MAKE)
        if not ROOT:
            shut = self.tmp / "shut"
            shut.mkdir(mode=0o500)
            self.addCleanup(os.chmod, shut, 0o700)
            self.refused(str(shut), settings.COPY_NOT_WRITABLE)

    def test_a_settings_file_that_cannot_be_read_is_never_replaced(self):
        (self.data / settings.FILE).write_text("{not json", encoding="utf-8")
        self.refused(str(self.copy), settings.COPY_UNREADABLE)
        self.assertEqual((self.data / settings.FILE).read_text(), "{not json")

    def test_a_saved_value_that_is_not_a_usable_path_reads_as_off(self):
        for value in ("relative", "", 5, None, ["/x"]):
            (self.data / settings.FILE).write_text(json.dumps({"backup_copy_folder": value}), encoding="utf-8")
            self.assertIsNone(settings.backup_copy_folder(self.data), value)


class TheCopy(Rig):
    def test_each_backup_is_also_a_finished_single_file_under_the_same_name(self):
        self.on()
        self.demo.action()                                           # its daily backup is copied too
        made = backup.take(self.s, "undo")
        self.assertEqual(self.names(self.copy), self.names(self.live))
        self.assertIn(made.name, self.names(self.copy))
        self.assertEqual(sha(self.copy / made.name), sha(made))
        self.assertEqual(cs.check_copy(self.copy / made.name)["rows"], cs.check_copy(made)["rows"])
        self.assertEqual([n for n in os.listdir(self.copy) if n.endswith(("-wal", "-shm", "-journal", ".part"))], [], "never a side file or a working file")
        self.assertIsNone(backup.copy_warning)

    def test_the_daily_copy_taken_by_a_save_is_copied_too(self):
        self.on()
        self.demo.action()
        self.assertEqual(self.names(self.copy), self.names(self.live))
        self.assertEqual(len(self.names(self.copy)), 1)

    def test_every_kind_of_backup_goes_to_the_folder(self):
        self.on()
        for tag in ("daily", "undo", "import", "changes", "restore", "migrate"):
            backup.take(self.s, tag)
        self.assertEqual(self.names(self.copy), self.names(self.live))
        self.assertEqual(len(self.names(self.copy)), 6)

    def test_off_means_nothing_is_written_anywhere_else(self):
        made = backup.take(self.s, "undo")
        self.assertEqual(self.names(self.copy), [])
        self.assertTrue(made.exists())
        self.assertIsNone(backup.copy_warning)

    def test_the_copy_is_written_to_a_temporary_name_and_renamed_into_place(self):
        self.on()
        seen = []
        real = pl.replace_file

        def watch(source, dest, *a, **k):
            seen.append((Path(source).name, Path(source).parent, Path(dest).name, os.path.lexists(dest), sorted(os.listdir(self.copy))))
            return real(source, dest, *a, **k)

        with mock.patch.object(pl, "replace_file", watch):
            made = backup.take(self.s, "undo")
        ours = [x for x in seen if x[1] == self.copy]
        self.assertEqual(len(ours), 1)
        source, _, dest, existed, listing = ours[0]
        self.assertTrue(source.startswith(".") and source.endswith(".part"), source)
        self.assertEqual(dest, made.name)
        self.assertFalse(existed)
        self.assertEqual(listing, [source], "until the rename, the only thing in the folder has a working name")

    def test_a_copy_that_fails_part_way_leaves_no_file_with_a_backup_name_and_no_working_file(self):
        self.on()
        with mock.patch.object(pl, "replace_file", side_effect=OSError(5, "boom")), self.assertLogs("clark.backup", "WARNING"):
            made = backup.take(self.s, "undo")
        self.assertTrue(made.exists(), "the backup here is made")
        self.assertEqual(self.names(self.copy), [])
        self.assertIn("could not be made", backup.copy_warning)

    def test_a_copy_cut_short_is_caught_by_reading_it_back(self):
        # bytes that differ after writing are refused (a full disk can cut a file short with no error)
        src = self.tmp / "src.bin"
        src.write_bytes(b"abc" * 1000)
        part = self.tmp / "part.bin"
        part.write_bytes(b"")
        real_open = open

        def cut(path, mode="r", *a, **k):
            handle = real_open(path, mode, *a, **k)
            if "w" in mode and Path(path) == part:
                write = handle.write
                handle.write = lambda data: write(data[:-1])
            return handle

        with mock.patch("builtins.open", cut):
            with self.assertRaises(Invalid) as caught:
                backup._copy_checked(src, part)
        self.assertEqual(str(caught.exception), backup.COPY_DIFFERENT)

    def test_a_name_already_there_is_left_as_it_is(self):
        self.on()
        made = backup.take(self.s, "undo")
        (self.copy / made.name).write_bytes(b"someone else's file")
        backup.copy_out(self.data, made)
        self.assertEqual((self.copy / made.name).read_bytes(), b"someone else's file")


class Retention(Rig):
    def test_the_copy_folder_keeps_the_same_number_as_the_data_folder_says(self):
        settings.set_backups_kept(self.data, 3)
        self.on()
        for _ in range(6):
            backup.take(self.s, "undo")
        kept = [e.name for e in backup.entries(self.copy)]
        self.assertEqual(len(kept), 3)
        self.assertEqual(kept, [e.name for e in backup.entries(self.live)], "the same newest three as here")

    def test_only_clarks_own_backup_names_are_ever_removed_there(self):
        settings.set_backups_kept(self.data, 1)
        self.on()
        keep = ["notes.txt", "clark-old.db", "clark-20200101T000000Z-bogus.db", "clark-20200101T000000Z-undo.db.txt", "Report.xlsx",
                "clark.db", "replaced-20200101T000000Z", ".hidden"]
        for name in keep:
            path = self.copy / name
            path.mkdir() if name.startswith("replaced-") else path.write_bytes(b"mine")
        for _ in range(4):
            backup.take(self.s, "undo")
        left = set(os.listdir(self.copy))
        self.assertEqual(set(keep) - left, set(), "nothing that is not a clark backup name was removed")
        self.assertEqual(len([n for n in left if backup.NAME.fullmatch(n)]), 1)

    def test_a_linked_file_or_a_link_in_the_folder_is_never_removed(self):
        settings.set_backups_kept(self.data, 1)
        self.on()
        outside = self.tmp / "outside.db"
        outside.write_bytes(b"x")
        (self.copy / "clark-20200101T000000Z-undo.db").symlink_to(outside)
        for _ in range(3):
            backup.take(self.s, "undo")
        self.assertTrue(outside.exists())
        self.assertTrue((self.copy / "clark-20200101T000000Z-undo.db").is_symlink())


class WhenItFails(Rig):
    def warned(self):
        self.assertIsNotNone(backup.copy_warning)
        self.assertIn("Your backup was made, but the copy in ", backup.copy_warning)
        return backup.copy_warning

    def test_a_missing_folder_is_a_plain_warning_and_the_backup_and_the_save_still_succeed(self):
        self.on()
        shutil.rmtree(self.copy)
        with self.assertLogs("clark.backup", "WARNING") as logs:
            self.demo.action()                                    # a save: takes the daily backup first
        self.assertEqual(len(self.names(self.live)), 1, "the backup here was made")
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM actions").fetchone()[0], 1, "and the change was saved")
        self.assertIn("it isn't there", self.warned())
        self.assertEqual(len(logs.records), 1)

    def test_an_unwritable_folder_is_a_plain_warning(self):
        if ROOT:
            self.skipTest("root can write anywhere")
        self.on()
        self.copy.chmod(0o500)
        self.addCleanup(self.copy.chmod, 0o700)
        with self.assertLogs("clark.backup", "WARNING"):
            self.demo.action()
        self.assertIn("this account isn't allowed to use it", self.warned())
        self.assertEqual(len(self.names(self.live)), 1)

    def test_a_full_folder_is_a_plain_warning(self):
        self.on()
        with mock.patch.object(backup, "_copy_checked", side_effect=OSError(28, "No space left on device")), \
                self.assertLogs("clark.backup", "WARNING"):
            self.demo.action()
        self.assertIn("the disk is full", self.warned())
        self.assertEqual(self.names(self.copy), [], "no half file")
        self.assertEqual(len(self.names(self.live)), 1)

    def test_a_folder_that_is_a_file_is_a_plain_warning(self):
        self.on()
        shutil.rmtree(self.copy)
        self.copy.write_text("x", encoding="utf-8")
        with self.assertLogs("clark.backup", "WARNING"):
            backup.take(self.s, "undo")
        self.assertIn("it isn't a folder", self.warned())

    def test_a_fault_nobody_expected_is_still_only_a_warning(self):
        self.on()
        with mock.patch.object(backup, "_copy_into", side_effect=RuntimeError("secret detail /Users/someone")), \
                self.assertLogs("clark.backup", "WARNING") as logs:
            self.demo.action()
        self.assertIn("something went wrong", self.warned())
        self.assertNotIn("secret detail", backup.copy_warning + "".join(logs.output))
        self.assertEqual(len(self.names(self.live)), 1)

    def test_the_copy_before_an_undo_or_an_import_is_never_refused_because_the_copy_folder_failed(self):
        self.on()
        self.demo.action()
        shutil.rmtree(self.copy)
        with self.assertLogs("clark.backup", "WARNING"):
            made = backup.take(self.s, "undo")
        self.assertTrue(made.exists())
        step = self.demo.update("actions", "ABC-A-001", {"owner": "Sam Example"})
        with self.assertLogs("clark.backup", "WARNING"):
            self.s.undo(step, "Demo User")                         # an undo takes its backup through Store.step
        self.assertIn("it isn't there", self.warned())

    def test_a_good_copy_clears_the_warning_and_turning_it_off_does_too(self):
        self.on()
        shutil.rmtree(self.copy)
        with self.assertLogs("clark.backup", "WARNING"):
            backup.take(self.s, "undo")
        self.warned()
        self.copy.mkdir()
        backup.take(self.s, "undo")
        self.assertIsNone(backup.copy_warning)
        shutil.rmtree(self.copy)
        with self.assertLogs("clark.backup", "WARNING"):
            backup.take(self.s, "undo")
        settings.set_backup_copy_folder(self.data, "")
        backup.take(self.s, "undo")
        self.assertIsNone(backup.copy_warning)

    def test_a_folder_the_settings_file_names_inside_the_data_folder_is_refused_at_copy_time(self):
        self.live.mkdir()
        for folder in (self.data, self.live, self.data / "inner"):
            (self.data / "inner").mkdir(exist_ok=True)
            (self.data / settings.FILE).write_text(json.dumps({"backup_copy_folder": str(folder)}), encoding="utf-8")
            before = set(os.listdir(folder))
            with self.assertLogs("clark.backup", "WARNING"):
                made = backup.take(self.s, "undo")
            added = set(os.listdir(folder)) - before - ({made.name} if folder == self.live else set())
            self.assertEqual(added, set(), "nothing was copied there")
            self.assertIn("can't be used", self.warned())

    def test_a_hung_folder_holds_a_save_up_for_the_wait_and_no_longer(self):
        self.on()
        stuck, done = threading.Event(), threading.Event()

        def hang(*a, **k):
            stuck.wait(10)
            done.set()

        with mock.patch.object(backup, "COPY_WAIT", 0.3), mock.patch.object(backup, "_copy_into", hang):
            began = time.monotonic()
            made = backup.take(self.s, "undo")
            took = time.monotonic() - began
        self.assertLess(took, 3)
        self.assertTrue(made.exists())
        stuck.set()
        self.assertTrue(done.wait(5))
        for t in threading.enumerate():
            if t.name == "clark-backup-copy":
                t.join(5)

    def test_a_slow_copy_folder_does_not_hold_up_the_live_backups_lock(self):
        self.on()
        entered, release = threading.Event(), threading.Event()
        real = backup.entries

        def slow(folder):
            if Path(folder) == self.copy:                          # reading the copy folder hangs, with its tidying under way
                entered.set()
                release.wait(10)
            return real(folder)

        with mock.patch.object(backup, "COPY_WAIT", 0.2), mock.patch.object(backup, "entries", slow):
            backup.take(self.s, "undo")
            self.assertTrue(entered.wait(5))
            began = time.monotonic()
            backup.take(self.s, "daily")                           # a second backup here while the first copy is stuck in the copy folder
            self.assertLess(time.monotonic() - began, 3)
            release.set()
            for t in threading.enumerate():
                if t.name == "clark-backup-copy":
                    t.join(5)

    def test_a_copy_taken_for_an_undo_or_import_goes_to_the_folder_only_if_its_step_kept_it(self):
        self.on()
        dropped = backup.take_pending(self.s, "undo")              # a step that failed or wrote nothing
        backup.finish(dropped, False)
        self.assertEqual((self.names(self.live), self.names(self.copy)), ([], []))
        kept = backup.take_pending(self.s, "undo")
        self.assertEqual(self.names(self.copy), [], "not before the step has finished")
        backup.finish(kept, True)
        self.assertEqual(self.names(self.copy), self.names(self.live))
        self.assertEqual(len(self.names(self.copy)), 1)


class NoDetailLeaks(Rig):
    def test_the_warning_writes_the_folder_from_the_home_folder_and_holds_no_technical_word(self):
        folder = Path.home() / "Documents" / "clark copies"
        text = backup.copy_warning_text(folder, OSError(28, "No space left on device"))
        self.assertIn("~/Documents/clark copies", text)
        self.assertNotIn(str(Path.home()), text)
        self.assertFalse([w for w in safety.JARGON if w in text.lower()], text)
        self.assertFalse(text.startswith(("clark", "Clark")))

    def test_the_settings_refusals_hold_no_technical_word(self):
        for text in (settings.COPY_BAD, settings.COPY_IN_DATA, settings.COPY_NOT_FOLDER, settings.COPY_CANT_MAKE, settings.COPY_NOT_WRITABLE,
                     settings.COPY_UNREADABLE, backup.COPY_REFUSED, safety.FOLDER_HELP, safety.FOLDER_ON, safety.FOLDER_OFF):
            self.assertFalse([w for w in safety.JARGON if w in text.lower()], text)
            self.assertFalse(text.startswith(("clark", "Clark")), text)


class OneDrive(Rig):
    def setUp(self):
        super().setUp()
        self.od = self.tmp / "OneDrive-DemoOrg"
        self.od.mkdir()

    def test_the_live_data_folder_in_onedrive_is_refused_and_says_what_to_do(self):
        with self.assertRaises(pl.PlatformError) as caught:
            open_store(self.od / "data" / "clark.db", onedrive_roots=[self.od])
        said = str(caught.exception)
        self.assertIn("choose a backup folder in OneDrive instead", said)
        self.assertIn("Your data can't be kept in", said)
        with self.assertRaises(pl.PlatformError) as caught:
            pl.check_data_dir(self.od / "x" / "backups", [self.od], what="backups")
        self.assertIn("Copy my backups to", str(caught.exception))
        self.assertNotIn("backups can still go to OneDrive", str(caught.exception))

    def test_the_copy_folder_may_be_in_onedrive_and_the_live_folder_still_may_not(self):
        self.s.onedrive_roots = [self.od]
        target = self.od / "clark backups"
        self.assertEqual(self.on(target), target)
        made = backup.take(self.s, "undo")
        self.assertEqual(self.names(target), [made.name])
        self.assertEqual(sha(target / made.name), sha(made))
        shutil.rmtree(self.live)
        self.live.symlink_to(self.od)                              # a live backups folder that is really in OneDrive is still refused
        with self.assertRaises(Invalid):
            backup.take(self.s, "undo")
        self.live.unlink()


class Restoring(Rig):
    def filled(self, tag="daily"):
        self.on()
        self.demo.action()
        self.demo.action()
        return backup.take(self.s, tag)

    def test_a_copy_is_restored_from_the_folder_onto_a_clean_data_folder(self):
        made = self.filled()
        want = cs.check_copy(made)["rows"]
        clean = self.tmp / "new-computer" / "clark"
        before = self.names(self.copy)
        out, err = io.StringIO(), io.StringIO()
        code = launcher.restore_main(["--data", str(clean), "--from", str(self.copy), made.name], out, err, onedrive_roots=[])
        self.assertEqual((code, err.getvalue()), (0, ""))
        self.assertIn(f"Put {made.name} back", out.getvalue())
        opened = open_store(clean / "clark.db", onedrive_roots=[])
        try:
            self.assertEqual(opened.con.execute("SELECT count(*) FROM actions").fetchone()[0], 2)
            self.assertEqual(cs.check_copy(clean / "clark.db")["rows"], want)
        finally:
            opened.close()
        self.assertEqual(self.names(self.copy), before, "a restore writes nothing into the copy folder")
        self.assertTrue((clean / "backups" / made.name).is_file(), "the file was checked and brought beside the data first")

    def test_restore_into_reads_a_copy_from_the_folder_into_a_fresh_data_folder(self):
        made = self.filled()
        fresh = self.tmp / "fresh"
        path = backup.restore_into(fresh, made.name, self.copy, [])
        self.assertEqual(cs.check_copy(path)["rows"], cs.check_copy(made)["rows"])

    def test_the_folder_can_be_listed_with_no_name(self):
        made = self.filled()
        out, err = io.StringIO(), io.StringIO()
        code = launcher.restore_main(["--data", str(self.data), "--from", str(self.copy)], out, err, onedrive_roots=[])
        self.assertEqual((code, err.getvalue()), (0, ""))
        self.assertIn(made.name, out.getvalue())
        self.assertIn("restore --from FOLDER NAME", out.getvalue())

    def refused(self, name, fragment, clean=None):
        clean = clean or self.tmp / "clean"
        before = self.names(self.copy)
        out, err = io.StringIO(), io.StringIO()
        code = launcher.restore_main(["--data", str(clean), "--from", str(self.copy), name], out, err, onedrive_roots=[])
        self.assertEqual(code, 1, (out.getvalue(), err.getvalue()))
        self.assertIn(fragment, err.getvalue())
        self.assertFalse((clean / "clark.db").exists(), "nothing was put back")
        self.assertEqual(self.names(self.copy), before)
        self.assertNotIn(str(Path.home()), err.getvalue())

    def test_a_corrupt_file_there_is_refused(self):
        self.filled()
        name = "clark-20300101T000000Z-undo.db"
        (self.copy / name).write_bytes(b"this is not a database" * 100)
        self.refused(name, "is damaged")

    def test_a_truncated_copy_is_refused(self):
        made = self.filled()
        name = "clark-20300101T000001Z-undo.db"
        (self.copy / name).write_bytes(made.read_bytes()[:5000])
        self.refused(name, "damaged")

    def test_bring_in_checks_the_file_and_puts_nothing_beside_the_data_when_it_is_refused(self):
        self.filled()
        name = "clark-20300101T000000Z-undo.db"
        (self.copy / name).write_bytes(b"not a database" * 50)
        with self.assertRaises(Invalid) as caught:
            backup.bring_in(self.copy, name, self.live, [])
        self.assertIn("damaged", str(caught.exception))
        self.assertEqual([n for n in os.listdir(self.live) if n.endswith(name[-8:]) or n.startswith(".")] if self.live.exists() else [], [])

    def test_a_name_that_is_not_a_backup_name_or_not_there_is_refused(self):
        self.filled()
        (self.copy / "notes.txt").write_text("x", encoding="utf-8")
        for name in ("notes.txt", "../escape.db", "clark-20300101T000000Z-undo.db", "clark.db"):
            with self.subTest(name=name):
                self.refused(name, "No backup called")
        self.assertIn("restore --from FOLDER", self._last_error("notes.txt"))

    def _last_error(self, name):
        out, err = io.StringIO(), io.StringIO()
        launcher.restore_main(["--data", str(self.tmp / "clean2"), "--from", str(self.copy), name], out, err, onedrive_roots=[])
        return err.getvalue()

    def test_a_link_in_the_folder_is_refused(self):
        made = self.filled()
        link = self.copy / "clark-20300101T000002Z-undo.db"
        link.symlink_to(made)
        self.refused(link.name, "No backup called")

    def test_a_backup_of_another_database_is_not_put_over_this_one(self):
        self.filled()
        other = DemoStore()
        self.addCleanup(other.close)
        stranger = backup.take(other.store, "undo")
        shutil.copy(stranger, self.copy / "clark-20300101T000003Z-undo.db")
        out, err = io.StringIO(), io.StringIO()
        self.s.close()
        code = launcher.restore_main(["--data", str(self.data), "--from", str(self.copy), "clark-20300101T000003Z-undo.db"], out, err, onedrive_roots=[])
        self.assertEqual(code, 1)
        self.assertIn("a backup of a different database", err.getvalue())
        self.assertNotIn("Put clark", out.getvalue())

    def test_a_different_file_with_the_same_name_beside_the_data_is_never_overwritten(self):
        made = self.filled()
        self.live.mkdir(exist_ok=True)
        (self.live / made.name).write_bytes(made.read_bytes() + b"")           # the same file: used as it is
        self.assertEqual(backup.bring_in(self.copy, made.name, self.live, []), self.live / made.name)
        (self.copy / made.name).write_bytes(Path(self.live / made.name).read_bytes())
        other = DemoStore()
        self.addCleanup(other.close)
        diff = backup.take(other.store, "undo")
        shutil.copy(diff, self.copy / made.name)
        with self.assertRaises(Invalid) as caught:
            backup.bring_in(self.copy, made.name, self.live, [])
        self.assertIn("is already in", str(caught.exception))


class TheRoute(Rig):
    def setUp(self):
        super().setUp()
        self.safety = safety.Safety(self.s.path, [])

    def test_the_listing_carries_the_folder_and_its_warning(self):
        status, body = self.safety.listing()
        self.assertEqual((status, body["copy_folder"], body["copy_warning"]), (200, "", None))
        self.assertEqual(body["copy_label"], "Copy my backups to")
        self.on()
        shutil.rmtree(self.copy)
        with self.assertLogs("clark.backup", "WARNING"):
            backup.take(self.s, "undo")
        body = self.safety.listing()[1]
        self.assertEqual(body["copy_folder"], str(self.copy))
        self.assertIn("could not be made", body["copy_warning"])

    def test_saving_and_clearing_through_the_seam(self):
        status, body = self.safety.copy_folder({"folder": str(self.copy)})
        self.assertEqual((status, body["ok"], body["folder"]), (200, True, str(self.copy)))
        self.assertEqual(settings.backup_copy_folder(self.data), self.copy)
        status, body = self.safety.copy_folder({"folder": ""})
        self.assertEqual((status, body["ok"], body["folder"]), (200, True, ""))
        self.assertIsNone(settings.backup_copy_folder(self.data))

    def test_a_refusal_is_plain_and_writes_nothing(self):
        for req in ({"folder": str(self.data)}, {"folder": "relative"}, {"folder": 5}, {}, {"folder": "", "x": 1}, None, "x", []):
            with self.subTest(req=req):
                status, body = self.safety.copy_folder(req)
                self.assertEqual((status, body["ok"]), (400, False))
                self.assertTrue(body["message"].endswith("Nothing was changed."), body["message"])
        self.assertFalse((self.data / settings.FILE).exists())

    def test_saving_a_new_folder_forgets_the_warning_about_the_old_one(self):
        self.on()
        shutil.rmtree(self.copy)
        with self.assertLogs("clark.backup", "WARNING"):
            backup.take(self.s, "undo")
        self.assertIsNotNone(backup.copy_warning)
        self.safety.copy_folder({"folder": str(self.tmp / "other")})
        self.assertIsNone(backup.copy_warning)

    def test_onedrive_folders_found_here_are_offered(self):
        od = self.tmp / "OneDrive-DemoOrg"
        od.mkdir()
        found = safety.Safety(self.s.path, [od]).listing()[1]["copy_suggestions"]
        self.assertEqual(found, [str(od / "clark backups")])
        self.assertEqual(self.safety.listing()[1]["copy_suggestions"], [])


if __name__ == "__main__":
    unittest.main()

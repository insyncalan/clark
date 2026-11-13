"""Tests added after hand-mutating src/clark/backup.py: each one fails if the condition it names is changed.
Run: python3 dev/run_tests.py test_backup_mutants      Fictional data only, in temporary folders."""
import json
import os
import shutil
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from test_backup import FIXED, Backed, USER
from clark import backup, platform as pl, store as cs
from clark.store import Invalid, open_store


def stamp(i):
    return (FIXED + timedelta(seconds=i)).strftime("%Y%m%dT%H%M%SZ")


class Mutants(Backed):
    def plant(self, tag, n):
        """n valid copies named for consecutive seconds, oldest first; their file times follow the names."""
        source = self.demo.dir / "source.db"
        shutil.copyfile(backup.take(self.s, "restore"), source)
        self.wipe()
        self.folder.mkdir(exist_ok=True)
        made = []
        for i in range(n):
            p = self.folder / f"clark-{stamp(i)}-{tag}.db"
            shutil.copyfile(source, p)
            os.utime(p, (1_900_000_000 + i, 1_900_000_000 + i))
            made.append(p.name)
        return made

    def empty_copy(self, dest):
        other = Path(tempfile.mkdtemp(prefix="clark-empty-"))
        self.addCleanup(shutil.rmtree, other, True)
        store = open_store(other / "clark.db", onedrive_roots=[])
        cs.snapshot(store.path, pl.private_file(dest))
        store.close()
        return dest

    def test_restored_copies_keep_two_even_when_one_is_asked(self):
        made = self.plant("restore", 3)
        backup.prune(self.folder, 1)
        self.assertEqual(self.names(), made[-2:])

    def test_the_newest_with_projects_is_kept_inside_its_own_kind(self):
        good = self.plant("daily", 3)
        self.empty_copy(self.folder / f"clark-{stamp(9)}-daily.db")
        os.utime(self.folder / f"clark-{stamp(9)}-daily.db", (1_900_000_100, 1_900_000_100))
        backup.prune(self.folder, 1, newest_has_rows=False)
        self.assertEqual(self.names(), [good[-1], f"clark-{stamp(9)}-daily.db"])

    def test_a_folder_that_cannot_be_read_means_a_copy_is_due(self):
        not_a_folder = self.demo.dir / "afile"
        not_a_folder.write_text("x", encoding="utf-8")
        self.assertTrue(backup.due_today(not_a_folder))

    def test_a_link_with_a_backups_name_is_not_a_backup(self):
        real = self.plant("undo", 1)[0]
        link = self.folder / f"clark-{stamp(5)}-undo.db"
        link.symlink_to(self.folder / real)
        self.assertEqual(self.copies(), [real])
        with self.assertRaisesRegex(Invalid, "^No backup called"):
            backup.valid_name(self.folder, link.name)

    def test_a_second_name_for_a_backup_is_refused_by_name(self):
        real = self.plant("undo", 1)[0]
        twin = self.folder / f"clark-{stamp(6)}-undo.db"
        os.link(self.folder / real, twin)
        with self.assertRaisesRegex(Invalid, "^No backup called"):
            backup.valid_name(self.folder, twin.name)
        with self.assertRaisesRegex(Invalid, "^No backup called"):
            backup.valid_name(self.folder, real)          # both names of one file are refused
        self.assertEqual(self.copies(), [])

    def test_a_name_longer_than_eighty_characters_is_cut_in_the_refusal(self):
        with self.assertRaises(Invalid) as got:
            backup.valid_name(self.folder, "x" * 200)
        self.assertIn("x" * 80, str(got.exception))
        self.assertNotIn("x" * 81, str(got.exception))

    def test_without_a_counter_a_name_orders_as_counter_one(self):
        plain = self.plant("undo", 1)[0]
        counted = self.folder / f"clark-{plain[6:-3].split('-undo')[0]}-undo-1.db"
        shutil.copyfile(self.folder / plain, counted)
        t = os.stat(self.folder / plain).st_mtime_ns
        os.utime(counted, ns=(t, t))
        two = self.folder / counted.name.replace("-undo-1", "-undo-2")
        shutil.copyfile(counted, two)
        os.utime(two, ns=(t, t))
        by = {e.name: e.counter for e in backup.entries(self.folder)}
        self.assertEqual(by, {plain: 1, counted.name: 1, two.name: 2})
        self.assertEqual(self.copies(), [counted.name, plain, two.name], "equal counter, equal time: ordered by name")

    def holds_nothing(self, projects, applies):
        with mock.patch.object(cs, "check_copy", return_value={"rows": {"projects": projects, "applies": applies}}):
            return backup._holds_nothing(self.demo.dir / "clark.db")

    def test_a_database_holds_nothing_only_with_no_projects_and_no_steps(self):
        self.assertTrue(self.holds_nothing(0, 0))
        self.assertFalse(self.holds_nothing(0, 3), "steps but no projects")
        self.assertFalse(self.holds_nothing(2, 0), "projects but no steps")
        self.assertFalse(self.holds_nothing(2, 3))

    def test_a_file_that_is_not_a_database_holds_something(self):
        junk = self.demo.dir / "junk.db"
        junk.write_bytes(b"not a database at all")
        self.assertFalse(backup._holds_nothing(junk))

    def test_the_aside_folder_takes_the_next_free_number(self):
        base = "replaced-" + FIXED.strftime("%Y%m%dT%H%M%SZ")
        self.folder.mkdir(exist_ok=True)
        first = backup._new_aside(self.folder, [])
        self.assertEqual(first.name, base)
        second = backup._new_aside(self.folder, [])
        third = backup._new_aside(self.folder, [])
        self.assertEqual((second.name, third.name), (base + "-2", base + "-3"))
        self.assertTrue(all(p.is_dir() for p in (first, second, third)))

    def test_a_restore_note_naming_an_odd_folder_is_not_followed(self):
        path = self.demo.dir / "gone.db"
        (self.demo.dir / "backups").mkdir(exist_ok=True)
        odd = self.demo.dir / "backups" / "notes"
        odd.mkdir(exist_ok=True)
        (self.demo.dir / ("gone.db" + backup.MARKER)).write_text(json.dumps({"aside": "notes"}), encoding="utf-8")
        aside, reason = backup._unfinished(path)
        self.assertIsNone(aside)
        self.assertIn("a folder whose name starts with replaced-", reason)

    def test_a_restore_with_no_working_copy_is_reported_with_the_folder_that_holds_the_database(self):
        path = self.demo.dir / "gone.db"
        aside = self.demo.dir / "backups" / "replaced-20300101T000000Z"
        aside.mkdir(parents=True)
        (self.demo.dir / ("gone.db" + backup.MARKER)).write_text(json.dumps({"aside": aside.name}), encoding="utf-8")
        found, reason = backup._unfinished(path)
        self.assertEqual(found, aside)
        self.assertIn(f"Your database is in {backup.shown(aside)}", reason)

    def test_the_list_shows_the_newest_first(self):
        made = self.plant("daily", 3)
        self.assertEqual([x["name"] for x in backup.listing(self.folder)], made[::-1])


if __name__ == "__main__":
    unittest.main()

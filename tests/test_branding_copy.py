"""1.0.6: the brand folder is branding/ at the top of the clark folder. The first start copies the old system/branding into it
(never over anything, never deleting, the old folder left as it is). Temp folders only.

Run: python3 dev/run_tests.py test_branding_copy
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _brand_rig
from clark import brands, page, release_files, update_helper


def tree(folder):
    return _brand_rig.snapshot(folder)


class Copy(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.old = self.root / "system" / "branding"
        (self.old / "mine").mkdir(parents=True)
        (self.old / "tokens.css").write_text(":root{--a:1}", encoding="utf-8")
        (self.old / "mine" / "logo.png").write_bytes(b"\x89PNG-mine")
        self.before = tree(self.old)
        self.new = self.root / "branding"

    def test_the_page_finds_the_folder_at_the_top_of_the_clark_folder(self):
        self.assertEqual(Path("/x/clark/branding"), page.branding_folder(Path("/x/clark")))
        self.assertEqual(Path("/x/clark/branding"), page.branding_folder(Path("/x/clark/.app")))
        self.assertEqual(Path("/x/clark"), page.branding_folder(Path("/x/clark")).parent, "the clark folder is one parent up, not two")

    def test_the_first_run_copies_and_leaves_the_old_folder_as_it_was(self):
        self.assertTrue(brands.copy_old_folder(self.root))
        self.assertEqual(self.before, tree(self.new))
        self.assertEqual(self.before, tree(self.old))
        self.assertEqual([], [n for n in os.listdir(self.root) if n.startswith(".clark-")], "no stage or journal is left")

    def test_running_twice_changes_nothing(self):
        brands.copy_old_folder(self.root)
        (self.new / "tokens.css").write_text(":root{--edited:1}", encoding="utf-8")
        after = tree(self.new)
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertEqual(after, tree(self.new))

    def test_a_branding_folder_with_anything_in_it_wins_and_both_are_untouched(self):
        self.new.mkdir()
        (self.new / "own.css").write_text("x", encoding="utf-8")
        mine = tree(self.new)
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertEqual(mine, tree(self.new))
        self.assertEqual(self.before, tree(self.old))

    def test_an_empty_branding_folder_is_filled(self):
        self.new.mkdir()
        self.assertTrue(brands.copy_old_folder(self.root))
        self.assertEqual(self.before, tree(self.new))

    def test_a_letter_case_spelling_counts_as_the_same_folder(self):
        (self.root / "Branding").mkdir()
        (self.root / "Branding" / "own.css").write_text("x", encoding="utf-8")
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertEqual(["Branding"], [n for n in os.listdir(self.root) if n.lower() == "branding"], "one folder of that name, whatever the disk's case rules")
        self.assertEqual(["own.css"], os.listdir(self.root / "Branding"))

    def test_a_link_at_branding_wins(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.new)
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertEqual([], os.listdir(elsewhere), "nothing was written through the link")

    def test_a_broken_link_at_branding_wins(self):
        os.symlink(self.root / "nowhere", self.new)
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertTrue(os.path.islink(self.new))

    def test_a_linked_old_folder_is_not_followed(self):
        shutil.rmtree(self.old)
        real = self.root / "real"
        real.mkdir()
        (real / "secret.txt").write_text("s", encoding="utf-8")
        os.symlink(real, self.old)
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertFalse(self.new.exists())

    def test_a_link_inside_the_old_folder_is_copied_as_a_link(self):
        os.symlink("tokens.css", self.old / "alias")
        brands.copy_old_folder(self.root)
        self.assertTrue(os.path.islink(self.new / "alias"))
        self.assertEqual("tokens.css", os.readlink(self.new / "alias"))

    def test_nothing_to_copy_does_nothing(self):
        shutil.rmtree(self.old)
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertFalse(self.new.exists())

    @unittest.skipIf(os.geteuid() == 0 if hasattr(os, "geteuid") else False, "root can write anywhere")
    def test_a_read_only_parent_changes_nothing_and_does_not_raise(self):
        os.chmod(self.root, 0o555)
        self.addCleanup(os.chmod, self.root, 0o755)
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertFalse(self.new.exists())
        self.assertEqual(self.before, tree(self.old))

    def test_a_copy_cut_halfway_leaves_no_branding_and_the_next_run_finishes_it(self):
        real = brands._copy_into
        calls = []

        def dying(src, dst):
            calls.append(src)
            if len(calls) == 2:                          # the subfolder: the first level is already written
                raise KeyboardInterrupt
            return real(src, dst)
        with mock.patch.object(brands, "_copy_into", dying):
            with self.assertRaises(KeyboardInterrupt):
                brands.copy_old_folder(self.root)
        self.assertFalse(self.new.exists(), "branding/ is never half-made")
        self.assertEqual(self.before, tree(self.old))
        # a crash that left the stage and the journal behind (no chance to clean up)
        (self.root / brands.COPY_STAGE).mkdir()
        (self.root / brands.COPY_STAGE / "half").write_text("h", encoding="utf-8")
        (self.root / brands.COPY_JOURNAL).write_text(json.dumps({"from": "system/branding"}), encoding="utf-8")
        self.assertTrue(brands.copy_old_folder(self.root))
        self.assertEqual(self.before, tree(self.new))
        self.assertFalse(brands.copy_old_folder(self.root))
        self.assertEqual([], [n for n in os.listdir(self.root) if n.startswith(".clark-")])

    def test_the_journal_is_written_before_the_first_byte_is_copied(self):
        seen = []
        real = brands._copy_into

        def watching(src, dst):
            seen.append(os.path.exists(self.root / brands.COPY_JOURNAL))
            return real(src, dst)
        with mock.patch.object(brands, "_copy_into", watching):
            brands.copy_old_folder(self.root)
        self.assertTrue(seen and seen[0])

    def test_a_branding_folder_that_appears_during_the_copy_is_never_overwritten(self):
        real = brands._copy_into

        def racing(src, dst):
            real(src, dst)
            if src == self.old:
                self.new.mkdir()
                (self.new / "theirs.css").write_text("t", encoding="utf-8")
        with mock.patch.object(brands, "_copy_into", racing):
            self.assertFalse(brands.copy_old_folder(self.root))
        self.assertEqual(["theirs.css"], os.listdir(self.new))
        self.assertEqual(self.before, tree(self.old))


class Protected(unittest.TestCase):
    def test_branding_is_a_person_folder_in_both_lists_and_system_stays(self):
        for lst in (release_files.PROTECTED, update_helper.PROTECTED):
            self.assertIn("branding", lst)
            self.assertIn("system", lst)
            self.assertIn("data", lst)
        for rel in ("branding/logo.png", "Branding/a", "BRANDING", "system/branding/x"):
            self.assertTrue(release_files.protected(rel), rel)
            self.assertTrue(update_helper.protected(rel) if hasattr(update_helper, "protected") else True, rel)
        self.assertFalse(release_files.covers("mac", "branding/logo.png"))


if __name__ == "__main__":
    unittest.main()

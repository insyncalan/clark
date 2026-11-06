"""Where each name sits in the zip (issue 694): program files in the one hidden folder, the visible few at the top, and the
person's own folders (system, data) never covered. Run: python3 dev/run_tests.py test_release_placement
"""
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
import clark.release_files as rf


class Place(unittest.TestCase):
    def test_program_files_go_in_the_hidden_folder(self):
        for rel in ("src/clark/__init__.py", "vendor/manifest.json", "vendor/README.md", "clark/__main__.py", "LICENSE",
                    "NOTICE.md", "dev/demo_data.py"):
            with self.subTest(rel=rel):
                self.assertEqual(".app/" + rel, rf.place(rel))

    def test_the_visible_few_stay_at_the_top(self):
        for rel in ("README.md", "START-HERE.md", "clark.command", "clark-release.json", "docker/compose.yaml", "docker/"):
            with self.subTest(rel=rel):
                self.assertEqual(rel, rf.place(rel))

    def test_a_readme_deeper_down_is_not_the_top_readme(self):
        self.assertEqual(".app/vendor/README.md", rf.place("vendor/README.md"))
        self.assertEqual(".app/docker2/x", rf.place("docker2/x"))

    def test_unplace_is_the_inverse_for_everything_the_list_holds(self):
        for item in rf.listed("mac") + (rf.START_HERE, rf.MANIFEST):
            with self.subTest(item=item):
                self.assertEqual(item, rf.unplace(rf.place(item)))

    def test_folder_items_place_as_folders(self):
        self.assertEqual(".app/src/clark/", rf.place("src/clark/"))
        self.assertEqual("docker/", rf.place("docker/"))


class Covers(unittest.TestCase):
    def test_every_listed_item_is_covered_where_it_is_placed(self):
        for item in rf.listed("mac"):
            if not item.endswith("/"):
                with self.subTest(item=item):
                    self.assertTrue(rf.covers("mac", rf.place(item)))
        self.assertTrue(rf.covers("mac", ".app/src/clark/store.py"))
        self.assertTrue(rf.covers("mac", "docker/compose.yaml"))
        self.assertTrue(rf.covers("mac", rf.START_HERE))
        self.assertTrue(rf.covers("mac", rf.MANIFEST))

    def test_a_flat_name_is_no_longer_covered(self):
        for rel in ("src/clark/store.py", "vendor/manifest.json", "clark/__main__.py", "LICENSE"):
            with self.subTest(rel=rel):
                self.assertFalse(rf.covers("mac", rel))

    def test_the_hidden_folder_name_must_match_exactly(self):
        for rel in (".APP/src/clark/store.py", ".app", ".app/tests/x.py", ".app2/src/clark/x.py", ".app/../x"):
            with self.subTest(rel=rel):
                self.assertFalse(rf.covers("mac", rel))

    def test_protected_prefixes_are_refused(self):
        for rel in ("system/branding/logo.png", "system/x", "data/clark.db", "data", "system", "System/branding/a",
                    "DATA/x", "Data/y.db"):
            with self.subTest(rel=rel):
                self.assertFalse(rf.covers("mac", rel))

    def test_protected_is_refused_even_when_the_list_names_it(self):
        with mock.patch.object(rf, "SHARED", ("README.md", "system/", "data/x.db")):
            self.assertFalse(rf.covers("mac", "system/branding/a"))
            self.assertFalse(rf.covers("mac", "data/x.db"))
            self.assertTrue(rf.covers("mac", "README.md"))

    def test_a_small_patched_list_is_placed_not_edited(self):
        with mock.patch.object(rf, "SHARED", ("README.md", "src/clark/")):
            self.assertTrue(rf.covers("mac", ".app/src/clark/a.py"))
            self.assertFalse(rf.covers("mac", "src/clark/a.py"))
            self.assertTrue(rf.covers("mac", "README.md"))

    def test_protected_helper_looks_at_the_first_part_only(self):
        self.assertTrue(rf.protected("system/branding/x"))
        self.assertTrue(rf.protected("SYSTEM"))
        self.assertFalse(rf.protected(".app/system/x"))
        self.assertFalse(rf.protected("docker/data/x"))
        self.assertFalse(rf.protected("database/x"))


if __name__ == "__main__":
    unittest.main()

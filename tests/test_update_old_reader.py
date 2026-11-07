"""The reader that SHIPPED in 1.0.0 against a download in the new layout (issue 694).

The installed 1.0.0 cannot be changed. Its read_release (kept verbatim in tests/fixtures/v1_0_0/, taken from the v1.0.0 tag)
accepts only a download whose one top folder is named clark-<version> and whose files sit straight under it. The new download
unzips to a folder called clark and holds the program files below .app/, so the old Update button refuses it and says the file
is damaged. This test pins that, so the one manual step for people on 1.0.0 stays documented and nobody believes a code
change can remove it. Run: python3 dev/run_tests.py test_update_old_reader
"""
import shutil
import tempfile
import types
import unittest
from pathlib import Path

from _paths import ROOT
import _signing
from clark import updates
from clark import release_files
from test_updates import listed_files, make_zip

FIXTURES = ROOT / "tests" / "fixtures" / "v1_0_0"


def load_old_reader():
    """The 1.0.0 updates module, built from its saved source around its own saved release_files."""
    rf = types.ModuleType("v100_release_files")
    exec(compile((FIXTURES / "release_files.py.txt").read_text(encoding="utf-8"), "v1.0.0 release_files.py", "exec"), rf.__dict__)
    source = (FIXTURES / "updates.py.txt").read_text(encoding="utf-8")
    line = "from clark import release_files\n"
    assert source.count(line) == 1
    old = types.ModuleType("v100_updates")
    old.__dict__["release_files"] = rf
    exec(compile(source.replace(line, ""), "v1.0.0 updates.py", "exec"), old.__dict__)
    return old


class OldReader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="clark old reader ")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.old = load_old_reader()

    def read(self, path):
        return self.old.read_release(path, "mac", "1.0.0", 2, public_key=_signing.TEST_PUBLIC)

    def flat_zip(self, start_file):
        """The old flat shape with the one start file named `start_file`; nothing else differs between two such zips."""
        files = {(start_file if rel == release_files.START_HERE else rel): body for rel, body in listed_files("1.0.1").items()}
        return make_zip(self.tmp, version="1.0.1", files=files, placed=False)

    def test_the_saved_reader_still_reads_the_shape_it_shipped_with(self):
        flat = self.flat_zip("START-HERE.txt")                # the start file 1.0.0 shipped with
        self.assertEqual("1.0.1", self.read(flat).version)

    def test_it_refuses_the_flat_shape_carrying_START_HERE_md(self):
        flat = self.flat_zip("START-HERE.md")
        with self.assertRaises(self.old.UpdateError) as said:
            self.read(flat)
        self.assertEqual("unsafe", said.exception.key)
        self.assertEqual(self.old.MESSAGES["unsafe"], said.exception.message)
        self.assertIn("START-HERE.md", said.exception.detail)

    def test_it_refuses_the_new_layout_as_damaged(self):
        placed = make_zip(self.tmp, version="1.0.1")
        with self.assertRaises(self.old.UpdateError) as said:
            self.read(placed)
        self.assertEqual("damaged", said.exception.key)
        self.assertIn("top folder 'clark'", said.exception.detail)

    def test_it_refuses_the_new_layout_even_under_the_old_top_folder_name(self):
        both = make_zip(self.tmp, version="1.0.1", top="clark-1.0.1")      # placed names, old top: the list refuses the .app names
        with self.assertRaises(self.old.UpdateError) as said:
            self.read(both)
        self.assertEqual("unsafe", said.exception.key)

    def test_the_new_reader_does_not_install_the_old_layout_either(self):
        flat = make_zip(self.tmp, version="1.0.1", placed=False)
        with self.assertRaises(updates.UpdateError) as said:
            updates.read_release(flat, "mac", "1.0.0", 2, public_key=_signing.TEST_PUBLIC)
        self.assertEqual("damaged", said.exception.key)
        self.assertTrue(said.exception.detail.startswith("old layout"))


if __name__ == "__main__":
    unittest.main()

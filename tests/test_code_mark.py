"""#1031 section 7: code_mark names the program folder by its file identity, not by how its path is spelled."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clark import appfiles  # noqa: E402


def expected(folder):
    st = os.stat(folder)
    return hashlib.sha256(f"{st.st_dev}:{st.st_ino}".encode("utf-8")).hexdigest()[:16]


class CodeMarkTest(unittest.TestCase):
    def test_the_mark_is_the_folders_file_identity(self):
        self.assertEqual(appfiles.code_mark(), expected(Path(appfiles.__file__).resolve().parents[2]))

    def test_two_spellings_of_one_folder_give_one_mark(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp).resolve() / "Clark"
            (real / "src" / "clark").mkdir(parents=True)
            other = Path(tmp).resolve() / "clark"
            if other.exists():
                self.skipTest("this file system is case-sensitive")
            fake = real / "src" / "clark" / "appfiles.py"
            fake.write_text("", encoding="utf-8")
            spelled = other / "src" / "clark" / "appfiles.py"
            if not spelled.exists():
                self.skipTest("this file system is case-sensitive")
            with mock.patch.object(appfiles, "__file__", str(fake)):
                one = appfiles.code_mark()
            with mock.patch.object(appfiles, "__file__", str(spelled)):
                two = appfiles.code_mark()
            self.assertEqual(one, two)

    def test_a_link_to_the_folder_gives_the_same_mark(self):
        # Runs on every file system: a second spelling made with a symlink.
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp).resolve() / "real"
            (real / "src" / "clark").mkdir(parents=True)
            (real / "src" / "clark" / "appfiles.py").write_text("", encoding="utf-8")
            link = Path(tmp).resolve() / "link"
            os.symlink(real, link)
            with mock.patch.object(appfiles, "__file__", str(real / "src" / "clark" / "appfiles.py")):
                one = appfiles.code_mark()
            with mock.patch.object(appfiles, "__file__", str(link / "src" / "clark" / "appfiles.py")):
                two = appfiles.code_mark()
            self.assertEqual(one, two)

    def test_different_folders_give_different_marks(self):
        with tempfile.TemporaryDirectory() as tmp:
            marks = set()
            for name in ("a", "b"):
                root = Path(tmp).resolve() / name
                (root / "src" / "clark").mkdir(parents=True)
                f = root / "src" / "clark" / "appfiles.py"
                f.write_text("", encoding="utf-8")
                with mock.patch.object(appfiles, "__file__", str(f)):
                    marks.add(appfiles.code_mark())
            self.assertEqual(len(marks), 2)

    def test_data_mark_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            want = hashlib.sha256(os.path.normcase(str(Path(tmp).resolve())).encode("utf-8")).hexdigest()[:16]
            self.assertEqual(appfiles.data_mark(tmp), want)


if __name__ == "__main__":
    unittest.main()

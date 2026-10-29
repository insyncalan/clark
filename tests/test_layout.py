"""The repo layout and the runner's set-up (#28)."""
import unittest
from pathlib import Path

from _paths import ROOT, SRC


class LayoutTest(unittest.TestCase):
    def test_clark_imports_from_src(self):
        import clark

        self.assertEqual(SRC / "clark" / "__init__.py", Path(clark.__file__).resolve())
        self.assertTrue(clark.__version__)

    def test_line_endings_are_lf_except_windows_launchers(self):
        rules = {}
        for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if parts and not parts[0].startswith("#"):
                rules[parts[0]] = parts[1:]
        self.assertIn("eol=lf", rules["*"])
        self.assertIn("eol=crlf", rules["*.cmd"])
        self.assertIn("eol=crlf", rules["*.bat"])


if __name__ == "__main__":
    unittest.main()

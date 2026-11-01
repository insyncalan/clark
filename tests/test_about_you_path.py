"""#422: the words that send a person to their name say Settings › Personal › About you, the path that exists, and
Settings > Profile (which does not) is written nowhere in src."""
import unittest
from pathlib import Path

from clark import history

SRC = Path(__file__).resolve().parent.parent / "src"
PATH = "Settings › Personal › About you"


class AboutYouPath(unittest.TestCase):
    def test_the_history_footnote_and_the_excel_cover_name_the_real_path(self):
        self.assertEqual(history.FOOTNOTE, "Names come from this computer until you add your name in " + PATH + ".")
        cover = (SRC / "clark" / "excel_cover.py").read_text(encoding="utf-8")
        self.assertIn("(" + PATH + ")", cover)

    def test_the_path_that_does_not_exist_is_written_nowhere_in_src(self):
        found = []
        for p in sorted(SRC.rglob("*")):
            if not p.is_file() or p.suffix in {".png", ".ico", ".woff", ".woff2", ".pyc", ".map", ".zip"}:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if "Settings > Profile" in text or "Settings &gt; Profile" in text:
                found.append(str(p.relative_to(SRC)))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()

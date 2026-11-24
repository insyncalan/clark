"""Row 950 (lifts the row 422 ban): About you is the Profile card, so the words that send a person to their name say Settings › Profile,
the path that exists, and the old path through Personal (Settings › Personal › About you, in any arrow form) is written nowhere in src,
page sources and the Help content included."""
import re
import unittest
from pathlib import Path

import _paths  # noqa: F401
from clark import history

SRC = Path(__file__).resolve().parent.parent / "src"
PATH = "Settings › Profile"
# The old path, Personal then About you, whatever the arrow: >, ›, &gt;, &rsaquo;, -> or →, with any spaces between.
ARROW = r"(?:>|›|&gt;|&rsaquo;|->|→|&rarr;)"
OLD_PATH = re.compile(r"Settings\s*" + ARROW + r"\s*Personal\s*" + ARROW + r"\s*About you", re.IGNORECASE)


class AboutYouPath(unittest.TestCase):
    def test_the_history_footnote_and_the_excel_cover_name_the_real_path(self):
        self.assertEqual(history.FOOTNOTE, "Names come from this computer until you add your name in " + PATH + ".")
        cover = (SRC / "clark" / "excel_cover.py").read_text(encoding="utf-8")
        self.assertIn("(" + PATH + ")", cover)

    def test_the_old_path_through_personal_is_written_nowhere_in_src(self):
        found = []
        for p in sorted(SRC.rglob("*")):
            if not p.is_file() or p.suffix in {".png", ".ico", ".woff", ".woff2", ".pyc", ".map", ".zip"}:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if OLD_PATH.search(text):
                found.append(str(p.relative_to(SRC)))
        self.assertEqual(found, [])

    def test_the_guard_catches_every_form_of_the_old_path(self):
        for old in ("Settings > Personal > About you", "Settings › Personal › About you", "Settings &gt; Personal &gt; About you",
                    "[Settings › Personal › About you](go:settings#personal)", "Settings›Personal›About you", "settings > personal > about you"):
            self.assertTrue(OLD_PATH.search(old), old)
        for good in (PATH, "Settings › Personal", "Settings › Personal › Keys", "your Profile menu"):
            self.assertFalse(OLD_PATH.search(good), good)


if __name__ == "__main__":
    unittest.main()

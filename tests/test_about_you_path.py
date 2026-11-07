"""#422: the words that send a person to their name say Settings › Personal › About you, the path that exists, and
no Settings path ending in Profile (Settings > Profile, Settings › Profile, the &gt; form) is written anywhere in src,
page sources and the Help content included."""
import re
import unittest
from pathlib import Path

import _paths  # noqa: F401
from clark import history

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
DOCS = ROOT / "docs"
# A document that quotes the 0.2.1 prototype as it was, in its own words, is history and not guidance.
QUOTES_THE_PROTOTYPE = {"handoff/prototype-gap-list.md"}
PATH = "Settings › Personal › About you"
# Any Settings path that ends at "Profile", whatever the arrow: >, ›, &gt;, &rsaquo;, -> or →, with any spaces between.
OLD_PATH = re.compile(r"Settings\s*(?:>|›|&gt;|&rsaquo;|->|→|&rarr;)\s*Profile", re.IGNORECASE)


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
            if OLD_PATH.search(text):
                found.append(str(p.relative_to(SRC)))
        self.assertEqual(found, [])

    def test_the_path_that_does_not_exist_is_written_nowhere_in_docs(self):
        found = []
        for p in sorted(DOCS.rglob("*.md")):
            rel = p.relative_to(DOCS).as_posix()
            if rel in QUOTES_THE_PROTOTYPE:
                continue
            if OLD_PATH.search(p.read_text(encoding="utf-8")):
                found.append(rel)
        self.assertEqual(found, [])

    def test_the_guard_catches_every_form_of_the_old_path(self):
        for old in ("Settings > Profile", "Settings › Profile", "Settings &gt; Profile", "[Settings › Profile](go:settings#profile)",
                    "Settings›Profile", "settings > profile"):
            self.assertTrue(OLD_PATH.search(old), old)
        for good in (PATH, "Settings › Personal", "your Profile menu"):
            self.assertFalse(OLD_PATH.search(good), good)


if __name__ == "__main__":
    unittest.main()

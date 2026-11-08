"""#599 (2): no doc, help text or test may say a use case has "three statuses" (or any count but four).

A use case can be Done (#412), so it has four statuses: On track, Flag, High risk, Done.
Run from tests/: PYTHONPATH=../src:. python3 test_status_count_words.py
Reads docs/, src/ and tests/ (text files only). This file is skipped (its examples are the stale phrases).
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("docs", "src", "tests")
SUFFIXES = {".md", ".py", ".js", ".jsx", ".html", ".txt", ".json"}
SKIPPED = {"node_modules", "vendor", "__pycache__", "fixtures"}
WRONG_COUNT = r"(?:one|two|three|five|six|1|2|3|5|6)"
STALE = re.compile(r"\b" + WRONG_COUNT + r"[ -](?:(?:use[ -]case|work[ -]item) )?status(?:es| words)\b", re.I)


def _files():
    for folder in FOLDERS:
        for path in sorted((ROOT / folder).rglob("*")):
            if path.suffix in SUFFIXES and path.is_file() and path != Path(__file__).resolve() and not SKIPPED & set(path.relative_to(ROOT).parts):
                yield path


class StatusCountWords(unittest.TestCase):
    def test_the_pattern_catches_the_stale_phrases_and_spares_four(self):
        for bad in ("thr" + "ee statuses", "Two status words", "3 use case statuses", "three work-item statuses"):
            self.assertTrue(STALE.search(bad), bad)
        for good in ("four statuses", "four use case statuses", "the status words", "a status line"):
            self.assertIsNone(STALE.search(good), good)

    def test_no_file_states_a_wrong_status_count(self):
        hits = []
        for path in _files():
            for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if STALE.search(line):
                    hits.append("%s:%d: %s" % (path.relative_to(ROOT), n, line.strip()[:100]))
        self.assertEqual(hits, [], "a use case has four statuses (Done included, #412):\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()

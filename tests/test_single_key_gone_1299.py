"""Row 1299 AP29: the old name "Single-key shortcuts" is nowhere in the page source (the four code comments now say slash commands).
Run: python3 dev/run_tests.py test_single_key_gone_1299"""
import unittest

import _paths  # noqa: F401
from _paths import ROOT

SRC = ROOT / "src" / "clark"
OLD = "single-key shortcuts"


class SingleKeyNameGone(unittest.TestCase):
    def test_old_name_is_nowhere_in_src(self):
        hits = []
        for p in sorted(SRC.rglob("*")):
            if not p.is_file() or "node_modules" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if OLD in text.lower():
                hits.append(str(p.relative_to(ROOT)))
        self.assertEqual(hits, [], "the old name Single-key shortcuts is still in: " + ", ".join(hits))


if __name__ == "__main__":
    unittest.main()

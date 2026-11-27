"""Row 1328 AP6: the releasing notes step carries the line about copies installed before the first signed version.

Run: python3 dev/run_tests.py test_releasing_doc_1328
"""
import unittest
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent / "dev" / "RELEASING.md"
LINE = ("Copies of clark installed before 1.4.0 (the first signed release) do not check an update's signature; "
        "only copies from 1.4.0 on are protected by it.")


class Releasing(unittest.TestCase):
    def test_the_releasing_notes_step_carries_the_unsigned_copies_line(self):
        step = next(l for l in DOC.read_text(encoding="utf-8").splitlines() if l.startswith("2. **Write the notes.**"))
        self.assertIn(LINE, step)
        self.assertEqual(1, step.count(LINE), "once")


if __name__ == "__main__":
    unittest.main()

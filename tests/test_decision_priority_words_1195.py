"""Row 1195: every place that refuses a decision's priority says the one approved sentence: the bulk bar's reason, the inline edit's
error, and the reader's note. Fictional data only.

Run: python3 dev/run_tests.py test_decision_priority_words_1195
"""
import re
import unittest
from pathlib import Path

from clark import sneak

SENTENCE = "A decision's priority is set in its details, one at a time."
DATA = {"project": {"code": "ABC"}, "actions": [], "raid": [], "milestones": [], "use_cases": [],
        "decisions": [{"id": "ABC-D-001", "status": "Pending", "needed_by": "2026-11-02", "made_by": "Sam Reed"}]}
LOGIC = Path(__file__).resolve().parents[1] / "src" / "clark" / "page" / "src" / "edit" / "bulkLogic.js"


class DecisionPriorityWords(unittest.TestCase):
    def test_the_reader_leaves_a_decisions_priority_out_with_the_sentence(self):
        r = sneak.read(DATA, "ABC-D-001", "high priority", __import__("datetime").date(2026, 11, 1))
        self.assertEqual(r.get("message"), f"{SENTENCE[:-1]}, so it was left out.")

    def test_the_bulk_bars_reason_is_the_sentence(self):
        m = re.search(r'noDecision:\s*"([^"]*)"', LOGIC.read_text(encoding="utf-8"))
        self.assertEqual(m.group(1), SENTENCE)


if __name__ == "__main__":
    unittest.main()

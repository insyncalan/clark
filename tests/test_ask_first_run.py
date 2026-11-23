"""#1292 slice 3: the panel word "Send the waiting messages" is the only one left; the duplicate #ask-first card is cut (slice 2 owns the first-run card).

Run: python3 dev/run_tests.py test_ask_first_run
"""
import re
import unittest

from _paths import ROOT

EDIT = ROOT / "src" / "clark" / "page" / "src" / "edit"
WORDS = (EDIT / "askWords.js").read_text(encoding="utf-8")
PANEL = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
CSS = (EDIT / "edit.css").read_text(encoding="utf-8")


class Words(unittest.TestCase):
    def test_send_word(self):
        self.assertIn('QUEUE_SEND = "Send the waiting messages"', WORDS)
        self.assertNotIn('"Send them"', WORDS)

    def test_duplicate_first_card_is_cut(self):
        old_id = r"ask-first(?!-run\b)(?![-\w]*(?:link|settings|tip))"
        self.assertIsNone(re.search(old_id, PANEL))
        self.assertIsNone(re.search(old_id, CSS))
        self.assertIsNone(re.search(r"FIRST_(TITLE|READS|SAVES|SENDS|LINK)", WORDS + PANEL))
        self.assertIn("ask-queue-send", PANEL)


if __name__ == "__main__":
    unittest.main()

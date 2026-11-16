"""Row 1234: the Help text for the use case summary's Configure panel uses only the approved words (ruling 16-11, ucConfigureWords.js).
Every bold label and every sentence in that Help paragraph must be one of the approved strings, so a reworded sentence turns this red.
Run: python3 dev/run_tests.py test_uc_help_1234. No browser."""
import json
import re
import unittest

from _paths import SRC

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"
WORDS = SRC / "clark" / "page" / "src" / "edit" / "ucConfigureWords.js"

LABELS = {"Configure", "Configure use cases", "Number shown", "All", "Viewers can scroll the list", "Status tracker", "Top", "Bottom", "Off"}
SENTENCES = [
    "Edit uses the same number but scrolls whenever a number is set, so you can reach every use case; viewers get the scrolling only when it is On.",
    "On: the list is n rows tall and scrolls up and down to the rest.",
    "Off: viewers see only the first n.",
    "The count by status and the bar.",
    "Top or bottom of the list, or off.",
]


def find(node):
    if isinstance(node, dict):
        if node.get("id") == "keep-the-use-cases":
            return node
        for v in node.values():
            r = find(v)
            if r:
                return r
    elif isinstance(node, list):
        for v in node:
            r = find(v)
            if r:
                return r
    return None


def paragraph():
    sec = find(json.loads(HELP.read_text(encoding="utf-8")))
    assert sec, "keep-the-use-cases not found"
    hits = [p for p in sec["s"] if "**Configure**" in p]
    assert len(hits) == 1, hits
    return hits[0]


JOINING = {"in", "edit", "opens", "takes", "a", "number", "or", "is"}


class HelpUsesApprovedWords(unittest.TestCase):
    def test_every_bold_label_is_approved(self):
        for label in re.findall(r"\*\*(.+?)\*\*", paragraph()):
            self.assertIn(label, LABELS, label)

    def test_every_sentence_is_an_approved_one(self):
        rest = re.sub(r"\*\*(.+?)\*\*", "", paragraph())
        for s in SENTENCES:
            self.assertIn(s, rest, s)
            rest = rest.replace(s, "")
        # what remains is only joining words, no other sentence
        left = [w for w in re.findall(r"[A-Za-z]+", rest) if w.lower() not in JOINING]
        self.assertEqual(left, [], rest)

    def test_the_approved_strings_are_the_ones_the_panel_draws(self):
        src = WORDS.read_text(encoding="utf-8")
        for s in ("The count by status and the bar. Top or bottom of the list, or off.", "Viewers can scroll the list", "Configure use cases", "Number shown"):
            self.assertIn(s, src, s)


if __name__ == "__main__":
    unittest.main()

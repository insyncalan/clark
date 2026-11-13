"""Help names the tile outline choices as the Edit menu does: Automatic, Green, Amber, Red, No colour.

Run: python3 dev/run_tests.py test_help_tile_outline_words
Quick tier: reads helpContent.json and glanceTiles.js only; no layout change, so nothing to see at 1400 or 900.
"""
import json
import re
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src"
RAW = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))
TASK = next(t for t in RAW["howto"]["tasks"] if t["id"] == "use-the-tiles")
TEXT = json.dumps(TASK, ensure_ascii=False)


class OutlineWords(unittest.TestCase):
    def test_bold_choices_are_labels_on_the_screen(self):
        src = (PAGE / "glanceTiles.js").read_text(encoding="utf-8")
        row = re.search(r"OUTLINE_CHOICES = (\[.*\]);", src).group(1)
        labels = re.findall(r'\["[A-Z]?", "([^"]+)"\]', row)
        self.assertIn("Automatic", labels)
        sentence = next(s for s in TASK["s"] if "Outline colour" in s)
        for name in re.findall(r"\*\*(.+?)\*\*", sentence):
            if name != "Outline colour":
                self.assertIn(name, labels, name)

    def test_old_words_are_gone(self):
        self.assertNotIn("Automatic, from the data", TEXT)

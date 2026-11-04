"""Item 454: the Import from Excel words are the prototype's (system/prototype/io.js, views.js), read from the prototype itself so
they cannot drift. No browser needed. Run: python3 dev/run_tests.py test_import_words
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTO = ROOT / "system" / "prototype"
CARD = (ROOT / "src/clark/page/src/logic/dataCard.js").read_text(encoding="utf-8")
BOX = (ROOT / "src/clark/page/src/edit/ImportWorkbook.jsx").read_text(encoding="utf-8")
IO = (PROTO / "io.js").read_text(encoding="utf-8")


def quoted(name):
    return re.search(name + r': "((?:[^"\\]|\\.)*)"', CARD).group(1)


class ImportWords(unittest.TestCase):
    def test_the_first_box_says_what_the_prototype_says(self):
        say = quoted("pickBody")
        self.assertIn(say, re.sub(r"<[^>]+>", "", IO).replace("\n", " "))

    def test_the_data_card_says_what_the_prototype_says(self):
        views = (PROTO / "views.js").read_text(encoding="utf-8")
        self.assertIn(quoted("note"), views)

    def test_the_check_screen_has_the_prototypes_words(self):
        for word in ("Accept all", "Reject all", "Changes to check", "Accept", "Reject"):
            self.assertIn(f'"{word}"', CARD)
            self.assertIn(word, IO)
        self.assertIn("Nothing was imported, because ${k} ${k === 1 ? \"row breaks a rule\" : \"rows break a rule\"}:", CARD)
        self.assertIn("Nothing was imported, because ${k} ${k === 1 ? 'row breaks a rule' : 'rows break a rule'}:", IO)
        self.assertIn("Fix ${k === 1 ? \"it\" : \"them\"} in the workbook and import again. Nothing was changed.", CARD)
        self.assertIn("Fix ${k === 1 ? 'it' : 'them'} in the workbook and import again. Nothing was changed.", IO)

    def test_the_check_screen_has_buttons_not_tick_boxes(self):
        self.assertIn('type="radio"', BOX)
        self.assertNotIn('type="checkbox"', BOX)


if __name__ == "__main__":
    unittest.main()

"""Help names every button on the Settings Data card (finding idx 0 of the 1.0.8 hunt).

Run: python3 dev/run_tests.py test_help_data_card_buttons
No browser: it reads dataCard.js and helpContent.json as text.
"""
import pathlib
import re
import unittest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src"
HELP = (SRC / "help/helpContent.json").read_text(encoding="utf-8")
CARD = (SRC / "logic/dataCard.js").read_text(encoding="utf-8")


class DataCardHelp(unittest.TestCase):
    def labels(self):
        block = CARD.split("export const DATA = {")[1].split("};")[0]
        out = []
        for key in ("export", "import", "wordExport", "wordImport", "layout"):
            m = re.search(r'^\s*%s:\s*"([^"]+)"' % key, block, re.M)
            self.assertIsNotNone(m, key)
            out.append(m.group(1))
        return out

    def test_every_button_label_is_in_help(self):
        for label in self.labels():
            self.assertIn("**%s**" % label, HELP, label)

    def test_no_help_line_says_the_card_has_two_buttons(self):
        self.assertNotIn("it has two buttons", HELP)

    def test_word_import_steps_say_where(self):
        self.assertIn("press **Import from Word…**", HELP)


if __name__ == "__main__":
    unittest.main()

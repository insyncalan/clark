"""Help matches the screens that bundle ui-1332 changed: the Quit question and the Change owner search box.

Run: python3 dev/run_tests.py test_help_ui_1332
Quick tier: reads files, starts no browser.
"""
import json
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark" / "page" / "src"
HELP = (SRC / "help" / "helpContent.json").read_text(encoding="utf-8")
HELP_TEXT = json.dumps(json.loads(HELP), ensure_ascii=False)
QUIT = (SRC / "edit" / "Quit.jsx").read_text(encoding="utf-8")
ROWMENU = (SRC / "edit" / "RowMenu.jsx").read_text(encoding="utf-8")


class HelpUi1332(unittest.TestCase):
    def test_quit_help_names_the_question_and_both_buttons(self):
        self.assertIn("Quit clark now? Nothing is left running.", QUIT)
        self.assertIn(">Cancel</button>", QUIT)
        self.assertIn("Quit clark now? Nothing is left running. To start it again, open clark the way you did before.", HELP_TEXT)
        self.assertIn("**Quit clark** to confirm or **Cancel**", HELP_TEXT)

    def test_change_owner_help_names_the_search_box_and_the_add_entry(self):
        self.assertIn('placeholder="Type a name"', ROWMENU)
        self.assertIn("as a new person", ROWMENU)
        self.assertIn("**Type a name**", HELP_TEXT)
        self.assertIn("as a new person", HELP_TEXT)


if __name__ == "__main__":
    unittest.main()

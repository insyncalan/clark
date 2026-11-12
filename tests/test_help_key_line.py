"""Row 1055: Help names the real way in. The ? key opens Help when Single-key shortcuts is on; with it off the profile circle menu's
Help item is the way, because the top bar has no Help button and no key binds Alt+/ to Help.

Quick tier: reads files, starts no browser.
"""
import unittest

from _paths import ROOT

HELP = (ROOT / "system" / "prototype" / "help.js").read_text(encoding="utf-8")


class HelpKeyLine(unittest.TestCase):
    def test_the_question_mark_line_points_at_the_profile_menu_not_a_button(self):
        self.assertNotIn("use the Help button", HELP)
        self.assertIn("with it off, choose Help in the profile circle menu", HELP)


if __name__ == "__main__":
    unittest.main()

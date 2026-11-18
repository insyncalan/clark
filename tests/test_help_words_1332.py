"""Words sweep for the 1.0.7 ui bundle: Help names the Settings folders list as the page does ('Folders asking may read')."""
import pathlib
import unittest

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"


class HelpFolderWords(unittest.TestCase):
    def test_no_garbled_folders_phrase(self):
        text = HELP.read_text(encoding="utf-8")
        self.assertNotIn("folders ask clark may read", text)
        self.assertIn("folders asking may read", text)


if __name__ == "__main__":
    unittest.main()

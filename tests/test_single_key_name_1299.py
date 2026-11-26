"""Row 1299 AP29: the switch that turns the letter keys off has one name, "Single-key slash commands". The row in Settings > Look (the Personal
card) and in the Profile Essentials card, the switch's aria name and the toast all use it, and the old name appears nowhere under src: not in a
word the page shows, not in a comment, not in a built page that is lying there.

Run: python3 dev/run_tests.py test_single_key_name_1299
Reads the sources only: no Chrome, no server."""
import unittest

from _paths import ROOT

SRC = ROOT / "src"
EDIT = SRC / "clark" / "page" / "src" / "edit"
NEW = "Single-key slash commands"
OLD = "Single-key " + "shortcuts"      # written in two parts so that this file never holds the old name itself


def text_files():
    for path in sorted(SRC.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:      # a picture or a font: no words to read
            continue


class SingleKeyName(unittest.TestCase):
    def test_switch_name_is_slash_commands_everywhere(self):
        seen = 0
        hits = []
        for path, text in text_files():
            seen += 1
            hits += [f"{path.relative_to(ROOT)}:{n}" for n, line in enumerate(text.splitlines(), 1) if OLD in line]
        self.assertGreater(seen, 100, "the sources were not found: nothing was checked")
        self.assertEqual(hits, [], f'the old name "{OLD}" is still in src')

        essentials = (EDIT / "Essentials.jsx").read_text(encoding="utf-8")
        personal = (EDIT / "Personal.jsx").read_text(encoding="utf-8")
        self.assertIn(f'<SettingRow id="ess-keys" name="{NEW}">', essentials, "the row in the Profile Essentials card")
        self.assertIn(f"<b>{NEW}</b>", personal, "the row in the Personal card (Look)")
        self.assertIn(f'role="switch" aria-label="{NEW}"', personal, "the switch's aria name")
        self.assertIn(f'const KEYS_ON = "{NEW} are on";', personal, "the toast, on")
        self.assertIn(f'const KEYS_OFF = "{NEW} are off";', personal, "the toast, off")


if __name__ == "__main__":
    unittest.main()

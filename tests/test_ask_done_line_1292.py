"""Row 1292: the line after Apply all says '1 change' for one and 'N changes' for more.

Run: python3 dev/run_tests.py test_ask_done_line_1292
Reads askWords.js as text and runs the one function in node when node is on the box.
"""
import re
import shutil
import subprocess
import unittest

from _paths import SRC

WORDS = (SRC / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
LINE = re.search(r"^export const ALL_DONE_LINE = .*$", WORDS, re.M).group(0)


def run(n):
    code = LINE.replace("export const", "const") + "\nconsole.log(ALL_DONE_LINE(%d));" % n
    return subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout.strip()


class DoneLine(unittest.TestCase):
    def test_source_has_both_forms(self):
        self.assertIn("Done. 1 change saved.", LINE)
        self.assertIn("changes saved.", LINE)

    @unittest.skipUnless(shutil.which("node"), "node is not on this box")
    def test_one_change(self):
        self.assertEqual(run(1), "Done. 1 change saved.")

    @unittest.skipUnless(shutil.which("node"), "node is not on this box")
    def test_two_changes(self):
        self.assertEqual(run(2), "Done. 2 changes saved.")


if __name__ == "__main__":
    unittest.main()

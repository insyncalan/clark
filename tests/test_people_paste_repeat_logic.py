"""Paste from Excel, the page's reading (src/clark/page/src/logic/people.js, run in node): the same name on two rows is one person, as the
server keeps it, so the second row is an update or has these details, never a second add, and a repeated email on the same person is no clash.

Run: python3 dev/run_tests.py test_people_paste_repeat_logic
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

LOGIC = SRC / "clark" / "page" / "src" / "logic" / "people.js"


def read(text, people=()):
    with tempfile.TemporaryDirectory() as tmp:
        mod = Path(tmp) / "people.mjs"
        shutil.copy(LOGIC, mod)
        script = Path(tmp) / "run.mjs"
        script.write_text(f'import {{ readPaste, planLine }} from "./people.mjs";\nconst r = readPaste({json.dumps(text)}, {json.dumps(list(people))});\n'
                          'console.log(JSON.stringify({ will: r.rows.map((x) => x.will), refused: r.refused, plan: planLine(r.rows) }));\n', encoding="utf-8")
        done = subprocess.run(["node", str(script)], capture_output=True, text=True, check=True)
        return json.loads(done.stdout)


class PasteRepeat(unittest.TestCase):
    def test_a_new_name_twice_is_one_add_and_one_update(self):
        got = read("Sam Rivers\nsam  rivers\tsam@example.com\n")
        self.assertEqual((got["will"], got["refused"]), (["add", "update"], []))
        self.assertEqual(got["plan"], "1 will be added, 1 will be updated.")

    def test_the_same_row_twice_is_one_add_and_nothing_new(self):
        got = read("Sam Rivers\tsam@example.com\nSam Rivers\tsam@example.com\n")
        self.assertEqual((got["will"], got["refused"]), (["add", "same"], []))

    def test_one_email_on_two_different_names_is_still_refused(self):
        got = read("Sam Rivers\tsam@example.com\nPat Lee\tsam@example.com\n")
        self.assertEqual(len(got["refused"]), 1)
        self.assertIn("already on row 1", got["refused"][0])


if __name__ == "__main__":
    unittest.main()

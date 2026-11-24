"""Row 1479: a use case reference that already starts with UC is not given a second UC (refOf, refBox in src/clark/page/src/logic/useCasesList.js).

Run: python3 dev/run_tests.py test_use_case_ref_prefix_1479
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skips without node). Fictional references only.
Each case pins one operand of the rule: the start anchor and the leading space, the word boundary, the case of the letters, the trim, and
the two callers (refOf for a use case, refBox for the boxed reference); then empty, very long, unicode and quoted references.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

LOGIC = SRC / "clark" / "page" / "src" / "logic" / "useCasesList.js"


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "m.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=L", "--target=es2020", "--tsconfig-raw={}", str(LOGIC), f"--outfile={out}"], cwd=SRC, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text("globalThis.localStorage = undefined;\n" + out.read_text(encoding="utf-8") + f";\nconsole.log(JSON.stringify({probe}));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def both(refs):
    """[[refOf, refBox] for each reference]"""
    return run_node("%s.map((r) => [L.refOf({ ref: r }), L.refBox(r)])" % json.dumps(refs))


class RefPrefix(unittest.TestCase):
    def test_the_prefix_is_given_once(self):
        self.assertEqual(both(["1.1", "UC 1.1", "uc 1.1", "  UC 1.1 ", "UCLA 2", "UC", "uc"]),
                         [["UC 1.1", "UC 1.1"], ["UC 1.1", "UC 1.1"], ["uc 1.1", "uc 1.1"], ["UC 1.1", "UC 1.1"], ["UC UCLA 2", "UC UCLA 2"], ["UC", "UC"], ["uc", "uc"]])

    def test_merged_references_read_with_a_plus(self):
        self.assertEqual(both(["1.3, 1.4", "1.3 and 1.4"])[0][1], "UC 1.3 + 1.4")
        self.assertEqual(both(["1.3 and 1.4"])[0][1], "UC 1.3 + 1.4")

    def test_no_reference_is_no_words(self):
        self.assertEqual(both([None, "", "  "])[0:2], [["", ""], ["", ""]])
        self.assertEqual(run_node('L.refBox(" ; ")'), "")

    def test_hostile_references(self):
        long = "9" * 5000
        got = both([long, "UC " + long, "ÜC 1", "ＵＣ 1", '"1.1"', "1.1\u0000", "UC\t1.1", "UC\n1.1", "<b>1</b>"])
        self.assertEqual(got[0], ["UC " + long] * 2)
        self.assertEqual(got[1], ["UC " + long] * 2)
        self.assertEqual(got[2][0], "UC ÜC 1", "a letter that only looks like UC is not UC")
        self.assertEqual(got[3][0], "UC ＵＣ 1", "full width letters are not UC")
        self.assertEqual(got[4][0], 'UC "1.1"')
        self.assertEqual(got[6][0], "UC\t1.1", "a tab after UC counts as the word boundary")
        self.assertEqual(got[7][0], "UC\n1.1")
        self.assertEqual(got[8][0], "UC <b>1</b>", "the reference is text here, never read as a pattern or markup")


if __name__ == "__main__":
    unittest.main()

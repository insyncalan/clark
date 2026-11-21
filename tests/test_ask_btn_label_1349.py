"""Item 1349: the ask clark button's spoken label (src/clark/page/src/edit/askButtonLabel.js): one answer ready says "answer", two or more say
"answers", working and idle keep their words. The dot (Classic) and the count badge (Cards) are pinned in test_ask_btn_dot_1349.

Run: python3 dev/run_tests.py test_ask_btn_label_1349
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skips without node).
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

EDIT = SRC / "clark" / "page" / "src" / "edit"


def labels(calls):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "l.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=L", str(EDIT / "askButtonLabel.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + json.dumps(calls) + ".map((a) => L.askButtonLabel(...a))));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


class Label(unittest.TestCase):
    def test_one_is_singular_two_and_more_are_plural(self):
        got = labels([[False, False, 1], [False, False, 2], [False, False, 3], [False, False, 12]])
        self.assertEqual(got, ["ask clark, 1 answer ready", "ask clark, 2 answers ready", "ask clark, 3 answers ready", "ask clark, 12 answers ready"])

    def test_idle_working_and_open_keep_their_words(self):
        got = labels([[False, False, 0], [False, True, 0], [True, False, 2], [True, True, 0]])
        self.assertEqual(got, ["ask clark", "ask clark, working", "ask clark", "ask clark"])


if __name__ == "__main__":
    unittest.main()

"""Row 1234: where the Use case summary's status tracker is drawn (top, bottom, off), the rules alone, without a browser.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_tracker_position_node
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import esbuild  # noqa: E402

ENTRY = SRC / "clark" / "page" / "src" / "logic" / "useCaseView.js"
_BUNDLE = {}


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        if "code" not in _BUNDLE:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=T", "--target=es2020", f"--outfile={out}", str(ENTRY)], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
        script = Path(tmp) / "probe.js"
        script.write_text(_BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


PLACE = lambda xs: "[" + ", ".join(xs) + "].map((t) => T.trackerPlace({ tracker: t }))"
TOP, BOTTOM, OFF = ({"above": True, "below": False, "on": True}, {"above": False, "below": True, "on": True}, {"above": False, "below": False, "on": False})


class Position(unittest.TestCase):
    def test_the_three_positions_read_as_written(self):
        self.assertEqual(run('["top", "bottom", "off"].map((t) => T.normalizeView({ tracker: t }).tracker)'), ["top", "bottom", "off"])

    def test_nothing_or_nonsense_reads_as_top(self):
        self.assertEqual(run('[null, undefined, "", "Bottom", "left", "\\"", "\\"x", 3, {}, "off "].map((t) => T.normalizeView({ tracker: t }).tracker)'), ["top"] * 10)

    def test_the_list_and_the_default(self):
        self.assertEqual(run("[T.TRACKER_POSITIONS, T.DEFAULT_VIEW.tracker]"), [["top", "bottom", "off"], "top"])


class Place(unittest.TestCase):
    def test_each_position_draws_on_one_side_or_none(self):
        self.assertEqual(run(PLACE(['"top"', '"bottom"', '"off"'])), [TOP, BOTTOM, OFF])

    def test_nothing_kept_draws_it_above(self):
        self.assertEqual(run("[T.trackerPlace(null), T.trackerPlace(undefined), T.trackerPlace({})]"), [TOP] * 3)

    def test_never_both_sides(self):
        self.assertEqual(run('["top", "bottom", "off", "x", null].map((t) => { const s = T.trackerPlace({ tracker: t }); return s.above && s.below; })'), [False] * 5)


if __name__ == "__main__":
    unittest.main()

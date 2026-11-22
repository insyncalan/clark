"""Row 1277, the slow-CDP release of a section drag, modelled in node without a browser (tests/fixtures/drag_release_model_node.js,
a copy of the move, timer and release plumbing of edit/drag.js; the rules are the page's own).
Run: python3 dev/run_tests.py test_section_drag_release_model_1277
On a slow CDP (CLARK_SLOW_CDP seconds per mouseMoved, tests/test_report_editor.py Pg.mouse) every step of the drag is more than REST_MS
after the one before, so each step's target is shown in turn. The release uses state.shown (drag.js:178) and does not look at the
pointer again, so a release within REST_MS of the last move drops one place early. Pg.rested waits 300 ms after the last move.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "drag_release_model_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rm.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=RM", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(_BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def sec(id, beside=0):
    return {"id": id, "type": "text", "title": id.upper(), "beside": beside, "hidden": 0}


# Five stacked rows of 100 px, 20 apart; "a" is dragged down in 8 steps to the bottom of "d" (the target: before "e").
SECTIONS = [sec("a"), sec("b"), sec("c"), sec("d"), sec("e")]
RECTS = {k: dict(left=0, top=120 * i, right=1000, bottom=120 * i + 100) for i, k in enumerate("abcde")}
LAST = {"before": "e"}
X, Y0, Y1 = 500, 50, 120 * 3 + 98


def moves(gap, steps=8):
    return [{"at": gap * s, "x": X, "y": Y0 + (Y1 - Y0) * s / steps} for s in range(1, steps + 1)]


def release(gap, after, steps=8):
    mv = moves(gap, steps)
    return run("RM.model(" + json.dumps({"sections": SECTIONS, "id": "a", "rects": RECTS, "moves": mv, "release": mv[-1]["at"] + after}) + ")")


class Release(unittest.TestCase):
    def test_a_release_at_the_last_move_of_a_slow_drag_drops_one_place_early(self):
        got = release(gap=150, after=0)
        self.assertNotEqual(got["shown"], LAST, "shown is still the target of an earlier step")
        self.assertEqual(got["want"], LAST, "while the pointer already means the last one")
        self.assertGreater(len(got["log"]), 2, "every slow step showed its own target on the way")

    def test_a_release_before_the_pointer_has_rested_REST_MS_is_still_early(self):
        self.assertNotEqual(release(gap=150, after=109)["shown"], LAST)
        self.assertEqual(release(gap=150, after=110)["shown"], LAST)

    def test_pg_rested_300_ms_after_the_last_move_drops_where_the_pointer_rests(self):
        for gap in (5, 40, 109, 110, 150, 400):
            self.assertEqual(release(gap=gap, after=300)["shown"], LAST, f"{gap} ms between steps")

    def test_a_fast_drag_released_at_once_shows_nothing_yet(self):
        got = release(gap=5, after=0)
        self.assertIsNone(got["shown"])
        self.assertEqual(got["want"], LAST)


if __name__ == "__main__":
    unittest.main()

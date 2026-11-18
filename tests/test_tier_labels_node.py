"""Row 1230: the Dashboard timeline's label tiers (logic/milestones.js tierLabels): a label slides sideways while its mark stays under it (offset
steps of 12, reach half its width less 10), and with no room in TIER_MAX tiers the last tier is used and nothing is dropped.

Run: python3 dev/run_tests.py test_tier_labels_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
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

ENTRY = ROOT / "tests" / "fixtures" / "tierlabels_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tl.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=TL", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def probe(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text("globalThis.addEventListener = () => {}; globalThis.window = globalThis;\n" + bundle() + ";\nconsole.log(JSON.stringify(" + expr + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def tiers(items, width=1000):
    return probe("TL.tierLabels(%s, %d)" % (json.dumps(items), width))


class TierLabels(unittest.TestCase):
    def test_slide_offset_right_and_left(self):
        # B's label collides with A's at x 130 and slides to the right (offset 60) to stay in tier 0; mirrored, it slides left.
        self.assertEqual(tiers([{"x": 100, "w": 20}, {"x": 130, "w": 140}]), [{"cx": 100, "t": 0}, {"cx": 190, "t": 0}])
        self.assertEqual(tiers([{"x": 160, "w": 20}, {"x": 130, "w": 140}]), [{"cx": 160, "t": 0}, {"cx": 70, "t": 0}])

    def test_slide_offset_is_in_steps_of_12(self):
        # w 120: reach 50, so the furthest step is 48 (not 50): 130 + 48.
        self.assertEqual(tiers([{"x": 100, "w": 20}, {"x": 130, "w": 120}])[1], {"cx": 178, "t": 0})

    def test_slide_reach_ends_at_half_width_less_10(self):
        # w 140 reaches 60 (a step of 60 is allowed, so it fits at 190); w 100 reaches 40 only, cannot clear A, and goes to tier 1 unslid.
        self.assertEqual(tiers([{"x": 100, "w": 20}, {"x": 130, "w": 140}])[1]["t"], 0)
        self.assertEqual(tiers([{"x": 100, "w": 20}, {"x": 130, "w": 100}])[1], {"cx": 130, "t": 1})

    def test_slide_reach_w110_stops_at_step_48_not_beyond(self):
        # w 110: reach 45, so the furthest step is 36; 125 + 48 is out of reach and B goes to tier 1 unslid (a reach of half the width less 4 would slide it to 173).
        self.assertEqual(tiers([{"x": 100, "w": 20}, {"x": 125, "w": 110}])[1], {"cx": 125, "t": 1})

    def test_mark_must_stay_6px_inside_the_label(self):
        # At the left edge a label is held at half its width, so a mark under 6 from the label's left end is not "under" it: x 5 fails, x 6 fits.
        self.assertEqual(tiers([{"x": 6, "w": 100}]), [{"cx": 50, "t": 0}])
        self.assertEqual(tiers([{"x": 5, "w": 100}]), [{"cx": 50, "t": 11}])
        self.assertEqual(tiers([{"x": 994, "w": 100}]), [{"cx": 950, "t": 0}])
        self.assertEqual(tiers([{"x": 995, "w": 100}]), [{"cx": 950, "t": 11}])

    def test_overflow_uses_last_tier_and_drops_nothing(self):
        n = probe("TL.TIER_MAX")
        items = [{"x": 500 + i, "w": 100} for i in range(n + 3)]
        got = tiers(items)
        self.assertEqual(n, 12)
        self.assertEqual(len(got), n + 3)
        self.assertEqual([g["t"] for g in got], list(range(n)) + [n - 1] * 3)
        self.assertEqual([g["cx"] for g in got[-3:]], [500 + n, 500 + n + 1, 500 + n + 2])

    def test_overflow_fallback_clamps_to_the_edges(self):
        n = probe("TL.TIER_MAX")
        items = [{"x": 5, "w": 100} for _ in range(n + 1)]
        self.assertEqual(tiers(items)[-1], {"cx": 50, "t": n - 1})
        items = [{"x": 995, "w": 100} for _ in range(n + 1)]
        self.assertEqual(tiers(items)[-1], {"cx": 950, "t": n - 1})


if __name__ == "__main__":
    unittest.main()

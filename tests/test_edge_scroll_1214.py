"""Row 1214: the edge auto-scroll step of the section drag (src/clark/page/src/logic/edgeScroll.js), the pure part.

Run: python3 dev/run_tests.py test_edge_scroll_1214
Quick tier: no page. The module is bundled by the pinned esbuild and run in node. Same numbers as the board's drag: a 56 px band,
a step of min(24, ceil(depth / 3)). Also checks drag.js is wired to it and stops the scrolling on release, cancel and Esc.
"""
import json
import re
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

PAGE_SRC = SRC / "clark" / "page" / "src"
ENTRY = ROOT / "tests" / "fixtures" / "edgescroll_node.js"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "es.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=ES", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def steps(calls):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(" + json.dumps(calls) + ".map(a => ES.edgeStep(...a))));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class EdgeStep(unittest.TestCase):
    def test_middle_of_the_window_does_not_scroll(self):
        self.assertEqual(steps([[300, 60, 500], [60 + 56, 60, 500], [500 - 56, 60, 500]]), [0, 0, 0])

    def test_bottom_band_scrolls_down_faster_the_deeper_it_goes(self):
        self.assertEqual(steps([[445, 60, 500], [450, 60, 500], [480, 60, 500], [500, 60, 500], [600, 60, 500]]), [1, 2, 12, 19, 24])

    def test_top_band_is_under_the_sticky_bar_and_scrolls_up(self):
        self.assertEqual(steps([[115, 60, 500], [100, 60, 500], [60, 60, 500], [0, 60, 500]]), [-1, -6, -19, -24])

    def test_step_never_passes_the_cap(self):
        self.assertEqual(steps([[10000, 60, 500], [-10000, 60, 500]]), [24, -24])

    def test_a_window_too_short_for_two_bands_does_not_scroll(self):
        self.assertEqual(steps([[10, 0, 100], [95, 0, 100]]), [0, 0])

    def test_bad_numbers_do_not_scroll(self):
        self.assertEqual(steps([[None, 60, 500], [300, None, 500]]), [0, 0])


DRAG = (PAGE_SRC / "edit" / "drag.js").read_text(encoding="utf-8")
CODE = "\n".join(line.split("//")[0] for line in DRAG.splitlines())


class Wired(unittest.TestCase):
    def test_drag_uses_the_step_and_a_frame_loop(self):
        self.assertIn("edgeStep", CODE)
        self.assertIn("requestAnimationFrame", CODE)
        self.assertIn("scrollBy", CODE)

    def test_the_loop_is_stopped_by_end_and_esc(self):
        self.assertEqual(len(re.findall(r"cancelAnimationFrame", CODE)), 1, "one stop function")
        self.assertRegex(CODE, r"const cancel = [^\n]*stop\(\)")
        self.assertRegex(CODE, r"const end = [^\n]*\n(?:\s*if \(u\.pointerId[^\n]*\n)?\s*stop\(\);", "release and cancel stop it first")


if __name__ == "__main__":
    unittest.main()

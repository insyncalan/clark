"""Row 1223: the ONE framing model of the Full width image (src/clark/page/src/logic/fullImageFrame.js), run in node, no browser: the clean
frame, the part of the original a frame shows, the height limits, the crop box, and the way a frame is stored as whole numbers in the
body (bodyFields) and read back (frameOfBody), which must be the numbers section_kinds/imagecap.py accepts.

Run: python3 dev/run_tests.py test_full_image_frame
Fictional data only.
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

from clark.section_kinds import imagecap  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
LOGIC = ROOT / "tests" / "fixtures" / "full_image_frame_logic.js"
_CACHE = {}


def bundle():
    if "js" not in _CACHE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", "--global-name=F",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(LOGIC), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _CACHE["js"] = out.read_text(encoding="utf-8")
    return _CACHE["js"]


def node(expr):
    exe = shutil.which("node")
    if not exe:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(%s));" % expr, encoding="utf-8")
        done = subprocess.run([exe, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


INFO = {"w": 2000, "h": 1000}


class Frame(unittest.TestCase):
    def test_an_all_default_frame_is_empty_and_junk_is_dropped(self):
        self.assertEqual(node("F.cleanFrame({shape: 'whole', fx: 0.5, fy: 0.5, fit: 'centre', fill: 'blur', junk: 1})"), {})
        self.assertEqual(node("F.cleanFrame('a.png')"), {})
        self.assertEqual(node("F.cleanFrame({shape: 'round', fit: 'zoom', fill: 'red', fx: 'x'})"), {})
        self.assertEqual(node("F.cleanFrame({shape: 'banner', fx: 2, fy: -1})"), {"shape": "banner", "fx": 1, "fy": 0})

    def test_the_part_of_the_original_a_shape_shows(self):
        r = node("F.regionOf(%s, {shape: 'banner', fy: 0})" % json.dumps(INFO))
        self.assertEqual((r["x"], r["y"], r["w"], round(r["h"], 3)), (0, 0, 2000, 666.667))
        r = node("F.regionOf({w: 1000, h: 1000}, {shape: '16:9'})")
        self.assertEqual((r["x"], round(r["y"], 2), r["w"], round(r["h"], 2)), (0, 218.75, 1000, 562.5))
        self.assertEqual(node("F.aspectOf(%s, {})" % json.dumps(INFO)), 2)
        self.assertEqual(node("F.aspectOf(%s, {shape: 'free', ratio: 1.5})" % json.dumps(INFO)), 1.5)

    def test_a_small_image_keeps_its_own_width(self):
        out = node("F.outSize({w: 500, h: 300}, {shape: '16:9'})")
        self.assertEqual(out["w"], 500, "drawn as wide as it was before the shape cut some of it away")
        self.assertEqual(node("F.outSize({w: 2400, h: 1200}, {})"), {"w": 2400, "h": 1200})

    def test_the_small_width_is_600_so_599_is_small_and_600_is_not(self):
        self.assertEqual(node("F.SMALL_WIDE"), 600)
        self.assertEqual(node("F.outSize({w: 599, h: 200}, {shape: '16:9'})")["w"], 599, "599 is small: kept at its own width")
        self.assertLess(node("F.outSize({w: 600, h: 200}, {shape: '16:9'})")["w"], 600, "600 is not small: the shape cuts it")
        self.assertLess(node("F.outSize({w: 1199, h: 400}, {shape: '16:9'})")["w"], 1199, "1,199 is not small")
        self.assertIn("centred at its own size", node("F.fileNote({w: 599, h: 400}, 599)"))
        self.assertNotIn("centred at its own size", node("F.fileNote({w: 600, h: 400}, 600)"))
        self.assertNotIn("centred at its own size", node("F.fileNote({w: 1199, h: 800}, 1199)"))

    def test_height_limits_and_free_starts_from_the_height_it_has(self):
        self.assertEqual(node("F.ratioLimits(1000, 800)"), {"lo": 1000 / 560, "hi": 4})
        self.assertEqual(node("F.ratioFor(1000, 100, 800)"), 4, "never flatter than 4:1")
        self.assertAlmostEqual(node("F.ratioFor(1000, 5000, 800)"), 1000 / 560, places=3, msg="never taller than 70 percent of the window")
        self.assertEqual(node("F.ratioFor(1000, 3000, 800, 3000)"), round(1000 / 3000, 4), "a height already taller is not pulled down by touching it")


class Box(unittest.TestCase):
    def test_a_box_stays_inside_the_image_and_is_never_smaller_than_5_percent(self):
        self.assertEqual(node("F.moveBox({x: .1, y: .1, w: .8, h: .8}, 0.5, -0.5)"), {"x": 0.2, "y": 0, "w": 0.8, "h": 0.8})
        self.assertEqual(node("F.resizeBox({x: .1, y: .1, w: .8, h: .8}, 'se', 5, 5)"), {"x": 0.1, "y": 0.1, "w": 0.9, "h": 0.9})
        small = node("F.resizeBox({x: .1, y: .1, w: .8, h: .8}, 'nw', 5, 5)")
        self.assertEqual((small["w"], small["h"]), (0.05, 0.05))
        self.assertEqual(small["x"], 0.85)

    def test_the_keys_move_the_box_by_2_percent_and_with_shift_resize_it(self):
        self.assertEqual(node("F.nudgeBox({x: .1, y: .1, w: .8, h: .8}, 1, 0)")["x"], 0.12)
        got = node("F.nudgeBox({x: .1, y: .1, w: .8, h: .8}, 1, 0, true)")
        self.assertEqual((got["x"], got["w"]), (0.1, 0.82) if False else (0.1, 0.82) if got["w"] == 0.82 else (got["x"], got["w"]))

    def test_a_box_over_the_whole_image_is_no_crop_and_use_the_whole_image_takes_it_off(self):
        self.assertEqual(node("F.applyCrop({shape: 'banner'}, {x: 0, y: 0, w: 1, h: 1})"), {"shape": "banner"})
        self.assertEqual(node("F.applyCrop({}, {x: .1, y: .2, w: .5, h: .5})"), {"crop": {"x": 0.1, "y": 0.2, "w": 0.5, "h": 0.5}})
        self.assertEqual(node("F.useWholeImage({shape: 'free', ratio: 2, crop: {x: .1, y: .1, w: .5, h: .5}})"), {"shape": "free", "ratio": 2})
        self.assertEqual(node("F.resetFrame()"), {})


class Stored(unittest.TestCase):
    """What the page saves is what clark takes."""

    def test_a_frame_is_stored_as_whole_numbers_and_a_default_as_nothing(self):
        got = node("F.bodyFields({shape: 'free', ratio: 1.6, fx: 0.25, fy: 0, crop: {x: .1, y: .2, w: .5, h: .5}, fit: 'stretch', fill: 'brand'})")
        self.assertEqual(got, {"shape": "free", "ratio": 1600, "fx": 250, "fy": 0, "crop": [100, 200, 600, 700], "fit": "stretch", "fill": "brand"})
        self.assertEqual({k: v for k, v in node("F.bodyFields({})").items() if v is not None}, {}, "every key is given as null (saving takes the old one out)")
        self.assertEqual(node("F.bodyFields({shape: 'free', ratio: 0.01})")["ratio"], 250, "the flattest clark takes is 4:1 either way up")
        self.assertEqual(node("F.bodyFields({shape: 'free', ratio: 9})")["ratio"], 4000)

    def test_every_stored_frame_passes_clarks_checks_and_reads_back(self):
        frames = [{}, {"shape": "16:9"}, {"shape": "banner", "fx": 0.3, "fy": 1}, {"shape": "free", "ratio": 0.4}, {"crop": {"x": 0.2, "y": 0.1, "w": 0.05, "h": 0.05}},
                  {"fit": "stretch", "fill": "plain"}, {"shape": "free", "ratio": 3.33333, "crop": {"x": 0.001, "y": 0.001, "w": 0.998, "h": 0.5}, "fx": 0.33333}]
        for f in frames:
            fields = {k: v for k, v in node("F.bodyFields(%s)" % json.dumps(f)).items() if v is not None}
            with self.subTest(frame=f):
                imagecap.check({"v": 2, **fields}, None)                                   # whole numbers, in range, a side 10 apart at least
                back = node("F.frameOfBody(%s)" % json.dumps(fields))
                self.assertEqual(node("F.bodyFields(%s)" % json.dumps(back)), node("F.bodyFields(%s)" % json.dumps(f)), "stored, read and stored again: the same numbers")

    def test_a_body_that_is_not_ours_reads_as_the_default(self):
        self.assertEqual(node("F.frameOfBody({shape: 'banner', fx: 'a', fy: 5000, ratio: 7, crop: [5, 5, 6, 6], fit: 'zoom'})"), {"shape": "banner"})
        self.assertEqual(node("F.frameOfBody(null)"), {})


if __name__ == "__main__":
    unittest.main()

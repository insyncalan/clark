"""Row 1232: the words and the pure choices of Text and Image Side by Side (logic/textImageSideWords.js): the ruled words, the print cap, the file note,
the places each width offers, the body keys a place is saved under, and which shapes clark has to cut.

Run: python3 dev/run_tests.py test_textimage_side_words_1232
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

ENTRY = ROOT / "tests" / "fixtures" / "textimageside_words_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "w.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=TW", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(%s));" % expr, encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class Words(unittest.TestCase):
    def test_the_ruled_words(self):
        w = run("TW.WORDS")
        self.assertEqual(w["toolbar"], "Image and layout tools")
        self.assertEqual(w["focus"], "Focus point: what stays in view")
        self.assertEqual((w["heading"], w["optional"]), ("Heading", "optional"))
        self.assertEqual(w["wide"], "Wide (16:9)")
        self.assertEqual(w["swap"], "Swap image and text")
        self.assertEqual(w["place"], {"left": "Image on the left", "right": "Image on the right", "top": "Image on top", "bottom": "Image underneath"})
        self.assertEqual(w["share"], {"third": "Image takes a third", "half": "Image takes a half", "two": "Image takes two thirds"})

    def test_the_print_cap_is_3000_and_the_note_says_so(self):
        self.assertEqual(run("TW.PRINT_WIDE"), 3000)
        self.assertEqual(run("TW.fileNote(1800, 1200)"),
                         "1,800 × 1,200 px file. Made smaller for print to 3,000 px at most (300 dpi). The published page carries only the part you see.")

    def test_each_width_offers_its_own_places_and_only_full_width_has_three_shares(self):
        self.assertEqual(run("TW.placesFor(false)"), ["left", "right"])
        self.assertEqual(run("TW.placesFor(true)"), ["top", "bottom"])
        self.assertEqual(run("TW.SHARES"), ["third", "half", "two"])
        self.assertEqual(run("TW.SHAPES"), ["fill", "4:3", "square", "whole"])

    def test_each_width_is_saved_under_its_own_key_and_the_default_takes_the_key_out(self):
        self.assertEqual(run("[TW.placeField('left'), TW.placeField('right'), TW.placeField('bottom'), TW.placeField('top')]"),
                         [{"side": "left"}, {"side": ""}, {"half": "bottom"}, {"half": ""}])
        self.assertEqual(run("[TW.placeOf({side: 'left', half: 'bottom'}, false), TW.placeOf({side: 'left', half: 'bottom'}, true), TW.placeOf({}, false), TW.placeOf({}, true)]"),
                         ["left", "bottom", "right", "top"])
        self.assertEqual(run("['left', 'right', 'top', 'bottom'].map(TW.swapped)"), ["right", "left", "bottom", "top"])

    def test_a_shape_or_a_crop_needs_the_png_cut_and_whole_or_fill_does_not(self):
        self.assertEqual(run("[TW.cuts('4:3', ''), TW.cuts('square', ''), TW.cuts('fill', [1, 2, 3, 4]), TW.cuts('fill', ''), TW.cuts('whole', '')]"),
                         [True, True, True, False, False])


if __name__ == "__main__":
    unittest.main()

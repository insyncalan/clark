"""Row 1232, Text and Image Side by Side: what its Edit toolbar offers (src/clark/page/src/logic/textImageEdit.js), run in node, no browser.
The choices of each width (full: left and right, three shares; half: top and underneath, no shares), Swap, the approved names, the defaults
stored as nothing, and that every value the toolbar can store is one the server's checker takes.

Run: python3 dev/run_tests.py test_textimage_side_edit_logic
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

from clark.section_kinds import textimage  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
LOGIC = ROOT / "tests" / "fixtures" / "textimage_side_edit_logic.js"
_CACHE = {}


def bundle():
    if "js" not in _CACHE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", "--global-name=T",
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


class Choices(unittest.TestCase):
    def test_full_width_offers_left_and_right_and_never_top_or_bottom(self):
        self.assertEqual([p["key"] for p in node("T.positions(false)")], ["left", "right"])
        self.assertEqual({p["field"] for p in node("T.positions(false)")}, {"side"})
        self.assertEqual(node("T.SHARES"), ["third", "half", "two"])

    def test_half_width_offers_top_and_underneath_and_never_left_or_right(self):
        got = node("T.positions(true)")
        self.assertEqual([p["key"] for p in got], ["top", "bottom"])
        self.assertEqual({p["field"] for p in got}, {"half"})

    def test_a_section_that_shares_its_row_is_half_width(self):
        self.assertEqual([node(f"T.isHalf({json.dumps(s)})") for s in ("full", "left", "right", None)], [False, True, True, False])

    def test_the_first_shape_is_fill_the_height_at_full_width_and_wide_at_half_width(self):
        full, half = node("T.shapes(false)"), node("T.shapes(true)")
        self.assertEqual([s["name"] for s in full], ["Fill the height of the text", "Shape 4:3", "Shape square", "Whole image"])
        self.assertEqual([s["name"] for s in half], ["Wide (16:9)", "Shape 4:3", "Shape square", "Whole image"])
        self.assertEqual([s["key"] for s in full], [s["key"] for s in half], "the same stored choice at both widths")

    def test_the_approved_names(self):
        names = node("T.NAMES")
        for key, word in (("left", "Image on the left"), ("right", "Image on the right"), ("top", "Image on top"), ("bottom", "Image underneath"),
                          ("swap", "Swap image and text"), ("third", "Image takes a third"), ("half", "Image takes a half"),
                          ("two", "Image takes two thirds"), ("replace", "Replace the image"), ("remove", "Remove the image")):
            self.assertEqual(names[key], word)
        self.assertEqual(node("T.TOOLBAR"), "Image and layout tools")
        self.assertEqual(node("T.GROUP"), {"shape": "Shape", "position": "Where the image sits", "share": "Image width"})


class Storing(unittest.TestCase):
    def test_nothing_stored_is_the_image_on_the_right_on_top_a_half_wide_filling_the_height(self):
        self.assertEqual(node("T.chosen({v: 2})"), {"side": "right", "half": "top", "share": "half", "shape": "fill"})
        self.assertEqual(node("T.chosen({v: 2, side: 'x', half: 3, share: 'odd', shape: 'odd'})"), {"side": "right", "half": "top", "share": "half", "shape": "fill"})

    def test_a_default_choice_is_stored_as_nothing_and_any_other_as_itself(self):
        self.assertEqual(node("T.setting('side', 'right')"), {"side": ""})
        self.assertEqual(node("T.setting('side', 'left')"), {"side": "left"})
        self.assertEqual(node("T.setting('half', 'bottom')"), {"half": "bottom"})
        self.assertEqual(node("T.setting('share', 'half')"), {"share": ""})
        self.assertEqual(node("T.setting('shape', 'fill')"), {"shape": ""})

    def test_the_three_shares_are_read_back_as_stored(self):
        for share in ("third", "half", "two"):
            self.assertEqual(node(f"T.chosen({{v: 2, share: {json.dumps(share)}}})")["share"], share)

    def test_swap_flips_this_widths_choice_and_leaves_the_other_width_alone(self):
        self.assertEqual(node("T.swapped({v: 2}, false)"), {"side": "left"})
        self.assertEqual(node("T.swapped({v: 2, side: 'left'}, false)"), {"side": ""})
        self.assertEqual(node("T.swapped({v: 2}, true)"), {"half": "bottom"})
        self.assertEqual(node("T.swapped({v: 2, half: 'bottom', side: 'left'}, true)"), {"half": ""})

    def test_every_choice_the_toolbar_stores_is_one_the_server_takes(self):
        self.assertEqual(node("T.SIDES"), list(textimage.SIDES[::-1]))
        self.assertEqual(sorted(node("T.HALVES")), sorted(textimage.HALVES))
        self.assertEqual(sorted(node("T.SHARES")), sorted(textimage.SHARES))
        self.assertEqual(sorted(node("T.SHAPES")), sorted(textimage.SHAPES_V2))

    def test_the_file_note_says_the_print_cap(self):
        self.assertEqual(node("T.fileNote(1800, 1200)"),
                         "1,800 × 1,200 px file. Made smaller for print to 3,000 px at most (300 dpi). The published page carries only the part you see.")
        self.assertEqual(node("T.fileNote(0, 0)"), "")
        self.assertEqual(node("T.fileNote(1800, 0)"), "", "a width with no height says nothing")
        self.assertEqual(node("T.fileNote(0, 1200)"), "")

    def test_wide_at_half_width_has_its_own_icon_and_the_others_keep_theirs(self):
        self.assertEqual([s["icon"] for s in node("T.shapes(true)")], ["16:9", "4:3", "square", "whole"])
        self.assertEqual([s["icon"] for s in node("T.shapes(false)")], ["fill", "4:3", "square", "whole"])

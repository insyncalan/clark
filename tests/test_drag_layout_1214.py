"""Row 1214, the pure layout rules of the live drag (logic/dragLayout.js), run in node without a browser.
Run: python3 dev/run_tests.py test_drag_layout_1214
The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
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

ENTRY = ROOT / "tests" / "fixtures" / "drag_layout_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "dl.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=DL", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
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


# Rows: [a] [b] [c d] [e]. Rects at the start of the drag (1400 wide): each row 100 high, 20 apart.
SECTIONS = [sec("a"), sec("b"), sec("c", 1), sec("d"), sec("e")]
RECTS = {"a": dict(left=0, top=0, right=1000, bottom=100), "b": dict(left=0, top=120, right=1000, bottom=220),
         "c": dict(left=0, top=240, right=490, bottom=340), "d": dict(left=510, top=240, right=1000, bottom=340),
         "e": dict(left=0, top=360, right=1000, bottom=460)}
S, R = json.dumps(SECTIONS), json.dumps(RECTS)


def at(moving, x, y, columns=2):
    return run(f"DL.dragTarget({S}, {json.dumps(moving)}, DL.freezeRects({R}), {{x: {x}, y: {y}}}, {{columns: {columns}}})")


class Target(unittest.TestCase):
    def test_the_top_quarter_of_a_section_is_a_full_width_row_above_it(self):
        self.assertEqual(at("e", 500, 125), {"before": "b"})
        self.assertEqual(at("e", 500, 144), {"before": "b"})

    def test_the_bottom_quarter_is_a_full_width_row_below_it_that_is_above_the_next_row(self):
        self.assertEqual(at("a", 500, 215), {"before": "c"})
        self.assertEqual(at("b", 500, 455), {"before": None})

    def test_the_middle_of_a_section_on_its_own_is_half_width_left_or_right_by_the_side_the_pointer_is_on(self):
        self.assertEqual(at("e", 200, 170), {"beside": "b", "side": "left"})
        self.assertEqual(at("e", 800, 170), {"beside": "b", "side": "right"})
        self.assertEqual(at("e", 499, 170), {"beside": "b", "side": "left"})
        self.assertEqual(at("e", 500, 170), {"beside": "b", "side": "right"})

    def test_the_quarter_edge_is_a_quarter_of_the_height_and_not_a_fixed_number_of_pixels(self):
        rects = json.dumps({**RECTS, "b": dict(left=0, top=120, right=1000, bottom=520)})
        sections = json.dumps(SECTIONS)
        probe = lambda y: run(f"DL.dragTarget({sections}, 'e', {rects}, {{x: 200, y: {y}}})")
        self.assertEqual(probe(215), {"before": "b"})                      # 95 px in: still the top quarter of 400
        self.assertEqual(probe(225), {"beside": "b", "side": "left"})      # 105 px in: the middle

    def test_over_a_pair_only_above_or_below_are_offered_whatever_the_x(self):
        for x in (100, 495, 800):
            self.assertEqual(at("a", x, 260), {"before": "c"})
            self.assertEqual(at("a", x, 320), {"before": "e"})
        self.assertEqual(at("a", 100, 289), {"before": "c"})
        self.assertEqual(at("a", 100, 290), {"before": "e"})

    def test_when_pairs_stack_there_is_no_half_to_drop_on(self):
        self.assertEqual(at("e", 800, 169, columns=1), {"before": "b"})
        self.assertEqual(at("e", 800, 170, columns=1), {"before": "c"})

    def test_over_its_own_old_place_nothing_changes(self):
        self.assertIsNone(at("b", 500, 170))
        self.assertIsNone(at("b", 500, 125))
        self.assertIsNone(at("b", 500, 215))
        self.assertIsNone(at("a", 500, 118 - 20))      # bottom quarter of a is below a: the row b is next, a is first: same place
        self.assertIsNone(at("b", 500, 80))            # top of b is where b is: the bottom quarter of a puts b before b

    def test_over_the_middle_of_its_own_pair_nothing_changes_on_either_half_and_over_either_member(self):
        for who in ("c", "d"):
            for x in (100, 495, 800):
                self.assertIsNone(at(who, x, 275))     # upper half of the pair row (would put it above its row: unpair)
                self.assertIsNone(at(who, x, 305))     # lower half (would put it below its row: unpair)
        self.assertEqual(at("c", 100, 345), {"before": "e"})      # the bottom quarter still leaves the pair on purpose
        self.assertEqual(at("d", 100, 245), {"before": "c"})      # and the top quarter
        self.assertEqual(at("a", 100, 275), {"before": "c"})      # another section over that pair still gets above/below

    def test_a_target_that_gives_the_same_page_is_no_change_but_a_pair_half_is_a_change(self):
        self.assertIsNone(at("e", 500, 455))           # below the last row, already last
        self.assertEqual(at("c", 100, 345), {"before": "e"})      # c leaves its pair for a row of its own: a change

    def test_the_target_comes_from_the_start_rects_and_not_from_what_the_page_shows_later(self):
        frozen = run(f"(() => {{ const r = {R}; const f = DL.freezeRects(r); r.b.top = 900; r.b.bottom = 1000; return DL.dragTarget({S}, 'e', f, {{x: 200, y: 170}}); }})()")
        self.assertEqual(frozen, {"beside": "b", "side": "left"})
        self.assertTrue(run("Object.isFrozen(DL.freezeRects({a: {left: 0, top: 0, right: 1, bottom: 1}}).a)"))

    def test_a_few_pixels_of_shake_over_the_right_half_of_a_full_width_section_keep_one_target(self):
        probe = (f"(() => {{ const f = DL.freezeRects({R}); const keys = new Set(); "
                 f"for (let i = 0; i < 40; i++) {{ const t = DL.dragTarget({S}, 'e', f, {{x: 700 + (i % 5) - 2, y: 170 + (i % 3) - 1}}); keys.add(DL.targetKey(t)); }} "
                 f"return [...keys]; }})()")
        self.assertEqual(run(probe), ["beside:b:right"])
        self.assertEqual(at("e", 700, 170), {"beside": "b", "side": "right"})


class Rest(unittest.TestCase):
    def go(self, steps):
        """steps: [[target, time]]; returns [[shown key, moved]] after each."""
        return run(f"(() => {{ let s = DL.settleStart(); return {json.dumps(steps)}.map(([t, n]) => {{ s = DL.settle(s, t, n); return [DL.targetKey(s.shown), s.moved]; }}); }})()")

    A, B = {"before": "b"}, {"beside": "c", "side": "left"}

    def test_the_slot_moves_only_after_the_pointer_has_rested_110_ms_on_the_new_target(self):
        self.assertEqual(run("DL.REST_MS"), 110)
        self.assertEqual(self.go([[self.A, 1000], [self.A, 1109], [self.A, 1110], [self.A, 1500]]),
                         [["none", False], ["none", False], ["before:b", True], ["before:b", False]])

    def test_a_quick_pass_over_another_target_changes_nothing(self):
        steps = [[self.A, 0], [self.A, 120], [self.B, 130], [self.B, 200], [self.A, 210], [self.A, 400]]
        self.assertEqual(self.go(steps), [["none", False], ["before:b", True], ["before:b", False], ["before:b", False], ["before:b", False], ["before:b", False]])

    def test_the_rest_time_counts_from_when_the_target_last_changed(self):
        steps = [[self.A, 0], [self.B, 100], [self.B, 209], [self.B, 210]]
        self.assertEqual(self.go(steps), [["none", False], ["none", False], ["none", False], ["beside:c:left", True]])

    def test_a_target_of_none_is_a_target_too_and_the_slot_leaves_after_the_rest(self):
        steps = [[self.A, 0], [self.A, 110], [None, 120], [None, 229], [None, 230]]
        self.assertEqual(self.go(steps), [["none", False], ["before:b", True], ["before:b", False], ["before:b", False], ["none", True]])

    def test_the_same_target_given_again_never_draws_again(self):
        steps = [[self.A, 0], [self.A, 110], [{"before": "b"}, 300], [{"before": "b"}, 900]]
        self.assertEqual([m for _, m in self.go(steps)], [False, True, False, False])

    def test_rest_left_is_the_time_still_to_wait_and_zero_when_nothing_waits(self):
        probe = ("(() => { const s = DL.settleStart(); const w = DL.settle(s, %s, 1000);"
                 " return [DL.restLeft(w, 1000), DL.restLeft(w, 1109), DL.restLeft(w, 1110), DL.restLeft(w, 1500), DL.restLeft(DL.settleStart(), 5)]; })()") % json.dumps(self.A)
        self.assertEqual(run(probe), [110, 1, 0, 0, 0])

    def test_nothing_waits_once_the_shown_target_is_the_wanted_one(self):
        probe = ("(() => { let s = DL.settle(DL.settleStart(), %s, 0); s = DL.settle(s, %s, 110); return [s.moved, DL.restLeft(s, 111)]; })()") % (json.dumps(self.A), json.dumps(self.A))
        self.assertEqual(run(probe), [True, 0])


if __name__ == "__main__":
    unittest.main()

"""#95 (Rearrange the dashboard by dragging sections), the pure part: where a section goes when it is dropped or moved by the keyboard
(src/clark/page/src/logic/placement.js). The rules are in docs/handoff/design-95-drag-sections.md, section 3 (the drops and refusals)
and section 4 (the change each makes). Nothing here draws or sends anything: the page parts wait for the guarded changes the note asks for.

Run: python3 dev/run_tests.py test_placement
The repo has no Node, so the plain-JS logic runs inside headless Chrome (the #33 harness, as test_page.py does): it is bundled with
the pinned esbuild into a temporary folder (never the repo) and put on a page that the harness server serves. Chrome is required:
these tests fail, never skip, without it.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark import changes, order  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402  (the #33 browser harness, shared)

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "placement_demo.js"


def sec(id, title, beside=0, type="text", hidden=0):
    return {"id": id, "type": type, "title": title, "beside": beside, "hidden": hidden}


# Fictional. Rows: [a] [b] [c] [d e] [f] [g]
SECTIONS = [sec("a", "Current state", type="current"), sec("b", "Milestones", type="milestones"), sec("c", "Summary"),
            sec("d", "This week", beside=1), sec("e", "Next week"), sec("f", "Risks and issues", type="raid"),
            sec("g", "Decisions", type="decisions")]

_PAGE = {}


def test_page_html():
    """The logic, bundled by the pinned esbuild in a temporary folder, on a bare page."""
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


class InBrowser(unittest.TestCase):
    """One server and one headless Chrome for the class; each test loads the page afresh."""

    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=test_page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.placement)", self.sid)), "the test bundle ran")

    def val(self, expr):
        """Evaluate an expression in the page and get its value back as JSON (so errors and undefined show up)."""
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertNotIsInstance(got, type(None), expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)


class Placement(InBrowser):
    def place(self, id, target, sections=SECTIONS):
        return self.val(f"T.placement.place({lit(sections)}, {lit(id)}, {lit(target)})")

    def call(self, fn, id, *more, sections=SECTIONS):
        return self.val(f"T.placement.{fn}({lit(sections)}, {lit(id)}{''.join(', ' + lit(m) for m in more)})")

    def rows(self, sections):
        return self.val(f"T.placement.rows({lit(sections)}).map(r => r.map(s => s.id))")

    def after(self, result, sections=SECTIONS):
        """The rows (ids) once the result's change is made."""
        self.assertTrue(result["ok"], result)
        return self.val(f"T.placement.rows(T.placement.applied({lit(sections)}, {lit(result['payload'])})).map(r => r.map(s => s.id))")

    def order(self, result, sections=SECTIONS):
        return self.val(f"T.placement.applied({lit(sections)}, {lit(result['payload'])}).map(s => s.id)")

    def quiet(self, result, why):
        self.assertEqual((result["ok"], result["why"], result["quiet"], result["message"]), (False, why, True, ""))

    def refused(self, result, why, words):
        self.assertEqual((result["ok"], result["why"], result["quiet"], result["message"]), (False, why, False, words))

    # ── the rows ──────────────────────────────────────────────────────────────

    def test_rows_are_read_from_the_flags_and_never_hold_three(self):
        self.assertEqual(self.rows(SECTIONS), [["a"], ["b"], ["c"], ["d", "e"], ["f"], ["g"]])
        chained = [sec("x", "X", 1), sec("y", "Y", 1), sec("z", "Z", 1), sec("w", "W", 1)]
        self.assertEqual(self.rows(chained), [["x", "y"], ["z", "w"]], "pairs never chain: the second one's flag does nothing")
        self.assertEqual(self.rows([sec("x", "X"), sec("y", "Y", 1)]), [["x"], ["y"]], "a flag on the last section does nothing")
        self.assertEqual(self.rows([]), [])

    def test_a_hidden_half_leaves_the_other_full_width_and_does_not_pair_its_neighbours(self):
        s = [sec("a", "A"), sec("b", "B", 1), sec("c", "C", hidden=1), sec("d", "D")]
        self.assertEqual(self.val(f"T.placement.rows({lit(s)}, s => !s.hidden).map(r => r.map(s => s.id))"), [["a"], ["b"], ["d"]],
                         "B is beside the hidden C, so B is alone: it does not move up to pair with D")
        self.assertEqual(self.val(f"T.placement.slots({lit(s)}, s => !s.hidden)"), {"a": "full", "b": "full", "d": "full"})
        both = [sec("a", "A"), sec("b", "B", 1, hidden=1), sec("c", "C", hidden=1), sec("d", "D")]
        self.assertEqual(self.val(f"T.placement.rows({lit(both)}, s => !s.hidden).map(r => r.map(s => s.id))"), [["a"], ["d"]])
        self.assertEqual(self.val(f"T.placement.slots({lit(SECTIONS)})"),
                         {"a": "full", "b": "full", "c": "full", "d": "left", "e": "right", "f": "full", "g": "full"})

    # ── between rows ──────────────────────────────────────────────────────────

    def test_a_section_dropped_between_rows_takes_a_row_of_its_own(self):
        r = self.place("f", {"before": "b"})
        self.assertEqual(r["payload"], {"op": "move", "id": "f", "before": "b"}, "the request the page sends today: no flags")
        self.assertEqual(r["words"], "Moved Risks and issues to its own row, above Milestones.")
        self.assertEqual(self.after(r), [["a"], ["f"], ["b"], ["c"], ["d", "e"], ["g"]])
        r = self.place("a", {"before": None})
        self.assertEqual(r["payload"], {"op": "move", "id": "a", "before": None})
        self.assertEqual(r["words"], "Moved Current state to its own row, at the end.")
        r = self.place("g", {"before": "a"})
        self.assertEqual(r["words"], "Moved Decisions to its own row, at the top.")
        self.assertEqual(self.order(r), ["g", "a", "b", "c", "d", "e", "f"])

    def test_a_row_can_be_dropped_above_or_below_a_pair(self):
        self.assertEqual(self.after(self.place("a", {"before": "d"})), [["b"], ["c"], ["a"], ["d", "e"], ["f"], ["g"]])
        self.assertEqual(self.after(self.place("a", {"before": "f"})), [["b"], ["c"], ["d", "e"], ["a"], ["f"], ["g"]])

    def test_dropping_where_it_already_is_does_nothing_and_says_nothing(self):
        self.quiet(self.place("b", {"before": "c"}), "same")
        self.quiet(self.place("g", {"before": None}), "same")
        self.quiet(self.place("a", {"before": "b"}), "same")
        self.quiet(self.place("b", {"before": "b"}), "itself")
        self.quiet(self.place("b", {"beside": "b", "side": "left"}), "itself")

    def test_taking_half_of_a_pair_out_leaves_its_partner_alone_at_full_width(self):
        r = self.place("d", {"before": "f"})
        self.assertEqual(r["payload"], {"op": "move", "id": "d", "before": "f", "flags": {"d": 0}})
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["e"], ["d"], ["f"], ["g"]])
        r = self.place("e", {"before": "b"})
        self.assertEqual(r["payload"], {"op": "move", "id": "e", "before": "b", "flags": {"d": 0}},
                         "the second half goes: the first half's flag is cleared, or it would pair with what follows")
        self.assertEqual(self.after(r), [["a"], ["e"], ["b"], ["c"], ["d"], ["f"], ["g"]])
        r = self.place("e", {"before": "d"})
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["e"], ["d"], ["f"], ["g"]], "just above its own partner: out of the pair")
        r = self.place("d", {"before": None})
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["e"], ["f"], ["g"], ["d"]])

    # ── beside ────────────────────────────────────────────────────────────────

    def test_a_section_dropped_on_the_left_or_right_half_of_a_lone_section_shares_its_row(self):
        r = self.place("g", {"beside": "f", "side": "left"})
        self.assertEqual(r["payload"], {"op": "move", "id": "g", "before": "f", "flags": {"g": 1}})
        self.assertEqual(r["words"], "Moved Decisions beside Risks and issues, on the left.")
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["d", "e"], ["g", "f"]])
        r = self.place("a", {"beside": "g", "side": "right"})
        self.assertEqual(r["payload"], {"op": "move", "id": "a", "before": None, "flags": {"g": 1}})
        self.assertEqual(r["words"], "Moved Current state beside Decisions, on the right.")
        self.assertEqual(self.after(r), [["b"], ["c"], ["d", "e"], ["f"], ["g", "a"]])
        r = self.place("a", {"beside": "b", "side": "right"})
        self.assertEqual(r["payload"], {"op": "move", "id": "a", "before": "c", "flags": {"b": 1}})
        self.assertEqual(self.after(r)[:2], [["b", "a"], ["c"]])

    def test_every_section_type_can_be_placed_beside_every_other(self):
        for first, second in (("a", "b"), ("b", "f"), ("g", "a"), ("f", "g")):
            r = self.place(first, {"beside": second, "side": "left"})
            self.assertTrue(r["ok"], (first, second))
            self.assertIn([first, second], self.after(r))

    def test_half_of_a_pair_dropped_beside_another_leaves_its_partner_alone(self):
        r = self.place("e", {"beside": "f", "side": "left"})
        self.assertEqual(r["payload"], {"op": "move", "id": "e", "before": "f", "flags": {"d": 0, "e": 1}})
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["d"], ["e", "f"], ["g"]])
        r = self.place("d", {"beside": "g", "side": "right"})
        self.assertEqual(r["payload"], {"op": "move", "id": "d", "before": None, "flags": {"d": 0, "g": 1}})
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["e"], ["f"], ["g", "d"]])

    def test_dropping_on_the_other_half_of_its_own_pair_swaps_the_sides(self):
        r = self.place("d", {"beside": "e", "side": "right"})
        self.assertEqual(r["payload"], {"op": "move", "id": "d", "before": "f", "flags": {"d": 0, "e": 1}})
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["e", "d"], ["f"], ["g"]])
        self.assertEqual(self.after(self.place("e", {"beside": "d", "side": "left"})), [["a"], ["b"], ["c"], ["e", "d"], ["f"], ["g"]])
        self.quiet(self.place("d", {"beside": "e", "side": "left"}), "same")
        self.quiet(self.place("e", {"beside": "d", "side": "right"}), "same")

    def test_a_row_never_holds_more_than_two(self):
        words = "A row holds two sections at most. Put it between rows, or beside a section on its own."
        for target in ({"beside": "d", "side": "left"}, {"beside": "e", "side": "right"}):
            self.refused(self.place("a", target), "full", words)
        self.refused(self.place("c", {"beside": "d", "side": "right"}), "full", words)

    def test_a_section_cannot_go_in_the_middle_of_a_pair(self):
        self.refused(self.place("a", {"before": "e"}), "inside", "A section can't go in the middle of a pair. Put it between rows.")

    def test_a_section_or_target_that_is_not_in_the_list_is_refused(self):
        words = "That section isn't in the report any more. Reload the page."
        self.refused(self.place("zz", {"before": "a"}), "gone", words)
        self.refused(self.place("a", {"before": "zz"}), "gone", words)
        self.refused(self.place("a", {"beside": "zz", "side": "left"}), "gone", words)
        self.refused(self.place("a", {"beside": "b", "side": "above"}), "gone", words)
        self.refused(self.place("a", {}), "gone", words)
        self.refused(self.place("a", None), "gone", words)

    def test_a_stray_flag_never_pairs_a_section_with_what_follows(self):
        s = [sec("x", "X", 1), sec("y", "Y", 1), sec("z", "Z"), sec("w", "W", 1)]    # y's flag does nothing; w's does nothing
        self.assertEqual(self.rows(s), [["x", "y"], ["z"], ["w"]])
        r = self.place("x", {"before": None}, s)
        self.assertEqual(r["payload"]["flags"], {"x": 0, "y": 0, "w": 0},
                         "y's old flag would pair it with z once x has gone, and w's would pair it with x, dropped after it")
        self.assertEqual(self.after(r, s), [["y"], ["z"], ["w"], ["x"]])
        r = self.place("z", {"before": None}, s)
        self.assertEqual(r["payload"], {"op": "move", "id": "z", "before": None, "flags": {"w": 0}},
                         "w's flag would pair it with z, dropped after it")
        self.assertEqual(self.after(r, s), [["x", "y"], ["w"], ["z"]])

    # ── the keyboard ──────────────────────────────────────────────────────────

    def test_move_up_and_down_go_by_rows(self):
        r = self.call("step", "c", -1)
        self.assertEqual(r["payload"], {"op": "move", "id": "c", "before": "b"})
        self.assertEqual(r["words"], "Moved Summary up.")
        r = self.call("step", "c", 1)
        self.assertEqual(r["payload"], {"op": "move", "id": "c", "before": "f"}, "a lone section passes the whole pair")
        self.assertEqual(self.after(r), [["a"], ["b"], ["d", "e"], ["c"], ["f"], ["g"]])
        self.assertEqual(self.after(self.call("step", "f", -1)), [["a"], ["b"], ["c"], ["f"], ["d", "e"], ["g"]])
        self.assertEqual(self.call("step", "f", 1)["words"], "Moved Risks and issues down.")

    def test_half_of_a_pair_steps_out_of_it(self):
        self.assertEqual(self.after(self.call("step", "d", -1)), [["a"], ["b"], ["d"], ["c"], ["e"], ["f"], ["g"]],
                         "away from its partner: out, and past the row above")
        self.assertEqual(self.after(self.call("step", "d", 1)), [["a"], ["b"], ["c"], ["e"], ["d"], ["f"], ["g"]],
                         "towards its partner: out, just below it")
        self.assertEqual(self.after(self.call("step", "e", -1)), [["a"], ["b"], ["c"], ["e"], ["d"], ["f"], ["g"]],
                         "towards its partner: out, just above it")
        self.assertEqual(self.after(self.call("step", "e", 1)), [["a"], ["b"], ["c"], ["d"], ["f"], ["e"], ["g"]],
                         "away from its partner: out, and past the row below")
        self.assertEqual(self.call("step", "d", -1)["payload"]["flags"], {"d": 0})

    def test_the_first_and_last_rows_cannot_move_further_and_say_so(self):
        self.refused(self.call("step", "a", -1), "first", "This section is already first.")
        self.refused(self.call("step", "g", 1), "last", "This section is already last.")
        self.refused(self.call("step", "zz", 1), "gone", "That section isn't in the report any more. Reload the page.")
        pair_last = [sec("a", "A"), sec("x", "X", 1), sec("y", "Y")]
        self.refused(self.call("step", "y", 1, sections=pair_last), "last", "This section is already last.")
        self.assertEqual(self.after(self.call("step", "x", 1, sections=pair_last), pair_last), [["a"], ["y"], ["x"]])
        pair_first = [sec("x", "X", 1), sec("y", "Y"), sec("a", "A")]
        self.refused(self.call("step", "x", -1, sections=pair_first), "first", "This section is already first.")
        self.assertEqual(self.after(self.call("step", "y", -1, sections=pair_first), pair_first), [["y"], ["x"], ["a"]])

    def test_place_beside_the_next_section(self):
        r = self.call("beside", "b")
        self.assertEqual(r["payload"], {"op": "move", "id": "b", "before": "c", "flags": {"b": 1}})
        self.assertEqual(r["words"], "Moved Milestones beside Summary, on the left.")
        self.assertEqual(self.after(r), [["a"], ["b", "c"], ["d", "e"], ["f"], ["g"]])
        self.assertEqual(self.after(self.call("beside", "f")), [["a"], ["b"], ["c"], ["d", "e"], ["f", "g"]])
        self.refused(self.call("beside", "g"), "noNext", "This is the last section, so there is nothing to sit beside.")
        self.refused(self.call("beside", "c"), "nextFull", "The next row already has two sections. Move one of them first, or move this section between rows.")
        self.refused(self.call("beside", "d"), "shared", "This section already shares its row. Choose Full width to give it a row of its own.")
        self.refused(self.call("beside", "e"), "shared", "This section already shares its row. Choose Full width to give it a row of its own.")

    def test_full_width_works_from_either_half(self):
        r = self.call("fullWidth", "d")
        self.assertEqual(r["payload"], {"op": "move", "id": "d", "before": "e", "flags": {"d": 0}})
        self.assertEqual(r["words"], "This week is now full width.")
        self.assertEqual(self.order(r), ["a", "b", "c", "d", "e", "f", "g"], "nothing moves")
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["d"], ["e"], ["f"], ["g"]])
        r = self.call("fullWidth", "e")
        self.assertEqual(r["payload"], {"op": "move", "id": "e", "before": "f", "flags": {"d": 0}}, "the first half's flag is the one cleared")
        self.assertEqual(self.after(r), [["a"], ["b"], ["c"], ["d"], ["e"], ["f"], ["g"]])
        last = [sec("a", "A"), sec("x", "X", 1), sec("y", "Y")]
        self.assertEqual(self.call("fullWidth", "y", sections=last)["payload"], {"op": "move", "id": "y", "before": None, "flags": {"x": 0}})
        self.refused(self.call("fullWidth", "c"), "alone", "This section already has its own row.")

    def test_the_words_use_the_title_cut_short_and_never_an_id(self):
        long = "x" * 80
        s = [sec("a", long), sec("b", "B"), sec("c", "   ")]
        said = self.place("a", {"before": None}, s)["words"]
        self.assertEqual(said, "Moved " + "x" * 39 + "… to its own row, at the end.")
        self.assertEqual(self.place("b", {"before": None}, s)["words"], "Moved B to its own row, at the end.")
        self.assertEqual(self.place("a", {"before": "c"}, s)["words"], "Moved " + "x" * 39 + "… to its own row, above This section.")

    # ── the pointer ───────────────────────────────────────────────────────────

    # The page at 1000 px: rows a b c [d e] f g, 100 px tall with 16 px between; the pair 488 and 488 wide with 24 between.
    RECTS = {"a": (0, 0, 1000, 100), "b": (0, 116, 1000, 216), "c": (0, 232, 1000, 332), "d": (0, 348, 488, 448), "e": (512, 348, 1000, 448),
             "f": (0, 464, 1000, 564), "g": (0, 580, 1000, 680)}

    def rects(self, drop=()):
        return {k: {"left": v[0], "top": v[1], "right": v[2], "bottom": v[3]} for k, v in self.RECTS.items() if k not in drop}

    def at(self, id, x, y, columns=2, drop=(), sections=SECTIONS):
        return self.val(f"T.placement.targetAt({lit(sections)}, {lit(id)}, {lit(self.rects(drop))}, {{x: {x}, y: {y}}}, {{columns: {columns}}})")

    def test_the_top_and_bottom_of_a_section_mean_between_rows(self):
        self.assertEqual(self.at("g", 500, 5), {"before": "a"}, "the top of the first row")
        self.assertEqual(self.at("g", 500, 95), {"before": "b"}, "the bottom of a, the top of b")
        self.assertEqual(self.at("g", 500, 124), {"before": "b"})
        self.assertEqual(self.at("a", 500, 670), {"before": None}, "the bottom of the last row")

    def test_above_the_first_row_and_below_the_last_are_the_top_and_the_end(self):
        self.assertEqual(self.at("g", 500, -80), {"before": "a"}, "over the cover: first, and the cover does not move")
        self.assertEqual(self.at("a", 500, 900), {"before": None})
        self.assertEqual(self.at("g", 2000, -80), {"before": "a"}, "far to the side too")

    def test_the_gap_between_rows_goes_to_the_nearer_row_edge(self):
        self.assertEqual(self.at("g", 500, 222), {"before": "c"}, "nearer b's bottom: below b, above c")
        self.assertEqual(self.at("g", 500, 226), {"before": "c"})

    def test_the_middle_of_a_lone_section_is_its_left_or_right_half(self):
        self.assertEqual(self.at("g", 100, 50), {"beside": "a", "side": "left"})
        self.assertEqual(self.at("g", 900, 50), {"beside": "a", "side": "right"})
        self.assertEqual(self.at("g", 499, 280), {"beside": "c", "side": "left"})
        self.assertEqual(self.at("g", 500, 280), {"beside": "c", "side": "right"})

    def test_over_a_pair_the_middle_is_a_line_above_or_below_it(self):
        self.assertEqual(self.at("g", 100, 380), {"before": "d"}, "the upper half of the pair")
        self.assertEqual(self.at("g", 900, 420), {"before": "f"}, "the lower half of the pair")
        self.assertEqual(self.at("g", 100, 350), {"before": "d"}, "the top edge")
        self.assertEqual(self.at("g", 900, 445), {"before": "f"}, "the bottom edge")

    def test_over_the_section_being_moved_there_is_no_target(self):
        self.assertIsNone(self.at("a", 500, 50))
        self.assertIsNone(self.at("a", 500, 5), "not even at its top edge")
        self.assertIsNone(self.at("d", 100, 400))
        self.assertIsNone(self.val(f"T.placement.targetAt({lit(SECTIONS)}, 'a', {{}}, {{x: 1, y: 1}})"), "no rectangles")

    def test_over_its_own_partner_the_target_is_never_the_moved_section(self):
        self.assertEqual(self.at("d", 900, 400), {"beside": "e", "side": "right"}, "the right of the partner")
        self.assertEqual(self.at("d", 520, 400), {"beside": "e", "side": "left"})
        self.assertEqual(self.at("d", 700, 350), {"before": "e"}, "above the pair, so d leaves it above e, not 'before d'")
        self.assertEqual(self.at("d", 700, 445), {"before": "f"})
        self.assertEqual(self.at("e", 100, 350), {"before": "d"})
        self.assertEqual(self.at("e", 100, 445), {"before": "f"})
        self.assertEqual(self.at("g", 700, 350), {"before": "d"})

    def test_the_gap_beside_a_lone_sections_own_place_is_where_it_already_is(self):
        t = self.at("b", 500, 95)                       # the bottom of a, and b's own row is next
        self.assertEqual(t, {"before": "c"})
        self.quiet(self.place("b", t), "same")
        self.assertIsNone(self.val(f"T.placement.indicator({lit(SECTIONS)}, 'b', {lit(t)})"))

    def test_when_pairs_stack_there_is_no_half_to_drop_on(self):
        stacked = {"a": (0, 0, 400, 100), "b": (0, 116, 400, 216), "c": (0, 232, 400, 332), "d": (0, 348, 400, 448),
                   "e": (0, 464, 400, 564), "f": (0, 580, 400, 680), "g": (0, 696, 400, 796)}
        rects = {k: {"left": v[0], "top": v[1], "right": v[2], "bottom": v[3]} for k, v in stacked.items()}
        at = lambda id, x, y: self.val(f"T.placement.targetAt({lit(SECTIONS)}, {lit(id)}, {lit(rects)}, {{x: {x}, y: {y}}}, {{columns: 1}})")
        self.assertEqual(at("g", 100, 40), {"before": "a"}, "the middle of a lone section: the nearer line, above it")
        self.assertEqual(at("g", 100, 60), {"before": "b"}, "or below it")
        self.assertEqual(at("g", 100, 420), {"before": "d"}, "the upper half of the stacked pair, which is one row")
        self.assertEqual(at("g", 100, 500), {"before": "f"}, "the lower half")

    def test_a_section_that_is_not_drawn_is_never_a_target(self):
        self.assertEqual(self.at("g", 900, 450, drop=("d", "e")), {"before": "f"}, "the pair is not drawn: the nearest drawn section is f")

    def test_a_small_section_uses_a_quarter_of_its_height_as_its_edge(self):
        small = {"a": {"left": 0, "top": 0, "right": 1000, "bottom": 40}, "b": {"left": 0, "top": 56, "right": 1000, "bottom": 96}}
        at = lambda y: self.val(f"T.placement.targetAt({lit(SECTIONS[:3])}, 'c', {lit(small)}, {{x: 100, y: {y}}})")
        self.assertEqual(at(9), {"before": "a"})
        self.assertEqual(at(11), {"beside": "a", "side": "left"}, "the edge is 10 px of 40")
        self.assertEqual(at(29), {"beside": "a", "side": "left"})
        self.assertEqual(at(31), {"before": "b"})

    # ── the indicator ─────────────────────────────────────────────────────────

    def indicator(self, id, target, sections=SECTIONS):
        return self.val(f"T.placement.indicator({lit(sections)}, {lit(id)}, {lit(target)})")

    def test_the_indicator_is_a_line_across_the_row_or_an_outline_on_a_half(self):
        self.assertEqual(self.indicator("a", {"before": "f"}), {"line": "before", "ids": ["f"]})
        self.assertEqual(self.indicator("a", {"before": "d"}), {"line": "before", "ids": ["d", "e"]}, "both halves of a pair carry the line")
        self.assertEqual(self.indicator("a", {"before": None}), {"line": "end", "ids": []})
        self.assertEqual(self.indicator("g", {"beside": "f", "side": "left"}), {"outline": "f", "side": "left"})
        self.assertEqual(self.indicator("g", {"beside": "f", "side": "right"}), {"outline": "f", "side": "right"})
        self.assertEqual(self.indicator("d", {"before": "e"}), {"line": "before", "ids": ["d", "e"]}, "leaving its own pair: the line over the pair")

    def test_there_is_no_indicator_where_a_drop_would_do_nothing_or_be_refused(self):
        for who, target in (("b", {"before": "c"}), ("b", {"before": "b"}), ("a", {"beside": "d", "side": "left"}), ("a", {"before": "e"}),
                            ("a", {"before": "zz"}), ("d", {"beside": "e", "side": "left"}), ("zz", {"before": "a"})):
            self.assertIsNone(self.indicator(who, target), (who, target))

    # ── all of it, against a second way of working it out ─────────────────────

    def test_every_drop_gives_the_rows_meant_and_a_change_clark_can_undo(self):
        """For every section, every target and several layouts (with stray flags): the rows after the change are the rows worked out
        another way (move the section in the list of rows, with its old partner left alone); a refusal is the one expected; each flag in
        the change differs from the section's own and is 0 or 1; no more than four; a change with no flags has no flags key."""
        bad = self.val("""(function () {
            const P = T.placement, out = [];
            const sec = (id, beside) => ({ id, title: id.toUpperCase(), beside: beside ? 1 : 0 });
            const layouts = [
              ['default', [sec('a'), sec('b'), sec('c'), sec('d', 1), sec('e'), sec('f'), sec('g')]],
              ['stray', [sec('x', 1), sec('y', 1), sec('z'), sec('w', 1)]],
              ['pairs at the ends', [sec('p', 1), sec('q'), sec('r'), sec('s', 1), sec('t')]],
              ['two pairs', [sec('a', 1), sec('b'), sec('c', 1), sec('d')]],
              ['one', [sec('a')]],
              ['a pair', [sec('a', 1), sec('b')]],
              ['chain', [sec('a', 1), sec('b', 1), sec('c', 1), sec('d', 1), sec('e')]],
            ];
            const ids = (rs) => JSON.stringify(rs.map((r) => r.map((s) => s.id)));
            for (const [label, list] of layouts) {
              const old = P.rows(list);
              for (const me of list) {
                const rest = old.map((r) => r.filter((s) => s.id !== me.id)).filter((r) => r.length);
                const targets = [{ before: null }];
                for (const s of list) { targets.push({ before: s.id }); targets.push({ beside: s.id, side: 'left' }); targets.push({ beside: s.id, side: 'right' }); }
                for (const t of targets) {
                  const got = P.place(list, me.id, t), name = label + ': ' + me.id + ' ' + JSON.stringify(t);
                  let want;                                     // the second way: rows in, rows out
                  if ('beside' in t) {
                    if (t.beside === me.id) want = { no: 'itself' };
                    else {
                      const k = rest.findIndex((r) => r.some((s) => s.id === t.beside));
                      if (rest[k].length > 1) want = { no: 'full' };
                      else { const rows = rest.map((r) => r.slice()); rows[k] = t.side === 'left' ? [me, rest[k][0]] : [rest[k][0], me]; want = { rows }; }
                    }
                  } else if (t.before === me.id) want = { no: 'itself' };
                  else if (t.before === null) want = { rows: rest.concat([[me]]) };
                  else {
                    const k = rest.findIndex((r) => r.some((s) => s.id === t.before));
                    if (rest[k][0].id !== t.before) want = { no: 'inside' };
                    else want = { rows: rest.slice(0, k).concat([[me]], rest.slice(k)) };
                  }
                  if (!got.ok) {
                    if (want.no) { if (got.why !== want.no) out.push(name + ' refused as ' + got.why + ', want ' + want.no); }
                    else if (got.why !== 'same' || ids(want.rows) !== ids(old)) out.push(name + ' refused as ' + got.why + ' but the rows should be ' + ids(want.rows));
                    continue;
                  }
                  if (want.no) { out.push(name + ' was allowed, want ' + want.no); continue; }
                  const rows = P.rows(P.applied(list, got.payload));
                  if (ids(rows) !== ids(want.rows)) out.push(name + ' gave ' + ids(rows) + ', want ' + ids(want.rows));
                  const f = got.payload.flags;
                  if ('flags' in got.payload && (!f || Object.keys(f).length === 0)) out.push(name + ' has an empty flags');
                  if (f) {
                    if (Object.keys(f).length > 4) out.push(name + ' has more than four flags');
                    for (const k of Object.keys(f)) {
                      const was = list.find((s) => s.id === k);
                      if (!was) out.push(name + ' sets a flag on ' + k);
                      else if (f[k] !== 0 && f[k] !== 1) out.push(name + ' flag ' + k + ' is ' + f[k]);
                      else if (f[k] === was.beside) out.push(name + ' flag ' + k + ' does not change');
                    }
                  }
                  if (got.payload.before === me.id) out.push(name + ' moves it before itself');
                  const keys = Object.keys(got.payload).sort().join();
                  if (keys !== 'before,id,op' && keys !== 'before,flags,id,op') out.push(name + ' has keys ' + keys);
                  if (P.indicator(list, me.id, t) === null) out.push(name + ' is allowed but has no indicator');
                }
              }
            }
            return out;
        })()""")
        self.assertEqual(bad, [])

    def test_every_step_gives_rows_where_the_section_moved_one_row_and_no_other_pair_changed(self):
        bad = self.val("""(function () {
            const P = T.placement, out = [];
            const sec = (id, beside) => ({ id, title: id.toUpperCase(), beside: beside ? 1 : 0 });
            const list = [sec('a'), sec('b'), sec('c', 1), sec('d'), sec('e'), sec('f', 1), sec('g'), sec('h')];
            const ids = (rs) => JSON.stringify(rs.map((r) => r.map((s) => s.id)));
            for (const me of list) for (const dir of [-1, 1]) {
              const got = P.step(list, me.id, dir), name = me.id + ' ' + dir;
              if (!got.ok) { if (!['first', 'last'].includes(got.why)) out.push(name + ' refused as ' + got.why); continue; }
              const was = P.rows(list), now = P.rows(P.applied(list, got.payload));
              const rowOf = (rs, id) => rs.findIndex((r) => r.some((s) => s.id === id));
              const partner = was[rowOf(was, me.id)].find((s) => s.id !== me.id);
              if (partner && now[rowOf(now, partner.id)].length !== 1) out.push(name + ' left its partner in a pair');
              const others = (rs) => rs.map((r) => r.filter((s) => s.id !== me.id)).filter((r) => r.length).map((r) => r.map((s) => s.id).join('+'));
              if (JSON.stringify(others(was)) !== JSON.stringify(others(now))) out.push(name + ' changed other rows: ' + ids(now));
              if (now[rowOf(now, me.id)].length !== 1) out.push(name + ' is not at full width: ' + ids(now));
              if (Math.abs(rowOf(now, me.id) - rowOf(was, me.id)) > 2) out.push(name + ' went too far: ' + ids(now));
            }
            return out;
        })()""")
        self.assertEqual(bad, [])


class AcceptedByChanges(InBrowser):
    """The change `placement.js` gives is the request /api/change takes: a move with no flags is accepted as it is. A move with `flags`
    (and a flag of 1 on a section that is not text) is what the design note's guarded changes add, so their tests come with them."""

    def test_a_move_without_flags_is_accepted_and_gives_the_order_the_logic_said(self):
        with DemoStore() as store:
            change = changes.make_change(store.path, [], USER)
            for who, target in (("ABC-S-009", {"before": "ABC-S-003"}), ("ABC-S-001", {"before": None}), ("ABC-S-004", {"before": "ABC-S-011"})):
                rows = order.in_order(store.read("report_sections", "ABC"))
                got = self.val(f"T.placement.place({lit(rows)}, {lit(who)}, {lit(target)})")
                self.assertTrue(got["ok"], got)
                self.assertNotIn("flags", got["payload"], "a lone section with no flag to change")
                status, body = change({"project": "ABC", "kind": "report_sections", "place": "report", **got["payload"]})
                self.assertEqual((status, body.get("message")), (200, None), body)
                want = self.val(f"T.placement.applied({lit(rows)}, {lit(got['payload'])}).map(s => s.id)")
                self.assertEqual([r["id"] for r in body["sections"]], want)
                self.assertTrue(body["apply_id"], "one step, with Undo")


if __name__ == "__main__":
    unittest.main()

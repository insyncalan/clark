"""#926, the Gantt table's rules (src/clark/page/src/gantt/logic/grid.js): the 21 columns, what a cell holds, the plain words of a refusal,
copy and paste as tab-separated text, fill, undo, the maths of a selected range and the hide-from-client rule. Nothing here draws anything.
Fictional data.

Run: python3 dev/run_tests.py test_gantt_grid
The repo has no Node, so the logic runs inside headless Chrome (as test_tracker_logic does). Chrome is required: these tests fail, never skip.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _gantt_lines import LINES
from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "gantt_grid_demo.js"
_PAGE = {}
TODAY = "2026-11-06"


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


class Grid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.K && window.K.COLUMNS)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def set(self, index, key, text, lines=LINES):
        return self.val(f"K.setField({lit(lines)}, {index}, {lit(key)}, {lit(text)})")

    def err(self, index, key, text):
        return self.set(index, key, text)["error"]

    # ── the columns ──

    def test_the_21_columns_in_the_agreed_order(self):
        cols = self.val("K.COLUMNS")
        self.assertEqual([c["label"] for c in cols], [
            "ID", "Line", "Type", "Parent", "Start", "End", "Days", "Done %", "Status", "Health", "Depends on", "Owner", "Workstream", "Priority",
            "Baseline start", "Baseline end", "Effort (days)", "Budget", "Deliverable", "On dashboard", "Notes"])
        self.assertEqual({c["key"] for c in cols if c["type"] == "ro"}, {"id", "dur", "st"})
        self.assertTrue(all(c["width"] > 0 for c in cols))
        self.assertEqual([c["key"] for c in cols if c["type"] == "select"], ["t", "rag", "pri", "show"])

    def test_view_draws_no_hidden_column_and_edit_draws_all(self):
        view = [c["key"] for c in self.val("K.visibleColumns(K.DEFAULT_HIDDEN, false)")]
        self.assertEqual(len(view), 15)
        for hidden in ("show", "note", "cost", "eff", "bs", "be"):
            self.assertNotIn(hidden, view)
        self.assertEqual(len(self.val("K.visibleColumns(K.DEFAULT_HIDDEN, true)")), 21)
        self.assertEqual(self.val("K.DEFAULT_HIDDEN"), ["show", "note", "cost", "eff", "bs", "be"])

    def test_id_and_line_can_never_be_hidden(self):
        view = [c["key"] for c in self.val("K.visibleColumns(['id', 'n', 's', 'o'], false)")]
        self.assertEqual(view[:2], ["id", "n"])
        self.assertIn("s", view, "Start can never be hidden from the client (the data layer refuses it: row 926)")
        self.assertNotIn("o", view, "a column that may be hidden still goes")

    # ── what a cell holds ──

    def test_dates_show_as_dd_mm_yyyy_and_worked_out_cells_are_worked_out(self):
        g = lambda i, k: self.val(f"K.getValue({lit(LINES[i])}, {lit(k)}, {lit(TODAY)})")
        self.assertEqual(g(0, "s"), "01-09-2026")
        self.assertEqual(g(0, "dur"), "50")
        self.assertEqual((g(2, "e"), g(2, "dur"), g(2, "pct")), ("", "", ""), "a milestone has one date and no percentage")
        self.assertEqual(g(2, "t"), "Milestone")
        self.assertEqual([g(i, "st") for i in (0, 4, 5, 6)], ["Done", "In progress", "In progress", "Not started"])
        self.assertEqual(self.val(f"K.statusOf({lit({**LINES[4], 'e': '2026-11-01'})}, {lit(TODAY)})"), "Late")
        self.assertEqual(g(4, "dep"), "GNT-003")
        self.assertEqual((g(4, "show"), g(0, "show")), ("No", "Yes"))

    def test_parsing_a_date(self):
        p = lambda t: self.val(f"K.parseDate({lit(t)})")
        self.assertEqual((p("06-11-2026"), p("6/11/2026"), p("2026-11-06")), ("2026-11-06",) * 3)
        self.assertIsNone(p("31-02-2026"))
        self.assertIsNone(p("tomorrow"))
        self.assertIsNone(p(""))
        self.assertEqual(self.val("K.formatDate('2027-01-05')"), "05-01-2027")

    def test_a_start_after_what_it_depends_on_ends_is_a_clash(self):
        early = [{**LINES[4], "s": "2026-10-10"}]
        self.assertEqual(self.val(f"K.clashes({lit(LINES[:3] + early)})"), {"GNT-005": ["GNT-003"]})
        self.assertEqual(self.val(f"K.clashes({lit(LINES)})"), {"GNT-006": ["GNT-005"]})

    # ── refusals, in plain words ──

    def test_a_bad_date_is_refused(self):
        self.assertEqual(self.err(0, "s", "31-13-2026"), "Use DD-MM-YYYY, for example 06-11-2026.")
        self.assertEqual(self.err(0, "e", "soon"), "Use DD-MM-YYYY, for example 06-11-2026.")
        self.assertEqual(self.err(0, "bs", "x"), "Baseline start: use DD-MM-YYYY.")

    def test_the_end_cannot_be_before_the_start(self):
        self.assertEqual(self.err(0, "e", "01-08-2026"), "The end cannot be before the start.")
        self.assertEqual(self.err(0, "s", "21-10-2026"), "The end cannot be before the start.")
        got = self.set(0, "e", "31-12-2026")
        self.assertEqual((got["error"], got["lines"][0]["e"]), ("", "2026-12-31"))

    def test_done_must_be_0_to_100(self):
        for bad in ("101", "-1", "", "lots"):
            self.assertEqual(self.err(3, "pct", bad), "Done % is a number from 0 to 100.", bad)
        self.assertEqual(self.set(3, "pct", "45%")["lines"][3]["pct"], 45)
        self.assertEqual(self.set(3, "pct", "100")["lines"][3]["pct"], 100)

    def test_depends_on_must_name_lines_that_exist(self):
        self.assertEqual(self.err(4, "dep", "GNT-003, GNT-099"), 'There is no line "GNT-099" to depend on.')
        self.assertEqual(self.err(4, "dep", "GNT-005"), 'There is no line "GNT-005" to depend on.', "a line cannot wait for itself")
        self.assertEqual(self.set(4, "dep", "GNT-001, GNT-003")["lines"][4]["dep"], ["GNT-001", "GNT-003"])
        self.assertEqual(self.set(4, "dep", "")["lines"][4]["dep"], [])

    def test_the_parent_must_be_a_phase_that_exists(self):
        self.assertEqual(self.err(4, "par", "GNT-099"), 'There is no line "GNT-099" to be the parent.')
        self.assertIn("is not a phase", self.err(4, "par", "GNT-002"))
        self.assertEqual(self.set(4, "par", "GNT-001")["lines"][4]["par"], "GNT-001")

    def test_a_milestone_has_one_date(self):
        self.assertEqual(self.err(2, "e", "25-10-2026"), "A milestone has one date: change Start.")
        got = self.set(2, "s", "25-10-2026")["lines"][2]
        self.assertEqual((got["s"], got["e"]), ("2026-10-25", "2026-10-25"))
        turned = self.set(1, "t", "Milestone")["lines"][1]
        self.assertEqual((turned["t"], turned["e"]), ("m", turned["s"]))

    def test_worked_out_cells_cannot_be_typed_over(self):
        self.assertEqual(self.err(0, "st", "Done"), "Status is worked out; it cannot be typed over.")
        self.assertEqual(self.err(0, "dur", "3"), "Days is worked out; it cannot be typed over.")
        self.assertEqual(self.err(0, "id", "GNT-100"), "ID is worked out; it cannot be typed over.")

    def test_a_line_needs_a_name_and_choices_must_be_on_the_list(self):
        self.assertEqual(self.err(0, "n", "  "), "A line needs a name.")
        self.assertEqual(self.err(0, "rag", "Purple"), "Health: choose Green, Amber, Red.")
        self.assertEqual(self.set(0, "rag", "amber")["lines"][0]["rag"], "Amber")
        self.assertEqual(self.set(0, "t", "p")["lines"][0]["t"], "p", "one letter picks a type")
        self.assertFalse(self.set(0, "show", "No")["lines"][0]["show"])
        self.assertEqual(self.err(0, "cost", "-4"), "Effort and budget are numbers, zero or more.")      # the server's own sentence (store.GANTT_BAD_NUMBER) for a number it would refuse
        self.assertEqual(self.err(0, "cost", "lots"), "Effort and budget are numbers, zero or more.", "a word is not a number either")
        self.assertEqual(self.set(0, "cost", "1,500")["lines"][0]["cost"], 1500)
        self.assertEqual(self.set(0, "bs", "")["lines"][0]["bs"], "")

    def test_a_refusal_changes_nothing(self):
        self.assertEqual(self.val(f"K.setField({lit(LINES)}, 0, 's', 'nope').lines.length"), len(LINES))
        self.assertTrue(self.val(f"(function(){{ const a = {lit(LINES)}; return K.setField(a, 0, 's', 'nope').lines === a; }})()"))

    # ── lines ──

    def test_a_new_line_gets_the_next_free_id_and_is_not_on_the_dashboard(self):
        got = self.val(f"K.addLine({lit(LINES)}, 'GNT-004', 't')")
        self.assertEqual((got["id"], got["index"]), ("GNT-008", 4))
        self.assertFalse(got["lines"][4]["show"])
        self.assertEqual(got["lines"][4]["n"], "New task")
        m = self.val(f"K.addLine({lit(LINES)}, 'GNT-001', 'm')")["lines"][1]
        self.assertEqual((m["t"], m["s"], m["e"]), ("m", "2026-09-01", "2026-09-01"))
        self.assertEqual(self.val("K.nextId([{id: 'GNT-009'}, {id: 'X-3'}])"), "GNT-010")
        self.assertEqual(self.val("K.nextId([])"), "GNT-001")

    def test_deleting_lets_go_of_what_pointed_at_them(self):
        got = self.val(f"K.deleteLines({lit(LINES)}, ['GNT-003', 'GNT-004'])")
        self.assertEqual([x["id"] for x in got], ["GNT-001", "GNT-002", "GNT-005", "GNT-006", "GNT-007"])
        self.assertEqual(got[2]["par"], "")
        self.assertEqual(got[2]["dep"], [])

    def test_rows_hidden_by_the_filter_or_the_eye_keep_their_own_numbers(self):
        v = lambda **o: self.val(f"K.visibleRows({lit(LINES)}, {lit(o)})")
        self.assertEqual(v(edit=True), list(range(7)))
        self.assertEqual(v(edit=False), [0, 2, 3, 6], "View draws only lines on the dashboard")
        self.assertEqual(v(edit=True, filter="phases"), [0, 3, 6])
        self.assertEqual(v(edit=True, filter="phasesMilestones"), [0, 2, 3, 6])
        self.assertEqual(v(edit=True, filter="ticked"), [0, 2, 3, 6])
        self.assertEqual(v(edit=False, filter="ticked"), [])

    # ── copy and paste ──

    def cols(self, *keys):
        return self.val(f"{lit(list(keys))}.map((k) => K.COLUMNS.find((c) => c.key === k))")

    def test_copy_gives_tab_separated_text(self):
        cols = self.cols("n", "s", "pct")
        text = self.val(f"K.toTSV({lit(LINES)}, [0, 1, 2], {lit(cols)}, K.makeSel(0, 0, 2, 2), {lit(TODAY)})")
        self.assertEqual(text.split("\n")[0], "Discovery\t01-09-2026\t100")
        self.assertEqual(text.split("\n")[2], "Records audit complete\t20-10-2026\t")
        self.assertEqual(len(text.split("\n")), 3)

    def test_a_cell_with_a_tab_or_a_quote_is_quoted_and_comes_back_the_same(self):
        odd = [{**LINES[0], "n": 'He said "go"\tnow\nthen'}]
        text = self.val(f"K.toTSV({lit(odd)}, [0], {lit(self.cols('n'))}, K.makeSel(0, 0), '')")
        self.assertEqual(text, '"He said ""go""\tnow\nthen"')
        self.assertEqual(self.val(f"K.parseTSV({lit(text)})"), [['He said "go"\tnow\nthen']])

    def test_pasted_text_from_excel_is_split_into_rows_and_cells(self):
        self.assertEqual(self.val("K.parseTSV('a\\tb\\r\\nc\\td\\r\\n')"), [["a", "b"], ["c", "d"]])
        self.assertEqual(self.val("K.parseTSV('one')"), [["one"]])
        self.assertEqual(self.val("K.parseTSV('')"), [])
        self.assertEqual(self.val("K.parseTSV('a\\t\\tc')"), [["a", "", "c"]])

    def paste(self, matrix, sel, keys=("n", "s", "pct"), rows=None, lines=LINES):
        rows = list(range(len(lines))) if rows is None else rows
        return self.val(f"K.pasteCells({lit(lines)}, {lit(rows)}, {lit(self.cols(*keys))}, {sel}, {lit(matrix)})")

    def test_pasting_a_block_lands_where_the_selection_starts(self):
        got = self.paste([["Alpha", "02-10-2026"], ["Beta", "03-10-2026"]], "K.makeSel(1, 0)", keys=("n", "s"))
        self.assertEqual((got["ok"], got["bad"], got["added"]), (4, 0, []))
        self.assertEqual([(x["n"], x["s"]) for x in got["lines"][1:3]], [("Alpha", "2026-10-02"), ("Beta", "2026-10-03")])

    def test_pasting_past_the_last_line_adds_lines(self):
        got = self.paste([["Alpha"], ["Beta"], ["Gamma"]], "K.makeSel(6, 0)", keys=("n",))
        self.assertEqual(got["added"], ["GNT-008", "GNT-009"])
        self.assertEqual([x["n"] for x in got["lines"][6:]], ["Alpha", "Beta", "Gamma"])
        self.assertEqual([x["id"] for x in got["lines"]][-2:], ["GNT-008", "GNT-009"])

    def test_one_pasted_value_fills_the_whole_selection(self):
        got = self.paste([["Sam Example"]], "K.makeSel(0, 0, 2, 0)", keys=("o",))
        self.assertEqual([x["o"] for x in got["lines"][:3]], ["Sam Example"] * 3)

    def test_a_pasted_value_that_is_refused_is_counted_and_the_rest_still_land(self):
        got = self.paste([["Alpha", "not a date", "50"]], "K.makeSel(1, 0)")
        self.assertEqual((got["ok"], got["bad"], got["first"]), (2, 1, "Use DD-MM-YYYY, for example 06-11-2026."))
        self.assertEqual((got["lines"][1]["n"], got["lines"][1]["s"], got["lines"][1]["pct"]), ("Alpha", "2026-09-01", 50))

    def test_pasting_skips_worked_out_columns(self):
        got = self.paste([["x", "y"]], "K.makeSel(0, 0)", keys=("dur", "n"))
        self.assertEqual((got["ok"], got["lines"][0]["n"]), (1, "y"))

    def test_pasting_with_lines_hidden_by_the_filter_lands_on_the_lines_shown(self):
        got = self.paste([["A"], ["B"]], "K.makeSel(0, 0)", keys=("n",), rows=[0, 3, 6])
        self.assertEqual([x["n"] for x in got["lines"]][:7], ["A", "Scan paper files", "Records audit complete", "B", "Staff training", "Move applications", "Go-live"])

    # ── clear and fill ──

    def test_clearing_counts_the_cells_that_need_a_value(self):
        cols = self.cols("n", "o", "dur")
        got = self.val(f"K.clearCells({lit(LINES)}, [0, 3], {lit(cols)}, K.makeSel(0, 0, 1, 2))")
        self.assertEqual((got["ok"], got["bad"]), (2, 2), "owners cleared, names refused, Days skipped")
        self.assertEqual((got["lines"][0]["o"], got["lines"][0]["n"]), ("", "Discovery"))

    def test_fill_down_copies_the_top_row_down(self):
        rows = [3, 4, 5]
        got = self.val(f"K.fillDown({lit(LINES)}, {lit(rows)}, {lit(self.cols('o', 'pct'))}, K.makeSel(0, 0, 2, 1), {lit(TODAY)})")
        self.assertEqual(got["ok"], 4)
        self.assertEqual([x["o"] for x in got["lines"][3:6]], ["Sam Example"] * 3)
        self.assertEqual([x["pct"] for x in got["lines"][3:6]], [30, 30, 30])

    def test_fill_right_copies_the_left_column_across(self):
        got = self.val(f"K.fillRight({lit(LINES)}, [0, 1], {lit(self.cols('s', 'e'))}, K.makeSel(0, 0, 1, 1), {lit(TODAY)})")
        self.assertEqual(got["ok"], 2)
        self.assertEqual((got["lines"][0]["e"], got["lines"][0]["s"]), ("2026-09-01", "2026-09-01"))

    def test_the_fill_handle_repeats_the_block_under_itself(self):
        got = self.val(f"K.fillTo({lit(LINES)}, [0, 1, 2, 3, 4], {lit(self.cols('o'))}, K.makeSel(0, 0, 1, 0), 4, {lit(TODAY)})")
        self.assertEqual([x["o"] for x in got["lines"][:5]], ["Ada Example", "", "Ada Example", "", "Ada Example"])

    # ── undo ──

    def test_many_steps_of_undo_and_redo(self):
        v = self.val("""(function () {
            let h = K.emptyHistory();
            h = K.record(h, 'a'); h = K.record(h, 'b'); h = K.record(h, 'c');          // three steps made: a, b, c were the states before them
            const one = K.undo(h, 'd'); const two = K.undo(one.history, one.lines); const three = K.undo(two.history, two.lines);
            const none = K.undo(three.history, three.lines);
            const back = K.redo(three.history, three.lines);
            const fresh = K.record(back.history, back.lines);                           // a new step ends the redo trail
            return { one: one.lines, two: two.lines, three: three.lines, none: none.lines, back: back.lines, trail: K.redo(fresh, 'x').lines };
        })()""")
        self.assertEqual((v["one"], v["two"], v["three"], v["none"], v["back"], v["trail"]), ("c", "b", "a", None, "b", None))

    def test_undo_remembers_at_most_100_steps(self):
        self.assertEqual(self.val("(function(){ let h = K.emptyHistory(); for (let i = 0; i < 130; i++) h = K.record(h, i); return [h.past.length, h.past[0]]; })()"), [100, 30])

    # ── selection maths ──

    def test_a_range_is_the_same_whichever_way_it_was_dragged(self):
        self.assertEqual(self.val("K.rangeOf(K.makeSel(4, 5, 1, 2))"), {"r0": 1, "r1": 4, "c0": 2, "c1": 5})
        self.assertEqual(self.val("K.cellCount(K.makeSel(4, 5, 1, 2))"), 16)
        self.assertEqual(self.val("[K.inRange(K.makeSel(1, 1, 3, 3), 2, 2), K.inRange(K.makeSel(1, 1, 3, 3), 4, 2)]"), [True, False])

    def test_arrow_keys_stay_inside_the_table_and_shift_extends(self):
        mv = lambda s, dr, dc, **o: self.val(f"K.moveSel({s}, {dr}, {dc}, {lit({'rows': 5, 'cols': 4, **o})})")
        self.assertEqual(mv("K.makeSel(0, 0)", -1, 0), {"ar": 0, "ac": 0, "fr": 0, "fc": 0})
        self.assertEqual(mv("K.makeSel(4, 3)", 1, 1), {"ar": 4, "ac": 3, "fr": 4, "fc": 3})
        self.assertEqual(mv("K.makeSel(1, 1)", 1, 0, extend=True), {"ar": 1, "ac": 1, "fr": 2, "fc": 1})
        self.assertEqual(mv("K.makeSel(1, 1)", 1, 0, edge=True), {"ar": 4, "ac": 1, "fr": 4, "fc": 1})
        self.assertEqual(mv("K.makeSel(2, 2)", 0, -1, edge=True), {"ar": 2, "ac": 0, "fr": 2, "fc": 0})

    def test_home_end_headers_and_select_all(self):
        self.assertEqual(self.val("K.homeSel(K.makeSel(3, 2), false)"), {"ar": 3, "ac": 0, "fr": 3, "fc": 0})
        self.assertEqual(self.val("K.homeSel(K.makeSel(3, 2), true)"), {"ar": 0, "ac": 0, "fr": 0, "fc": 0})
        self.assertEqual(self.val("K.endSel(K.makeSel(3, 2), false, 5, 4)"), {"ar": 3, "ac": 3, "fr": 3, "fc": 3})
        self.assertEqual(self.val("K.endSel(K.makeSel(3, 2), true, 5, 4)"), {"ar": 4, "ac": 3, "fr": 4, "fc": 3})
        self.assertEqual(self.val("K.selectRow(K.makeSel(0, 0), 2, 4, false)"), {"ar": 2, "ac": 0, "fr": 2, "fc": 3})
        self.assertEqual(self.val("K.selectColumn(K.makeSel(0, 0), 2, 5, false)"), {"ar": 0, "ac": 2, "fr": 4, "fc": 2})
        self.assertEqual(self.val("K.selectAll(5, 4)"), {"ar": 0, "ac": 0, "fr": 4, "fc": 3})

    def test_tab_wraps_and_at_the_last_cell_asks_for_a_new_line(self):
        t = lambda s, back=False: self.val(f"K.tabNext({s}, {lit(back)}, 3, 4)")
        self.assertEqual(t("K.makeSel(0, 1)")["sel"], {"ar": 0, "ac": 2, "fr": 0, "fc": 2})
        self.assertEqual(t("K.makeSel(0, 3)")["sel"], {"ar": 1, "ac": 0, "fr": 1, "fc": 0})
        self.assertEqual(t("K.makeSel(1, 0)", True)["sel"], {"ar": 0, "ac": 3, "fr": 0, "fc": 3})
        last = t("K.makeSel(2, 3)")
        self.assertTrue(last["addLine"])
        self.assertFalse(t("K.makeSel(0, 0)", True)["addLine"])
        self.assertEqual(self.val("K.enterNext(K.makeSel(2, 1), false, 3)"), {"ar": 2, "ac": 1, "fr": 2, "fc": 1})
        self.assertEqual(self.val("K.enterNext(K.makeSel(1, 1), true, 3)"), {"ar": 0, "ac": 1, "fr": 0, "fc": 1})

    def test_a_selection_is_kept_inside_a_table_that_shrank(self):
        self.assertEqual(self.val("K.clampSel(K.makeSel(9, 9, 12, 20), 3, 4)"), {"ar": 2, "ac": 3, "fr": 2, "fc": 3})
        self.assertEqual(self.val("K.clampSel(K.makeSel(1, 1), 0, 0)"), {"ar": 0, "ac": 0, "fr": 0, "fc": 0})

    # ── widths and zoom ──

    def test_fit_width_follows_the_longest_text_between_56_and_420(self):
        self.assertEqual(self.val("K.fitWidth('ID', ['1'], false)"), 56)
        self.assertEqual(self.val("K.fitWidth('Line', ['x'.repeat(100)], true)"), 420)
        self.assertEqual(self.val("K.fitWidth('Owner', ['Sam Example'], false)"), 101)

    def test_zoom_runs_from_50_to_200_percent(self):
        self.assertEqual(self.val("[K.clampZoom(0.1), K.clampZoom(5), K.clampZoom(1.2345)]"), [0.5, 2, 1.23])


if __name__ == "__main__":
    unittest.main()

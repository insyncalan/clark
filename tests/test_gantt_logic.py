"""#926, the Gantt chart's rules (src/clark/page/src/gantt/logic/gantt.js): dates, the outline numbers, clashes, status, the scales and zoom,
the rows to show, and what a typed change means. Nothing here draws anything. Fictional data.

Run: python3 dev/run_tests.py test_gantt_logic
The repo has no Node, so the logic runs inside headless Chrome (as test_tracker_logic does). Chrome is required: these tests fail, never skip,
without it.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "gantt_demo.jsx"
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = build_page.page_css().replace("</style", "<\\/style")   # the chart's looks live in the shell's CSS, so the bare page carries it too
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title><style>{css}</style></head>'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


def ln(id, name, type, start, end, pct=0, parent="", depends=(), show=False):
    return {"id": id, "name": name, "type": type, "parent": parent, "start": start, "end": end, "pct": pct, "depends": list(depends), "show": show}


# Fictional. Three phases; "Move applications" starts before "Staff training" ends (a clash); the eye is on for the phases and milestones.
LINES = [
    ln("GNT-001", "Discovery", "phase", "2026-09-01", "2026-10-20", 100, show=True),
    ln("GNT-002", "Scan paper files", "task", "2026-09-01", "2026-10-14", 100, "GNT-001"),
    ln("GNT-003", "Records audit complete", "milestone", "2026-10-20", "2026-10-20", 100, "GNT-001", ["GNT-002"], True),
    ln("GNT-004", "Migration", "phase", "2026-10-22", "2027-02-26", 30, show=True),
    ln("GNT-005", "Staff training", "task", "2026-10-22", "2026-12-04", 60, "GNT-004", ["GNT-003"]),
    ln("GNT-006", "Move applications", "task", "2026-11-20", "2027-02-12", 20, "GNT-004", ["GNT-005"]),
    ln("GNT-007", "Pilot office live", "milestone", "2026-12-18", "2026-12-18", 0, "GNT-004", ["GNT-005"], True),
    ln("GNT-008", "Go-live", "phase", "2027-02-15", "2027-05-28", 0, show=True),
    ln("GNT-009", "Cut-over rehearsal", "task", "2027-02-15", "2027-03-26", 0, "GNT-008", ["GNT-006"]),
    ln("GNT-010", "Supplier contract signed", "task", "2027-03-01", "2027-04-09", 0, "GNT-008"),
    ln("GNT-011", "Full roll-out", "milestone", "2027-05-28", "2027-05-28", 0, "GNT-008", ["GNT-009"], True),
]
TODAY = "2026-11-06"


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.K && window.K.gantt)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def g(self, call):
        return self.val(f"K.gantt.{call}")

    def ids(self, **opts):
        return self.g(f"visibleRows({lit(LINES)}, {lit(opts)}).map(l => l.id)")

    # ── dates ────────────────────────────────────────────────────────────────

    def test_dates_are_shown_day_month_year_and_stored_year_month_day(self):
        self.assertEqual(self.g('formatDate("2026-11-06")'), "06-11-2026")
        self.assertEqual(self.g('parseDate("06-11-2026")'), "2026-11-06")
        self.assertEqual(self.g('parseDate(" 6-1-2027 ")'), "2027-01-06")
        self.assertEqual(self.g('formatDate("")'), "")

    def test_a_date_that_is_not_real_is_refused(self):
        for text in ("31-02-2026", "2026-11-06", "06/11/2026", "", "1-1-1999", "32-01-2026", "tomorrow"):
            self.assertIsNone(self.g(f"parseDate({lit(text)})"), text)

    def test_day_maths_crosses_months_and_leap_days(self):
        self.assertEqual(self.g('addDays("2027-02-26", 3)'), "2027-03-01")
        self.assertEqual(self.g('addDays("2028-02-28", 1)'), "2028-02-29")
        self.assertEqual(self.g('daysBetween("2026-09-01", "2026-10-01")'), 30)
        self.assertEqual(self.g('spanDays({type: "task", start: "2026-11-02", end: "2026-11-02"})'), 1)
        self.assertEqual(self.g('spanDays({type: "milestone", start: "2026-11-02", end: "2030-01-01"})'), 1)

    # ── outline numbers ──────────────────────────────────────────────────────

    def test_outline_numbers_phases_tasks_and_milestones(self):
        no = self.g(f"outline({lit(LINES)})")
        self.assertEqual([no[f"GNT-0{n:02d}"] for n in range(1, 12)], ["1", "1.1", "M-1", "2", "2.1", "2.2", "M-2", "3", "3.1", "3.2", "M-3"])

    def test_a_task_with_no_phase_is_numbered_on_its_own(self):
        lone = [ln("GNT-001", "Alone", "task", "2026-11-02", "2026-11-03"), ln("GNT-002", "Also alone", "task", "2026-11-02", "2026-11-03", parent="GNT-099")]
        self.assertEqual(self.g(f"outline({lit(lone)})"), {"GNT-001": "T-1", "GNT-002": "T-2"})

    def test_adding_a_phase_renumbers_what_is_after_it_and_dependencies_follow(self):
        made = self.val(f'(function(){{ const r = K.gantt.addBelow({lit(LINES)}, "GNT-005", "phase"); return {{ids: r.lines.map(l => l.id), line: r.line, rows: K.gantt.renumber(r.lines)}}; }})()')
        self.assertEqual(made["line"]["id"], "GNT-012")
        self.assertEqual(made["ids"].index("GNT-012") + 1, made["ids"].index("GNT-008"), "a new phase goes in after the last line of the phase above it")
        by = {r["id"]: r for r in made["rows"]}
        self.assertEqual((by["GNT-012"]["no"], by["GNT-008"]["no"], by["GNT-009"]["no"]), ("3", "4", "4.1"))
        self.assertEqual(by["GNT-011"]["dependsNo"], ["4.1"], "the roll-out still depends on the cut-over, which is now 4.1")
        self.assertEqual(by["GNT-009"]["parentNo"], "4")
        self.assertEqual(by["GNT-011"]["depends"], ["GNT-009"], "the stored id never changes")

    def test_a_task_added_below_a_phase_is_its_first_task(self):
        r = self.val(f'(function(){{ const r = K.gantt.addBelow({lit(LINES)}, "GNT-004", "task"); return {{line: r.line, no: K.gantt.outline(r.lines)}}; }})()')
        self.assertEqual((r["line"]["parent"], r["line"]["start"], r["line"]["end"], r["line"]["show"]), ("GNT-004", "2027-02-26", "2027-03-11", False))
        self.assertEqual((r["no"]["GNT-012"], r["no"]["GNT-005"], r["no"]["GNT-006"]), ("2.1", "2.2", "2.3"))

    def test_a_milestone_added_has_one_date(self):
        line = self.val(f'K.gantt.addBelow({lit(LINES)}, "GNT-005", "milestone").line')
        self.assertEqual((line["start"], line["end"], line["parent"]), ("2026-12-04", "2026-12-04", "GNT-004"))

    def test_the_next_free_id(self):
        self.assertEqual(self.g(f"nextId({lit(LINES)})"), "GNT-012")
        self.assertEqual(self.g("nextId([])"), "GNT-001")

    # ── clash and status ─────────────────────────────────────────────────────

    def test_a_line_that_starts_before_what_it_depends_on_ends_is_a_clash(self):
        self.assertEqual(self.g(f"clashes({lit(LINES)})"), {"GNT-006": ["GNT-005"]})

    def test_starting_the_day_it_ends_is_not_a_clash_but_a_day_earlier_is(self):
        a = ln("A", "First", "task", "2026-11-02", "2026-11-10")
        self.assertEqual(self.g(f'clashes({lit([a, ln("B", "Second", "task", "2026-11-10", "2026-11-12", depends=["A"])])})'), {})
        self.assertEqual(self.g(f'clashes({lit([a, ln("B", "Second", "task", "2026-11-09", "2026-11-12", depends=["A"])])})'), {"B": ["A"]})

    def test_a_milestone_ends_on_its_one_date(self):
        m = ln("M", "Sign-off", "milestone", "2026-11-10", "2026-11-10")
        self.assertEqual(self.g(f'clashes({lit([m, ln("B", "After", "task", "2026-11-08", "2026-11-12", depends=["M"])])})'), {"B": ["M"]})

    def test_a_dependency_on_a_line_that_is_gone_is_not_a_clash(self):
        self.assertEqual(self.g(f'clashes({lit([ln("B", "After", "task", "2026-11-08", "2026-11-12", depends=["GONE"])])})'), {})

    def test_status_done_late_in_progress_not_started(self):
        def st(**kw):
            return self.g(f"statusOf({lit(ln('X', 'x', kw.pop('type', 'task'), kw.pop('start'), kw.pop('end'), kw.pop('pct', 0)))}, {lit(TODAY)})")
        self.assertEqual(st(start="2026-09-01", end="2026-10-14", pct=100), "done")
        self.assertEqual(st(start="2026-09-01", end="2026-10-14", pct=100, type="milestone"), "done")
        self.assertEqual(st(start="2026-09-01", end="2026-10-14", pct=40), "late")
        self.assertEqual(st(start="2026-09-01", end="2026-10-14"), "late")
        self.assertEqual(st(start="2026-11-01", end="2026-11-30", pct=0), "inprogress")
        self.assertEqual(st(start="2026-11-20", end="2026-11-30", pct=10), "inprogress")
        self.assertEqual(st(start="2026-11-20", end="2026-11-30", pct=0), "notstarted")
        self.assertEqual(st(start="2026-12-18", end="2026-12-18", type="milestone"), "notstarted")
        self.assertEqual(st(start="2026-11-06", end="2026-11-06", type="milestone"), "notstarted", "a milestone today has not started or ended")
        self.assertEqual(st(start="2026-10-01", end="2026-11-05", type="milestone"), "late")

    def test_the_status_words(self):
        self.assertEqual([self.g(f"statusWord({lit(s)})") for s in ("done", "late", "inprogress", "notstarted")], ["Done", "Late", "In progress", "Not started"])

    # ── rows to show ─────────────────────────────────────────────────────────

    def test_a_line_with_no_usable_date_is_left_out_and_listed(self):
        lines = LINES + [ln("GNT-012", "No dates", "task", "", "garbage", show=True), ln("GNT-013", "Bad start", "phase", "nope", "2026-10-01", show=True)]
        self.assertEqual(self.g(f"tidyAll({lit(lines)}).length"), 11, "the chart still draws the dated lines only")
        self.assertEqual(self.g(f"leftOut({lit(lines)}).map(l => l.id)"), ["GNT-012", "GNT-013"], "the left-out list is exact")
        self.assertEqual(self.g(f"leftOut({lit(LINES)})"), [], "nothing is left out when every line has a date")

    def test_view_shows_only_the_lines_whose_eye_is_on(self):
        self.assertEqual(self.ids(edit=False, filter="all"), ["GNT-001", "GNT-003", "GNT-004", "GNT-007", "GNT-008", "GNT-011"])

    def test_edit_shows_every_line(self):
        self.assertEqual(len(self.ids(edit=True, filter="all")), 11)

    def test_the_filters(self):
        self.assertEqual(self.ids(edit=True, filter="phases"), ["GNT-001", "GNT-004", "GNT-008"])
        self.assertEqual(self.ids(edit=True, filter="milestones"), ["GNT-001", "GNT-003", "GNT-004", "GNT-007", "GNT-008", "GNT-011"])
        self.assertEqual(self.ids(edit=True, filter="ticked"), ["GNT-001", "GNT-003", "GNT-004", "GNT-007", "GNT-008", "GNT-011"])
        self.assertEqual(self.ids(edit=False, filter="phases"), ["GNT-001", "GNT-004", "GNT-008"])
        self.assertEqual(self.ids(edit=False, filter="nonsense"), self.ids(edit=False, filter="all"))

    def test_ticked_lines_is_an_edit_only_choice(self):
        self.assertEqual(self.g("filtersFor(true)"), ["all", "phases", "milestones", "ticked"])
        self.assertEqual(self.g("filtersFor(false)"), ["all", "phases", "milestones"])
        self.assertEqual([self.g(f"filterWord({lit(f)})") for f in ("all", "phases", "milestones", "ticked")],
                         ["All lines", "Phases only", "Phases and milestones", "Ticked lines"])

    def test_the_plan_height_is_in_rows_never_below_one_never_past_the_last(self):
        rs = lambda *a: self.g("rowsShown(" + ", ".join(lit(x) for x in a) + ")")
        self.assertEqual(rs(11, None, None, True), 11)
        self.assertEqual(rs(11, 5, None, True), 5)
        self.assertEqual(rs(11, 5, 8, True), 5, "in Edit the saved default is the height; a viewer's own choice is not used")
        self.assertEqual(rs(11, 5, 8, False), 8)
        self.assertEqual(rs(11, 5, None, False), 5)
        self.assertEqual(rs(11, 0, None, True), 1)
        self.assertEqual(rs(11, 50, None, True), 11)
        self.assertEqual(rs(11, 5, -3, False), 1)
        self.assertEqual(rs(0, 5, None, True), 0)

    def test_dragging_the_grip_moves_by_whole_rows(self):
        rd = lambda *a: self.g("rowsFromDrag(" + ", ".join(lit(x) for x in a) + ")")
        self.assertEqual(rd(5, 64, 32, 11), 7)
        self.assertEqual(rd(5, 50, 32, 11), 7)
        self.assertEqual(rd(5, 40, 32, 11), 6)
        self.assertEqual(rd(5, -500, 32, 11), 1)
        self.assertEqual(rd(5, 900, 32, 11), 11)

    # ── scales and zoom ──────────────────────────────────────────────────────

    def test_the_range_covers_every_line_and_today_and_is_never_under_six_months(self):
        self.assertEqual(self.g(f"chartRange({lit(LINES)}, {lit(TODAY)})"), {"start": "2026-09-01", "end": "2027-05-31"})
        short = [ln("A", "Short", "task", "2026-11-02", "2026-11-10")]
        self.assertEqual(self.g(f"chartRange({lit(short)}, {lit(TODAY)})"), {"start": "2026-11-01", "end": "2027-04-30"})
        self.assertEqual(self.g(f'chartRange({lit(short)}, "2027-09-15")'), {"start": "2026-11-01", "end": "2027-09-30"})
        self.assertIsNone(self.g(f"chartRange([], null)"))

    def test_a_plan_in_december_2100_still_has_a_range_and_a_header(self):
        # 2100 is the last accepted year, so the month after it (2101) is used for arithmetic and must not break it (it once hung the page).
        late = [ln("A", "Late", "task", "2100-10-01", "2100-12-31")]
        self.assertEqual(self.g(f'chartRange({lit(late)}, "2100-10-02")'), {"start": "2100-07-01", "end": "2100-12-31"})
        wide = [ln("A", "Long", "task", "2026-01-01", "2100-12-31")]
        rng = self.g(f'chartRange({lit(wide)}, {lit(TODAY)})')
        self.assertEqual(rng, {"start": "2026-01-01", "end": "2100-12-31"})
        for scale in ("week", "month", "quarter"):
            cells = self.g(f'headerCells("{scale}", {lit(rng)}, 2)')
            self.assertEqual(cells["upper"][-1]["iso"][:7], "2100-12" if scale != "quarter" else "2100-10", scale)

    def test_a_far_off_year_cannot_stretch_the_range(self):
        far = [ln("A", "Near", "task", "2026-11-02", "2026-11-10"), ln("B", "Far", "milestone", "5000-01-01", "5000-01-01")]
        self.assertEqual(self.g(f"chartRange({lit(far)}, {lit(TODAY)})"), {"start": "2026-11-01", "end": "2027-04-30"})
        self.assertEqual(self.g(f"tidyAll({lit(far)}).length"), 1)
        self.assertEqual(self.g(f"leftOut({lit(far)}).length"), 1)
        self.assertIsNone(self.g('dayNum("1999-12-31")'))

    def test_fit_gives_every_day_the_same_width_and_never_less_than_the_floor(self):
        rng = {"start": "2026-09-01", "end": "2027-05-31"}
        self.assertAlmostEqual(self.g(f"fitPpd(1006, {lit(rng)})"), 1000 / 273, places=6)
        self.assertEqual(self.g(f"fitPpd(100, {lit(rng)})"), 1.4)

    def test_zoom_never_goes_below_fit_or_past_the_top(self):
        self.assertEqual(self.g("clampZoom(0.5)"), 1)
        self.assertEqual(self.g("zoomOut(1)"), 1)
        self.assertEqual(self.g("zoomIn(1)"), 1.25)
        self.assertEqual(self.g("zoomOut(1.25)"), 1)
        self.assertEqual(self.g("zoomIn(8)"), 8)
        self.assertEqual(self.g("ppdFor('month', 3, 1)"), 3)
        self.assertEqual(self.g("ppdFor('month', 3, 0.2)"), 3)
        self.assertEqual(self.g("ppdFor('month', 3, 2)"), 6)
        self.assertEqual(self.g("ppdFor('quarter', 3, 2)"), 6)

    def test_week_draws_a_day_at_least_seven_pixels_wide(self):
        self.assertEqual(self.g("ppdFor('week', 3, 1)"), 7)
        self.assertEqual(self.g("ppdFor('week', 10, 2)"), 20)

    def test_a_date_sits_a_whole_number_of_days_from_the_start(self):
        self.assertEqual(self.g('xOf("2026-09-11", {start: "2026-09-01", end: "2027-05-31"}, 4)'), 40)

    def test_month_scale_header(self):
        rng = {"start": "2026-09-01", "end": "2027-05-31"}
        h = self.g(f"headerCells('month', {lit(rng)}, 3)")
        self.assertEqual([c["label"] for c in h["upper"]], ["Sep 26", "Oct 26", "Nov 26", "Dec 26", "Jan 27", "Feb 27", "Mar 27", "Apr 27", "May 27"])
        self.assertEqual(h["lower"], [], "the days are left out when they would be crowded")
        wide = self.g(f"headerCells('month', {lit(rng)}, 4)")
        self.assertEqual([c["label"] for c in wide["lower"][:5]], ["01", "08", "15", "22", "01"])

    def test_quarter_scale_header(self):
        rng = {"start": "2026-09-01", "end": "2027-05-31"}
        h = self.g(f"headerCells('quarter', {lit(rng)}, 3)")
        self.assertEqual([c["label"] for c in h["upper"]], ["Q3 2026", "Q4 2026", "Q1 2027", "Q2 2027"])
        self.assertEqual([c["label"] for c in h["lower"]], ["Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"])
        self.assertEqual(h["upper"][-1]["to"], "2027-06-01")

    def test_week_scale_header_starts_on_a_monday(self):
        rng = {"start": "2026-09-01", "end": "2027-05-31"}
        h = self.g(f"headerCells('week', {lit(rng)}, 7)")
        self.assertEqual([c["iso"] for c in h["lower"][:3]], ["2026-09-07", "2026-09-14", "2026-09-21"])
        self.assertEqual(h["lower"][0]["label"], "07")

    # ── arrows and changes ───────────────────────────────────────────────────

    def test_a_forward_arrow_is_one_elbow_and_a_clash_goes_round_through_the_gap(self):
        self.assertEqual(self.g("arrowPath(100, 16, 200, 48, 32).d"), "M100 16 H108 V48 H196")
        self.assertEqual(self.g("arrowPath(200, 16, 100, 48, 32).d"), "M200 16 H208 V32 H88 V48 H96")
        self.assertEqual(self.g("arrowPath(200, 48, 100, 16, 32).d"), "M200 48 H208 V32 H88 V16 H96")

    def test_moving_a_bar_keeps_its_length_and_a_milestone_moves_its_one_date(self):
        task = ln("A", "x", "task", "2026-10-22", "2026-12-04")
        self.assertEqual(self.g(f"moved({lit(task)}, 3)"), {"start": "2026-10-25", "end": "2026-12-07"})
        self.assertEqual(self.g(f"moved({lit(task)}, -22)"), {"start": "2026-09-30", "end": "2026-11-12"})
        ms = ln("M", "x", "milestone", "2026-12-18", "2026-12-18")
        self.assertEqual(self.g(f"moved({lit(ms)}, -2)"), {"start": "2026-12-16", "end": "2026-12-16"})

    def test_stretching_a_bar_moves_only_its_end_and_never_before_its_start(self):
        task = ln("A", "x", "task", "2026-10-22", "2026-12-04")
        self.assertEqual(self.g(f"resized({lit(task)}, 6)"), {"start": "2026-10-22", "end": "2026-12-10"})
        self.assertEqual(self.g(f"resized({lit(task)}, -400)"), {"start": "2026-10-22", "end": "2026-10-22"})
        ms = ln("M", "x", "milestone", "2026-12-18", "2026-12-18")
        self.assertEqual(self.g(f"resized({lit(ms)}, 5)"), {"start": "2026-12-18", "end": "2026-12-18"})

    def test_typed_changes_and_the_words_of_a_refusal(self):
        task = ln("A", "Staff training", "task", "2026-10-22", "2026-12-04", 60)
        ms = ln("M", "Pilot live", "milestone", "2026-12-18", "2026-12-18")
        ce = lambda line, field, text: self.g(f"checkEdit({lit(line)}, {lit(field)}, {lit(text)})")
        self.assertEqual(ce(task, "name", "  Train staff "), {"ok": True, "field": "name", "value": "Train staff"})
        self.assertEqual(ce(task, "name", "  ")["message"], "A line needs a name.")
        self.assertEqual(ce(task, "pct", "75%"), {"ok": True, "field": "pct", "value": 75})
        for bad in ("101", "-1", "abc", "", "7.5", "1e1", "0x10", "12.0"):
            self.assertEqual(ce(task, "pct", bad)["message"], "Done % is a number from 0 to 100.", bad)
        self.assertEqual(ce(task, "start", "01-11-2026"), {"ok": True, "field": "dates", "value": {"start": "2026-11-01", "end": "2026-12-04"}})
        self.assertEqual(ce(task, "end", "01-12-2026")["value"], {"start": "2026-10-22", "end": "2026-12-01"})
        self.assertEqual(ce(task, "start", "05-12-2026")["message"], "The end cannot be before the start.")
        self.assertEqual(ce(task, "end", "21-10-2026")["message"], "The end cannot be before the start.")
        self.assertEqual(ce(task, "start", "2026-11-01")["message"], "Use DD-MM-YYYY, for example 06-11-2026.")
        self.assertEqual(ce(ms, "start", "20-12-2026")["value"], {"start": "2026-12-20", "end": "2026-12-20"})
        self.assertEqual(ce(ms, "end", "20-12-2026")["message"], "A milestone has one date: change Start.")

    def test_the_edit_box_sends_only_what_changed_and_refuses_in_words(self):
        task = ln("A", "Staff training", "task", "2026-10-22", "2026-12-04", 60)
        form = {"name": "Staff training", "start": "22-10-2026", "end": "04-12-2026", "pct": "60"}
        cb = lambda f: self.g(f"checkBox({lit(task)}, {lit(f)})")
        self.assertEqual(cb(form), {"ok": True, "changes": []})
        self.assertEqual(cb({**form, "pct": "80", "end": "10-12-2026"})["changes"],
                         [{"field": "dates", "value": {"start": "2026-10-22", "end": "2026-12-10"}}, {"field": "pct", "value": 80}])
        bad = cb({**form, "end": "01-10-2026"})
        self.assertEqual((bad["ok"], bad["field"], bad["message"]), (False, "end", "The end cannot be before the start."))
        self.assertEqual(cb({**form, "start": "soon"})["field"], "start")
        self.assertEqual(cb({**form, "name": ""})["message"], "A line needs a name.")

    def test_a_drag_cannot_leave_the_accepted_years_and_one_day_is_singular(self):
        t = ln("A", "x", "task", "2100-12-30", "2100-12-31")
        self.assertEqual(self.g(f"moved({lit(t)}, 5)"), {"start": "2100-12-30", "end": "2100-12-31"})
        self.assertEqual(self.g(f"resized({lit(t)}, 5)"), {"start": "2100-12-30", "end": "2100-12-31"})
        one = ln("B", "x", "task", "2026-01-01", "2026-01-01")
        self.assertEqual(self.g(f"detailOf({lit(one)}, {lit([one])}, {lit(TODAY)})")["when"], "01-01-2026 to 01-01-2026 (1 day)")

    def test_the_words_under_a_selected_line(self):
        d = self.g(f"detailOf({lit(LINES[5])}, {lit(LINES)}, {lit(TODAY)})")
        self.assertEqual((d["title"], d["kind"], d["pct"], d["status"], d["shown"]), ("2.2 Move applications", "Task", 20, "In progress", False))
        self.assertEqual((d["when"], d["depends"], d["clash"]), ("20-11-2026 to 12-02-2027 (85 days)", ["2.1"], "Starts before 2.1 ends"))
        m = self.g(f"detailOf({lit(LINES[2])}, {lit(LINES)}, {lit(TODAY)})")
        self.assertEqual((m["when"], m["clash"], m["status"]), ("20-10-2026", "", "Done"))


if __name__ == "__main__":
    unittest.main()

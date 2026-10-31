"""#68 / #81, the Work items board's pure logic (src/clark/page/src/logic/board.js; spec docs/handoff/design-68-81-board.md):
Group by -> columns and swimlanes, the card, `moveFor` with every refusal in the spec's table, and the remembered state. No page
code is tested here: there is none yet. The key check is the last class: every request the logic produces is accepted by
changes.make_change for a real demo store (and undone), and every refusal is the logic's own words.

Run: python3 dev/run_tests.py test_board
The repo has no Node, so the logic runs inside headless Chrome (as test_picker_minimap does): bundled with the pinned esbuild
into a temporary folder, put on a page the harness server serves. Chrome is required: these tests fail, never skip, without it.
The server does not yet know the place "board" (#126), so the logic's one PLACE constant is "cell" until then; the tests follow
changes.PLACES.
"""
import contextlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark import changes  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "board_demo.js"
TODAY = "2026-10-29"        # a Thursday: this week ends Sunday 01-11-2026
ME = "Sara Khan"
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
        _PAGE["html"] = ('<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


def make_data():
    """A DemoStore with every kind of work item, and the data the page gets for it."""
    demo = DemoStore()
    s = demo.store
    with s.step("dashboard", USER) as st:
        st.create("workstreams", {"project": "ABC", "name": "Data", "source": "demo"})
        ms2 = st.create("milestones", {"project": "ABC", "name": "Go live", "baseline_date": "2030-06-01", "source": "demo"})
        base = {"project": "ABC", "raised": "2026-10-01", "source": "demo"}
        for n, vals in enumerate([
            dict(description="Draft the cut-over plan", workstream="Build", owner=ME, priority="High", due_date="2026-10-20", milestone=demo.milestone),
            dict(description="Book the training room", owner="TBC", priority="Low", due_date="2026-11-01"),
            dict(description="Send the invitations", workstream="Data", owner="Priya Nair", priority="Urgent", due_date="2026-11-05", status="Delayed"),
            dict(description="Order the laptops", workstream="Data", owner=ME, priority="Medium", due_date="2026-12-01", milestone=ms2),
            dict(description="Archive the old files", owner="Priya Nair", priority="Medium", status="Closed", closed="2026-10-10", due_date="2026-10-05"),
        ]):
            st.create("actions", {**base, **vals})
        st.create("raid", {**base, "type": "Risk", "description": "Supplier slips", "workstream": "Build", "owner": ME, "impact": "High", "likelihood": "High", "due_date": "2026-11-03"})
        st.create("raid", {**base, "type": "Issue", "description": "Test system is down", "owner": "TBC"})
        st.create("raid", {**base, "type": "Assumption", "description": "Users have laptops", "workstream": "Data", "owner": "Priya Nair", "impact": "Low", "likelihood": "Low"})
        st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending", "needed_by": "2026-11-20", "made_by": ME, "source": "demo"})
        st.create("decisions", {"project": "ABC", "decision": "Pick a supplier", "status": "Pending", "source": "demo"})
        st.create("decisions", {"project": "ABC", "decision": "Use the shared calendar", "status": "Made", "date": "2026-10-01", "made_by": "Priya Nair", "source": "demo"})
        st.create("decisions", {"project": "ABC", "decision": "Go with the old plan", "status": "Withdrawn", "made_by": "Priya Nair", "source": "demo"})
    return demo, s.data_for("ABC")


class InBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.T && window.T.board)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)


class Board(InBrowser):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.demo, cls.data = make_data()
        cls.ids = {k: [r["id"] for r in cls.data[k]] for k in ("actions", "raid", "decisions")}

    @classmethod
    def tearDownClass(cls):
        cls.demo.close()
        super().tearDownClass()

    def setUp(self):
        self.rows = self.val(f"T.board.rowsFor({lit(self.data)})")
        self.ctx = self.val(f"T.board.ctxFor({lit(self.data)}, {{project: 'ABC', today: {lit(TODAY)}, me: {lit(ME)}}})")

    def row(self, text):
        return next(r for r in self.rows if text in r["title"])

    def cols(self, group, lane=None):
        got = self.val(f"T.board.build(T.board.rowsFor({lit(self.data)}), {{group: {lit(group)}, lane: {lit(lane)}, ctx: {lit(self.ctx)}}})")
        return got

    def labels(self, group):
        b = self.cols(group)
        return [(c["label"], c["count"]) for c in b["lanes"][0]["columns"]]

    def move(self, row, group, key, lane=None, frm=None, to_lane=None):
        fromCell = frm or {"group": group, "key": self.val(f"T.board.cellOf({lit(group)}, {lit(row)}, {lit(self.ctx)})"), "lane": lane}
        toCell = {"group": group, "key": key, "lane": to_lane if to_lane is not None else lane}
        return self.val(f"T.board.moveFor({lit(row)}, {lit(fromCell)}, {lit(toCell)}, {lit(self.ctx)})")

    # rows, columns, lanes

    def test_rows_keep_what_a_move_needs(self):
        a = self.row("cut-over")
        self.assertEqual((a["table"], a["milestone_id"], a["milestone"]), ("actions", self.demo.milestone, "Pilot live"))
        self.assertEqual(self.row("new tool")["table"], "decisions")
        self.assertIsNone(self.row("new tool")["milestone_id"])

    def test_workstream_columns_and_the_no_workstream_column_holds_decisions(self):
        self.assertEqual(self.labels("workstream"), [("Build", 2), ("Data", 3), ("No workstream", 7)])

    def test_status_columns_hold_every_kinds_words(self):
        self.assertEqual(self.labels("status"), [("Open", 6), ("Delayed", 1), ("Pending", 2), ("Closed", 1), ("Made", 1), ("Cancelled", 0), ("Withdrawn", 1)])

    def test_due_columns_the_week_ends_on_sunday_and_a_decided_decision_has_no_date(self):
        b = self.cols("due")["lanes"][0]["columns"]
        ids = {c["label"]: sorted(x["id"] for x in c["cards"]) for c in b}
        self.assertEqual([c["label"] for c in b], ["Overdue", "This week", "Next week", "Later", "No date"])
        by_title = lambda col: sorted(x["title"] for x in b[col]["cards"])
        self.assertEqual(by_title(0), ["Archive the old files", "Draft the cut-over plan"], "a closed item sits in its date column")
        self.assertEqual(by_title(1), ["Book the training room"], "Sunday 01-11-2026 is this week")
        self.assertEqual(by_title(2), ["Send the invitations", "Supplier slips"])
        self.assertEqual(by_title(3), ["Order the laptops", "Use the new tool"])
        self.assertNotIn("Use the shared calendar", by_title(3) + by_title(2))
        self.assertIn("Use the shared calendar", by_title(4))
        self.assertTrue(b[0]["nodrop"] and not b[1].get("nodrop"), ids)

    def test_owner_columns_me_first_then_count_then_name_then_no_owner(self):
        self.assertEqual(self.labels("owner"), [("Sara Khan (me)", 4), ("Priya Nair", 5), ("No owner", 3)])

    def test_priority_has_a_not_rated_column_so_decisions_do_not_vanish(self):
        got = dict(self.labels("priority"))
        self.assertEqual(list(got), ["Urgent", "High", "Medium", "Low", "Not rated"])
        self.assertEqual(sum(got.values()), len(self.rows))
        self.assertEqual(got["Not rated"], 5, "the four decisions and the issue with no impact or likelihood")

    def test_milestone_columns_in_order_then_no_milestone(self):
        self.assertEqual(self.labels("milestone"), [("Pilot live", 1), ("Go live", 1), ("No milestone", 10)])

    def test_type_columns_and_nothing_is_one_column_on_a_table_and_status_on_the_board(self):
        self.assertEqual(self.labels("type"), [("Actions", 5), ("Risks and issues", 3), ("Decisions", 4)])
        self.assertEqual(self.val(f"T.board.columnsFor('nothing', T.board.rowsFor({lit(self.data)}), {lit(self.ctx)}).length"), 1)
        self.assertEqual(self.cols("nothing")["group"], "status")

    def test_every_card_is_in_exactly_one_column_for_every_group(self):
        for g in ("workstream", "status", "due", "owner", "priority", "milestone", "type"):
            self.assertEqual(sum(c for _, c in self.labels(g)), len(self.rows), g)

    def dangling(self):
        data = json.loads(json.dumps(self.data))
        acts = data["actions"]
        acts[0]["milestone"] = "ABC-M-404"; acts[1]["milestone"] = "ABC-M-405"
        acts[1]["workstream"] = "Gone"; acts[2]["priority"] = "Odd"; acts[3]["status"] = "In progress"
        acts[4]["owner"] = "  Somebody New "
        data["milestones"] = [m for m in data["milestones"] if m["id"] not in ("ABC-M-404", "ABC-M-405")]
        return data

    def test_no_card_vanishes_when_its_milestone_status_priority_or_workstream_has_no_column(self):
        data = self.dangling()
        rows = self.val(f"T.board.rowsFor({lit(data)})")
        ctx = self.val(f"T.board.ctxFor({lit(data)}, {{project: 'ABC', today: {lit(TODAY)}, me: {lit(ME)}}})")
        for g in ("workstream", "status", "due", "owner", "priority", "milestone", "type", "nothing"):
            for lane in (None, "workstream", "type"):
                b = self.val(f"T.board.build({lit(rows)}, {{group: {lit(g)}, lane: {lit(lane)}, ctx: {lit(ctx)}}})")
                seen = [c_["id"] for ln in b["lanes"] for col in ln["columns"] for c_ in col["cards"]]
                self.assertEqual(sorted(seen), sorted(r["id"] for r in rows), (g, lane))
        cols = {c["key"]: c for c in self.val(f"T.board.columnsFor('milestone', {lit(rows)}, {lit(ctx)})")}
        self.assertEqual((cols["ABC-M-404"]["label"], cols["ABC-M-404"]["nodrop"]), ("Archived or missing milestone", True))
        self.assertEqual(self.val(f"T.board.columnsFor('milestone', {lit(rows)}, {lit(ctx)})")[-1]["label"], "No milestone", "the missing-value column stays last")
        status = self.val(f"T.board.columnsFor('status', {lit(rows)}, {lit(ctx)})")
        self.assertIn("Old status: In progress", [c["label"] for c in status])
        prio = self.val(f"T.board.columnsFor('priority', {lit(rows)}, {lit(ctx)})")
        self.assertIn("Not a priority: Odd", [c["label"] for c in prio])
        odd = next(r for r in rows if r["id"] == data["actions"][2]["id"])
        self.assertRefused(self.move(odd, "priority", "Odd", frm={"group": "priority", "key": "High", "lane": None}), "A card can't be given that priority. Choose Urgent, High, Medium or Low.")

    def test_a_date_must_fall_in_the_column_it_was_dropped_on(self):
        got = self.move(self.row("laptops"), "due", "this_week")
        self.assertRefused(self.val(f"T.board.dateMove({lit(got)}, '2031-06-01', {lit(TODAY)})"),
                           'That date isn\'t in the "This week" column. Pick a day in it, or drop the card on the column that holds that date.')

    def test_a_withdrawn_decision_has_its_own_words_and_may_go_back_to_pending(self):
        d = self.row("old plan")
        self.assertRefused(self.move(d, "owner", "Priya Nair", frm={"group": "owner", "key": "x", "lane": None}),
                           "A decision that has been withdrawn can't be moved. It can go back to Pending, or record a new decision.")
        self.assertRefused(self.move(d, "due", "later"), "A decision that has been withdrawn has no due date, so it has nothing to move.")
        self.assertEqual(self.move(d, "status", "Pending")["request"]["changes"], {"status": "Pending"})

    def test_lanes_list_every_active_workstream_and_no_workstream_only_when_it_holds_a_card(self):
        b = self.cols("status", "workstream")
        self.assertEqual([(ln["label"], ln["count"]) for ln in b["lanes"]], [("Build", 2), ("Data", 3), ("No workstream", 7)])
        data = json.loads(json.dumps(self.data))
        data["workstreams"].append({"name": "Empty", "status": "Active"})
        ctx = self.val(f"T.board.ctxFor({lit(data)}, {{project: 'ABC', today: {lit(TODAY)}}})")
        only = [r for r in self.rows if r["workstream"]]
        got = self.val(f"T.board.build({lit(only)}, {{group: 'status', lane: 'workstream', ctx: {lit(ctx)}}})")
        self.assertEqual([ln["label"] for ln in got["lanes"]], ["Build", "Data", "Empty"], "an empty lane is a target; no card, no No workstream lane")
        self.assertEqual(self.cols("status", "type")["lanes"][1]["label"], "Risks and issues")
        self.assertIsNone(self.cols("workstream", "workstream")["lane"], "the chosen group is not a lane")

    def test_the_card(self):
        card = self.val(f"T.board.cardOf({lit(self.row('cut-over'))}, {lit(TODAY)})")
        self.assertEqual((card["id"], card["type"], card["client"], card["title"], card["initials"]), ("ABC-A-001", "Action", True, "Draft the cut-over plan", "SK"))
        self.assertEqual((card["due"]["words"], card["due"]["tone"], card["state"]["text"]), ("9 days late", "late", "Overdue"))
        closed = self.val(f"T.board.cardOf({lit(self.row('old files'))}, {lit(TODAY)})")
        self.assertEqual((closed["due"]["words"], closed["open"]), ("", False), "nothing for a closed item")
        quiet = self.val(f"T.board.cardOf({lit(dict(self.row('cut-over'), client=False, owner='TBC'))}, {lit(TODAY)})")
        self.assertEqual((quiet["client"], quiet["initials"]), (False, ""))
        self.assertEqual(self.val(f"T.board.cardOf({lit(self.row('Test system'))}, {lit(TODAY)})")["type"], "Issue")

    # moves: the spec's table

    def assertRefused(self, got, words):
        self.assertEqual((got["ok"], got["message"]), (False, words), got)

    def test_workstream_moves(self):
        a = self.row("cut-over")
        got = self.move(a, "workstream", "Data")
        self.assertEqual(got["request"], {"project": "ABC", "kind": "actions", "op": "update", "id": "ABC-A-001", "changes": {"workstream": "Data"}, "place": self.val("T.board.PLACE")})
        self.assertEqual(self.move(a, "workstream", "__none")["request"]["changes"], {"workstream": None})
        self.assertRefused(self.move(self.row("new tool"), "workstream", "Data"), "A decision isn't part of a workstream.")
        self.assertRefused(self.move(self.row("new tool"), "workstream", "__none", frm={"group": "workstream", "key": "Build", "lane": None}), "A decision isn't part of a workstream.")
        self.assertRefused(self.move(a, "workstream", "Closed one"), "That workstream isn't available.")

    def test_status_moves(self):
        a, r = self.row("cut-over"), self.row("Supplier")
        self.assertEqual(self.move(a, "status", "Delayed")["request"]["changes"], {"status": "Delayed"})
        self.assertEqual(self.move(a, "status", "Closed")["request"]["changes"], {"status": "Closed"})
        self.assertRefused(self.move(r, "status", "Delayed"), "A risk can't be Delayed. It can be Open, Closed or Cancelled.")
        self.assertRefused(self.move(self.row("Test system"), "status", "Pending"), "An issue can't be Pending. It can be Open, Closed or Cancelled.")
        self.assertRefused(self.move(self.row("Users have"), "status", "Delayed"), "An assumption can't be Delayed. It can be Open, Closed or Cancelled.")
        self.assertRefused(self.move(a, "status", "Made"), "An action can't be Made. It can be Open, Delayed, Closed or Cancelled.")
        d = self.row("new tool")
        self.assertRefused(self.move(d, "status", "Open"), "A decision can't be Open. It can be Pending, Made or Withdrawn.")

    def test_a_pending_decision_dragged_to_made_is_one_step_with_todays_date(self):
        got = self.move(self.row("new tool"), "status", "Made")
        self.assertEqual(got["request"]["changes"], {"status": "Made", "date": TODAY})
        self.assertEqual((got["note"], got["undoable"]), ("Made, dated today", False), "the store won't put a Made decision back, so no Undo")
        self.assertNotIn("undoable", self.move(self.row("cut-over"), "status", "Closed"))
        self.assertEqual(self.val(f"T.board.movedWords({lit(got)}, {lit(self.row('new tool'))})"), f"{self.row('new tool')['id']} is now Made, dated today. This can't be undone. Record a new decision to change it.")
        self.assertEqual(self.move(self.row("new tool"), "status", "Withdrawn")["request"]["changes"], {"status": "Withdrawn"})

    def test_a_made_or_withdrawn_decision_never_moves(self):
        words = "A decision that is made or withdrawn can't be moved. Record a new decision that replaces it."
        for title in ("shared calendar",):
            d = self.row(title)
            for g, k in (("status", "Pending"), ("status", "Withdrawn"), ("owner", "Priya Nair"), ("owner", "__none"), ("milestone", self.demo.milestone), ("workstream", "Build")):
                said = changes.MADE_STAYS if (g, k) == ("status", "Pending") else words
                self.assertRefused(self.move(d, g, k, frm={"group": g, "key": "x", "lane": None}), said)
        self.assertRefused(self.move(self.row("shared calendar"), "due", "later"), "A decision that has been made has no due date, so it has nothing to move.")
        self.assertRefused(self.move(self.row("shared calendar"), "due", "__none", frm={"group": "due", "key": "later", "lane": None}), "A decision that has been made has no due date, so it has nothing to move.")
        same = self.move(self.row("shared calendar"), "status", "Made")
        self.assertEqual((same["ok"], same.get("noop")), (True, True), "to where it is: nothing, no message")

    def test_due_asks_for_a_date_never_past_overdue_is_not_a_target_no_date_clears(self):
        a = self.row("training room")                          # due Sunday 01-11-2026, this week
        got = self.move(a, "due", "next_week")
        self.assertEqual(got["request"]["changes"], {})
        self.assertEqual(got["needsDate"], {"field": "due_date", "min": TODAY, "suggested": "2026-11-06", "column": "next_week"})
        done = self.val(f"T.board.dateMove({lit(got)}, '2026-11-05', {lit(TODAY)})")
        self.assertEqual(done["request"]["changes"], {"due_date": "2026-11-05"})
        self.assertNotIn("needsDate", done)
        self.assertRefused(self.val(f"T.board.dateMove({lit(got)}, '2026-10-28', {lit(TODAY)})"), "Pick today or a later date.")
        today_ok = self.val(f"T.board.dateMove({lit(self.move(a, 'due', 'this_week'))}, {lit(TODAY)}, {lit(TODAY)})")
        self.assertTrue(today_ok["ok"], "today is allowed in This week")
        self.assertRefused(self.val(f"T.board.dateMove({lit(got)}, '2026-02-30', {lit(TODAY)})"), "That isn't a date. Pick a day from the calendar.")
        self.assertEqual(self.move(a, "due", "later")["needsDate"]["suggested"], "2026-11-13")
        self.assertRefused(self.move(a, "due", "overdue"), "Overdue is worked out from the due date. Drop the card on This week, Next week or Later and choose a date.")
        self.assertEqual(self.move(a, "due", "__none")["request"]["changes"], {"due_date": None})
        nodate = self.row("Test system")
        self.assertTrue(self.move(nodate, "due", "__none").get("noop"), "already no date")
        # the suggested day is today when the week's Friday has gone
        late = self.val(f"T.board.moveFor({lit(a)}, {{group: 'due', key: 'overdue', lane: null}}, {{group: 'due', key: 'this_week', lane: null}}, {lit(dict(self.ctx, today='2026-10-31'))})")
        self.assertEqual(late["needsDate"]["suggested"], "2026-10-31")

    def test_a_pending_decision_dates_use_needed_by(self):
        d = self.row("new tool")
        self.assertEqual(self.move(d, "due", "this_week")["needsDate"]["field"], "needed_by")
        self.assertEqual(self.move(d, "due", "__none")["request"]["changes"], {"needed_by": None})
        done = self.val(f"T.board.dateMove({lit(self.move(d, 'due', 'this_week'))}, '2026-10-30', {lit(TODAY)})")
        self.assertEqual(done["request"]["changes"], {"needed_by": "2026-10-30"})

    def test_owner_moves(self):
        a, d = self.row("cut-over"), self.row("new tool")
        self.assertEqual(self.move(a, "owner", "Priya Nair")["request"]["changes"], {"owner": "Priya Nair"})
        self.assertEqual(self.move(a, "owner", "__none")["request"]["changes"], {"owner": "TBC"})
        self.assertEqual(self.move(d, "owner", "Priya Nair")["request"]["changes"], {"made_by": "Priya Nair"})
        self.assertEqual(self.move(d, "owner", "__none")["request"]["changes"], {"made_by": None})

    def test_priority_moves(self):
        self.assertEqual(self.move(self.row("cut-over"), "priority", "Urgent")["request"]["changes"], {"priority": "Urgent"})
        self.assertRefused(self.move(self.row("Supplier"), "priority", "Low"), "A risk or issue's priority comes from its impact and likelihood. Change those in its details.")
        self.assertRefused(self.move(self.row("Test system"), "priority", "Low", frm={"group": "priority", "key": "__none", "lane": None}), "A risk or issue's priority comes from its impact and likelihood. Change those in its details.")
        self.assertRefused(self.move(self.row("new tool"), "priority", "High"), "A decision has no priority.")
        self.assertRefused(self.move(self.row("cut-over"), "priority", "__none"), "An action can't be moved to Not rated. Choose Urgent, High, Medium or Low.")

    def test_milestone_moves(self):
        a = self.row("cut-over")
        self.assertEqual(self.move(a, "milestone", "ABC-M-002")["request"]["changes"], {"milestone": "ABC-M-002"})
        self.assertEqual(self.move(a, "milestone", "__none")["request"]["changes"], {"milestone": None})
        self.assertRefused(self.move(self.row("new tool"), "milestone", "ABC-M-002"), "A decision isn't tied to a milestone.")
        self.assertRefused(self.move(self.row("new tool"), "milestone", "__none", frm={"group": "milestone", "key": "x", "lane": None}), "A decision isn't tied to a milestone.")
        self.assertRefused(self.move(a, "milestone", "XYZ-M-001"), "That milestone isn't in this project.")

    def test_a_type_never_changes(self):
        self.assertRefused(self.move(self.row("cut-over"), "type", "decisions"), "An action can't change its type.")
        self.assertRefused(self.move(self.row("Supplier"), "type", "actions"), "A risk can't change its type.")
        self.assertRefused(self.move(self.row("Test system"), "type", "actions"), "An issue can't change its type.")
        self.assertRefused(self.move(self.row("new tool"), "type", "raid"), "A decision can't change its type.")

    def test_lane_and_column_are_one_request(self):
        a = self.row("cut-over")                                          # Build, Open, in the status column
        frm = {"group": "status", "key": "Open", "lane": {"group": "workstream", "key": "Build"}}
        both = self.move(a, "status", "Closed", frm=frm, to_lane={"group": "workstream", "key": "Data"})
        self.assertEqual(both["request"]["changes"], {"status": "Closed", "workstream": "Data"})
        lane_only = self.move(a, "status", "Open", frm=frm, to_lane={"group": "workstream", "key": "Data"})
        self.assertEqual(lane_only["request"]["changes"], {"workstream": "Data"})
        none = self.move(a, "status", "Open", frm=frm, to_lane=frm["lane"])
        self.assertTrue(none.get("noop"))
        with_date = self.move(a, "due", "later", frm={"group": "due", "key": "overdue", "lane": {"group": "workstream", "key": "Build"}}, to_lane={"group": "workstream", "key": "Data"})
        self.assertEqual((with_date["request"]["changes"], with_date["needsDate"]["field"]), ({"workstream": "Data"}, "due_date"))

    def test_the_refusals_use_the_agreed_plain_words(self):
        a = self.row("cut-over")
        got = self.move(a, "bogus", "x", frm={"group": "bogus", "key": "y", "lane": None})
        self.assertRefused(got, "A card can't be moved there.")
        moved = self.val("T.board.movedWords({request: {changes: {milestone: 'ABC-M-001'}}, note: null}, " + lit(a) + ")")
        self.assertEqual(moved, f"{a['id']} is now with a milestone.")
        moved = self.val("T.board.movedWords({request: {changes: {milestone: null}}, note: null}, " + lit(a) + ")")
        self.assertEqual(moved, f"{a['id']} is now with no milestone.")
        words = self.val("T.board.WORDS")
        self.assertEqual(words["madeStays"], "A decision that has been made can't go back to Pending. Record a new decision that replaces it.")
        self.assertEqual(words["notADate"], "That isn't a date. Pick a day from the calendar.")
        for w in words.values():
            self.assertNotIn("RAID", w)
            self.assertNotIn("lane", w.lower().replace("swimlane", ""))
            self.assertNotIn("refused", w)

    def test_if_one_half_is_refused_neither_is_made_and_it_says_which(self):
        d = self.row("new tool")                                          # a Pending decision
        frm = {"group": "status", "key": "Pending", "lane": {"group": "workstream", "key": "__none"}}
        got = self.move(d, "status", "Made", frm=frm, to_lane={"group": "workstream", "key": "Data"})
        self.assertRefused(got, "Nothing was moved. The card can't go in that swimlane. A decision isn't part of a workstream.")
        self.assertEqual(got["half"], "lane")
        r = self.row("Supplier")
        frm = {"group": "status", "key": "Open", "lane": {"group": "workstream", "key": "Build"}}
        got = self.move(r, "status", "Delayed", frm=frm, to_lane={"group": "workstream", "key": "Data"})
        self.assertEqual((got["ok"], got["half"]), (False, "column"))
        self.assertTrue(got["message"].startswith("Nothing was moved. The card can't go in that column. A risk can't be Delayed."))
        lane_type = self.move(self.row("cut-over"), "status", "Open", frm={"group": "status", "key": "Open", "lane": {"group": "type", "key": "actions"}}, to_lane={"group": "type", "key": "decisions"})
        self.assertRefused(lane_type, "An action can't change its type.")
        both = self.move(self.row("cut-over"), "workstream", "Data", to_lane={"group": "workstream", "key": "Build"})
        self.assertRefused(both, "Swimlanes and columns can't use the same grouping. Choose a different swimlane.")

    def test_the_menu_lists_only_places_a_card_can_go(self):
        ctx = self.ctx
        risk = self.row("Supplier")
        cols = self.val(f"T.board.columnsFor('status', T.board.rowsFor({lit(self.data)}), {lit(ctx)})")
        got = self.val(f"T.board.targetsFor({lit(risk)}, {{group: 'status', key: 'Open', lane: null}}, {lit(cols)}, {lit(ctx)}).map(c => c.key)")
        self.assertEqual(got, ["Closed", "Cancelled"])
        due = self.val(f"T.board.columnsFor('due', T.board.rowsFor({lit(self.data)}), {lit(ctx)})")
        a = self.row("training room")
        got = self.val(f"T.board.targetsFor({lit(a)}, {{group: 'due', key: 'this_week', lane: null}}, {lit(due)}, {lit(ctx)}).map(c => c.key)")
        self.assertEqual(got, ["next_week", "later", "__none"], "Overdue is not offered")

    def test_no_delete_anywhere_in_the_logic(self):
        source = (PAGE_SRC / "logic" / "board.js").read_text(encoding="utf-8")
        for word in ("delete", "Delete", "remove"):
            self.assertNotIn(word, source.replace("// ", "//"), word)

    # what is remembered

    def test_remembered_state_defaults_clamps_and_survives_blocked_storage(self):
        fake = "{getItem(k){return this.d[k]===undefined?null:this.d[k]}, setItem(k,v){this.d[k]=v}, d:{}}"
        self.assertEqual(self.val(f"T.board.readState('ABC', {fake})"), {"view": "table", "group": "workstream", "lane": None, "collapsed": []})
        self.assertEqual(self.val(f"(function(){{ const s = {fake}; T.board.writeState('ABC', {{view:'board', group:'owner', lane:'type'}}, s); T.board.writeState('XYZ', {{view:'board'}}, s); return [T.board.readState('ABC', s), T.board.readState('XYZ', s).group, Object.keys(JSON.parse(s.d['clark.work.v1']))]; }})()"),
                         [{"view": "board", "group": "owner", "lane": "type", "collapsed": []}, "workstream", ["ABC", "XYZ"]])
        for junk in ('"not an object"', '{"ABC": 5}', '{"ABC": {"view": "x", "group": "nope", "lane": "owner", "collapsed": [1, "a:b", null]}}', "[1,2]", "{not json"):
            got = self.val(f"T.board.readState('ABC', {{getItem(){{return {junk!r} === {junk!r} ? {lit(junk)} : null}}, setItem(){{}}}})")
            self.assertEqual(got["view"], "table", junk)
            self.assertEqual(got["group"], "workstream", junk)
            self.assertIsNone(got["lane"], junk)
            self.assertLessEqual(len(got["collapsed"]), 1, junk)
        blocked = "{getItem(){throw new Error('blocked')}, setItem(){throw new Error('blocked')}}"
        self.assertEqual(self.val(f"T.board.readState('ABC', {blocked})")["group"], "workstream")
        self.assertEqual(self.val(f"T.board.writeState('ABC', {{view:'board'}}, {blocked})"), {"state": {"view": "board", "group": "workstream", "lane": None, "collapsed": []}, "saved": False})
        self.assertTrue(self.val("T.board.writeState('ABC', {view:'board'}).saved"), "the page's own storage, or the pure fallback, takes it")

    def test_a_lane_that_is_the_group_is_dropped_and_nothing_reads_as_status(self):
        self.assertIsNone(self.val("T.board.cleanState({group:'type', lane:'type'})")["lane"])
        self.assertEqual(self.val("T.board.boardGroup('nothing')"), "status")

    def test_collapsed_columns_toggle_and_stale_ones_are_ignored(self):
        got = self.val("(function(){ let s = T.board.cleanState({group:'status'}); s = T.board.toggleCollapsed(s, 'status', 'Closed'); s = T.board.toggleCollapsed(s, 'status', 'Gone'); const a = T.board.isCollapsed(s, 'status', 'Closed'); const now = T.board.collapsedNow(s, 'status', [{key:'Open'},{key:'Closed'}]); const t = T.board.toggleCollapsed(s, 'status', 'Closed'); return [a, now, T.board.isCollapsed(t, 'status', 'Closed'), T.board.collapsedNow(s, 'owner', [{key:'Closed'}])]; })()")
        self.assertEqual(got, [True, ["Closed"], False, []])

    # the generic drag

    def test_the_generic_drag_starts_after_four_pixels_and_a_click_stays_a_click(self):
        got = self.val("""(function(){ const log = []; const d = T.dragCore.createDrag({onStart: (x) => log.push(['start', x]), onMove: (m) => log.push(['move', m.x]),
          onDrop: (m) => log.push(['drop', m.x, m.data]), onCancel: () => log.push(['cancel'])});
          d.down(0, 0, 'card'); const a = d.move(2, 2); const b = d.move(4, 0); const c = d.move(9, 0); const was = d.up(9, 0);
          d.down(5, 5, 'x'); d.move(5, 6); const click = d.up(5, 6);
          d.down(0, 0, 'y'); d.move(10, 0); d.cancel(); const after = d.up(1, 1);
          return [log, a, b, c, was, click, after, d.dragging]; })()""")
        self.assertEqual(got, [[["start", "card"], ["move", 4], ["move", 9], ["drop", 9, "card"], ["start", "y"], ["move", 10], ["cancel"]], False, True, True, True, False, False, False])


class AgainstTheServer(InBrowser):
    """Every request the logic produces is accepted by changes.make_change for a demo store; every refusal comes from the logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.demo, cls.data = make_data()
        cls.change = staticmethod(changes.make_change(cls.demo.store.path, [], USER))
        cls.undo = staticmethod(changes.make_undo(cls.demo.store.path, [], USER))

    @classmethod
    def tearDownClass(cls):
        cls.demo.close()
        super().tearDownClass()

    def send(self, request):
        """The request exactly as produced: its place is one the server accepts today."""
        self.assertEqual(request["place"], self.expected_place())
        return self.change(request)

    @staticmethod
    def expected_place():
        return "board" if "board" in changes.PLACES else "cell"

    def test_the_place_is_one_constant_the_server_accepts(self):
        self.assertEqual(self.val("T.board.PLACE"), self.expected_place(), "flip the one constant to 'board' once changes.PLACES has it")
        source = (PAGE_SRC / "logic" / "board.js").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'PLACE = "', source)), 1)
        self.assertNotIn('place: "', source, "the word is written once")
        self.assertIn(self.val("T.board.PLACE"), changes.PLACES)

    def test_the_words_the_logic_repeats_are_the_servers(self):
        words = self.val("T.board.WORDS")
        for mine, theirs in (("madeStays", changes.MADE_STAYS), ("noWorkstream", changes.NO_DECISION_FIELD["workstream"]),
                             ("noMilestone", changes.NO_DECISION_FIELD["milestone"]), ("noPriority", changes.NO_DECISION_FIELD["priority"]),
                             ("riskPriority", changes.NO_RAID_PRIORITY), ("notADate", changes.NOT_A_DATE),
                             ("strangeWorkstream", changes.NO_WORKSTREAM), ("strangeMilestone", changes.NO_MILESTONE)):
            self.assertEqual(words[mine], theirs, mine)

    def test_every_request_the_logic_makes_is_accepted_and_undone(self):
        sweep = self.val(f"T.sweep({lit(self.data)}, 'ABC', {lit(TODAY)}, {lit(ME)})")
        self.assertGreater(len(sweep), 500)
        seen, accepted, refused, noops = set(), 0, 0, 0
        for m in sweep:
            r = m["result"]
            if not r["ok"]:
                refused += 1
                self.assertTrue(r["message"].endswith("."), r)
                self.assertNotIn("clark", r["message"].lower(), "the logic's own words, not the server's")
                continue
            if r.get("noop"):
                noops += 1
                continue
            self.assertNotIn("needsDate", r, "the sweep finishes every date")
            key = json.dumps(r["request"], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            status, body = self.send(r["request"])
            self.assertEqual((status, body.get("message")), (200, None), r["request"])
            accepted += 1
            if body["apply_id"] is not None:
                self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 200, r["request"])
        self.assertGreater(accepted, 100)
        self.assertGreater(refused, 100)
        self.assertGreater(noops, 20)

    def test_a_request_never_sets_a_risks_priority_a_status_the_kind_lacks_or_a_delete(self):
        sweep = self.val(f"T.sweep({lit(self.data)}, 'ABC', {lit(TODAY)}, {lit(ME)})")
        allowed = {"actions": {"Open", "Delayed", "Closed", "Cancelled"}, "raid": {"Open", "Closed", "Cancelled"}, "decisions": {"Pending", "Made", "Withdrawn"}}
        fields = {k: set(v["update"]) for k, v in changes.CHANGE_KINDS.items() if k in changes.ITEM_KINDS}
        for m in sweep:
            r = m["result"]
            if not r["ok"] or r.get("noop"):
                continue
            q = r["request"]
            self.assertEqual((q["op"], q["place"], q["project"]), ("update", self.expected_place(), "ABC"))
            self.assertTrue(set(q["changes"]) <= fields[q["kind"]], q)
            self.assertNotIn("priority", q["changes"] if q["kind"] != "actions" else {}, q)
            if "status" in q["changes"]:
                self.assertIn(q["changes"]["status"], allowed[q["kind"]], q)
            if q["kind"] == "decisions" and q["changes"].get("status") == "Made":
                self.assertEqual(q["changes"]["date"], TODAY)

    def test_the_logic_refuses_what_a_naive_request_would_send_and_the_server_would_too(self):
        rows = self.val(f"T.board.rowsFor({lit(self.data)})")
        by = lambda text: next(r for r in rows if text in r["title"])
        sweep = self.val(f"T.sweep({lit(self.data)}, 'ABC', {lit(TODAY)}, {lit(ME)})")
        ms = self.demo.milestone
        naive = [("Supplier", "priority", "Low", {"priority": "Low"}), ("Supplier", "status", "Delayed", {"status": "Delayed"}),
                 ("new tool", "workstream", "Build", {"workstream": "Build"}), ("new tool", "milestone", ms, {"milestone": ms}),
                 ("shared calendar", "status", "Pending", {"status": "Pending"}), ("cut-over", "status", "Pending", {"status": "Pending"})]
        for title, group, key, ch in naive:
            row = by(title)
            got = self.change({"project": "ABC", "kind": row["table"], "op": "update", "id": row["id"], "changes": ch, "place": self.expected_place()})
            self.assertFalse(got[1]["ok"], (title, ch))
            said = next((m["result"] for m in sweep if (m["id"], m["group"], m["key"], m["lane"]) == (row["id"], group, key, None)), None)
            self.assertIsNotNone(said, (title, group, key))
            self.assertFalse(said["ok"], f"the logic refuses it before the server: {title} {ch}")

    def test_a_card_dragged_to_made_is_one_step_and_cannot_be_undone(self):
        row = next(r for r in self.val(f"T.board.rowsFor({lit(self.data)})") if r["title"] == "Use the new tool")
        ctx = self.val(f"T.board.ctxFor({lit(self.data)}, {{project: 'ABC', today: {lit(TODAY)}, me: {lit(ME)}}})")
        got = self.val(f"T.board.moveFor({lit(row)}, {{group:'status', key:'Pending', lane:null}}, {{group:'status', key:'Made', lane:null}}, {lit(ctx)})")
        status, body = self.send(got["request"])
        self.assertEqual(status, 200, body)
        self.assertIsNone(body["apply_id"], "the server offers no Undo for a decision that has been made")
        self.assertFalse(body["undoable"])
        self.assertFalse(got["undoable"])
        self.assertEqual(self.demo.store.read("decisions", ref=row["id"])["date"], TODAY)
        step = self.demo.store.con.execute("SELECT apply_id FROM change_log WHERE item_id = ? ORDER BY rowid DESC LIMIT 1", (row["id"],)).fetchone()[0]
        self.assertEqual({r["key"] for r in self.demo.store.step_rows(step)}, {row["id"]})
        status, back = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual((status, back["message"], back["code"]), (409, changes.MADE_CANT_BE_PUT_BACK, "not_undoable"))
        self.assertEqual(self.demo.store.read("decisions", ref=row["id"])["status"], "Made")

if __name__ == "__main__":
    unittest.main()

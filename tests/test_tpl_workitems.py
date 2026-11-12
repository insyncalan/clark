"""#96 G3, the Work items list template (store type "workitems"): live rows from Work items, chosen by a filter saved in Edit.

- The checker: every key rebuilt with its default, unknown or hostile values refused in plain words that never quote them, the
  limits (rows, values, caption), canonical text.
- One save is one step with one Undo, through the real change route.
- Publish: the file carries the ordered ids publish chose from the rows it already kept, the columns and the caption, never the
  filter; an archived, client-off, Sensitive, eye-hidden or hidden-section item is never in it; an empty match, an unsaved filter
  and a hidden section leave the section out of the file. Planted markers are absent from the file's bytes.
- The page's rules and section_kinds/workitems.py choose the same ids, in the same order, over the same rows.
- In a real browser: View shows the rows the client sees (and leaves the section out when nothing matches); Edit saves each
  committed choice as one step and says when nothing matches; rows open their peek in Edit only; full width draws the table and
  half width the two-line rows; 1400 and 900 px, light and dark, no sideways scroll; the published file draws from its own data.

Run: python3 dev/run_tests.py test_tpl_workitems
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import contextlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import ROOT, SRC
from clark import changes, publish, section_bodies, store as store_module
from clark.section_kinds import base, workitems as wi
from test_changes import Api
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg, tearDownModule  # noqa: F401
from test_server import Running, chrome, wait, wait_toast

PAGE_SRC = SRC / "clark" / "page" / "src"
RULES = store_module.BODY_RULES
TODAY = "2030-01-15"
_PAGE = {}


def check(value):
    return wi.check(value, RULES)


def stored(value):
    return store_module.check_section_body("workitems", json.dumps(value))


class Checker(unittest.TestCase):
    def test_an_empty_object_is_every_default(self):
        got = check({})
        self.assertEqual(got, {"v": 1, "kinds": [], "mode": "open", "status": [], "due": [], "owner": [], "workstream": [],
                               "use_case": [], "priority": [], "sort": "due", "max": 10,
                               "columns": ["type", "id", "owner", "due", "status"], "caption": "",
                               "milestone": [], "not": {k: [] for k in wi.LEFT_OUT}, "has": [], "no": [], "text": []})
        self.assertEqual(set(got), set(wi.KEYS))

    def test_choices_are_kept_in_their_own_order_without_repeats(self):
        got = check({"kinds": ["decision", "risk", "risk"], "due": ["later", "overdue"], "columns": ["status", "type"],
                     "owner": ["  Pat   Demo ", "Pat Demo", "(none)"], "priority": ["(none)", "High"]})
        self.assertEqual(got["kinds"], ["risk", "decision"])
        self.assertEqual(got["due"], ["overdue", "later"])
        self.assertEqual(got["columns"], ["type", "status"])
        self.assertEqual(got["owner"], ["Pat Demo", "(none)"])
        self.assertEqual(got["priority"], ["High", "(none)"])

    def test_the_stored_text_is_canonical_and_saving_it_again_changes_nothing(self):
        a = stored({"max": 5, "kinds": ["action"]})
        self.assertEqual(stored(json.loads(a)), a)
        self.assertEqual(json.loads(a)["max"], 5)

    def test_hostile_and_unknown_values_are_refused_in_words_that_never_quote_them(self):
        cases = [({"client": ["yes"]}, wi.UNKNOWN_FIELD), ({"kinds": ["ZQ-kind"]}, wi.BAD_CHOICE), ({"kinds": "action"}, wi.BAD_CHOICE),
                 ({"mode": "ZQ-mode"}, wi.BAD_CHOICE), ({"sort": ["due"]}, wi.BAD_CHOICE), ({"status": ["Done"]}, wi.BAD_CHOICE),
                 ({"max": 0}, wi.BAD_MAX), ({"max": 51}, wi.BAD_MAX), ({"max": True}, wi.BAD_MAX), ({"max": "5"}, wi.BAD_MAX),
                 ({"columns": []}, wi.NO_COLUMNS), ({"columns": ["title"]}, wi.BAD_CHOICE), ({"v": 2}, wi.NOT_A_FILTER),
                 ({"v": True}, wi.NOT_A_FILTER), ({"owner": [""]}, wi.BAD_CHOICE), ({"owner": [7]}, wi.BAD_CHOICE),
                 ({"owner": ["x" * 121]}, wi.LONG_NAME), ({"owner": [f"Owner {n}" for n in range(31)]}, wi.TOO_MANY),
                 ({"use_case": ["ZQ-not-an-id"]}, wi.BAD_CHOICE), ({"use_case": ["ABC-A-001"]}, wi.BAD_CHOICE),
                 ({"caption": "x" * 201}, wi.LONG_CAPTION), ({"caption": 5}, wi.BAD_CHOICE)]
        for value, words in cases:
            with self.subTest(value=value):
                with self.assertRaises(base.Bad) as got:
                    check(value)
                self.assertEqual(str(got.exception), words)
                self.assertNotIn("ZQ-", str(got.exception))
        self.assertRaises(base.Bad, check, [])
        self.assertEqual(check({"use_case": ["ABC-U-001", "(none)"]})["use_case"], ["ABC-U-001", "(none)"])

    def test_the_store_refuses_a_line_break_markup_is_only_text_and_the_limit_fits_the_route(self):
        with self.assertRaises(store_module.Invalid):
            stored({"caption": "one\ntwo"})
        self.assertEqual(json.loads(stored({"caption": "<b>bold</b>"}))["caption"], "<b>bold</b>")
        self.assertLess(len(stored({"owner": ["x" * 120] * 30, "workstream": ["y" * 120] * 30, "caption": "z" * 200})), wi.LIMIT * 2)
        self.assertEqual(section_bodies.LIMITS["workitems"], wi.LIMIT)
        self.assertTrue(wi.READY)

    def test_day_number_is_the_pages_and_refuses_a_made_up_day(self):
        self.assertEqual(wi.day_number("1970-01-01"), 0)
        self.assertEqual(wi.day_number("2030-01-15"), 21929)
        self.assertEqual(wi.day_number("2000-02-29") + 1, wi.day_number("2000-03-01"))
        for v in ("2030-02-31", "2100-02-29", "2030-1-5", "15-01-2030", "", None, "2030-01-1x"):
            self.assertIsNone(wi.day_number(v), v)


ROWS = {
    "actions": [
        {"id": "ABC-A-001", "status": "Open", "owner": "Pat Demo", "workstream": "Build", "use_case": "ABC-U-001", "priority": "High", "due_date": "2030-01-10"},
        {"id": "ABC-A-002", "status": "Delayed", "owner": "Lee Demo", "workstream": None, "use_case": None, "priority": None, "due_date": "2030-01-20"},
        {"id": "ABC-A-003", "status": "Closed", "owner": "Pat Demo", "workstream": "Build", "use_case": None, "priority": "Low", "due_date": "2029-12-01"},
        {"id": "ABC-A-004", "status": "Open", "owner": " ", "workstream": "Run", "use_case": None, "priority": "Urgent", "due_date": None},
        {"id": "ABC-A-005", "status": "Open", "owner": "Sam Demo", "workstream": "Build", "use_case": None, "priority": "Medium", "due_date": "2030-03-01"},
        {"id": "ABC-A-006", "status": "Cancelled", "owner": "Sam Demo", "workstream": "Run", "use_case": None, "priority": None, "due_date": "2030-02-30"},
    ],
    "raid": [
        {"id": "ABC-001", "type": "Risk", "status": "Open", "owner": "Pat Demo", "workstream": "Build", "use_case": "ABC-U-001", "priority": "High", "due_date": None},
        {"id": "ABC-002", "type": "Issue", "status": "Open", "owner": "Lee Demo", "workstream": None, "use_case": None, "priority": "Urgent", "due_date": "2030-01-14"},
        {"id": "ABC-003", "type": "Dependency", "status": "Closed", "owner": None, "workstream": "Run", "use_case": None, "priority": "Low", "due_date": "2030-01-01"},
    ],
    "decisions": [
        {"id": "ABC-D-001", "status": "Pending", "made_by": "Pat Demo", "use_case": None, "needed_by": "2030-01-16", "date": None},
        {"id": "ABC-D-002", "status": "Made", "made_by": "Lee Demo", "use_case": "ABC-U-001", "needed_by": "2030-01-01", "date": "2030-01-05"},
    ],
}
ROWS["milestones"] = [{"id": "ABC-M-001", "name": "Go live"}, {"id": "ABC-M-002", "name": "Pilot"}]
for _id, _title, _ms in (("ABC-A-001", "Chase the supplier file", "ABC-M-001"), ("ABC-A-002", "Plan the second wave", None),
                         ("ABC-A-005", "Order the laptops", "ABC-M-002"), ("ABC-A-004", "Fix the badge printer", None),
                         ("ABC-001", "Key person leaves", "ABC-M-001"), ("ABC-002", "Supplier portal is down", None)):
    for _r in ROWS["actions"] + ROWS["raid"]:
        if _r["id"] == _id:
            _r["description"], _r["milestone"] = _title, _ms
ROWS["decisions"][0]["decision"] = "Pick the vendor"
LEFT = [{"not": {"owner": ["Pat Demo"]}}, {"milestone": ["go LIVE"]}, {"milestone": ["(none)"]}, {"has": [["owner"]]}, {"no": [["due"]]},
        {"text": ["supplier"]}, {"text": ["abc-00"]}, {"not": {"due": ["overdue"]}}, {"has": [["owner", "due"]], "mode": "all"},
        {"no": [["owner", "milestone"]]}, {"not": {"kinds": ["risk", "issue"], "milestone": ["Pilot"]}}, {"text": ["second wave", "plan"]}]
FILTERS = [{}, {"mode": "all"}, {"mode": "closed"}, {"kinds": ["risk", "issue"]}, {"kinds": ["decision"], "mode": "all"},
           {"due": ["overdue"]}, {"due": ["soon", "none"]}, {"due": ["later"], "mode": "all"}, {"owner": ["Pat Demo"]},
           {"owner": ["(none)"], "mode": "all"}, {"workstream": ["Build", "(none)"]}, {"use_case": ["ABC-U-001"], "mode": "all"},
           {"priority": ["Urgent", "High"]}, {"priority": ["(none)"], "mode": "all"}, {"status": ["Delayed", "Pending"]},
           {"sort": "priority", "mode": "all"}, {"sort": "id", "mode": "all"}, {"max": 3}, {"max": 1, "sort": "priority"},
           {"kinds": ["action"], "owner": ["Sam Demo", "Pat Demo"], "mode": "all", "sort": "priority"}] + LEFT


class Rules(unittest.TestCase):
    def test_the_rules_choose_and_order_as_written(self):
        ctx = base.Context(ROWS, TODAY)
        ids = lambda v: wi.matching(check(v), wi.rows_of(ctx.rows), TODAY)
        self.assertEqual(ids({}), ["ABC-A-001", "ABC-002", "ABC-D-001", "ABC-A-002", "ABC-A-005", "ABC-001", "ABC-A-004"],
                         "open first, the soonest due first, no date last, then the id")
        self.assertEqual(ids({"due": ["overdue"]}), ["ABC-A-001", "ABC-002"])
        self.assertEqual(ids({"sort": "priority"}), ["ABC-002", "ABC-A-004", "ABC-A-001", "ABC-001", "ABC-A-005", "ABC-D-001", "ABC-A-002"])
        self.assertEqual(ids({"owner": ["(none)"], "mode": "all"}), ["ABC-A-004", "ABC-003"], "a blank owner has none")
        self.assertEqual(ids({"mode": "closed", "due": ["none"]}), ["ABC-A-006"], "a closed row with a made-up day has no date")

    def test_not_has_no_milestone_and_free_words_choose_as_the_page_reads_them(self):
        ids = lambda v: wi.matching(check(v), wi.rows_of(ROWS), TODAY)
        self.assertEqual(ids({"not": {"owner": ["Pat Demo"]}}), ["ABC-002", "ABC-A-002", "ABC-A-005", "ABC-A-004"])
        self.assertEqual(ids({"milestone": ["go LIVE"]}), ["ABC-A-001", "ABC-001"], "a milestone is read without regard to case")
        self.assertEqual(ids({"milestone": ["(none)"]}), ["ABC-002", "ABC-D-001", "ABC-A-002", "ABC-A-004"])
        self.assertEqual(ids({"has": [["owner"]]}), ["ABC-A-001", "ABC-002", "ABC-D-001", "ABC-A-002", "ABC-A-005", "ABC-001"])
        self.assertEqual(ids({"no": [["due"]]}), ["ABC-001", "ABC-A-004"])
        self.assertEqual(ids({"text": ["supplier"]}), ["ABC-A-001", "ABC-002"], "the title is searched, not the case")
        self.assertEqual(ids({"text": ["abc-00"]}), ["ABC-002", "ABC-001"], "the id is searched too")
        self.assertEqual(ids({"not": {"due": ["overdue"]}}), ["ABC-D-001", "ABC-A-002", "ABC-A-005", "ABC-001", "ABC-A-004"])
        self.assertEqual(ids({"no": [["owner", "milestone"]]}), ["ABC-002", "ABC-D-001", "ABC-A-002", "ABC-A-004"], "no: with two fields is either one empty")

    def test_the_new_parts_are_checked_and_an_old_saved_filter_reads_as_before(self):
        got = check({"has": [["due", "owner"]], "no": [["milestone"]], "text": ["  two   words ", "two words"], "not": {"owner": ["Pat Demo"]}})
        self.assertEqual((got["has"], got["no"], got["text"], got["not"]["owner"]), ([["owner", "due"]], [["milestone"]], ["two words"], ["Pat Demo"]))
        self.assertEqual(set(got["not"]), set(wi.LEFT_OUT))
        for value in ({"has": [["client"]]}, {"has": [[]]}, {"has": "owner"}, {"no": [["owner"]] * 11}, {"text": [""]}, {"text": ["x" * 121]},
                      {"not": {"client": ["x"]}}, {"not": {"kinds": ["ZQ-kind"]}}, {"not": []}, {"milestone": [5]}):
            with self.subTest(value=value):
                with self.assertRaises(base.Bad):
                    check(value)
        old = {"v": 1, "kinds": ["risk"], "mode": "open", "status": [], "due": [], "owner": [], "workstream": [], "use_case": [],
               "priority": [], "sort": "due", "max": 10, "columns": ["id"], "caption": ""}
        self.assertEqual(check(old)["kinds"], ["risk"])
        self.assertEqual(wi.matching(check(old), wi.rows_of(ROWS), TODAY), ["ABC-001"])

    def test_published_carries_ordered_kept_ids_columns_and_caption_and_never_the_filter(self):
        ctx = base.Context(ROWS, TODAY)
        got = section_bodies.published("workitems", check({"kinds": ["risk", "issue"], "columns": ["id", "owner"], "caption": "Red items",
                                                           "owner": ["Lee Demo", "Pat Demo"]}), ctx)
        self.assertEqual(got, {"items": ["ABC-002", "ABC-001"], "columns": ["id", "owner"], "caption": "Red items"})
        self.assertIsNone(section_bodies.published("workitems", check({"owner": ["Nobody Demo"]}), ctx), "an empty match is left out")
        self.assertIsNone(section_bodies.published("workitems", check({}), base.Context()), "no kept rows: left out")
        self.assertIsNone(section_bodies.published("workitems", {"v": 1}), "an unchecked value is never published")


def bare_page():
    """The template's pure rules, bundled by the pinned esbuild in a temporary folder, on a bare page."""
    if "html" not in _PAGE:
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "entry.js"
            entry.write_text('import * as W from "@src/templates/workItemsList.js";\nimport * as L from "@src/templates/workItemsLine.js";\n'
                             'import { evaluateQuery } from "@src/logic/filterQueryEval.js";\nimport { rowsOf } from "@src/workItems.js";\n'
                             'window.W = W;\nwindow.L = L;\nwindow.Q = { evaluateQuery, rowsOf };\n', encoding="utf-8")
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(entry), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class PageRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=bare_page)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.W", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertFalse(str(got).startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def test_the_page_and_publish_choose_the_same_ids_in_the_same_order(self):
        for f in FILTERS:
            with self.subTest(filter=f):
                want = wi.matching(check(f), wi.rows_of(ROWS), TODAY)
                body = stored(f)
                page = self.val(f"W.matching(W.filterOf({{body: {json.dumps(body)}}}), W.ruleRows({json.dumps(ROWS)}), {json.dumps(TODAY)})")
                self.assertEqual(page, want)

    def test_a_name_that_is_gone_matches_nothing_and_the_page_and_publish_agree(self):
        every = lambda f: wi.matching(check(f), wi.rows_of(ROWS), TODAY)
        for f, lv, plive, want in (
                ({"owner": ["Pat Demo"], "mode": "all"}, {"goneOwner": ["pat demo"]}, {"gone_owner": frozenset({"pat demo"})}, []),
                ({"owner": ["Pat Demo", "Lee Demo"], "mode": "all"}, {"goneOwner": ["pat demo"]}, {"gone_owner": frozenset({"pat demo"})}, every({"owner": ["Lee Demo"], "mode": "all"})),
                ({"workstream": ["Build"], "mode": "all"}, {"workstream": ["run"]}, {"workstream": frozenset({"run"})}, []),
                ({"workstream": ["Build", "Run"], "mode": "all"}, {"workstream": ["run"]}, {"workstream": frozenset({"run"})}, every({"workstream": ["Run"], "mode": "all"})),
                ({"use_case": ["ABC-U-001"], "mode": "all"}, {"use_case": []}, {"use_case": frozenset()}, []),
                ({"use_case": ["ABC-U-001"], "mode": "all"}, {"use_case": ["ABC-U-001"]}, {"use_case": frozenset({"ABC-U-001"})}, every({"use_case": ["ABC-U-001"], "mode": "all"})),
                ({"owner": ["(none)"], "mode": "all"}, {"goneOwner": ["pat demo"]}, {"gone_owner": frozenset({"pat demo"})}, every({"owner": ["(none)"], "mode": "all"}))):
            with self.subTest(filter=f, live=lv):
                self.assertEqual(wi.matching(check(f), wi.rows_of(ROWS), TODAY, plive), want)
                page = self.val(f"W.matching(W.filterOf({{body: {json.dumps(stored(f))}}}), W.ruleRows({json.dumps(ROWS)}), {json.dumps(TODAY)}, {json.dumps(lv)})")
                self.assertEqual(page, want)
        self.assertTrue(every({"owner": ["Pat Demo"], "mode": "all"}), "the rows are there; only the missing name makes it empty")

    def test_a_filter_naming_what_is_gone_lists_none_and_its_line_is_still_shown(self):
        data = {"project": {"code": "ABC"}, "labels": {}, "report_sections": [], "use_cases": [], "milestones": [], "gone_owners": ["pat demo"],
                "actions": [dict(r, project="ABC", archived=0, client_visible=1, description=r["id"]) for r in ROWS["actions"]], "raid": [], "decisions": []}
        section = {"id": "ABC-S-001", "body": stored({"owner": ["Pat Demo"], "mode": "all"})}
        got = self.val(f"(function(){{ var d = {json.dumps(data)}, s = {json.dumps(section)}; var l = W.listOf(s, d, {json.dumps(TODAY)});"
                       f" return {{ n: l.items.length, saved: l.saved, line: L.lineOf(W.filterOf(s)) }}; }})()")
        self.assertEqual(got, {"n": 0, "saved": True, "line": 'owner:"Pat Demo" is:open,closed'})
        data["gone_owners"] = []
        again = self.val(f"W.listOf({json.dumps(section)}, {json.dumps(data)}, {json.dumps(TODAY)}).items.length")
        self.assertGreater(again, 0, "the same filter lists rows while the owner is still on the list")

    def test_a_typed_line_lists_what_the_work_items_pages_own_line_lists(self):
        lines = ['-owner:"Pat Demo"', 'milestone:"go live"', "milestone:none", "has:owner", "no:due", "supplier", '"second wave"', "-due:overdue",
                 "-is:overdue", "is:overdue", "-status:Delayed type:action", "has:owner,due", "no:owner,milestone", '-milestone:"Go live"',
                 "-type:risk,issue", "-priority:none", "due:next-7-days -type:decision", "Supplier -has:milestone", "-is:closed no:workstream"]
        for line in lines:
            with self.subTest(line=line):
                got = self.val(f"(function(){{ var r = L.readLine({json.dumps(line)}, W.defaults(), []); if (r.problem) return {{problem: r.problem}};"
                               f" r.filter.max = 50; return W.matching(r.filter, W.ruleRows({json.dumps(ROWS)}), {json.dumps(TODAY)}).sort(); }})()")
                data = dict(ROWS, use_cases=[])
                data = {k: ([dict(r, project="ABC") for r in v] if k != "use_cases" else v) for k, v in data.items()}
                want = self.val(f"Q.evaluateQuery(Q.rowsOf({json.dumps(data)}), {json.dumps(line + ' is:open')}, {{today: {json.dumps(TODAY)}, me: ''}})"
                                ".map(function (r) { return r.id; }).sort()")
                self.assertEqual(got, want)

    def test_the_line_is_read_back_the_way_it_was_typed_and_what_cannot_be_used_is_refused(self):
        for line in ['type:risk -owner:"Pat Demo" milestone:"Go live" has:owner,due no:workstream supplier "second wave"', "-due:overdue is:closed"]:
            with self.subTest(line=line):
                again = self.val(f"(function(){{ var a = L.readLine({json.dumps(line)}, W.defaults(), []).filter;"
                                 f" var b = L.readLine(L.lineOf(a), W.defaults(), []).filter; return [a, b]; }})()")
                self.assertEqual(again[0], again[1])
                self.assertEqual(check(again[0]), again[0], "what the line saves is what the checker keeps")
        for line in ["client:yes", "is:quiet", "colour:red", "owner:@me", "-is:open -is:closed", "has:client", "due:zzz"]:
            with self.subTest(line=line):
                self.assertIn("problem", self.val(f"L.readLine({json.dumps(line)}, W.defaults(), [])"))

    def test_the_page_and_publish_name_the_same_choices(self):
        for name in ("KINDS", "MODES", "STATUSES", "DUE", "PRIORITIES", "SORTS", "COLUMNS", "DEFAULT_COLUMNS"):
            self.assertEqual(self.val(f"W.{name}"), list(getattr(wi, name)), name)
        for name in ("NONE", "MAX_ROWS", "DEFAULT_MAX", "MAX_CAPTION"):
            self.assertEqual(self.val(f"W.{name}"), getattr(wi, name), name)
        self.assertEqual(self.val("W.defaults()"), check({}))

    def test_the_served_list_keeps_only_what_would_publish(self):
        data = {"project": {"code": "ABC"}, "labels": {"ABC-A-002": ["Sensitive"]}, "report_sections": [], "use_cases": [], "milestones": [],
                "actions": [dict(r, project="ABC", archived=0, client_visible=1, description=r["id"]) for r in ROWS["actions"]],
                "raid": [], "decisions": []}
        data["actions"][4]["client_visible"] = 0
        data["actions"][0]["archived"] = 1
        body = json.dumps(stored({"mode": "all", "sort": "id"}))
        got = self.val(f"W.listOf({{type: 'workitems', body: {body}}}, {json.dumps(data)}, {json.dumps(TODAY)}).items")
        self.assertEqual(got, ["ABC-A-003", "ABC-A-004", "ABC-A-006"], "archived, client-off and Sensitive are left out")
        data["report_hidden"] = ["ABC-A-004"]
        self.assertEqual(self.val(f"W.listOf({{type: 'workitems', body: {body}}}, {json.dumps(data)}, {json.dumps(TODAY)}).items"),
                         ["ABC-A-003", "ABC-A-006"], "an eye-hidden id is left out when the data carries it")
        data["report_sections"] = [{"id": "ABC-S-001", "type": "actions", "hidden": 1}]
        self.assertEqual(self.val(f"W.listOf({{type: 'workitems', body: {body}}}, {json.dumps(data)}, {json.dumps(TODAY)}).items"), [],
                         "a hidden Actions section leaves every action out")
        self.assertEqual(self.val(f"W.listOf({{type: 'workitems', body: ''}}, {json.dumps(data)}, {json.dumps(TODAY)})")["saved"], False)

    def test_a_file_section_draws_only_ids_its_data_holds(self):
        data = {"actions": [{"id": "ABC-A-001", "description": "One"}], "raid": [], "decisions": []}
        got = self.val(f"W.listOf({{type: 'workitems', items: ['ABC-A-009', 'ABC-A-001', 5], columns: ['owner', 'title', 'id']}}, {json.dumps(data)}, {json.dumps(TODAY)})")
        self.assertEqual(got["items"], ["ABC-A-001"])
        self.assertEqual(got["columns"], ["owner", "id"])


def plant(test):
    """Open and closed work items in ABC; one Sensitive, one client-off, one archived, one eye-hidden (all carry ZQ- markers)."""
    d, s = test.demo, test.demo.store
    test.a_due = d.action(description="Chase the supplier file", owner="Pat Demo", due_date="2030-01-10", priority="High")
    test.a_later = d.action(description="Plan the second wave", owner="Lee Demo", due_date="2030-03-01")
    test.a_secret = d.action(description="ZQ-sensitive step", owner="Sam Demo", due_date="2030-01-11")
    test.a_off = d.action(description="ZQ-client-off step", owner="Sam Demo", due_date="2030-01-12", client_visible=0)
    test.a_arch = d.action(description="ZQ-archived step", owner="Sam Demo", due_date="2030-01-12")
    test.a_eye = d.action(description="ZQ-eye-hidden step", owner="Kim Demo", due_date="2030-01-13")   # its own owner: see InThePage
    with s.step("dashboard", USER) as st:
        test.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Key person leaves", "raised": "2026-10-01",
                                       "source": "demo", "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
    with s.step("dashboard", USER) as st:
        st.archive("actions", test.a_arch)
    s.con.execute("INSERT OR IGNORE INTO item_labels (item_id, label) VALUES (?, 'Sensitive')", (test.a_secret,))
    s.con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (test.a_eye,))
    s.con.commit()


class Saved(Api):
    def setUp(self):
        super().setUp()
        plant(self)
        self.ref = self.ok("new", values={"type": "workitems", "title": "Due soon"}, after=None)["ref"]

    def body(self):
        return self.s.read("report_sections", ref=self.ref)["body"]

    def save(self, value):
        return self.ok(changes.UPDATE, id=self.ref, changes={"body": json.dumps(value)}, place="report")

    def test_a_new_list_starts_empty_and_stays_out_of_the_file(self):
        self.assertEqual(self.body(), "")
        built = publish.build(self.s, "ABC", now=TODAY)
        self.assertNotIn(self.ref, [s["id"] for s in built["published"]["sections"]])

    def test_one_save_is_one_step_and_one_undo_puts_the_old_filter_back(self):
        steps = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        first = self.save({"kinds": ["action"]})
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps + 1)
        self.save({"kinds": ["action"], "max": 3})
        self.assertEqual(json.loads(self.body())["max"], 3)
        last = self.s.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        status, got = self.undone(last)
        self.assertEqual(status, 200, got)
        self.assertEqual(json.loads(self.body())["max"], 10)
        status, got = self.undone(first["apply_id"])
        self.assertEqual(status, 200, got)
        self.assertEqual(self.body(), "")

    def listed(self):
        sec = next((x for x in publish.build(self.s, "ABC", now=TODAY)["published"]["sections"] if x["id"] == self.ref), None)
        return sec["items"] if sec else []

    def person_with_item(self, name):
        with self.s.step("dashboard", USER) as st:
            pid = st.add_person(name=name, source="demo")
        item = self.demo.action(description="Row for the live name", owner=name, due_date="2030-01-09")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", item, {"owner": name, "owner_id": pid})
        return pid, item

    def test_a_renamed_owner_or_workstream_is_followed_by_the_section(self):
        pid, item = self.person_with_item("Zed Demo")
        self.save({"owner": ["Zed Demo"], "not": {"owner": ["zed  demo"]}})
        with self.s.step("dashboard", USER) as st:
            st.rename_person(pid, "Zed Renamed")
        got = json.loads(self.body())
        self.assertEqual((got["owner"], got["not"]["owner"]), (["Zed Renamed"], ["Zed Renamed"]), "the saved words follow the live name")
        self.save({"owner": ["Zed Demo"]})
        self.assertEqual(self.listed(), [], "the old name matches nothing")
        self.save({"owner": ["Zed Renamed"]})
        self.assertEqual(self.listed(), [item])
        with self.s.step("dashboard", USER) as st:
            ws = st.create("workstreams", {"project": "ABC", "name": "Lane One", "source": "demo"})
            st.update("actions", item, {"workstream": "Lane One"})
        self.save({"workstream": ["Lane One"]})
        self.assertEqual(self.listed(), [item])
        with self.s.step("dashboard", USER) as st:
            st.update("workstreams", ws, {"name": "Lane Two"})
        self.assertEqual(json.loads(self.body())["workstream"], ["Lane Two"])
        self.assertEqual(self.listed(), [item])

    def test_an_owner_or_workstream_or_use_case_that_is_gone_matches_nothing_and_the_filter_stays(self):
        pid, item = self.person_with_item("Zed Demo")
        with self.s.step("dashboard", USER) as st:
            ws = st.create("workstreams", {"project": "ABC", "name": "Lane One", "source": "demo"})
            st.update("actions", item, {"workstream": "Lane One"})
        for f in ({"owner": ["Zed Demo"]}, {"workstream": ["Lane One"]}):
            self.save(f)
            self.assertEqual(self.listed(), [item])
        with self.s.step("dashboard", USER) as st:
            st.archive_person(pid)
        self.s.con.execute("UPDATE workstreams SET archived = 1 WHERE id = ?", (ws,))      # no step archives a workstream yet; the rules read the flag
        self.s.con.commit()
        for f in ({"owner": ["Zed Demo"]}, {"workstream": ["Lane One"]}):
            self.save(f)
            self.assertEqual(self.listed(), [], f"{f} is gone")
            self.assertEqual(json.loads(self.body())[next(iter(f))], list(f.values())[0], "the filter still names it")
        self.save({"owner": ["Zed Demo", "Pat Demo"]})
        self.assertEqual(self.listed(), [self.a_due, self.risk], "a name that is left still matches")

    def test_a_refused_filter_writes_nothing_and_says_why_without_quoting_it(self):
        got = self.refused(self.req(changes.UPDATE, id=self.ref, changes={"body": json.dumps({"kinds": ["ZQ-kind"]})}, place="report"), wi.BAD_CHOICE)
        self.assertNotIn("ZQ-", got["message"])

    def test_the_file_carries_only_kept_ids_in_order_and_never_the_filter_or_a_hidden_item(self):
        self.save({"mode": "all", "columns": ["id", "owner", "due"], "caption": "What is due", "owner": ["Pat Demo", "Lee Demo", "Sam Demo", "Kim Demo"]})
        built = publish.build(self.s, "ABC", now=TODAY)
        sec = next(s for s in built["published"]["sections"] if s["id"] == self.ref)
        self.assertEqual(sec["items"], [self.a_due, self.a_later, self.risk])
        self.assertEqual(sec["columns"], ["id", "owner", "due"])
        self.assertEqual(sec["caption"], "What is due")
        self.assertEqual(set(sec), {"id", "type", "title", "beside", "items", "columns", "caption"}, "the filter is never in the file")
        text = built["body"].decode("utf-8")
        for planted in ("ZQ-sensitive step", "ZQ-client-off step", "ZQ-archived step", "ZQ-eye-hidden step"):
            self.assertNotIn(planted, text)
        for hidden in (self.a_secret, self.a_off, self.a_arch, self.a_eye):
            self.assertNotIn(hidden, text)
        self.assertNotIn("Sam Demo", text, "a name only in the filter never reaches the file")
        self.assertNotIn("Kim Demo", text)

    def test_an_empty_match_or_a_hidden_section_is_left_out_of_the_file(self):
        self.save({"owner": ["Sam Demo"]})             # every row of Sam's is kept out
        sections = publish.build(self.s, "ABC", now=TODAY)["published"]["sections"]
        self.assertNotIn(self.ref, [s["id"] for s in sections])
        self.save({})
        self.assertIn(self.ref, [s["id"] for s in publish.build(self.s, "ABC", now=TODAY)["published"]["sections"]])
        self.ok(changes.UPDATE, id=self.ref, changes={"hidden": 1})
        self.assertNotIn(self.ref, [s["id"] for s in publish.build(self.s, "ABC", now=TODAY)["published"]["sections"]])

    def test_a_hidden_actions_section_drops_every_action_from_the_list(self):
        self.save({"mode": "all"})
        with self.s.step("dashboard", USER) as st:
            st.create("report_sections", {"project": "ABC", "type": "actions", "title": "Open actions", "sort_order": 50, "hidden": 1})
        sec = next(s for s in publish.build(self.s, "ABC", now=TODAY)["published"]["sections"] if s["id"] == self.ref)
        self.assertEqual(sec["items"], [self.risk])


class InThePage(PageBase):
    """The page clark serves. Its data (Store.data_for) does not carry the eye's hidden ids yet, so these lists never name the
    eye-hidden item's owner; PageRules shows the page leaves an eye-hidden id out once the data carries it."""

    def setUp(self):
        super().setUp()
        plant(self)

    def add(self, value=None, title="Due soon", after=None, beside=0):
        req = {"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": title}, "after": after}
        if beside:
            req["beside"] = 1
        status, got = self.real_change(req)
        self.assertEqual(status, 200, got)
        ref = got["ref"]
        if value is not None:
            status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": ref,
                                            "changes": {"body": json.dumps(value)}})
            self.assertEqual(status, 200, got)
        return ref

    def show(self, cdp, width=1400, dark=False):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p

    def rows(self, p, ref, part="table"):
        sel = f"[data-id=\"{ref}\"] .wil-table tbody tr" if part == "table" else f"[data-id=\"{ref}\"] .wil-lines li"
        return p.js(f"[...document.querySelectorAll({json.dumps(sel)})].filter(e => e.offsetParent).map(e => e.dataset.id)")

    def test_view_shows_the_live_rows_the_client_sees_at_both_widths_in_light_and_dark(self):
        ref = self.add({"mode": "all", "owner": ["Pat Demo", "Lee Demo", "Sam Demo"]})          # Sam's three are all kept out
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table')", "the list drew")
                    self.assertEqual(self.rows(p, ref), [self.a_due, self.a_later, self.risk])
                    text = p.js("document.querySelector('#report').textContent")
                    for planted in ("ZQ-sensitive step", "ZQ-client-off step", "ZQ-archived step"):
                        self.assertNotIn(planted, text)
                    self.assertEqual(p.js(f"document.querySelectorAll('[data-id=\"{ref}\"] input, [data-id=\"{ref}\"] select, [data-id=\"{ref}\"] [tabindex]').length"), 0,
                                     "View is read only: no control and no row to open")
                    self.assertEqual(self.rows(p, ref, "lines"), [], "full width draws the table only")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    head = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table th')].map(e => e.textContent)")
                    self.assertEqual(head, ["Type", "ID", "Item", "Owner", "Due", "Status"])

    def test_text_contrast_is_at_least_4_5_to_1_in_light_and_dark(self):
        ref = self.add({"mode": "all", "caption": "Fictional caption", "owner": ["Pat Demo"]})
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const out = [];
          for (const sel of ['.wil-table th', '.wil-table td.wil-c-title', '.wil-table td.wil-c-id', '.wil-cap']) {
            const el = document.querySelector(sel); if (!el) { out.push([sel, 0]); continue; }
            let bg = el, back = 'rgba(0, 0, 0, 0)';
            while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
            out.push([sel, ratio(getComputedStyle(el).color, back)]);
          }
          return out;
        })()"""
        for dark in (False, True):
            with self.subTest(dark=dark), chrome() as cdp:
                p = self.show(cdp, 1400, dark)
                p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table')", "the list drew")
                for sel, r in p.js(script):
                    self.assertGreaterEqual(r, 4.5, f"{sel} in {'dark' if dark else 'light'}")

    def test_half_width_draws_two_line_rows(self):
        with self.store.step("dashboard", USER) as st:
            text = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 1})
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]}, after=text, beside=1)
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"document.querySelector('[data-id=\"{ref}\"]') && document.querySelector('[data-id=\"{ref}\"]').classList.contains('slot-right')", "the list is the right half")
            self.assertEqual(self.rows(p, ref, "table"), [], "half width hides the table")
            self.assertEqual(self.rows(p, ref, "lines"), [self.a_due, self.a_later, self.risk])
            line = p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-lines li .wil-m').textContent")
            self.assertEqual(line, f"{self.a_due} · Pat Demo")

    def test_an_empty_match_is_left_out_of_view_and_said_in_edit(self):
        ref = self.add({"owner": ["Sam Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"]')"), "View leaves an empty match out")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-say=none]')", "Edit says nothing matches")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-wil-say=none]').textContent"),
                             "No work items match this filter, so this section is left out of the published page. Change the filter to list some.")

    def test_a_new_list_says_how_to_start_it_and_one_tick_saves_one_step_with_undo(self):
        ref = self.add()
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"]')"), "an unsaved list is not in View")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-say=not-yet]')", "the start line")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-wil-say=not-yet]').textContent"),
                             "No filter is saved for this section yet. Save one on Work items and it shows here.")
            steps = self.demo.last_step()
            p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-field=kinds] input[value=risk]').click()")
            p.saved()
            self.assertEqual(self.toast(p), "Work items list changed.")
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["kinds"], ["risk"])
            self.assertEqual(self.demo.last_step(), steps + 1, "one tick, one step")
            p.until(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table tbody tr')].map(e => e.dataset.id).join() === {json.dumps(self.risk)}", "the preview follows")
            sent = [r for w, r in self.sent if w == "change"]
            self.assertEqual(sent[-1]["place"], "report")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-say=not-yet]')", "Undo puts the empty list back")
            self.assertEqual(self.store.read("report_sections", ref=ref)["body"], "")

    def test_the_number_and_the_caption_save_when_left_and_a_bad_number_is_refused(self):
        ref = self.add({})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            sel = f"[data-id=\"{ref}\"] [data-field=max] input"
            p.until(f"!!document.querySelector({json.dumps(sel)})", "the form drew")
            steps = self.demo.last_step()
            p.js(f"(el => {{ el.focus(); el.value = '99'; el.dispatchEvent(new Event('change', {{bubbles: true}})); }})(document.querySelector({json.dumps(sel)}))")
            p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent.startsWith('Show between')", "refused")
            self.assertEqual(self.demo.last_step(), steps, "nothing saved")
            p.clear_toast()
            p.js(f"(el => {{ el.focus(); el.value = '2'; el.dispatchEvent(new Event('change', {{bubbles: true}})); }})(document.querySelector({json.dumps(sel)}))")
            p.saved()
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["max"], 2)
            p.until(f"document.querySelectorAll('[data-id=\"{ref}\"] .wil-table tbody tr').length === 2", "two rows")
            p.clear_toast()
            cap = f"[data-id=\"{ref}\"] [data-field=caption] input"
            p.js(f"document.querySelector({json.dumps(cap)}).focus()")
            p.type("Fictional caption")
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["caption"], "Fictional caption")
            self.assertEqual(self.demo.last_step(), steps + 2)

    def test_the_edit_form_fits_both_widths_in_light_and_dark_with_a_focus_ring(self):
        ref = self.add({"owner": ["Pat Demo"]})
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.edit()
                    box = f"[data-id=\"{ref}\"] [data-field=kinds] input[value=action]"
                    p.until(f"!!document.querySelector({json.dumps(box)})", "the form drew")
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-wil-more]').open = true")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    p.js(f"document.querySelector({json.dumps(box)}).focus()")
                    p.key("Tab", code="Tab", vk=9)
                    p.key("Tab", code="Tab", vk=9, modifiers=8)
                    self.assertEqual(p.js(f"document.activeElement === document.querySelector({json.dumps(box)})"), True)
                    self.assertEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "solid", "the focus ring shows")
                    legends = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-f legend, [data-id=\"{ref}\"] .wil-sel > span')].map(e => e.textContent)")
                    self.assertEqual(legends, ["Filter", "Kinds", "Show", "Due", "Status", "Priority", "Owner", "Workstream", "Use case", "Sort by",
                                               "Most rows", "Columns at full width", "Caption (optional)"])

    def test_rows_open_their_peek_in_edit_with_a_click_or_enter(self):
        ref = self.add({"mode": "all", "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            row = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"]"
            p.until(f"!!document.querySelector({json.dumps(row)})", "the preview drew")
            self.assertEqual(p.js(f"document.querySelector({json.dumps(row)}).tabIndex"), 0)
            p.js(f"document.querySelector({json.dumps(row)}).click()")
            p.until(f"location.hash.includes('item={self.a_due}')", "the click opened its peek")
            p.js("history.back()")
            p.until(f"!location.hash.includes('item=')", "closed")
            later = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_later}\"]"
            p.until(f"!!document.querySelector({json.dumps(later)})", "still drawn")
            p.js(f"document.querySelector({json.dumps(later)}).focus()")
            p.key("Enter", code="Enter", vk=13)
            p.until(f"location.hash.includes('item={self.a_later}')", "Enter opened its peek")

    def test_the_filter_line_saves_what_is_typed_shows_chips_and_a_chip_x_takes_one_off(self):
        for width in (1400, 900):
            ref = self.add({}, title=f"Line {width}")
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                line = f"[data-id=\"{ref}\"] [data-wil-line] input[name=line]"
                p.until(f"!!document.querySelector({json.dumps(line)})", "the line drew")
                self.assertFalse(p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-wil-more]').open"), "the tick boxes start folded")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                steps = self.demo.last_step()
                p.js(f"document.querySelector({json.dumps(line)}).focus()")
                p.type("type:risk,issue status:Open")
                p.key("Enter", code="Enter", vk=13)
                p.saved()
                body = json.loads(self.store.read("report_sections", ref=ref)["body"])
                self.assertEqual((body["kinds"], body["status"]), (["risk", "issue"], ["Open"]))
                self.assertEqual(self.demo.last_step(), steps + 1, "one line, one step")
                chips = f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-chip')]"
                p.until(f"{chips}.length === 3", "three chips")
                self.assertTrue(p.js(f"{chips}.every(c => c.querySelector('button').getBoundingClientRect().height >= 24)"), "24 px targets")
                p.clear_toast()
                p.js(f"{chips}.find(c => c.textContent.includes('Issues')).querySelector('button').click()")
                p.saved()
                self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["kinds"], ["risk"])
                p.clear_toast()
                steps = self.demo.last_step()
                p.js(f"(el => {{ el.focus(); el.value = 'colour:red'; }})(document.querySelector({json.dumps(line)}))")
                p.key("Enter", code="Enter", vk=13)
                p.until("document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent.includes('not a word the filter line knows')", "refused in words")
                self.assertEqual(self.demo.last_step(), steps, "nothing saved")

    def test_the_filter_line_clears_refuses_a_bad_value_and_finds_a_use_case_by_title_or_id(self):
        for width in (1400, 900):
            ref = self.add({"status": ["Open"], "kinds": ["risk"], "mode": "closed"}, title=f"Clear {width}")
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                line = f"[data-id=\"{ref}\"] [data-wil-line] input[name=line]"
                p.until(f"!!document.querySelector({json.dumps(line)})", "the line drew")

                def enter(text):
                    p.js(f"(el => {{ el.focus(); el.value = {json.dumps(text)}; }})(document.querySelector({json.dumps(line)}))")
                    p.key("Enter", code="Enter", vk=13)

                def body():
                    return json.loads(self.store.read("report_sections", ref=ref)["body"])

                def said(words):
                    p.until(f"!!document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent.includes({json.dumps(words)})", words)

                # a bad value: named back in words, nothing saved, the old filter stays
                steps = self.demo.last_step()
                enter("status:Bogus")
                said("is not a value status can take here")
                self.assertEqual(self.demo.last_step(), steps, "nothing saved for status:Bogus")
                self.assertEqual((body()["status"], body()["kinds"], body()["mode"]), (["Open"], ["risk"], "closed"))
                p.clear_toast()
                # a use case that is not there is refused the same way
                enter("usecase:Nothing")
                said("is not a value usecase can take here")
                self.assertEqual(self.demo.last_step(), steps, "nothing saved for an unknown use case")
                p.clear_toast()
                # a use case by its title, then by its id: both save its id
                enter('usecase:"Invoice matching"')
                p.saved()
                self.assertEqual(body()["use_case"], ["ABC-U-001"], "found by title")
                p.clear_toast()
                enter("status:Open")
                p.saved()
                self.assertEqual(body()["use_case"], [], "the use case came off with the line")
                p.clear_toast()
                enter("usecase:ABC-U-001 is:open")
                p.saved()
                self.assertEqual((body()["use_case"], body()["mode"]), (["ABC-U-001"], "open"), "found by id")
                p.clear_toast()
                # clearing the line empties every choice and goes back to open items only, in one step
                steps = self.demo.last_step()
                enter("")
                p.saved()
                got = body()
                self.assertEqual([got[k] for k in ("kinds", "status", "due", "priority", "owner", "workstream", "use_case")], [[]] * 7)
                self.assertEqual(got["mode"], "open")
                self.assertEqual(self.demo.last_step(), steps + 1, "clearing is one step")
                p.until(f"document.querySelectorAll('[data-id=\"{ref}\"] .wil-chip').length === 0", "no chips left")

    def test_sort_rows_columns_and_caption_stay_in_the_one_form_block(self):
        ref = self.add({}, title="Form")
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-line]')", "the line drew")
            forms = p.js(f"document.querySelectorAll('[data-id=\"{ref}\"] .wil-form').length")
            self.assertEqual(forms, 1, "one form block, as before the line was added")
            self.assertTrue(p.js(f"(f => ['sort', 'max', 'caption'].every(n => f.querySelector('[name=' + n + '], [data-field=' + n + ']')))"
                                 f"(document.querySelector('[data-id=\"{ref}\"] .wil-form'))"), "Sort by, Most rows and Caption sit in it")

    def test_two_ticks_made_before_the_first_reply_are_both_kept(self):
        ref = self.add({})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            base = f"[data-id=\"{ref}\"] [data-field=kinds] input"
            p.until(f"!!document.querySelector({json.dumps(base + '[value=risk]')})", "the form drew")
            steps = self.demo.last_step()
            p.js(f"(() => {{ for (const v of ['risk', 'action']) document.querySelector({json.dumps(base)}.replace('input', 'input[value=' + v + ']')).click(); }})()")
            p.until(f"document.querySelectorAll({json.dumps(base + ':checked')}).length === 2", "both ticks stay")
            p.saved()
            # Two saves are in flight and saved() returns on the FIRST toast; under load the second reply lands after that, so wait
            # for the second step in the store before reading the body (the store is the truth here, not the toast).
            self.assertTrue(wait(lambda: self.demo.last_step() == steps + 2), "two ticks, two steps")
            body = json.loads(self.store.read("report_sections", ref=ref)["body"])
            self.assertEqual(sorted(body["kinds"]), ["action", "risk"])

    def test_a_caption_of_many_emoji_is_typed_and_saved_as_counted_by_the_store(self):
        ref = self.add({})
        caption = "\U0001F600" * 150
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            cap = f"[data-id=\"{ref}\"] [data-field=caption] input"
            p.until(f"!!document.querySelector({json.dumps(cap)})", "the form drew")
            self.assertFalse(p.js(f"document.querySelector({json.dumps(cap)}).hasAttribute('maxlength')"))
            p.js(f"document.querySelector({json.dumps(cap)}).focus()")
            p.type(caption)
            p.key("Enter", code="Enter", vk=13)
            p.saved()
            self.assertEqual(json.loads(self.store.read("report_sections", ref=ref)["body"])["caption"], caption)

    def test_rows_are_buttons_and_space_opens_them_like_enter(self):
        ref = self.add({"mode": "all", "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            row = f"[data-id=\"{ref}\"] .wil-table tbody tr[data-id=\"{self.a_later}\"]"
            p.until(f"!!document.querySelector({json.dumps(row)})", "the preview drew")
            self.assertEqual(p.js(f"document.querySelector({json.dumps(row)}).getAttribute('role')"), "button")
            p.js(f"document.querySelector({json.dumps(row)}).focus()")
            p.key(" ", code="Space", vk=32)
            p.until(f"location.hash.includes('item={self.a_later}')", "Space opened its peek")

    def toast(self, p):
        return wait_toast(lambda: p.js("(document.querySelector('.toast-text') || {}).textContent || ''"))


class PublishedFile(PageBase):
    def setUp(self):
        super().setUp()
        plant(self)

    def test_the_file_draws_the_list_from_its_own_data_with_no_controls(self):
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": "Due soon"}, "after": None})
        ref = got["ref"]
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": ref,
                                        "changes": {"body": json.dumps({"mode": "all", "caption": "Fictional caption", "owner": ["Pat Demo", "Lee Demo", "Sam Demo", "Kim Demo"]})}})
        self.assertEqual(status, 200, got)
        out = tempfile.mkdtemp(prefix="clark-96-wil-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        text = path.read_text(encoding="utf-8")
        for planted in ("ZQ-sensitive step", "ZQ-client-off step", "ZQ-archived step", "ZQ-eye-hidden step", "Sam Demo", "Kim Demo", "wil-edit", "data-wil-say"):
            self.assertNotIn(planted, text)
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table')", "the list drew")
                ids = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .wil-table tbody tr')].map(e => e.dataset.id)")
                self.assertEqual(ids, [self.a_due, self.a_later, self.risk])
                self.assertEqual(p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-cap').textContent"), "Fictional caption")
                self.assertEqual(p.js(f"document.querySelectorAll('[data-id=\"{ref}\"] input, [data-id=\"{ref}\"] select, [data-id=\"{ref}\"] [tabindex]').length"), 0)
                self.assertIn("Overdue", p.js(f"document.querySelector('[data-id=\"{ref}\"]').textContent"), "Due reads as at the publish date")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")


if __name__ == "__main__":
    unittest.main()

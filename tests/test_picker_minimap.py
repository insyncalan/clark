"""#67 (Report editor 3 of 3), the pure parts: the project-record picker's logic and the contents minimap's logic, and the
two small components that use them. Rules: Done-when on the planning repo #67 (the picker "lists only hidden rows, searches, and takes
several at once"; the minimap "lists every visible section and none hidden", a click scrolls to the section, Tab and Esc work).

Run: python3 dev/run_tests.py test_picker_minimap
The repo has no Node, so the plain-JS logic runs inside headless Chrome (the #33 harness, as test_page.py does): the logic and
the components are bundled with the pinned esbuild into a temporary folder (never the repo), put on a page that the harness
server serves, and each case is evaluated there. Chrome is required: these tests fail, never skip, without it.
Nothing here saves anything: the save path is #65's, so the components only hand their callbacks the ids.
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

from test_server import Running, chrome, wait  # noqa: E402  (the #33 browser harness, shared)

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "picker_minimap_demo.jsx"
HOSTILE = '<script>window.pwned = 1</script><img src=x onerror="window.pwned = 2">'

# One fictional project in the shape Store.data_for gives (#31), with hidden and shown rows of every kind.
DATA = {
    "actions": [
        {"id": "ABC-A-001", "description": "Agree the cut-over plan", "owner": "Sam", "due_date": "2026-11-03", "client_visible": 1},
        {"id": "ABC-A-002", "description": "Book the training room", "owner": "TBC", "due_date": None, "client_visible": 0},
        {"id": "ABC-A-003", "description": "Send the invitations", "owner": "Priya", "due_date": "2026-11-10", "client_visible": 1},
    ],
    "raid": [
        {"id": "ABC-001", "type": "Risk", "description": "Supplier may deliver late", "owner": "Priya", "client_visible": 1},
        {"id": "ABC-002", "type": "Issue", "description": "The test system is down", "owner": "TBC", "client_visible": 1},
    ],
    "decisions": [{"id": "ABC-D-001", "decision": "Use the shared calendar", "made_by": "Steering group", "status": "Made", "client_visible": 1}],
    "milestones": [{"id": "ABC-M-001", "name": "Pilot live", "baseline_date": "2026-12-01", "state": "On track", "status": "Planned", "client_visible": 1},
                   {"id": "ABC-M-002", "name": "Go live", "baseline_date": "2027-02-01", "state": None, "status": "Planned", "client_visible": 1}],
    "use_cases": [{"id": "ABC-U-001", "ref": "1.1", "title": "Draft replies\nsecond line", "status": "Flag", "client_visible": 1}],
    "documents": [{"id": "d1", "title": "Steering minutes", "kind": "Minutes", "date": "2026-10-20"}],
}
HIDDEN = ["ABC-A-003", "ABC-001", "ABC-D-001", "ABC-U-001", "d1", "ABC-M-002"]       # plus ABC-A-002 (client_visible 0)
SECTIONS = [{"id": "current", "type": "current", "title": "Current state"},
            {"id": "glance", "type": "glance", "title": "At a glance"},
            {"id": "t1", "type": "text", "title": "Next steps"},
            {"id": "risks", "type": "raid", "title": "Risks and issues", "hidden": 1},
            {"id": "ms", "type": "milestones", "title": "Milestones"},
            {"id": "docs", "type": "docs", "title": "Documents"}]

_PAGE = {}


def test_page_html():
    """The logic and both components, bundled by the pinned esbuild in a temporary folder, on a page with the brand and shell CSS."""
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8"))
        css = css.replace("</style", "<\\/style")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8">'
                         f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>t</title>'
                         f'<style>\n{css}</style></head>\n<body><div id="root"></div>\n'
                         f'<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


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
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def load(self, width=1400, height=900):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.picker)", self.sid)), "the test bundle ran")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        """Evaluate an expression in the page and get its value back as JSON (so errors and undefined show up)."""
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertNotIsInstance(got, type(None), expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def key(self, key, code=None, vk=0, shift=False):
        base = {"key": key, "code": code or key, "windowsVirtualKeyCode": vk, "modifiers": 8 if shift else 0}
        self.cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **base}, self.sid)
        self.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **base}, self.sid)

    def tab(self, shift=False):
        self.key("Tab", "Tab", 9, shift)

    def settle(self):
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 150))", "awaitPromise": True}, self.sid)


def lit(x):
    return json.dumps(x)


class PickerLogic(InBrowser):
    def pick(self, query="", hidden=HIDDEN, data=DATA, on_page=None):
        return self.val(f"T.picker.pickable({lit(data)}, {lit(hidden)}, {lit(query)}, {lit(on_page)})")

    def ids(self, groups):
        return [[g["kind"], [r["id"] for r in g["rows"]]] for g in groups]

    def setUp(self):
        self.load()

    def test_only_rows_hidden_from_the_report_are_listed(self):
        got = self.ids(self.pick())
        listed = [i for _, ids in got for i in ids]
        self.assertEqual(sorted(listed), sorted(HIDDEN + ["ABC-A-002"]), "report_hidden rows, and a Work item with client_visible 0")
        for shown in ("ABC-A-001", "ABC-002", "ABC-M-001"):
            self.assertNotIn(shown, listed, f"{shown} is on the page, so the picker never offers it")

    def test_a_document_is_hidden_only_by_report_hidden_and_an_archived_row_is_never_offered(self):
        data = {"documents": [{"id": "d1", "title": "A", "client_visible": 0}, {"id": "d2", "title": "B"}],
                "actions": [{"id": "ABC-A-009", "description": "Old", "client_visible": 0, "archived": 1}]}
        self.assertEqual(self.ids(self.pick(data=data, hidden=["d2"])), [["documents", ["d2"]]])

    def test_search_is_case_insensitive_over_the_id_and_the_text_and_every_word_must_match(self):
        self.assertEqual(self.ids(self.pick("SUPPLIER")), [["raid", ["ABC-001"]]])
        self.assertEqual(self.ids(self.pick("abc-a-002")), [["actions", ["ABC-A-002"]]])
        self.assertEqual(self.ids(self.pick("  the   CALENDAR ")), [["decisions", ["ABC-D-001"]]])
        self.assertEqual(self.ids(self.pick("invitations nonsense")), [], "a word that matches nothing leaves nothing")
        self.assertEqual(self.ids(self.pick("steering")), [["documents", ["d1"]]], "a document's title is its text")
        self.assertEqual(self.ids(self.pick("second line")), [], "only a use case's first line is its text")

    def test_rows_are_grouped_by_kind_in_a_stable_order_whatever_order_the_ids_arrive_in(self):
        want = [["actions", ["ABC-A-002", "ABC-A-003"]], ["raid", ["ABC-001"]], ["decisions", ["ABC-D-001"]],
                ["milestones", ["ABC-M-002"]], ["usecases", ["ABC-U-001"]], ["documents", ["d1"]]]
        self.assertEqual(self.ids(self.pick()), want)
        self.assertEqual(self.ids(self.pick(hidden=list(reversed(HIDDEN)))), want)
        self.assertEqual([g["label"] for g in self.pick()], ["Actions", "Risks and issues", "Decisions", "Milestones", "Use cases", "Documents"])
        self.assertEqual(self.val(f"T.picker.pickable({lit(DATA)}, new Set({lit(HIDDEN)}), '').length"), 6, "a Set of ids works too")

    def test_a_row_already_back_on_the_page_is_never_listed_and_a_row_is_never_listed_twice(self):
        self.assertEqual(self.ids(self.pick(on_page=["ABC-A-003", "d1"]))[0], ["actions", ["ABC-A-002"]])
        self.assertNotIn("documents", [k for k, _ in self.ids(self.pick(on_page=["d1"]))])
        twice = {"actions": [{"id": "ABC-A-001", "description": "x", "client_visible": 0}, {"id": "ABC-A-001", "description": "x", "client_visible": 0}]}
        self.assertEqual(self.ids(self.pick(data=twice)), [["actions", ["ABC-A-001"]]])

    def test_taking_several_at_once(self):
        v = self.val(f"""(function () {{
            const P = T.picker, g = P.pickable({lit(DATA)}, {lit(HIDDEN)}, '');
            let s = P.toggle([], 'ABC-A-002'); s = P.toggle(s, 'ABC-001'); const two = s.slice();
            s = P.toggle(s, 'ABC-A-002'); const one = s.slice();
            const all = P.selectAll(one, g), again = P.selectAll(all, g);
            const narrowed = P.selectAll([], P.pickable({lit(DATA)}, {lit(HIDDEN)}, 'abc-a'));
            return {{ two, one, all, again, narrowed, cleared: P.clear(), count: [P.countWords(0), P.countWords(3), P.addWords(0), P.addWords(3)],
                     kept: P.chosen(['ABC-A-002', 'ABC-A-001', 'nope', 'ABC-001'], {lit(DATA)}, {lit(HIDDEN)}),
                     gone: P.chosen(['ABC-A-002', 'ABC-001'], {lit(DATA)}, {lit(HIDDEN)}, ['ABC-001']) }};
        }})()""")
        self.assertEqual(v["two"], ["ABC-A-002", "ABC-001"])
        self.assertEqual(v["one"], ["ABC-001"], "toggling again takes it out")
        self.assertEqual(len(v["all"]), 7)
        self.assertEqual(v["all"][0], "ABC-001", "what was chosen first stays first")
        self.assertEqual(v["again"], v["all"], "select all twice changes nothing")
        self.assertEqual(sorted(v["narrowed"]), ["ABC-A-002", "ABC-A-003"], "select all shown means the rows the search shows")
        self.assertEqual(v["cleared"], [])
        self.assertEqual(v["count"], ["None selected", "3 selected", "Add selected", "Add 3"])
        self.assertEqual(v["kept"], ["ABC-A-002", "ABC-001"], "a shown row (ABC-A-001) or a made-up id is never handed on")
        self.assertEqual(v["gone"], ["ABC-A-002"], "a row that went back on the page meanwhile is not added twice")

    def test_empty_states_in_plain_words(self):
        w = lambda q, hidden, data=DATA: self.val(f"T.picker.emptyWords({lit(data)}, {lit(hidden)}, {lit(q)})")
        self.assertEqual(w("", [], {}), "Everything is already on the page.")
        self.assertEqual(w("zzz", HIDDEN), "Nothing matches your search. Clear it to see what can be added.")
        self.assertEqual(w("supplier", HIDDEN), "")
        self.assertEqual(self.pick(data={}), [])
        self.assertEqual(self.pick(data=None, hidden=None), [])

    def test_a_plain_words_line_for_each_kind(self):
        said = {r["id"]: r["summary"] for g in self.pick(hidden=HIDDEN + ["ABC-M-001", "ABC-002", "ABC-A-001"]) for r in g["rows"]}
        self.assertEqual(said["ABC-A-001"], "Action ABC-A-001: Agree the cut-over plan (owner Sam, due 03-11-2026)")
        self.assertEqual(said["ABC-A-002"], "Action ABC-A-002: Book the training room (no owner, no due date)")
        self.assertEqual(said["ABC-001"], "Risk or issue ABC-001: Supplier may deliver late (risk, owner Priya)")
        self.assertEqual(said["ABC-002"], "Risk or issue ABC-002: The test system is down (issue, no owner)")
        self.assertEqual(said["ABC-D-001"], "Decision ABC-D-001: Use the shared calendar (made, by Steering group)")
        self.assertEqual(said["ABC-M-001"], "Milestone ABC-M-001: Pilot live (on track, agreed 01-12-2026)")
        self.assertEqual(said["ABC-M-002"], "Milestone ABC-M-002: Go live (planned, agreed 01-02-2027)")
        self.assertEqual(said["ABC-U-001"], "Use case 1.1 ABC-U-001: Draft replies (flag)")
        self.assertEqual(said["d1"], "Document d1: Steering minutes (Minutes, 20-10-2026)")
        long = self.val("T.picker.describe({ id: 'ABC-A-005', description: 'x'.repeat(400) })")
        self.assertTrue(len(long) <= 140 and long.endswith("…"))
        self.assertEqual(self.val("T.picker.describe({ id: 'ABC-A-006', description: '' })"), "Action ABC-A-006: No text (no owner, no due date)")
        self.assertEqual(self.val("T.picker.plainDate('not a date')"), "not a date")
        self.assertEqual(self.val("T.picker.plainDate('2026-13-01')"), "2026-13-01")

    def test_a_date_is_shown_day_month_year_like_everywhere_else_in_clark(self):
        plain = lambda v: self.val(f"T.picker.plainDate({lit(v)})")
        self.assertEqual(plain("2026-11-23"), "23-11-2026", "a normal date")
        self.assertEqual(plain("2026-03-04"), "04-03-2026", "a one-digit day and month are padded")
        self.assertEqual(plain("2026-11-03"), "03-11-2026")
        self.assertEqual(plain("2028-02-29"), "29-02-2028", "a real leap day")
        self.assertEqual(self.val("T.picker.plainDate('2026-11-03') === T.showDate('2026-11-03')"), True, "the same words as the Work items list")

    def test_a_date_that_is_not_a_real_day_is_never_made_into_one(self):
        plain = lambda v: self.val(f"T.picker.plainDate({lit(v)})")
        for odd in ("2026-02-31", "2027-02-29", "2026-04-31", "2026-00-10", "2026-13-01", "2026-11-00"):
            self.assertEqual(plain(odd), odd, f"{odd} is shown as it was stored, not as a day")
        said = self.val("T.picker.describe({ id: 'ABC-A-007', description: 'Odd', owner: 'Sam', due_date: '2026-02-31' })")
        self.assertEqual(said, "Action ABC-A-007: Odd (owner Sam, due 2026-02-31)")
        for nothing in ("", None):
            self.assertEqual(plain(nothing), "", "no date shows nothing")
        self.assertEqual(self.val("T.picker.plainDate()"), "")
        said = self.val("T.picker.describe({ id: 'd9', title: 'Plan', kind: 'Plan', date: '' })")
        self.assertEqual(said, "Document d9: Plan (Plan)", "an empty document date adds nothing")

    def test_a_long_line_is_cut_by_whole_characters_never_through_an_emoji(self):
        lone = "/[\\uD800-\\uDBFF](?![\\uDC00-\\uDFFF])|(?<![\\uD800-\\uDBFF])[\\uDC00-\\uDFFF]/"
        cut = 0
        for pad in range(100, 141):
            line = self.val(f"T.picker.describe({{ id: 'ABC-A-005', description: 'x'.repeat({pad}) + '\\u{{1F600}}' + 'y'.repeat(60) }})")
            self.assertIs(self.js(f"{lone}.test({lit(line)})"), False, f"pad {pad}: no half of an emoji is left at the cut")
            self.assertLessEqual(len(list(line)), 140)
            self.assertTrue(line.endswith("…"))
            cut += "\U0001F600" not in line and "x" * 50 in line
        self.assertGreater(cut, 0, "the cut did fall at or before the emoji in some cases")
        line = self.val(f"T.picker.describe({{ id: 'ABC-A-005', description: 'x'.repeat(112) + '\\u{{1F600}}' + 'y'.repeat(60) }})")
        self.assertIn("\U0001F600", line, "an emoji before the cut is kept whole")


class PickerPanel(InBrowser):
    def setUp(self):
        self.load()

    def mount(self, data=DATA, hidden=HIDDEN, on_page=None):
        self.js(f"T.mountPicker({lit(data)}, {lit(hidden)}, {lit(on_page)})")
        self.assertTrue(wait(lambda: self.js("!!document.querySelector('.picker')")))

    def rows(self):
        return self.val("Array.from(document.querySelectorAll('.pick input')).map(i => i.value)")

    def type_in_search(self, text):
        self.js(f"(function(){{ const q = document.querySelector('.pk-q input'); q.value = {lit(text)}; q.dispatchEvent(new Event('input', {{ bubbles: true }})); }})()")
        self.settle()

    def test_it_lists_only_hidden_rows_grouped_and_the_search_box_has_the_focus(self):
        self.mount()
        self.assertEqual(self.rows(), ["ABC-A-002", "ABC-A-003", "ABC-001", "ABC-D-001", "ABC-M-002", "ABC-U-001", "d1"])
        self.assertEqual(self.val("Array.from(document.querySelectorAll('.pk-group h3')).map(h => h.textContent)"),
                         ["Actions", "Risks and issues", "Decisions", "Milestones", "Use cases", "Documents"])
        self.assertTrue(wait(lambda: self.js("document.activeElement === document.querySelector('.pk-q input')")), "the search box has the focus")
        self.assertEqual(self.js("document.querySelector('.pk-foot .pri').disabled"), True, "nothing is chosen, so there is nothing to add")

    def test_search_narrows_the_list_and_nothing_matching_says_so(self):
        self.mount()
        self.type_in_search("SUPPLIER")
        self.assertEqual(self.rows(), ["ABC-001"])
        self.assertEqual(self.val("document.querySelectorAll('.pk-group').length"), 1, "a group with no row is not drawn")
        self.type_in_search("zzzz")
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.js("document.querySelector('.pk-none').textContent"), "Nothing matches your search. Clear it to see what can be added.")

    def test_several_at_once_then_one_add_with_the_ids_in_the_order_chosen(self):
        self.mount()
        for i in ("d1", "ABC-A-003", "ABC-001"):
            self.js(f"document.querySelector('.pick input[value=\"{i}\"]').click()")
        self.assertEqual(self.js("document.querySelector('.pk-count').textContent"), "3 selected")
        self.assertEqual(self.js("document.querySelector('.pk-foot .pri').textContent"), "Add 3")
        self.js("document.querySelector('.pk-foot .pri').click()")
        self.assertEqual(self.val("T.added"), [["d1", "ABC-A-003", "ABC-001"]])

    def test_select_all_shown_takes_what_the_search_shows_and_cancel_and_esc_close_it(self):
        self.mount()
        self.type_in_search("abc-a")
        self.js("Array.from(document.querySelectorAll('.pk-btn')).find(b => b.textContent === 'Select all shown').click()")
        self.settle()
        self.assertEqual(self.js("document.querySelector('.pk-count').textContent"), "2 selected")
        self.js("document.querySelector('.pk-foot .pri').click()")
        self.assertEqual(self.val("T.added"), [["ABC-A-002", "ABC-A-003"]])
        self.key("Escape", "Escape", 27)
        self.assertEqual(self.val("T.closed"), 1, "Esc asks the caller to close it")
        self.js("Array.from(document.querySelectorAll('.pk-btn')).find(b => b.textContent === 'Cancel').click()")
        self.assertEqual(self.val("T.closed"), 2)

    def test_when_everything_is_on_the_page_it_says_so_and_adds_nothing(self):
        self.mount(hidden=[], data={"actions": [{"id": "ABC-A-001", "description": "x", "client_visible": 1}]})
        self.assertIn("Everything is already on the page.", self.js("document.querySelector('.pk-head').textContent"))
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.js("document.querySelector('.pk-btn').disabled"), True)

    def test_a_row_already_on_the_page_is_not_in_the_panel(self):
        self.mount(on_page=["ABC-A-003", "d1"])
        self.assertEqual(self.rows(), ["ABC-A-002", "ABC-001", "ABC-D-001", "ABC-M-002", "ABC-U-001"])

    def test_hostile_text_in_a_title_is_shown_as_text_and_runs_nothing(self):
        data = {"actions": [{"id": "ABC-A-001", "description": HOSTILE, "client_visible": 0}],
                "decisions": [{"id": "ABC-D-001", "decision": '"><b id=boom>bold</b>', "client_visible": 0}],
                "documents": [{"id": "d1", "title": HOSTILE}]}
        self.mount(data=data, hidden=["d1"])
        self.settle()
        self.assertIs(self.js("window.pwned === undefined"), True)
        self.assertEqual(self.js("document.querySelectorAll('.picker script, .picker img, .picker b').length"), 0)
        self.assertIn(HOSTILE, self.js("document.querySelector('.pick').textContent"))
        self.assertIn("<b id=boom>", self.js("document.querySelector('.picker').textContent"))
        self.type_in_search("<script>")
        self.assertEqual(self.rows(), ["ABC-A-001", "d1"], "the search treats it as plain text too")


class MinimapLogic(InBrowser):
    def setUp(self):
        self.load()

    def test_only_visible_sections_are_listed_in_order_with_a_stable_anchor(self):
        got = self.val(f"T.minimap.entries({lit(SECTIONS)}, ['docs'])")
        self.assertEqual([e["id"] for e in got], ["current", "glance", "t1", "ms"], "risks has its own hidden flag, docs is in hiddenSections")
        self.assertEqual([e["anchor"] for e in got], ["sec-current", "sec-glance", "sec-t1", "sec-ms"])
        self.assertEqual([e["index"] for e in got], [0, 1, 2, 3])
        self.assertEqual(self.val(f"T.minimap.entries({lit(SECTIONS)}, new Set(['docs'])).length"), 4)
        self.assertEqual(self.val(f"T.minimap.entries({lit(SECTIONS)}).length"), 5, "hiddenSections is optional")
        self.assertEqual(self.val("T.minimap.entries([], [])"), [])
        self.assertEqual(self.val("T.minimap.entries(null, null)"), [])
        self.assertEqual(self.val(f"T.minimap.entries({lit(SECTIONS)}, {lit([s['id'] for s in SECTIONS])})"), [], "every section hidden")

    def test_an_anchor_is_the_same_each_time_safe_in_a_page_and_never_shared(self):
        self.assertEqual(self.val("T.minimap.anchorId('t1')"), self.val("T.minimap.anchorId('t1')"))
        self.assertEqual(self.val("T.minimap.anchorId('a b\"><x')"), "sec-a-b---x")
        got = self.val("T.minimap.entries([{id:'a b',title:'One'},{id:'a-b',title:'Two'},{id:'a?b',title:'Three'}])")
        self.assertEqual(len({e["anchor"] for e in got}), 3, "ids that give one anchor still get their own")
        self.assertEqual(got[0]["anchor"], "sec-a-b")
        self.assertEqual(self.val("T.minimap.entries([{id:'x',type:'raid',title:'  '}])[0].title"), "Risks and issues", "no title: the type's plain name")

    def test_the_current_section_while_scrolling_and_with_a_sticky_bar(self):
        offs = [{"id": "a", "top": 100}, {"id": "b", "top": 800}, {"id": "c", "top": 1500}, {"id": "d", "top": 2200}]
        at = lambda *a: self.val(f"T.minimap.activeEntry({lit(offs)}, {', '.join(lit(x) for x in a)})")
        self.assertEqual(at(0, 800), "a", "at the top the first is current, even above its top")
        self.assertEqual(at(0, 800, 0), "a")
        self.assertEqual(at(500, 800), "a", "line is 240 below the top of the view: 740 is above b's 800")
        self.assertEqual(at(600, 800), "b", "line at 840")
        self.assertEqual(at(1400, 800), "c")
        self.assertEqual(at(1900, 800), "c", "line at 2140")
        self.assertEqual(at(1970, 800), "d")
        # with a 48 px sticky bar the line is 48 + 30% of the 752 px under it, so a section changes a little later
        self.assertEqual(at(559, 800, 0), "a", "line at 559 + 240 = 799 has not reached b's top at 800")
        self.assertEqual(at(560, 800, 0), "b", "line at 800")
        self.assertEqual(at(526, 800, 48), "a", "line at 526 + 48 + 225.6 = 799.6")
        self.assertEqual(at(527, 800, 48), "b", "line at 800.6: the bar's height moves the change a little earlier")
        self.assertEqual(at(2100, 800, 48, 2900), "d", "line at 2373.6")
        self.assertEqual(at(1500, 800, 48, 2900), "c")
        self.assertEqual(self.val("T.minimap.activeEntry([], 0, 800)"), None)
        self.assertEqual(self.val("T.minimap.activeEntry(null, 0, 800)"), None)

    def test_the_last_section_is_current_at_the_very_bottom_even_if_its_top_never_gets_that_high(self):
        offs = [{"id": "a", "top": 0}, {"id": "b", "top": 700}, {"id": "c", "top": 1400}]
        self.assertEqual(self.val(f"T.minimap.activeEntry({lit(offs)}, 1000, 700, 0, 2100)"), "b", "view 1000..1700 of a 2100 page is not the end")
        self.assertEqual(self.val(f"T.minimap.activeEntry({lit(offs)}, 1000, 700, 0, 1700)"), "c", "scrolled to the end")
        self.assertEqual(self.val(f"T.minimap.activeEntry({lit(offs)}, 600, 700, 0, 1300)"), "c", "a short last section never reaches the line")
        self.assertEqual(self.val(f"T.minimap.activeEntry({lit(offs)}, 600, 700, 0, 2000)"), "b")
        self.assertEqual(self.val(f"T.minimap.activeEntry({lit(offs)}, 0, 700, 0, 600)"), "a", "a page shorter than the window stays on the first")

    def test_where_to_scroll_to_is_under_the_sticky_bar_and_never_negative(self):
        offs = [{"id": "a", "top": 20}, {"id": "b", "top": 800}, {"id": "c", "top": 1500.4}]
        self.assertEqual(self.val(f"T.minimap.scrollTargets({lit(offs)}, 48)"), {"a": 0, "b": 752, "c": 1452})
        self.assertEqual(self.val(f"T.minimap.scrollTargets({lit(offs)}, 48, 12)"), {"a": 0, "b": 740, "c": 1440})
        self.assertEqual(self.val(f"T.minimap.scrollTargets({lit(offs)})"), {"a": 20, "b": 800, "c": 1500})
        self.assertEqual(self.val("T.minimap.scrollTargets([], 48)"), {})

    def test_keys_arrow_home_end_move_and_escape_closes(self):
        n = lambda i, c, k: self.val(f"T.minimap.nextOnKey({i}, {c}, {lit(k)})")
        self.assertEqual([n(-1, 4, "ArrowDown"), n(0, 4, "ArrowDown"), n(3, 4, "ArrowDown"), n(1, 4, "ArrowRight")], [0, 1, 0, 2])
        self.assertEqual([n(-1, 4, "ArrowUp"), n(2, 4, "ArrowUp"), n(0, 4, "ArrowUp"), n(2, 4, "ArrowLeft")], [3, 1, 3, 1])
        self.assertEqual([n(2, 4, "Home"), n(0, 4, "End"), n(-1, 4, "End")], [0, 3, 3])
        self.assertEqual([n(2, 4, "a"), n(2, 4, "Tab"), n(-1, 4, "Enter")], [2, 2, -1], "other keys leave it alone")
        self.assertEqual([n(0, 0, "ArrowDown"), n(5, 3, "ArrowDown"), n(0, 1, "ArrowDown"), n(0, 1, "ArrowUp")], [-1, 0, 0, 0])
        k = lambda s, key: self.val(f"T.minimap.onKey({lit(s)}, {lit(key)})")
        self.assertEqual(k({"index": 2, "count": 4, "open": True}, "Escape"), {"index": -1, "open": False, "handled": True})
        self.assertEqual(k({"index": -1, "count": 4, "open": False}, "Escape")["handled"], False, "Esc on a shut list is not ours")
        self.assertEqual(k({"index": 0, "count": 4, "open": False}, "ArrowDown"), {"index": 1, "open": True, "handled": True})
        self.assertEqual(k({"index": 1, "count": 4, "open": True}, "Tab")["handled"], False)
        self.assertIs(self.val("T.minimap.closesOn('Escape')"), True)
        self.assertIs(self.val("T.minimap.closesOn('Enter')"), False)


class MinimapCounts(InBrowser):
    """countOf: the words beside each section, from the report's own data only (so a published file shows the same)."""
    def setUp(self):
        self.load()

    def count(self, typ, data, today="2026-11-05", client=False):
        return self.val(f"T.minimap.countOf({{type: {lit(typ)}}}, {lit(data)}, {lit(today)}, {lit(client)})")

    def test_flagged_use_cases_slipped_milestones_and_documents(self):
        self.assertEqual(self.count("usecases", DATA), {"text": "1 flagged", "hot": True})
        self.assertIsNone(self.count("usecases", {"use_cases": [{"status": "On track"}]}))
        done = {"use_cases": [{"status": "Done"}, {"status": "On track"}, {"status": "High risk"}, {"status": "Done", "archived": 1}]}
        self.assertEqual(self.count("usecases", done), {"text": "1 flagged", "hot": True}, "#412: Done is finished, not flagged")
        self.assertIsNone(self.count("usecases", {"use_cases": [{"status": "Done"}]}))
        ms = {"milestones": [{"id": "m1", "name": "A", "baseline_date": "2026-10-01", "status": "Planned"},
                             {"id": "m2", "name": "B", "baseline_date": "2027-01-01", "forecast_date": "2027-02-01", "status": "Planned"},
                             {"id": "m3", "name": "C", "baseline_date": "2027-03-01", "status": "Planned"},
                             {"id": "m4", "name": "D", "baseline_date": "2026-09-01", "status": "Done", "actual_date": "2026-09-02"}]}
        self.assertEqual(self.count("milestones", ms), {"text": "2 slipped", "hot": True})
        self.assertEqual(self.count("docs", DATA), {"text": "1", "hot": False})
        self.assertIsNone(self.count("docs", {}))

    def test_late_actions_red_risks_and_pending_decisions(self):
        d = {"actions": [{"status": "Open", "due_date": "2026-11-01"}, {"status": "Open", "due_date": "2026-12-01"}, {"status": "Closed", "due_date": "2026-10-01"}],
             "raid": [{"status": "Open", "priority": "High"}, {"status": "Open", "priority": "Low"}],
             "decisions": [{"status": "Pending"}, {"status": "Made"}]}
        self.assertEqual(self.count("actions", d), {"text": "1 late", "hot": True})
        self.assertEqual(self.count("actions", {"actions": d["actions"][1:2]}), {"text": "1", "hot": False})
        self.assertEqual(self.count("raid", d), {"text": "1 red", "hot": True})
        self.assertEqual(self.count("decisions", d), {"text": "1 pending", "hot": True})
        self.assertIsNone(self.count("glance", d))
        self.assertIsNone(self.count("text", d))


class MinimapInBrowser(InBrowser):
    def setUp(self):
        self.load()

    def mount(self, hidden=("docs",), sections=SECTIONS, counts=None):
        self.js(f"T.mountMinimap({lit(sections)}, {lit(list(hidden))}, false, {lit(counts) if counts else 'undefined'})")
        self.assertTrue(wait(lambda: self.js("!!document.querySelector('.toc')")))
        self.settle()

    def is_open(self):
        return self.js("document.querySelector('.toc').classList.contains('open')")

    def focused(self):
        return self.js("(function(){ const a = document.activeElement; return a.dataset && a.dataset.id ? 'link:' + a.dataset.id : a.className || a.tagName; })()")

    def test_it_lists_every_visible_section_and_none_hidden_one(self):
        self.mount()
        self.assertEqual(self.val("Array.from(document.querySelectorAll('.toc li button')).map(a => a.dataset.id)"), ["current", "glance", "t1", "ms"])
        self.assertEqual(self.js("document.querySelectorAll('.toc-lines i').length"), 4, "one line per entry")
        self.assertEqual(self.js("document.querySelector('.toc').textContent.includes('Risks and issues')"), False)
        self.assertEqual(self.js("document.querySelector('.toc').textContent.includes('Documents')"), False)

    def test_nothing_is_drawn_when_every_section_is_hidden(self):
        self.mount(hidden=[s["id"] for s in SECTIONS]) if False else None
        self.js(f"T.mountMinimap({lit(SECTIONS)}, {lit([s['id'] for s in SECTIONS])})")
        self.settle()
        self.assertEqual(self.js("document.querySelectorAll('.toc').length"), 0)

    def test_it_is_shut_until_pointed_at_or_focused_and_a_leave_closes_it(self):
        self.mount()
        self.assertIs(self.is_open(), False)
        self.assertEqual(self.js("getComputedStyle(document.querySelector('.toc-card')).visibility"), "hidden")
        self.js("document.querySelector('.toc').dispatchEvent(new MouseEvent('mouseenter'))")
        self.settle()
        self.assertIs(self.is_open(), True)
        self.assertEqual(self.js("getComputedStyle(document.querySelector('.toc-card')).visibility"), "visible")
        self.js("document.querySelector('.toc').dispatchEvent(new MouseEvent('mouseleave'))")
        self.settle()
        self.assertIs(self.is_open(), False)

    def test_tab_reaches_it_opens_it_and_walks_the_entries_then_esc_closes_and_returns_to_the_button(self):
        self.mount()
        self.js("document.body.focus()")
        self.tab()
        self.settle()
        self.assertEqual(self.focused(), "toc-lines", "the first Tab stop on the page is the minimap")
        self.assertIs(self.is_open(), True, "focus opens it")
        self.tab()
        self.assertEqual(self.focused(), "link:current")
        self.tab()
        self.assertEqual(self.focused(), "link:glance")
        self.key("ArrowDown", "ArrowDown", 40)
        self.settle()
        self.assertEqual(self.focused(), "link:t1")
        self.key("End", "End", 35)
        self.settle()
        self.assertEqual(self.focused(), "link:ms")
        self.key("ArrowDown", "ArrowDown", 40)
        self.settle()
        self.assertEqual(self.focused(), "link:current", "it wraps")
        self.key("Home", "Home", 36)
        self.settle()
        self.assertEqual(self.focused(), "link:current")
        self.key("Escape", "Escape", 27)
        self.settle()
        self.assertIs(self.is_open(), False, "Esc closes it")
        self.assertEqual(self.focused(), "toc-lines", "and the focus goes back to its button, still shut")
        self.key("ArrowDown", "ArrowDown", 40)
        self.settle()
        self.assertIs(self.is_open(), True, "an arrow on the button opens it again")
        self.assertEqual(self.focused(), "link:current")

    def test_tabbing_away_closes_it(self):
        self.mount()
        self.js("document.querySelector('.toc-lines').focus()")
        self.settle()
        self.assertIs(self.is_open(), True)
        for _ in range(4):
            self.tab()
        self.assertEqual(self.focused(), "link:ms", "the last entry")
        self.tab()
        self.assertEqual(self.focused(), "toc-top", "then Back to top")
        self.tab()
        self.settle()
        self.assertEqual(self.js("document.activeElement.id"), "after")
        self.assertIs(self.is_open(), False, "tabbing out of it closes it")
        self.settle()
        self.settle()                           # the list's fade-out is over, so it has no links to stop at
        self.tab(shift=True)
        self.settle()
        self.assertEqual(self.focused(), "toc-lines", "Shift+Tab back lands on its button (the shut list has no links to stop at)")
        self.assertIs(self.is_open(), True, "and focus opens it again")

    def test_a_click_scrolls_the_section_to_just_under_the_sticky_bar_and_closes_the_list(self):
        self.mount()
        self.js("document.querySelector('.toc-lines').focus()")
        self.settle()
        for sid, anchor in (("ms", "sec-ms"), ("glance", "sec-glance"), ("t1", "sec-t1")):
            self.js("document.querySelector('.toc-lines').focus()")
            self.settle()
            self.js(f"document.querySelector('.toc li button[data-id={sid}]').click()")
            self.settle()
            top = self.js(f"Math.round(document.getElementById('{anchor}').getBoundingClientRect().top)")
            self.assertEqual(top, 48, f"{sid}: its top sits just under the 48 px bar, so it is in view")
            self.assertIs(self.is_open(), False)
        self.assertEqual(self.val("T.jumped"), ["ms", "glance", "t1"])
        self.assertEqual(self.js("document.getElementById('bar').getBoundingClientRect().top"), 0, "the sticky bar is still at the top")

    def test_an_entry_is_a_button_and_a_click_never_touches_the_address_or_the_history(self):
        self.mount()
        self.assertEqual(self.js("document.querySelectorAll('.toc a, .toc [href]').length"), 0, "no #links for the router to read")
        self.assertEqual(self.js("document.querySelectorAll('.toc li button[type=button]').length"), 4)
        self.js("history.replaceState(null, '', '#mine')")
        before = self.val("[location.hash, history.length, location.href]")
        for sid in ("ms", "t1"):
            self.js("document.querySelector('.toc-lines').focus()")
            self.settle()
            self.js(f"document.querySelector('.toc li button[data-id={sid}]').click()")
            self.settle()
            self.assertEqual(self.val("[location.hash, history.length, location.href]"), before, f"{sid}: same hash, no new history entry")
        self.assertEqual(self.val("T.jumped"), ["ms", "t1"])

    def test_without_an_onjump_a_click_scrolls_to_the_anchor_and_still_leaves_the_address_alone(self):
        self.js(f"T.mountMinimap({lit(SECTIONS)}, {lit(['docs'])}, true)")
        self.assertTrue(wait(lambda: self.js("!!document.querySelector('.toc')")))
        self.settle()
        before = self.val("[location.hash, history.length]")
        self.js("document.querySelector('.toc-lines').focus()")
        self.settle()
        self.js("document.querySelector('.toc li button[data-id=ms]').click()")
        self.assertTrue(wait(lambda: self.js("window.scrollY > 1000"), 3), "the page scrolled to the section")
        self.assertEqual(self.val("[location.hash, history.length]"), before)

    def test_the_marks_use_a_grey_with_enough_contrast_on_the_page_background(self):
        self.mount()
        css = lambda sel, prop: self.js(f"getComputedStyle(document.querySelector('{sel}')).{prop}")
        self.assertEqual(css(".toc-lines i:not(.on)", "backgroundColor"), self.js("(function(){ const e = document.createElement('i'); e.style.background = 'var(--grey-700)'; document.body.appendChild(e); const c = getComputedStyle(e).backgroundColor; e.remove(); return c; })()"),
                         "an unmarked line is grey-700 (grey-300 failed 4.5:1)")

    def test_a_count_shows_beside_its_section_and_a_hot_one_marks_its_line(self):
        self.mount(counts={"ms": {"text": "2 slipped", "hot": True}, "glance": {"text": "3", "hot": False}})
        self.assertEqual(self.val("Array.from(document.querySelectorAll('.toc li button')).map(b => b.textContent)"),
                         ["Current state", "At a glance3", "Next steps", "Milestones2 slipped"])
        self.assertEqual(self.js("document.querySelectorAll('.toc li button em.hot').length"), 1)
        self.assertEqual(self.js("document.querySelector('.toc-lines i[data-tl=ms]').classList.contains('hot')"), True)
        self.assertEqual(self.js("document.querySelector('.toc-lines i[data-tl=glance]').classList.contains('hot')"), False)

    def test_no_counts_leaves_the_list_as_labels_only(self):
        self.mount()
        self.assertEqual(self.js("document.querySelectorAll('.toc li em').length"), 0)

    def test_the_count_text_has_enough_contrast_in_light_and_dark(self):
        for theme in ("light", "dark"):
            self.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
            self.mount(counts={"ms": {"text": "2 slipped", "hot": True}, "t1": {"text": "4", "hot": False}})
            ratio = self.val("""(function(){
              const rgb = (c) => c.match(/[0-9.]+/g).slice(0, 3).map(Number);
              const lum = (c) => { const [r, g, b] = rgb(c).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
              const bg = getComputedStyle(document.querySelector('.toc-card')).backgroundColor;
              return ['.toc li button em.hot', '.toc li button em:not(.hot)', '.toc-top'].map((q) => {
                const a = lum(getComputedStyle(document.querySelector(q)).color), b = lum(bg);
                return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); });
            })()""")
            for r in ratio:
                self.assertGreaterEqual(r, 4.5, f"{theme}: {ratio}")

    def test_back_to_top_scrolls_to_the_top_closes_the_list_and_is_reached_by_tab(self):
        self.mount()
        self.js("window.scrollTo(0, 900)")
        self.settle()
        self.assertGreater(self.js("window.scrollY"), 0)
        self.js("document.querySelector('.toc').dispatchEvent(new MouseEvent('mouseenter'))")
        self.assertTrue(wait(self.is_open))
        self.assertEqual(self.js("document.querySelector('.toc-top').textContent.trim().startsWith('Back to top')"), True)
        self.js("document.querySelector('.toc-top').click()")
        self.assertTrue(wait(lambda: self.js("window.scrollY") == 0))
        self.assertFalse(self.is_open())

    def test_the_current_entry_follows_the_scroll(self):
        self.mount()
        cur = lambda: self.js("(document.querySelector('.toc li button.on') || {}).dataset && document.querySelector('.toc li button.on').dataset.id")
        self.assertEqual(cur(), "current")
        for y, want in ((750, "glance"), (1500, "t1"), (1900, "ms")):
            self.js(f"window.scrollTo(0, {y})")
            self.assertTrue(wait(lambda: cur() == want, 3), f"at {y} the current section is {want}, not {cur()}")
        self.assertEqual(self.js("document.querySelectorAll('.toc-lines i.on').length"), 1)
        self.js("window.scrollTo(0, 99999)")
        self.assertTrue(wait(lambda: cur() == "ms", 3), "at the very bottom the last visible section is current")
        self.js("window.scrollTo(0, 0)")
        self.assertTrue(wait(lambda: cur() == "current", 3))

    def test_a_hostile_title_is_shown_as_text(self):
        sections = [{"id": "t1", "type": "text", "title": HOSTILE}, {"id": "t2", "type": "text", "title": "Fine"}]
        self.mount(hidden=[], sections=sections)
        self.assertIs(self.js("window.pwned === undefined"), True)
        self.assertEqual(self.js("document.querySelectorAll('.toc script, .toc img').length"), 0)
        self.assertIn(HOSTILE, self.js("document.querySelector('.toc-card').textContent"))
        self.assertEqual(self.js("document.querySelectorAll('#page script, #page img').length"), 0)


class Fit(InBrowser):
    """At 1400 and 900 px (the two widths #67 checks) nothing makes the page scroll sideways and both stay inside the window."""

    def many(self):
        rows = [{"id": f"ABC-A-{i:03d}", "description": "A long line of words that has to wrap inside the panel and never push it wider " * 3, "client_visible": 0,
                 "owner": "Alexandria Montgomery-Featherstonehaugh", "due_date": "2026-11-03"} for i in range(1, 40)]
        rows.append({"id": "ABC-A-900", "description": "Unbrokenwordunbrokenwordunbrokenwordunbrokenwordunbrokenwordunbrokenwordunbrokenword" * 2, "client_visible": 0})
        return {"actions": rows}

    def test_the_picker_fits_at_both_widths(self):
        for width in (1400, 900):
            self.load(width)
            self.js(f"T.mountPicker({lit(self.many())}, [], null)")
            self.assertTrue(wait(lambda: self.js("!!document.querySelector('.picker')")))
            self.settle()
            self.assertIs(self.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"no sideways scroll at {width}")
            box = self.val("(function(){ const r = document.querySelector('.picker').getBoundingClientRect(); return [r.left, r.right, r.bottom]; })()")
            self.assertTrue(box[0] >= 0 and box[1] <= width and box[2] <= 900, f"the panel is inside the window at {width}: {box}")
            self.assertIs(self.js("(function(){ const b = document.querySelector('.pk-body'); return b.scrollWidth <= b.clientWidth; })()"), True, "the list does not scroll sideways")
            self.assertIs(self.js("(function(){ const b = document.querySelector('.pk-body'); return b.scrollHeight > b.clientHeight; })()"), True, "a long list scrolls inside the panel")
            self.assertIs(self.js("(function(){ const r = document.querySelector('.pk-foot .pri').getBoundingClientRect(); return r.bottom <= window.innerHeight && r.width >= 24 && r.height >= 24; })()"), True,
                          "the Add button stays in view and is at least 24 px")

    def test_the_minimap_fits_at_both_widths_open_and_shut(self):
        for width in (1400, 900):
            self.load(width)
            self.js(f"T.mountMinimap({lit(SECTIONS)}, ['docs'])")
            self.assertTrue(wait(lambda: self.js("!!document.querySelector('.toc')")))
            self.settle()
            self.assertIs(self.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"shut, no sideways scroll at {width}")
            self.js("document.querySelector('.toc-lines').click()" if width <= 900 else "document.querySelector('.toc-lines').focus()")   # at 900 it is the "On this page" button
            self.settle()
            self.assertIs(self.js("document.querySelector('.toc').classList.contains('open')"), True)
            box = self.val("(function(){ const r = document.querySelector('.toc-card').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom]; })()")
            self.assertTrue(box[0] >= 0 and box[1] <= width and box[2] >= 0 and box[3] <= 900, f"the list is inside the window at {width}: {box}")
            self.assertIs(self.js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"open, no sideways scroll at {width}")
            self.assertIs(self.js("(function(){ const r = document.querySelector('.toc-lines').getBoundingClientRect(); return r.right <= window.innerWidth && r.left >= 0; })()"), True)
            self.assertIs(self.js("Array.from(document.querySelectorAll('.toc li button')).every(a => a.getBoundingClientRect().height >= 24)"), True, "each entry is at least 24 px tall")


if __name__ == "__main__":
    unittest.main()

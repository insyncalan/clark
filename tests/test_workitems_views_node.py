"""Item 1195, first slice: the Work items list template's saved views, priority cell, Show all / Show only N and optional columns
(templates/workItemsList.js), pure functions.

Run: python3 dev/run_tests.py test_workitems_views_node
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

ENTRY = ROOT / "tests" / "fixtures" / "workitemsviews_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}

ROWS = ("[{id:'A-1',kind:'action',title:'a',status:'Open',due:'2030-01-10'},"
        "{id:'A-2',kind:'action',title:'b',status:'Open',due:'2030-02-10'},"
        "{id:'A-3',kind:'action',title:'c',status:'Closed',due:'2030-01-01'},"
        "{id:'R-1',kind:'risk',title:'d',status:'Open',due:'2030-03-01'},"
        "{id:'I-1',kind:'issue',title:'e',status:'Open',due:'2030-03-02'},"
        "{id:'D-1',kind:'decision',title:'f',status:'Pending',due:'2030-03-03'}]")


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wv.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=WV", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconst W = WV;\nconst rows = " + ROWS + ";\n"
                          "console.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def ids(view, today="2030-01-15"):
    return run_node("W.matching(W.viewFilter(%s), rows, %s)" % (json.dumps(view), json.dumps(today)))


class SavedViews(unittest.TestCase):
    def test_the_views_and_their_names(self):
        got = run_node("W.VIEWS.map((v) => [v.id, v.name])")
        self.assertEqual(got, [["all", "All work items"], ["actions", "Actions"], ["risks-issues", "Risks and issues"],
                               ["decisions", "Decisions"], ["overdue", "Overdue"]])

    def test_all_is_the_default_filter(self):
        self.assertEqual(run_node("W.viewFilter('all')"), run_node("W.defaults()"))
        self.assertEqual(ids("all"), ["A-1", "A-2", "R-1", "I-1", "D-1"])

    def test_actions_lists_open_actions_only(self):
        self.assertEqual(ids("actions"), ["A-1", "A-2"])

    def test_risks_and_issues_lists_both_kinds(self):
        self.assertEqual(ids("risks-issues"), ["R-1", "I-1"])

    def test_decisions_lists_decisions_only(self):
        self.assertEqual(ids("decisions"), ["D-1"])

    def test_overdue_lists_open_items_past_their_date(self):
        self.assertEqual(ids("overdue"), ["A-1"])

    def test_an_unknown_view_is_the_default_filter_and_each_call_is_fresh(self):
        self.assertEqual(run_node("W.viewFilter('nope')"), run_node("W.defaults()"))
        self.assertEqual(run_node("(() => { W.viewFilter('actions').kinds.push('risk'); return W.viewFilter('actions').kinds; })()"), ["action"])

    def test_every_view_filter_survives_the_saved_body(self):
        for v in ("all", "actions", "risks-issues", "decisions", "overdue"):
            same = run_node("(() => { const f = W.viewFilter(%s); return JSON.stringify(W.filterOf({body: W.bodyOf(f)})) === JSON.stringify(f); })()" % json.dumps(v))
            self.assertTrue(same, v)


class DecisionsView(unittest.TestCase):
    def test_the_decisions_view_is_pending_and_made_in_the_last_14_days(self):      # row 1268, item 4
        self.assertEqual(run_node("W.viewFilter('decisions').mode"), "current")
        self.assertEqual(run_node("W.WORDS.mode.current"), "Open, and decisions made in the last 14 days")
        rows = ("[{id:'D-1',kind:'decision',status:'Pending',due:'2030-03-03'},{id:'D-2',kind:'decision',status:'Made',due:'2030-01-01'},"
                "{id:'D-3',kind:'decision',status:'Made',due:'2029-12-31'},{id:'D-4',kind:'decision',status:'Withdrawn',due:'2030-01-10'}]")
        self.assertEqual(run_node("W.matching(W.viewFilter('decisions'), %s, '2030-01-15').sort()" % rows), ["D-1", "D-2"])

    def test_a_decision_made_today_counts_and_a_made_row_that_is_not_a_decision_does_not(self):      # row 1268, item 4: the survivors of the mutation pass
        rows = "[{id:'D-1',kind:'decision',status:'Made',due:'2030-01-15'},{id:'R-1',kind:'risk',status:'Made',due:'2030-01-15'}]"
        self.assertEqual(run_node("W.matching(W.viewFilter('decisions'), %s, '2030-01-15').sort()" % rows), ["D-1"])
        self.assertEqual(run_node("W.matching({...W.viewFilter('all'), mode: 'current', kinds: ['risk']}, %s, '2030-01-15').sort()" % rows), [])


class PriorityCell(unittest.TestCase):
    def cell(self, kind, priority):
        return run_node("W.priorityCell({kind: %s, priority: %s})" % (json.dumps(kind), json.dumps(priority)))

    def test_rated_rows_show_the_priority_word_and_colour(self):
        self.assertEqual(self.cell("risk", "Urgent"), {"text": "Urgent", "class": "r"})
        self.assertEqual(self.cell("action", "High"), {"text": "High", "class": "r"})
        self.assertEqual(self.cell("issue", "Medium"), {"text": "Medium", "class": "a"})
        self.assertEqual(self.cell("action", "Low"), {"text": "Low", "class": "g"})

    def test_an_unrated_row_says_not_rated(self):
        self.assertEqual(self.cell("action", None), {"text": "Not rated", "class": "n"})

    def test_a_decision_without_a_priority_has_an_empty_cell(self):
        self.assertEqual(self.cell("decision", None), {"text": "", "class": "n"})

    def test_a_decision_shows_the_priority_its_peek_sets(self):      # row 1268, item 8
        got = run_node("W.priorityCell({kind: 'decision', priority: null, peek_priority: 'High'})")
        self.assertEqual(got, {"text": "High", "class": "r"})
        self.assertEqual(run_node("W.priorityCell({kind: 'decision', priority: 'Low'})"), {"text": "Low", "class": "g"})
        both = run_node("W.priorityCell({kind: 'decision', priority: 'Low', peek_priority: 'High'})")      # the peek's priority wins over the rule row's
        self.assertEqual(both, {"text": "High", "class": "r"})


class ShowAll(unittest.TestCase):
    def win(self, total, max_, show_all):
        return run_node("W.windowOf(%d, %d, %s)" % (total, max_, "true" if show_all else "false"))

    def test_a_short_list_has_no_link(self):
        self.assertEqual(self.win(10, 10, False), {"count": 10, "link": ""})
        self.assertEqual(self.win(0, 10, False), {"count": 0, "link": ""})

    def test_a_longer_list_shows_max_and_offers_show_all_items(self):
        self.assertEqual(self.win(25, 10, False), {"count": 10, "link": "Show all items"})

    def test_once_open_all_show_and_the_link_reads_show_only_n(self):
        self.assertEqual(self.win(25, 10, True), {"count": 25, "link": "Show only 10"})

    def test_show_all_of_a_short_list_changes_nothing(self):
        self.assertEqual(self.win(5, 10, True), {"count": 5, "link": ""})

    def test_one_row_over_max_is_already_a_longer_list(self):
        """The boundary: max + 1 rows is the shortest list that offers the link; max rows (above) is the longest that does not."""
        self.assertEqual(self.win(11, 10, False), {"count": 10, "link": "Show all items"})
        self.assertEqual(self.win(11, 10, True), {"count": 11, "link": "Show only 10"})
        self.assertEqual(self.win(10, 10, True), {"count": 10, "link": ""})
        self.assertEqual(self.win(1, 1, False), {"count": 1, "link": ""})
        self.assertEqual(self.win(2, 1, False), {"count": 1, "link": "Show all items"})

    def test_matching_can_return_every_hit_not_just_max(self):
        got = run_node("(() => { const f = Object.assign(W.defaults(), {max: 2}); return [W.matching(f, rows, '2030-01-15'), W.matching(f, rows, '2030-01-15', undefined, true)]; })()")
        self.assertEqual(got[0], ["A-1", "A-2"])
        self.assertEqual(got[1], ["A-1", "A-2", "R-1", "I-1", "D-1"])


class OptionalColumns(unittest.TestCase):
    def test_the_design_offers_status_workstream_and_milestone_off_by_default(self):
        self.assertEqual(run_node("W.DESIGN_COLUMNS"), ["status", "owner", "due", "priority", "workstream", "milestone", "id"])
        self.assertEqual(run_node("W.DESIGN_DEFAULT_COLUMNS"), ["owner", "due", "priority", "id"])
        off = run_node("W.DESIGN_COLUMNS.filter((c) => !W.DESIGN_DEFAULT_COLUMNS.includes(c))")
        self.assertEqual(off, ["status", "workstream", "milestone"])

    def test_column_words(self):
        got = run_node("W.DESIGN_COLUMNS.map((c) => W.WORDS.columns[c])")
        self.assertEqual(got, ["Status", "Owner", "Due", "Priority", "Workstream", "Milestone", "ID"])

    def test_columns_for_keeps_the_design_order_and_drops_unknown(self):
        self.assertEqual(run_node("W.columnsFor(['id', 'milestone', 'bogus', 'owner'])"), ["owner", "milestone", "id"])

    def test_columns_for_one_chosen_column_is_that_column_not_the_default(self):
        """A single chosen column is a choice: the list shows it alone, and the default is only for nothing chosen."""
        self.assertEqual(run_node("W.columnsFor(['priority'])"), ["priority"])
        self.assertEqual(run_node("W.columnsFor(['bogus', 'id'])"), ["id"])

    def test_columns_for_nothing_chosen_is_the_default(self):
        self.assertEqual(run_node("W.columnsFor([])"), ["owner", "due", "priority", "id"])
        self.assertEqual(run_node("W.columnsFor(['bogus'])"), ["owner", "due", "priority", "id"])

    def test_the_existing_columns_are_unchanged(self):
        # Row 1199 (issue 1199, PR 1633): Priority and Milestone joined the six; Status, Workstream and Milestone start off in a new list. The lists are
        # compared whole and in order, so a column dropped, added or moved fails here and the change is made on purpose.
        self.assertEqual(run_node("W.COLUMNS"), ["type", "id", "owner", "due", "status", "priority", "workstream", "milestone"])
        self.assertEqual(run_node("W.DEFAULT_COLUMNS"), ["id", "owner", "due", "priority"])
        self.assertEqual(run_node("W.WORDS.columns.type"), "Type")


if __name__ == "__main__":
    unittest.main()

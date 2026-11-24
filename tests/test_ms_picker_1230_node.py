"""Row 1230, picker PR: the Add a milestone picker's rules (logic/msPicker.js), pure functions. No browser.

Run: python3 dev/run_tests.py test_ms_picker_1230_node
Bundled by the pinned esbuild and run in node (skipped when node is not on the machine). "Today" is 2026-10-28.
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

ENTRY = ROOT / "tests" / "fixtures" / "mspicker_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
TODAY = "2026-10-28"
DATA = """{milestones: [
 {id:'M-1', name:'Eye one', baseline_date:'2026-10-01', status:'Planned'},
 {id:'M-2', name:'Eye two', baseline_date:'2026-11-02', status:'Planned'},
 {id:'M-3', name:'Internal', baseline_date:'2027-03-01', status:'Planned', client_visible:0},
 {id:'M-4', name:'On the page', baseline_date:'2027-04-01', status:'Planned'},
 {id:'M-5', name:'Archived', baseline_date:'2027-04-01', status:'Planned', client_visible:0, archived:1},
 {id:'M-6', name:'Done eye', baseline_date:'2026-01-01', status:'Done', actual_date:'2026-01-02'},
 {id:'M-7', name:'No date eye'}]}"""
LEFT = "['M-1','M-2','M-6','M-7']"


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "mp.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=MP", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
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
        script.write_text(bundle() + ";\nconst W = MP, today = '" + TODAY + "';\nconst rows = W.offered(" + DATA + ", " + LEFT + ", today);\n"
                          "console.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def shown(flt):
    return run_node("W.shownRows(rows, %s, today).map((r) => r.id)" % json.dumps(flt))


class Offered(unittest.TestCase):
    def test_the_rows_say_where_they_are_with_one_of_two_words_and_archived_is_never_offered(self):
        got = run_node("rows.map((r) => [r.id, r.why])")
        self.assertEqual(got, [["M-6", "Taken off with the eye"], ["M-1", "Taken off with the eye"], ["M-2", "Taken off with the eye"],
                               ["M-3", "Not on the page"], ["M-7", "Taken off with the eye"]])
        self.assertEqual(sorted(set(w for _i, w in got)), ["Not on the page", "Taken off with the eye"], "two values only")

    def test_the_on_the_page_field_has_exactly_those_two_values_with_counts(self):
        self.assertEqual(run_node("W.options('page').map((o) => o[0])"), ["Not on the page", "Taken off with the eye"])
        self.assertEqual(run_node("W.counts(rows, {}, 'page', today)"), [["Not on the page", 1], ["Taken off with the eye", 4]])


class Filters(unittest.TestCase):
    def test_is_any_of_and_is_not_any_of(self):
        self.assertEqual(shown({"sel": {"page": ["Not on the page"]}}), ["M-3"])
        self.assertEqual(shown({"sel": {"page": ["Not on the page"]}, "not": {"page": True}}), ["M-6", "M-1", "M-2", "M-7"])
        self.assertEqual(shown({"sel": {}}), ["M-6", "M-1", "M-2", "M-3", "M-7"])

    def test_due_buckets_from_the_agreed_date_closed_ones_are_later(self):
        got = run_node("rows.map((r) => [r.id, W.dueBucket(r, today)])")
        self.assertEqual(dict(got), {"M-1": "overdue", "M-2": "soon", "M-3": "later", "M-6": "later", "M-7": "none"})

    def test_counts_apply_the_other_fields_filters_and_the_result_words(self):
        flt = {"sel": {"page": ["Taken off with the eye"]}}
        self.assertEqual(run_node("W.counts(rows, %s, 'client', today)" % json.dumps(flt)), [["yes", 4], ["no", 0]])
        self.assertEqual(run_node("W.filtersOn(%s)" % json.dumps(flt)), 1)
        self.assertEqual(run_node("W.resultWords(2, 5)"), "Result: 2 of 5 shown")

    def test_search_over_name_id_and_state(self):
        self.assertEqual(shown({"query": "eye two"}), ["M-2"])
        self.assertEqual(shown({"query": "m-3"}), ["M-3"])
        self.assertEqual(shown({"query": "achieved"}), ["M-6"])

    def test_footer_words(self):
        self.assertEqual(run_node("[W.selectedWords(0), W.selectedWords(3), W.addWords(0), W.addWords(2), W.toastWords(1), W.toastWords(2)]"),
                         ["None selected", "3 selected", "Add selected", "Add 2", "1 milestone added to the page.", "2 milestones added to the page."])


def row(**kw):
    base = {"id": "X", "name": "x", "word": "", "baseline": "2026-12-01", "state": "On track", "why": "Not on the page", "clientVisible": True}
    base.update(kw)
    return json.dumps(base)


class Survivors(unittest.TestCase):
    """Pins the edges the mutation sweep (mut-row1230-pr4-picker) found unguarded."""

    def test_due_edges_today_and_seven_and_eight_days(self):
        probe = "[%s].map((r) => W.dueBucket(r, today))" % ", ".join(
            row(baseline=d) for d in ("2026-10-27", "2026-10-28", "2026-11-04", "2026-11-05"))
        self.assertEqual(run_node(probe), ["overdue", "soon", "soon", "later"])

    def test_cancelled_is_closed_so_later_even_when_past_due(self):
        self.assertEqual(run_node("W.dueBucket(%s, today)" % row(baseline="2026-10-01", state="Cancelled")), "later")
        self.assertEqual(run_node("W.dueBucket(%s, today)" % row(baseline="2026-10-01", state="Achieved")), "later")
        self.assertEqual(run_node("W.dueBucket(%s, today)" % row(baseline="2026-10-01", state="Slipped")), "overdue")

    def test_a_date_that_is_not_a_date_is_no_date(self):
        self.assertEqual(run_node("W.dueBucket(%s, today)" % row(baseline="soonish")), "none")
        self.assertEqual(run_node("W.dueBucket(%s, today)" % row(baseline="")), "none")

    def test_counts_ignore_the_fields_own_selection_but_apply_the_others(self):
        rows = "[%s, %s, %s]" % (row(id="A", state="Achieved"), row(id="B", state="Slipped"),
                                 row(id="C", state="Slipped", clientVisible=False))
        got = run_node("W.counts(%s, {sel: {status: ['Achieved']}}, 'status', today).filter((c) => c[1])" % rows)
        self.assertEqual(got, [["Achieved", 1], ["Slipped", 2]])
        got = run_node("W.counts(%s, {sel: {status: ['Achieved'], client: ['yes']}}, 'status', today).filter((c) => c[1])" % rows)
        self.assertEqual(got, [["Achieved", 1], ["Slipped", 1]])

    def test_search_ignores_the_case_of_what_is_typed(self):
        self.assertEqual(shown({"query": "EYE TWO"}), ["M-2"])
        self.assertEqual(shown({"query": "  M-3 "}), ["M-3"])

    def test_the_status_options(self):
        self.assertEqual(run_node("W.options('status').map((o) => o[0])"),
                         ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast", "Cancelled"])

    def test_the_due_and_client_options_and_the_zero_toast(self):
        self.assertEqual(run_node("W.options('due')"), [["overdue", "Overdue"], ["soon", "Due in 7 days"], ["none", "No date"], ["later", "Later"]])
        self.assertEqual(run_node("W.options('client')"), [["yes", "Shown to the client"], ["no", "Internal only"]])
        self.assertEqual(run_node("W.toastWords(0)"), "0 milestones added to the page.")

    def test_no_data_offers_nothing(self):
        self.assertEqual(run_node("[W.offered(null, [], today), W.offered({}, null, today)]"), [[], []])


if __name__ == "__main__":
    unittest.main()

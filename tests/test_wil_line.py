"""Row 1113 (the Work items list's filter line): the pure reading of a typed line onto a filter (templates/workItemsLine.js).

Run: python3 dev/run_tests.py test_wil_line
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
Added by the mutation hunt on PR 1386: the browser test there types two lines; every word the reader knows and every refusal it
names is pinned here, so a changed mapping, a dropped dedupe or a lost reset is a failing test.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "wil_line_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
EMPTY = {"v": 1, "kinds": [], "mode": "open", "status": [], "due": [], "owner": [], "workstream": [], "use_case": [], "priority": [], "sort": "due",
         "max": 50, "columns": ["type", "id", "owner", "due", "status"], "caption": "",
         "milestone": [], "not": {k: [] for k in ("kinds", "status", "due", "owner", "workstream", "use_case", "priority", "milestone")}, "has": [], "no": [], "text": []}      # row 1113: the whole filter a section keeps
KNOWN = [{"id": "U-1", "names": ["Invoice matching", "UC1", "UC1 Invoice matching"]}, {"id": "U-2", "names": ["Month end"]}]


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wil.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=WL", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def read(line, base=None):
    return run(f"WL.readLine({json.dumps(line)}, {json.dumps(base or EMPTY)}, {json.dumps(KNOWN)})")


def chosen(line, base=None):
    got = read(line, base)
    assert "filter" in got, got
    f = got["filter"]
    return {k: f[k] for k in ("kinds", "status", "due", "priority", "owner", "workstream", "use_case", "mode") if f[k] != EMPTY[k]}


class Read(unittest.TestCase):
    def test_each_field_word_lands_on_its_own_choice(self):
        self.assertEqual(chosen("type:risk,issue"), {"kinds": ["risk", "issue"]})
        self.assertEqual(chosen("status:Open,closed"), {"status": ["Open", "Closed"]})
        self.assertEqual(chosen("priority:high"), {"priority": ["High"]})
        self.assertEqual(chosen("priority:none"), {"priority": ["(none)"]})
        self.assertEqual(chosen('owner:"Pat Demo"'), {"owner": ["Pat Demo"]})
        self.assertEqual(chosen("owner:none"), {"owner": ["(none)"]})
        self.assertEqual(chosen("workstream:Finance"), {"workstream": ["Finance"]})
        self.assertEqual(chosen("workstream:none"), {"workstream": ["(none)"]})
        self.assertEqual(chosen("usecase:none"), {"use_case": ["(none)"]})

    def test_a_kind_is_read_by_its_name_or_its_plural_word_and_a_due_word_by_its_spellings(self):
        self.assertEqual(chosen("type:Issues"), {"kinds": ["issue"]})
        self.assertEqual(chosen("type:dependencies"), {"kinds": ["dependency"]})
        self.assertEqual(chosen("type:ACTION"), {"kinds": ["action"]})
        for word, want in (("overdue", "overdue"), ("soon", "soon"), ("next7days", "soon"), ("in7days", "soon"), ("none", "none"), ("nodate", "none"),
                           ("later", "later"), ("Overdue", "overdue")):
            self.assertEqual(chosen("due:" + word), {"due": [want]}, word)

    def test_a_use_case_is_found_by_title_by_ref_by_both_or_by_its_id_in_any_case_of_the_name(self):
        for text in ('usecase:"Invoice matching"', 'usecase:"invoice MATCHING"', "usecase:UC1", 'usecase:"UC1 Invoice matching"', "usecase:U-1"):
            self.assertEqual(chosen(text), {"use_case": ["U-1"]}, text)
        self.assertEqual(chosen('usecase:"Month end",UC1'), {"use_case": ["U-2", "U-1"]})

    def test_the_mode_follows_is_words_and_defaults_to_open(self):
        self.assertEqual(chosen("is:open"), {})
        self.assertEqual(chosen("is:closed"), {"mode": "closed"})
        self.assertEqual(chosen("is:open,closed"), {"mode": "all"})
        self.assertEqual(chosen("is:open is:closed"), {"mode": "all"})
        self.assertEqual(chosen("status:Open"), {"status": ["Open"]})

    def test_a_word_said_twice_is_one_choice_and_the_order_is_the_order_typed(self):
        self.assertEqual(chosen("type:risk,risk type:issue,risk"), {"kinds": ["risk", "issue"]})

    def test_the_line_replaces_every_choice_so_a_word_taken_out_is_taken_off_and_sort_max_columns_and_caption_stay(self):
        base = {**EMPTY, "kinds": ["risk"], "status": ["Open"], "due": ["soon"], "priority": ["High"], "owner": ["A"], "workstream": ["B"], "use_case": ["U-1"],
                "mode": "closed", "sort": "id", "max": 7, "columns": ["id"], "caption": "Keep"}
        got = read("", base)["filter"]
        self.assertEqual([got[k] for k in ("kinds", "status", "due", "priority", "owner", "workstream", "use_case")], [[]] * 7)
        self.assertEqual((got["mode"], got["sort"], got["max"], got["columns"], got["caption"], got["v"]), ("open", "id", 7, ["id"], "Keep", 1))
        self.assertEqual(base["kinds"], ["risk"], "the filter it was given is not changed")
        self.assertEqual(read("type:action", base)["filter"]["status"], [])

    def test_what_the_list_cannot_use_is_named_back_and_nothing_is_returned_to_save(self):
        for line, words in (("colour:red", '"colour:red" is not a word the filter line knows'),
                            ("-is:open -is:closed", "is not a choice this list has"),
                            ("is:blocked", '"is:blocked" is not a word the filter line knows'),
                            ("is:archived", '"is:archived" is not a word the filter line knows'),
                            ("status:Bogus", '"Bogus" is not a value status can take here'),
                            ("type:risk,nothing", '"nothing" is not a value type can take here'),
                            ("priority:Huge", '"Huge" is not a value priority can take here'),
                            ("due:yesterday", '"yesterday" is not a value due can take here'),
                            ("usecase:Unknown", '"Unknown" is not a value usecase can take here'),
                            ("-is:open -is:closed", "is not a choice this list has")):
            got = read(line)
            self.assertNotIn("filter", got, line)
            self.assertIn(words, got.get("problem", ""), line)

    def test_a_refused_line_names_the_choices_the_line_does_know(self):
        self.assertIn("Try type:, status:, owner:, workstream:, usecase:, priority:, due: or is:.", read("colour:red")["problem"])
        self.assertIn("Use type:, status:, owner:, workstream:, usecase:, priority:, due: or is:open.", read("-is:open -is:closed")["problem"])


class Show(unittest.TestCase):
    FILTER = {**EMPTY, "kinds": ["risk", "issue"], "status": ["Open"], "due": ["soon"], "priority": ["(none)"], "owner": ["Pat Demo", "(none)"],
              "workstream": ["Finance Ops"], "use_case": ["U-1", "(none)"]}

    def test_the_line_reads_back_in_a_fixed_order_with_quotes_where_a_value_needs_them(self):
        got = run(f"WL.lineOf({json.dumps(self.FILTER)}, (f, v) => 'Invoice matching')")
        self.assertEqual(got, 'type:risk,issue status:Open due:soon priority:none owner:"Pat Demo",none workstream:"Finance Ops" usecase:"Invoice matching",none')

    def test_a_name_with_a_comma_is_quoted_so_it_reads_back_as_one_value(self):
        f = {**EMPTY, "owner": ["Demo,Pat", "Lee Demo"]}
        line = run(f"WL.lineOf({json.dumps(f)})")
        self.assertEqual(line, 'owner:"Demo,Pat","Lee Demo"')
        self.assertEqual(read(line)["filter"]["owner"], ["Demo,Pat", "Lee Demo"])

    def test_the_mode_closes_or_widens_the_line(self):
        self.assertEqual(run(f"WL.lineOf({json.dumps({**EMPTY, 'mode': 'closed'})})"), "is:closed")
        self.assertEqual(run(f"WL.lineOf({json.dumps({**EMPTY, 'mode': 'all', 'kinds': ['risk']})})"), "type:risk is:open,closed")
        self.assertEqual(run(f"WL.lineOf({json.dumps(EMPTY)})"), "")

    def test_a_line_read_again_gives_the_same_filter(self):
        line = run(f"WL.lineOf({json.dumps({**self.FILTER, 'mode': 'all'})}, (f, v) => 'Invoice matching')")
        got = read(line)["filter"]
        want = {**self.FILTER, "mode": "all", "use_case": ["U-1", "(none)"]}
        self.assertEqual(got, want)

    def test_the_chips_say_each_choice_in_the_words_the_page_uses(self):
        got = run(f"WL.chipsOf({json.dumps(self.FILTER)}, (f, v) => 'Invoice matching')")
        self.assertEqual([(c["field"], c["value"], c["label"]) for c in got], [
            ("kinds", "risk", "Type: Risks"), ("kinds", "issue", "Type: Issues"), ("status", "Open", "Status: Open"), ("due", "soon", "Due: Due in 7 days"),
            ("priority", "(none)", "Priority: No priority"), ("owner", "Pat Demo", "Owner: Pat Demo"), ("owner", "(none)", "Owner: No owner"),
            ("workstream", "Finance Ops", "Workstream: Finance Ops"), ("use_case", "U-1", "Use case: Invoice matching"), ("use_case", "(none)", "Use case: No use case")])
        self.assertEqual(run(f"WL.chipsOf({json.dumps(EMPTY)})"), [])


if __name__ == "__main__":
    unittest.main()

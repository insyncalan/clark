"""Row 1113: the Work items section's typed filter line (templates/workItemsLine.js), lineOf and readLine, pure functions.

Run: python3 dev/run_tests.py test_workitems_line_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
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

ENTRY = ROOT / "tests" / "fixtures" / "workitemsline_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "wl.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=WL", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
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
        script.write_text(bundle() + ";\nconst {lineOf, readLine, defaults} = WL;\n"
                          "const known = [{id:'u1', names:['Say \"hi\"','UC1','UC1 Say \"hi\"']}, {id:'u2', names:['Twin']}, {id:'u3', names:['Twin']}, {id:'u4', names:['Zażółć 日本']}, {id:'u5', names:['u3']}];\n"
                          "const nameOf = (f, v) => (known.find((k) => k.id === v) || {names:[v]}).names[0];\n"
                          "const trip = (f) => { const line = lineOf(f, nameOf); const r = readLine(line, f, known); return {line, r}; };\n"
                          "console.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def trip(patch):
    return run_node("(() => { const f = Object.assign(defaults(), %s); const t = trip(f); return {line: t.line, problem: t.r.problem || null, same: !t.r.problem && JSON.stringify(t.r.filter) === JSON.stringify(f), got: t.r.filter}; })()" % json.dumps(patch))


class LineRoundTrip(unittest.TestCase):
    def test_values_with_quotes_commas_colons_round_trip(self):
        for field in ("owner", "workstream", "milestone"):
            for v in ['Dev, "Ops"', 'a:b', 'He said "x"', 'two  words', 'plain']:
                r = trip({field: [v, "Pat Demo"]})
                self.assertIsNone(r["problem"], (field, v, r))
                self.assertTrue(r["same"], (field, v, r))

    def test_use_case_title_with_quote_round_trips(self):
        r = trip({"use_case": ["u1"]})
        self.assertIsNone(r["problem"], r)
        self.assertEqual(r["got"]["use_case"], ["u1"])

    def test_unicode_and_very_long_values(self):
        for v in ["Zażółć 日本 ✓", "x" * 5000, ("word " * 800).strip()]:
            r = trip({"owner": [v]})
            self.assertTrue(r["same"], (v[:20], r["problem"]))
        r = trip({"use_case": ["u4"]})
        self.assertTrue(r["same"], r)

    def test_text_words_with_quotes_round_trip(self):
        r = trip({"text": ['say "hi" now', "plain"]})
        self.assertTrue(r["same"], r)

    def test_not_values_round_trip(self):
        r = trip({"not": {**{}, "owner": ['Dev, "Ops"'], "use_case": ["u1"]}})
        self.assertTrue(r["same"], r)


class LineReadNames(unittest.TestCase):
    def test_same_title_is_refused_not_picked(self):
        r = run_node("readLine('usecase:Twin', defaults(), known)")
        self.assertIn("is not a value", r["problem"])

    def test_same_title_both_saved_reads_back(self):
        r = trip({"use_case": ["u2", "u3"]})
        self.assertTrue(r["same"], r)

    def test_id_picks_one_of_two_same_titles(self):
        r = run_node("readLine('usecase:u3', defaults(), known)")
        self.assertEqual(r["filter"]["use_case"], ["u3"])

    def test_gone_use_case_stays_and_other_words_still_edit(self):
        r = run_node("(() => { const f = Object.assign(defaults(), {use_case: ['gone1'], owner: ['Pat']}); const line = lineOf(f, nameOf);"
                     " return {line, a: readLine(line, f, known), b: readLine(line + ' status:Open', f, known)}; })()")
        self.assertEqual(r["line"], "owner:Pat usecase:gone1")
        self.assertEqual(r["a"]["filter"]["use_case"], ["gone1"])
        self.assertEqual(r["b"]["filter"]["use_case"], ["gone1"])
        self.assertEqual(r["b"]["filter"]["status"], ["Open"])

    def test_gone_id_not_in_the_saved_list_is_still_refused(self):
        r = run_node("readLine('usecase:gone2', defaults(), known)")
        self.assertIn("is not a value", r["problem"])


if __name__ == "__main__":
    unittest.main()

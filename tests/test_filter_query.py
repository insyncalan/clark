"""#662 step 2: the parser of the filter line's text (src/clark/page/src/logic/filterQueryParse.js), a pure function.

Run: python3 dev/run_tests.py test_filter_query
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
Nothing here draws anything, and no on-screen word is tested: an error carries a code and data, not a sentence.
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

ENTRY = ROOT / "tests" / "fixtures" / "filterquery_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fq.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=FQ", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
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
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def lit(x):
    return json.dumps(x)


class Parse(unittest.TestCase):
    def q(self, line, extra=None):
        return run_node(f"FQ.parseQuery({lit(line)}, FQ.schemaOf({lit(extra or [])}))")

    def kinds(self, line):
        return [(t["kind"], t.get("field") or t.get("text") or t.get("states") or t.get("fields")) for t in self.q(line)["tokens"]]

    def test_empty_string(self):
        for line in ("", "   ", None):
            p = run_node(f"FQ.parseQuery({lit(line)})")
            self.assertEqual((p["tokens"], p["errors"], p["terms"], p["text"]), ([], [], [], []))

    def test_free_text(self):
        p = self.q("Cut-over plan")
        self.assertEqual(p["text"], ["Cut-over", "plan"])
        self.assertEqual(p["errors"], [])
        self.assertEqual(self.q('"two words" x')["text"], ["two words", "x"])

    def test_one_value(self):
        t = self.q("status:Open")["terms"]
        self.assertEqual(len(t), 1)
        self.assertEqual((t[0]["kind"], t[0]["field"], t[0]["values"], t[0]["negate"]), ("field", "status", ["Open"], False))
        self.assertEqual((t[0]["start"], t[0]["end"]), (0, 11))

    def test_field_names_ignore_case(self):
        for line in ("STATUS:Open", "Status:Open", "status:Open"):
            self.assertEqual(self.q(line)["terms"][0]["field"], "status")

    def test_or_list(self):
        t = self.q("priority:Urgent,High")["terms"][0]
        self.assertEqual((t["field"], t["values"]), ("priority", ["Urgent", "High"]))

    def test_and_across_fields(self):
        t = self.q("priority:Urgent,High workstream:Data")["terms"]
        self.assertEqual([(x["field"], x["values"]) for x in t], [("priority", ["Urgent", "High"]), ("workstream", ["Data"])])

    def test_exclude(self):
        t = self.q("-status:Closed,Cancelled")["terms"][0]
        self.assertEqual((t["kind"], t["field"], t["values"], t["negate"]), ("field", "status", ["Closed", "Cancelled"], True))

    def test_has_and_no(self):
        no = self.q("no:owner")["terms"][0]
        has = self.q("has:owner,due")["terms"][0]
        self.assertEqual((no["kind"], no["fields"], no["present"]), ("presence", ["owner"], False))
        self.assertEqual((has["kind"], has["fields"], has["present"]), ("presence", ["owner", "due"], True))
        self.assertTrue(self.q("-no:owner")["terms"][0]["present"])
        self.assertFalse(self.q("-has:owner")["terms"][0]["present"])
        self.assertEqual(self.q("NO:Owner")["terms"][0]["fields"], ["owner"])

    def test_is_states(self):
        t = self.q("is:open -is:overdue")["terms"]
        self.assertEqual([(x["kind"], x["states"], x["negate"]) for x in t], [("state", ["open"], False), ("state", ["overdue"], True)])
        self.assertEqual(self.q("is:closed")["terms"][0]["states"], ["closed"])

    def test_quotes(self):
        t = self.q('owner:"Owner One",Two workstream:"Build"')["terms"]
        self.assertEqual(t[0]["values"], ["Owner One", "Two"])
        self.assertEqual(t[1]["values"], ["Build"])
        # a quoted multi-word field name, a hyphenated one and the joined one are the same field
        for line in ('"Use case":x', '"use case":x', "use-case:x", "usecase:x", "Use_Case:x"):
            p = self.q(line)
            self.assertEqual((p["errors"], p["terms"][0]["field"]), ([], "usecase"), line)
        # a comma or a colon inside quotes stays in the value; white space inside quotes does not cut the token
        t = self.q('owner:"A, B" x:y')
        self.assertEqual(t["terms"][0]["values"], ["A, B"])
        self.assertEqual(t["errors"][0]["name"], "x")
        self.assertEqual(self.q('owner:"a:b"')["terms"][0]["values"], ["a:b"])
        self.assertEqual(self.q('owner:"never closed')["terms"][0]["values"], ["never closed"])

    def test_at_me_is_kept_for_the_evaluation(self):
        t = self.q("owner:@me -owner:@me,Owner")["terms"]
        self.assertEqual((t[0]["values"], t[0]["negate"]), (["@me"], False))
        self.assertEqual((t[1]["values"], t[1]["negate"]), (["@me", "Owner"], True))

    def test_unknown_field_is_an_error_and_not_guessed(self):
        p = self.q("stat:Open type:action")
        self.assertEqual(len(p["errors"]), 1)
        e = p["errors"][0]
        self.assertEqual((e["code"], e["name"], e["raw"], e["start"], e["end"]), ("unknown-field", "stat", "stat:Open", 0, 9))
        self.assertEqual(e["suggestions"][0], {"key": "status", "name": "Status"})
        self.assertEqual([t["kind"] for t in p["tokens"]], ["error", "field"])
        self.assertEqual([t["field"] for t in p["terms"]], ["type"])            # the other token still applies
        # the old shorthand is not a guess any more: it is unknown too
        for short in ("ws", "prio", "state", "ms", "uc", "own", "wor"):
            self.assertEqual(self.q(f"{short}:x")["errors"][0]["code"], "unknown-field", short)
        self.assertEqual(self.q("-state:Merged")["errors"][0]["code"], "unknown-field")
        e = self.q("no:stat")["errors"][0]
        self.assertEqual((e["code"], e["name"], e["qualifier"], e["suggestions"][0]["key"]), ("unknown-field", "stat", "no", "status"))
        self.assertEqual(self.q("zzzzzz:1")["errors"][0]["suggestions"], [])
        self.assertEqual(self.q("is:opn")["errors"][0]["code"], "unknown-state")
        self.assertEqual(self.q("is:opn")["errors"][0]["suggestions"][0]["key"], "open")

    def test_ambiguous_field_is_an_error_and_not_guessed(self):
        custom = [{"key": "status2", "name": "Status"}, {"key": "phase_a", "name": "Phase"}, {"key": "phase_b", "name": "phase"},
                  {"key": "has", "name": "Has"}]
        p = self.q("status:x phase:y Phase_A:z has:owner", custom)
        self.assertEqual([e["code"] for e in p["errors"]], ["ambiguous-field", "ambiguous-field", "ambiguous-field"])
        self.assertEqual(p["errors"][0]["candidates"], ["status", "status2"])
        self.assertEqual(sorted(p["errors"][1]["candidates"]), ["phase_a", "phase_b"])
        self.assertEqual(p["errors"][2]["candidates"], ["has", "has"])
        self.assertEqual(p["terms"], [t for t in p["terms"] if t["kind"] != "error"])
        # a field with one clear name beside them is still fine
        self.assertEqual(self.q("type:action", custom)["terms"][0]["field"], "type")

    def test_custom_fields_appear_by_themselves(self):
        extra = [{"key": "region", "name": "Sales region"}]
        p = self.q('"sales region":EMEA region:x', extra)
        self.assertEqual(p["errors"], [])
        self.assertEqual([t["field"] for t in p["terms"]], ["region", "region"])
        self.assertEqual(self.q("region:x")["errors"][0]["code"], "unknown-field")          # not in the schema without it

    def test_a_colon_with_no_value_filters_nothing(self):
        p = self.q("status: type:action")
        self.assertEqual(p["errors"][0]["code"], "missing-value")
        self.assertEqual(p["errors"][0]["field"], "status")
        self.assertEqual([t["field"] for t in p["terms"]], ["type"])
        self.assertEqual(self.q("no:")["errors"][0]["code"], "missing-value")

    def test_places_are_exact(self):
        line = 'a  status:Open "x y" -no:owner'
        for t in self.q(line)["tokens"]:
            self.assertEqual(line[t["start"]:t["end"]], t["raw"])

    def test_words_that_look_like_prototype_keys_are_just_unknown(self):
        for name in ("constructor", "__proto__", "toString", "hasOwnProperty"):
            self.assertEqual(self.q(f"{name}:x")["errors"][0]["code"], "unknown-field", name)

    def test_the_parser_does_not_look_at_rows(self):
        self.assertEqual(run_node("FQ.parseQuery.length"), 2)


if __name__ == "__main__":
    unittest.main()

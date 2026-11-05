"""#662 steps 2 and 3: the parser of the filter line's text (logic/filterQueryParse.js) and its evaluation over work items
(logic/filterQueryEval.js), both pure functions.

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


TODAY = "2026-10-29"
ME = "Owner One"
CTX = {"today": TODAY, "me": ME}


def row(id, kind, title, status, owner, priority=None, due=None, **more):
    r = {"id": id, "kind": kind, "title": title, "status": status, "owner": owner, "priority": priority, "workstream": "", "uc": "",
         "milestone": "", "client": False, "due_date": due}
    r.update(more)
    return r


# Fictional. Today is a Thursday.
ROWS = [
    row("T-A-001", "action", "Draft the cut-over plan", "Open", ME, "High", "2026-10-20", workstream="Build", uc="Use case 1.1", milestone="Go live"),
    row("T-A-002", "action", "Book the training room", "Open", "TBC", "Low", "2026-11-01"),
    row("T-A-003", "action", "Send the invitations", "Delayed", "Owner Two", "Urgent", "2026-11-05", workstream="Data", uc="Use case 2"),
    row("T-A-004", "action", "Order the laptops", "Open", ME, "Medium", "2026-12-01", workstream="Data", client=True),
    row("T-A-005", "action", "Archive the old files", "Closed", "Owner Two", "Medium", "2026-10-05"),
    row("T-R-001", "risk", "Supplier slips", "Open", ME, "High", "2026-11-03", workstream="Build", reviewed="2026-10-01", client_action=True),
    row("T-R-002", "issue", "Test system is down", "Open", "", "High"),
    row("T-R-003", "assumption", "Users have laptops", "Open", "Owner Two", "Low", workstream="Data"),
    row("T-D-001", "decision", "Use the new tool", "Pending", ME, None, None, needed_by="2026-11-20"),
    row("T-D-002", "decision", "Pick a supplier", "Pending", "Owner Two", None, None),
    row("T-D-003", "decision", "Use the shared calendar", "Made", "Owner Two", None, None, date="2026-10-01"),
    row("T-D-004", "decision", "Go with the old plan", "Withdrawn", "Owner Two", None, None),
]
ALL = [r["id"] for r in ROWS]
CLOSED = ["T-A-005", "T-D-003", "T-D-004"]


class Evaluate(unittest.TestCase):
    def ids(self, line, ctx=CTX, rows=ROWS, extra=None):
        # `of` cannot travel as JSON: the probe attaches the custom field's reader to the field it is given
        probe = (f"(() => {{ const x = {lit(extra or [])}.map((f) => ({{ ...f, of: (r) => r.region ? [r.region] : ['(none)'] }})); "
                 f"return FQ.evaluateQuery({lit(rows)}, {lit(line)}, {lit(ctx)}, x).map((r) => r.id); }})()")
        return run_node(probe)

    def test_empty_line_shows_everything(self):
        self.assertEqual(self.ids(""), ALL)
        self.assertEqual(self.ids("   "), ALL)

    def test_free_text_matches_the_title_in_any_case(self):
        self.assertEqual(self.ids("laptops"), ["T-A-004", "T-R-003"])
        self.assertEqual(self.ids("LAPTOP"), ["T-A-004", "T-R-003"])
        self.assertEqual(self.ids('"the old"'), ["T-A-005", "T-D-004"])
        self.assertEqual(self.ids("order laptops"), ["T-A-004"])           # two words: both
        self.assertEqual(self.ids("nothing like this"), [])

    def test_one_value_and_the_names_ignore_case(self):
        self.assertEqual(self.ids("priority:Urgent"), ["T-A-003"])
        self.assertEqual(self.ids("PRIORITY:urgent"), ["T-A-003"])
        self.assertEqual(self.ids("status:Delayed"), ["T-A-003"])
        self.assertEqual(self.ids("type:decision"), ["T-D-001", "T-D-002", "T-D-003", "T-D-004"])
        self.assertEqual(self.ids("client:shown"), ["T-A-004"])

    def test_comma_is_or_within_a_field(self):
        self.assertEqual(self.ids("type:risk,issue"), ["T-R-001", "T-R-002"])
        self.assertEqual(self.ids("priority:Urgent,Low"), ["T-A-002", "T-A-003", "T-R-003"])

    def test_space_is_and_across_fields(self):
        self.assertEqual(self.ids("priority:Urgent,High workstream:Data"), ["T-A-003"])
        self.assertEqual(self.ids("priority:Urgent,High workstream:Build"), ["T-A-001", "T-R-001"])
        self.assertEqual(self.ids("type:action laptops"), ["T-A-004"])
        self.assertEqual(self.ids('owner:"Owner One" type:action'), ["T-A-001", "T-A-004"])

    def test_exclude(self):
        self.assertEqual(self.ids("-status:Closed"), [i for i in ALL if i != "T-A-005"])
        self.assertEqual(self.ids("-status:Closed,Made,Withdrawn"), [i for i in ALL if i not in CLOSED])
        self.assertEqual(self.ids("-type:action,decision,assumption"), ["T-R-001", "T-R-002"])
        self.assertEqual(self.ids("-status:NoSuchStatus"), ALL)

    def test_has_and_no(self):
        self.assertEqual(self.ids("no:owner"), ["T-R-002"])
        self.assertEqual(self.ids("has:owner"), [i for i in ALL if i != "T-R-002"])
        self.assertEqual(self.ids("no:priority"), ["T-D-001", "T-D-002", "T-D-003", "T-D-004"])
        self.assertEqual(self.ids("has:priority,workstream no:priority"), [])
        self.assertEqual(self.ids("no:workstream,priority"), ["T-A-002", "T-A-005", "T-R-002", "T-D-001", "T-D-002", "T-D-003", "T-D-004"])     # a list is OR
        self.assertEqual(self.ids("-no:owner"), self.ids("has:owner"))
        self.assertEqual(self.ids("has:due"), [i for i in ALL if i not in ("T-R-002", "T-R-003", "T-D-002", "T-D-004")])
        self.assertEqual(self.ids("no:due"), ["T-R-002", "T-R-003", "T-D-002", "T-D-004"])      # a closed item with a date has a date
        self.assertEqual(self.ids("has:type"), ALL)                                                # a field every item has
        self.assertEqual(self.ids("no:type"), [])

    def test_is_states(self):
        self.assertEqual(self.ids("is:closed"), CLOSED)
        self.assertEqual(self.ids("is:open"), [i for i in ALL if i not in CLOSED])
        self.assertEqual(self.ids("-is:open"), CLOSED)
        self.assertEqual(self.ids("is:open no:owner"), ["T-R-002"])
        self.assertEqual(self.ids("is:overdue"), ["T-A-001"])
        self.assertEqual(self.ids("is:incomplete"), ["T-A-002", "T-R-002", "T-D-002"])
        self.assertEqual(self.ids("is:open,closed"), ALL)

    def test_at_me_is_the_signed_in_person(self):
        self.assertEqual(self.ids("owner:@me"), ["T-A-001", "T-A-004", "T-R-001", "T-D-001"])
        self.assertEqual(self.ids("owner:@me type:action"), ["T-A-001", "T-A-004"])
        self.assertEqual(self.ids("-owner:@me type:action"), ["T-A-002", "T-A-003", "T-A-005"])
        self.assertEqual(self.ids("owner:@me,\"Owner Two\" type:risk,assumption"), ["T-R-001", "T-R-003"])
        self.assertEqual(self.ids("owner:@ME"), self.ids("owner:@me"))
        self.assertEqual(self.ids("owner:me"), self.ids("owner:@me"))                  # the older spelling still reads
        # clark knows nobody: it matches no item and the line does not widen
        self.assertEqual(self.ids("owner:@me", {"today": TODAY, "me": ""}), [])
        self.assertEqual(self.ids("owner:@me", {"today": TODAY}), [])
        self.assertEqual(self.ids("-owner:@me", {"today": TODAY, "me": ""}), ALL)

    def test_an_unknown_or_ambiguous_field_filters_nothing(self):
        self.assertEqual(self.ids("stat:Open"), ALL)
        self.assertEqual(self.ids("-state:Merged"), ALL)                        # the reference tool returned nothing here
        self.assertEqual(self.ids("stat:Open type:risk,issue"), ["T-R-001", "T-R-002"])      # the other token still applies
        self.assertEqual(self.ids("no:stat is:closed"), CLOSED)
        self.assertEqual(self.ids("is:opn type:risk"), ["T-R-001"])
        self.assertEqual(self.ids("status:"), ALL)
        # two fields with one name: neither is guessed
        dup = [{"key": "status2", "name": "Status", "none": True}]
        self.assertEqual(self.ids("status:Closed", extra=dup), ALL)
        self.assertEqual(self.ids("status:Closed type:action", extra=dup), ["T-A-001", "T-A-002", "T-A-003", "T-A-004", "T-A-005"])

    def test_a_value_that_nothing_has_matches_nothing(self):
        self.assertEqual(self.ids("status:Merged"), [])
        self.assertEqual(self.ids("owner:Nobody"), [])

    def test_dates_and_the_older_value_words(self):
        self.assertEqual(self.ids("due:overdue"), ["T-A-001"])
        self.assertEqual(self.ids("due:next-7-days"), ["T-A-002", "T-A-003", "T-R-001"])
        self.assertEqual(self.ids("due:none"), ["T-R-002", "T-R-003", "T-D-002", "T-D-004"])
        self.assertEqual(self.ids("usecase:\"Use case 1.1\""), ["T-A-001"])
        self.assertEqual(self.ids("use-case:1"), ["T-A-001"])                                    # the group: 1 reaches 1.1
        self.assertEqual(self.ids("usecase:2"), ["T-A-003"])
        self.assertEqual(self.ids("milestone:\"go live\""), ["T-A-001"])

    def test_custom_fields_work_by_themselves(self):
        rows = [{**r, "region": "EMEA" if i % 3 == 0 else ("APAC" if i % 3 == 1 else "")} for i, r in enumerate(ROWS)]
        extra = [{"key": "region", "name": "Sales region", "none": True}]
        emea = [r["id"] for i, r in enumerate(ROWS) if i % 3 == 0]
        self.assertEqual(self.ids('"sales region":emea', rows=rows, extra=extra), emea)
        self.assertEqual(self.ids("sales-region:EMEA,APAC type:action", rows=rows, extra=extra), ["T-A-001", "T-A-002", "T-A-004", "T-A-005"])
        self.assertEqual(self.ids("no:region", rows=rows, extra=extra), [r["id"] for i, r in enumerate(ROWS) if i % 3 == 2])
        self.assertEqual(self.ids("has:region -region:APAC", rows=rows, extra=extra), emea)
        self.assertEqual(self.ids("region:EMEA", rows=rows), ALL)                 # no such field without it: ignored, not guessed

    def test_the_order_of_the_items_is_kept(self):
        rev = list(reversed(ROWS))
        got = run_node(f"FQ.evaluateQuery({lit(rev)}, 'type:action', {lit(CTX)}).map((r) => r.id)")
        self.assertEqual(got, ["T-A-005", "T-A-004", "T-A-003", "T-A-002", "T-A-001"])

    def test_the_parsed_line_can_be_used_again(self):
        got = run_node(f"(() => {{ const p = FQ.parseQuery('type:risk'); return [FQ.evaluateQuery({lit(ROWS)}, p, {lit(CTX)}).length, FQ.evaluateQuery({lit(ROWS)}, p, {lit(CTX)}).length]; }})()")
        self.assertEqual(got, [1, 1])

    def test_nothing_in_an_item_is_changed(self):
        self.assertEqual(run_node(f"(() => {{ const rows = {lit(ROWS)}; const before = JSON.stringify(rows); FQ.evaluateQuery(rows, 'is:open owner:@me', {lit(CTX)}); return before === JSON.stringify(rows); }})()"), True)

    def test_1000_items_evaluate_well_inside_100_ms(self):
        """A generous bound (the work is a few milliseconds on a laptop): the point is that it does not grow badly. The line is a long one."""
        probe = f"""(() => {{
          const kinds = ['action','risk','issue','decision'], st = ['Open','Pending','Closed','Delayed'], ws = ['Build','Data','Run'], pr = ['Urgent','High','Medium','Low'];
          const rows = Array.from({{ length: 1000 }}, (_, i) => ({{ id: 'X-' + i, kind: kinds[i % 4], title: 'Item number ' + i + ' about the supplier', status: st[i % 4],
            owner: i % 5 ? 'Owner ' + (i % 7) : '', priority: pr[i % 4], workstream: ws[i % 3], uc: 'Use case ' + (i % 4), milestone: 'M' + (i % 5),
            due_date: '2026-' + String(10 + (i % 3)).padStart(2, '0') + '-' + String(1 + (i % 28)).padStart(2, '0') }}));
          const line = 'supplier type:action,risk,issue -status:Closed priority:Urgent,High,Medium no:milestone,owner is:open owner:@me workstream:Build,Data due:overdue -usecase:2 bogus:x';
          const ctx = {{ today: '2026-10-29', me: 'Owner 3' }};
          FQ.evaluateQuery(rows, line, ctx);                          // a first run warms the engine
          const t0 = performance.now();
          const n = FQ.evaluateQuery(rows, line, ctx).length;
          const dt = performance.now() - t0;
          const t1 = performance.now();
          const m = FQ.evaluateQuery(rows, 'supplier -status:Closed owner:@me', ctx).length;
          return {{ ms: dt, ms2: performance.now() - t1, n, m }};
        }})()"""
        got = run_node(probe)
        self.assertLess(got["ms"], 100, got)
        self.assertLess(got["ms2"], 100, got)
        self.assertGreater(got["m"], 0, got)


if __name__ == "__main__":
    unittest.main()

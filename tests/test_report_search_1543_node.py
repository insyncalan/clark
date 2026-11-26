"""Row 1543 part 1 (AP9, AP12): the search logic of a published report (logic/reportSearch.js) with no browser.

Run: python3 dev/run_tests.py test_report_search_1543_node
Quick tier: bundled by the pinned esbuild and run in node (skipped when node is not on the machine). All rows are fictional.
The rule: the search reads only the data the file holds: work items by ID, title, owner and client message; milestones; use cases; the text of every
section. Every word typed must be found (any case); no words give no results; a title match comes before a text match; at most 50 results.
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

ENTRY = ROOT / "tests" / "fixtures" / "reportsearch_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
SHIM = "globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {};\n"

DATA = {
    "actions": [{"id": "A-1", "description": "Chase the supplier file", "owner": "Pat Demo", "client_message": "<p>We are <b>waiting</b> on the bank</p>", "latest_update": "ZQ-team-update"}],
    "raid": [{"id": "R-1", "type": "Risk", "description": "Key person leaves", "owner": "Sam Demo", "client_message": "ZQraidmsg"}],
    "decisions": [{"id": "D-1", "decision": "Use the shared drive", "made_by": "Lee Demo", "client_message": "ZQdecmsg"}],
    "milestones": [{"id": "M-1", "name": "Pilot live", "description": "<p>First suppliers</p>", "owner": "Kim Demo", "client_message": "ZQmsmsg", "latest_update": "ZQ-ms-update"}],
    "use_cases": [{"id": "U-1", "ref": "1.2", "title": "Payment runs", "headline": "One file still fails", "standing": "<p>Two of three load</p>", "owner": "Ann Demo"}],
    "report_sections": [
        {"id": "S-1", "type": "text", "title": "This week", "body": "<p>Cut-over rehearsal done</p>", "beside": 0},
        {"id": "S-2", "type": "table", "title": "Costs", "rows": [["Item", "Spend"], ["Licences", "12 000"]], "colour": ["teal", "ZQlistcolour"], "image": "ZQimage", "pic": "data:image/png;base64,QUJD", "url": "https://zq-address.invalid",
         "color": "ZQcolor", "style": "ZQstyle", "layout": "ZQlayout", "href": "ZQhref", "src": "ZQsrc", "icon": "ZQicon", "sort_order": "ZQsort", "beside": "ZQbeside",
         "groups": [{"id": "ZQ-nested-id", "note": {"words": "Nested words here"}}]},
        {"id": "S-3", "type": "text", "title": "Two paragraphs", "body": "<p>alpha</p><p>beta</p>"},
    ],
}
PAGES = {"S-3": ("Dashboard", "dashboard"), "A-1": ("Work items", "work"), "R-1": ("Work items", "work"), "D-1": ("Work items", "work"), "M-1": ("Milestones", "milestones"),
         "U-1": ("Use cases", "usecases"), "S-1": ("Dashboard", "dashboard"), "S-2": ("Dashboard", "dashboard")}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rs.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=RS", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run(expr, data=DATA):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    probe = f"(() => {{ const idx = RS.buildIndex({json.dumps(data)}); return {expr}; }})()"
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(SHIM + bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def ids(q, data=DATA):
    return run(f"RS.searchReport(idx, {json.dumps(q)}).map((e) => e.id)", data)


class WhatIsIndexed(unittest.TestCase):
    def test_every_kind_is_found_by_id_title_owner_and_client_message(self):
        self.assertEqual(ids("A-1"), ["A-1"], "a work item by its ID")
        self.assertEqual(ids("supplier file"), ["A-1"], "by its title")
        self.assertEqual(ids("Pat"), ["A-1"], "by its owner")
        self.assertEqual(ids("waiting bank"), ["A-1"], "by its client message, with the markup left out")
        self.assertEqual(ids("Key person"), ["R-1"])
        self.assertEqual(ids("Sam"), ["R-1"])
        self.assertEqual(ids("shared drive"), ["D-1"])
        self.assertEqual(ids("Lee"), ["D-1"], "a decision's owner is who made it")
        self.assertEqual(ids("pilot"), ["M-1"])
        self.assertEqual(ids("First suppliers"), ["M-1"])
        self.assertEqual(ids("Kim"), ["M-1"])
        self.assertEqual((ids("ZQraidmsg"), ids("ZQdecmsg"), ids("ZQmsmsg")), (["R-1"], ["D-1"], ["M-1"]), "each kind's client message")
        self.assertEqual(ids("payment"), ["U-1"])
        self.assertEqual(ids("1.2"), ["U-1"], "a use case by its reference")
        self.assertEqual(ids("still fails"), ["U-1"])
        self.assertEqual(ids("two of three"), ["U-1"])
        self.assertEqual(ids("Ann"), ["U-1"])

    def test_the_text_of_every_section_is_found_but_never_its_structure(self):
        self.assertEqual(ids("rehearsal"), ["S-1"])
        self.assertEqual(ids("licences"), ["S-2"], "a table's cells, however deep")
        self.assertEqual(ids("12 000"), ["S-2"])
        self.assertEqual(ids("costs"), ["S-2"], "its title")
        self.assertEqual(ids("nested words"), ["S-2"], "an object inside a list inside a section")
        self.assertEqual(ids("alpha beta"), ["S-3"], "two paragraphs read as separate words")
        for structure in ("teal", "QUJD", "zq-address", "image", "ZQimage", "ZQlistcolour", "table", "ZQcolor", "ZQstyle", "ZQlayout", "ZQhref", "ZQsrc", "ZQicon", "ZQsort", "ZQbeside", "ZQ-nested-id"):
            self.assertEqual(ids(structure), [], f"{structure!r}: a colour, a picture or an address is not a word of the report")

    def test_what_the_file_does_not_hold_cannot_be_found(self):
        self.assertEqual(ids("ZQ-team-update"), [], "a latest update is not searched")
        self.assertEqual(ids("ZQ-ms-update"), [])
        self.assertEqual(run("idx.length"), 8)
        self.assertEqual(run("idx.length", {}), 0, "no data, nothing indexed")

    def test_kind_and_view_name_the_page(self):
        got = run("idx.map((e) => [e.id, e.kind, e.view])")
        self.assertEqual({r[0]: (r[1], r[2]) for r in got}, PAGES)


class HowItMatches(unittest.TestCase):
    def test_every_word_must_be_found_in_any_case(self):
        self.assertEqual(ids("PILOT LIVE"), ["M-1"])
        self.assertEqual(ids("pilot nothere"), [], "one word missing is no match")
        self.assertEqual(ids("  supplier   file "), ["A-1"], "spaces around and between words do not matter")

    def test_no_words_give_no_results(self):
        self.assertEqual(ids(""), [])
        self.assertEqual(ids("   "), [])
        self.assertEqual(run("RS.searchReport(idx, null).length"), 0)

    def test_a_title_match_comes_before_a_text_match(self):
        data = {"actions": [{"id": "A-1", "description": "Other thing", "owner": "Pat Demo", "client_message": "mentions budget here"},
                            {"id": "A-2", "description": "Budget review", "owner": "Sam Demo", "client_message": ""}]}
        self.assertEqual(ids("budget", data), ["A-2", "A-1"])

    def test_at_most_fifty_results(self):
        data = {"actions": [{"id": f"A-{i}", "description": "Same words", "owner": "Pat", "client_message": ""} for i in range(80)]}
        self.assertEqual(len(ids("same", data)), 50)
        self.assertEqual(ids("same", data)[0], "A-0", "the report's own order")

    def test_a_row_with_no_title_is_listed_by_its_id(self):
        data = {"actions": [{"id": "A-9", "description": "", "owner": "Pat", "client_message": ""}]}
        self.assertEqual(run("RS.searchReport(idx, 'pat')[0].title", data), "A-9")

    def test_the_title_is_plain_words_and_a_section_keeps_its_own(self):
        self.assertEqual(run("idx.find((e) => e.id === 'S-1').title"), "This week")
        data = {"actions": [{"id": "A-1", "description": "<p>Chase   the\nfile</p>", "owner": "Pat", "client_message": ""}]}
        self.assertEqual(run("idx[0].title", data), "Chase the file")
        self.assertEqual((ids("<b>"), ids("</p>"), ids("<p>")), ([], [], []), "markup is never a word")

    def test_a_word_in_the_title_and_another_only_in_the_text_is_not_a_title_match(self):
        data = {"actions": [{"id": "A-1", "description": "Budget thing", "owner": "Pat", "client_message": "a review"},
                            {"id": "A-2", "description": "Review of the budget", "owner": "Sam", "client_message": ""}]}
        self.assertEqual(ids("budget review", data), ["A-2", "A-1"])

    def test_a_row_with_no_id_is_not_listed(self):
        data = {"actions": [{"id": "", "description": "No id here", "owner": "Pat", "client_message": ""}]}
        self.assertEqual(run("idx.length", data), 0)

    def test_a_section_text_reads_nothing_from_a_data_address_or_a_number(self):
        self.assertEqual(run("RS.sectionText({id: 'x', type: 'text', title: 'Plan', body: 'data:text/plain,hello', n: 12})"), "Plan")


if __name__ == "__main__":
    unittest.main()

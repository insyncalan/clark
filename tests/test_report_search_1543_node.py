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
        {"id": "S-2", "type": "table", "title": "Costs", "content": {"cols": ["Item", "Spend"], "rows": [["Licences", "12 000"]], "caption": "Quarter one", "colour": ["teal", "ZQlistcolour"],
         "image": "ZQimage", "pic": "data:image/png;base64,QUJD", "url": "https://zq-address.invalid", "color": "ZQcolor", "style": "ZQstyle", "layout": "ZQlayout",
         "href": "ZQhref", "src": "ZQsrc", "icon": "ZQicon", "sort_order": "ZQsort", "beside": "ZQbeside", "groups": [{"id": "ZQ-nested-id", "note": {"words": "ZQ-nested-words"}}]},
         "colour": "ZQouter-colour", "extra": "ZQouter-extra"},
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
        self.assertEqual(ids("quarter one"), ["S-2"], "the table's caption")
        self.assertEqual(ids("alpha beta"), ["S-3"], "two paragraphs read as separate words")
        for structure in ("teal", "QUJD", "zq-address", "image", "ZQimage", "ZQlistcolour", "table", "ZQcolor", "ZQstyle", "ZQlayout", "ZQhref", "ZQsrc", "ZQicon", "ZQsort", "ZQbeside", "ZQ-nested-id", "ZQ-nested-words", "ZQouter-colour", "ZQouter-extra"):
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

    def test_a_section_of_a_type_not_on_the_list_is_found_by_its_title_only(self):
        self.assertEqual(run("RS.sectionText({id: 'x', type: 'newtype', title: 'Plan', body: 'ZQ-body', content: {caption: 'ZQ-cap'}})"), "Plan")
        self.assertEqual(run("RS.sectionText({id: 'x', title: 'Plan', body: 'ZQ-body'})"), "Plan", "no type, no whitelist")
        self.assertEqual(run("RS.sectionText({id: 'x', type: 'constructor', title: 'Plan', content: {caption: 'ZQ-cap'}})"), "Plan", "a name from Object is not a type")


PIC = "data:image/png;base64,QUJD"
# type -> (the published section, the words its view draws, the words in the section that it does not draw as text). Each section is shaped as section_kinds/<type>.py published() makes it.
CASES = {
    "text": ({"body": "<p>ZQd-text</p>", "ZQu-key": "ZQu-text", "colour": "ZQu-text-colour"}, ["ZQd-text"], ["ZQu-text", "ZQu-text-colour"]),
    "imagecap": ({"content": {"image": PIC, "caption": "ZQd-icap", "alt": "ZQu-icap-alt", "full": 1, "fit": "stretch", "fill": "ZQu-icap-fill"}}, ["ZQd-icap"], ["ZQu-icap-alt", "ZQu-icap-fill"]),
    "textimage": ({"content": {"words": ["ZQd-ti-words"], "html": "<p>ZQd-ti-html</p>", "side": "ZQu-ti-side", "image": PIC, "caption": "ZQd-ti-cap", "alt": "ZQu-ti-alt", "heading": "ZQd-ti-head", "half": "ZQu-ti-half",
                                 "shape": "ZQu-ti-shape", "share": "ZQu-ti-share"}}, ["ZQd-ti-words", "ZQd-ti-html", "ZQd-ti-cap", "ZQd-ti-head"], ["ZQu-ti-side", "ZQu-ti-alt", "ZQu-ti-half", "ZQu-ti-shape", "ZQu-ti-share"]),
    "gallery": ({"content": {"pictures": [{"image": PIC, "caption": "ZQd-gal-cap", "alt": "ZQu-gal-alt"}], "columns": 2, "shape": "ZQu-gal-shape"}}, ["ZQd-gal-cap"], ["ZQu-gal-alt", "ZQu-gal-shape"]),
    "headline": ({"content": {"words": "ZQd-hl-words", "label": "ZQd-hl-label", "href": "https://zqu-hl.invalid", "image": PIC, "alt": "ZQu-hl-alt"}}, ["ZQd-hl-words", "ZQd-hl-label"], ["ZQu-hl-alt", "zqu-hl"]),
    "figures4": ({"figures": [{"mode": "ZQu-f4-mode", "label": "ZQd-f4-label", "value": "ZQd-f4-value", "detail": "ZQd-f4-detail", "rag": "ZQu-f4-rag", "asof": "ZQu-f4-asof", "metric": "ZQu-f4-metric"}]},
                  ["ZQd-f4-label", "ZQd-f4-value", "ZQd-f4-detail"], ["ZQu-f4-mode", "ZQu-f4-rag", "ZQu-f4-asof", "ZQu-f4-metric"]),
    "figures3": ({"figures": [{"mode": "ZQu-f3-mode", "label": "ZQd-f3-label", "value": "ZQd-f3-value", "detail": "ZQd-f3-detail", "rag": "ZQu-f3-rag"}]}, ["ZQd-f3-label", "ZQd-f3-value", "ZQd-f3-detail"], ["ZQu-f3-mode", "ZQu-f3-rag"]),
    "table": ({"content": {"cols": ["ZQd-tb-col"], "rows": [["ZQd-tb-cell"]], "caption": "ZQd-tb-cap", "colour": "ZQu-tb-colour"}, "layout": "ZQu-tb-layout"}, ["ZQd-tb-col", "ZQd-tb-cell", "ZQd-tb-cap"], ["ZQu-tb-colour", "ZQu-tb-layout"]),
    "doclinks": ({"content": {"items": [{"kind": "file", "name": "ZQd-dl-file.pdf", "rel": "Report files/ZQd-dl-file.pdf", "bytes": 5, "label": "ZQd-dl-label"},
                                         {"kind": "link", "href": "https://zqd-dl-site.invalid/ZQu-dl-path", "label": ""}, {"kind": "ZQu-dl-kind", "href": "https://zqu-dl-other.invalid", "label": "ZQu-dl-kindlabel"}]}},
                 ["ZQd-dl-file.pdf", "ZQd-dl-label", "zqd-dl-site.invalid", "PDF", "Web link"], ["Report files", "ZQu-dl-path", "ZQu-dl-kind", "zqu-dl-other", "ZQu-dl-kindlabel"]),
    "linkcard": ({"content": {"href": "https://zqd-lc-site.invalid/ZQu-lc-path", "title": "ZQd-lc-title", "site": "ZQd-lc-sitename", "text": ["ZQd-lc-text"], "html": "<p>ZQd-lc-html</p>", "ZQu-lc-key": "ZQu-lc-val"}},
                 ["ZQd-lc-title", "ZQd-lc-sitename", "ZQd-lc-text", "ZQd-lc-html"], ["ZQu-lc-path", "ZQu-lc-val", "ZQu-lc-key"]),
    "onedoc": ({"content": {"file": {"name": "ZQd-od-file.pdf", "rel": "Report files/ZQd-od-file.pdf", "bytes": 1}, "label": "ZQd-od-label", "text": ["ZQd-od-text"], "html": "<p>ZQd-od-html</p>"}},
               ["ZQd-od-file.pdf", "ZQd-od-label", "ZQd-od-text", "ZQd-od-html"], ["Report files"]),
    "raid3": ({"cards": [{"id": "ZQu-r3-id", "text": "ZQd-r3-text", "show": ["ZQu-r3-show"]}], "across": "ZQu-r3-across"}, ["ZQd-r3-text"], ["ZQu-r3-id", "ZQu-r3-show", "ZQu-r3-across"]),
    "raid4": ({"cards": [{"id": "ZQu-r4-id", "text": "ZQd-r4-text"}]}, ["ZQd-r4-text"], ["ZQu-r4-id"]),
    "workitems": ({"items": ["ZQu-wi-id"], "columns": ["ZQu-wi-column"], "caption": "ZQd-wi-cap"}, ["ZQd-wi-cap"], ["ZQu-wi-id", "ZQu-wi-column"]),
    "callout": ({"content": {"tone": "warning", "title": "ZQd-co-title", "paras": ["ZQd-co-para"], "html": "<p>ZQd-co-html</p>", "category": "ZQd-co-cat", "colour": "ZQu-co-colour", "icon": "ZQu-co-icon", "heading": True}},
                ["ZQd-co-title", "ZQd-co-para", "ZQd-co-html", "ZQd-co-cat"], ["warning", "ZQu-co-colour", "ZQu-co-icon"]),
    "quote": ({"content": {"quotes": [{"quote": "ZQd-qu-quote", "by": "ZQd-qu-by", "role": "ZQd-qu-role"}], "align": "ZQu-qu-align", "perRow": "ZQu-qu-per", "heading": "ZQu-qu-heading", "quote": "ZQu-qu-flat", "by": "ZQu-qu-flatby"}},
              ["ZQd-qu-quote", "ZQd-qu-by", "ZQd-qu-role"], ["ZQu-qu-align", "ZQu-qu-per", "ZQu-qu-heading", "ZQu-qu-flat", "ZQu-qu-flatby"]),
    "contacts": ({"content": {"people": [{"name": "ZQd-ct-name", "role": "ZQd-ct-role", "email": "zqd-ct@example.invalid", "phone": "ZQd-ct-phone", "ZQu-ct-key": "ZQu-ct-val"}]}}, ["ZQd-ct-name", "ZQd-ct-role", "zqd-ct@example.invalid", "ZQd-ct-phone"], ["ZQu-ct-val"]),
    "checklist": ({"v": 1, "items": [{"text": "ZQd-ck-line", "done": 1}, {"item": "ZQu-ck-linked"}]}, ["ZQd-ck-line"], ["ZQu-ck-linked"]),
    "keydates": ({"v": 1, "items": [{"label": "ZQd-kd-label", "date": "2031-01-02"}, {"milestone": "ZQu-kd-linked"}, {"label": "ZQu-kd-baddate", "date": "not a day"}]}, ["ZQd-kd-label"], ["2031-01-02", "ZQu-kd-linked", "ZQu-kd-baddate"]),
    "reportheadline": ({"content": {"health": "at_risk", "headline": "ZQd-rh-head", "sentence": "ZQd-rh-sent", "pill": True}}, ["ZQd-rh-head", "ZQd-rh-sent", "at risk"], ["at_risk", "off track", "on track", "not set"]),
    "glancetemplate": ({"content": {"health": {"shown": True, "own_row": True}, "per_row": "ZQu-gt-per", "order": ["ZQu-gt-order"], "builtin": {"overdue": {"outline": "ZQu-gt-outline"}},
                                    "bespoke": [{"id": "ZQu-gt-id", "label": "ZQd-gt-label", "figure": "ZQd-gt-figure", "tag": "ZQd-gt-tag", "note": "ZQd-gt-note", "tone": "ZQu-gt-tone"}]}},
                       ["ZQd-gt-label", "ZQd-gt-figure", "ZQd-gt-tag", "ZQd-gt-note"], ["ZQu-gt-per", "ZQu-gt-order", "ZQu-gt-outline", "ZQu-gt-id", "ZQu-gt-tone"]),
    "tracker": ({"size": "ZQu-tr-size", "overall": {"note": "ZQd-tr-note", "health": "ZQu-tr-health"}, "columns": {"ZQu-tr-col": True},
                 "groups": [{"name": "ZQd-tr-group", "lines": [{"no": "ZQd-tr-no", "text": "ZQd-tr-line", "status": "ZQu-tr-status", "start": "ZQu-tr-start"}]}]},
                ["ZQd-tr-note", "ZQd-tr-group", "ZQd-tr-no", "ZQd-tr-line"], ["ZQu-tr-size", "ZQu-tr-health", "ZQu-tr-col", "ZQu-tr-status", "ZQu-tr-start"]),
}


def one(kind):
    content, drawn, undrawn = CASES[kind]
    return {"report_sections": [{"id": "S-1", "type": kind, "title": "Title", "beside": 0, **content}]}


class OnlyWhatTheViewDraws(unittest.TestCase):
    """The index is a whitelist of the fields each section type's view draws as text (reportSearch.js DRAWN). A picture's description is the img's alt, a file's folder,
    a tone, a colour, an icon, an alignment, an id and an ISO date are never drawn as text, so they are never found. One test per type (made below)."""

    def test_every_type_the_registry_draws_has_a_case_or_is_title_only(self):
        listed = set(run("Object.keys(RS.DRAWN)"))
        self.assertEqual(listed, set(CASES) - {"text"} | {"text"}, "the whitelist and these cases name the same types")

    def test_a_type_that_is_not_on_the_list_is_found_by_its_title_only(self):
        self.assertEqual(run("RS.sectionText({id: 'x', type: 'newtype', title: 'Plan', body: 'ZQ-body', content: {caption: 'ZQ-cap'}})"), "Plan")
        self.assertEqual(run("RS.sectionText({id: 'x', title: 'Plan', body: 'ZQ-body'})"), "Plan", "no type, no whitelist")
        self.assertEqual(run("RS.sectionText({id: 'x', type: 'constructor', title: 'Plan', content: {caption: 'ZQ-cap'}})"), "Plan", "a name from Object is not a type")

    def test_the_whitelist_reads_exact_keys_and_exact_types(self):
        data = {"report_sections": [
            {"id": "X-1", "type": "imagecap", "title": "One", "content": {"Caption": "ZQcase-key", " caption": "ZQspace-key", "caption ": "ZQspace-end", "caption": "ZQexact-key"}},
            {"id": "X-2", "type": "ImageCap", "title": "Two", "content": {"caption": "ZQcase-type"}},
            {"id": "X-3", "type": " imagecap", "title": "Three", "content": {"caption": "ZQspace-type"}},
            {"id": "X-4", "type": "imagecap ", "title": "Four", "content": {"caption": "ZQspace-type-end"}},
        ]}
        self.assertEqual(ids("ZQexact-key", data), ["X-1"])
        for word in ("ZQcase-key", "ZQspace-key", "ZQspace-end", "ZQcase-type", "ZQspace-type", "ZQspace-type-end"):
            self.assertEqual(ids(word, data), [], f"{word!r}: the whitelist matches names exactly")

    def test_a_whitelisted_name_deeper_or_higher_than_its_place_is_not_read(self):
        data = {"report_sections": [{"id": "X-1", "type": "imagecap", "title": "One", "content": {"image": {"caption": "ZQdeep-caption"}}, "caption": "ZQouter-caption"}]}
        self.assertEqual((ids("ZQdeep-caption", data), ids("ZQouter-caption", data)), ([], []))

    def test_an_added_page_section_is_found_and_its_undrawn_field_is_not(self):
        sec = {"id": "P1-S-1", "type": "imagecap", "title": "Plant photo", "content": {"image": PIC, "caption": "ZQd-page-caption", "alt": "ZQu-page-alt"}}
        data = {"added_pages": [{"id": "P1", "name": "Site page", "sections": [sec]}]}
        self.assertEqual(ids("ZQd-page-caption", data), ["P1-S-1"], "a section of a page the page draws (`added_pages`) is found")
        self.assertEqual(ids("plant photo", data), ["P1-S-1"])
        self.assertEqual(ids("ZQu-page-alt", data), [], "its alt text is not")
        self.assertEqual(run("RS.searchReport(idx, 'ZQd-page-caption')[0].view", data), "page:P1")
        self.assertEqual(run("RS.searchReport(idx, 'ZQd-page-caption')[0].kind", data), "Site page")

    def test_search_reads_added_pages_the_view_reads_and_gives_hits_for_their_words(self):
        """The search reads `added_pages`, the key the view reads (stores/report.js:19,20,94): the text section's title and body words are found, with the page's view and name."""
        sec = {"id": "P1-S-1", "type": "text", "title": "Added page head", "body": "<p>ZQ-page-words</p>"}
        data = {"added_pages": [{"id": "P1", "name": "Site page", "sections": [sec]}]}
        self.assertEqual((ids("ZQ-page-words", data), ids("Added page head", data)), (["P1-S-1"], ["P1-S-1"]))
        self.assertEqual(run("RS.searchReport(idx, 'ZQ-page-words')[0].view", data), "page:P1")
        self.assertEqual(run("RS.searchReport(idx, 'ZQ-page-words')[0].kind", data), "Site page")

    def test_a_quote_or_callout_without_its_heading_does_not_find_its_title_and_the_switch_is_no_word(self):
        for kind, content in (("quote", {"quotes": [{"quote": "Q", "by": "", "role": ""}]}), ("callout", {"tone": "info", "title": "T", "paras": ["P"], "category": "C", "colour": "plain", "icon": "none"})):
            for heading, found in ((False, []), (True, ["S-1"]), (None, ["S-1"])):
                c = dict(content) if heading is None else {**content, "heading": heading}
                data = {"report_sections": [{"id": "S-1", "type": kind, "title": "ZQ heading words", "content": c}]}
                self.assertEqual(ids("ZQ heading words", data), found, f"{kind}: heading switch {heading!r}")
            self.assertEqual(ids("false", {"report_sections": [{"id": "S-1", "type": kind, "title": "x", "content": {**content, "heading": False}}]}), [], "the switch's value is never a word")
            self.assertEqual(ids("true", {"report_sections": [{"id": "S-1", "type": kind, "title": "x", "content": {**content, "heading": True}}]}), [], "the switch's value is never a word")

    def test_another_type_always_draws_its_title(self):
        data = {"report_sections": [{"id": "S-1", "type": "text", "title": "ZQ always shown", "body": "<p>x</p>", "content": {"heading": False}}]}
        self.assertEqual(ids("ZQ always shown", data), ["S-1"])

    def test_a_key_dates_milestone_line_is_found_by_its_state_word_and_never_by_its_day(self):
        data = {"milestones": [{"id": "M-1", "name": "Pilot live", "state": "Slipped", "baseline_date": "2031-05-06", "forecast_date": "2031-06-07"}],
                "report_sections": [{"id": "S-1", "type": "keydates", "title": "Dates", "v": 1, "items": [{"milestone": "M-1"}, {"label": "Go live party", "date": "2031-09-10"}]}]}
        self.assertEqual(ids("expected later", data), ["S-1"], "keydates.js: the milestone's state word as the client reads it")
        self.assertEqual(ids("pilot live", data)[:2], ["M-1", "S-1"], "its label, drawn in the section too")
        self.assertEqual(ids("go live party", data), ["S-1"], "a typed day has its label and no state word")
        for day in ("2031-05-06", "2031-06-07", "2031-09-10", "slipped"):
            self.assertEqual(ids(day, data), [], f"{day!r} is not drawn as the file holds it")
        self.assertEqual(run("RS.searchReport(idx, 'expected later').length", data), 1)

    def test_a_file_in_doclinks_is_found_by_its_type_word_and_not_by_its_raw_kind_or_path(self):
        data = {"report_sections": [{"id": "S-1", "type": "doclinks", "title": "Papers", "content": {"items": [{"kind": "file", "name": "plan.pdf", "rel": "Report files/plan.pdf", "bytes": 5, "label": ""},
                                                                                                          {"kind": "link", "href": "https://zq-site.invalid/path", "label": ""}]}}]}
        self.assertEqual((ids("pdf", data), ids("web link", data), ids("zq-site.invalid", data)), (["S-1"], ["S-1"], ["S-1"]), "the Type word and the site")
        for undrawn in ("file", "kind", "report", "rel", "zq-site.invalid/path", "path"):
            self.assertEqual(ids(undrawn, data), [], f"{undrawn!r}: a folder, a path and the raw kind are never drawn")

    def test_a_health_word_is_found_only_while_the_pill_shows(self):
        on = {"report_sections": [{"id": "S-1", "type": "reportheadline", "title": "Head", "content": {"health": "off_track", "headline": "H", "sentence": "S", "pill": True}}]}
        off = {"report_sections": [{"id": "S-1", "type": "reportheadline", "title": "Head", "content": {"health": "off_track", "headline": "H", "sentence": "S", "pill": False}}]}
        self.assertEqual(ids("off track", on), ["S-1"])
        self.assertEqual(ids("off track", off), [], "the eye is off: the page draws no health word")
        self.assertEqual(ids("off_track", on), [])

    def test_an_older_callout_is_found_by_its_tone_word_and_a_newer_one_by_its_category(self):
        older = {"report_sections": [{"id": "S-1", "type": "callout", "title": "Note", "content": {"tone": "decision", "title": "T", "paras": []}}]}
        self.assertEqual(ids("decision needed", older), ["S-1"], "no category, colour or icon: the page draws the tone's word")
        newer = {"report_sections": [{"id": "S-1", "type": "callout", "title": "Note", "content": {"tone": "decision", "title": "T", "paras": [], "category": "Heads up", "colour": "amber", "icon": "question"}}]}
        self.assertEqual((ids("heads up", newer), ids("decision needed", newer), ids("amber", newer)), (["S-1"], [], []))


def _case_test(kind):
    def test(self):
        content, drawn, undrawn = CASES[kind]
        data = one(kind)
        for w in undrawn:
            self.assertEqual(ids(w, data), [], f"{kind}: {w!r} is in the file but not drawn as text, so search must not find it")
            self.assertEqual(ids(w.upper(), data), [], f"{kind}: {w!r} in capitals")
        for w in drawn:
            self.assertEqual(ids(w, data), ["S-1"], f"{kind}: {w!r} is drawn, so search finds it")
    return test


for _kind in CASES:
    setattr(OnlyWhatTheViewDraws, "test_type_" + _kind, _case_test(_kind))


if __name__ == "__main__":
    unittest.main()

"""Row 1292 (S12): a Draft from ask clark put into a report section: what the draft is read as, what "Add to the report" offers, and the one
change each choice makes (src/clark/page/src/edit/askDraft.js), and that the panel and sheet draw only that data.

Run: python3 dev/run_tests.py test_ask_draft_logic
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skips without node). Fictional text only.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

EDIT = SRC / "clark" / "page" / "src" / "edit"

SECTIONS = [
    {"id": "s1", "type": "text", "title": "Summary", "body": "<p>One two three.</p>"},
    {"id": "s2", "type": "glance", "title": "At a glance", "body": ""},
    {"id": "s3", "type": "text", "title": "Next week", "body": "<p>Solo</p>"},
    {"id": "s4", "type": "text", "title": "", "body": ""},
]


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "ad.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AD", str(EDIT / "askDraft.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def call(fn, *args):
    return run_node("AD." + fn + "(" + ",".join(json.dumps(a) for a in args) + ")")


class ReadDraft(unittest.TestCase):
    def test_a_draft_is_kept_with_its_title_and_section(self):
        d = call("readDraft", {"html": "<p>Hello</p>", "title": "This week's summary", "sec": "s1"})
        self.assertEqual(d, {"html": "<p>Hello</p>", "title": "This week's summary", "sec": "s1"})

    def test_nothing_to_open(self):
        for bad in (None, "x", {}, {"html": ""}, {"html": "   "}, {"html": "<p></p>"}, {"html": 5}):
            self.assertIsNone(call("readDraft", bad), bad)

    def test_model_markup_is_cleaned(self):
        d = call("readDraft", {"html": "<p onclick=\"x()\">Hi</p><script>alert(1)</script>"})
        self.assertNotIn("script", d["html"])
        self.assertNotIn("onclick", d["html"])
        self.assertIn("Hi", d["html"])

    def test_title_and_section_default_to_empty_and_the_title_is_cut(self):
        d = call("readDraft", {"html": "<p>A</p>", "title": "x" * 300, "sec": 7})
        self.assertEqual(len(d["title"]), 120)
        self.assertEqual(d["sec"], "")


    def test_text_the_cleaner_refuses_is_kept_as_plain_paragraphs(self):
        padded = "x & y\nz\n\n<q>www" + " " * 200001      # too long as written, so cleanHtml refuses it; the blank padding is gone in paragraphs
        d = call("readDraft", {"html": padded})
        self.assertEqual(d["html"], "<p>x &amp; y<br>z</p><p>&lt;q&gt;www</p>")

    def test_a_draft_too_long_for_a_field_is_no_draft_and_does_not_throw(self):
        self.assertIsNone(call("readDraft", {"html": "<p>" + "w" * 200001 + "</p>", "title": "T"}))
        self.assertIsNone(call("readDraft", {"html": "x\n\n" + "w" * 200001}))


class Words(unittest.TestCase):
    def test_count(self):
        self.assertEqual(call("wordsIn", "<p>One two three.</p>"), 3)
        self.assertEqual(call("wordsIn", "<p>a</p><p>b c</p>"), 3)
        self.assertEqual(call("wordsIn", "<p>a   b</p>"), 2)
        self.assertEqual(call("wordsIn", ""), 0)
        self.assertEqual(call("wordsIn", None), 0)


class Choices(unittest.TestCase):
    def test_each_text_section_offers_a_replace_and_a_glance_none(self):
        c = call("choices", SECTIONS, "")
        rep = [x for x in c if x["kind"] == "replace"]
        self.assertEqual([x["id"] for x in rep], ["s1", "s3", "s4"])
        self.assertEqual(rep[0]["label"], "Replace the text of Summary (3 words now)")
        self.assertEqual(rep[1]["label"], "Replace the text of Next week (1 word now)")
        self.assertEqual(rep[2]["label"], "Replace the text of this section (0 words now)")

    def test_classic_says_empty_for_a_section_with_no_text_and_cards_keeps_0_words(self):      # row 1347
        rep = [x for x in call("choices", SECTIONS, "", True) if x["kind"] == "replace"]
        self.assertEqual([x["label"] for x in rep], ["Replace the text of Summary (3 words now)", "Replace the text of Next week (1 word now)", "Replace the text of this section (empty)"])
        cards = [x["label"] for x in call("choices", SECTIONS, "", False) if x["kind"] == "replace"]      # Cards stays as on main
        self.assertEqual(cards[2], "Replace the text of this section (0 words now)")

    def test_the_end_is_always_offered_last(self):
        c = call("choices", SECTIONS, "")
        self.assertEqual(c[-1], {"kind": "add", "id": "", "after": None, "label": "Add as a new Text section at the end"})
        self.assertEqual([x["kind"] for x in c], ["replace", "replace", "replace", "add"])

    def test_a_draft_for_a_section_lists_it_first_and_adds_after_it(self):
        c = call("choices", SECTIONS, "s3")
        self.assertEqual([x["id"] for x in c if x["kind"] == "replace"], ["s3", "s1", "s4"])
        self.assertEqual(c[-2], {"kind": "add", "id": "", "after": "s3", "label": "Add as a new Text section after Next week"})
        self.assertEqual(c[-1]["after"], None)

    def test_a_section_that_is_not_text_is_never_the_place(self):
        c = call("choices", SECTIONS, "s2")
        self.assertEqual([x["after"] for x in c if x["kind"] == "add"], [None])

    def test_no_sections_still_offers_the_end(self):
        self.assertEqual([x["label"] for x in call("choices", [], "")], ["Add as a new Text section at the end"])
        self.assertEqual(len(call("choices", None, "")), 1)


class Request(unittest.TestCase):
    def test_replace_is_one_update_of_the_body(self):
        r = call("request", {"kind": "replace", "id": "s1"}, "<p>New words</p>", "", SECTIONS)
        self.assertEqual(r["req"], {"op": "update", "id": "s1", "changes": {"body": "<p>New words</p>"}, "place": "report"})
        self.assertEqual(r["done"], "Draft put in Summary.")

    def test_a_section_with_no_title_is_called_the_section_in_the_message(self):
        r = call("request", {"kind": "replace", "id": "s4"}, "<p>New words</p>", "", SECTIONS)
        self.assertEqual(r["done"], "Draft put in the section.")

    def test_add_is_one_new_text_section_with_its_body(self):
        r = call("request", {"kind": "add", "id": "", "after": "s1"}, "<p>New</p>", "This week's summary", SECTIONS)
        self.assertEqual(r["req"], {"op": "new", "values": {"type": "text", "body": "<p>New</p>", "title": "This week's summary"}, "after": "s1", "place": "report"})
        self.assertEqual(r["done"], "Draft added as a new section.")

    def test_add_at_the_end_with_no_title_leaves_the_default_title(self):
        r = call("request", {"kind": "add", "id": "", "after": None}, "<p>New</p>", "  ", SECTIONS)
        self.assertEqual(r["req"]["values"], {"type": "text", "body": "<p>New</p>"})
        self.assertIsNone(r["req"]["after"])

    def test_the_edited_text_is_cleaned_again(self):
        r = call("request", {"kind": "replace", "id": "s1"}, "<p>Hi</p><script>x()</script>", "", SECTIONS)
        self.assertNotIn("script", r["req"]["changes"]["body"])

    def test_nothing_is_made_for_an_empty_draft_a_missing_choice_or_a_gone_section(self):
        self.assertIsNone(call("request", {"kind": "replace", "id": "s1"}, "<p></p>", "", SECTIONS))
        self.assertIsNone(call("request", None, "<p>A</p>", "", SECTIONS))
        self.assertIsNone(call("request", {"kind": "replace", "id": "gone"}, "<p>A</p>", "", SECTIONS))
        self.assertIsNone(call("request", {"kind": "replace", "id": "s2"}, "<p>A</p>", "", SECTIONS))      # a glance is not a Text section


class Wiring(unittest.TestCase):
    """The panel and the sheet use the module and draw its data; closing the panel closes the draft and changes nothing."""

    def setUp(self):
        self.panel = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
        self.sheet = (EDIT / "AskDraft.jsx").read_text(encoding="utf-8") if (EDIT / "AskDraft.jsx").exists() else ""
        self.state = (EDIT / "askPanelState.js").read_text(encoding="utf-8")

    def test_the_panel_reads_the_answers_draft_and_offers_to_open_it(self):
        self.assertIn("readDraft(", self.panel)
        self.assertIn("Open the draft", (EDIT / "askWords.js").read_text(encoding="utf-8"))
        self.assertIn("<AskDraft", self.panel)

    def test_the_sheet_has_the_words_of_the_mock_up(self):
        for w in ("DRAFT_TITLE", "DRAFT_HINT", "DRAFT_ADD", "DRAFT_COPY", "DRAFT_CLOSE"):
            self.assertIn("W." + w, self.sheet)
        words = (EDIT / "askWords.js").read_text(encoding="utf-8")
        self.assertIn('"Edit it freely. Nothing is in the report yet."', words)
        self.assertIn('"Add to the report"', words)

    def test_the_sheet_is_editable_and_sends_one_change(self):
        self.assertIn('contentEditable', self.sheet)
        self.assertEqual(self.sheet.count("change("), 1)

    def test_closing_the_panel_closes_the_draft(self):
        self.assertIn("draft.value = null", self.state)


if __name__ == "__main__":
    unittest.main()

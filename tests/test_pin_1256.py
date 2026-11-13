"""Pins for PR 1256 (row 1078, the milestone peek): six behaviours a mutation run found no test for.
Run: python3 dev/run_tests.py test_pin_1256
Sources and built values only (no browser)."""
import copy
import json
import re
import unittest
from unittest import mock

from _paths import SRC
import _publish_fixture as fx

from clark import docx_build, excel_client, publish, section_bodies  # noqa: E402
from test_docx_build import parts  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
RICH = "<p>Keep <em>this</em> wording</p>"
PLAIN = "Keep this wording"


def read(*parts):
    return PAGE_SRC.joinpath(*parts).read_text(encoding="utf-8")


def planted():
    plant = fx.load()
    for m in plant["data"]["milestones"]:
        m["client_message"] = RICH
    return plant


class Publish(unittest.TestCase):
    def test_a_template_is_handed_the_milestone_client_wording_as_plain_words(self):          # P4 (publish.py, for_templates)
        seen = []
        real = section_bodies.Context

        def spy(data, as_at, *rest):          # row 1113: Context also takes the live names
            seen.append(copy.deepcopy(data))
            return real(data, as_at, *rest)
        with mock.patch.object(section_bodies, "Context", spy):
            pub = publish.select(fx.inputs(planted()))
        said = [m["client_message"] for m in seen[0]["milestones"] if m.get("client_message")]
        self.assertTrue(said)
        self.assertEqual(set(said), {PLAIN}, "a template gets words, not the file's HTML")
        self.assertTrue(any(m.get("client_message") == RICH for m in pub["data"]["milestones"]), "the file itself keeps the HTML")


class Outputs(unittest.TestCase):
    def test_the_client_sheet_words_cell_of_a_milestone_is_plain_words(self):          # P6 (excel_client.py _words)
        row = {"description": "<p>Own</p>", "client_message": RICH}
        self.assertEqual(excel_client.value_of("milestones", row, "_words"), PLAIN)
        self.assertEqual(excel_client.value_of("milestones", {"description": "Own", "client_message": ""}, "_words"), "Own")

    def test_the_word_report_shows_the_milestone_client_wording_as_plain_words(self):          # P7 (docx_build.py section_milestones)
        pub = publish.select(fx.inputs(planted()))
        xml = parts(docx_build.build(pub))["word/document.xml"].decode("utf-8")
        self.assertIn(PLAIN, xml)
        self.assertNotIn("&lt;em&gt;", xml)
        self.assertNotIn("&lt;p&gt;", xml)


class Page(unittest.TestCase):
    def test_a_done_milestone_with_no_percent_shows_100_in_the_header(self):          # J5 (Peek.jsx)
        src = read("components", "Peek.jsx")
        self.assertIn('m.status === "Done" && m.percent_complete == null ? 100 : m.percent_complete', src)

    def test_the_help_says_a_client_sees_the_peek_without_the_visible_to_client_row(self):          # J10 (helpContent.json)
        text = json.dumps(json.loads(read("help", "helpContent.json")), ensure_ascii=False)
        self.assertIn("A client sees the same peek, read only, without the Visible to client row.", text)

    def test_the_client_wording_of_a_milestone_is_an_ai_place(self):          # J13 (aiPlaces.js)
        src = read("logic", "aiPlaces.js")
        self.assertRegex(src, r'(?m)^\s*client_message:\s*"milestone\.client_wording"')

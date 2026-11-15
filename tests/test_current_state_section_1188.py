"""Item 1188: the published project block carries the Current state text section's body (that is where edits go now), so the file
and Ask read it. Fictional data only.

Run: python3 dev/run_tests.py test_current_state_section_1188
"""
import unittest

from _paths import ROOT  # noqa: F401
from clark import ask_data, publish
from test_sections_store import Base


def sec(body, hidden=0, title="Current state", type_="text"):
    return {"type": type_, "title": title, "body": body, "hidden": hidden}


class Body(unittest.TestCase):
    def test_the_first_visible_text_section_titled_current_state_gives_its_cleaned_body(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>Ok.</p><script>x()</script>")]), "<p>Ok.</p>")

    def test_title_case_and_spacing_do_not_matter(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>A.</p>", title="  CURRENT   state ")]), "<p>A.</p>")

    def test_a_hidden_section_first_and_a_visible_one_second_gives_the_visible_ones_text(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>Secret.</p>", 1), sec("<p>Shown.</p>")]), "<p>Shown.</p>")

    def test_only_hidden_sections_give_nothing(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>Secret.</p>", 1)]), "")

    def test_another_title_or_type_and_no_sections_give_nothing(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>x</p>", title="Summary"), sec("<p>y</p>", type_="current")]), "")
        self.assertEqual(publish.current_state_section_body(None), "")


class Reads(Base):
    def inputs(self):
        return publish.read_inputs(self.s, "ABC")

    def state(self, inputs=None):
        return publish.select(inputs or self.inputs())["data"]["project"]["current_state"]

    def test_the_published_project_block_carries_the_section_body(self):
        self.change(self.sections()[0]["id"], title="Current state", body="<p>Build is half done.</p>")
        self.assertEqual(self.state(), "<p>Build is half done.</p>")

    def test_a_hidden_section_gives_nothing(self):
        self.change(self.sections()[0]["id"], body="<p>Secret.</p>", hidden=1)
        self.assertEqual(self.state(), "")

    def test_an_old_report_with_a_current_section_still_reads_the_column(self):
        inputs = self.inputs()
        inputs["data"]["project"]["current_state"] = "<p>Old column.</p>"
        inputs["sections"] = [{"id": "ABC-S-001", "type": "current", "title": "Current state", "sort_order": 10}]
        self.assertEqual(self.state(inputs), "<p>Old column.</p>")

    def test_ask_sees_the_section_body(self):
        self.change(self.sections()[0]["id"], body="<p>Vendor contract signed.</p>")
        text = repr(ask_data.project_data(self.s, "ABC", "current state vendor", budget=40000).passages)
        self.assertIn("Vendor contract signed.", text)


if __name__ == "__main__":
    unittest.main()

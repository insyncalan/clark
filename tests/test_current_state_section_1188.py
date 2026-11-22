"""Item 1188: the published project block carries the Current state text section's body (that is where edits go now), so the file
and Ask read it. Fictional data only.

Run: python3 dev/run_tests.py test_current_state_section_1188
"""
import unittest

from _paths import ROOT  # noqa: F401
from clark import ask_data, default_sections, publish
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


class Instruction(unittest.TestCase):
    def test_the_prefill_line_stored_as_the_body_gives_nothing(self):
        self.assertEqual(publish.current_state_section_body([sec("<p>%s</p>" % default_sections.CURRENT_STATE_PREFILL)]), "")
        self.assertEqual(publish.current_state_section_body([sec("  <div>%s</div>\n" % default_sections.CURRENT_STATE_PREFILL.replace(" ", "  "))]), "")

    def test_every_hint_value_stored_as_the_body_gives_nothing(self):
        for hint in default_sections.SECTION_HINTS.values():
            self.assertEqual(publish.current_state_section_body([sec("<p>%s</p>" % hint)]), "", hint)

    def test_an_edited_body_that_merely_contains_the_line_is_kept(self):
        body = "<p>%s Also, the vendor is late.</p>" % default_sections.CURRENT_STATE_PREFILL
        self.assertEqual(publish.current_state_section_body([sec(body)]), body)


class Order(unittest.TestCase):
    def test_the_first_in_display_order_wins_not_the_first_in_input_order(self):
        later = dict(sec("<p>Later.</p>"), id="S-1", sort_order=20)
        earlier = dict(sec("<p>Earlier.</p>"), id="S-2", sort_order=10)
        self.assertEqual(publish.current_state_section_body([later, earlier]), "<p>Earlier.</p>")


class Reads(Base):
    def inputs(self):
        return publish.read_inputs(self.s, "ABC")

    def first_text(self):
        """The first text section of a new project: Header (row 1266 put the Headline and At a glance before it)."""
        return next(r["id"] for r in self.sections() if r["type"] == "text")

    def state(self, inputs=None):
        return publish.select(inputs or self.inputs())["data"]["project"]["current_state"]

    def test_the_published_project_block_carries_the_section_body(self):
        self.change(self.first_text(), title="Current state", body="<p>Build is half done.</p>")
        self.assertEqual(self.state(), "<p>Build is half done.</p>")

    def test_a_hidden_section_gives_nothing(self):
        self.change(self.first_text(), title="Current state", body="<p>Secret.</p>", hidden=1)
        self.assertEqual(self.state(), "")

    def test_an_old_report_with_a_current_section_still_reads_the_column(self):
        inputs = self.inputs()
        inputs["data"]["project"]["current_state"] = "<p>Old column.</p>"
        inputs["sections"] = [{"id": "ABC-S-001", "type": "current", "title": "Current state", "sort_order": 10}]
        self.assertEqual(self.state(inputs), "<p>Old column.</p>")

    def test_a_built_in_current_section_with_an_empty_column_and_a_current_state_text_section_gives_the_text_body(self):
        inputs = self.inputs()
        inputs["data"]["project"]["current_state"] = ""
        inputs["sections"] = [{"id": "ABC-S-001", "type": "current", "title": "Current state", "sort_order": 10, "hidden": 0},
                              {"id": "ABC-S-002", "type": "text", "title": "Current state", "body": "<p>Text body.</p>", "sort_order": 20, "hidden": 0}]
        self.assertEqual(self.state(inputs), "<p>Text body.</p>")

    def test_a_built_in_current_section_with_a_filled_column_keeps_the_column_over_the_text_section(self):
        inputs = self.inputs()
        inputs["data"]["project"]["current_state"] = "<p>Column.</p>"
        inputs["sections"] = [{"id": "ABC-S-001", "type": "current", "title": "Current state", "sort_order": 10, "hidden": 0},
                              {"id": "ABC-S-002", "type": "text", "title": "Current state", "body": "<p>Text body.</p>", "sort_order": 20, "hidden": 0}]
        self.assertEqual(self.state(inputs), "<p>Column.</p>")

    def test_ask_sees_the_section_body(self):
        self.change(self.first_text(), title="Current state", body="<p>Vendor contract signed.</p>")
        text = repr(ask_data.project_data(self.s, "ABC", "current state vendor", budget=40000).passages)
        self.assertIn("Vendor contract signed.", text)


if __name__ == "__main__":
    unittest.main()

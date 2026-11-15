"""Row 1213: ask says which kinds the report leaves out, so a missing kind is not read as "none exist".

Run: python3 dev/run_tests.py test_ask_left_out_kinds
The project is #39's publish plant; its milestones section is hidden in the inputs handed to project_data. What is asserted: a passage
names the left-out kind and tells the model not to say none exist; the service's note says the same to the person; nothing about a
hidden row (id, name, count) is in either; a project with every section shown gets neither.
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
import test_ask_route as route
from clark import ask_data, ask_service, publish


def inputs_with(hidden_types):
    given = plant.inputs()
    given["sections"] = [{**s, "hidden": 1 if s.get("type") in hidden_types else 0} for s in publish.DEFAULT_SECTIONS]
    return given


class LeftOutKinds(unittest.TestCase):
    def run_with(self, hidden):
        with mock.patch.object(publish, "read_inputs", return_value=inputs_with(hidden)):
            return ask_data.project_data(object(), "PUB", "what milestones are there?")

    def test_a_hidden_milestones_section_is_named_in_a_passage(self):
        got = self.run_with({"milestones"})
        self.assertEqual(got.kinds_left_out, ("milestones",))
        line = [p for p in got.passages if p.label == "report: left out"]
        self.assertEqual(len(line), 1)
        self.assertIn("milestones", line[0].text)
        self.assertIn("Do not say there are none", line[0].text)

    def test_the_passage_carries_no_row_of_the_hidden_kind(self):
        got = self.run_with({"milestones"})
        text = [p.text for p in got.passages if p.label == "report: left out"][0]
        self.assertNotRegex(text, r"PUB-M-\d|\d+ milestone")

    def test_every_section_shown_gives_no_passage_and_no_note(self):
        got = self.run_with(set())
        self.assertEqual(got.kinds_left_out, ())
        self.assertFalse([p for p in got.passages if p.label == "report: left out"])
        self.assertEqual(ask_service.kinds_note(got.kinds_left_out), "")

    def test_the_note_to_the_person_names_the_kind_in_plain_words(self):
        note = ask_service.kinds_note(self.run_with({"milestones", "raid"}).kinds_left_out)
        self.assertIn("milestones, risks and issues", note)
        self.assertIn("may be missing something", note)

    def test_every_section_row_deleted_counts_the_built_ins_as_left_out(self):
        given = plant.inputs()
        given["sections"] = []
        given["sections_deleted"] = 1
        with mock.patch.object(publish, "read_inputs", return_value=given):
            got = ask_data.project_data(object(), "PUB", "what milestones are there?")
        self.assertIn("milestones", got.kinds_left_out)
        self.assertEqual(len([p for p in got.passages if p.label == "report: left out"]), 1)

    def test_no_section_rows_and_none_deleted_leaves_nothing_out(self):
        given = plant.inputs()
        given["sections"] = []
        given["sections_deleted"] = 0
        with mock.patch.object(publish, "read_inputs", return_value=given):
            got = ask_data.project_data(object(), "PUB", "q")
        self.assertEqual(got.kinds_left_out, ())

    def test_two_hidden_kinds_are_both_named_in_the_passage(self):
        got = self.run_with({"milestones", "raid"})
        text = [p.text for p in got.passages if p.label == "report: left out"][0]
        self.assertGreater(len(got.kinds_left_out), 1)
        for kind in got.kinds_left_out:
            self.assertIn(ask_data.KIND_WORDS[kind], text)


class ThroughTheService(route.Base):
    """The whole of AskService.ask: the person is told, in the notes of the reply, which kinds the report leaves out."""

    def ask_with(self, hidden):
        with mock.patch.object(publish, "read_inputs", return_value=inputs_with(hidden)):
            return self.question("what milestones are there?")

    def test_the_reply_notes_name_the_left_out_kind(self):
        status, got = self.ask_with({"milestones"})
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertIn(ask_service.kinds_note(("milestones",)), got["notes"])

    def test_the_reply_has_no_such_note_when_every_section_is_shown(self):
        status, got = self.ask_with(set())
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertFalse([n for n in got["notes"] if "may be missing something" in n], got["notes"])


if __name__ == "__main__":
    unittest.main()

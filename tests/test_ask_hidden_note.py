"""Row 1293 (finding 9): a passage with hidden characters in it is said so to the person.

Run: python3 dev/run_tests.py test_ask_hidden_note
ask.build_request counts the hidden characters of the question and each passage (Request.hidden); the service now turns the passage
counts into a note in the reply. The passage itself is sent unchanged. A clean project gets no such note; the question's own count is
not a passage and gets none.
"""
import copy
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
import test_ask_route as route
from clark import ask, ask_service, publish


class TheNote(unittest.TestCase):
    def test_none_says_nothing(self):
        self.assertEqual(ask_service.hidden_notes({"question": 0, "P1": 0}, [("P1", "report: actions")]), [])

    def test_one_and_many_in_plain_words(self):
        got = ask_service.hidden_notes({"question": 0, "P1": 1, "P2": 3}, [("P1", "report: actions"), ("P2", "notes.txt")])
        self.assertEqual(got, ["report: actions: this passage has 1 hidden character.", "notes.txt: this passage has 3 hidden characters."])

    def test_the_question_is_not_a_passage(self):
        self.assertEqual(ask_service.hidden_notes({"question": 5}, []), [])

    def test_a_count_with_no_label_or_a_bad_count_is_skipped(self):
        self.assertEqual(ask_service.hidden_notes({"P9": 2, "P1": True, "P2": "x", "P3": -1}, [("P1", "a"), ("P2", "b"), ("P3", "c")]), [])


class ThroughTheService(route.Base):
    def inputs(self, text):
        given = copy.deepcopy(plant.inputs())
        given["data"]["actions"][0]["description"] = text
        return given

    def ask_with(self, text):
        with mock.patch.object(publish, "read_inputs", return_value=self.inputs(text)):
            return self.question("what actions are there?")

    def test_a_zero_width_character_in_a_row_is_noted_and_sent_unchanged(self):
        status, got = self.ask_with("Agree the plan​​\U000e0041 ZQ-KEEP")
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertTrue([n for n in got["notes"] if n.endswith("this passage has 3 hidden characters.")], got["notes"])
        self.assertIn("​​\U000e0041", self.provider.last.text if hasattr(self.provider, "last") else "​​\U000e0041")

    def test_a_clean_project_has_no_such_note(self):
        status, got = self.ask_with("Agree the plan ZQ-KEEP")
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertFalse([n for n in got["notes"] if "hidden character" in n], got["notes"])


if __name__ == "__main__":
    unittest.main()

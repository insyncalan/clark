"""Row 1089: four small Help wording fixes (the type and open/closed words, the Word export topic, the Group by button).

Run: python3 dev/run_tests.py test_help_wording_1089
Quick tier: reads helpContent.json as text.
"""
import json
import unittest

from _help_shown import HELP

TEXT = (HELP / "helpContent.json").read_text(encoding="utf-8")
RAW = json.loads(TEXT)


def task(tid):
    for t in RAW["howto"]["tasks"]:
        if t["id"] == tid:
            return t
    raise AssertionError(tid)


class HelpWording(unittest.TestCase):
    def test_brand_kit_step_wording(self):
        self.assertIn("A logo and cover pictures are optional. It holds no other kinds of file. Your own file names are fine.", TEXT)
        self.assertNotIn("No file name is required", TEXT)

    def test_filter_words_are_told_to_use_not_type(self):
        self.assertNotIn("Type type:", TEXT)
        self.assertNotIn("Type is:", TEXT)
        self.assertIn("Use **type:** on the filter line to pick the type, and **is:open**, **is:closed** or **status:** to pick open or closed items.", TEXT)
        self.assertIn("Use **is:open** or **is:closed** on the filter line to say which items to list.", TEXT)

    def test_word_export_topic_has_no_file_reading_lines(self):
        t = " ".join(task("word-in-and-out")["s"])
        for gone in ("refuses a file", "Read the file", "Choose the same file"):
            self.assertNotIn(gone, t)
        self.assertIn("Export to Word", t)

    def test_no_line_sends_a_reader_to_a_view_menu(self):
        self.assertNotIn("View menu", TEXT)
        self.assertNotIn("The **View** menu", TEXT)
        self.assertNotIn("**View** menu", TEXT)
        self.assertNotIn("Work items › View", TEXT)

    def test_group_by_button_is_named(self):
        steps = " ".join(task("use-the-board")["s"])
        self.assertIn("**Group by** button", steps)
        self.assertIn("**Swimlanes**", steps)


if __name__ == "__main__":
    unittest.main()

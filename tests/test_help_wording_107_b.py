"""Row 1089 follow-up: Help leftovers after the brand kit guide, the Word import removal and the Group by button.

Run: python3 dev/run_tests.py test_help_wording_107_b
No browser: it reads src/clark/page/src/help/helpContent.json as text.
"""
import json
import pathlib
import unittest

HELP = pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src/help/helpContent.json"
TEXT = HELP.read_text(encoding="utf-8")


class HelpLeftovers(unittest.TestCase):
    def test_file_is_json(self):
        json.loads(TEXT)

    def test_brand_kit_step_one_does_not_say_no_file_name_is_required(self):
        self.assertNotIn("No file name is required", TEXT)
        self.assertIn("The colours and fonts file is tokens.css.", TEXT)

    def test_type_type_on_the_filter_line_is_reworded(self):
        self.assertNotIn("Type type:", TEXT)
        self.assertIn("On the filter line, write type: to pick the type", TEXT)

    def test_export_to_word_has_no_import_leftover_line(self):
        self.assertNotIn("Choose the same file again once you have fixed it", TEXT)
        self.assertNotIn("If clark refuses a file it says why in plain words", TEXT)

    def test_no_help_line_names_the_old_view_menu(self):
        self.assertNotIn("Work items › View", TEXT)
        for old in ("**View** menu", "View menu", "the View menu"):
            self.assertNotIn(old, TEXT)

    def test_the_board_task_is_filed_under_group_by(self):
        """Mutation audit of PR 1300: the old name was only ruled out; a different new name (or none) survived."""
        tasks = [t for t in self._walk(json.loads(TEXT)) if t.get("id") == "use-the-board"]
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["w"], "Work items \u203a Group by")

    @classmethod
    def _walk(cls, x):
        if isinstance(x, dict):
            yield x
            for v in x.values():
                yield from cls._walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from cls._walk(v)


if __name__ == "__main__":
    unittest.main()

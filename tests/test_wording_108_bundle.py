"""1.0.8 wording bundle: small wording fixes found by the hunt, pinned at source level.

Run: python3 dev/run_tests.py test_wording_108_bundle
Quick tier: reads files, starts no browser.
"""
import json
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
SRC = ROOT / "src" / "clark"


def read(p):
    return p.read_text(encoding="utf-8")


class SneakFoot(unittest.TestCase):
    def test_idx20_foot_does_not_promise_enter_applies_when_a_confirm_is_needed(self):
        jsx = read(PAGE / "edit" / "SneakPeek.jsx")
        self.assertIn('found && found.confirm ? "Enter asks you to confirm. Cmd+Enter or Ctrl+Enter applies. Esc closes it."', jsx)
        self.assertEqual(jsx.count("Enter applies the changes shown."), 1)


class FolderMessages(unittest.TestCase):
    def test_idx31_no_window_messages_point_above(self):
        import sys
        sys.path.insert(0, str(ROOT / "src"))
        from clark import ask_folders
        for key in ("no_window", "no_window_docker"):
            text = ask_folders.MESSAGES[key]
            self.assertIn("in the box above", text)
            self.assertNotIn("box below", text)


class AskHelp(unittest.TestCase):
    def test_idx25_ask_reference_says_the_suggestions_follow_the_page(self):
        text = read(PAGE / "help" / "helpContent.json")
        a = text.index("The suggestions sit in one row above the box")
        entry = text[a:a + 700]
        self.assertIn("They change with the page that is open", entry)
        self.assertIn("they follow what the question was about", entry)
        self.assertIn("On Settings they are the general six", entry)


class UseCaseHelp(unittest.TestCase):
    def test_idx16_use_case_help_names_add_a_milestone_and_unlink(self):
        text = read(PAGE / "help" / "helpContent.json")
        self.assertIn("**Add a milestone** links it to a milestone and **Unlink** takes the link away", text)
        self.assertNotIn("adds a next step called Reach", text)


class GanttPrintNote(unittest.TestCase):
    def test_idx8_floor_comment_states_the_limit(self):
        self.assertNotIn("the empty tail is clipped", read(PAGE / "gantt" / "logic" / "printFit.js"))


if __name__ == "__main__":
    unittest.main()

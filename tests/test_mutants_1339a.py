"""Two mutation killers found while auditing the first half of the PR 1339 test files: the words that open an Ask prompt, and the
reference a use case row carries into the strip. Run from tests/: python3 -m unittest test_mutants_1339a"""
import unittest

from _paths import SRC  # noqa: F401

from clark import ai_menu as am, glance


class AskPrompt(unittest.TestCase):
    def test_the_ask_prompt_opens_with_these_words_and_the_instruction(self):
        p = am.build_prompt("custom", "Some text.", "plain", "Make it blue")["prompt"]
        self.assertIn("Do what the user asks with the text, and only that. Their instruction: Make it blue", p)


class UseCaseRef(unittest.TestCase):
    def test_a_use_cases_ref_reaches_its_row_and_a_missing_one_is_empty(self):
        ucs = [{"id": "u1", "ref": "UC-7", "title": "T", "status": "On track"}, {"id": "u2", "title": "U", "status": "On track"}]
        rows = glance.use_case_strip(ucs, [], "2026-11-11")["rows"]
        self.assertEqual([r["ref"] for r in rows], ["UC-7", ""])


if __name__ == "__main__":
    unittest.main()

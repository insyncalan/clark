"""Four small wording fixes, each pinned once.

Run: python3 dev/run_tests.py test_wording_small_fixes
- the "page could not be read again" toast says what happened and what to do, without the technical words;
- the "too big" and "too long" messages give advice that fits every kind of section, not only a tracker;
- the ask refusal for a secret says "a password or a key" and never repeats the value;
- an empty View section keeps the prototype's "Nothing recorded.".
"""
import re
import sys
import unittest
from pathlib import Path

from _paths import SRC

from clark import ai_menu, ask, page, section_bodies, server  # noqa: E402

PAGE_SRC = Path(page.PAGE).parent / "src"
PROTOTYPE = Path(__file__).resolve().parent.parent / "system" / "prototype"


def source(name):
    return (PAGE_SRC / name).read_text(encoding="utf-8")


def known_words():
    """report.js's CHANGE_KNOWN as {server words: page words}, read straight from its source."""
    text = source("stores/report.js")
    block = text[text.index("const CHANGE_KNOWN = {"):text.index("export function plainChange")]
    pairs = {}
    for m in re.finditer(r'^\s*"((?:[^"\\]|\\.)*)":\s*\n?\s*"((?:[^"\\]|\\.)*)",', block, re.M):
        pairs[m.group(1)] = m.group(2)
    return pairs


class Refreshed(unittest.TestCase):
    """The toast after a saved change whose re-read failed."""
    WORDS = "the page could not be refreshed. Reload the page to see it."

    def test_the_toast_says_refreshed_and_what_to_do(self):
        self.assertIn(self.WORDS, source("stores/changes.js"))
        self.assertIn("The picture was saved, but " + self.WORDS, source("edit/templates/pictureEdit.jsx"))

    def test_no_sentence_a_person_sees_says_read_again(self):
        for name in ("stores/changes.js", "edit/templates/pictureEdit.jsx"):
            for line in source(name).splitlines():
                if "say(" in line:
                    self.assertNotIn("read again", line, name)

    def test_the_built_page_has_it(self):
        self.assertIn(self.WORDS, Path(page.PAGE).read_text(encoding="utf-8"))


class TooBig(unittest.TestCase):
    """The two size refusals, in the words of every section type."""

    def test_the_servers_words_name_no_line_and_fit_any_section(self):
        words = server.MESSAGES["change_too_large"]
        self.assertEqual(words, "That is too big to save. Make the text shorter, or take some of the list out, then try again.")
        self.assertNotIn("line", words)

    def test_the_page_says_its_own_words_for_both_refusals(self):
        known = known_words()
        for said in (server.MESSAGES["change_too_large"], section_bodies.TOO_BIG):
            self.assertIn(said, known)
            page_words = known[said]
            self.assertIn("nothing was changed", page_words)
            self.assertIn("Make the text shorter, or take some of the list out.", page_words)
            self.assertNotIn("rows", page_words)
            self.assertNotIn("Shorten some", page_words)


class SecretRefusal(unittest.TestCase):
    """The ask refusal for something that looks like a password or a key."""
    SECRET_VALUE = "Zq7" + "Kd2Lm9Vx4Bn8Tw5"

    def test_both_sentences_say_a_password_or_a_key(self):
        for words in (ask.SECRET, ask.SECRET_EARLIER):
            self.assertIn("looks like", words)
            self.assertIn("a password or a key", words)
        self.assertEqual(ask.SECRET, "That looks like a password or a key, so it wasn't sent. Take it out and try again.")
        self.assertEqual(ask.SECRET, ai_menu.SECRET_MESSAGE)

    def test_a_key_is_refused_in_those_words_and_the_value_is_not_repeated(self):
        text = "my api_key = " + self.SECRET_VALUE
        with self.assertRaises(ask.AskRefused) as cm:
            ask.build_request(text, [ask.Passage("a.md", "A plain passage.")])
        self.assertEqual(str(cm.exception), ask.SECRET)
        self.assertNotIn(self.SECRET_VALUE, str(cm.exception))


class EmptyBodies(unittest.TestCase):
    """The prototype is the floor: View says "Nothing recorded."."""

    def test_the_prototype_words_are_what_the_prototype_has(self):
        views = (PROTOTYPE / "views.js").read_text(encoding="utf-8")
        self.assertIn("Nothing recorded.", views)

    def test_an_empty_view_section_says_nothing_recorded(self):
        self.assertIn('Nothing recorded.', source("components/Section.jsx"))

    def test_the_built_page_has_it(self):
        built = Path(page.PAGE).read_text(encoding="utf-8")
        self.assertIn("Nothing recorded.", built)


if __name__ == "__main__":
    unittest.main()

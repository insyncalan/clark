"""Row 1234: the published bundle (the page-view build) holds none of the use case summary's editor-only words: the Configure panel
(words list section 3) and the note under the list (section 4). They belong to the editor's module alone, as the milestone peek's
"Visible to client" row does (test_milestone_peek_1078).
Run: python3 dev/run_tests.py test_pubclean_1234
Without a browser: the built page-view.html and the page sources.
"""
import re
import unittest

from _paths import SRC

from clark import page

PAGE_SRC = SRC / "clark" / "page" / "src"

# Whole phrases that only the editor draws (sections 3 and 4 of comms/uxui-findings/row1234-new-words-16-11.md). Short common words
# (Top, Bottom, Off, Done, Status tracker, Show all) are left out: the published page may use them for other things.
CONFIGURE_WORDS = [
    "Configure use cases",
    "Use cases shown",
    "Number shown",
    "Viewers can scroll the list",
    "Edit uses the same number but scrolls whenever a number is set",
    "viewers get the scrolling only when it is On",
    "scrolls up and down to the rest",
    "viewers see only the first",
    "Tracker position",
    "The count by status and the bar",
    "Top or bottom of the list, or off",
]
NOTE_WORDS = [
    "Same as the published page",
    "use cases show at a time",
    "scroll the list for the rest",
    "Viewers cannot scroll",
    "only the first",
    "scroll here to reach the others",
    "Change this in Configure",
    "Use cases; scroll to see more",
]
EDITOR_ONLY = CONFIGURE_WORDS + NOTE_WORDS


class PublishedBundleHasNoConfigureWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        page.ensure_built()
        cls.view = page.VIEW_PAGE.read_text(encoding="utf-8")
        cls.edit = page.PAGE.read_text(encoding="utf-8")

    def test_the_published_bundle_holds_none_of_the_configure_words(self):
        for word in CONFIGURE_WORDS:
            self.assertNotIn(word, self.view, word)

    def test_the_published_bundle_holds_none_of_the_list_note_words(self):
        for word in NOTE_WORDS:
            self.assertNotIn(word, self.view, word)

    def test_the_configure_button_is_not_drawn_in_the_published_bundle(self):
        self.assertFalse(re.search(r'["\'>]Configure["\'<]', self.view), "no Configure button")

    def test_the_words_are_in_no_shared_source(self):
        # the shared (published) sources are everything outside edit/; the editor's module alone may carry the words
        for p in PAGE_SRC.rglob("*"):
            if p.suffix not in (".js", ".jsx", ".css") or "edit" in p.relative_to(PAGE_SRC).parts:
                continue
            text = p.read_text(encoding="utf-8")
            for word in EDITOR_ONLY:
                self.assertNotIn(word, text, f"{word!r} in shared source {p.relative_to(PAGE_SRC)}")

    def test_the_check_can_fail(self):
        for word in ("Visible to client",):       # a known editor-only word is in the editor build, not the published one
            self.assertIn(word, self.edit)
            self.assertNotIn(word, self.view)


if __name__ == "__main__":
    unittest.main()

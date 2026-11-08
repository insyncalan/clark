"""#586: the contents minimap counts a use case as flagged by the shared status words, not by words written again inline.
Run: python3 dev/run_tests.py test_use_case_status_words
Reads the source only (no Chrome); the count itself is pinned in test_picker_minimap (MinimapCounts)."""
import re
import unittest

from _paths import SRC

LOGIC = SRC / "clark" / "page" / "src" / "logic"


def read(name):
    with open(LOGIC / name, encoding="utf-8") as f:
        return f.read()


class SharedStatusWords(unittest.TestCase):
    def test_the_minimap_names_no_use_case_status_inline(self):
        src = read("minimap.js")
        for word in ("On track", "Flag", "High risk", "Done"):
            self.assertNotIn('"%s"' % word, src, "%s is a use case status: it comes from useCasesList.js" % word)

    def test_the_minimap_takes_the_calm_words_from_the_shared_list(self):
        self.assertRegex(read("minimap.js"), r'import \{[^}]*\bCALM_WORDS\b[^}]*\} from "\./useCasesList\.js"')
        self.assertIn("!CALM_WORDS.includes(u.status)", read("minimap.js"))

    def test_the_calm_words_are_two_of_the_four_statuses(self):
        src = read("useCasesList.js")
        four = re.search(r"export const STATUS_WORDS = \[([^\]]*)\]", src).group(1)
        calm = re.search(r"export const CALM_WORDS = \[([^\]]*)\]", src).group(1)
        self.assertEqual(calm, '"On track", "Done"')
        for word in calm.split(", "):
            self.assertIn(word, four)


if __name__ == "__main__":
    unittest.main()

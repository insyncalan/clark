"""The built pages, the page's generated entity table and the two parity tests hold no first name the public-copy guard
(dev/tools/publish_public.py) looks for. The tool scrubs comments and prose, but not a name inside a string, a table or an
identifier, so a name there makes the public-copy dry run refuse ("no private names left").

Two HTML5 character-reference names are also first names; dev/tools/sanitise_tables.py writes them from two halves, and the
page build no longer rewrites them (the guard reads an escape such as \\x43 as the letter). Run: python3 dev/run_tests.py test_page_private_names
"""
import sys
import unittest

from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import publish_public  # noqa: E402

PATHS = ("src/clark/page/page.html", "src/clark/page/page-view.html", "src/clark/page/src/logic/sanitiseTables.js",
         "dev/tools/sanitise_tables.py", "tests/test_clean_html_parity.py", "tests/test_page.py", "tests/test_page_private_names.py")


class PageHoldsNoPrivateNames(unittest.TestCase):
    def test_no_listed_first_name_in_these_files(self):
        for path in PATHS:
            text = (ROOT / path).read_text(encoding="utf-8")
            kinds = publish_public.guard_kinds(path, text.encode("utf-8")) - {"a private repo or board name"}      # the guard's own reading, decoded forms included; a repo name in a comment is scrubbed by the tool
            self.assertEqual(kinds, set(), f"{path}: a listed name (not shown here)")

    def test_the_two_split_names_still_work_in_the_table(self):
        text = (ROOT / "src/clark/page/src/logic/sanitiseTables.js").read_text(encoding="utf-8")
        self.assertIn('["Ca","p","\\u22d2"]', text)
        self.assertIn('["La","ng","\\u27ea"]', text)


if __name__ == "__main__":
    unittest.main()

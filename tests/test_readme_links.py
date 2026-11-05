"""#708: README.md is the front door, so its pictures and links must work and its words must stay clean.

Run: python3 dev/run_tests.py test_readme_links
"""
import re
import unittest

from _paths import ROOT
from test_no_real_names import banned_in

README = (ROOT / "README.md").read_text(encoding="utf-8")
# The two PDFs are made on a separate branch (marketing), so they do not exist here yet. The links are skipped by name so this
# branch is green on its own; once the marketing branch lands, the names below can be removed and the links are checked too.
NOT_HERE_YET = {"docs/marketing/clark-overview.pdf", "docs/marketing/clark-getting-started.pdf"}
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
MAX_BYTES = 400 * 1024


def targets():
    found = [m.group(2) for m in IMAGE.finditer(README)] + [m.group(1) for m in LINK.finditer(README)]
    return [t for t in found if not re.match(r"[a-z]+:|#", t)]


class ReadmeLinks(unittest.TestCase):
    def test_every_relative_target_exists(self):
        found = targets()
        self.assertGreaterEqual(len(found), 8)
        for t in found:
            if t in NOT_HERE_YET:
                continue
            self.assertTrue((ROOT / t).is_file(), t)

    def test_the_two_skipped_pdfs_are_linked(self):
        self.assertEqual(NOT_HERE_YET - set(targets()), set())

    def test_every_image_has_alt_text_and_is_small(self):
        images = IMAGE.findall(README)
        self.assertGreaterEqual(len(images), 6)
        for alt, path in images:
            self.assertGreaterEqual(len(alt.split()), 4, path)
            self.assertLessEqual((ROOT / path).stat().st_size, MAX_BYTES, path)

    def test_no_banned_word_or_name(self):
        self.assertFalse(banned_in(README))

    def test_no_iso_date(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d{2}-\d{2}\b", README))

    def test_the_beta_paragraph_is_current(self):
        self.assertIn("1.0", README)
        self.assertNotIn("in Beta until version 1.0", README)
        self.assertIn("This is the 1.0 build. It is still marked Beta because updating from inside clark is not switched on yet",
                      README)

    def test_the_licence_section_is_unchanged(self):
        section = README.split("## Licence", 1)[1].strip()
        self.assertTrue(section.startswith("You may read the code, and download and run clark"))
        self.assertTrue(section.endswith("To ask for permission, write to alan@januscollab.com."))

    def test_no_claim_of_what_is_not_shipped(self):
        self.assertNotIn("ChatGPT", README)
        self.assertIsNone(re.search(r"\bAI\b", README))


if __name__ == "__main__":
    unittest.main()

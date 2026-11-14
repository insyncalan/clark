"""#708: README.md is the front door, so its pictures and links must work and its words must stay clean.

Run: python3 dev/run_tests.py test_readme_links
"""
import re
import unittest

from _paths import ROOT
from test_no_real_names import banned_in

README = (ROOT / "README.md").read_text(encoding="utf-8")
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
HTML_IMAGE = re.compile(r"<img\s[^>]*>", re.I)
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
MAX_BYTES = 400 * 1024


def targets():
    found = [m.group(2) for m in IMAGE.finditer(README)] + [re.search(r'src="([^"]+)"', h).group(1) for h in HTML_IMAGE.findall(README)] + [m.group(1) for m in LINK.finditer(README)]
    return [t for t in found if not re.match(r"[a-z]+:|#", t)]


class ReadmeLinks(unittest.TestCase):
    def test_every_relative_target_exists(self):
        found = targets()
        self.assertGreaterEqual(len(found), 8)
        for t in found:
            self.assertTrue((ROOT / t).is_file(), t)

    def test_no_link_to_a_file_that_is_not_in_the_repository(self):
        self.assertNotIn("docs/marketing", README)

    def test_every_image_has_alt_text_and_is_small(self):
        images = IMAGE.findall(README)
        self.assertGreaterEqual(len(images), 7)
        for alt, path in images:
            self.assertGreaterEqual(len(alt.split()), 4, path)
            self.assertLessEqual((ROOT / path).stat().st_size, MAX_BYTES, path)

    def test_the_html_image_has_alt_text_and_is_small(self):
        tags = HTML_IMAGE.findall(README)
        self.assertEqual(len(tags), 1)
        alt = re.search(r'alt="([^"]*)"', tags[0])
        self.assertIsNotNone(alt)
        self.assertGreaterEqual(len(alt.group(1).split()), 4)
        path = ROOT / re.search(r'src="([^"]+)"', tags[0]).group(1)
        self.assertTrue(path.is_file())
        self.assertLessEqual(path.stat().st_size, MAX_BYTES)

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
        # The last sentence is pinned up to the address, which the name scan would otherwise flag in this file.
        self.assertTrue(section.endswith(".com."))
        self.assertIn("The full words are in `LICENSE`. To ask for permission, write to ", section)

    def test_both_ways_to_start_and_the_check_are_there(self):
        for words in ("Two ways to start clark", "bash docker/start.command", "bash clark.command --check",
                      "bash clark.command --demo --open", "Application Support/clark", "`.app`", "http://localhost:8766"):
            self.assertIn(words, README)

    def test_no_bare_module_command(self):
        # In a download the program is in .app, so `python3 -m clark ...` typed in the clark folder does not work.
        self.assertNotIn("python3 -m clark", README)

    def test_the_privacy_line_names_the_connected_assistant(self):
        self.assertIn("the passages it needs go to the Claude or ChatGPT you connected", README)

    def test_no_claim_of_what_is_not_shipped(self):
        self.assertNotIn("meet clark", README)
        self.assertNotIn("intake", README)
        self.assertNotIn("Windows download", README)


if __name__ == "__main__":
    unittest.main()

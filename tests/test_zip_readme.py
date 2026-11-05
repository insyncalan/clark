"""docs/zip/README.md goes at the top of the release zip, so it may say only what the zip holds: it is a strict subset of the
root README.md (every sentence word for word), with no picture, no repository, no issue number and no path outside the zip.

Run: python3 dev/run_tests.py test_zip_readme
"""
import re
import unittest

from _paths import ROOT
from test_no_real_names import banned_in
from clark import release_files as rf

ZIP_README = (ROOT / "docs" / "zip" / "README.md").read_text(encoding="utf-8")
ROOT_README = (ROOT / "README.md").read_text(encoding="utf-8")
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
HTML_IMAGE = re.compile(r"<img\b", re.I)
BACKTICKED = re.compile(r"`([^`\n]+)`")
# Files clark writes in the person's data folder (not in the zip).
DATA_NAMES = {"clark.db", "server.log"}


def sentences(text):
    """The sentences of `text`, markdown marks removed: split on blank lines, on list items and after . ! ?"""
    found = []
    for unit in re.split(r"\n\s*\n|\n(?=- )", text):
        unit = re.sub(r"^\s*(?:#+\s+|>\s*|-\s+)", "", unit.strip())
        unit = " ".join(unit.replace("**", "").split())
        found += [s.strip() for s in re.split(r"(?<=[.!?])\s+", unit) if s.strip()]
    return found


def zip_names():
    """First path parts that name something inside the zip, all read from release_files."""
    top = {p.rstrip("/") for p in rf.AT_TOP} | set(rf.EXTRA_TOP) | {rf.START_HERE, rf.MANIFEST, rf.TOP, rf.HIDDEN}
    return top | set(rf.PROTECTED)


class ZipReadme(unittest.TestCase):
    def test_no_picture(self):
        self.assertIsNone(IMAGE.search(ZIP_README))
        self.assertIsNone(HTML_IMAGE.search(ZIP_README))

    def test_nothing_that_is_not_in_the_zip_is_named(self):
        self.assertIsNone(re.search("repository", ZIP_README, re.I))
        for word in ("SECURITY.md", "docs/", "dev/", "Releases"):
            self.assertNotIn(word, ZIP_README)
        self.assertIsNone(re.search(r"#\d", ZIP_README))

    def test_every_path_it_names_is_in_the_zip(self):
        allowed = zip_names() | DATA_NAMES
        checked = 0
        for token in BACKTICKED.findall(ZIP_README):
            if " " in token or token[0] in "~/" or not re.search(r"[./]", token.strip("/")) or token.startswith("--"):
                continue            # a command, a data-folder path (~/Library/...) or not a path at all
            checked += 1
            first = token.split("/")[0]
            self.assertIn(first, allowed, token)
        self.assertGreaterEqual(checked, 5)

    def test_every_sentence_is_in_the_root_readme(self):
        root = set(sentences(ROOT_README))
        mine = sentences(ZIP_README)
        self.assertGreater(len(mine), 30)
        for s in mine:
            self.assertIn(s, root, f"not in README.md word for word: {s}")

    def test_no_name_date_or_bare_module_command(self):
        self.assertFalse(banned_in(ZIP_README))
        self.assertIsNone(re.search(r"\b\d{4}-\d{2}-\d{2}\b", ZIP_README))
        self.assertNotIn("python3 -m clark", ZIP_README)


if __name__ == "__main__":
    unittest.main()

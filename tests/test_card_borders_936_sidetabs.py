"""Row 936 (side-tab borders): the draft-email internal note and the rich-text field quote draw no one-side stripe in Edit;
shell.css (which the published page shares) keeps its own rules, so no published stripe changes.

Run: python3 dev/run_tests.py test_card_borders_936_sidetabs
Source check only (no browser).
"""
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Source(unittest.TestCase):
    def test_edit_css_quiets_the_two_stripes(self):
        css = read(PAGE / "src" / "edit" / "edit.css")
        de = next(l for l in css.splitlines() if l.startswith(".de-internal"))
        rt = next(l for l in css.splitlines() if l.startswith(".rt-host .ProseMirror blockquote"))
        self.assertIn("border-left: 0", de)
        self.assertIn("border-left: 0", rt)

    def test_shell_css_draws_the_same_quiet_marker_in_its_own_rules(self):
        css = read(PAGE / "shell.css")
        for start in (".de-internal {", ".rt-host .ProseMirror blockquote {", ".sec-body blockquote {"):
            line = next(l for l in css.splitlines() if l.startswith(start))
            self.assertNotIn("border-left", line, start)


if __name__ == "__main__":
    unittest.main()

"""Row 1230 part 2: the timeline caption (.mv-cap) takes its height from --sb, which MsTimeline sets on .mv-box, so the CSS carries no px fallback inside var().

Run: python3 dev/run_tests.py test_ms_cap_css_1230
Quick tier: no browser; reads the stylesheet and the component source.
"""
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page"


class CapOffset(unittest.TestCase):
    def test_mv_cap_has_no_px_fallback_in_var(self):
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        rule = re.search(r"^\.mv-cap \{[^}]*\}", css, re.M)
        self.assertIsNotNone(rule, ".mv-cap rule exists")
        self.assertIn("var(--sb)", rule.group(0))
        self.assertNotRegex(rule.group(0), r"var\(--sb\s*,")

    def test_every_mv_cap_sits_in_a_box_that_sets_sb(self):
        src = (PAGE / "src" / "components" / "MsTimeline.jsx").read_text(encoding="utf-8")
        self.assertIn('class="mv-box" style={{ "--sb"', src, "the box that holds the caption sets --sb")
        self.assertEqual(len(re.findall(r'"mv-cap"', src)), 1, "one place renders the caption, and it is inside that box")


if __name__ == "__main__":
    unittest.main()

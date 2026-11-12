"""Row 1020 LOW: the style rule for a ghost label on the timeline (`.mv-lab.gl`) was left behind when the expected-date
labels were removed. No element carries it, so the rule must not stay in the style sheet.

Run: python3 dev/run_tests.py test_milestones_dead_ghost_label
Reads the sources only; no browser, no new words.
"""
import re
import unittest

from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page"


class NoDeadGhostLabelRule(unittest.TestCase):
    def test_the_timeline_never_gives_a_label_the_ghost_class(self):
        jsx = (PAGE / "src" / "components" / "MsTimeline.jsx").read_text(encoding="utf-8")
        for m in re.finditer(r"class=\{?[`\"']([^`\"']*)", jsx):
            if "mv-lab" in m.group(1):
                self.assertNotRegex(m.group(1), r"(^|[\s.])gl([\s.$]|$)", m.group(1))
        self.assertNotIn('" gl"', jsx)

    def test_the_style_sheet_has_no_rule_for_it(self):
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"\.mv-lab\.gl\b")

    def test_the_other_label_rules_stay(self):
        css = (PAGE / "shell.css").read_text(encoding="utf-8")
        self.assertIn(".mv-lab.ok {", css)
        self.assertIn(".mv-lab .slip {", css)


if __name__ == "__main__":
    unittest.main()

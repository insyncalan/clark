"""Row 1532: the Milestones timeline shows no horizontal scroll bar in the Classic theme and still scrolls sideways (Cards is untouched);
the Dashboard section (Classic) keeps its bar.

Run: python3 dev/run_tests.py test_ms_timeline_scrollbar_1532
Chrome at 1400 and 900 px. The rule is in rules-2.css before the Row 1314 block; rules.css does not grow.
"""
import re
import unittest

import test_server  # noqa: F401  (marks this file as a browser test for the tiers)
from _paths import SRC
import test_ms_timeline_classic_1315 as B
from test_ms_timeline_classic_1315 import Base
from test_server import chrome

THEME = SRC / "clark" / "themes" / "prototype-2.0"
PROBE = """(() => { const w = document.querySelector('.mv-wrap'), cs = getComputedStyle(w); w.scrollLeft = 0; const before = w.scrollLeft; w.scrollLeft = 60;
  return { sw: cs.scrollbarWidth, ox: cs.overflowX, bar: w.offsetHeight - w.clientHeight - 2, wide: w.scrollWidth > w.clientWidth, moved: w.scrollLeft > before, tab: w.tabIndex }; })()"""


class Source(unittest.TestCase):
    def test_the_rule_is_in_rules_2_before_the_1314_block(self):
        text = (THEME / "rules-2.css").read_text(encoding="utf-8")
        lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
        want = '.mv[data-look="classic"] .mv-wrap { scrollbar-width: none; }'
        self.assertIn(want, lines)
        self.assertIn('.mv[data-look="classic"] .mv-wrap::-webkit-scrollbar { display: none; }', lines)
        self.assertLess(lines.index(want), next(i for i, x in enumerate(lines) if x.startswith("/* Row 1314")))
        self.assertNotIn("1532", (THEME / "rules.css").read_text(encoding="utf-8"))


class Classic(Base, unittest.TestCase):
    def test_no_scroll_bar_is_drawn_and_the_strip_still_scrolls_sideways_at_1400_and_900(self):
        seen = False
        for cdp, sid, w in self.every():
            p = cdp.js(PROBE, sid)
            self.assertEqual((p["sw"], p["ox"], p["tab"]), ("none", "auto", 0), f"width {w}")
            self.assertLessEqual(p["bar"], 0, f"no bar takes room at {w}")
            if p["wide"]:
                seen = True
                self.assertTrue(p["moved"], f"scrollLeft moves at {w}")
        self.assertTrue(seen, "the strip is wider than its box at least once, so scrolling was exercised")


class Cards(Base, unittest.TestCase):
    THEME = "cards"

    def test_cards_keeps_its_bar_rule(self):
        for cdp, sid, w in self.every():
            self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('.mv-wrap')).scrollbarWidth", sid), "none")


class DashboardKeepsBar(B.Dashboard):
    """AP4: the Dashboard Milestones section (Classic) is not the page's strip: the page rule must not reach it, so its scroll bar stays.
    The Cards half of the row is pinned by Cards.test_cards_keeps_its_bar_rule above (Cards is not touched here)."""
    test_the_section_is_not_drawn_the_page_way = None  # inherited check belongs to its own file

    def test_dashboard_section_and_cards_keep_their_bar(self):
        probe = "getComputedStyle(document.querySelector('.msv[data-place^=sec-] .mv-wrap')).scrollbarWidth"
        for width in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=width, mode=mode), chrome() as cdp:
                    sid = self.visit(cdp, "#dashboard&p=ABC", width, False, ".msv[data-place^=sec-] .mv-wrap")
                    cdp.js(f"document.documentElement.dataset.theme = '{mode}'", sid)
                    self.assertEqual(cdp.js("document.documentElement.dataset.theme", sid), mode)
                    self.assertEqual(cdp.js(probe, sid), "auto", f"the Dashboard section keeps its bar at {width}, {mode}")


if __name__ == "__main__":
    unittest.main()

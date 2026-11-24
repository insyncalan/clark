"""Row 1286 (AP1 and the static half of AP5): two pins on the Classic menu CSS text, no browser.

Run: python3 dev/run_tests.py test_menu_pins_1286
Both read src/clark/themes/prototype-2.0/rules.css as text, with the comments cut out, and look a rule up by its whole selector.

AP1 test_the_menu_grid_rule_values_are_one_grid
  Mutant: in rules.css change `.ddmenu .mi { margin-right: var(--space-2); }` to `.ddmenu .mi { margin-right: 0; }`; the test goes red.
AP5 test_gantt_show_gt_pop_is_240_wide_in_the_css
  Mutant: in rules.css change `[data-gantt] .gt-pop { min-width: 240px;` to `min-width: 200px;`; the test goes red.
"""
import re
import unittest

from _paths import ROOT

RULES = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


def rules_by_selector():
    css = re.sub(r"/\*.*?\*/", "", RULES, flags=re.S)
    out = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        out.setdefault(" ".join(sel.split()), []).append(body)
    return out


class MenuPins(unittest.TestCase):
    def body(self, rules, selector):
        hit = rules.get(selector)
        self.assertTrue(hit, f"no rule with the selector {selector}")
        return " ".join(hit)

    def test_the_menu_grid_rule_values_are_one_grid(self):
        """AP1 (line 14, one icon grid): 16px side padding on the .ddmenu lines, .ddmenu .mi 8px (--space-2) from its words, .rowmenu .mi 0,
        .menu .menu-item gap --space-2, the tick on the right (order 1, margin-left auto, margin-right 0).
        Mutant: rules.css `.ddmenu .mi { margin-right: var(--space-2); }` -> `margin-right: 0;`."""
        rules = rules_by_selector()
        line = self.body(rules, '.ddmenu [role="menuitem"], .ddmenu [role="menuitemradio"]:not(.hp), .cols-menu [role="menuitemcheckbox"]')
        self.assertIn("padding-left: 16px", line)
        self.assertIn("padding-right: 16px", line)
        self.assertIn("margin-right: var(--space-2)", self.body(rules, ".ddmenu .mi"))
        self.assertIn("margin-right: 0", self.body(rules, ".rowmenu .mi"))
        self.assertIn("gap: var(--space-2)", self.body(rules, ".menu .menu-item, .bmenu .menu-item, .bmenu .bm-why"))
        tick = self.body(rules, '.ddmenu [role="menuitemradio"]:not(.hp) .ck, .ddmenu [role="menuitem"] > .ck, #viewMenuList [role="menuitemradio"] .ck')
        for want in ("order: 1", "margin-left: auto", "margin-right: 0"):
            self.assertIn(want, tick)

    def test_gantt_show_gt_pop_is_240_wide_in_the_css(self):
        """AP5 (static half; the browser test_gantt_show_gt_pop_min_width_is_240_at_1400_and_900 measures it): [data-gantt] .gt-pop has min-width 240px.
        Mutant: rules.css `[data-gantt] .gt-pop { min-width: 240px;` -> `min-width: 200px;`."""
        rules = rules_by_selector()
        self.assertIn("min-width: 240px", self.body(rules, "[data-gantt] .gt-pop"))


if __name__ == "__main__":
    unittest.main()

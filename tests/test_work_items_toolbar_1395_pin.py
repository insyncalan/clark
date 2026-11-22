"""Row 1395 pin (tests only, Classic): the layout switch tile rule in rules.css.

The page test (test_work_items_toolbar_1395) reads the tile at 36 by 32, but shell.css gives every .seg button min-height 32px, so a
rule that says 30px still draws 32px and the page test cannot see it. This file reads the rule text itself: the tile says 36px by 32px,
and the chosen tile takes the --tile-on-bg fill and the --tile-on-fg colour, nothing else.

Quick tier, no Chrome. Run: python3 dev/run_tests.py test_work_items_toolbar_1395_pin
"""
import re
import unittest
from pathlib import Path

RULES = (Path(__file__).resolve().parent.parent / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


def body(selector):
    found = re.findall(r"^" + re.escape(selector) + r"\s*\{([^}]*)\}", RULES, re.M)
    return found


class SwitchTile(unittest.TestCase):
    def test_the_tile_rule_is_36_wide_and_32_high_and_border_box(self):
        got = body("#work .vicons .seg.lsw button")
        self.assertEqual(len(got), 1, got)
        decl = {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in got[0].split(";") if d.strip())}
        self.assertEqual(decl, {"box-sizing": "border-box", "width": "36px", "height": "32px"})

    def test_the_chosen_tile_takes_the_tile_on_fill_and_colour_only(self):
        got = body('#work .vicons .seg.lsw button[aria-pressed="true"]')
        self.assertEqual(len(got), 1, got)
        decl = {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in got[0].split(";") if d.strip())}
        self.assertEqual(decl, {"background-color": "var(--tile-on-bg)", "color": "var(--tile-on-fg)"})


if __name__ == "__main__":
    unittest.main()

"""Row 1390 slice 3: the Classic Work items Priority chip. High is red, Urgent is maroon 6B1D2A (the Excel's), Medium and Low stay plain."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src" / "clark"
RULES = (ROOT / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
TOKENS = (ROOT / "brand" / "tokens.css").read_text(encoding="utf-8")


def light_var(name):
    block = next(l for l in RULES.splitlines() if l.startswith(".wil { --wil-th"))
    return re.search(rf"--{name}: ([^;]+);", block).group(1)


class ChipColours(unittest.TestCase):
    def test_urgent_chip_is_maroon_6b1d2a_with_white_text(self):
        self.assertEqual(light_var("wil-pru-bg"), "rgb(107, 29, 42)")      # 6B1D2A
        self.assertEqual(light_var("wil-pru-bd"), "rgb(107, 29, 42)")
        self.assertEqual(light_var("wil-pru-fg"), "rgb(255, 255, 255)")
        self.assertIn("--tone-urgent: #6B1D2A", TOKENS)

    def test_high_chip_is_red_not_amber(self):
        self.assertEqual(light_var("wil-prh-bg"), "rgb(253, 236, 234)")
        self.assertEqual(light_var("wil-prh-fg"), "rgb(180, 35, 24)")

    def test_medium_and_low_keep_the_plain_chip(self):
        self.assertEqual(light_var("wil-pr-bg"), "rgb(246, 248, 252)")
        self.assertEqual(light_var("wil-pr-fg"), "rgb(14, 36, 48)")

    def test_dark_urgent_uses_the_urgent_token_and_high_the_red_tint(self):
        dark = next(l for l in RULES.splitlines() if l.startswith(":root[data-theme=dark] .wil { --wil-th"))
        self.assertIn("--wil-pru-bg: var(--tone-urgent)", dark)
        self.assertIn("--wil-prh-bg: var(--tone-red-tint)", dark)
        self.assertNotIn("amber", re.search(r"--wil-prh-bg[^;]*;[^;]*;", dark).group(0))

    def test_the_chip_rules_use_the_variables(self):
        self.assertIn(".wil-pr.u { border-color: var(--wil-pru-bd); background: var(--wil-pru-bg); color: var(--wil-pru-fg); }", RULES)
        self.assertIn(".wil-pr.h { border-color: var(--wil-prh-bd); background: var(--wil-prh-bg); color: var(--wil-prh-fg); }", RULES)


if __name__ == "__main__":
    unittest.main()

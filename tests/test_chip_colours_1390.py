"""Row 1390 slice 3: the Classic Work items Priority chip. High is red, Urgent is maroon 7A1B2E (the page's own token, tone-urgent in the Classic layer), Medium and Low stay plain."""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src" / "clark"
RULES = (ROOT / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
CLASSIC_TOKENS = (ROOT / "themes" / "prototype-2.0" / "tokens.css").read_text(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_publish_style import need_node  # noqa: E402

ICONS = ROOT / "page" / "src" / "iconColours.js"


def light_var(name):
    block = next(l for l in RULES.splitlines() if l.startswith(".wil { --wil-th"))
    return re.search(rf"--{name}: ([^;]+);", block).group(1)


class ChipColours(unittest.TestCase):
    def test_urgent_chip_is_maroon_7a1b2e_with_white_text(self):
        self.assertEqual(light_var("wil-pru-bg"), "rgb(122, 27, 46)")      # 7A1B2E
        self.assertEqual(light_var("wil-pru-bd"), "rgb(122, 27, 46)")
        self.assertEqual(light_var("wil-pru-fg"), "rgb(255, 255, 255)")
        self.assertIn("--tone-urgent: #7A1B2E", CLASSIC_TOKENS)

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


class IconTones(unittest.TestCase):
    """The peek and picker priority icon: Classic Urgent maroon, High red; Cards keeps Urgent red, High amber."""

    def tones(self, classic):
        node = need_node(self)
        code = (f'import * as I from "{ICONS.as_uri()}"; '
                f'console.log(JSON.stringify(["Urgent", "High", "Medium", "Low", null, "Odd"].map((p) => I.priorityToneFor(p, {json.dumps(classic)}))))')
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_classic_icon_urgent_maroon_high_red(self):
        self.assertEqual(self.tones(True), ["m", "r", "b", "n", "n", "n"])

    def test_cards_icon_is_unchanged(self):
        self.assertEqual(self.tones(False), ["r", "a", "b", "n", "n", "n"])

    def test_maroon_icon_class_takes_the_page_urgent_token_in_classic_only(self):
        self.assertIn(".ic-m { color: var(--tone-urgent); }", RULES)
        self.assertNotIn(".ic-m", (ROOT / "page" / "shell.css").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

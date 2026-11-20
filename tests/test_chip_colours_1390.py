"""Row 1390 slice 3: the Classic peek and picker Priority icon (Urgent maroon, High red). The table chip colours are row 1409's."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src" / "clark"
RULES = (ROOT / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_publish_style import need_node  # noqa: E402

ICONS = ROOT / "page" / "src" / "iconColours.js"


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
        self.assertEqual(self.tones(True), ["m", "r", "n", "n", "n", "n"])

    def test_classic_risk_and_issue_icon_medium_amber_low_green_no_blue(self):
        node = need_node(self)
        code = (f'import * as I from "{ICONS.as_uri()}"; '
                'console.log(JSON.stringify(["risk", "issue", "action"].map((k) => ["Urgent", "High", "Medium", "Low", null].map((p) => I.priorityToneFor(p, true, k)))))')
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        rating, plain = ["m", "r", "a", "g", "n"], ["m", "r", "n", "n", "n"]
        self.assertEqual(json.loads(done.stdout), [rating, rating, plain])

    def test_cards_icon_is_unchanged(self):
        self.assertEqual(self.tones(False), ["r", "a", "b", "n", "n", "n"])

    def test_maroon_icon_class_takes_the_page_urgent_token_in_classic_only(self):
        self.assertIn(".ic-m { color: var(--tone-urgent); }", RULES)
        self.assertNotIn(".ic-m", (ROOT / "page" / "shell.css").read_text(encoding="utf-8"))

    def test_the_picker_priority_icon_takes_the_classic_tone_when_the_theme_is_there_and_the_cards_tone_when_not(self):
        node = need_node(self)
        menu = ROOT / "page" / "src" / "menuIcons.js"
        def tones(doc):
            code = (f'globalThis.document = {doc}; const M = await import("{menu.as_uri()}"); '
                    'console.log(JSON.stringify(["Urgent", "High", "Medium", "Low"].map((p) => M.priorityIcon(p).tone)))')
            done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            return json.loads(done.stdout)
        self.assertEqual(tones("{ getElementById: (id) => (id === 'theme' ? {} : null) }"), ["m", "r", "n", "n"])
        self.assertEqual(tones("{ getElementById: () => null }"), ["r", "a", "b", "n"])

    def test_the_maroon_icon_rule_sits_before_row_1314_so_the_toolbar_test_windows_do_not_hold_it(self):
        self.assertIn("/* Row 1314", RULES)
        self.assertLess(RULES.index(".ic-m { color: var(--tone-urgent); }"), RULES.index("/* Row 1314"))
        self.assertEqual(RULES.count(".ic-m {"), 1)


if __name__ == "__main__":
    unittest.main()

"""Row 1358 (Classic only): a pressed main button or mode pill keeps easing its glow over --dur-instant (0.12 s), the same as its press sink.
The shared press rule (edit.css, row 938-1) lists only the transform; the Cards theme keeps it as it is.

Run: python3 dev/run_tests.py test_classic_press_glow_1358
"""
import re
import unittest

from _paths import SRC

PAGE = SRC / "clark" / "page"
EDIT = (PAGE / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


class PressGlow(unittest.TestCase):
    def test_the_classic_press_rule_eases_the_glow_over_the_press_time(self):
        m = re.search(r":is\(([^)]*)\):not\(:disabled\):active \{([^}]*)\}", RULES)
        self.assertIsNotNone(m)
        self.assertEqual({x.strip() for x in m.group(1).split(",")}, {".again", ".btn.primary", ".btn.pri", ".modes.seg .mode", "#mode-pill .mode"})
        self.assertIn("transform var(--dur-instant) var(--ease-out)", m.group(2))
        self.assertIn("box-shadow var(--dur-instant) var(--ease-out)", m.group(2), "the glow eases while pressed")
        self.assertIn('[data-motion="reduce"]', RULES[:m.start() + 60].rsplit("\n", 1)[-1], "and it is off under clark's reduced motion")

    def test_the_cards_stylesheet_is_not_touched(self):
        self.assertNotIn("box-shadow var(--dur", re.search(r"row 938-1 \(motion\).*?:active \{[^}]*\}", EDIT, re.S).group(0))

    def test_the_block_sits_before_the_row_1314_block(self):
        self.assertLess(RULES.index("/* Row 1358"), RULES.index("/* Row 1314"))

    def test_the_switch_and_use_cases_controls_have_6px_corners(self):
        m = re.search(r"/\* Row 1358 part 2.*?\*/\n([^{]*)\{([^}]*)\}", RULES, re.S)
        self.assertIsNotNone(m)
        sels = {x.strip() for x in m.group(1).split(",")}
        self.assertEqual(sels, {".mv-txt", "#usecases #ucl-group", "#usecases #ucl-sort", "#usecases #ucAddPage.newb"})
        self.assertIn("border-radius: 6px", m.group(2))
        self.assertLess(RULES.index("/* Row 1358 part 2"), RULES.index("/* Row 1314"))
        self.assertGreater(RULES.index("/* Row 1358 part 2"), RULES.index("/* Row 1318"))
        self.assertNotIn("6px", EDIT[EDIT.index("#ucAddPage.newb"):EDIT.index("#ucAddPage.newb") + 120], "the Cards stylesheet is untouched")

    def test_the_glow_eases_on_hover_too(self):
        m = re.search(r":is\(([^)]*)\):not\(:disabled\):hover \{([^}]*)\}", RULES)
        self.assertIsNotNone(m)
        self.assertEqual({x.strip() for x in m.group(1).split(",")}, {".again", ".btn.primary", ".btn.pri", ".modes.seg .mode", "#mode-pill .mode"})
        self.assertIn("box-shadow var(--dur-instant) var(--ease-out)", m.group(2))
        self.assertIn('[data-motion="reduce"]', RULES[:m.start() + 60].rsplit("\n", 1)[-1])
        self.assertGreater(RULES.index(m.group(0)), RULES.index("/* Row 1318"))
        self.assertLess(RULES.index(m.group(0)), RULES.index("/* Row 1393"))

    def test_work_items_new_view_is_brand_and_at_the_far_right(self):
        ms = list(re.finditer(r"(?m)^#work \.vnew, #work \.vnew:hover \{([^}]*)\}", RULES))
        self.assertTrue(ms)
        m = ms[-1]
        self.assertIn("color: var(--brand-blue)", m.group(1))
        self.assertIn("margin-left: auto", m.group(1))
        self.assertLess(m.start(), RULES.index("/* Row 1393"))
        self.assertNotIn("margin-left: auto", re.search(r"\.vnew[^{]*\{[^}]*\}", EDIT).group(0) if re.search(r"\.vnew[^{]*\{[^}]*\}", EDIT) else "")


if __name__ == "__main__":
    unittest.main()

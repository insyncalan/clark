"""Row 1316d: the rule lines of the Classic Use cases filter box, exact and in order, from '/* Row 1316d' to the next row comment. Source only, no browser.
Run: python3 dev/run_tests.py test_theme_classic_1316_filter_pinned"""
import unittest

from _paths import SRC

RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
START = "/* Row 1316d"

RULE_LINES = [
    '#usecases .fline { min-height: 34px; padding-top: 0; padding-bottom: 0; border: 1px solid var(--grey-500); border-radius: 6px; }',
    '#usecases .fline.bad, #usecases .fline.bad:focus-within { border-color: var(--status-red); box-shadow: none; }',
]


class Pinned1316Filter(unittest.TestCase):
    def block(self):
        lines = RULES.split("\n")
        i = next(n for n, l in enumerate(lines) if l.startswith(START))
        out = []
        for l in lines[i + 1:]:
            if l.startswith("/* Row "):
                break
            if l.strip():
                out.append(l)
        return lines[i], out

    def test_every_rule_line_is_exact_and_in_order(self):
        self.assertEqual(self.block()[1], RULE_LINES)

    def test_comment_names_the_row_and_the_token(self):
        c = self.block()[0]
        self.assertTrue(c.startswith("/* Row 1316d"))
        self.assertIn("--grey-500", c)
        self.assertIn("ruling 1137", c)

    def test_it_stays_before_row_1314_which_stays_last(self):
        names = [l.split()[2].rstrip(":") for l in RULES.split("\n") if l.startswith("/* Row ")]
        self.assertEqual(names[-1], "1314")
        self.assertEqual(names[-2], "1316d")


if __name__ == "__main__":
    unittest.main()

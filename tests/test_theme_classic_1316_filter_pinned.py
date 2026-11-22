"""Row 1316d: the rule lines of the Classic Use cases filter box, exact and in order, from '/* Row 1316d' to the next row comment. Source only, no browser.
Run: python3 dev/run_tests.py test_theme_classic_1316_filter_pinned"""
import re
import unittest

from _paths import SRC

RULES = ((SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (SRC / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
START = "/* Row 1316d"

RULE_LINES = [
    '#usecases .fline { min-height: 34px; padding-top: 0; padding-bottom: 0; border: 1px solid var(--grey-500); border-radius: 6px; background: var(--surface); }',
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

    def test_it_follows_1316c_and_row_1314_stays_last(self):
        names = [l.split()[2].rstrip(":,") for l in RULES.split("\n") if l.startswith("/* Row ")]
        self.assertEqual(names[-1], "1314")
        self.assertEqual(names[names.index("1316d") - 1], "1316c")

    def test_no_other_rule_touches_the_usecases_filter(self):
        lines = RULES.split("\n")
        i = next(n for n, l in enumerate(lines) if l.startswith(START))
        j = next(n for n in range(i + 1, len(lines)) if lines[n].startswith("/* Row "))
        outside = [l for n, l in enumerate(lines) if not (i <= n < j) and not l.startswith("/*")]
        pat = re.compile(r"#usecases \.fline(?!-)|\.fline\.on|(^|[ ,])\.fx\b")
        allowed = {
            "#usecases .fline { padding-left: 34px; }",
            ".fline.bad, .fline.bad:focus-within { border-bottom-color: var(--status-red); box-shadow: 0 1px 0 var(--status-red); }",
        }
        hits = [l for l in outside if pat.search(l.split("{")[0]) and l not in allowed and not l.startswith("#usecases .fline::")]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()

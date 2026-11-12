"""Help text is clean on every changed path: no control characters or markup, balanced bold and key marks, and every link in shown help lands on a shown entry (item hm-help-1335).

Run: python3 dev/run_tests.py test_help_text_hostile
Quick tier: reads files, starts no browser.
"""
import re
import unittest

from _help_shown import shown_content


def strings(x, path=""):
    if isinstance(x, str):
        yield path, x
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from strings(v, f"{path}[{i}]")
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from strings(v, f"{path}.{k}")


SHOWN = shown_content()
ALL = list(strings(SHOWN))


class HelpTextIsClean(unittest.TestCase):
    def test_no_control_characters_or_markup(self):
        for p, s in ALL:
            self.assertIsNone(re.search(r"[\x00-\x08\x0b-\x1f\x7f​‮]", s), p)
            self.assertNotIn("<", s, p)
            self.assertNotIn("&lt;", s, p)

    def test_bold_and_key_marks_are_balanced(self):
        for p, s in ALL:
            self.assertEqual(s.count("**") % 2, 0, p + " " + s[:60])
            self.assertEqual(s.count("[["), s.count("]]"), p)
            self.assertNotIn("****", s, p)
            self.assertNotIn("**  **", s, p)

    def test_no_empty_bold_and_no_stray_straight_double_quotes(self):
        for p, s in ALL:
            self.assertNotIn("****", s, p)
            self.assertNotIn('\\"', s, p)

    def test_every_link_lands_on_a_shown_entry(self):
        ids = {x["id"] for x in SHOWN["reference"]["sections"]} | {x["id"] for x in SHOWN["howto"]["tasks"]}
        for p, s in ALL:
            for kind, target in re.findall(r"\]\(#(ref|how)-([\w-]+)\)", s):
                self.assertIn(target, ids, f"{p}: {kind}-{target}")


if __name__ == "__main__":
    unittest.main()

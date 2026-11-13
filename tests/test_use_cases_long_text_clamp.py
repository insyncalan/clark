"""Item 1131: the Use cases no-match message wraps, and long headlines and milestone lists stay two lines."""
import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")


def rule(selector):
    for m in re.finditer(r"^([^{}\n@][^{}]*)\{([^}]*)\}", CSS, re.M):
        if selector in [s.strip() for s in m.group(1).split(",")]:
            yield m.group(2)


class UseCasesLongTextClamp(unittest.TestCase):
    def test_no_match_message_wraps_anywhere(self):
        self.assertTrue(any("overflow-wrap: anywhere" in b for b in rule(".ucl-none")))

    def test_small_headline_and_milestones_clamp_to_two_lines(self):
        for sel in (".ucl-name small", ".ucl-head", ".ucl-ms"):
            bodies = list(rule(sel))
            body = " ".join(bodies)
            self.assertIn("-webkit-line-clamp: 2", body, sel)
            self.assertIn("overflow: hidden", body, sel)
            self.assertIn("-webkit-box-orient: vertical", body, sel)
            # .ucl-name small is hidden in its base rule; the 1100px rule (the last) is the one that shows it, and it must show it as a box
            self.assertIn("display: -webkit-box", bodies[-1] if sel == ".ucl-name small" else body, sel)


if __name__ == "__main__":
    unittest.main()

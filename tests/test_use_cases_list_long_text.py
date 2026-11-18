"""The Use cases list keeps long text inside the page: the no-match message wraps, and the headline stops at two lines."""
import re
import unittest

from _paths import SRC

CSS = (SRC / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")


def rule(selector):
    return " ".join(re.findall(r"(?m)^\s*" + re.escape(selector) + r" \{([^}]*)\}", CSS))


def narrow_block():
    """The text of the first @media (max-width: 900px) block that holds the .ucl rules, braces matched."""
    start = CSS.index("@media (max-width: 900px) {\n  .ucl-row")
    depth, k = 0, CSS.index("{", start)
    for end in range(k, len(CSS)):
        depth += {"{": 1, "}": -1}.get(CSS[end], 0)
        if depth == 0:
            return CSS[k + 1:end]
    raise AssertionError("unclosed @media block")


NARROW_RULES = {m.group(1).strip(): m.group(2) for m in re.finditer(r"([^{}]+)\{([^}]*)\}", narrow_block())}


class LongText(unittest.TestCase):
    def test_no_match_message_wraps(self):
        self.assertIn("overflow-wrap: anywhere", rule(".ucl-none"))

    def test_headline_clamps_to_two_lines_at_every_width(self):
        # item 1149: where it stands is shown in full on the row, clamped; the one rule is the base rule, so no width turns it off
        body = rule(".ucl-head")
        self.assertIn("-webkit-line-clamp: 2", body)
        self.assertIn("overflow: hidden", body)
        self.assertNotIn(".ucl-head", NARROW_RULES, "the narrow block keeps the headline on the row")

    def test_narrow_count_line_takes_its_own_row(self):
        body = NARROW_RULES[".ucl-count"]
        self.assertIn("margin-left: 0", body)
        self.assertIn("flex-basis: 100%", body)


if __name__ == "__main__":
    unittest.main()

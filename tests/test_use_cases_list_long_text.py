"""The Use cases list keeps long text inside the page: the no-match message wraps, and the headline and milestone cells stop at two lines."""
import re
import unittest

from _paths import SRC

CSS = (SRC / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")


def rule(selector):
    return " ".join(re.findall(r"(?m)^\s*" + re.escape(selector) + r" \{([^}]*)\}", CSS))


def narrow_block():
    """The text of the first @media (max-width: 1100px) block that holds the .ucl rules, braces matched."""
    start = CSS.index("@media (max-width: 1100px) {\n  .ucl-row")
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

    def test_headline_and_milestones_clamp_to_two_lines(self):
        body = rule(".ucl-head, .ucl-ms")
        self.assertIn("-webkit-line-clamp: 2", body)
        self.assertIn("overflow: hidden", body)

    def test_narrow_headline_small_clamps(self):
        # The clamp lives in the base rule; the narrow block must turn the line on as a box, or the clamp does nothing there.
        self.assertIn("-webkit-line-clamp: 2", rule(".ucl-name small"))
        self.assertIn("display: none", rule(".ucl-name small"))
        self.assertIn("display: -webkit-box", NARROW_RULES[".ucl-name small"])

    def test_narrow_count_line_takes_its_own_row(self):
        body = NARROW_RULES[".ucl-count"]
        self.assertIn("margin-left: 0", body)
        self.assertIn("flex-basis: 100%", body)


if __name__ == "__main__":
    unittest.main()

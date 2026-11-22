"""Theme Cards item 3 (plan item 1269), CSS only, read from src/clark/page/shell.css as plain rules.

Run: python3 dev/run_tests.py test_theme_cards_i3
Item 3: the sideways scroll bar of the board is hidden on .boardbox (the scroller), not on .board; the board still scrolls.
The bar is hidden at all times; showing it on hover is an open question.
"""
import re
import unittest

from _paths import ROOT

CSS = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def rules(selector_part):
    """Every (selector list, body) whose selector list holds a selector equal to selector_part, in file order."""
    out = []
    for m in re.finditer(r"([^{}/]+)\{([^{}]*)\}", CSS):
        sels = [s.strip() for s in m.group(1).split(",")]
        if selector_part in sels:
            out.append((m.start(), m.group(2)))
    return out


class BoardScrollBar(unittest.TestCase):
    def test_the_bar_is_hidden_on_boardbox_only(self):
        plain = [b for p, b in rules(".boardbox")]
        self.assertTrue(any(re.search(r"scrollbar-width:\s*none", b) for b in plain), "Firefox-style property on .boardbox")
        wk = rules(".boardbox::-webkit-scrollbar")
        self.assertTrue(wk and re.search(r"display:\s*none", wk[-1][1]), "WebKit pseudo-element on .boardbox")
        self.assertEqual(rules(".board::-webkit-scrollbar"), [], "no rule for .board::-webkit-scrollbar")
        for p, b in rules(".board"):
            self.assertNotIn("scrollbar", b, ".board")

    def test_boardbox_still_scrolls(self):
        base = next(b for p, b in rules(".boardbox") if "overflow" in b)
        self.assertRegex(base, r"overflow:\s*auto")


if __name__ == "__main__":
    unittest.main()

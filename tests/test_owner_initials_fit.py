"""#799: the owner initials (1 to 3 characters, wide letters, non-Latin) stay inside their small circle. The circle grows to a pill
rather than letting the letters spill: a minimum width, no fixed width, no wrapping, tight line height."""
import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", CSS, re.M)
    assert m, selector
    return m.group(1)


class InitialsFit(unittest.TestCase):
    def test_every_avatar_rule_grows_instead_of_fixing_its_width(self):
        for sel in (".av", ".cp-name .av", ".ucstepl .av", ".wl-meta .av"):
            body = rule(sel)
            self.assertNotRegex(body, r"(?<![-\w])width:", sel)
            self.assertIn("min-width:", body, sel)
        base = rule(".av")
        for need in ("white-space: nowrap", "line-height: 1", "box-sizing: border-box", "padding:"):
            self.assertIn(need, base)

    def test_the_risk_row_avatar_uses_a_size_that_the_scale_allows(self):
        self.assertIn("font-size: var(--size-caption)", rule(".wl-meta .av"))


if __name__ == "__main__":
    unittest.main()

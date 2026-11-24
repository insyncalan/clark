"""Row 1615: in the Work items footer (Edit and View, Classic) Show all items and Review all N items keep one line and their own width, and the count
text is the part that gives way. Static: it reads the theme's CSS text, no browser (the Chrome side is test_wil_footer_edit_1615.py).
Run: python3 -m unittest test_wil_footer_buttons_1615"""
import os
import re
import unittest
from pathlib import Path

CSS = Path(os.environ.get("CLARK_RULES_2_CSS") or Path(__file__).resolve().parent.parent / "src/clark/themes/prototype-2.0/rules-2.css")
BUTTONS = ".wil-foot .wil-all-b, .wil-foot .wil-review"
COUNT = ".wil-foot [data-wil-count]"
LAST = "/* Row 1314"


def body(selector):
    """The declarations of every rule whose selector list is exactly `selector`, joined (None when there is none)."""
    found = None
    for m in re.finditer(r"(?m)^([^{}/\n][^{}]*?)\s*\{([^{}]*)\}", CSS.read_text(encoding="utf-8")):
        if " ".join(m.group(1).split()) == selector:
            found = (found or "") + m.group(2)
    return found


def decls(selector):
    b = body(selector)
    return {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in (b or "").split(";") if ":" in d)}


class FooterButtons(unittest.TestCase):
    def test_the_two_buttons_do_not_wrap(self):
        """Mutant: in rules-2.css the rule `.wil-foot .wil-all-b, .wil-foot .wil-review` loses `white-space: nowrap;` (Review all N items wraps again)."""
        self.assertEqual(decls(BUTTONS).get("white-space"), "nowrap", body(BUTTONS))

    def test_the_two_buttons_do_not_shrink(self):
        """Mutant: the same rule has `flex: none;` changed to `flex: 0 1 auto;` (the foot squeezes the buttons instead of the count)."""
        self.assertEqual(decls(BUTTONS).get("flex"), "none", body(BUTTONS))

    def test_the_count_can_shrink_below_its_longest_word(self):
        """Mutant: the rule `.wil-foot [data-wil-count]` loses `min-width: 0;` (or is renamed `.wil-foot [data-wil-counts]`)."""
        self.assertEqual(decls(COUNT).get("min-width"), "0", body(COUNT))

    def test_the_new_rules_sit_before_the_last_row_block(self):
        """Mutant: the two rules are moved below the line `/* Row 1314 ...` (that block must stay the last row block)."""
        css = CSS.read_text(encoding="utf-8")
        self.assertEqual(css.count(LAST), 1)
        for sel in (BUTTONS, COUNT):
            at = [m.start() for m in re.finditer(r"(?m)^" + re.escape(sel) + r" \{", css)]
            self.assertTrue(at, sel)
            self.assertLess(max(at), css.index(LAST), sel)

    def test_the_rules_are_scoped_to_the_work_items_footer(self):
        """Mutant: the rule's selector loses its `.wil-foot ` prefix (`.wil-review { white-space: nowrap; flex: none; }` would reach any button of that class)."""
        css = CSS.read_text(encoding="utf-8")
        parts = [p.strip() for m in re.finditer(r"(?m)^([^{}/\n][^{}\n]*)\{", css) for p in m.group(1).split(",") if re.search(r"wil-all-b|wil-review|data-wil-count", p)]
        self.assertGreaterEqual(len(parts), 3, parts)
        for part in parts:
            self.assertTrue(part.startswith(".wil-foot "), part)


if __name__ == "__main__":
    unittest.main()

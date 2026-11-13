"""Print: the Work items table's fixed pixel column widths are reset to percentages under html.print-all, so Item keeps about half of an A4 page.
Static test, no browser. Run: python3 dev/run_tests.py test_print_items_widths"""
import re
import unittest

from _paths import SRC


class PrintItemsWidths(unittest.TestCase):
    def test_print_block_resets_the_fixed_widths_to_percent(self):
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        start = css.index("html.print-all, html.print-all body")
        block = css[start:css.index("\n}\n", start)]
        for col in ("c-owner", "c-due", "c-prio", "c-status"):
            m = re.search(r"html\.print-all table\.items \." + col + r"\b[^{]*\{[^}]*width:\s*(\d+)%", block)
            self.assertTrue(m, col + " has no percent width in print")
        self.assertLess(sum(int(x) for x in re.findall(r"width:\s*(\d+)%", re.search(r"html\.print-all table\.items \.c-owner[^{]*\{[^}]*\}", block).group(0))) * 4, 100)


if __name__ == "__main__":
    unittest.main()

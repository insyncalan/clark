"""Row 1273: Add milestone, Add project and Add use case take the dashed look of the Add opener on Work items, border style only.

Reads edit.css (no browser): a rule for the three openers sets a 1px dashed border, and sets nothing that moves the button
(no margin, padding, width, height or position), and the border colour is the blue text token. The look in a browser is not run here.
"""
import re
import unittest

from _paths import ROOT

EDIT = ROOT / "src" / "clark" / "page" / "src" / "edit"
CSS = (EDIT / "edit.css").read_text(encoding="utf-8")
IDS = ("addMs", "npBtn", "ucAddPage")


def body_for(opener_id):
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)):
        if f"#{opener_id}" in sel and "newb" in sel and ":hover" not in sel and ":focus" not in sel:
            return body
    return None


class AddOpenerDashed(unittest.TestCase):
    def test_each_opener_has_a_dashed_border(self):
        for i in IDS:
            body = body_for(i)
            self.assertIsNotNone(body, f"no rule for #{i}")
            self.assertRegex(body, r"border\s*:\s*1px\s+dashed\s+var\(--status-blue-text\)\s*;?\s*$", i)

    def test_the_rule_moves_nothing(self):
        for i in IDS:
            body = body_for(i) or ""
            for prop in ("margin", "padding", "width", "height", "position", "top", "left", "gap"):
                self.assertNotRegex(body, rf"(^|[;\s]){prop}\s*:", f"{i} sets {prop}")

    def test_the_openers_still_use_the_tile(self):
        for f, i in (("MsAdd.jsx", "addMs"), ("Projects.jsx", "npBtn"), ("UseCasesPage.jsx", "ucAddPage")):
            self.assertIn(f'id="{i}"', (EDIT / f).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

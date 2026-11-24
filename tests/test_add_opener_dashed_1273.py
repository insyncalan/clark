"""Row 1273: Add milestone, Add project and Add use case take the dashed look of the Add opener on Work items, border style only.

Reads edit.css (no browser): a rule for the three openers sets a 1px dashed border, and sets nothing that moves the button
(no margin, padding, width, height or position), and the border colour is the blue text token. The look of the Work items opener in Classic dark is read in a
browser by WorkItemsOpenerInDark (row 1462 AP5); the three openers above are not run in a browser here.
"""
import json
import re
import unittest

from _paths import ROOT

from test_server import chrome
import test_work_items_mockup_1195 as W

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


class WorkItemsOpenerInDark(W.Look):
    """Row 1462 AP5: the Add opener of a Work items list (computed style, Classic, dark) is the dashed 34px square."""

    def test_work_items_add_opener_is_the_dashed_34px_square_in_dark(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]})
        read = ("JSON.stringify((() => { const b = document.querySelector(" + json.dumps(f'[data-id="{ref}"] .wil-add .newb') + "), s = getComputedStyle(b), r = b.getBoundingClientRect();"
                " const col = v => { const i = document.createElement('i'); i.style.color = v; document.body.append(i); const c = getComputedStyle(i).color; i.remove(); return c; };"
                " return {style: s.borderTopStyle, bw: s.borderTopWidth, rad: s.borderTopLeftRadius, w: r.width, h: r.height, bd: s.borderTopColor, fg: s.color,"
                " bdWant: col('var(--grey-500)'), fgWant: col('var(--status-blue-text)'), theme: document.documentElement.dataset.theme}; })())")
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.show(cdp, width, dark=True)
                p.edit()
                p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-add .newb')", "the Add opener drew")
                p.until("document.getAnimations({subtree: true}).length === 0", "no transition is still running on the page")      # .newb has a colour transition: read its colour only once it has ended
                self.assertTrue(p.js("!!document.getElementById('theme')"), "the Classic theme is the one drawn")
                got = json.loads(p.js(read))
                self.assertEqual(got["theme"], "dark", width)
                self.assertEqual((got["style"], got["bw"], got["rad"]), ("dashed", "1px", "6px"), (width, got))
                self.assertEqual((got["w"], got["h"]), (34, 34), (width, got))
                self.assertEqual(got["bd"], got["bdWant"], (width, "border var(--grey-500)", got))
                self.assertEqual(got["fg"], got["fgWant"], (width, "colour var(--status-blue-text)", got))


if __name__ == "__main__":
    unittest.main()

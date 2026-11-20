"""Row 1273 (Classic): the Add menu of the all-kinds Work page (#newBtn) takes the prototype's look, measured in Chrome at 1400 and 900.

Run: python3 dev/run_tests.py test_add_menu_all_kinds_1273
The menu is 224px wide at least, its words are 15px, and every line holds an empty 16px tick slot (after the item's own 16px of padding), then the icon, then 10px to its words (the words start 26px after the icon's left edge). Group by and Move to share the 10px gap.
"""
import re
import unittest

from _paths import ROOT
from test_server import chrome
from test_work_items_classic_1314 import Browser as ClassicBrowser

RULES = re.sub(r"/\*.*?\*/", "", (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8"), flags=re.S)

MEASURE = r"""(() => {
 const box = document.querySelector('#newBtnMenu'); if (!box) return null;
 const br = box.getBoundingClientRect();
 const rows = [...box.querySelectorAll('[role=menuitem]')].map(b => {
   const icon = b.querySelector('svg.i'); const ir = icon && icon.getBoundingClientRect();
   let left = null; const w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT); let n;
   while ((n = w.nextNode())) { if (!n.textContent.trim() || n.parentElement.closest('svg')) continue; const r = document.createRange(); r.selectNodeContents(n); const x = r.getClientRects()[0]; if (x && x.width) { left = x.left; break; } }
   return {t: b.textContent.trim(), fs: getComputedStyle(b).fontSize, icon: !!icon, gap: icon && left !== null ? Math.round((left - ir.right) * 10) / 10 : null, slot: ir ? Math.round((ir.left - (b.getBoundingClientRect().left + 16)) * 10) / 10 : null, from_icon: ir && left !== null ? Math.round((left - ir.left) * 10) / 10 : null, inside: br.left >= 0 && br.right <= innerWidth};
 });
 return {w: Math.round(br.width), rows};
})()"""


class AddMenuAllKinds(ClassicBrowser):
    def test_the_add_menu_is_224_wide_15px_with_a_16px_slot_and_10px_from_icon_to_words(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                cdp.js("document.querySelector('#newBtn').click()", sid)
                self.until(cdp, sid, "document.querySelector('#newBtnMenu [role=menuitem]')", "the Add menu")
                got = cdp.js(MEASURE, sid)
                self.assertGreaterEqual(got["w"], 224, got)
                self.assertGreaterEqual(len(got["rows"]), 2, got)
                for r in got["rows"]:
                    self.assertEqual(r["fs"], "15px", r)
                    self.assertTrue(r["icon"], r)
                    self.assertAlmostEqual(r["gap"], 10, delta=0.5, msg=str(r))
                    self.assertAlmostEqual(r["slot"], 16, delta=0.5, msg=str(r))
                    self.assertAlmostEqual(r["from_icon"], 26, delta=0.5, msg=str(r))
                    self.assertTrue(r["inside"], r)


class Static(unittest.TestCase):
    def test_rule_names_the_all_kinds_add_menu(self):
        self.assertRegex(RULES, r"#newBtnMenu(\.ddmenu)?\s*[,{]")
        self.assertRegex(RULES, r"#newBtnMenu\.ddmenu \[role=\"menuitem\"\][^{]*\{[^}]*gap:\s*calc\(var\(--space-2\) \+ 2px\)")


if __name__ == "__main__":
    unittest.main()

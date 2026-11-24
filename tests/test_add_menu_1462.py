"""Row 1462: the Add menu of a Work items list in Classic draws a grey + icon and its words at x36, and the menu is 224px wide at least.

The static part reads the theme CSS (no browser). The browser part opens the Add menu of a Work items list at 1400 and 900, light and dark, with the Classic
theme layered, and reads computed values: the icon colour is the --text-muted colour and not the colour of the words, the icon is 16px, the words start 36px
from the line's left edge (padding 10 + icon 16 + gap 10, no reserved slot), the menu is 224px wide at least and its right edge is inside the window.
"""
import json
import re
import unittest

from _paths import ROOT

import test_work_items_mockup_1195 as W  # noqa: E402
import test_tpl_workitems as T  # noqa: E402
from clark import theme  # noqa: E402

NAME = "prototype-2.0"
MEASURE = r"""(() => {
 const ok = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
 const menus = [...document.querySelectorAll('.wil-add .ddmenu')].filter(ok); const box = menus[menus.length - 1]; if (!box) return null;
 const probe = document.createElement('i'); probe.style.color = 'var(--text-muted)'; document.body.append(probe); const muted = getComputedStyle(probe).color; probe.remove();
 const br = box.getBoundingClientRect();
 const rows = [...box.querySelectorAll('[role=menuitem]')].filter(ok).map(b => {
   const icon = b.querySelector('svg.i, .mi'); const ir = icon.getBoundingClientRect(); const lr = b.getBoundingClientRect();
   const w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT); let n, tx = null;
   while ((n = w.nextNode())) { if (!n.textContent.trim() || n.parentElement.closest('svg')) continue; const r = document.createRange(); r.selectNodeContents(n); const x = r.getClientRects()[0]; if (x && x.width) { tx = x.left - lr.left; break; } }
   return {t: b.textContent.trim(), icon: getComputedStyle(icon).color, word: getComputedStyle(b).color, iw: ir.width, il: ir.left - lr.left, tx};
 });
 return {muted, width: br.width, right: br.right, win: window.innerWidth, rows};
})()"""


class Static(unittest.TestCase):
    def test_the_classic_theme_greys_the_add_menu_icon(self):
        css = re.sub(r"/\*.*?\*/", "", theme.css(NAME), flags=re.S)
        hits = [b for s, b in re.findall(r"([^{}]+)\{([^{}]*)\}", css) if "newBtnMenu" in s and re.search(r"\.mi\s*$", s.strip()) and "color" in b]
        self.assertEqual(len(hits), 1)
        self.assertRegex(hits[0], r"(^|[;\s])color\s*:\s*var\(--text-muted\)\s*;?\s*$")
        self.assertIn("min-width: 224px", css)


class AddMenu(W.Look):
    LIST = {"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]}

    def read(self, width, dark):
        ref = self.add(self.LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, width, dark=dark)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} .wil-add .newb')", "the Add opener drew")
            p.js(f"document.querySelector('{sec} .wil-add .newb').click()")
            p.until("!!document.querySelector('.wil-add .ddmenu [role=menuitem]')", "the Add menu opened")
            p.until("(b => b.getAnimations({subtree: true}).every(a => a.playState === 'finished' || a.playState === 'idle'))([...document.querySelectorAll('.wil-add .ddmenu')].pop())", "the menu finished opening")
            got = json.loads(p.js(f"JSON.stringify({MEASURE})"))
        self.assertTrue(got and got["rows"], (width, dark))
        return got

    def test_add_menu_icon_is_text_muted_grey(self):
        for width in (1400, 900):
            for dark in (False, True):
                where = (width, "dark" if dark else "light")
                got = self.read(width, dark)
                for r in got["rows"]:
                    self.assertEqual(r["icon"], got["muted"], (where, r["t"], "the + icon is the --text-muted colour"))
                    self.assertNotEqual(r["icon"], r["word"], (where, r["t"], "the icon is not the colour of the words"))
                    self.assertEqual(r["iw"], 16, (where, r["t"]))

    def test_add_menu_words_start_at_x36_and_menu_min_width_224(self):
        for width in (1400, 900):
            for dark in (False, True):
                where = (width, "dark" if dark else "light")
                got = self.read(width, dark)
                self.assertGreaterEqual(got["width"], 224, where)
                self.assertLessEqual(got["right"], got["win"], (where, "the menu stays inside the window"))
                for r in got["rows"]:
                    self.assertAlmostEqual(r["il"], 10, delta=0.5, msg=(where, r["t"], "no reserved slot before the icon"))
                    self.assertAlmostEqual(r["tx"], 36, delta=0.5, msg=(where, r["t"], "the words start at x36"))


if __name__ == "__main__":
    unittest.main()

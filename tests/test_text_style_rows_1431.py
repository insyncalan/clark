"""Row 1431: the Classic Text style menu rows are 32px high as the prototype draws them (index.html:295), the rest of the menu stays as it is.

Run: python3 dev/run_tests.py test_text_style_rows_1431.py
Classic only. Cards is proved unchanged without a browser: no Cards style block holds a Row 1431 rule.
"""
import json
import re
import unittest
from unittest import mock

from _paths import ROOT

import _rich_page as rp  # noqa: E402
import build_page  # noqa: E402
import test_menu_icons_every_1138 as T  # noqa: E402
from clark import page, theme  # noqa: E402
from test_server import chrome  # noqa: E402,F401  (the runner tells a browser file by this import)

NAME = "prototype-2.0"
RULES = (ROOT / "src" / "clark" / "themes" / NAME / "rules-2.css").read_text(encoding="utf-8")
OPT = ".rt-bar [role=menu] [role=menuitemradio]"
READ = r"""(() => { const m = [...document.querySelectorAll('.rt-bar [role=menu]')].pop(); if (!m) return null;
 const o = [...m.querySelectorAll('[role=menuitemradio]')]; const c = e => getComputedStyle(e);
 return {w: Math.round(m.getBoundingClientRect().width), rows: o.map(e => ({t: e.textContent.trim(), h: Math.round(e.getBoundingClientRect().height * 10) / 10, fs: c(e).fontSize, pl: c(e).paddingLeft, pr: c(e).paddingRight, icon: !!e.querySelector('svg'), on: e.getAttribute('aria-checked') || e.getAttribute('aria-current') || e.className}))}; })()"""
LOOKS = [(1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")]
_patch = None


def setUpModule():
    global _patch
    css = theme.css(NAME)
    orig = build_page.page_css
    _patch = mock.patch.object(build_page, "page_css", lambda *a, **k: orig(*a, **k) + "\n" + css)
    _patch.start()
    unittest.addModuleCleanup(_patch.stop)


def open_menu(test, h, d):
    h.mount("<p>Title</p>")
    d.button(".rt-bar .rt-style", "the Text style button")
    d.js("document.querySelector('.rt-bar .rt-style').click()")
    d.until("document.querySelector('.rt-bar [role=menu]')", "the menu is on the page")
    d.until(f"document.querySelectorAll({json.dumps(OPT)}).length >= 4", "the Text style menu drew its four lines")
    d.until(f"(() => {{ const b = [...document.querySelectorAll('.rt-bar [role=menu]')].pop(); return b.getAnimations({{subtree: true}}).every(a => a.playState === 'finished' || a.playState === 'idle'); }})()", "the menu finished opening")
    return d.js(READ)


class Rows(unittest.TestCase):
    def read_all(self):
        out = {}
        with rp.Harness(chrome) as h:
            d = T.Drive(self, h.cdp, h.sid)
            for w, th in LOOKS:
                d.look(w, th)
                out[(w, th)] = open_menu(self, h, d)
                d.key("Escape", "Escape", 27)
                d.gone(".rt-bar [role=menu]", "the style menu")
                h.ev("window.unmount(); true")
        return out

    def test_classic_text_style_rows_are_32px_at_1400_and_900(self):
        for look, m in self.read_all().items():
            self.assertEqual(len(m["rows"]), 4, look)
            for r in m["rows"]:
                self.assertEqual(r["h"], 32, f"{look}: the row {r['t']!r} is {r['h']}px high, the prototype draws 32")

    def test_text_style_menu_keeps_its_items_word_text_and_tick(self):
        for look, m in self.read_all().items():
            self.assertEqual([r["t"].lstrip("\u2713") for r in m["rows"]], ["Text", "Heading 1", "Heading 2", "Heading 3"], look)
            for r in m["rows"]:
                self.assertEqual((r["fs"], r["pl"], r["pr"], r["icon"]), ("14px", "16px", "16px", True), f"{look}: {r['t']!r} keeps its size, side padding and icon")
            self.assertGreaterEqual(m["w"], 150, look)

    def test_cards_page_has_no_row_1431_rule(self):
        self.assertIn("Row 1431", RULES)
        for block in re.findall(r"<style[^>]*>(.*?)</style>", page.page_html(branding=page.NO_BRAND, theme=None), re.S):
            self.assertNotIn("Row 1431", block)
            self.assertNotIn(OPT, block)

    def test_other_menus_keep_their_row_height(self):
        css = re.sub(r"/\*.*?\*/", "", RULES, flags=re.S)
        found = 0
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if "menuitemradio" in sel:
                # The View menu's Group by (#viewMenuList) is a different menu with its own row rule (Row 1273); only text-style menu rules are checked here.
                if "#viewMenuList" in sel and ".rt-bar" not in sel:
                    continue
                found += 1
                self.assertIn(".rt-bar .ddmenu", sel, f"a menu row rule names more than the Text style menu: {sel.strip()[:90]}")
                self.assertNotRegex(sel, r"\.menu-item|\.rt-slash|\.gt-")
        self.assertGreaterEqual(found, 1)


if __name__ == "__main__":
    unittest.main()

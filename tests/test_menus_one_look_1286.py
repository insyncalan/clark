"""Row 1286 (impeccable audit B-M2 and B-M3): every menu of the Classic look is on one grid and draws what the approved mock-up menus draw.

Run: python3 dev/run_tests.py test_menus_one_look_1286
Classic only. Cards is proved unchanged without a browser: its page is byte for byte the page of main, and no Cards style block holds a Row 1286 rule.
The browser part opens every menu of tests/test_menu_icons_every_1138.py (the dashboard, the Work items page and board, the Use cases pages, the row and
bulk menus, the Gantt menus, the rich text style menu) at 1400 and 900, light and dark, with the Classic theme layered, and reads each open menu:
  - the grid: every icon 17px in from the panel edge (+/-1) and 8px (+/-0.5) from the next thing drawn on its line (its words, or the tick of a
    menu whose tick is on the left); the same for the pick menus, the row menus, the section menu, the bulk menu, the Gantt menus
  - the type: 14px on every line (the Classic body size)
  - the tick of the line in use is on the right of the words, except in the three menus whose mock-ups draw it on the left (Columns, the Gantt Show menus)
  - the head of a group is plain: no capitals, no letter spacing
  - the width: no menu narrower than 200px, the Group by menus 240px at least
Words and icons are not read here (test_menu_icons_every_1138 does that); nothing here changes a word.
"""
import json
import os
import re
import unittest
from unittest import mock

from _paths import ROOT

import _testpage  # noqa: E402
import test_gantt_page as GP  # noqa: E402
import test_menu_icons_every_1138 as T  # noqa: E402
import build_page  # noqa: E402
from clark import page, theme  # noqa: E402
from test_server import chrome  # noqa: E402,F401  (the runner tells a browser file by this import)

NAME = "prototype-2.0"
RULES = (ROOT / "src" / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8")
TICK_LEFT = {"columns", "gantt-show-chart", "gantt-show-table"}          # their mock-ups draw the tick before the word (1195 Columns, 1197 Show)
NO_ICON_GRID = {"owner-pick", "owner-pick-typed", "health", "report-headline-health"}    # an initials circle or a coloured pill, not an icon
GROUP_BY = {"uc-group"}
MIN_W, GROUP_W = 200, 240
PROTOTYPE_THREE = {"view", "board-move", "board-move-lanes", "new-tile"}       # row 1273: Group by (the View menu's), Move to and the Add menu: 15px, 224 wide, 26px icon gap, the tick before the icon
THREE_W, THREE_FS, THREE_GAP = 224, "15px", 26

MEASURE = r"""(root => {
 const ok = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
 const boxes = [...document.querySelectorAll(root)].filter(ok); const box = boxes[boxes.length - 1]; if (!box) return null;
 const cs = e => getComputedStyle(e); const br = box.getBoundingClientRect();
 const items = [...new Set(box.querySelectorAll('[role=menuitem],[role=menuitemcheckbox],[role=menuitemradio],[role=option],.menu-item,.cm-row,.cp-name,.cp-q button'))].filter(ok);
 const rows = items.map(b => {
   const icon = [...b.querySelectorAll('svg.i')].find(s => !s.closest('.ck') && ok(s)); if (!icon) return {t: b.textContent.trim().slice(0, 22), fs: cs(b).fontSize, icon: false};
   const ir = icon.getBoundingClientRect(); const after = [], before = [ir.left];
   for (const d of b.querySelectorAll('.ragdot')) { const dr = d.getBoundingClientRect(); if (dr.width && dr.left >= ir.right - 0.5) after.push(dr.left); }   // the status dot of a word row is the next thing drawn
   const w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT); let n;
   while ((n = w.nextNode())) { if (!n.textContent.trim() || n.parentElement.closest('svg')) continue; const r = document.createRange(); r.selectNodeContents(n); const x = r.getClientRects()[0]; if (!x || !x.width) continue; if (x.left >= ir.right - 0.5) after.push(x.left); else if (x.right <= ir.left + 0.5) before.push(x.left); }
   const ck = b.querySelector('.ck, .gt-ck'); const ckr = ck ? ck.getBoundingClientRect() : null;
   if (ckr && ckr.width > 0) { if (ckr.left >= ir.right - 0.5) after.push(ckr.left); else if (ckr.right <= ir.left + 0.5) before.push(ckr.left); }
   const dot = b.querySelector('.ragdot'); if (dot) { const d = dot.getBoundingClientRect(); if (d.width > 0 && d.left >= ir.right - 0.5) after.push(d.left); }      // the coloured dot of a status word is drawn before the word
   const checked = b.getAttribute('aria-checked') === 'true' || b.getAttribute('aria-current') === 'true';
   const side = !checked ? null : (ck && ck.textContent.trim() && ckr) ? (ckr.left + ckr.width / 2 > br.left + br.width / 2 ? 'right' : 'left') : (getComputedStyle(b, '::after').content.length > 4 ? 'right' : null);
   return {t: b.textContent.trim().slice(0, 22), fs: cs(b).fontSize, icon: true, il: Math.round((Math.min(...before) - br.left) * 10) / 10, gap: after.length ? Math.round((Math.min(...after) - ir.right) * 10) / 10 : null, side};
 });
 const heads = [...box.querySelectorAll('.lab,.mh,.menu-head')].filter(ok).map(h => ({t: h.textContent.trim().slice(0, 24), tt: cs(h).textTransform, ls: cs(h).letterSpacing}));
 return {w: Math.round(br.width), rows, heads}; })"""


def check(test, name, look, m):
    where = f"{name} at {look[0]} {look[1]}"
    test.assertTrue(m, where)
    three = name in PROTOTYPE_THREE
    test.assertGreaterEqual(m["w"], THREE_W if three else GROUP_W if name in GROUP_BY else MIN_W, f"{where}: the menu is {m['w']}px wide")
    for r in m["rows"]:
        test.assertEqual(r["fs"], THREE_FS if three else "14px", f"{where}: the line {r['t']!r} is not {THREE_FS if three else '14px'}")
        if r["icon"] and three:
            test.assertAlmostEqual(r["gap"], THREE_GAP, delta=0.5, msg=f"{where}: {r['t']!r} has {r['gap']}px between its icon and its words, row 1273 draws {THREE_GAP}")
        elif r["icon"] and name not in NO_ICON_GRID:
            test.assertIsNotNone(r["gap"], f"{where}: {r['t']!r} has nothing after its icon")
            test.assertAlmostEqual(r["il"], 17, delta=1, msg=f"{where}: the icon of {r['t']!r} is {r['il']}px in from the edge, the grid is 17")
            test.assertAlmostEqual(r["gap"], 8, delta=0.5, msg=f"{where}: {r['t']!r} has {r['gap']}px between its icon and the next thing, the grid is 8")
        if r.get("side"):
            test.assertEqual(r["side"], "left" if name in TICK_LEFT or three else "right", f"{where}: the tick of {r['t']!r}")
    for h in m["heads"]:
        test.assertEqual(h["tt"], "uppercase" if name.startswith("board-move") else "none", f"{where}: the head {h['t']!r} is in the wrong case")
        if not name.startswith("board-move"):
            test.assertIn(h["ls"], ("normal", "0px"), f"{where}: the head {h['t']!r} is letter-spaced")


class Seen:
    """Records and checks every menu a Drive reads."""
    names = set()


def setUpModule():
    css = theme.css(NAME)
    patches = []

    def start(p):
        p.start()
        patches.append(p)
    orig_html, orig_gp, orig_css, orig_lines = _testpage.html, GP.page_html, build_page.page_css, T.Drive.lines
    start(mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(orig_html(branding), css)))
    start(mock.patch.object(GP, "page_html", lambda: (lambda h: h.replace("</head>", f'<style id="theme">{css}</style></head>', 1) if "</head>" in h else h + f'<style id="theme">{css}</style>')(orig_gp())))
    start(mock.patch.object(build_page, "page_css", lambda *a, **k: orig_css(*a, **k) + "\n" + css))

    def lines(self, root, name, minimum):
        got = orig_lines(self, root, name, minimum)
        check(self.t, name, self.look_is, self.js(f"({MEASURE})({json.dumps(root)})"))
        Seen.names.add(name)
        return got
    start(mock.patch.object(T.Drive, "lines", lines))
    for p in patches:
        unittest.addModuleCleanup(p.stop)


class Static(unittest.TestCase):
    def test_the_rules_are_in_the_classic_theme_only(self):
        self.assertIn("Row 1286", RULES)
        cards = page.page_html(branding=page.NO_BRAND, theme=None)
        self.assertNotIn("Row 1286", cards, "Cards holds no Row 1286 rule")
        self.assertIn(".ddmenu .mi { margin-right: var(--space-2); }", page.page_html(branding=page.NO_BRAND, theme=NAME))

    def test_no_style_block_of_cards_names_the_row(self):
        for block in re.findall(r"<style[^>]*>(.*?)</style>", page.page_html(branding=page.NO_BRAND, theme=None), re.S):
            self.assertNotIn("Row 1286", block)


class Dashboard(T.Dashboard):
    test_report_headline_health_menu = test_glance_template_add_a_tile_menu = test_the_section_menu_gives_each_line_its_icon_and_keeps_its_words = None
    test_the_profile_menu_gives_each_command_its_icon = None


class Work(T.Work):
    test_peek_more_menu_icons_and_duplicate_matches_the_row_menu = test_bulk_menu_with_lines_it_cannot_offer = None


class Gantt(T.Gantt):
    pass


class Rich(T.Rich):
    test_slash_list_gives_every_block_its_icon = None



if __name__ == "__main__":
    unittest.main()

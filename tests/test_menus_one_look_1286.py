"""Row 1286 (impeccable audit B-M2 and B-M3): every menu of the Classic look is on one grid and draws what the approved mock-up menus draw.

Run: python3 dev/run_tests.py test_menus_one_look_1286
Classic only. Cards is proved unchanged without a browser: its page is byte for byte the page of main, and no Cards style block holds a Row 1286 rule.
The browser part opens every menu of tests/test_menu_icons_every_1138.py (the dashboard, the Work items page and board, the Use cases pages, the row and
bulk menus, the Gantt menus, the rich text style menu) at 1400 and 900, light and dark, with the Classic theme layered, and reads each open menu:
  - Group by (the View menu), Add and Move to (ruling 17-11, the prototype's values): lines 15px, padding 7px 10px, radius 6px, the icon 16px wide,
    17px in from the panel edge and 10px (an 8px gap and a 2px icon margin) from its words; the popup 224px at least, radius 10px, padding 6px
  - every other menu keeps production: lines 14px, not the prototype's padding and radius, the icon 17px in from the edge and 8px from its words
    (the date and owner pickers are forms, not menus, and are left out)
  - the tick of the line in use is on the right of the words, except in the three menus whose mock-ups draw it on the left (Columns, the Gantt Show menus)
  - the head of a group is plain: no capitals, no letter spacing, except the two heads Row 1273 draws in capitals (the Group by head of the View menu and the Move <id> to head of a card)
  - the panel radius: 10px on every menu, as the prototype .pop (Row menu-radius), except the Gantt Show panel .gt-pop: 12px (1197 item 10)
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
TIGHT = {"text-style"}      # row 1288: the rich editor's menus are the tight ones (radius 12, padding 4, rows 4px 10px at 13.5px; test_rich_menus_tight_1288)
GANTT_SHOW = {"gantt-show-chart"}     # the Gantt Show panel (.gt-pop under [data-gantt]): radius 12 by the measured mock-up of 1197 item 10 (comment 7022907667), by ruling; it wins over 1286's general 10px. The Work items table Show menu (gantt-show-table) is a .gt-pop outside [data-gantt], draws 10 and stays 10 here
MIN_W = 224
COLUMNS_7B = {"columns"}      # row 1499 (pick 7B, mock-up work-items-mockup.html:2011): the Classic Columns menu is the mock-up's own panel (200 wide, radius 12, padding 6); only its panel radius differs from the 1286 grid
THREE = {"view", "new-tile", "board-move", "board-move-lanes"}     # Group by (the View menu), Add, Move to: the prototype's values (ruling 17-11)
PICKERS = {"owner-pick", "owner-pick-typed", "bulk-picker-owner", "bulk-picker-due", "cell-Due date"}     # forms with their own look, not menus of lines
PILL_MENU = {"health", "report-headline-health"}

MEASURE = r"""(root => {
 const ok = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
 const boxes = [...document.querySelectorAll(root)].filter(ok); const box = boxes[boxes.length - 1]; if (!box) return null;
 const cs = e => getComputedStyle(e); const br = box.getBoundingClientRect();
 const items = [...new Set(box.querySelectorAll('[role=menuitem],[role=menuitemcheckbox],[role=menuitemradio],[role=option],.menu-item,.cm-row,.cp-name,.cp-q button'))].filter(b => ok(b) && !b.closest('.ptrack'));   // the Appearance pills (Row 1281) are one pill line, not menu lines; test_profile_menu_classic_1281 pins their look
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
   const c = cs(b);
   return {t: b.textContent.trim().slice(0, 22), fs: c.fontSize, pad: c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft, rad: c.borderTopLeftRadius, iw: Math.round(ir.width * 10) / 10, icon: true, ibl: Math.round((ir.left - b.getBoundingClientRect().left) * 10) / 10, tx: after.length ? Math.round((Math.min(...after) - b.getBoundingClientRect().left) * 10) / 10 : null, ckl: ckr && ckr.width > 0 ? Math.round((ckr.left - b.getBoundingClientRect().left) * 10) / 10 : null, il: Math.round((Math.min(...before) - br.left) * 10) / 10, slot: Math.round((ir.left - (b.getBoundingClientRect().left + parseFloat(c.paddingLeft))) * 10) / 10, gap: after.length ? Math.round((Math.min(...after) - ir.right) * 10) / 10 : null, side};
 });
 const heads = [...box.querySelectorAll('.lab,.mh,.menu-head')].filter(ok).map(h => ({t: h.textContent.trim().slice(0, 24), tt: cs(h).textTransform, ls: cs(h).letterSpacing}));
 const bc = cs(box);
 return {w: Math.round(br.width), cls: box.className, rad: bc.borderTopLeftRadius, pad: bc.paddingTop + ' ' + bc.paddingRight + ' ' + bc.paddingBottom + ' ' + bc.paddingLeft, bord: bc.borderTopWidth + ' ' + bc.borderTopStyle + ' ' + bc.borderTopColor, line: cs(document.documentElement).getPropertyValue('--line').trim(), rows, heads}; })"""


def check(test, name, look, m):
    where = f"{name} at {look[0]} {look[1]}"
    test.assertTrue(m, where)
    three = name in THREE
    r1273 = name in {"view", "board-move", "board-move-lanes"}     # row 1273 changes Group by and Move to only; the Add menu is row 1462
    want = "12px" if name in TIGHT or name in GANTT_SHOW or name in COLUMNS_7B else "10px"      # 1197 item 10: the Gantt Show panel keeps 12; row 1499 AP5: the Classic Columns panel is 12 (the 7B mock-up .ctxm); every other popover is 10
    test.assertEqual(m["rad"], want, f"{where}: the panel radius is {m['rad']}, expected {want} (the prototype popover (.pop) draws 10px, the Gantt Show panel 12px by 1197 item 10)")
    if three:
        test.assertGreaterEqual(m["w"], MIN_W, f"{where}: the menu is {m['w']}px wide")
        test.assertEqual(m["pad"], "6px 6px 6px 6px", f"{where}: the popup padding")
    for r in m["rows"]:
        if name in PICKERS or name in PILL_MENU:
            continue
        own = {"Heading 1": "20px", "Heading 2": "18px", "Heading 3": "16px"}.get(r["t"].lstrip("\u2713"), "15px") if name == "text-style" else None      # row 1288 AP3: the Style menu draws each line at its own size (Text 15px)
        test.assertEqual(r["fs"], own or ("15px" if three else "13.5px" if name in TIGHT else "14px"), f"{where}: the line {r['t']!r} is {r['fs']}, the {'prototype' if three else 'production'} size is {'15' if three else '14'}px")
        if not three and name != "text-style" and "pad" in r:      # the Style menu has the prototype rows (row 1288 AP3); row 1499: a line with no icon is measured for its size only
            test.assertNotEqual((r["pad"], r["rad"]), ("7px 10px 7px 10px", "6px"), f"{where}: the line {r['t']!r} has the prototype padding and radius, only Group by, Add and Move to have it")
        if r["icon"] and name not in NO_ICON_GRID:
            test.assertIsNotNone(r["gap"], f"{where}: {r['t']!r} has nothing after its icon")
            if r1273:
                test.assertEqual((r["pad"].split()[:3], r["rad"]), (["7px", "10px", "7px"], "6px"), f"{where}: the line {r['t']!r} padding (top, right, bottom) and radius")
                test.assertEqual(r["pad"].split()[3], "10px", f"{where}: the line {r['t']!r} has {r['pad'].split()[3]} of left padding, the prototype draws 7px 10px")
                test.assertEqual(r["iw"], 16, f"{where}: the icon of {r['t']!r} is {r['iw']}px wide")
                test.assertAlmostEqual(r["gap"], 10, delta=0.5, msg=f"{where}: {r['t']!r} has {r['gap']}px between its icon and the next thing, row 1273 draws 10")
                # 7px 10px padding, [16px icon][10px gap][text]: icon at x10, text at x36 from the item's left edge; the mock's x60 includes a tick slot that ruling 9A (tick right of the word) removes
                test.assertAlmostEqual(r["slot"], 0, delta=0.5, msg=f"{where}: {r['t']!r} has {r['slot']}px before its icon, 9A reserves no tick slot")
                test.assertAlmostEqual(r["ibl"], 10, delta=0.5, msg=f"{where}: the icon of {r['t']!r} is {r['ibl']}px from the item's left edge, the padding")
                test.assertAlmostEqual(r["tx"], 36, delta=0.5, msg=f"{where}: {r['t']!r} text starts {r['tx']}px from the item's left edge, 10 + 16 + 10")
            elif three:
                test.assertAlmostEqual(r["il"], 17, delta=1, msg=f"{where}: the icon of {r['t']!r} is {r['il']}px in from the edge, the grid is 17")
                test.assertEqual((r["pad"], r["rad"]), ("7px 10px 7px 10px", "6px"), f"{where}: the line {r['t']!r} padding and radius")
                test.assertEqual(r["iw"], 16, f"{where}: the icon of {r['t']!r} is {r['iw']}px wide")
                test.assertAlmostEqual(r["gap"], 10, delta=0.5, msg=f"{where}: {r['t']!r} has {r['gap']}px between its icon and the next thing, the grid is 10")
            else:
                test.assertAlmostEqual(r["il"], 15 if name in TIGHT else 17, delta=1, msg=f"{where}: the icon of {r['t']!r} is {r['il']}px in from the edge, the grid is 17")
                grid = 10 if name == "gantt-show-chart" else 8      # row 1197 item 10: the chart Show menu rows gap 10
                test.assertAlmostEqual(r["gap"], grid, delta=0.5, msg=f"{where}: {r['t']!r} has {r['gap']}px between its icon and the next thing, production's grid is {grid}")
        if r.get("side"):
            test.assertEqual(r["side"], "left" if name in TICK_LEFT else "right", f"{where}: the tick of {r['t']!r}")
    for h in m["heads"]:
        caps = (name == "view" and h["t"] == "Group by") or (name.startswith("board-move") and re.fullmatch(r"Move \S+ to", h["t"]) is not None)    # row 1273: only these two heads
        test.assertEqual(h["tt"], "uppercase" if caps else "none", f"{where}: the head {h['t']!r} is in the wrong case")
        if not caps:
            test.assertIn(h["ls"], ("normal", "0px"), f"{where}: the head {h['t']!r} is letter-spaced")


class Seen:
    """Records and checks every menu a Drive reads."""
    names = set()
    leaving = None
    live = None


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
        # Row 1463: read the menu only once its open animation has ended (a rise or slide moves the icon a pixel or two while it runs)
        self.until(f"(r => {{ const b = [...document.querySelectorAll(r)].filter(e => e.getBoundingClientRect().width > 0).pop(); return !!b && b.getAnimations({{subtree: true}}).every(a => a.playState === 'finished' || a.playState === 'idle'); }})({json.dumps(root)})", f"{name}: the menu {root} finished opening")
        check(self.t, name, self.look_is, self.js(f"({MEASURE})({json.dumps(root)})"))
        if name == "gantt-add-below-table" and self.look_is[0] == 1400 and Seen.live is None:     # row 1286 (PR 2092), 1400 only: the fade copy's line padding equals the live Gantt menu's (12px at the sides)
            read = "(b => { const c = getComputedStyle(b); return c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft; })"
            Seen.live = self.js(f"(r => {read}([...document.querySelectorAll(r)].filter(e => e.getBoundingClientRect().width > 0).pop().querySelector('button')))({json.dumps(root)})")
            copy = self.js(f"(() => {{ const d = document.createElement('div'); d.className = 'gt-menu leaving'; d.innerHTML = '<button>x</button>'; document.body.append(d); const r = {read}(d.firstChild); d.remove(); return r; }})()")
            self.t.assertEqual(copy, Seen.live, "the fade copy's line padding equals the live menu's")
            self.t.assertEqual(Seen.live, "6px 12px 6px 12px", "the live Gantt menu keeps 12px at the sides")
        if not Seen.leaving:     # row 1463: the fade copy of a Gantt menu (body > .gt-menu.leaving, edit.css) keeps the box padding and the line padding: read its computed values from a copy on the page
            Seen.leaving = self.js("(() => { const d = document.createElement('div'); d.className = 'gt-menu leaving'; d.innerHTML = '<button>x</button>'; document.body.append(d); const b = d.firstChild, p = e => { const c = getComputedStyle(e); return c.paddingTop + ' ' + c.paddingRight + ' ' + c.paddingBottom + ' ' + c.paddingLeft; }; const r = [p(d), p(b)]; d.remove(); return r; })()")
            self.t.assertEqual(Seen.leaving[0], "4px 4px 4px 4px", "the fading Gantt menu: box padding")
            self.t.assertEqual(Seen.leaving[1], "6px 12px 6px 12px", "the fading Gantt menu: line padding is 12px at the sides (Row 1286)")
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
        classic = page.page_html(branding=page.NO_BRAND, theme=NAME)
        scope = '#viewMenuList, #newBtnMenu, .ddmenu[aria-label^="Add "], .ddmenu[aria-label^="Move "][aria-label$=" to"]'
        self.assertIn(scope + " { min-width: 224px; padding: 6px; border-radius: 10px; }", classic)

    def test_the_15px_and_224_menu_rules_name_only_the_three_menus(self):
        css = re.sub(r"/\*.*?\*/", "", RULES, flags=re.S)
        found = 0
        for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if re.search(r"menu|ddmenu|\.gt-|\.mi\b|\.cpop", sel) and re.search(r"font-size: 15px|min-width: 224px|[^-]width: 224px|padding: 7px 10px", body):
                found += 1
                self.assertRegex(sel, r"#viewMenuList|#newBtnMenu|aria-label\^=", f"a 15px, 224px or 7px 10px menu rule names a menu other than the three: {sel.strip()[:90]}")
        self.assertGreaterEqual(found, 2)

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

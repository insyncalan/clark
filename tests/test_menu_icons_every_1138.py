"""Row 1138 (extends 1074): every drop-down menu shows an icon beside each line's words, the same icon for the same action.

Run: python3 dev/run_tests.py test_menu_icons_every_1138
Part 1 reads the shared map (page/src/menuIcons.js ACTION_ICON) in node. Part 2 reads the source: each menu takes its icons from the
map. Part 3 drives the real page (the harness of tests/test_report_editor.py) in headless Chrome at 1400 and 900: the section menu and
the profile menu, with the words as they were.
"""
import json
import re
import shutil
import subprocess
import time
import unittest

from _paths import ROOT

from test_report_editor import Base, IDS  # noqa: E402
from test_server import chrome  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
WIDTHS = (1400, 900)


def run_js(body):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    code = f'import * as M from "{(SRC / "menuIcons.js").as_uri()}"; {body}'
    done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


class Map(unittest.TestCase):
    def test_every_icon_in_the_map_is_in_the_existing_set(self):
        icons = (SRC / "components" / "Icon.jsx").read_text(encoding="utf-8")
        for action, name in run_js("console.log(JSON.stringify(M.ACTION_ICON))").items():
            self.assertRegex(icons, rf'(?m)^\s*"?{re.escape(name)}"?:', action)

    def test_move_up_and_move_down_differ_and_delete_is_the_bin(self):
        m = run_js("console.log(JSON.stringify(M.ACTION_ICON))")
        self.assertNotEqual(m["up"], m["down"])
        self.assertEqual(m["delete"], "trash")
        self.assertEqual(m["exportExcel"], m["exportWord"])
        self.assertEqual(m["exportExcel"], m["excel"], "Export to Excel and the client menu's Excel are the same action")
        self.assertNotEqual(m["add"], m["duplicate"], "Add and Duplicate are told apart")
        self.assertNotEqual(m["show"], m["preview"], "Show and Preview are told apart")
        self.assertEqual(m["copyId"], m["copyIds"], "Copy ID and Copy IDs are the same action")
        self.assertEqual(len({m["lookLight"], m["lookDark"], m["lookSystem"]}), 3, "the three looks have three icons")
        self.assertEqual(run_js("console.log(JSON.stringify(M.actionIcon('nonsense') ?? null))"), None)


class Source(unittest.TestCase):
    # Every file that draws a drop-down menu, and so must take its icons from the map. A new file with a menu that is in neither list fails.
    MENUS = ("edit/Gutter.jsx", "edit/ProfileMenu.jsx", "edit/RowMenu.jsx", "components/ClientMenu.jsx", "gantt/components/GanttTable.jsx",
             "gantt/components/GanttChart.jsx", "gantt/components/GanttPage.jsx", "edit/Bulk.jsx", "edit/Board.jsx", "edit/GlanceEdit.jsx",
             "edit/ProjectSwitch.jsx", "components/FilterLine.jsx", "components/WorkItems.jsx", "components/NewTile.jsx", "edit/UseCasesPage.jsx",
             "components/UseCasesTab.jsx", "edit/UseCasesEdit.jsx", "components/UseCaseDetail.jsx", "edit/CommitMenu.jsx", "edit/RichText.jsx",
             "edit/cells/OwnerPick.jsx")
    # Menus that already drew an icon on every line through their own choices (row 1074), checked by test_menu_icons_mutproof_1074, or that are
    # not drop-down menus of commands: the search suggestions and the command palette are lists of what was typed.
    OTHER = ("edit/cells/MenuPick.jsx", "edit/cells/RatingPick.jsx", "edit/cells/StatusPick.jsx", "edit/cells/PriorityPick.jsx", "edit/PeekPick.jsx",
             "edit/MilestonePeek.jsx", "components/Menu.jsx", "edit/Palette.jsx", "edit/ArchivedPeek.jsx", "edit/PeekActivity.jsx", "edit/ArchivedItems.jsx",
             "components/UseCases.jsx", "components/Peek.jsx")
    DRAWS = re.compile(r'<Menu\b|<MenuPanel|role="menu"|role="listbox"|role=menu')

    def test_each_menu_takes_its_icons_from_the_map(self):
        for rel in self.MENUS:
            text = (SRC / rel).read_text(encoding="utf-8")
            self.assertTrue("actionIcon" in text or "groupIcon" in text, rel)

    def test_no_file_draws_a_menu_that_is_not_listed(self):
        for path in sorted(SRC.rglob("*.jsx")):
            rel = path.relative_to(SRC).as_posix()
            if rel in self.MENUS or rel in self.OTHER or not self.DRAWS.search(path.read_text(encoding="utf-8")):
                continue
            self.fail(f"{rel} draws a menu: give each line an icon from menuIcons.js and list the file in MENUS")

    def test_the_dead_mi_t_class_has_a_rule(self):
        css = (SRC.parent / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"(?m)^\.mi-t\s*\{")

    def test_the_row_menu_no_longer_names_its_own_icons_for_shared_actions(self):
        text = (SRC / "edit" / "RowMenu.jsx").read_text(encoding="utf-8")
        for bad in ('icon: "trash"', 'icon: "archive"', 'icon: "ext"'):
            self.assertNotIn(bad, text)


# Every menu the page can open from a plain visit: (address, button to click, what the menu may skip). A line of the menu that is not a
# note (a heading, a separator, the top "who" line, a disabled explainer) must draw an icon of 15px or more. A menu with a bare line fails.
REACHABLE = [
    ("#dashboard&p=ABC", "#profile-btn"),
    ("#dashboard&p=ABC", "#project-name"),
    ("#work&p=ABC", "#viewMenu"),
    ("#work&p=ABC", "#viewTabMenu"),
    ("#work&p=ABC", "#newBtn"),
    ("#work&p=ABC", "#group-by"),
]
BARE = ("(() => { const m = [...document.querySelectorAll('[role=menu]')].pop(); if (!m) return null;"
        " return [...m.querySelectorAll('[role=menuitem],[role=menuitemradio]')].filter(b => b.getAttribute('aria-disabled') !== 'true' && !b.closest('.who'))"
        ".map(b => { const s = b.querySelector('svg.i'); return {t: b.textContent.trim().slice(0, 30), w: s ? s.getBoundingClientRect().width : 0}; }); })()")


class Page(Base):
    def test_every_reachable_menu_has_an_icon_on_every_line(self):
        seen = 0
        with chrome() as cdp:
            for addr, button in REACHABLE:
                p = self.visit(cdp)
                p.edit()
                if addr != "#dashboard&p=ABC":
                    p.js("document.querySelector('[data-view=work]').click()")
                    p.until("!!document.querySelector('#work')", "Work items drew")
                    time.sleep(.5)
                for w in WIDTHS:
                    self.at(cdp, p, w)
                    if not p.js(f"!!document.querySelector('{button}')"):
                        continue
                    p.js(f"document.querySelector('{button}').click()")
                    time.sleep(.4)
                    got = p.js(BARE)
                    p.key("Escape", code="Escape", vk=27)
                    time.sleep(.3)
                    if got is None:
                        continue
                    seen += 1
                    for g in got:
                        self.assertGreaterEqual(g["w"], 15, f"{button} at {w}: the line {g['t']!r} has no icon")
        self.assertGreaterEqual(seen, 6, "the menus were really opened")

    def at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        time.sleep(.2)

    def test_the_section_menu_gives_each_line_its_icon_and_keeps_its_words(self):
        want = {"add": "plus", "up": "chevup", "down": "chevdown", "beside": "board", "full": "arrows-out", "hide": "eyeoff",
                "show": "eye", "delete": "trash", "settings": "gear"}
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in WIDTHS:
                self.at(cdp, p, w)
                for ref in IDS:
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-options]').click()")
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .menu')", "the menu opened")
                    p.until("!!document.activeElement && !!document.activeElement.closest('.menu')", "focus moved into the menu")
                    got = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .menu-item')].map(b => {{ const s = b.querySelector('svg.i'); "
                               "const r = s ? s.getBoundingClientRect() : {width: 0}; const t = b.querySelector('.mi-t'); "
                               "return {act: b.dataset.act, icn: s ? s.dataset.icn : '', w: r.width, text: t ? t.textContent.trim() : '', all: b.textContent.trim()}; })")
                    p.key("Escape", code="Escape", vk=27)
                    p.until(f"!document.querySelector('[data-id=\"{ref}\"] .menu')", "closed")
                    self.assertTrue(got)
                    for g in got:
                        self.assertEqual(g["icn"], want[g["act"]], f"{ref} {g['act']} at {w}")
                        self.assertGreaterEqual(g["w"], 15, f"{ref} {g['act']} at {w}: the icon is drawn")
                        self.assertTrue(g["text"] and g["text"] == g["all"], f"{ref} {g['act']}: the words are plain")

    def test_the_profile_menu_gives_each_command_its_icon(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in WIDTHS:
                self.at(cdp, p, w)
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu [role=menuitem]')", "the profile menu opened")
                got = p.js("[...document.querySelectorAll('#profile-menu [role=menuitem]:not(.who-link)')].map(b => { const s = b.querySelector('svg.i'); "
                           "return {id: b.dataset.kind, icn: s ? s.dataset.icn : ''}; })")
                p.key("Escape", code="Escape", vk=27)
                ids = {g["id"]: g["icn"] for g in got}
                self.assertEqual(ids.get("publish"), "ul", w)
                self.assertEqual(ids.get("export"), "dl", w)
                self.assertEqual(ids.get("word-export"), "dl", w)
                self.assertEqual(ids.get("settings"), "gear", w)
                self.assertEqual(ids.get("help"), "info", w)


if __name__ == "__main__":
    unittest.main()

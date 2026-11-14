"""Row 1138 (extends 1074): every drop-down menu shows an icon beside each line's words, the same icon for the same action.

Run: python3 dev/run_tests.py test_menu_icons_every_1138
Part 1 reads the shared map (page/src/menuIcons.js ACTION_ICON) in node. Part 2 reads the source: every file that draws a menu is
named in a list, and each is tied to the browser drive below that opens its menus. Part 3 opens EVERY menu in headless Chrome at 1400
and 900, light and dark (the dashboard, the Work items page and board, the Gantt, the published file's menu, the rich text style menu),
and checks that every line of each one draws an icon. A menu button that is missing fails the test, it is never skipped. No sleeps:
each step waits for a signal on the page.
"""
import contextlib
import json
import re
import shutil
import subprocess
import unittest

from _paths import ROOT

import _rich_page as rp  # noqa: E402
import test_client_menu as CM  # noqa: E402
import test_gantt_page as GP  # noqa: E402
from test_bulk_bar import Base as BulkBase  # noqa: E402
from test_work_filters import set_line  # noqa: E402
from test_multi_select import MOD, peek_away, tap  # noqa: E402
from test_report_editor import Base, IDS  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

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


# The name of every menu the drives below open. Each belongs to a menu file in Source.MENUS (and the other way round).
DRIVE_NAMES = {
    "section", "profile", "project-switch", "outline", "health", "uc-status", "commitment", "uc-group", "uc-sort", "uc-detail-status",
    "uc-milestone-link", "new-tile", "view-tab", "view", "owner-pick", "owner-pick-typed", "cell-Due date", "cell-Priority", "cell-Status",
    "rowmenu", "rowmenu-status", "rowmenu-due", "rowmenu-owner", "rowmenu-owner-add", "rowmenu-card", "bulk-items", "bulk-items-mixed",
    "bulk-picker-status", "bulk-picker-owner", "bulk-picker-due", "bulk-picker-priority", "bulk-picker-workstream", "bulk-picker-milestone",
    "board-move", "board-move-lanes", "gantt-show-chart", "gantt-show-table", "gantt-add-below-chart", "gantt-add-below-table",
    "gantt-right-click", "client", "client-disabled-excel", "text-style", "slash-list", "peek-more", "record-more",
}


class Source(unittest.TestCase):
    # Every file that draws a drop-down menu, and the drives (DRIVE_NAMES, run in the browser below) that open its menus. A file with a menu
    # that is in neither table fails, and so does a drive that no file names or a file that names a drive that does not exist.
    MENUS = {
        "edit/Gutter.jsx": ("section",), "edit/ProfileMenu.jsx": ("profile",),
        "edit/RowMenu.jsx": ("rowmenu", "rowmenu-card", "rowmenu-status", "rowmenu-due", "rowmenu-owner", "rowmenu-owner-add"),
        "components/ClientMenu.jsx": ("client", "client-disabled-excel"),
        "gantt/components/GanttTable.jsx": ("gantt-right-click", "gantt-add-below-table"),
        "gantt/components/GanttChart.jsx": ("gantt-add-below-chart",), "gantt/components/GanttPage.jsx": ("gantt-show-chart", "gantt-show-table"),
        "edit/Bulk.jsx": ("bulk-items", "bulk-items-mixed", "bulk-picker-status", "bulk-picker-owner", "bulk-picker-due",
                          "bulk-picker-priority", "bulk-picker-workstream", "bulk-picker-milestone"),
        "edit/Board.jsx": ("board-move", "board-move-lanes"), "edit/GlanceEdit.jsx": ("outline", "health"),
        "edit/ProjectSwitch.jsx": ("project-switch",), "components/FilterLine.jsx": ("view",), "components/WorkItems.jsx": ("view-tab", "view"),
        "components/NewTile.jsx": ("new-tile",), "edit/UseCasesPage.jsx": ("uc-group", "uc-sort"), "components/UseCasesTab.jsx": ("uc-group", "uc-sort"),
        "edit/UseCasesEdit.jsx": ("uc-status", "uc-milestone-link"), "components/UseCaseDetail.jsx": ("uc-detail-status",),
        "edit/CommitMenu.jsx": ("commitment",), "edit/RichText.jsx": ("text-style", "slash-list"), "edit/PeekMore.jsx": ("peek-more",), "edit/RecordMore.jsx": ("record-more",),
        "edit/cells/OwnerPick.jsx": ("owner-pick", "owner-pick-typed"),
        "edit/cells/MenuPick.jsx": ("cell-Due date", "cell-Priority", "cell-Status"),
    }
    # Pickers that drew an icon on every line through their own choices (row 1074, test_menu_icons_mutproof_1074), the shared box, and one
    # list that is not a menu of commands.
    OTHER = {
        "edit/cells/RatingPick.jsx": "row 1074", "edit/cells/StatusPick.jsx": "row 1074", "edit/cells/PriorityPick.jsx": "row 1074",
        "edit/PeekPick.jsx": "row 1074", "edit/MilestonePeek.jsx": "row 1074", "components/Menu.jsx": "the shared box and row: every menu above draws through it",
        "edit/ArchivedPeek.jsx": "row 1074", "edit/PeekActivity.jsx": "row 1074", "edit/ArchivedItems.jsx": "row 1074", "components/UseCases.jsx": "row 1074",
        "components/Peek.jsx": "row 1074",
        "edit/Palette.jsx": "the command palette is a search list of what was typed (pages, items and commands found), not a menu of actions",
        "components/UseCaseFilePage.jsx": "only a selector that tells when a menu is open (for Esc); it draws none",
    }
    # By design NOT icon menus, kept here with the reason: lists that follow what is typed, whose lines are text matches.
    # (The RichText slash list is NOT here: it is driven, see Rich.test_slash_list_gives_every_block_its_icon.)
    BY_DESIGN = {
        "FilterLine suggestions (components/FilterLine.jsx, the list under the filter box)":
            "they complete what is typed (a field name, an owner, a date word); the View menu beside it is an icon menu and is driven",
        "Command palette (edit/Palette.jsx)": "a search over pages, items and commands by what is typed",
        "Work items filter value box (components/WorkFilters.jsx, class fbox, role=group)":
            "a checkbox filter panel (one checkbox line per value), not a command menu: its lines are choices, not actions",
        "Native select drop-downs (edit/AiSettings.jsx, edit/BrandPick.jsx, edit/DocumentsEdit.jsx, edit/NeedsEdit.jsx, edit/TrackerEdit.jsx, "
        "edit/UseCasesEdit.jsx, edit/WeekPicker.jsx, edit/templates/Callout.jsx, edit/templates/Checklist.jsx, edit/templates/FiguresEdit.jsx, "
        "edit/templates/KeyDates.jsx, edit/templates/WorkItemsList.jsx, edit/templates/raidEdit.jsx, gantt/components/GanttTable.jsx cell editor)":
            "a native select cannot hold icons: the browser draws its list",
        "Hand over people datalist (edit/HandOver.jsx)": "a native datalist of names that completes what is typed; the browser draws it, so it cannot hold icons",
    }
    # A popup that is not a command menu: the filter value box (class fbox), a native select or a datalist. A file that draws one must be
    # named in a BY_DESIGN key, so a new one is a choice made on purpose.
    POPUPS = re.compile(r'class=(?:"fbox"|\{`fbox)|<select\b|<datalist\b')
    DRAWS = re.compile(r'<Menu\b|<MenuPanel|role="menu"|role="listbox"|role=menu')

    def test_each_menu_file_is_tied_to_a_drive_that_opens_its_menus(self):
        named = set()
        for rel, drives in self.MENUS.items():
            self.assertTrue((SRC / rel).exists(), rel)
            for d in drives:
                self.assertIn(d, DRIVE_NAMES, f"{rel} names the drive {d!r}, which the browser tests do not have")
                named.add(d)
        self.assertEqual(sorted(DRIVE_NAMES - named), [], "a drive that belongs to no menu file: list it in MENUS")

    def test_the_menu_files_name_the_icon_map_and_the_by_design_list_is_kept(self):
        for rel in self.MENUS:
            text = (SRC / rel).read_text(encoding="utf-8")
            self.assertTrue("actionIcon" in text or "groupIcon" in text or "<Icon" in text, rel)
        self.assertEqual(len(self.BY_DESIGN), 5)
        for what, why in self.BY_DESIGN.items():
            self.assertTrue(why, what)

    def test_no_file_draws_a_menu_that_is_not_listed(self):
        for path in sorted(SRC.rglob("*.jsx")):
            rel = path.relative_to(SRC).as_posix()
            if rel in self.MENUS or rel in self.OTHER or not self.DRAWS.search(path.read_text(encoding="utf-8")):
                continue
            self.fail(f"{rel} draws a menu: give each line an icon from menuIcons.js, list the file in MENUS and open its menu in a drive")

    def test_no_file_draws_a_filter_box_or_native_select_that_is_not_listed_by_design(self):
        keys = " ".join(self.BY_DESIGN)
        for path in sorted(SRC.rglob("*.jsx")):
            rel = path.relative_to(SRC).as_posix()
            if self.POPUPS.search(path.read_text(encoding="utf-8")) and rel not in keys:
                self.fail(f"{rel} draws a filter value box, a native select or a datalist: name the file in a Source.BY_DESIGN key with the reason")

    def test_the_dead_mi_t_class_has_a_rule(self):
        css = (SRC.parent / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"(?m)^\.mi-t\s*\{")

    def test_the_row_menu_no_longer_names_its_own_icons_for_shared_actions(self):
        text = (SRC / "edit" / "RowMenu.jsx").read_text(encoding="utf-8")
        for bad in ('icon: "trash"', 'icon: "archive"', 'icon: "ext"'):
            self.assertNotIn(bad, text)

    def test_the_gantt_row_menu_takes_its_icon_at_the_drawing(self):
        # So the lines that build the menu are left as they were here and the change merges with the ones that edit the Delete line.
        text = (SRC / "gantt" / "components" / "GanttTable.jsx").read_text(encoding="utf-8")
        self.assertIn("rowAction(it)", text)
        self.assertNotIn('false, "add"', text)


# ── driving every menu ────────────────────────────────────────────────────────────────────────────────────────────────────────

ITEM = "[role=menuitem],[role=menuitemradio],[role=option],.menu-item,.cm-row,.cp-name,.cp-q button"
# The lines of the open menu `root`: anything a person can pick, a disabled line too. Each must draw an svg.i of 15px or more. A line for a
# named person draws that person's initials circle (.av) as its icon, so it needs no second one.
LINES = ("(root => { const ok = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };"
         " const boxes = [...document.querySelectorAll(root)].filter(ok); const box = boxes[boxes.length - 1]; if (!box) return null;"
         f" return [...new Set(box.querySelectorAll({json.dumps(ITEM)}))].filter(ok).map(b => {{ const s = b.querySelector('svg.i, .av');"
         " return {t: b.textContent.trim().slice(0, 40), w: s ? s.getBoundingClientRect().width : 0, off: b.getAttribute('aria-disabled') === 'true'}; }); })")
CONTEXT = ("(sel => { const el = document.querySelector(sel); const r = el.getBoundingClientRect();"
           " el.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true, button: 2, clientX: r.left + 30, clientY: r.top + 8})); })")
LOOKS = [(1400, "light"), (900, "dark"), (1400, "dark"), (900, "light")]


def q(x):
    return json.dumps(x)


class Drive:
    """One page in Chrome: open a menu, wait for it, check every line, close it, wait for it to be gone. A step that cannot find its button or
    its menu FAILS (it never skips). The name of each menu checked goes in `done`; a test ends by saying which names it must have reached."""

    def __init__(self, test, cdp, sid):
        self.t, self.cdp, self.sid, self.done = test, cdp, sid, set()

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, secs=20):
        self.t.assertTrue(wait(lambda: self.js(f"!!({expr})"), secs), f"timed out waiting for: {what} (at {getattr(self, 'look_is', None)})")

    def key(self, key, code=None, vk=0):
        for kind in ("keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code or key, "windowsVirtualKeyCode": vk, "modifiers": 0}, self.sid)

    def look(self, width, theme):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.until(f"window.innerWidth === {width}", f"the window is {width} wide")
        self.js(f"document.documentElement.dataset.theme = {q(theme)}")
        self.until(f"document.documentElement.dataset.theme === {q(theme)}", f"the {theme} theme")
        self.look_is = (width, theme)

    def button(self, sel, what):
        self.until(f"document.querySelector({q(sel)})", f"{what}: the button {sel} is on the page")

    def lines(self, root, name, minimum):
        self.t.assertIn(name, DRIVE_NAMES, f"{name} is not a registered drive")
        self.until(f"(({LINES})({q(root)}) || []).length >= {minimum}", f"{name}: the menu {root} drew at least {minimum} lines")
        got = self.js(f"({LINES})({q(root)})")
        where = f"{name} at {self.look_is[0]} {self.look_is[1]}"
        self.t.assertGreaterEqual(len(got), minimum, where)
        for g in got:
            self.t.assertTrue(g["t"], f"{where}: a line has no words")
            self.t.assertGreaterEqual(g["w"], 15, f"{where}: the line {g['t']!r} (disabled: {g['off']}) draws no icon")
        self.done.add(name)
        return got

    def gone(self, root, what):
        self.until(f"!({LINES})({q(root)})", f"{what}: the menu {root} closed")

    def frames(self):
        """Wait for two animation frames: the page's own handlers for what was just drawn (they are set after the draw) are in place."""
        self.js("window.__frames = false; requestAnimationFrame(() => requestAnimationFrame(() => { window.__frames = true; })); true")
        self.until("window.__frames === true", "two frames drew")

    def focused_in(self, root):
        self.until(f"(root => {{ const bs = [...document.querySelectorAll(root)]; const b = bs[bs.length - 1]; return !!b && b.contains(document.activeElement); }})({q(root)})",
                   f"the focus is in the menu {root}")

    def check(self, name, opener, root="[role=menu]", minimum=2, focus=True):
        """Run `opener` (JS that clicks), check every line of the menu `root`, close it with Escape (once the focus is in it) or, for a menu that takes no focus, with a press elsewhere on the page."""
        self.js(opener)
        got = self.lines(root, name, minimum)
        if focus:
            self.focused_in(root)
            self.key("Escape", "Escape", 27)
        else:
            self.frames()
            self.js("document.body.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, cancelable: true}))")      # a press elsewhere on the page
        self.gone(root, name)
        return got

    def click(self, sel, what):
        self.button(sel, what)
        self.js(f"document.querySelector({q(sel)}).click()")

    def expect(self, names):
        self.t.assertEqual(sorted(set(names) - self.done), [], "these menus were never opened")


class Dashboard(Base):
    def drive(self, cdp):
        p = self.visit(cdp)
        p.edit()
        return p, Drive(self, cdp, p.sid)

    def test_dashboard_menus(self):
        with chrome() as cdp:
            p, d = self.drive(cdp)
            for w, th in LOOKS:
                d.look(w, th)
                d.button("#profile-btn", "profile")
                d.check("profile", "document.querySelector('#profile-btn').click()", "#profile-menu", 8)
                d.button("#project-name", "project switch")
                d.check("project-switch", "document.querySelector('#project-name').click()", "[role=menu]", 1)
                for ref in IDS:
                    d.button(f"[data-id='{ref}'] [data-options]", "section options")
                    d.check("section", f"document.querySelector('[data-id=\"{ref}\"] [data-options]').click()", f"[data-id='{ref}'] .menu", 4)
                d.button(".tgrip", "outline grip")
                grips = d.js("document.querySelectorAll('.tgrip').length")
                self.assertGreaterEqual(grips, 4, "the At a glance tiles are drawn")
                for n in range(grips):
                    d.check("outline", f"document.querySelectorAll('.tgrip')[{n}].dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))", ".tilemenu", 3)
                d.button("#health-pill", "health pill")
                d.check("health", "document.querySelector('#health-pill').click()", "#health-menu", 3)
                d.button("[id^=ucst-]", "use case status")
                d.check("uc-status", "document.querySelector('[id^=ucst-]').click()", "[role=menu]", 3)
                d.button("[id^=uccm-]", "commitment")
                d.check("commitment", "document.querySelector('[id^=uccm-]').click()", "[role=menu]", 2)
            d.expect(["profile", "project-switch", "section", "outline", "health", "uc-status", "commitment"])

    def test_the_section_menu_gives_each_line_its_icon_and_keeps_its_words(self):
        want = {"add": "plus", "up": "chevup", "down": "chevdown", "beside": "board", "full": "arrows-out", "hide": "eyeoff",
                "show": "eye", "delete": "trash", "settings": "gear"}
        with chrome() as cdp:
            p, d = self.drive(cdp)
            for w in WIDTHS:
                d.look(w, "light")
                for ref in IDS:
                    d.button(f"[data-id='{ref}'] [data-options]", "section options")
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
            p, d = self.drive(cdp)
            for w in WIDTHS:
                d.look(w, "light")
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu [role=menuitem]')", "the profile menu opened")
                got = p.js("[...document.querySelectorAll('#profile-menu [role=menuitem]:not(.who-link)')].map(b => { const s = b.querySelector('svg.i'); "
                           "return {id: b.dataset.kind, icn: s ? s.dataset.icn : ''}; })")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#profile-menu')", "the profile menu closed")
                ids = {g["id"]: g["icn"] for g in got}
                self.assertEqual(ids.get("publish"), "ul", w)
                self.assertEqual(ids.get("export"), "dl", w)
                self.assertEqual(ids.get("word-export"), "dl", w)
                self.assertEqual(ids.get("settings"), "gear", w)
                self.assertEqual(ids.get("help"), "info", w)


def selected(test, cdp, sid, ids):
    """Select `ids` as a person does (a click, then Ctrl- or Cmd-clicks) and wait until the page says they are selected."""
    tap(cdp, sid, f"#work-list tr[data-id='{ids[0]}'] .c-item .t")
    peek_away(cdp, sid, cdp.js("innerWidth", sid))
    for rid in ids[1:]:
        tap(cdp, sid, f"#work-list tr[data-id='{rid}'] .c-item .t", MOD)
    test.assertTrue(wait(lambda: cdp.js("clarkPage.selected()", sid) == ids), "the rows are selected")


class Work(BulkBase):
    """The Work items page and board, the Use cases pages, the row menu, the bulk menu and its pickers."""
    ROWS = "[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)"

    def load(self, cdp, kind="action"):
        """The Work items page, its filter line set to one kind of item (or to none: every kind), and the rows drawn."""
        sid = self.visit(cdp)
        set_line(cdp, sid, f"type:{kind}" if kind else "")
        self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length >= 2", "the rows")
        return sid

    def test_work_page_menus(self):
        with chrome() as cdp:
            sid = self.load(cdp, kind=None)
            d = Drive(self, cdp, sid)
            for w, th in LOOKS:
                d.look(w, th)
                d.button("#newBtn", "new tile")
                d.check("new-tile", "document.querySelector('#newBtn').click()", "[role=menu]", 2)
                d.button("#viewTabMenu", "view tab")
                d.check("view-tab", "document.querySelector('#viewTabMenu').click()", "[role=menu]", 1)
                d.button("#viewMenu", "view menu")
                d.check("view", "document.querySelector('#viewMenu').click()", "#viewMenuList", 8)
                osel = "#work-list tr[data-id] [aria-label^='Owner of ']"
                d.button(osel, "the owner cell")
                d.check("owner-pick", f"document.querySelector({q(osel)}).click()", ".cpop", 1)
                for kind in ("Due date", "Priority", "Status"):
                    sel = f"#work-list tr[data-id] [aria-label^='{kind} of ']"
                    d.button(sel, f"the {kind} cell")
                    d.check(f"cell-{kind}", f"document.querySelector({q(sel)}).click()", "[role=menu],.cpop", 1)
                # the owner box with a name nobody has: the Add line and the Keep the name only line
                d.js(f"document.querySelector({q(osel)}).click()")
                d.until("document.activeElement && document.activeElement.classList.contains('cp-in')", "the owner box has the focus")
                cdp.call("Input.insertText", {"text": "Zelda Quince"}, sid)
                d.until("document.querySelector('.cpop [data-add]')", "the Add line for a new name")
                d.lines(".cpop", "owner-pick-typed", 3)
                d.key("Escape", "Escape", 27)
                d.gone(".cpop", "the owner box")
            d.expect(["new-tile", "view-tab", "view", "owner-pick", "owner-pick-typed", "cell-Due date", "cell-Priority", "cell-Status"])

    def test_row_menu_and_its_lists(self):
        with chrome() as cdp:
            sid = self.load(cdp, kind=None)
            d = Drive(self, cdp, sid)
            first = "#work-list tr[data-id]"
            actions = "[role=menu][aria-label^='Actions for']"
            for w, th in LOOKS:
                d.look(w, th)
                d.button(first, "a work row")
                d.js(f"({CONTEXT})({q(first)})")
                d.lines(actions, "rowmenu", 8)
                for level in ("status", "due", "owner"):
                    d.click(f"[data-rm={level}]", f"the {level} entry of the row menu")
                    d.lines(".rm-fly", f"rowmenu-{level}", 1)
                    if level == "owner":
                        d.button("[data-rm-search]", "the owner search box")
                        d.js("document.querySelector('[data-rm-search]').focus()")
                        cdp.call("Input.insertText", {"text": "Zelda Quince"}, sid)
                        d.until("document.querySelector('.rm-fly [data-rm=addp]')", "the Add line for a new person")
                        d.lines(".rm-fly", "rowmenu-owner-add", 1)
                    d.key("Escape", "Escape", 27)
                    d.gone(".rm-fly", f"the {level} list")
                d.key("Escape", "Escape", 27)
                d.gone(actions, "the row menu")
            d.expect(["rowmenu", "rowmenu-status", "rowmenu-due", "rowmenu-owner", "rowmenu-owner-add"])

    def test_peek_more_menu_icons_and_duplicate_matches_the_row_menu(self):
        with chrome() as cdp:
            sid = self.load(cdp, kind=None)
            d = Drive(self, cdp, sid)
            first = "#work-list tr[data-id]"
            actions = "[role=menu][aria-label^='Actions for']"
            icon = "(k => { const b = [...document.querySelectorAll('[role=menu]')].pop().querySelector(k); return b && b.querySelector('svg.i') ? b.querySelector('svg.i').dataset.icn : null; })"
            for w, th in LOOKS:
                d.look(w, th)
                d.js(f"({CONTEXT})({q(first)})")
                d.lines(actions, "rowmenu", 8)
                row_dup = d.js(f"({icon})('[data-rm=dup]')")
                d.click("[data-rm=peek]", "the Peek line of the row menu")
                d.button("#pk-more", "the peek's More actions button")
                self.assertEqual(d.js("(() => { const b = document.querySelector('#peek [data-pk-dup] svg.i'); return b ? b.dataset.icn : null; })()"), row_dup, f"The peek header Duplicate button has the row menu's icon at {w} {th}")
                d.js("document.getElementById('pk-more').click()")
                d.lines("[role=menu][aria-label='More actions']", "peek-more", 3)
                self.assertEqual(d.js(f"({icon})('[data-kind=duplicate]')"), row_dup, f"Duplicate has the row menu's icon at {w} {th}")
                d.key("Escape", "Escape", 27)
                d.gone("[role=menu][aria-label='More actions']", "the More actions menu")
                d.js("document.querySelector('#peek [data-pk-close]').click()")
            d.expect(["peek-more"])

    def test_bulk_menu_and_pickers(self):
        with chrome() as cdp:
            sid = self.load(cdp, kind="action")
            d = Drive(self, cdp, sid)
            rows = cdp.js(self.ROWS, sid)[:3]
            for w, th in LOOKS:
                d.look(w, th)
                selected(self, cdp, sid, rows)
                d.js(f"({CONTEXT})({q(f'#work-list tr[data-id={chr(34)}{rows[0]}{chr(34)}]')})")
                d.lines(".bmenu", "bulk-items", 9)
                d.key("Escape", "Escape", 27)
                d.gone(".bmenu", "the bulk menu")
                for control in ("status", "owner", "due", "priority", "workstream", "milestone"):
                    sel = f"#sel-bar [data-bulk={control}]"
                    d.button(sel, f"the {control} button of the bar")
                    d.check(f"bulk-picker-{control}", f"document.querySelector({q(sel)}).click()", ".cpop" if control in ("owner", "due") else "[role=menu]", 1)
            d.expect(["bulk-items"] + [f"bulk-picker-{c}" for c in ("status", "owner", "due", "priority", "workstream", "milestone")])

    def test_bulk_menu_with_lines_it_cannot_offer(self):
        with chrome() as cdp:
            sid = self.load(cdp, kind=None)
            d = Drive(self, cdp, sid)
            ids = cdp.js(self.ROWS, sid)
            mixed = [next(i for i in ids if "-A-" in i), next(i for i in ids if "-A-" not in i and "-D-" not in i)]
            for w, th in LOOKS:
                d.look(w, th)
                selected(self, cdp, sid, mixed)
                d.js(f"({CONTEXT})({q(f'#work-list tr[data-id={chr(34)}{mixed[0]}{chr(34)}]')})")
                got = d.lines(".bmenu", "bulk-items-mixed", 2)
                self.assertTrue(any(g["off"] for g in got), "a line that cannot be used is among the lines checked")
                d.key("Escape", "Escape", 27)
                d.gone(".bmenu", "the bulk menu")
            d.expect(["bulk-items-mixed"])

    def test_board_menus(self):
        for lane, name in ((None, "board-move"), ("type", "board-move-lanes")):
            with self.subTest(lane=lane), chrome() as cdp:
                sid = self.visit(cdp)
                self.board(cdp, sid, group="status", lane=lane)
                d = Drive(self, cdp, sid)
                for w, th in LOOKS:
                    d.look(w, th)
                    d.button("[data-move]", "a card's Move to button")
                    n = d.js("document.querySelectorAll('[data-move]').length")
                    for i in range(min(n, 3)):
                        d.check(name, f"document.querySelectorAll('[data-move]')[{i}].click()", "[role=menu][aria-label^='Move ']", 1)
                    d.js(f"({CONTEXT})('article.bcard[data-id]')")
                    d.lines("[role=menu][aria-label^='Actions for']", "rowmenu-card", 8)
                    d.key("Escape", "Escape", 27)
                    d.gone("[role=menu][aria-label^='Actions for']", "the card menu")
                d.expect([name, "rowmenu-card"])

    def test_use_case_pages(self):
        with chrome() as cdp:
            sid = self.visit(cdp, hash_="#usecases&p=ABC", wait_for="#usecases")
            d = Drive(self, cdp, sid)
            for w, th in LOOKS:
                d.look(w, th)
                d.button("#ucl-group", "Group by")
                d.check("uc-group", "document.querySelector('#ucl-group').click()", "[role=menu]", 3)
                d.button("#ucl-sort", "Sort by")
                d.check("uc-sort", "document.querySelector('#ucl-sort').click()", "[role=menu]", 3)
            d.js("location.hash = '#usecases&p=ABC&uc=ABC-U-001'")
            d.until("document.querySelector('#ucd-status')", "the use case page")
            for w, th in LOOKS:
                d.look(w, th)
                d.check("uc-detail-status", "document.querySelector('#ucd-status').click()", "[role=menu]", 3)
                d.check("commitment", "document.querySelector('[id^=uccm-]').click()", "[role=menu]", 2)
                d.button("[id^=ucd-mslink-]", "Link a milestone")
                d.check("uc-milestone-link", "document.querySelector('[id^=ucd-mslink-]').click()", "[role=menu]", 1)
                d.button("#ucd-more", "More actions")
                d.check("record-more", "document.querySelector('#ucd-more').click()", "[role=menu]", 2)
            d.expect(["uc-group", "uc-sort", "uc-detail-status", "commitment", "uc-milestone-link", "record-more"])


class Gantt(unittest.TestCase):
    """The Gantt page (the bare page of tests/test_gantt_page.py), in Edit: the Show menu, the Add below menus, the right-click menu."""

    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=GP.page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.P && window.P.mount)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def mount(self, d, layout):
        d.js(f"P.mount({{mode: 'edit', width: window.innerWidth - 40}})")
        d.until("document.querySelector('#gantt-page[data-mode=edit]')", "the Gantt page in Edit")
        if layout == "table":
            d.click("[data-gp-layout=table]", "the Table switch")
            d.until("document.querySelector('.gt-scroll td[data-k=id]')", "the table")
        else:
            d.until("document.querySelector('[data-g-add]')", "the chart")

    def test_gantt_menus(self):
        d = Drive(self, self.cdp, self.sid)
        for w, th in LOOKS:
            d.look(w, th)
            d.js("document.body.style.margin = '0'")
            self.mount(d, "chart")
            d.button("[data-g-show]", "Show in the chart")
            d.check("gantt-show-chart", "document.querySelector('[data-g-show]').click()", "[data-g-showmenu]", 3, focus=False)
            d.button("[data-g-add]", "Add below")
            d.check("gantt-add-below-chart", "document.querySelector('[data-g-add]').click()", "[data-g-addmenu]", 3)
            self.mount(d, "table")
            d.button("[data-gp-show]", "Show in the table")
            d.check("gantt-show-table", "document.querySelector('[data-gp-show]').click()", "[data-gp-showmenu]", 4)
            d.button(".gt-scroll [data-add]", "the plus beside a row")
            d.check("gantt-add-below-table", "document.querySelector('.gt-scroll [data-add]').click()", ".gt-menu", 3)
            d.check("gantt-right-click", f"({CONTEXT})('.gt-scroll td[data-k=id]')", ".gt-menu", 5)
        d.expect(["gantt-show-chart", "gantt-add-below-chart", "gantt-show-table", "gantt-add-below-table", "gantt-right-click"])


class Client(unittest.TestCase):
    """The published file's menu (components/ClientMenu.jsx), with every row it can draw."""
    setUp = CM.Menu.setUp
    show = CM.Menu.show

    def run_rows(self, extra, name, minimum):
        with chrome() as cdp:
            for w, th in LOOKS:
                js = self.show(cdp, extra, width=w, name=f"report-{w}-{th}.html")
                d = Drive(self, cdp, self.sid)
                d.look(w, th)
                d.button("#client-menu-btn", "the badge")
                d.check(name, f"{CM.BADGE}.click()", "#client-menu", minimum)
                d.expect([name])

    def test_every_row_with_a_workbook_and_past_reports(self):
        past = [{"week_ending": "2026-10-14", "file": "PUB-report-2026-10-14.html"}, {"week_ending": "2026-10-21", "file": "PUB-report-2026-10-21.html"}]
        self.run_rows({"client_workbook": {"name": "Report-2026-10-28.xlsx", "base64": CM.SHEET}, "past_reports": past}, "client", 5)

    def test_the_disabled_excel_row_has_its_icon_too(self):
        self.run_rows({"client_workbook_too_large": True}, "client-disabled-excel", 3)


class Rich(unittest.TestCase):
    """The text style menu of the rich text bar, and the / list (typed, but every block line still draws its icon)."""

    def test_slash_list_gives_every_block_its_icon(self):
        with rp.Harness(chrome) as h:
            d = Drive(self, h.cdp, h.sid)
            for w, th in LOOKS:
                d.look(w, th)
                h.mount("")
                h.type("/")
                d.lines(".rt-slash", "slash-list", 6)
                h.type("head")                                          # narrowed by what is typed: the three headings still draw icons
                d.lines(".rt-slash", "slash-list", 3)
                d.key("Escape", "Escape", 27)
                d.gone(".rt-slash", "the / list")
                h.ev("window.unmount(); true")
            d.expect(["slash-list"])

    def test_text_style_menu(self):
        with rp.Harness(chrome) as h:
            d = Drive(self, h.cdp, h.sid)
            for w, th in LOOKS:
                d.look(w, th)
                h.mount("<p>Title</p>")
                d.button(".rt-bar .rt-style", "the Text style button")
                d.js("document.querySelector('.rt-bar .rt-style').click()")
                d.lines(".rt-bar [role=menu]", "text-style", 4)
                d.key("Escape", "Escape", 27)
                d.gone(".rt-bar [role=menu]", "the style menu")
            d.expect(["text-style"])


if __name__ == "__main__":
    unittest.main()

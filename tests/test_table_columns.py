"""Row 1222: a right click on the heading row of a Work items table or the Milestones list opens a menu of the columns that table can show.

Run: python3 dev/run_tests.py test_table_columns
Right click, the Menu key, Shift+F10 and the visible Columns button open the same menu; a tick turns a column on or off and the table redraws; the
title (name) and status columns are ticked and greyed with a reason; "Show the standard columns" is the foot. The choice is kept for each table and
each project in this browser only (localStorage), a blocked store still lets the table redraw, the published page has none of it, and the Excel export
and the project's data do not know about it. At 1400 and 900 px, light and dark. A real page and server.
"""
import json
import shutil
import time
import unittest
from pathlib import Path
from unittest import mock

from _real_server import real_server
from clark import page, server as sv
from clark.store import open_store
from _new_page import reload_to_new_page_cdp
from test_inline_edits import EMPTY_BRANDING, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

SRC = Path(page.__file__).parent / "src"
WORK_ALL = ["Status", "Item", "Owner", "Due", "Priority", "Id", "Type", "Workstream", "Milestone", "Raised", "Closed", "Use case", "Labels", "Latest update", "Client wording"]
MS_ALL = ["Date", "Milestone", "State", "Progress", "Id", "Description", "Workstream", "Owner", "Agreed", "Forecast", "Order", "State reason"]
KEYS = {"Tab": 9, "ContextMenu": 93, "F10": 121, "Escape": 27, "Enter": 13}
# name, address, the heading row's cells, a heading cell by column id, a body cell by column id, a row, every label, the locked labels, the standard labels
TABLES = {
    "work": ("#work&p=TUL&f=mode:all", "#work table.items thead th", "#work th[data-col='%s']", "#work tbody tr[data-id] td[data-col='%s']", "#work tbody tr[data-id]",
             WORK_ALL, ["Status", "Item"], ["Status", "Item", "Owner", "Due", "Priority", "Id"]),
    "milestones": ("#milestones&p=TUL", "#milestones .msl-hd [data-col]", "#milestones .msl-hd [data-col='%s']", "#milestones .msl-cells [data-col='%s']:not(.cols-off)", "#milestones li.msl-row",
                   MS_ALL, ["Milestone", "State"], ["Date", "Milestone", "State", "Progress"]),
}
# Notes the time of every scroll of the page (any element, captured), from the first moment of the page; a late one closes an open menu.
SETTLE = "window.__lastScroll = 0; window.addEventListener('scroll', () => { window.__lastScroll = performance.now(); }, true);"
QUIET_MS = 700
MENU = ".cols-menu[role=menu]"
ITEMS = MENU + " [role=menuitemcheckbox]"


class Columns(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def visit(self, cdp, width, scheme, name, early=""):
        sid = page_target(cdp)
        for m, p in (("Page.enable", {}), ("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}),
                     ("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}), ("Emulation.setFocusEmulationEnabled", {"enabled": True})):
            cdp.call(m, p, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + early}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{name}"}, sid)
        return sid

    def open_table(self, cdp, width, scheme, table, early=""):
        url, heads, head, cell, row, *_ = TABLES[table]
        sid = self.visit(cdp, width, scheme, url, SETTLE + early)
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        self.assertTrue(wait(lambda: js(f"document.querySelectorAll({json.dumps(row)}).length > 0 && document.querySelectorAll({json.dumps(heads)}).length > 0"), 20), "the table is drawn")
        # The menu closes on any scroll of the window (MenuPanel), and the page scrolls itself while it settles (the address's own place, fonts moving the
        # layout), later on a slower computer (macOS CI). So the menu is asked for only once the Columns button is there, the fonts are in and no scroll
        # has come for a while.
        btn = "#work .cols-btn" if table == "work" else "#milestones .msl-cols-btn"
        self.assertTrue(wait(lambda: js(f"!!document.querySelector({json.dumps(btn)}) && document.fonts.status === 'loaded' && performance.now() - window.__lastScroll > {QUIET_MS}"), 20), "the page has settled")
        return sid, js

    def right_click(self, cdp, sid, selector):
        x, y = cdp.js(f"(() => {{ const b = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()", sid)
        for t in ("mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "right", "buttons": 2 if t == "mousePressed" else 0, "clickCount": 1}, sid)

    def open_menu(self, cdp, sid, js, selector, seconds=20):
        """Right-clicks the heading and waits for the menu; asks again while it is not there. The menu is placed once and closes on any scroll or
        resize of the window (Menu.jsx), so on a slow computer (macOS CI) a late scroll can shut the one the first click opened."""
        def asked():
            if self.menu(js):
                return True
            self.right_click(cdp, sid, selector)
            return wait(lambda: self.menu(js), 1.5)
        return wait(asked, seconds)

    def press(self, cdp, sid, name, shift=False):
        common = {"key": name, "code": name, "windowsVirtualKeyCode": KEYS[name], **({"modifiers": 8} if shift else {})}
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown" if name == "Enter" else "rawKeyDown", **({"text": "\r"} if name == "Enter" else {}), **common}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)

    def menu(self, js):
        return js(f"""(() => {{ const m = document.querySelector({json.dumps(MENU)}); if (!m) return null;
            return {{label: m.getAttribute('aria-label'), items: [...m.querySelectorAll('[role=menuitemcheckbox]')].map((b) => ({{name: b.dataset.colName, on: b.getAttribute('aria-checked'), off: b.getAttribute('aria-disabled'), text: b.textContent.trim()}})),
                foot: [...m.querySelectorAll('[role=menuitem]')].map((b) => b.textContent.trim()), why: [...m.querySelectorAll('.cols-why')].map((e) => e.textContent.trim()),
                rows: m.getBoundingClientRect().toJSON(), win: [innerWidth, innerHeight]}}; }})()""")

    def heads(self, js, table):
        return js(f"[...new Set([...document.querySelectorAll({json.dumps(TABLES[table][1])})].map((e) => e.dataset.col).filter(Boolean))]")

    def pick(self, js, label):
        js(f"[...document.querySelectorAll({json.dumps(ITEMS)})].find((b) => b.dataset.colName === {json.dumps(label)}).click()")

    # --- the settled parts -------------------------------------------------------------------------------------------------------------

    def test_a_right_click_on_the_heading_row_lists_every_column_the_table_can_show(self):
        for table, (_, _, head, _, _, every, locked, standard) in TABLES.items():
            for width in (1400, 900):
                for scheme in ("light", "dark"):
                    with self.subTest(table=table, width=width, scheme=scheme), chrome() as cdp:
                        sid, js = self.open_table(cdp, width, scheme, table)
                        self.assertIsNone(self.menu(js), "no menu until it is asked for")
                        self.assertTrue(self.open_menu(cdp, sid, js, head % ("owner" if table == "work" else "state")), "the menu opens")
                        # The menu slides in by a few pixels, so its box is read only once it has stopped (twice the same, 100 ms apart).
                        seen = []
                        def still():
                            seen.append(self.menu(js)["rows"]); time.sleep(.1)
                            return len(seen) > 1 and seen[-1] == seen[-2]
                        self.assertTrue(wait(still, 5), "the menu stops moving")
                        got = self.menu(js)
                        self.assertEqual([i["name"] for i in got["items"]], every, "every column the table can show, in the table's own order")
                        for i in got["items"]:
                            self.assertEqual(i["on"], "true" if i["name"] in standard else "false", f"{i['name']}: ticked when shown")
                            self.assertEqual(i["off"], "true" if i["name"] in locked else None, f"{i['name']}: greyed only when it cannot be turned off")
                        self.assertEqual(got["foot"], ["Show the standard columns"], "the foot of the menu")
                        self.assertEqual(len(got["why"]), len(locked), "each locked column says why")
                        for w in got["why"]:
                            self.assertGreater(len(w), 10)
                        inside = ("(() => { const r = document.querySelector(%s).getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight + 1; })()"
                                  % json.dumps(MENU))
                        wait(lambda: js(inside), 5)      # the menu is placed after it first paints: read where it ended up, not where it started (slow CI runners)
                        got = self.menu(js)
                        r, win = got["rows"], got["win"]
                        self.assertTrue(r["left"] >= 0 and r["right"] <= win[0] and r["top"] >= 0 and r["bottom"] <= win[1] + 1, "the menu is inside the window")

    def test_a_tick_turns_a_column_on_or_off_and_the_table_redraws(self):
        for table, (_, _, head, cell, _, every, _, standard) in TABLES.items():
            for width in (1400, 900):
                with self.subTest(table=table, width=width), chrome() as cdp:
                    sid, js = self.open_table(cdp, width, "light", table)
                    self.assertTrue(self.open_menu(cdp, sid, js, head % ("owner" if table == "work" else "state")))
                    self.pick(js, "Workstream")
                    self.assertTrue(wait(lambda: "workstream" in self.heads(js, table), 5), "the column appears")
                    self.assertTrue(js(f"document.querySelectorAll({json.dumps(cell % 'workstream')}).length > 0"), "and so do its cells")
                    self.assertEqual(self.menu(js)["items"][every.index("Workstream")]["on"], "true", "the menu stays open and shows the tick")
                    first = "owner" if table == "work" else "prog"
                    self.pick(js, "Owner" if table == "work" else "Progress")
                    self.assertTrue(wait(lambda: first not in self.heads(js, table), 5), "turning one off takes the column out")
                    self.assertEqual(js(f"document.querySelectorAll({json.dumps(cell % first)}).length"), 0, "and its cells")
                    self.assertEqual(js("document.documentElement.scrollWidth <= innerWidth + 1"), True, "the page does not scroll sideways")

    def test_the_title_and_the_status_cannot_be_turned_off(self):
        for table, (_, _, head, _, _, _, locked, _) in TABLES.items():
            with self.subTest(table=table), chrome() as cdp:
                sid, js = self.open_table(cdp, 1400, "light", table)
                before = self.heads(js, table)
                self.assertTrue(self.open_menu(cdp, sid, js, head % ("owner" if table == "work" else "state")))
                for name in locked:
                    self.pick(js, name)
                self.assertEqual(self.heads(js, table), before, "pressing a greyed item changes nothing")
                self.assertIsNone(js(f"localStorage.getItem('clark.cols.show.{table}.TUL')"), "and keeps nothing")

    def test_the_standard_columns_are_one_press_away(self):
        for table, (_, _, head, _, _, _, _, standard) in TABLES.items():
            with self.subTest(table=table), chrome() as cdp:
                sid, js = self.open_table(cdp, 1400, "light", table)
                was = self.heads(js, table)
                self.assertTrue(self.open_menu(cdp, sid, js, head % ("owner" if table == "work" else "state")))
                self.pick(js, "Type" if table == "work" else "Id")
                self.pick(js, "Workstream")
                self.assertTrue(wait(lambda: len(self.heads(js, table)) == len(was) + 2, 5))
                js(f"document.querySelector({json.dumps(MENU + ' [data-cols-standard]')}).click()")
                self.assertTrue(wait(lambda: self.heads(js, table) == was, 5), "the table is back to its standard columns")
                self.assertIsNone(js(f"localStorage.getItem('clark.cols.show.{table}.TUL')"), "and no choice is kept")

    def test_the_choice_is_kept_for_each_table_and_each_project_in_this_browser_only(self):
        for table, (_, _, head, _, _, _, _, _) in TABLES.items():
            with self.subTest(table=table), chrome() as cdp:
                sid, js = self.open_table(cdp, 1400, "light", table)
                self.assertTrue(self.open_menu(cdp, sid, js, head % ("owner" if table == "work" else "state")))
                self.pick(js, "Workstream")
                self.assertTrue(wait(lambda: "workstream" in self.heads(js, table), 5))
                stored = js(f"localStorage.getItem('clark.cols.show.{table}.TUL')")
                self.assertIn("workstream", stored or "", "kept under the table and the project")
                other = "milestones" if table == "work" else "work"
                self.assertIsNone(js(f"localStorage.getItem('clark.cols.show.{other}.TUL')"), "the other table has its own choice")
                self.assertIsNone(js(f"localStorage.getItem('clark.cols.show.{table}.OTHER')"), "and so has another project")
                reload_to_new_page_cdp(cdp, sid, f"!!document.querySelector({json.dumps(TABLES[table][2] % 'workstream')})", "the choice is still there after a reload")

    def test_a_hidden_columns_width_is_kept_per_column_id_and_comes_back_with_the_column(self):
        """Row 1222, ruled 15-11: hiding a column does not forget the width chosen for it (row 1104 keeps widths by column id)."""
        early = "try { localStorage.setItem('clark.cols.work', JSON.stringify({workstream: 222})); } catch (e) {}"
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work", early)
            self.assertTrue(self.open_menu(cdp, sid, js, "#work th[data-col='owner']"))
            self.pick(js, "Workstream")
            self.assertTrue(wait(lambda: "workstream" in self.heads(js, "work"), 5))
            width = lambda: js("Math.round(document.querySelector(\"#work th[data-col='workstream']\").getBoundingClientRect().width)")  # noqa: E731
            self.assertTrue(wait(lambda: abs(width() - 222) <= 2, 5), f"the kept width is drawn ({width()})")
            self.pick(js, "Workstream")
            self.assertTrue(wait(lambda: "workstream" not in self.heads(js, "work"), 5), "hidden")
            self.assertIn("222", js("localStorage.getItem('clark.cols.work')") or "", "the width is still kept while the column is hidden")
            self.pick(js, "Workstream")
            self.assertTrue(wait(lambda: "workstream" in self.heads(js, "work"), 5))
            self.assertTrue(wait(lambda: abs(width() - 222) <= 2, 5), f"and it comes back at that width ({width()})")

    def test_the_dashboard_milestones_choice_and_widths_are_kept_under_msdash_and_leave_the_milestones_keys_alone(self):
        """Row 1230: the Dashboard section is its own table ("msDash"); its columns choice and widths do not write the Milestones page's keys."""
        keys = "JSON.stringify(Object.keys(localStorage).filter((k) => k.startsWith('clark.cols')).sort())"
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, "light", "#dashboard&p=TUL", SETTLE)
            js = lambda e: cdp.js(e, sid)  # noqa: E731
            quiet = f"document.fonts.status === 'loaded' && performance.now() - window.__lastScroll > {QUIET_MS}"      # the menu closes on any scroll: ask for it only after the page has stopped moving
            box = ".msv .msl-box"
            self.assertTrue(wait(lambda: js(f"!!document.querySelector('{box} .msl-row')"), 20), "the Dashboard milestones drew their rows")
            js("document.querySelector('[data-mode=edit]').click()")
            head = f"{box} .msl-hd [data-col='state']"
            self.assertTrue(wait(lambda: js(f"!!document.querySelector({json.dumps(head)})"), 10), "Edit draws the heading row")
            js(f"document.querySelector({json.dumps(head)}).scrollIntoView({{block: 'center'}})")
            self.assertTrue(wait(lambda: js(quiet), 20), "the page has settled after the scroll")
            self.assertTrue(self.open_menu(cdp, sid, js, head), "the menu opens on the Dashboard heading row")
            self.pick(js, "Workstream")
            self.assertTrue(wait(lambda: js(f"!!document.querySelector({json.dumps(box + ' .msl-hd [data-col=workstream]')})"), 5), "the column appears on the Dashboard")
            chosen = js("localStorage.getItem('clark.cols.show.msDash.TUL')")
            self.assertIn("workstream", chosen or "", "the choice is kept under msDash and the project")
            self.press(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: not self.menu(js), 5), "the menu is closed")
            grip = f"{box} .msl-hd [data-cgrip='agreed']"
            # The new column re-flows the heading row (and on a slower computer the page scrolls once more), so the grip is aimed at only when the page is quiet
            # and the grip has stood still for two reads; a press at a place the grip has left starts no drag and nothing is written.
            spot = f"(() => {{ const e = document.querySelector({json.dumps(grip)}); if (!e) return null; const b = e.getBoundingClientRect(); return JSON.stringify([b.x, b.y, b.width, b.height]); }})()"
            seen = []
            def still():
                seen.append(js(spot) if js(quiet) else None)
                return len(seen) > 1 and seen[-1] is not None and seen[-1] == seen[-2]
            self.assertTrue(wait(still, 20), "the grip stands still")
            x, y = js(f"(() => {{ const b = document.querySelector({json.dumps(grip)}).getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")
            for t, px, extra in (("mouseMoved", x, {}), ("mousePressed", x, {"button": "left", "buttons": 1, "clickCount": 1}), ("mouseMoved", x + 20, {"buttons": 1}),
                                 ("mouseReleased", x + 20, {"button": "left", "buttons": 0, "clickCount": 1})):
                cdp.call("Input.dispatchMouseEvent", {"type": t, "x": px, "y": y, **extra}, sid)
            self.assertTrue(wait(lambda: "agreed" in (js("localStorage.getItem('clark.cols.msDash')") or ""), 5), "the width is kept under clark.cols.msDash")
            have = json.loads(js(keys))
            self.assertIn("clark.cols.msDash", have, "the width key is there")
            self.assertIn("clark.cols.show.msDash.TUL", have, "the choice key is there")
            self.assertEqual([k for k in have if "milestones" in k], [], "no key of the Milestones page is written")
            self.assertIsNone(js("localStorage.getItem('clark.cols.milestones')"), "the Milestones page's widths are untouched")
            self.assertIsNone(js("localStorage.getItem('clark.cols.show.milestones.TUL')"), "and so is its choice")

    def test_the_work_table_shows_the_id_in_its_own_blue_column_and_not_under_the_title(self):
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work")
            self.assertEqual(self.heads(js, "work"), ["status", "item", "owner", "due", "prio", "id"], "the Id column is shown by default, after Priority")
            got = js("""(() => { const r = document.querySelector('#work tbody tr[data-id]'), c = r.querySelector("td[data-col='id']"), t = r.querySelector('.t');
                return {id: r.dataset.id, cell: c.textContent.trim(), meta: r.querySelector('.meta').textContent, cc: getComputedStyle(c).color, tc: getComputedStyle(t).color, fw: getComputedStyle(c).fontWeight, ws: getComputedStyle(c).whiteSpace}; })()""")
            self.assertEqual(got["cell"], got["id"], "the cell holds the id")
            self.assertNotIn(got["id"], got["meta"], "the id is not under the title")
            self.assertNotEqual(got["cc"], got["tc"], "the id is blue, not the title's colour")
            self.assertEqual((got["fw"], got["ws"]), ("600", "nowrap"), "the id is semi-bold and stays on one line")
            blue = js("(() => { const p = document.createElement('span'); p.style.color = 'var(--link)'; document.body.append(p); const c = getComputedStyle(p).color; p.remove(); return c; })()")
            self.assertEqual(got["cc"], blue, "the id takes the page's link colour")

    def test_the_open_menu_closes_when_the_page_scrolls(self):
        """Row 1276: the settle waits of the other tests exist because a scroll closes the menu; so a scroll must close it (MenuPanel listens to the window)."""
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work")
            self.assertTrue(self.open_menu(cdp, sid, js, "#work th[data-col='owner']"), "the menu opens")
            js("window.dispatchEvent(new Event('scroll'))")
            self.assertTrue(wait(lambda: not self.menu(js), 5), "a scroll of the page closes it")

    def test_the_menu_is_asked_for_again_when_a_late_scroll_closes_the_one_the_first_click_opened(self):
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work")
            clicks = []
            first = self.right_click

            def click_then_scroll_once(cdp, sid, selector):
                first(cdp, sid, selector)
                clicks.append(1)
                if len(clicks) == 1:
                    self.assertTrue(wait(lambda: self.menu(js), 5), "the first click opens it")
                    js("window.dispatchEvent(new Event('scroll'))")
                    self.assertTrue(wait(lambda: not self.menu(js), 5), "and a scroll closes it")
            self.right_click = click_then_scroll_once
            self.assertTrue(self.open_menu(cdp, sid, js, "#work th[data-col='owner']"), "the menu is open in the end")
            self.assertEqual(len(clicks), 2, "after one more right click")
            self.assertIsNotNone(self.menu(js))

    def test_a_right_click_inside_a_text_field_of_the_heading_row_leaves_the_browsers_own_menu_alone(self):
        """Row 1276: typing in a field (copy, paste) keeps the browser's menu; the Columns menu is for the heading itself."""
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work")
            got = js("""(() => { const th = document.querySelector("#work th[data-col='owner']"); const i = document.createElement('input'); th.appendChild(i);
                const ev = new MouseEvent('contextmenu', {bubbles: true, cancelable: true}); i.dispatchEvent(ev); i.remove(); return ev.defaultPrevented; })()""")
            self.assertFalse(got, "the page leaves the event alone")
            self.assertIsNone(self.menu(js), "and opens no Columns menu")

    def test_a_blocked_store_still_lets_the_table_redraw(self):
        block = "Storage.prototype.setItem = function () { throw new Error('blocked'); };"
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work", early=block)
            self.assertTrue(self.open_menu(cdp, sid, js, "#work th[data-col='owner']"))
            self.pick(js, "Type")
            self.assertTrue(wait(lambda: "type" in self.heads(js, "work"), 5), "the table redraws although nothing can be kept")

    def test_the_menu_key_and_shift_f10_open_the_same_menu_from_a_focused_heading(self):
        for table, (_, _, head, _, _, every, _, _) in TABLES.items():
            for how in ("ContextMenu", "F10"):
                with self.subTest(table=table, key=how), chrome() as cdp:
                    sid, js = self.open_table(cdp, 1400, "light", table)
                    focus = "#work th[data-col='owner']" if table == "work" else "#milestones .msl-cols-btn"
                    js(f"document.querySelector({json.dumps(focus)}).focus()")
                    self.press(cdp, sid, how, shift=how == "F10")
                    self.assertTrue(wait(lambda: self.menu(js), 5), "the menu opens from the keyboard")
                    self.assertEqual([i["name"] for i in self.menu(js)["items"]], every)
                    self.assertTrue(js(f"document.activeElement.closest({json.dumps(MENU)}) !== null"), "the focus is in the menu")
                    self.press(cdp, sid, "Escape")
                    self.assertTrue(wait(lambda: not self.menu(js), 5), "Escape closes it")
                    self.assertTrue(js(f"document.activeElement === document.querySelector({json.dumps(focus)})"), "with the focus back where it was")
                    # the page's own key handling, with no native contextmenu event behind it (a browser that sends none for the key)
                    shift = "true" if how == "F10" else "false"
                    js(f"document.querySelector({json.dumps(focus)}).dispatchEvent(new KeyboardEvent('keydown', {{key: {json.dumps(how)}, shiftKey: {shift}, bubbles: true, cancelable: true}}))")
                    self.assertTrue(wait(lambda: self.menu(js), 5), "the key handler opens it on its own too")

    def test_the_work_table_has_a_keyboard_way_in_that_is_not_a_second_tab_stop_of_the_grid(self):
        """The Columns button in the work headings is mouse only (the grid is one tab stop); one more, outside the grid, is reached by Tab and shows when focused."""
        with chrome() as cdp:
            sid, js = self.open_table(cdp, 1400, "light", "work")
            self.assertEqual(js("[...document.querySelectorAll('#work table.items *')].filter((e) => e.tabIndex >= 0 && !e.disabled && !e.closest('tr.grp')).length"), 1, "the grid is still one tab stop")
            js("document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0)")
            for _ in range(60):
                self.press(cdp, sid, "Tab")
                if js("document.activeElement.classList.contains('cols-kbd')"):
                    break
            self.assertTrue(js("document.activeElement.classList.contains('cols-kbd')"), "Tab reaches the Columns button")
            self.assertEqual(js("getComputedStyle(document.activeElement).opacity"), "1", "and it is seen while it has the focus")
            self.press(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: self.menu(js), 5), "Enter opens the menu")
            self.assertEqual(js("document.querySelector('.cols-kbd').getAttribute('aria-expanded')"), "true")
            self.assertEqual(js("document.querySelectorAll('.cols-btn[aria-expanded=true]').length"), 1, "only the button that opened it says so")
            self.press(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: not self.menu(js), 5))
            self.assertTrue(js("document.activeElement.classList.contains('cols-kbd')"), "the focus comes back to it")

    def test_a_visible_columns_button_opens_the_same_menu(self):
        for table, (_, _, _, _, _, every, _, _) in TABLES.items():
            for width in (1400, 900):
                for scheme in ("light", "dark"):
                    with self.subTest(table=table, width=width, scheme=scheme), chrome() as cdp:
                        sid, js = self.open_table(cdp, width, scheme, table)
                        btn = "#work .cols-btn" if table == "work" else "#milestones .msl-cols-btn"
                        got = js(f"""(() => {{ const b = document.querySelector({json.dumps(btn)}), r = b.getBoundingClientRect();
                            return {{tag: b.tagName, name: b.getAttribute('aria-label') || b.textContent.trim(), popup: b.getAttribute('aria-haspopup'), expanded: b.getAttribute('aria-expanded'),
                                     w: r.width, h: r.height, visible: r.width > 0 && getComputedStyle(b).visibility !== 'hidden', hidden: !!b.closest('[aria-hidden=true]'), inwin: r.right <= innerWidth}}; }})()""")
                        self.assertEqual((got["tag"], got["popup"], got["expanded"], got["visible"], got["hidden"], got["inwin"]), ("BUTTON", "menu", "false", True, False, True))
                        self.assertIn("Columns", got["name"])
                        self.assertGreaterEqual(min(got["w"], got["h"]), 24, "a hit area of 24 px at least")
                        js(f"document.querySelector({json.dumps(btn)}).click()")
                        self.assertTrue(wait(lambda: self.menu(js), 5))
                        self.assertEqual([i["name"] for i in self.menu(js)["items"]], every)
                        self.assertEqual(js(f"document.querySelector({json.dumps(btn)}).getAttribute('aria-expanded')"), "true")

    # --- where it is not -------------------------------------------------------------------------------------------------------------

    def test_the_published_page_has_none_of_it(self):
        view = (Path(page.__file__).parent / "page-view.html").read_text(encoding="utf-8")
        for word in ("Show the standard columns", "cols-menu", "cols.show", "msl-cols-btn", "menuitemcheckbox", "data-cols-standard"):
            self.assertNotIn(word, view)

    def test_the_choice_is_not_in_the_data_and_the_excel_export_does_not_read_it(self):
        for py in sorted((Path(page.__file__).parent.parent).glob("*.py")):
            self.assertNotIn("cols.show", py.read_text(encoding="utf-8"), f"{py.name}: the choice is the browser's own, not the project's data")
        excel = (Path(page.__file__).parent.parent / "excel.py").read_text(encoding="utf-8")
        self.assertNotIn("tableColumns", excel)
        self.assertTrue((SRC / "logic" / "columnsWords.js").is_file(), "every new word is listed for a ruling")
        words = (SRC / "logic" / "columnsWords.js").read_text(encoding="utf-8")
        self.assertIn("UNRULED_STANDARD", words)
        self.assertNotIn("export const ", words.replace("export const UNRULED_", "").replace("export const PANEL_HEADING = \"Columns to show\"", ""), "every constant is marked UNRULED, except the one ruled panel heading (row 1499)")
        self.assertIn('export const UNRULED_BUTTON = "Columns"', words, "the button label is unchanged")
        self.assertIn('export const UNRULED_BUTTON_TIP = "Choose the columns"', words, "and so is its tip")


if __name__ == "__main__":
    unittest.main()

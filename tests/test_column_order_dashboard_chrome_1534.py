"""Row 1534 part 3 (Dashboard sections), real Chrome flows at 1400 and 900 px, Classic light and dark: a heading dragged on a Dashboard Work items list (mouse and touch) saves the order
with the project (projects.column_orders) and the page (View) and the published file draw it; a plain click, a drop on the Status or the Item, a drop off the heading row and Esc move nothing;
a heading keeps its chosen width; the built-in Dashboard lists in a half card and in a full card keep head and cells on the same columns; Cards keeps the standard order and has nothing to drag.
The real server and the demo project ABC (fictional); the PM ruling of 26-11: an order set on a Dashboard section is published.

Run: python3 dev/run_tests.py test_column_order_dashboard_chrome_1534
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)
import _testpage as testpage
import test_tpl_workitems as T
from _real_server import real_server
from clark import page, publish, theme
from test_half_cards_1099 import PAIR
from test_item_one_line import Base as OneLine, width as set_width
from test_report_editor import EMPTY_BRANDING, Pg
from test_server import Running, chrome, wait

NAME = "prototype-2.0"
WIDTHS = (1400, 900)
SCHEMES = ("light", "dark")
STANDARD = ["title", "status", "owner", "due", "priority", "id"]      # the list's ids as the headings draw them (the Item first)
HEADS = "[...document.querySelectorAll('[data-id=\"%s\"] .wil-table thead th[data-cw-head]')].map(h => h.dataset.cwHead)"
FILE_HEADS = "[...document.querySelectorAll('[data-id=\"%s\"] .wil-table thead th')].map(h => (h.className.match(/wil-c-(\\w+)/) || [])[1]).filter((c) => c && c !== 'tile' && c !== 'eye')"
CARDS = ["owner", "due", "status", "priority", "id"]      # the order the Cards page has always drawn this list in (its own column order, no saved order)
COLUMNS = ["status", "owner", "due", "priority", "id"]
KEEP_AFTER_ID_ON_OWNER = ["title", "status", "id", "owner", "due", "priority"]
SAVED_ID_ON_OWNER = {"actions": ["status", "item", "id", "owner", "due", "prio"]}
SAVED_PRIO_ON_OWNER = {"actions": ["status", "item", "prio", "owner", "due", "id"]}
ESC = {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}
ALT_SHIFT = 1 | 8


class Base(T.PageBase):
    """Serves the test page with the Classic theme layered (or without it, for Cards) and the demo Work items."""
    classic = True
    add = T.InThePage.add
    show = T.InThePage.show

    def setUp(self):
        super().setUp()
        T.plant(self)
        self.s.close()
        css = theme.css(NAME)
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(testpage.html(), css) if self.classic else testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)

    def put(self, order):
        self.store.con.execute("UPDATE projects SET column_orders = ? WHERE code = 'ABC'", (json.dumps(order) if order else "{}",))
        self.store.con.commit()

    def saved(self):
        con = sqlite3.connect(str(self.store.path))
        try:
            return json.loads(con.execute("SELECT column_orders FROM projects WHERE code = 'ABC'").fetchone()[0] or "{}")
        finally:
            con.close()

    def one(self, order=None):
        """A list of the open Actions with the Status, Owner, Due, Priority and Id columns."""
        self.put(order)
        return self.add({"mode": "all", "kinds": ["action"], "columns": COLUMNS, "owner": ["Pat Demo", "Lee Demo"]})

    def edit(self, cdp, ref, w, scheme):
        p = self.show(cdp, w, dark=scheme == "dark")
        p.edit()
        p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]')", "Edit drew the list")
        p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table').scrollIntoView({{block: 'center'}})")
        p.until("window.scrollY >= 0 && performance.now() > 0", "settled")
        return p

    def where(self, p, ref, col):
        return p.js(f"(() => {{ const r = document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head={col}]').getBoundingClientRect(); return [r.left + 14, r.top + r.height / 2]; }})()")

    def drag(self, p, ref, src, dst, release=True, steps=10):
        (x0, y0), (x1, y1) = self.where(p, ref, src), self.where(p, ref, dst)
        p.mouse("mouseMoved", x0, y0)
        p.mouse("mousePressed", x0, y0, buttons=1)
        for i in range(1, steps + 1):
            p.mouse("mouseMoved", x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps, buttons=1)
        if release:
            p.mouse("mouseReleased", x1, y1, buttons=1)

    def touch(self, p, ref, src, dst):
        p.cdp.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1}, p.sid)
        (x0, y0), (x1, y1) = self.where(p, ref, src), self.where(p, ref, dst)
        p.cdp.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0, "id": 1}]}, p.sid)
        for i in range(1, 9):
            p.cdp.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / 8, "y": y0 + (y1 - y0) * i / 8, "id": 1}]}, p.sid)
        p.cdp.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}, p.sid)

    def unchanged(self, p, ref, order):
        """Nothing moved: the headings, and (after the page has had its turn) the saved order."""
        p.js("window.__turn = 0; setTimeout(() => { window.__turn = 1; }, 300)")
        p.until("window.__turn === 1", "the page had its turn")
        self.assertEqual(p.js(HEADS % ref), STANDARD)
        self.assertEqual(self.saved(), order or {})
        self.assertEqual(p.js("document.querySelectorAll('.col-dragging, .col-drop-before, .col-drop-after').length"), 0, "no drag mark is left")


class Drag(Base):
    def test_a_mouse_drag_saves_the_order_and_the_page_and_the_published_file_draw_it(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), T.chrome() as cdp:
                    ref = self.one()
                    p = self.edit(cdp, ref, w, scheme)
                    self.assertEqual(p.js(HEADS % ref), STANDARD)
                    self.drag(p, ref, "id", "owner")
                    p.until(f"({HEADS % ref}).join() === {json.dumps(KEEP_AFTER_ID_ON_OWNER)}.join()", f"the headings moved: {p.js(HEADS % ref)}")
                    self.assertTrue(wait(lambda: self.saved() == SAVED_ID_ON_OWNER, 10), f"saved with the project: {self.saved()}")
                    self.assertEqual(p.js("document.querySelectorAll('.col-dragging, .col-drop-before, .col-drop-after').length"), 0, "no drag mark after the drop")
                    self.assertEqual(p.js(f"[...document.querySelector('[data-id=\"{ref}\"] .wil-table tbody tr').children].map((e) => (e.className.match(/wil-c-(\\w+)/) || [])[1]).filter((c) => c && c !== 'tile' && c !== 'eye' && c !== 'type')"),
                                     KEEP_AFTER_ID_ON_OWNER, "the cells follow the headings")
                    p.view()
                    p.until(f"({FILE_HEADS % ref}).join() === {json.dumps(KEEP_AFTER_ID_ON_OWNER)}.join()", "View draws the saved order")
                    self.published(ref, w, scheme, KEEP_AFTER_ID_ON_OWNER)

    def published(self, ref, w, scheme, want):
        """The published file draws the order set on the Dashboard section."""
        out = tempfile.mkdtemp(prefix="clark-1534-p3-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=T.USER, now=T.TODAY, branding=T.EMPTY_BRANDING)["path"])
        with T.chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            f = Pg(self, cdp, sid)
            f.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
            if scheme == "dark":
                f.js("document.documentElement.dataset.theme = 'dark'")
            self.assertTrue(f.js("!!document.getElementById('theme')"), "the file is Classic")
            f.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table thead th')", "the list drew")
            self.assertEqual(f.js(FILE_HEADS % ref), want, "the published list draws the saved order")
            self.assertEqual(f.js(f"document.querySelectorAll('[data-id=\"{ref}\"] .wil-table thead [draggable=true], [data-id=\"{ref}\"] .wil-table thead [data-move]').length"), 0, "a file has nothing to drag")

    def test_a_touch_drag_moves_a_heading_like_a_mouse_drag(self):
        for w, scheme in ((1400, "light"), (900, "dark")):
            with self.subTest(width=w, scheme=scheme), T.chrome() as cdp:
                ref = self.one()
                p = self.edit(cdp, ref, w, scheme)
                self.touch(p, ref, "priority", "owner")
                p.until(f"({HEADS % ref}).join() === {json.dumps(['title', 'status', 'priority', 'owner', 'due', 'id'])}.join()", f"a touch drag moves it: {p.js(HEADS % ref)}")
                self.assertTrue(wait(lambda: self.saved() == SAVED_PRIO_ON_OWNER, 10), f"saved with the project: {self.saved()}")

    def test_a_plain_click_a_drop_on_the_status_or_item_a_drop_off_the_row_and_esc_move_nothing(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), T.chrome() as cdp:
                    ref = self.one()
                    p = self.edit(cdp, ref, w, scheme)
                    x, y = self.where(p, ref, "owner")      # a plain click
                    p.mouse("mouseMoved", x, y)
                    p.mouse("mousePressed", x, y, buttons=1)
                    p.mouse("mouseReleased", x, y, buttons=1)
                    self.unchanged(p, ref, None)
                    self.drag(p, ref, "priority", "title")      # the Item takes no drop
                    self.unchanged(p, ref, None)
                    self.drag(p, ref, "priority", "status")      # nor the Status
                    self.unchanged(p, ref, None)
                    self.drag(p, ref, "status", "owner")      # the Status is not dragged
                    self.unchanged(p, ref, None)
                    (x0, y0) = self.where(p, ref, "priority")      # a drop off the heading row
                    p.mouse("mouseMoved", x0, y0)
                    p.mouse("mousePressed", x0, y0, buttons=1)
                    for i in range(1, 9):
                        p.mouse("mouseMoved", x0, y0 + 40 * i, buttons=1)
                    p.mouse("mouseReleased", x0, y0 + 320, buttons=1)
                    self.unchanged(p, ref, None)
                    self.drag(p, ref, "id", "owner", release=False)      # Esc during a drag cancels it
                    p.until("!!document.querySelector('.col-dragging') && !!document.querySelector('.col-drop-before')", "the drag shows its drop place")
                    p.cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **ESC}, p.sid)
                    p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **ESC}, p.sid)
                    p.until("document.querySelectorAll('.col-dragging, .col-drop-before').length === 0", "Esc took the drag away")
                    x1, y1 = self.where(p, ref, "owner")
                    p.mouse("mouseReleased", x1, y1, buttons=1)
                    self.unchanged(p, ref, None)

    def test_a_dragged_heading_keeps_its_chosen_width(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), T.chrome() as cdp:
                    ref = self.one()
                    p = self.edit(cdp, ref, w, scheme)
                    widths = f"(() => {{ const o = {{}}; document.querySelectorAll('[data-id=\"{ref}\"] .wil-table thead th[data-cw-head]').forEach((h) => {{ o[h.dataset.cwHead] = Math.round(h.getBoundingClientRect().width); }}); return o; }})()"
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]').focus()")
                    for _ in range(3):      # Ctrl with the Right arrow widens the focused heading
                        p.cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39, "modifiers": 2}, p.sid)
                        p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "ArrowRight", "code": "ArrowRight", "windowsVirtualKeyCode": 39, "modifiers": 2}, p.sid)
                    wide = p.js(widths)
                    self.assertTrue(wait(lambda: p.js(widths) == wide, 5))
                    self.drag(p, ref, "owner", "priority")
                    p.until(f"({HEADS % ref}).indexOf('owner') > ({HEADS % ref}).indexOf('priority')", "the owner moved")
                    p.js("window.__turn = 0; setTimeout(() => { window.__turn = 1; }, 300)")
                    p.until("window.__turn === 1", "the page had its turn")
                    now = p.js(widths)
                    for col in wide:
                        self.assertLessEqual(abs(now[col] - wide[col]), 1, f"{col} kept its width: {wide} -> {now}")


class Keys(Base):
    """AP2 on the Dashboard: Alt+Shift+Left and Alt+Shift+Right move the focused heading of a list of one type, the move is said in the list's own live line
    (counting every drawn column, the Item and the Status included) and saved with the project; Alt with an arrow, the key the heading's label names, moves it too."""
    LIVE = "document.querySelector('[data-id=\"%s\"] [data-wil-live]').textContent"
    OWNER_RIGHT = ["title", "status", "due", "owner", "priority", "id"]

    def arrow(self, p, name, modifiers=ALT_SHIFT):
        common = {"key": name, "code": name, "windowsVirtualKeyCode": {"ArrowLeft": 37, "ArrowRight": 39}[name], "modifiers": modifiers}
        p.cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common}, p.sid)
        p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, p.sid)

    def test_alt_shift_arrows_move_a_dashboard_heading_announce_it_and_save_it_with_the_project(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), T.chrome() as cdp:
                    ref = self.one()
                    p = self.edit(cdp, ref, w, scheme)
                    live = self.LIVE % ref
                    self.assertEqual(p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-wil-live]').getAttribute('aria-live')"), "polite")
                    self.assertEqual(p.js(live), "", "nothing is said before a move")
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]').focus()")
                    self.arrow(p, "ArrowRight")
                    p.until(f"({HEADS % ref}).join() === {json.dumps(self.OWNER_RIGHT)}.join()", f"Alt+Shift+Right moved the Owner: {p.js(HEADS % ref)}")
                    self.assertEqual(p.js(live), "Owner moved to position 4 of 6")
                    self.assertTrue(wait(lambda: self.saved() == {"actions": ["status", "item", "due", "owner", "prio", "id"]}, 10), f"saved with the project: {self.saved()}")
                    p.until("document.activeElement.dataset.cwHead === 'owner'", "the heading keeps the focus")
                    self.arrow(p, "ArrowLeft")
                    p.until(f"({HEADS % ref}).join() === {json.dumps(STANDARD)}.join()", f"Alt+Shift+Left moved it back: {p.js(HEADS % ref)}")
                    self.assertEqual(p.js(live), "Owner moved to position 3 of 6")
                    self.assertTrue(wait(lambda: self.saved() == {}, 10), f"the standard order is saved as nothing: {self.saved()}")
                    p.until("document.activeElement.dataset.cwHead === 'owner'", "the heading keeps the focus")
                    self.arrow(p, "ArrowLeft")      # beside the Status: as far left as it may go
                    self.unchanged(p, ref, None)
                    self.assertEqual(p.js(live), "Owner moved to position 3 of 6", "nothing new is said")
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]').focus()")
                    self.arrow(p, "ArrowRight", modifiers=1)      # Alt with an arrow, the key the heading's label names (row 1195), still moves it, and now saves it with the project
                    p.until(f"({HEADS % ref}).join() === {json.dumps(self.OWNER_RIGHT)}.join()", f"Alt+Right moved the Owner: {p.js(HEADS % ref)}")
                    self.assertEqual(p.js(live), "Owner moved to position 4 of 6")
                    self.arrow(p, "ArrowLeft", modifiers=1)
                    p.until(f"({HEADS % ref}).join() === {json.dumps(STANDARD)}.join()", f"Alt+Left moved it back: {p.js(HEADS % ref)}")
                    self.assertTrue(wait(lambda: self.saved() == {}, 10), f"saved: {self.saved()}")
                    self.unchanged(p, ref, None)
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=status]').focus()")      # the Status and the Item are not moved by key
                    self.arrow(p, "ArrowRight")
                    self.unchanged(p, ref, None)
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=title]').focus()")
                    self.arrow(p, "ArrowRight")
                    self.unchanged(p, ref, None)


class BlockedStore(Base):
    """AP6 on the Dashboard: with the browser store blocked (a private window) the list draws the standard order, or the order saved with the project, with no error,
    and a move is still saved: the order of a list of one type needs no browser store."""
    BLOCK = ("window.__errs = []; addEventListener('error', (e) => { window.__errs.push(String(e.message)); }); addEventListener('unhandledrejection', (e) => { window.__errs.push(String(e.reason)); });"
             " Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }});")
    IS_BLOCKED = "(() => { try { void window.localStorage; return false; } catch (e) { return true; } })()"

    def blocked(self, cdp, ref, w, scheme):
        p = self.show(cdp, w, dark=scheme == "dark")
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.BLOCK}, p.sid)
        p.reload()
        if scheme == "dark":
            p.js("document.documentElement.dataset.theme = 'dark'")
        self.assertTrue(p.js(self.IS_BLOCKED), "the browser store is blocked")
        p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table thead th')", "the list drew")
        return p

    def test_a_blocked_browser_store_draws_the_standard_or_the_saved_order_without_an_error(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), T.chrome() as cdp:
                    ref = self.one()
                    p = self.blocked(cdp, ref, w, scheme)
                    self.assertEqual(p.js(FILE_HEADS % ref), STANDARD, "nothing saved: the standard order")
                    p.edit()
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]')", "Edit drew the list")
                    self.assertEqual(p.js(HEADS % ref), STANDARD)
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table').scrollIntoView({{block: 'center'}})")
                    self.drag(p, ref, "id", "owner")
                    p.until(f"({HEADS % ref}).join() === {json.dumps(KEEP_AFTER_ID_ON_OWNER)}.join()", f"a drag still moves the heading: {p.js(HEADS % ref)}")
                    self.assertTrue(wait(lambda: self.saved() == SAVED_ID_ON_OWNER, 10), f"saved with the project, not in the browser: {self.saved()}")
                    self.assertEqual(p.js("window.__errs"), [], "no error")
                with self.subTest(width=w, scheme=scheme, saved=True), T.chrome() as cdp:      # a new browser with a blocked store: the saved order is the project's
                    p = self.blocked(cdp, ref, w, scheme)
                    self.assertEqual(p.js(FILE_HEADS % ref), KEEP_AFTER_ID_ON_OWNER, "the order saved with the project is drawn")
                    self.assertEqual(p.js("window.__errs"), [], "no error")


class Cards(Base):
    classic = False

    def test_cards_keeps_the_standard_order_and_has_nothing_to_drag(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), T.chrome() as cdp:
                    ref = self.one(SAVED_PRIO_ON_OWNER)
                    p = self.show(cdp, w, dark=scheme == "dark")
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table thead th')", "the list drew")
                    self.assertFalse(p.js("!!document.getElementById('theme')"), "the Cards page")
                    self.assertEqual([c for c in p.js(FILE_HEADS % ref) if c != "title"], CARDS, "Cards ignores the saved order")
                    p.edit()
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table th[data-cw-head=owner]')", "Edit drew the list")
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] .wil-table').scrollIntoView({{block: 'center'}})")
                    self.assertEqual(p.js("document.querySelectorAll('.wil-table th[data-move]').length"), 0, "nothing the new drag can take")
                    self.assertEqual([c for c in p.js(HEADS % ref) if c != "title"], CARDS)
                    self.assertEqual(self.saved(), SAVED_PRIO_ON_OWNER, "nothing was written")


class HalfCard(OneLine):
    """The built-in Dashboard lists draw the order saved for their type; in a half card and at 900 px the cells and the heading sit exactly where they sit with no saved order, and in a wide full card they follow it."""
    ORDER = {"actions": ["status", "item", "prio", "owner", "due", "id"], "risks": ["status", "item", "prio", "owner", "due", "id"]}
    SAVED = ["c-ico", "wl-title", "c-prio", "c-owner", "c-date", "c-id"]
    BOXES = ("(sec, part) => Object.fromEntries([...document.querySelector('.sec[data-type=' + sec + '] ' + part).children].map((e) => { const b = e.getBoundingClientRect();"
             " return [e.className.split(' ').find((c) => /^(c-|wl-title)/.test(c)) || e.textContent.trim(), [Math.round(b.x), Math.round(b.y), Math.round(b.width), Math.round(b.height)]]; }))")

    def set(self, order):
        self.store.con.execute("UPDATE projects SET column_orders = ? WHERE code = 'ABC'", (json.dumps(order),))
        self.store.con.commit()

    def served(self):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING, theme=NAME))
        self.addCleanup(s.close)
        return s

    def setUp(self):
        super().setUp()
        self.demo.plant_builtin_sections(project="ABC")

    def pass_(self, order):
        """Every section, view and edit, card and half card, width and scheme: the boxes of the heading and of the first row."""
        self.set(order)
        got = {}
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            self.assertTrue(p.js("!!document.getElementById('theme')"), "Classic")
            for half in (False, True):
                if half:
                    p.js(PAIR)
                for mode in ("view", "edit"):
                    if mode == "edit":
                        p.edit()
                    for w in WIDTHS:
                        set_width(cdp, p.sid, w)
                        for scheme in SCHEMES:
                            p.js(f"document.documentElement.setAttribute('data-theme', '{scheme}')")
                            for sec in ("raid", "actions"):
                                where = f"{'half' if half else 'full'} {mode} {w} {scheme} {sec}"
                                p.until(f"!!document.querySelector('.sec[data-type={sec}] .wl-row') && document.fonts.status === 'loaded'", where)
                                got[where] = {"card": p.js(f"document.querySelector('.sec[data-type={sec}]').getBoundingClientRect().width"),
                                              "head": p.js(f"({self.BOXES})('{sec}', '.wl-head')"), "row": p.js(f"({self.BOXES})('{sec}', '.wl-row')"),
                                              "side": p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth")}
                    p.js("document.documentElement.setAttribute('data-theme', 'light')")
        return got

    def test_full_and_half_cards_keep_each_heading_over_its_cells_at_1400_and_900(self):
        saved, standard = self.pass_(self.ORDER), self.pass_({})
        self.assertEqual(set(saved), set(standard))
        wide_seen = 0
        for where, now in saved.items():
            was = standard[where]
            self.assertLessEqual(now["side"], 0, f"{where}: page scrolls sideways")
            wide = " 1400 " in where and (where.startswith("full") or now["card"] > 700)
            if not wide:      # 900 px and a half card: nothing moved from its standard place
                self.assertEqual(now["row"], was["row"], f"{where}: the cells keep their standard places (card {now['card']:.0f} px)")
                self.assertEqual(now["head"], was["head"], f"{where}: the heading keeps its standard places")
                continue
            wide_seen += 1
            by_x = lambda boxes: [k for k, v in sorted(boxes.items(), key=lambda kv: kv[1][0])]
            self.assertEqual(by_x(now["row"]), self.SAVED, f"{where}: the cells in the saved order")
            self.assertEqual(by_x({k: v for k, v in now["head"].items() if v[2] > 1}), [c for c in by_x(now["head"]) if now["head"][c][2] > 1])
            for k, h in now["head"].items():      # each heading word is over the cell it names: same left edge, same width
                if h[2] > 1 and k in now["row"]:
                    self.assertLessEqual(abs(h[0] - now["row"][k][0]), 2, f"{where}: the heading {k} is over its cells")
                    self.assertLessEqual(abs(h[2] - now["row"][k][2]), 2, f"{where}: the heading {k} is as wide as its cells")
        self.assertGreater(wide_seen, 0, "a wide card was measured")


class PublishedBuiltIn(OneLine):
    """AP5: the published report draws the built-in Dashboard lists in the order saved for their type; a type with nothing saved keeps the standard order; a file has no Id column and nothing to drag."""
    ORDER = {"actions": ["status", "item", "prio", "owner", "due", "id"]}
    NAMES = ("(sec, part) => [...document.querySelector('.sec[data-type=' + sec + '] ' + part).children].map((e) => (e.className.match(/\\bc-(ico|title|owner|date|prio|id)\\b/) || [])[1])")

    def test_column_order_is_published_in_the_dashboard_lists_of_the_report(self):
        self.store.con.execute("UPDATE projects SET column_orders = ? WHERE code = 'ABC'", (json.dumps(self.ORDER),))
        self.store.con.commit()
        path = self.published()
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                    sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                    f = Pg(self, cdp, sid)
                    f.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('.sec[data-type=actions] .wl-row') && !!document.querySelector('.sec[data-type=raid] .wl-row')", "the file drew its lists")
                    if scheme == "dark":
                        f.js("document.documentElement.dataset.theme = 'dark'")
                    self.assertTrue(f.js("!!document.getElementById('theme')"), "the file is Classic")
                    for part in (".wl-head", ".wl-row"):
                        self.assertEqual(f.js(f"({self.NAMES})('actions', '{part}')"), ["ico", "title", "prio", "owner", "date"], f"Open actions {part}: the saved order, no Id")
                        self.assertEqual(f.js(f"({self.NAMES})('raid', '{part}')"), ["ico", "title", "owner", "date", "prio"], f"Risks and issues {part}: its own (the standard) order")
                    self.assertTrue(f.js("document.querySelector('.sec[data-type=actions] .irows').hasAttribute('data-ord')"))
                    self.assertFalse(f.js("document.querySelector('.sec[data-type=raid] .irows').hasAttribute('data-ord')"), "the standard order adds nothing to the markup")
                    self.assertEqual(f.js("document.querySelectorAll('[data-move], [data-colmove], [draggable=true], [data-wil-live]').length"), 0, "a file has nothing to drag and no edit-only hook")

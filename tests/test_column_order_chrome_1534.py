"""Row 1534 (Work items table UI), real Chrome flows at 1400 and 900 px, Classic light and dark: a heading dragged to a new place (header and rows move, a plain click moves nothing), Alt+Shift+Left/Right moves a column and says '<Column> moved to position <N> of <M>' (N and M count every drawn column, Status and Item included: PM ruling
26-11), Status first and Item second kept, the Columns menu lists the table order as tick lines only (no Move or Reset line: the row 1499 pick 7B ruling), All is not movable, and a
blocked browser store draws the standard order. The real server and the demo project TUL (fictional); the order is saved with the project (projects.column_orders).

Run: python3 dev/run_tests.py test_column_order_chrome_1534
"""
import json
import shutil
import sqlite3
import unittest
from unittest import mock

from _real_server import real_server
from clark import page, server as sv
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_table_columns import SETTLE, MENU
from test_work_items import FIXED_DATE, load_demo, page_target

STANDARD = ["status", "item", "owner", "due", "prio", "id"]
SAVED = ["status", "item", "due", "owner", "prio", "id"]
ALT_SHIFT = 1 | 8
HEADS = "[...document.querySelectorAll('#work table.items thead th[data-col]')].map((e) => e.dataset.col)"
UNIQ = "[...new Set(" + HEADS + ")]"      # the Cards page at 900 px draws a second, narrow heading row: each column once
ROW = "(() => { const r = document.querySelector('#work tbody tr[data-id]'); return [...r.querySelectorAll('td[data-col], td.c-status, td.c-item')].map((e) => e.dataset.col || (e.classList.contains('c-status') ? 'status' : 'item')); })()"
LIVE = "document.getElementById('work-live').textContent"
WIDTHS = (1400, 900)
SCHEMES = ("light", "dark")


class Base(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = None
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def put(self):
        con = sqlite3.connect(str(self.path))
        con.execute("UPDATE projects SET column_orders = ? WHERE code = 'TUL'", (json.dumps(self.seed),))
        con.commit()
        con.close()

    def serve(self, order=None, theme="prototype-2.0"):
        self.seed = order or {}      # every sub-test starts from this saved order again (a move is saved with the project)
        self.put()
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}],
                             page_html=lambda: page.page_html(EMPTY_BRANDING, theme=theme))
        self.addCleanup(self.s.close)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def saved(self):
        con = sqlite3.connect(str(self.path))
        try:
            return json.loads(con.execute("SELECT column_orders FROM projects WHERE code = 'TUL'").fetchone()[0] or "{}")
        finally:
            con.close()

    def opened(self, cdp, width, scheme, kind="action", before="", classic=True, more=""):
        self.put()
        sid = page_target(cdp)
        for m, p in (("Page.enable", {}), ("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}),
                     ("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}), ("Emulation.setFocusEmulationEnabled", {"enabled": True})):
            cdp.call(m, p, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": before + FIXED_DATE + SETTLE}, sid)
        f = "mode:all" + (";type:" + kind if kind != "all" else "") + more
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f={f}"}, sid)
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        self.assertTrue(wait(lambda: js("document.querySelectorAll('#work tbody tr[data-id]').length > 0 && document.querySelectorAll('#work table.items thead th').length > 0"), 20), "the table is drawn")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#work .cols-btn') && document.fonts.status === 'loaded' && performance.now() - window.__lastScroll > 700"), 20), "settled")
        self.assertEqual(js("!!document.getElementById('theme')"), classic, "the look asked for")
        return sid, js

    def mouse(self, cdp, sid, kind, x, y, **kw):
        cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": kw.pop("button", "none"), "buttons": kw.pop("buttons", 0), "clickCount": kw.pop("clickCount", 0), **kw}, sid)

    def centre(self, js, col):
        return js(f"(() => {{ const b = document.querySelector(\"#work th[data-col='{col}']\").getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")

    def drag(self, cdp, sid, js, src, dst, release=True):
        (x0, y0), (x1, y1) = self.centre(js, src), (dst if isinstance(dst, (list, tuple)) else self.centre(js, dst))
        self.mouse(cdp, sid, "mouseMoved", x0, y0)
        self.mouse(cdp, sid, "mousePressed", x0, y0, button="left", buttons=1, clickCount=1)
        for i in range(1, 9):
            self.mouse(cdp, sid, "mouseMoved", x0 + (x1 - x0) * i / 8, y0 + (y1 - y0) * i / 8, buttons=1)
        if release:
            self.mouse(cdp, sid, "mouseReleased", x1, y1, button="left", clickCount=1)

    def frames(self, js):
        """settle condition: two animation frames have run since now (a no-change check reads the page after the page had its turn)."""
        js("window.__frames = 0; requestAnimationFrame(() => requestAnimationFrame(() => { window.__frames = 1; }))")
        self.assertTrue(wait(lambda: js("window.__frames === 1"), 5), "two frames ran")

    def quiet(self, js):
        """settle condition: no drag mark is left on any heading, then two frames."""
        self.assertTrue(wait(lambda: js("document.querySelectorAll('#work th.col-dragging, #work th.col-drop-before, #work th.col-drop-after').length === 0"), 5), "the drag marks are gone")
        self.frames(js)

    def below(self, js):
        """a point inside the first body row (off the header row)."""
        return js("(() => { const b = document.querySelector('#work tbody tr[data-id] td[data-col]').getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })()")

    def esc(self, cdp, sid):
        common = {"key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}
        cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)

    def click(self, cdp, sid, js, col):
        x, y = self.centre(js, col)
        self.mouse(cdp, sid, "mouseMoved", x, y)
        self.mouse(cdp, sid, "mousePressed", x, y, button="left", buttons=1, clickCount=1)
        self.mouse(cdp, sid, "mouseReleased", x, y, button="left", clickCount=1)

    def arrow(self, cdp, sid, name):
        vk = {"ArrowLeft": 37, "ArrowRight": 39}[name]
        common = {"key": name, "code": name, "windowsVirtualKeyCode": vk, "modifiers": ALT_SHIFT}
        cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)

    def menu(self, cdp, sid, js, col):
        x, y = self.centre(js, col)
        for t in ("mousePressed", "mouseReleased"):
            self.mouse(cdp, sid, t, x, y, button="right", buttons=2 if t == "mousePressed" else 0, clickCount=1)
        self.assertTrue(wait(lambda: js(f"!!document.querySelector({json.dumps(MENU)})"), 5), "the menu opens")
        seen = []

        def still():
            seen.append(js(f"JSON.stringify(document.querySelector({json.dumps(MENU)}).getBoundingClientRect())"))
            return len(seen) > 1 and seen[-1] == seen[-2]
        self.assertTrue(wait(still, 5), "the menu stops moving")

    def press(self, js, attr):
        js(f"document.querySelector({json.dumps(MENU + ' [' + attr + ']')}).click()")

    def where(self, js):
        return js(HEADS), js(ROW)


class Moves(Base):
    def test_drag_a_heading_moves_header_and_rows_and_a_plain_click_moves_nothing(self):
        self.serve()
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme)
                    self.assertEqual(js(HEADS), STANDARD)
                    self.drag(cdp, sid, js, "prio", "owner", release=False)
                    self.assertTrue(js("!!document.querySelector('#work th.col-dragging') && !!document.querySelector('#work th.col-drop-before')"), "the drop place is shown while dragging")
                    self.mouse(cdp, sid, "mouseReleased", *self.centre(js, "owner"), button="left", clickCount=1)
                    want = ["status", "item", "prio", "owner", "due", "id"]
                    self.assertTrue(wait(lambda: js(HEADS) == want, 5), f"header moved: {js(HEADS)}")
                    self.assertEqual(js(ROW), want, "the cells moved with the header")
                    self.assertEqual(js("document.querySelector('#work th.col-dragging, #work th.col-drop-before, #work th.col-drop-after')"), None)
                    self.assertTrue(wait(lambda: self.saved().get("actions") == want, 5), f"saved with the project: {self.saved()}")
                    self.assertIn("moved to position 3 of 6", js(LIVE))
                    # the click that ended the drag is swallowed: nothing else happened; a plain click on a heading changes no order and saves nothing
                    self.assertEqual(js("document.querySelectorAll('#work th[aria-sort]').length"), 0, "the drop did not sort")
                    saved = self.saved()
                    self.click(cdp, sid, js, "due")
                    self.quiet(js)
                    self.assertEqual(js(HEADS), want, "a plain click moves nothing")
                    self.assertEqual(self.saved(), saved, "and saves nothing")
                    self.assertEqual(js("document.querySelectorAll('#work th.col-dragging, #work th.col-drop-before, #work th.col-drop-after').length"), 0)

    def test_the_drop_place_is_drawn_on_the_side_of_the_heading_it_would_land_beside(self):
        self.serve()
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme)
                    probe = ("(() => { const t = document.querySelector('#work th.%s'); if (!t) return null; const i = document.createElement('i'); i.style.color = 'var(--brand-blue)'; document.body.appendChild(i);"
                             " const blue = getComputedStyle(i).color; i.remove(); return {col: t.dataset.col, shadow: getComputedStyle(t).boxShadow, blue}; })()")
                    # Priority dragged left onto Owner: the bar is on Owner's left side (before)
                    self.drag(cdp, sid, js, "prio", "owner", release=False)
                    b = js(probe % "col-drop-before")
                    self.assertEqual(b["col"], "owner")
                    self.assertIn(b["blue"], b["shadow"], "the bar is the brand blue")
                    self.assertIn("inset", b["shadow"])
                    self.assertTrue(b["shadow"].rstrip().endswith("3px 0px 0px 0px inset") or " 3px 0px 0px 0px" in b["shadow"], f"3px on the left: {b['shadow']}")
                    self.assertEqual(js("getComputedStyle(document.querySelector('#work th.col-dragging')).opacity"), "0.55")
                    self.mouse(cdp, sid, "mouseReleased", *self.centre(js, "owner"), button="left", clickCount=1)
                    self.assertTrue(wait(lambda: js(HEADS)[2] == "prio", 5))
                    # Due dragged left to the right of... Owner (now 3rd) dragged right onto Id: the bar is on Id's right side (after)
                    self.drag(cdp, sid, js, "owner", "id", release=False)
                    a = js(probe % "col-drop-after")
                    self.assertEqual(a["col"], "id")
                    self.assertTrue(" -3px 0px 0px 0px" in a["shadow"], f"3px on the right: {a['shadow']}")
                    self.assertIn(a["blue"], a["shadow"])
                    self.mouse(cdp, sid, "mouseReleased", *self.centre(js, "id"), button="left", clickCount=1)
                    self.assertTrue(wait(lambda: js(HEADS)[-1] == "owner", 5), js(HEADS))
                    self.assertEqual(js("document.querySelectorAll('#work th.col-dragging, #work th.col-drop-before, #work th.col-drop-after').length"), 0, "the marks are gone after the drop")

    def test_a_heading_keeps_its_width_after_a_move(self):
        self.serve()
        W = "Object.fromEntries([...document.querySelectorAll('#work table.items thead th[data-col]')].map((e) => [e.dataset.col, Math.round(e.getBoundingClientRect().width)]))"
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme)
                    was = js(W)
                    self.drag(cdp, sid, js, "prio", "owner")
                    self.assertTrue(wait(lambda: js(HEADS)[2] == "prio", 5))
                    self.quiet(js)
                    now = js(W)
                    self.assertEqual(set(now), set(was))
                    for col in was:
                        self.assertLessEqual(abs(now[col] - was[col]), 1, f"{col} kept its width: {was} -> {now}")
                    js("document.querySelector(\"#work th[data-col='due']\").focus()")
                    self.arrow(cdp, sid, "ArrowLeft")
                    self.assertTrue(wait(lambda: js(HEADS)[3] == "due", 5))
                    self.quiet(js)
                    again = js(W)
                    for col in was:
                        self.assertLessEqual(abs(again[col] - was[col]), 1, f"{col} kept its width after a key move: {was} -> {again}")

    def test_the_eye_and_hand_over_columns_neither_move_nor_count(self):
        """WorkItems.jsx:217 (the Hand over pick column, first) and :219 (the eye column, last) are controls: not draggable, not moved, not counted in N or M."""
        self.serve({"actions": SAVED})
        owner = next(r["owner"] for r in self.read("TUL")["actions"] if r.get("owner"))
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme, more=";owner:" + owner.replace(" ", "%20"))
                    self.assertTrue(js("!!document.querySelector('#hand-over')"), "Hand over is offered for an owner")
                    js("document.querySelector('#hand-over').click()")
                    self.assertTrue(wait(lambda: js("!!document.querySelector('#work th.c-pick')"), 5), "the pick column is drawn")
                    cells = "[...document.querySelectorAll('#work table.items thead th')].map((e) => e.dataset.col || e.className.split(' ')[0]).filter(Boolean)"
                    got = js(cells)
                    self.assertEqual(got[0], "c-pick", got)
                    self.assertEqual(got[-1], "c-eye", got)
                    self.assertEqual(got[1:-1], SAVED, "the pick column leads and the eye column ends the saved order")
                    self.assertEqual(js("document.querySelectorAll('#work th.c-pick[data-colmove], #work th.c-eye[data-colmove]').length"), 0, "neither is draggable")
                    js("document.querySelector(\"#work th[data-col='owner']\").focus()")
                    self.arrow(cdp, sid, "ArrowLeft")
                    self.assertTrue(wait(lambda: js(HEADS)[2] == "owner", 5), js(HEADS))
                    self.assertEqual(js(LIVE), "Owner moved to position 3 of 6", "the controls are not counted")
                    got = js(cells)
                    self.assertEqual((got[0], got[-1]), ("c-pick", "c-eye"))
                    self.drag(cdp, sid, js, "prio", "id")           # a drop beside the controls moves only data columns
                    self.assertTrue(wait(lambda: js(HEADS)[-1] == "prio", 5), js(HEADS))
                    got = js(cells)
                    self.assertEqual((got[0], got[-1]), ("c-pick", "c-eye"))

    def test_touch_drag_moves_a_heading(self):
        self.serve()
        for w, scheme in ((1400, "light"), (900, "dark")):
            with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                sid, js = self.opened(cdp, w, scheme)
                cdp.call("Emulation.setTouchEmulationEnabled", {"enabled": True, "maxTouchPoints": 1}, sid)
                (x0, y0), (x1, y1) = self.centre(js, "prio"), self.centre(js, "owner")
                cdp.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0, "id": 1}]}, sid)
                for i in range(1, 9):
                    cdp.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / 8, "y": y0, "id": 1}]}, sid)
                cdp.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}, sid)
                self.assertTrue(wait(lambda: js(HEADS) == ["status", "item", "prio", "owner", "due", "id"], 5), f"a touch drag moves it: {js(HEADS)}")

    def test_cards_keeps_the_standard_order_and_cannot_move(self):
        self.serve({"actions": SAVED}, theme=None)
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme, classic=False)
                    self.assertEqual(js(UNIQ), STANDARD, "Cards ignores the saved order")
                    self.assertEqual(js(ROW), STANDARD)
                    self.assertEqual(js("document.querySelectorAll('#work th[data-colmove]').length"), 0)
                    js("document.querySelector(\"#work th[data-col='owner']\").focus()")
                    self.arrow(cdp, sid, "ArrowRight")
                    self.frames(js)
                    self.assertEqual(js(UNIQ), STANDARD)
                    self.assertEqual(self.saved(), {"actions": SAVED})

    def test_a_drop_off_the_header_row_or_on_status_or_item_is_cancelled_and_nothing_is_saved(self):
        """Status and Item are not drop targets: no drop bar, the drop cancels, the order stays whole and nothing is saved."""
        self.serve()
        for w in WIDTHS:
            for scheme in SCHEMES:
                for name in ("off the header row", "Status", "Item"):
                    with self.subTest(width=w, scheme=scheme, drop=name), chrome() as cdp:
                        sid, js = self.opened(cdp, w, scheme)
                        self.assertEqual(self.saved(), {})
                        dst = self.below(js) if name.startswith("off") else self.centre(js, name.lower())
                        self.drag(cdp, sid, js, "prio", dst, release=False)
                        self.assertTrue(js("!!document.querySelector('#work th.col-dragging')"), "the drag is in progress")
                        self.assertEqual(js("document.querySelectorAll('#work th.col-drop-before, #work th.col-drop-after').length"), 0, "no drop bar is drawn")
                        self.mouse(cdp, sid, "mouseReleased", *dst, button="left", clickCount=1)
                        self.quiet(js)
                        self.assertEqual(js(HEADS), STANDARD, "the full order is unchanged")
                        self.assertEqual(js(ROW), STANDARD, "the cells are unchanged")
                        self.assertEqual(self.saved(), {}, "nothing was saved")
                        self.assertEqual(js("[...document.querySelectorAll('#work th[data-colmove]')].map((e) => e.dataset.col).filter((c) => c === 'status' || c === 'item')"), [], "Status and Item are not draggable")

    def test_esc_cancels_a_drag_in_progress(self):
        self.serve()
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme)
                    self.drag(cdp, sid, js, "prio", "owner", release=False)
                    self.assertTrue(js("!!document.querySelector('#work th.col-dragging') && !!document.querySelector('#work th.col-drop-before')"), "the bar is drawn while dragging")
                    self.esc(cdp, sid)
                    self.quiet(js)
                    self.assertEqual(js("document.querySelectorAll('#work th.col-dragging, #work th.col-drop-before, #work th.col-drop-after').length"), 0, "the bar and the dragging mark are gone")
                    self.mouse(cdp, sid, "mouseReleased", *self.centre(js, "owner"), button="left", clickCount=1)      # the button comes up later: still nothing
                    self.quiet(js)
                    self.assertEqual(js(HEADS), STANDARD, "no move")
                    self.assertEqual(js(ROW), STANDARD)
                    self.assertEqual(self.saved(), {}, "no save")

    def test_alt_shift_arrows_move_and_announce_the_position_of_all_drawn_columns(self):
        self.serve({"actions": SAVED})
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme)
                    self.assertEqual(js(HEADS), SAVED, "the saved order is drawn")
                    js("document.querySelector(\"#work th[data-col='owner']\").focus()")
                    self.arrow(cdp, sid, "ArrowLeft")
                    want = ["status", "item", "owner", "due", "prio", "id"]
                    self.assertTrue(wait(lambda: js(HEADS) == want, 5), f"moved left: {js(HEADS)}")
                    self.assertEqual(js(ROW), want)
                    self.assertEqual(js(LIVE), "Owner moved to position 3 of 6")
                    self.assertEqual(js("document.activeElement.dataset.col"), "owner", "the heading keeps the focus")
                    self.arrow(cdp, sid, "ArrowLeft")                       # already as far left as it may go: Status and Item stay first
                    self.frames(js)
                    self.assertEqual(js(HEADS), want)
                    self.arrow(cdp, sid, "ArrowRight")
                    self.assertTrue(wait(lambda: js(HEADS) == SAVED, 5))
                    self.assertEqual(js(LIVE), "Owner moved to position 4 of 6")
                    self.assertEqual(js(HEADS)[:2], ["status", "item"])
                    self.assertTrue(wait(lambda: self.saved().get("actions") == SAVED, 5), self.saved())

    def test_status_and_item_cannot_be_moved_by_key(self):
        self.serve()
        with chrome() as cdp:
            sid, js = self.opened(cdp, 1400, "light")
            for col in ("status", "item"):
                js(f"document.querySelector(\"#work th[data-col='{col}']\").focus()")
                self.arrow(cdp, sid, "ArrowRight")
            self.frames(js)
            self.assertEqual(js(HEADS), STANDARD)
            self.assertEqual(self.saved(), {})

    def test_all_view_is_not_movable_and_keeps_the_standard_order(self):
        self.serve({"actions": SAVED, "risks": SAVED, "decisions": SAVED})
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme, kind="all")
                    self.assertEqual(js(HEADS), STANDARD, "All keeps the standard order")
                    self.assertEqual(js("document.querySelectorAll('#work th[data-colmove]').length"), 0, "no heading is draggable")
                    js("document.querySelector(\"#work th[data-col='owner']\").focus()")
                    self.arrow(cdp, sid, "ArrowRight")
                    self.drag(cdp, sid, js, "prio", "owner")
                    self.quiet(js)
                    self.assertEqual(js(HEADS), STANDARD)
                    self.menu(cdp, sid, js, "owner")
            
    def test_the_other_types_have_their_own_order(self):
        self.serve({"risks": SAVED})
        with chrome() as cdp:
            sid, js = self.opened(cdp, 1400, "light", kind="risk")
            self.assertEqual(js(HEADS), SAVED, "Risks and issues use the saved risks order")
        with chrome() as cdp:
            sid, js = self.opened(cdp, 1400, "light", kind="action")
            self.assertEqual(js(HEADS), STANDARD, "Actions keep the standard order")

    def test_a_blocked_browser_store_draws_the_standard_order(self):
        self.serve()
        block = "Object.defineProperty(window, 'localStorage', {get() { throw new Error('blocked'); }});"
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme, before=block)
                    self.assertEqual(js(HEADS), STANDARD)
                    self.assertEqual(js(ROW), STANDARD)


class Menu(Base):
    def test_menu_lists_columns_in_table_order_with_ticks_and_no_move_or_reset_line(self):
        """the Classic Work items menu is a heading, tick lines, then Move left and Move right (Q23, after row 1499 pick 7B); no Reset."""
        self.serve({"actions": SAVED})
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme)
                    self.menu(cdp, sid, js, "owner")
                    lines = js(f"[...document.querySelectorAll({json.dumps(MENU + ' [role=menuitemcheckbox]')})].map((b) => [b.dataset.colName, b.getAttribute('aria-checked')])")
                    self.assertEqual([l[0] for l in lines[:5]], ["Status", "Due", "Owner", "Priority", "Id"], "the shown columns in the table's order, the Status first")
                    self.assertEqual([l[1] for l in lines[:5]], ["true"] * 5)
                    self.assertTrue(all(l[1] == "false" for l in lines[5:]), "the hidden columns come after, unticked")
                    self.assertEqual(js(f"document.querySelectorAll({json.dumps(MENU + ' [role=menuitem]')}).length"), 2, "Move left and Move right only, no Reset line")
                    self.assertEqual(js(f"document.querySelector({json.dumps(MENU)}).querySelector('h5').textContent"), "Columns to show")
                    # a tick still works and leaves the order alone
                    js(f"[...document.querySelectorAll({json.dumps(MENU + ' [role=menuitemcheckbox]')})].find((b) => b.dataset.colName === 'Priority').click()")
                    self.assertTrue(wait(lambda: js(HEADS) == ["status", "item", "due", "owner", "id"], 5), js(HEADS))


if __name__ == "__main__":
    unittest.main()

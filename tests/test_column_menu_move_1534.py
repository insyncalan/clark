"""Row 1534 (Q23): the Classic Work items Columns menu has Move left and Move right (no Reset). They act on the column whose heading opened the menu, with the
same moveColumn and the same saved order as the drag and Alt+Shift+Left/Right. Real Chrome at 1400 and 900, light and dark, the real server and the demo project TUL (fictional).

Run: python3 -m unittest test_column_menu_move_1534   (from tests/)
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _new_page import reload_to_new_page_cdp
from clark import publish
from clark.store import open_store
from test_client_page_filters import open_page
from test_column_order_chrome_1534 import Base, HEADS, MENU, SCHEMES, WIDTHS, STANDARD, LIVE
from test_inline_edits import EMPTY_BRANDING, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import TODAY

ITEM = MENU + " [role=menuitem]"
KEYS = {"ArrowDown": 40, "ArrowUp": 38, "Home": 36, "End": 35, "Enter": 13, "ContextMenu": 93}


class MenuMove(Base):
    def key(self, cdp, sid, name):
        common = {"key": name, "code": name, "windowsVirtualKeyCode": KEYS[name]}
        if name == "Enter":
            common["text"] = "\r"
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown" if name == "Enter" else "rawKeyDown", **common}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)

    def line(self, js, side):
        return js(f"(() => {{ const b = document.querySelector({json.dumps(ITEM + '[data-colmenu-move=' + side + ']')}); return b && [b.textContent.trim(), b.getAttribute('aria-disabled'), b.tabIndex, b.type]; }})()")

    def each(self, kind="action"):
        self.serve()
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    sid, js = self.opened(cdp, w, scheme, kind)
                    yield cdp, sid, js

    def test_a_menu_has_move_left_and_move_right_and_no_reset_or_standard_line(self):
        for cdp, sid, js in self.each():
            self.menu(cdp, sid, js, "due")
            self.assertEqual(js(f"[...document.querySelectorAll({json.dumps(ITEM)})].map((b) => b.textContent.trim())"), ["Move left", "Move right"])
            self.assertEqual(js(f"document.querySelectorAll({json.dumps(MENU + ' [data-cols-standard]')}).length"), 0)
            text = js(f"document.querySelector({json.dumps(MENU)}).textContent").lower()
            self.assertNotIn("reset", text)
            self.assertNotIn("standard", text)
            self.assertEqual(self.line(js, "left"), ["Move left", None, -1, "button"])
            self.assertEqual(self.line(js, "right"), ["Move right", None, -1, "button"])

    def test_b_move_right_moves_a_middle_column_one_place_and_the_table_follows_and_it_is_announced(self):
        for cdp, sid, js in self.each():
            self.menu(cdp, sid, js, "due")
            js(f"document.querySelector({json.dumps(ITEM + '[data-colmenu-move=right]')}).click()")
            want = ["status", "item", "owner", "prio", "due", "id"]
            self.assertTrue(wait(lambda: js(HEADS) == want, 5), js(HEADS))
            self.assertEqual(self.where(js)[1], want, "the cells follow")
            self.assertIn("Moved Due right", js(LIVE))
            js(f"document.querySelector({json.dumps(ITEM + '[data-colmenu-move=left]')}).click()")
            self.assertTrue(wait(lambda: js(HEADS) == STANDARD or js(HEADS) == ["status", "item", "owner", "due", "prio", "id"], 5), js(HEADS))

    def test_c_the_order_is_saved_with_the_project_and_the_published_file_shows_it(self):
        self.serve()
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                sid, js = self.opened(cdp, w, "light")
                self.menu(cdp, sid, js, "owner")
                js(f"document.querySelector({json.dumps(ITEM + '[data-colmenu-move=right]')}).click()")
                want = ["status", "item", "due", "owner", "prio", "id"]
                self.assertTrue(wait(lambda: self.saved().get("actions") == want, 5), f"saved with the project: {self.saved()}")
                reload_to_new_page_cdp(cdp, sid, what="the page reloaded after the move")      # waits for the NEW document (test_reload_waits)
                self.assertTrue(wait(lambda: js(HEADS) == want, 20), "the saved order is drawn again after a reload")
            out = Path(tempfile.mkdtemp(prefix="clark-cmm-"))
            self.addCleanup(shutil.rmtree, str(out), True)
            st = open_store(self.path, onedrive_roots=[])
            try:
                made = Path(publish.publish(st, "TUL", out, by_user="Demo User", now=TODAY, branding=EMPTY_BRANDING)["path"])
            finally:
                st.close()
            with self.subTest(width=w, part="published file"), chrome() as cdp:
                sid = open_page(cdp, made.as_uri() + "#work&f=mode:all;type:action", w, "light")
                heads = "[...document.querySelectorAll('#work table.items thead th[data-col]')].map((e) => e.dataset.col)"
                self.assertTrue(wait(lambda: len(cdp.js(heads, sid) or []) > 0, 20), "the published table drew")
                self.assertEqual([c for c in cdp.js(heads, sid) if c != "id"], [c for c in want if c != "id"], "the published table has the saved order (the Id is an extra cell the file does not draw)")

    def test_d_a_column_that_cannot_move_has_its_item_disabled_not_hidden_and_pressing_it_changes_nothing(self):
        for cdp, sid, js in self.each():
            for col, side, other in (("owner", "left", "right"), ("id", "right", "left")):
                self.menu(cdp, sid, js, col)
                self.assertEqual(self.line(js, side)[1], "true", f"{col}: Move {side} is disabled")
                self.assertIsNone(self.line(js, other)[1], f"{col}: Move {other} is not")
                js(f"document.querySelector({json.dumps(ITEM + '[data-colmenu-move=' + side + ']')}).click()")
                self.frames(js)
                self.assertEqual(js(HEADS), STANDARD)
                self.assertEqual(self.saved(), {}, "nothing saved")
                self.esc(cdp, sid)
                self.assertTrue(wait(lambda: not js(f"!!document.querySelector({json.dumps(MENU)})"), 5))
            self.menu(cdp, sid, js, "status")
            self.assertEqual([self.line(js, "left")[1], self.line(js, "right")[1]], ["true", "true"], "the Status does not move")

    def test_e_keyboard_open_arrow_to_move_right_and_enter(self):
        for cdp, sid, js in self.each():
            js("(() => { const t = document.querySelector(\"#work th[data-col='due']\"); t.setAttribute('tabindex', '-1'); t.focus(); })()")
            self.key(cdp, sid, "ContextMenu")
            self.assertTrue(wait(lambda: js(f"!!document.querySelector({json.dumps(MENU)})"), 5), "the menu opens from the keyboard")
            self.frames(js)
            self.key(cdp, sid, "End")
            self.assertEqual(js("document.activeElement.dataset.colmenuMove"), "right", "End reaches Move right")
            self.key(cdp, sid, "ArrowUp")
            self.assertEqual(js("document.activeElement.dataset.colmenuMove"), "left", "Up reaches Move left")
            self.key(cdp, sid, "ArrowDown")
            self.assertEqual(js("document.activeElement.dataset.colmenuMove"), "right", "Down reaches Move right")
            self.key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: js(HEADS) == ["status", "item", "owner", "prio", "due", "id"], 5), js(HEADS))
            self.assertTrue(wait(lambda: self.saved().get("actions") == ["status", "item", "owner", "prio", "due", "id"], 5), self.saved())

    def test_f_a_drag_still_moves_a_column(self):
        for cdp, sid, js in self.each():
            self.drag(cdp, sid, js, "prio", "owner")
            self.assertTrue(wait(lambda: js(HEADS) == ["status", "item", "prio", "owner", "due", "id"], 5), js(HEADS))


if __name__ == "__main__":
    unittest.main()

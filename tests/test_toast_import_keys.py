"""Hunt 10: the keyboard and the corners of a message at the foot, and the Import from Excel box while it works.

Run: python3 dev/run_tests.py test_toast_import_keys
1. Close or Undo pressed from the keyboard leaves focus on the page (<main>), not on nothing.
2. Esc puts away the message at the foot when nothing else has the key.
3. A message of three lines keeps its text inside the rounded corners (1400 and 900 px).
4. The Import box keeps focus on Choose a file while a file is checked and after it is refused; while the changes are saved Esc, Cancel and
   the backdrop leave the box open, so the result and Undo this import are shown.
"""
import base64
import json
import unittest

from test_server import chrome
import test_undo_key as tuk
import test_settings_data_page as sdp
from test_publish_dialog import Base

CELL, click, WIDTHS, workbook = tuk.CELL, tuk.click, sdp.WIDTHS, sdp.workbook

TEXT = ("The change was saved, but the page could not be refreshed. Reload the page to see it. "
        "The page keeps what it had until then, and nothing else was lost.")
CORNER = """(() => { const r = document.createElement('div'); r.className = 'toasts'; r.id = 'h10-r';
  r.innerHTML = '<div class="toast problem"><span class="toast-text">%s</span><button type="button" class="toast-btn">Close</button></div>';
  document.body.appendChild(r); const t = r.firstChild, tb = t.getBoundingClientRect(), x = t.querySelector('.toast-text').getBoundingClientRect();
  const rad = Math.min(parseFloat(getComputedStyle(t).borderTopLeftRadius), tb.height / 2), dx = rad - (x.left - tb.left), dy = rad - (x.top - tb.top);
  return {h: tb.height, rad, out: dx > 0 && dy > 0 ? Math.hypot(dx, dy) - rad : -1}; })()""" % TEXT


def press(cdp, sid, key, code, vk):
    common = {"key": key, "code": code, "windowsVirtualKeyCode": vk, **({"text": "\r"} if key == "Enter" else {})}
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **common}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


class Toast(unittest.TestCase):
    setUp = tuk.UndoKey.setUp
    read = tuk.UndoKey.read
    open_page = tuk.UndoKey.open_page
    until = tuk.UndoKey.until

    def change(self, cdp, sid, value="Low"):
        click(cdp, sid, CELL)
        self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the priority menu opened")
        click(cdp, sid, f"[data-pop] [data-value={value}]")
        self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")

    def test_close_and_undo_from_the_keyboard_leave_focus_in_the_page(self):
        for which, value in (("[data-dismiss]", "Low"), ("[data-undo]", "High")):
            with self.subTest(which=which), chrome() as cdp:
                sid = self.open_page(cdp, 1400)
                self.change(cdp, sid, value)
                cdp.js(f"document.querySelector('.toast {which}').focus()", sid)
                press(cdp, sid, "Enter", "Enter", 13)
                self.until(cdp, sid, "!document.querySelector('[data-dismiss]') || !document.querySelector('.toast [data-undo]')", "the message went")
                self.until(cdp, sid, "document.activeElement && document.activeElement.id === 'main'", "focus is on the page, not dropped")

    def test_escape_puts_the_message_away(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            self.change(cdp, sid)
            cdp.js("document.activeElement && document.activeElement.blur && document.activeElement.blur()", sid)
            press(cdp, sid, "Escape", "Escape", 27)
            self.until(cdp, sid, "!document.querySelector('.toast-text')", "Esc put the message away (not the 5 seconds)", 2)

    def test_a_three_line_message_keeps_its_text_inside_the_corners(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                sid = self.open_page(cdp, w)
                m = cdp.js(CORNER, sid)
                self.assertGreater(m["h"], 60, m)
                self.assertLessEqual(m["out"], 0, f"the first line starts outside the corner {m}")


class Import(Base):
    def setUp(self):
        Base.setUp(self)
        self._card_setup()

    def _card_setup(self):
        import tempfile
        from clark import excel_route
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.rig.httpd.excel_import = excel_route.make_excel_import(self.rig.db, [], sdp.USER)

    settle = sdp.Card.settle
    open_settings = sdp.Card.open_settings
    choose = sdp.Card.choose
    pick_file = sdp.Card.pick_file

    def open_box(self, p):
        self.open_settings(p)
        p.js("document.querySelector('#import-workbook').click()")
        p.until("!!document.querySelector('#import-box')", "the box opened")
        self.settle(p, "document.activeElement && document.activeElement.id === 'import-choose'", "focus on Choose a file")

    def test_focus_stays_on_choose_a_file_when_a_file_is_refused(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_box(p)
                self.choose(p, base64.b64encode(b"not a workbook").decode())
                p.until("!!document.querySelector('#import-problem').textContent", "the refusal")
                self.assertEqual(p.js("document.activeElement && document.activeElement.id"), "import-choose")
                p.js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                p.until("!document.querySelector('#import-box')", "Esc still closes the box")

    def test_the_box_stays_while_the_changes_are_saved(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                from pathlib import Path
                folder = Path(self.tmp.name) / str(w)
                folder.mkdir()
                b64, _, _ = workbook(self.rig, folder, f"Agree the cut-over plan, version {w}")
                p = self.page(cdp)
                p.width(w)
                self.open_box(p)
                p.js("""(() => { const real = window.fetch; window.__go = null; const hold = new Promise((r) => { window.__release = r; });
                  window.fetch = (u, o) => (o && typeof o.body === 'string' && o.body.includes('"op":"apply"')) ? hold.then(() => real(u, o)) : real(u, o); })()""")
                self.choose(p, b64)
                p.until("!!document.querySelector('#import-go')", "the check")
                p.js("document.querySelector('#import-go').click()")
                p.until("document.querySelector('#import-go').getAttribute('aria-disabled') === 'true'", "it is saving")
                self.assertEqual(p.js("document.activeElement && document.activeElement.id"), "import-go", "focus stays on the button")
                p.js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                p.js("document.querySelector('#import-box [data-close]').click()")
                p.js("document.querySelector('.ad-scrim').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))")
                self.assertTrue(p.js("!!document.querySelector('#import-box')"), "the box stays while it saves")
                p.js("window.__release()")
                p.until("!!document.querySelector('#import-result') && !!document.querySelector('#import-undo')", "the result and Undo this import")


if __name__ == "__main__":
    unittest.main()

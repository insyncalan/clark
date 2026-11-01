"""#276 (from #194): in the prototype's Work items table, Enter on a cell opens that cell's picker, never the row's peek.

Run: python3 dev/run_tests.py test_proto_cell_enter
The product page does this already (src/clark/page/src/components/WorkItems.jsx: a key on a cell's own button is left to the
button, and tests/test_inline_edits.py proves it). The prototype's row listened for Enter on anything inside it, opened the
peek and cancelled the key, so the cell's button never got its click. This loads the prototype (system/prototype/index.html,
its clock fixed to one day, as run_selftest.py does) in headless Chrome and drives it with real key events: Enter on a status,
owner, priority or due cell opens that cell's picker with the focus inside it (the calendar keeps it on its cell and takes the keys itself) and the peek stays shut; Esc closes it and the
focus is back on the cell; Enter on the row itself still opens the peek; Enter in the owner picker's name box is the box's own.
The browser part is required: it fails, never skips, without Chrome (set CLARK_CHROME to its path).
"""
import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

from run_support import chrome_command, remove_profile, start_chrome, stop_chrome
from test_server import CHROME, _Pipe, wait  # noqa: E402

PROTO = ROOT / "system" / "prototype"
KEYS = {"Enter": (13, "\r"), "Escape": (27, ""), "ArrowDown": (40, "")}
CLOCK = ('<script>(() => { const R = Date, off = new R(2026, 9, 29, 12, 0, 0).getTime() - R.now();'
         ' function D(...a) { if (!new.target) return new R(R.now() + off).toString(); return a.length ? new R(...a) : new R(R.now() + off); }'
         ' D.prototype = R.prototype; D.now = () => R.now() + off; D.UTC = R.UTC; D.parse = R.parse; window.Date = D; })();</script>')


@contextlib.contextmanager
def proto_chrome():
    """The prototype's page in a fresh headless Chrome (file access allowed, as for its own self-test); yields (cdp, session)."""
    assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
    page = (PROTO / "index.html").read_text(encoding="utf-8").replace("<head>", "<head>" + CLOCK, 1)
    tmp = PROTO / f"cell-enter-run-{os.getpid()}.html"      # beside index.html, which loads its scripts by relative path
    tmp.write_text(page, encoding="utf-8")
    to_r, to_w = os.pipe()
    from_r, from_w = os.pipe()
    prof = tempfile.mkdtemp(prefix="clark-chrome-profile-")
    try:
        proc = start_chrome(chrome_command(CHROME, prof, "--allow-file-access-from-files", "--window-size=1400,900"), to_r, from_w)
        os.close(to_r)
        os.close(from_w)
        try:
            cdp = _Pipe(to_w, from_r)
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": tmp.as_uri()}, sid)
            yield cdp, sid
        finally:
            stop_chrome(proc)
            os.close(to_w)
            os.close(from_r)
    finally:
        remove_profile(prof)
        tmp.unlink(missing_ok=True)


def key(cdp, sid, name):
    vk, text = KEYS[name]
    common = {"key": name, "code": name, "windowsVirtualKeyCode": vk}
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **common, **({"text": text} if text else {})}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


class CellEnter(unittest.TestCase):
    def until(self, cdp, sid, expr, what, seconds=15):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), what)

    def open_table(self, cdp, sid):
        self.until(cdp, sid, "!!(window.C && C.UI && window.ClarkDB && ClarkDB.S && ClarkDB.S.items.length)", "the prototype loaded its demo data", 30)
        cdp.js("C.go('work')", sid)
        self.until(cdp, sid, "document.querySelectorAll('tr[data-id] [data-pick]').length > 0", "the Work items table drew its cells")
        first = cdp.js("document.querySelector('tr[data-id]').dataset.id", sid)
        self.assertTrue(first)
        return first

    def focus_cell(self, cdp, sid, ref, prop):
        sel = f"[data-pick='{ref}'][data-prop={prop}]"
        cdp.js(f"document.querySelector({json.dumps(sel)}).focus()", sid)
        self.assertTrue(cdp.js(f"document.activeElement === document.querySelector({json.dumps(sel)})", sid), f"the {prop} cell has the focus")
        return sel

    def peek_open(self, cdp, sid):
        return cdp.js("!!C.UI.peek", sid)

    def test_enter_on_a_cell_opens_its_picker_and_esc_returns_to_the_cell(self):
        with proto_chrome() as (cdp, sid):
            ref = self.open_table(cdp, sid)
            for prop in ("status", "priority", "owner", "due"):
                with self.subTest(cell=prop):
                    sel = self.focus_cell(cdp, sid, ref, prop)
                    key(cdp, sid, "Enter")
                    self.until(cdp, sid, "!!document.querySelector('.menu.on, .menu')", f"Enter on the {prop} cell opened a picker")
                    self.assertFalse(self.peek_open(cdp, sid), f"Enter on the {prop} cell did not open the peek")
                    self.assertEqual(cdp.js("location.hash.includes('id=')", sid), False, "the address does not name an item either")
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(sel)}).getAttribute('aria-expanded')", sid), "true")
                    if prop != "due":      # the calendar keeps the focus on its cell and takes the arrows and Enter itself (core.js, calPick)
                        self.assertTrue(cdp.js("document.querySelector('.menu').contains(document.activeElement)", sid), f"the focus is inside the {prop} picker")
                    else:
                        self.assertTrue(cdp.js("!!document.querySelector('.menu [data-cp]')", sid), "the calendar shows its days")
                    key(cdp, sid, "Escape")
                    self.until(cdp, sid, "!document.querySelector('.menu')", f"Esc closed the {prop} picker")
                    self.assertTrue(cdp.js(f"document.activeElement === document.querySelector({json.dumps(sel)})", sid), f"the focus is back on the {prop} cell")
                    self.assertFalse(self.peek_open(cdp, sid), "Esc opened no peek")

    def test_enter_on_the_row_itself_still_opens_the_peek(self):
        with proto_chrome() as (cdp, sid):
            ref = self.open_table(cdp, sid)
            cdp.js(f"document.querySelector(\"tr[data-id='{ref}']\").focus()", sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, f"C.UI.peek === {json.dumps(ref)}", "Enter on a row opens its peek")
            self.assertFalse(cdp.js("!!document.querySelector('.menu')", sid), "and no picker")

    def test_enter_in_the_pickers_name_box_is_the_boxs_own(self):
        with proto_chrome() as (cdp, sid):
            ref = self.open_table(cdp, sid)
            self.focus_cell(cdp, sid, ref, "owner")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "document.activeElement && document.activeElement.id === 'ownIn'", "the owner picker's name box has the focus")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!document.querySelector('.menu')", "Enter in the box confirmed it and closed the picker")
            self.assertFalse(self.peek_open(cdp, sid), "Enter in the box opened no peek")


if __name__ == "__main__":
    unittest.main()

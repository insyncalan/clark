"""Keyboard pass on the Work items filter line and the saved-view tabs, at 1400 and 900 px.

Run: python3 dev/run_tests.py test_filter_line_keys
Real keys (Tab, Shift+Tab, Arrow Down, Esc, Enter) are sent to the real page over the fictional demo data. Checked: every control of the line and the tabs
can be reached with Tab, in the order it is drawn, and has a name; none has a tab stop above 0; each shows a keyboard focus ring when it has the focus;
Esc closes the list of suggestions and keeps the text; Enter on an empty line does not leave the page or lose focus; focus is never trapped (Tab walks
out of the line and back with Shift+Tab); Group by has a name that begins with its visible word and no second description.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import page, server as sv  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
KEYS = {"Tab": ("Tab", 9), "Escape": ("Escape", 27), "Enter": ("Enter", 13), "ArrowDown": ("ArrowDown", 40), "ArrowRight": ("ArrowRight", 39)}

# what has the focus now, in words the test can read
WHO = r"""(() => { const a = document.activeElement; if (!a || a === document.body) return JSON.stringify({ body: true });
  const box = a.tagName === 'INPUT' && a.closest('.fline'), cs = getComputedStyle(box || a);   // item 1137: the box has no ring; a darker border than its resting one marks the focus
  let edge = false;
  if (box) { const rest = box.cloneNode(false); box.after(rest); edge = getComputedStyle(rest).borderTopColor !== cs.borderTopColor; rest.remove(); }
  return JSON.stringify({ id: a.id || '', cls: String(a.className || ''), name: a.getAttribute('aria-label') || a.textContent.trim().slice(0, 30), tag: a.tagName,
    desc: a.getAttribute('aria-description'), view: a.getAttribute('data-view-id'), tabindex: a.getAttribute('tabindex'), visible: a.matches(':focus-visible'),
    ring: box ? edge : (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2 || (cs.boxShadow !== 'none' && cs.boxShadow !== '')),
    inLine: !!a.closest('.vtabs, .fline, .vicons, [data-fline]') }); })()"""
# every control the line and the tabs draw that a keyboard can reach
STOPS = r"""(() => { const root = document.querySelector('.vtabs') ? document.querySelector('.vtabs').parentElement : null;
  const sel = 'button, input, [tabindex]'; const out = [];
  for (const e of document.querySelectorAll('.vtabs ' + sel.split(', ').join(', .vtabs ') + ', .fline ' + sel.split(', ').join(', .fline ') + ', .vicons ' + sel.split(', ').join(', .vicons '))) {
    if (!e.getClientRects().length || e.disabled) continue;
    out.push({ name: e.getAttribute('aria-label') || e.textContent.trim(), tabindex: e.getAttribute('tabindex'), desc: e.getAttribute('aria-description') }); }
  return JSON.stringify(out); })()"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Keys(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = Running(data_for=self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived=None):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code)
        finally:
            st.close()

    def open_page(self, cdp, width):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input') && !!document.querySelector('.vtab')", sid)), "the line and the tabs are drawn")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "motion has finished")
        return sid

    def press(self, cdp, sid, key, shift=False):
        k, vk = KEYS[key]
        mod = 8 if shift else 0
        for kind in ("rawKeyDown", "keyUp"):
            ev = {"type": kind, "key": k, "code": k, "windowsVirtualKeyCode": vk, "modifiers": mod}
            if key == "Enter" and kind == "rawKeyDown":      # a button is pressed by Enter only when the key carries its text
                ev.update({"type": "keyDown", "text": "\r"})
            cdp.call("Input.dispatchKeyEvent", ev, sid)
        cdp.js("0", sid)

    def who(self, cdp, sid):
        return json.loads(cdp.js(WHO, sid))

    def test_tab_order_names_rings_and_no_trap_at_both_widths(self):
        with chrome() as cdp:
            for width in (1400, 900):
                where = f"{width} px"
                sid = self.open_page(cdp, width)
                stops = json.loads(cdp.js(STOPS, sid))
                self.assertTrue(stops, where)
                for s in stops:
                    self.assertTrue(s["name"], f"{where}: a control has no name: {s}")
                    self.assertIn(s["tabindex"], (None, "0", "-1"), f"{where}: no positive tab stop: {s}")
                    self.assertIsNone(s["desc"], f"{where}: {s['name']} has an aria-description besides its name")
                group = [s for s in stops if s["name"].startswith("Group by")]
                self.assertEqual(len(group), 1, f"{where}: Group by is one button named by its visible word: {stops}")
                # walk forward from the line's box with Tab: every stop has a ring; the walk leaves the line (no trap) and Shift+Tab comes back
                cdp.js("document.querySelector('#fline-input').focus()", sid)
                self.press(cdp, sid, "Tab")                      # a key press puts the page in keyboard mode
                self.press(cdp, sid, "Tab", shift=True)
                seen, left = [], False
                for _ in range(40):
                    w = self.who(cdp, sid)
                    if w.get("body") or not w["inLine"]:
                        left = True
                        break
                    self.assertTrue(w["visible"] and w["ring"], f"{where}: {w['name']} shows a focus ring")
                    seen.append(w["name"])
                    self.press(cdp, sid, "Tab")
                self.assertTrue(left, f"{where}: Tab leaves the line and the tabs (no trap); walked {seen}")
                self.assertEqual(seen[0], "Filter work items", where)
                back = []
                for _ in range(40):
                    self.press(cdp, sid, "Tab", shift=True)
                    w = self.who(cdp, sid)
                    if w.get("body") or not w["inLine"] or w["name"] == "Filter work items":
                        break
                    back.append(w["name"])
                self.assertEqual(back, list(reversed(seen[1:])), f"{where}: Shift+Tab walks the same stops back")

    def test_esc_closes_the_list_keeps_the_text_and_enter_keeps_the_focus(self):
        with chrome() as cdp:
            for width in (1400, 900):
                where = f"{width} px"
                sid = self.open_page(cdp, width)
                cdp.js("document.querySelector('#fline-input').focus()", sid)
                self.press(cdp, sid, "Tab", shift=True)
                self.press(cdp, sid, "Tab")
                self.assertEqual(self.who(cdp, sid).get("id"), "fline-input", where)
                self.press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').getAttribute('aria-expanded')", sid) == "true"), where + ": Arrow Down opens the list")
                self.press(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').getAttribute('aria-expanded')", sid) == "false"), where + ": Esc closes the list")
                self.assertEqual(self.who(cdp, sid).get("id"), "fline-input", where + ": Esc leaves the focus in the box")
                self.press(cdp, sid, "Enter")
                self.assertEqual(self.who(cdp, sid).get("id"), "fline-input", where + ": Enter on the box keeps the focus there")

    def test_arrow_keys_do_not_trap_or_move_a_tab_unless_it_is_being_moved(self):
        with chrome() as cdp:
            for width in (1400, 900):
                where = f"{width} px"
                sid = self.open_page(cdp, width)
                cdp.js("document.querySelector('.vtab').focus()", sid)
                self.press(cdp, sid, "Tab", shift=True)
                self.press(cdp, sid, "Tab")
                before = cdp.js("[...document.querySelectorAll('.vtab')].map(e => e.dataset.viewId).join()", sid)
                self.press(cdp, sid, "ArrowRight")
                self.assertEqual(cdp.js("[...document.querySelectorAll('.vtab')].map(e => e.dataset.viewId).join()", sid), before, where + ": an arrow key alone does not reorder the tabs")
                self.press(cdp, sid, "Tab")
                self.assertTrue(self.who(cdp, sid)["name"], where + ": Tab after an arrow key moves on to a named control")

    def test_the_tabs_and_a_typed_line_are_reached_in_drawn_order_with_rings(self):
        with chrome() as cdp:
            for width in (1400, 900):
                where = f"{width} px"
                sid = self.open_page(cdp, width)
                names_dom = json.loads(cdp.js("JSON.stringify([...document.querySelectorAll('.vtabs button, #fline-input, .fline button, .vicons button')].filter(e => e.getClientRects().length).map(e => e.getAttribute('aria-label') || e.textContent.trim()))", sid))
                cdp.js("document.querySelector('.vtab').focus()", sid)
                self.press(cdp, sid, "Tab", shift=True)
                self.press(cdp, sid, "Tab")
                seen = []
                for _ in range(60):
                    w = self.who(cdp, sid)
                    if w.get("body") or not w["inLine"]:
                        break
                    self.assertTrue(w["visible"] and w["ring"], f"{where}: {w['name']} shows a focus ring")
                    seen.append(w["name"])
                    self.press(cdp, sid, "Tab")
                self.assertGreaterEqual(len(seen), 3, f"{where}: {seen}")
                self.assertTrue(any(n.endswith("items") or "," in n for n in seen[:-1]), f"{where}: a saved view is reached: {seen}")
                self.assertEqual(seen, [n for n in names_dom if n in seen], f"{where}: Tab order is the drawn order")
                # a typed word adds the clear button, and Tab reaches it with a ring and a name
                cdp.js("(() => { const i = document.querySelector('#fline-input'); i.focus(); document.execCommand('insertText', false, 'is:open'); })()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-x')", sid)), where + ": the x is drawn")
                self.press(cdp, sid, "Tab")
                w = self.who(cdp, sid)
                self.assertEqual(w["name"], "Clear filter", where)
                self.assertTrue(w["visible"] and w["ring"], where + ": the x shows a ring")
                self.press(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#fline-x')", sid)), where + ": Enter on the x clears the line")
                self.assertEqual(self.who(cdp, sid).get("id"), "fline-input", where + ": the focus goes back to the box, not lost with the removed button")

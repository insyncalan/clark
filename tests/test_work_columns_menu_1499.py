"""Row 1499: the Work items Columns menu as the approved mock-up (pick 7B), in the Classic look only; Cards keeps its menu.

Run: python3 dev/run_tests.py test_work_columns_menu_1499
A real page and server at 1400 and 900 px. The Classic look is the page with the Theme prototype-2.0; Cards is the page with no Theme. The mock-up's own
--line, --muted, --soft and --blue are read as the Classic tokens --grey-200, --text-muted, --grey-50 and --brand-blue (tests compare the drawn colour with the token's).
"""
import hashlib
import json
import re
import shutil
import time
import unittest
from unittest import mock

from _real_server import real_server
from clark import page, server as sv
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_table_columns import KEYS, MENU, SETTLE, WORK_ALL
from test_work_items import FIXED_DATE, load_demo, page_target

THEME = "prototype-2.0"
HEAD = "#work th[data-col='owner']"
ITEMS = MENU + " [role=menuitemcheckbox]"
LISTED = [n for n in WORK_ALL if n != "Item"]        # the title is not in the menu: it is always drawn
# Cards: the md5 of the rendered #work block closed and of the whole body (less script and style text) with the menu open, taken on origin/main before this row.
CARDS_MD5 = {
    1400: {"closed": "aec653bd1c121a8d5039e9e00e1f43b3", "menu": "32b4dcdcc70d2b6ae63f593b500bf27a"},
    900: {"closed": "aec653bd1c121a8d5039e9e00e1f43b3", "menu": "32b4dcdcc70d2b6ae63f593b500bf27a"},
}


class Base(unittest.TestCase):
    classic = True

    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        theme = THEME if self.classic else None
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING, theme=theme))
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

    def opened(self, cdp, width):
        """The Work items table at `width`, settled, with the menu opened by a right click on the Owner heading; the menu's box has stopped moving."""
        sid = page_target(cdp)
        for m, p in (("Page.enable", {}), ("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}),
                     ("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}), ("Emulation.setFocusEmulationEnabled", {"enabled": True})):
            cdp.call(m, p, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + SETTLE}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        self.assertTrue(wait(lambda: js("document.querySelectorAll('#work tbody tr[data-id]').length > 0 && document.querySelectorAll('#work table.items thead th').length > 0"), 20), "the table is drawn")
        self.assertTrue(wait(lambda: js("!!document.querySelector('#work .cols-btn') && document.fonts.status === 'loaded' && performance.now() - window.__lastScroll > 700"), 20), "the page has settled")
        self.assertEqual(bool(js("!!document.getElementById('theme')")), self.classic, "the look is the one asked for")
        x, y = js(f"(() => {{ const b = document.querySelector({json.dumps(HEAD)}).getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")
        for t in ("mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "right", "buttons": 2 if t == "mousePressed" else 0, "clickCount": 1}, sid)
        self.assertTrue(wait(lambda: js(f"!!document.querySelector({json.dumps(MENU)})"), 5), "the menu opens")
        seen = []

        def still():
            seen.append(js(f"JSON.stringify(document.querySelector({json.dumps(MENU)}).getBoundingClientRect())")); time.sleep(.1)
            return len(seen) > 1 and seen[-1] == seen[-2]
        self.assertTrue(wait(still, 5), "the menu stops moving")
        return sid, js

    def lines(self, js):
        return js(f"[...document.querySelectorAll({json.dumps(ITEMS)})].map((b) => ({{name: b.dataset.colName, on: b.getAttribute('aria-checked')}}))")

    def heads(self, js):
        return js("[...new Set([...document.querySelectorAll('#work table.items thead th')].map((e) => e.dataset.col).filter(Boolean))]")

    def key(self, cdp, sid, name):
        common = {"key": name, "code": name, "windowsVirtualKeyCode": KEYS[name]}
        cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


class ClassicMenu(Base):
    def test_heading_text_and_style_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                _, js = self.opened(cdp, width)
                got = js(f"""(() => {{ const m = document.querySelector({json.dumps(MENU)}), h = m.querySelectorAll('h5'), c = getComputedStyle(h[0]);
                    const probe = document.createElement('i'); probe.style.color = 'var(--text-muted)'; document.body.appendChild(probe); const muted = getComputedStyle(probe).color; probe.remove();
                    return {{n: h.length, text: h[0].textContent, size: c.fontSize, weight: c.fontWeight, color: c.color, muted, margin: [c.marginTop, c.marginRight, c.marginBottom, c.marginLeft], caps: c.textTransform,
                        label: m.getAttribute('aria-label'), first: m.firstElementChild === h[0]}}; }})()""")
                self.assertEqual((got["n"], got["text"], got["first"]), (1, "Columns to show", True), "one heading line, the first thing in the menu")
                self.assertEqual(got["label"], "Columns to show", "the menu aria-label")
                self.assertEqual(js("[document.querySelector('#work .cols-btn').getAttribute('aria-label'), document.querySelector('#work .cols-btn').title]"), ["Columns", "Choose the columns"], "the button keeps its label and tip")
                self.assertEqual((got["size"], got["weight"], got["caps"]), ("12px", "600", "none"))
                self.assertEqual(got["color"], got["muted"], "the muted token")
                self.assertEqual(got["margin"], ["4px", "10px", "6px", "10px"])

    def test_tick_lines_in_order_with_aria_checked_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid, js = self.opened(cdp, width)
                lines = self.lines(js)
                self.assertEqual([i["name"] for i in lines], LISTED, "one line per column, in the table's own order, no title line")
                for i in lines:
                    self.assertEqual(i["on"], "true" if i["name"] in ("Status", "Owner", "Due", "Priority", "Id") else "false", i["name"])
                self.assertEqual(js(f"document.querySelectorAll({json.dumps(MENU + ' [role=menuitem]')}).length"), 0, "only tick lines")
                got = js(f"""(() => {{ const b = document.querySelector({json.dumps(ITEMS)}), c = getComputedStyle(b), t = b.firstElementChild, tc = getComputedStyle(t);
                    const probe = document.createElement('i'); probe.style.color = 'var(--brand-blue)'; document.body.appendChild(probe); const blue = getComputedStyle(probe).color; probe.remove();
                    return {{tk: t.className, tw: tc.width, tweight: tc.fontWeight, tcolor: tc.color, blue, first: t === b.firstChild || b.firstChild === t, gap: c.columnGap, min: c.minHeight, pad: [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft],
                        radius: c.borderTopLeftRadius, weight: c.fontWeight, role: b.getAttribute('role'), text: b.textContent.trim()}}; }})()""")
                self.assertEqual((got["tk"], got["tw"], got["tweight"]), ("tk", "16px", "700"), "the 16px tick cell, bold, at the left")
                self.assertEqual(got["tcolor"], got["blue"], "the blue token")
                self.assertEqual((got["gap"], got["min"], got["pad"], got["radius"], got["weight"]), ("10px", "38px", ["0px", "10px", "0px", "10px"], "8px", "500"))
                self.assertEqual(got["role"], "menuitemcheckbox")
                x, y = js(f"(() => {{ const b = [...document.querySelectorAll({json.dumps(ITEMS)})][3].getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
                hov = js(f"""(() => {{ const b = [...document.querySelectorAll({json.dumps(ITEMS)})][3], c = getComputedStyle(b), i = document.createElement('i'); i.style.color = 'var(--grey-50)'; document.body.appendChild(i);
                    const soft = getComputedStyle(i).color; i.remove(); return [c.backgroundColor, soft, c.outlineStyle]; }})()""")
                self.assertEqual(hov[0], hov[1], "hover fills with the soft token")
                self.assertEqual(hov[2], "none", "and draws no outline")

    def test_no_locked_line_and_status_can_be_unticked_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                _, js = self.opened(cdp, width)
                self.assertEqual(js(f"document.querySelectorAll({json.dumps(MENU + ' [aria-disabled], ' + MENU + ' [data-keep], ' + MENU + ' .cols-why, ' + MENU + ' small')}).length"), 0, "no locked line, no reason")
                self.assertNotIn("Always shown", js(f"document.querySelector({json.dumps(MENU)}).textContent"))
                self.assertIn("status", self.heads(js))
                js(f"[...document.querySelectorAll({json.dumps(ITEMS)})].find((b) => b.dataset.colName === 'Status').click()")
                self.assertTrue(wait(lambda: "status" not in self.heads(js), 5), "Status is taken out")
                self.assertIn("item", self.heads(js), "the title is always drawn")
                self.assertEqual(self.lines(js)[0], {"name": "Status", "on": "false"})
                js(f"[...document.querySelectorAll({json.dumps(ITEMS)})].find((b) => b.dataset.colName === 'Status').click()")
                self.assertTrue(wait(lambda: "status" in self.heads(js), 5), "and back")

    def test_no_standard_reset_line_and_no_separator_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                _, js = self.opened(cdp, width)
                self.assertEqual(js(f"document.querySelectorAll({json.dumps(MENU + ' [data-cols-standard], ' + MENU + ' [role=separator], ' + MENU + ' .sep, ' + MENU + ' [role=menuitem]')}).length"), 0)
                text = js(f"document.querySelector({json.dumps(MENU)}).textContent")
                self.assertNotIn("standard columns", text.lower())

    def test_panel_values_200_12_6_and_shadow_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                _, js = self.opened(cdp, width)
                got = js(f"""(() => {{ const m = document.querySelector({json.dumps(MENU)}), c = getComputedStyle(m);
                    const probe = (v, p) => {{ const i = document.createElement('i'); i.style[p] = v; document.body.appendChild(i); const r = getComputedStyle(i)[p]; i.remove(); return r; }};
                    const a = document.querySelector({json.dumps(HEAD)}).getBoundingClientRect(), r = m.getBoundingClientRect();
                    return {{min: c.minWidth, radius: c.borderTopLeftRadius, pad: [c.paddingTop, c.paddingRight, c.paddingBottom, c.paddingLeft], shadow: c.boxShadow, border: [c.borderTopWidth, c.borderTopStyle, c.borderTopColor],
                        bg: c.backgroundColor, surface: probe('var(--surface)', 'color'), line: probe('var(--grey-200)', 'color'), anchored: [r.left >= a.left - 1 && r.left <= a.right, r.top >= 0 && r.bottom <= innerHeight, r.top >= a.top - r.height && r.top <= a.bottom + 12], width: r.width}}; }})()""")
                self.assertEqual((got["min"], got["radius"], got["pad"]), ("200px", "12px", ["6px"] * 4))
                self.assertEqual(got["shadow"], "rgba(6, 47, 58, 0.2) 0px 10px 30px 0px")
                self.assertEqual((got["border"][0], got["border"][1]), ("1px", "solid"))
                self.assertEqual(got["border"][2], got["line"], "the line token")
                self.assertEqual(got["bg"], got["surface"], "the white surface token")
                self.assertGreaterEqual(got["width"], 200)
                self.assertEqual(got["anchored"], [True, True, True], "the menu opens at its anchor (its left edge on the heading's), moved up only as far as it needs to stay in the window")

    def test_click_toggles_menu_stays_open_focus_on_line_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid, js = self.opened(cdp, width)
                focus = "document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.colName : null"
                self.assertEqual(js(focus), "Status", "the first line takes the focus on open")
                x, y = js(f"(() => {{ const b = [...document.querySelectorAll({json.dumps(ITEMS)})].find((b) => b.dataset.colName === 'Workstream').getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")
                for t in ("mousePressed", "mouseReleased"):
                    cdp.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "buttons": 1 if t == "mousePressed" else 0, "clickCount": 1}, sid)
                self.assertTrue(wait(lambda: "workstream" in self.heads(js), 5), "the column is on at once")
                self.assertEqual(js(f"!!document.querySelector({json.dumps(MENU)})"), True, "the menu stays open")
                self.assertEqual(js(focus), "Workstream", "and the focus stays on the line")
                self.assertEqual([i for i in self.lines(js) if i["name"] == "Workstream"], [{"name": "Workstream", "on": "true"}])
                self.key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: js(f"!document.querySelector({json.dumps(MENU)})"), 5), "Escape closes the menu")


class CardsMenu(Base):
    classic = False

    def capture(self, cdp, width):
        norm = lambda v: hashlib.md5(re.sub(r"(last updated \d\d-\d\d-\d{4}) \d\d:\d\d", r"\1 HH:MM", re.sub(r'style="[^"]*"', 'style=""', v)).encode("utf-8")).hexdigest()  # noqa: E731
        sid = page_target(cdp)
        for m, p in (("Page.enable", {}), ("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}), ("Emulation.setFocusEmulationEnabled", {"enabled": True})):
            cdp.call(m, p, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + SETTLE}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
        js = lambda e: cdp.js(e, sid)  # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('#work .cols-btn') && document.fonts.status === 'loaded' && performance.now() - window.__lastScroll > 700"), 20))
        closed = js("document.querySelector('#work').outerHTML")
        x, y = js(f"(() => {{ const b = document.querySelector({json.dumps(HEAD)}).getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()")
        for t in ("mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "right", "buttons": 2 if t == "mousePressed" else 0, "clickCount": 1}, sid)
        self.assertTrue(wait(lambda: js(f"!!document.querySelector({json.dumps(MENU)})"), 5))
        time.sleep(.6)
        menu = js(f"document.querySelector({json.dumps(MENU)}).outerHTML")
        return js, {"closed": norm(closed), "menu": norm(re.sub(r'style="[^"]*"', "", menu))}

    def test_cards_menu_unchanged_at_1400_and_900(self):
        got = {}
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                js, got[width] = self.capture(cdp, width)
                self.assertEqual(js(f"document.querySelector({json.dumps(MENU)}).getAttribute('aria-label')"), "Columns", "Cards: the old menu name")
                self.assertEqual(js(f"document.querySelectorAll({json.dumps(MENU + ' h5, ' + MENU + '.cm-7b')}).length"), 0, "no heading and no new panel in Cards")
                self.assertEqual(js(f"document.querySelectorAll({json.dumps(MENU + ' [data-cols-standard]')}).length"), 1, "the standard foot is still there")
                self.assertEqual(js(f"document.querySelector({json.dumps(MENU + ' [data-col-name=Status]')}).getAttribute('aria-disabled')"), "true", "Status still greyed")
                self.assertEqual(js(f"[...document.querySelectorAll({json.dumps(ITEMS)})].map((b) => b.dataset.colName).join()"), ",".join(WORK_ALL))
        self.assertEqual(got, CARDS_MD5, "the rendered Cards DOM (Client Message label, row 1466)")


if __name__ == "__main__":
    unittest.main()

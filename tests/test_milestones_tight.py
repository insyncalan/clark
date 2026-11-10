"""Row 1020 (owner defect): the Milestones section is tighter, as the owner chose ('Milestones A, same layout, tightened').

Run: python3 dev/run_tests.py test_milestones_tight
The timeline is about half its old height (one label line per milestone, the late text '+13 days', the date stays in the detail
list); each list row is one compact line (date, name, state, progress) plus a small second line (Agreed, or Expected date and days
later in red), about half the old row height, with the coloured ring on the rail kept; 'Hide milestone details' (left) and
'Legend' (right) share one row; the remembered hide state and the focus rings stay. The same checks run on the
live page (demo database, fixed CLARK_NOW) and on a published file, because shell.css is inlined into the published page.
The browser parts need Chrome and fail, never skip, without it.

Heights before this row (measured at 1400 px, the demo with milestones): timeline box 289 px, list row 62 px.
"""
import json
import re
import shutil
import tempfile
import unittest

from _paths import SRC

from clark import page
from test_milestones_page import publish_with_plants
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

OLD_TIMELINE, OLD_ROW = 289, 62
TIMELINE_BUDGET = 175          # about half of 289 (a few px over for the sideways scrollbar some systems draw inside the box)
ROW_BUDGET = 37                # about half of 62: one 17 px line and a small 13 px second line, a little padding

LOOK = r"""(() => {
  const q = (s) => document.querySelector(s), box = (e) => { const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, h: r.height, w: r.width}; };
  const probe = (v) => { const e = document.createElement('i'); e.style.borderColor = `var(${v})`; e.style.borderStyle = 'solid'; document.body.appendChild(e); const c = getComputedStyle(e).borderTopColor; e.remove(); return c; };
  const prim = (v, prop) => { const e = document.createElement('i'); e.style[prop] = `var(${v})`; document.body.appendChild(e); const c = getComputedStyle(e)[prop]; e.remove(); return c; };
  const slipEl = q('[data-slip]'), wrap = q('.mv-wrap'), tog = q('.msl-det'), leg = q('.mlg-b'), bar = q('.msl-bar');
  const rows = [...document.querySelectorAll('.msl-row')].map((row) => {
    const n = row.querySelector('.node'), cs = getComputedStyle(n), rb = row.getBoundingClientRect(), nb = n.getBoundingClientRect();
    const sub = row.querySelector('.msl-sub'), cells = row.querySelector('.msl-cells').getBoundingClientRect();
    return {h: rb.height, cls: n.className, ring: cs.borderTopColor, fill: cs.backgroundColor, w: nb.width, h2: nb.height,
            onRail: Math.abs((nb.left + nb.width / 2) - rb.left) <= 8, mid: Math.abs((nb.top + nb.height / 2) - (rb.top + rb.height / 2)) <= 2,
            sub: sub ? sub.textContent : null, late: sub ? sub.classList.contains('late') : null, subColour: sub ? getComputedStyle(sub).color : null,
            subSize: sub ? parseFloat(getComputedStyle(sub).fontSize) : null, subTop: sub ? sub.getBoundingClientRect().top : null,
            inRow: [...row.querySelectorAll('.msl-cells > *')].every((c) => { const r = c.getBoundingClientRect(); return r.left >= cells.left - 1 && r.right <= cells.right + 1; }),
            clip: [...row.querySelectorAll('.msl-cells > *')].some((c) => c.scrollWidth > c.clientWidth + 1)};
  });
  return {wrap: wrap ? wrap.getBoundingClientRect().height : null, rows,
    tog: tog ? box(tog) : null, leg: leg ? box(leg) : null, bar: bar ? box(bar) : null,
    barKids: bar ? [...bar.children].map((c) => c.className) : null,
    slipColour: slipEl ? getComputedStyle(slipEl).color : null, redText: prim('--status-red-text', 'color'), bodyColour: getComputedStyle(document.body).color,
    colours: {green: probe('--status-green'), red: probe('--status-red'), amber: probe('--status-amber'), surface: probe('--surface')},
    slips: [...document.querySelectorAll('[data-slip]')].map((e) => e.textContent), labs: [...document.querySelectorAll('.mv-lab')].map((e) => { const c = e.cloneNode(true); c.querySelectorAll('.sr').forEach((x) => x.remove()); return c.textContent; }),   // what is seen: the screen-reader-only words are left out
    labH: [...document.querySelectorAll('.mv-lab')].map((e) => e.getBoundingClientRect().height),
    pageScroll: [...document.querySelectorAll('.msv *')].filter((e) => !e.closest('.mv-wrap') && e.getBoundingClientRect().right > window.innerWidth + 1).length > 0,   // inside the section (a published file's tab bar is wider than a narrow screen, which is not this row's)
    wrapInside: wrap ? box(wrap).r <= window.innerWidth + 1 : null};
})()"""

FOCUS = r"""(() => { const e = document.activeElement, c = getComputedStyle(e);
  return {cls: e.className, style: c.outlineStyle, width: parseFloat(c.outlineWidth), colour: c.outlineColor, vis: e.matches(':focus-visible')}; })()"""


class Both(unittest.TestCase):
    """Checks that run on the live page and on a published file."""

    def check_all(self, cdp, sid, where, width, published):
        got = cdp.js(LOOK, sid)
        c = got["colours"]
        # Legend and the hide toggle: one row, the toggle at the left, Legend at the right.
        self.assertIsNotNone(got["bar"], f"{where}: the toggle and Legend share a bar (.msl-bar)")
        self.assertIn("mlg", got["barKids"], f"{where}: Legend is in that bar")
        leg = got["leg"]
        if not published:
            tog = got["tog"]
            self.assertIn("msl-det", got["barKids"], f"{where}: the toggle is in that bar")
            self.assertLess(abs((tog["t"] + tog["b"]) / 2 - (leg["t"] + leg["b"]) / 2), 4, f"{where}: the toggle and Legend are on the same row")
            self.assertLess(tog["r"], leg["l"], f"{where}: the toggle is left of Legend")
            self.assertLess(tog["l"] - got["bar"]["l"], 12, f"{where}: the toggle sits at the left edge")
        self.assertGreater(leg["r"], got["bar"]["r"] - 12, f"{where}: Legend sits at the right edge")
        self.assertLessEqual(got["bar"]["h"], 40, f"{where}: the bar is one row high")
        # The late text on the timeline is '+N days' and nothing else.
        self.assertTrue(got["slips"], f"{where}: the demo has a slipped milestone")
        for s in got["slips"]:
            self.assertRegex(s, r"^\+\d+ days?$", where)
        self.assertEqual(got["slipColour"], got["redText"], f"{where}: the late '+N days' text is the red text colour")
        self.assertNotEqual(got["slipColour"], got["bodyColour"], f"{where}: the late text is not the body colour")
        for r in got["rows"]:
            if r["late"]:
                self.assertEqual(r["subColour"], got["redText"], f"{where}: the late second line is red ({r['sub']})")
        for lab in got["labs"]:
            self.assertNotIn("later", lab, f"{where}: the long late text is gone from the timeline ({lab})")
            self.assertNotIn("Expected", lab, f"{where}: the expected date stays in the detail list ({lab})")
        # Rows: about half the old height, and the ring kept for every state.
        self.assertTrue(got["rows"], where)
        seen = set()
        for r in got["rows"]:
            if width >= 1000:
                self.assertLessEqual(r["h"], ROW_BUDGET, f"{where}: a row is about half the old {OLD_ROW} px ({r['sub']})")
            self.assertTrue(r["onRail"] and r["mid"], f"{where}: the ring sits on the rail, half way down its row ({r['sub']})")
            self.assertEqual((r["w"], r["h2"]), (12, 12), where)
            colour = re.search(r"c-(green|amber|red|blue)", r["cls"])
            if colour:
                want = {"green": c["green"], "red": c["red"], "amber": c["amber"]}.get(colour.group(1))
                if want:
                    self.assertEqual(r["ring"], want, f"{where}: the ring is the state's colour ({r['cls']})")
            filled = " fill" in r["cls"]
            self.assertEqual(r["fill"] == c["green"], filled, f"{where}: only an achieved milestone is filled green ({r['cls']})")
            if not filled:
                self.assertEqual(r["fill"], c["surface"], where)
            seen.add((colour.group(1) if colour else None, filled))
            self.assertIsNotNone(r["sub"], f"{where}: the second line is there")
            self.assertTrue(r["sub"] == "Agreed" or r["sub"].startswith(("Expected ", "Achieved", "Forecast", "No agreed")), r["sub"])
            self.assertEqual(r["late"], r["sub"].startswith("Expected ") and "later" in r["sub"], f"{where}: only the late second line is the red one ({r['sub']})")
            self.assertLess(r["subSize"], 13.5, f"{where}: the second line is small")
        self.assertIn(("red", False), seen, f"{where}: a red ring is on the page")
        return got

    def test_the_live_page_at_1400_and_900_light_and_dark(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = page_target(cdp)
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": theme}]}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p=MOSS"}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)))
                    where = f"live {theme} {width}px"
                    got = self.check_all(cdp, sid, where, width, False)
                    if width == 1400:
                        self.assertLessEqual(got["wrap"], TIMELINE_BUDGET, f"{where}: the timeline is about half the old {OLD_TIMELINE} px")
                        self.assertTrue(all(h <= 24 for h in got["labH"]), f"{where}: one label line per milestone ({got['labH']})")

    def test_the_published_file_at_1400_and_900_light_and_dark(self):
        demo, folder, path, _ids = publish_with_plants()
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = page_target(cdp)
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": theme}]}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                    cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)))
                    where = f"published {theme} {width}px"
                    got = self.check_all(cdp, sid, where, width, True)
                    if width == 1400:
                        self.assertLessEqual(got["wrap"], TIMELINE_BUDGET, where)
                    html = cdp.js("document.documentElement.outerHTML", sid)
                    self.assertNotIn("Activity", cdp.js("document.querySelector('.msv').innerText", sid), "no Activity text in the section")
                    self.assertNotIn("PLANTED-INTERNAL", html, "no Source or internal text reaches the published file")

    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)


class Keys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def visit(self, cdp, port, theme="light", width=1400):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": theme}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#milestones&p=MOSS"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-det')", sid)))
        return sid

    def tab_to(self, cdp, sid, cls):
        cdp.js("document.querySelector('.msv-b').focus()", sid)           # start before the bar, then press Tab like a keyboard user
        for _ in range(60):
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9}, sid)
            if cdp.js(f"document.activeElement.classList.contains('{cls}')", sid):
                return
        self.fail(f"Tab never reached {cls}")

    def test_the_toggle_and_legend_show_a_focus_ring_for_the_keyboard_and_the_toggle_comes_first(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for theme in ("light", "dark"):
            with self.subTest(theme=theme), chrome() as cdp:
                sid = self.visit(cdp, s.port, theme)
                order = []
                for cls in ("msl-det", "mlg-b"):
                    self.tab_to(cdp, sid, cls)
                    f = cdp.js(FOCUS, sid)
                    order.append(cdp.js("document.activeElement.getBoundingClientRect().left", sid))
                    self.assertTrue(f["vis"] and f["style"] != "none" and f["width"] >= 2, f"{theme} {cls}: a visible ring ({f})")
                self.assertLess(order[0], order[1], "Tab goes left to right: the toggle, then Legend")

    def test_the_hide_choice_is_still_remembered_and_the_legend_stays_when_hidden(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = self.visit(cdp, s.port)
            cdp.js("document.querySelector('.msl-det').click()", sid)
            self.assertIs(json.loads(cdp.js("localStorage.getItem('clark.msDet.page')", sid)), False)
            sid = self.visit(cdp, s.port)
            got = cdp.js("""(() => ({rows: [...document.querySelectorAll('.msl-row')].filter((e) => e.getClientRects().length).length,
              label: document.querySelector('.msl-det').textContent, same: (() => { const a = document.querySelector('.msl-det').getBoundingClientRect(), b = document.querySelector('.mlg-b').getBoundingClientRect();
              return Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) < 4; })()}))()""", sid)
            self.assertEqual((got["rows"], got["label"], got["same"]), (0, "Show milestone details", True), "still hidden, and the two stay on one row")


class Stylesheet(unittest.TestCase):
    def test_cells_are_two_lines_not_ten_px_padding(self):
        css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        cells = re.search(r"\n\.msl-cells \{([^}]*)\}", css).group(1)
        self.assertNotIn("padding: 10px", cells, "the row is compact now")


if __name__ == "__main__":
    unittest.main()

"""Row 1396: the Milestones list in the Classic Theme as the prototype draws it, as Chrome computes it at 1400 px, light and dark.

Run: python3 dev/run_tests.py test_gap_1396
Fails, never skips, without Chrome. Value table (ticket 1396): row padding 9px 8px 9px 20px, divider and hover from the line-soft / band-bg tokens, name in the heading
colour, heading row 13px / 500 / .08em with padding 4px 8px 4px 20px, percent min-width 36 and weight 600, only the name of a left-out row greyed (the row keeps opacity 1),
the four state colours. Not built: columns (decided out). The Legend row (ruling 20-11, row 8): the six states in one always-visible 13px row on the Milestones page and on the Dashboard, in addition to the status tracker.
Cards (theme None) keeps the installed values. Every colour is read through the token it must equal.
"""
import re
import shutil
import tempfile
import unittest

from _paths import ROOT

import tempfile
from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

CODE = "MOSS"
MEASURE = r"""(() => {
  const rowsAll = document.querySelectorAll('.msl-row');
  if (!document.querySelector('.msl-prog .num')) { const c = rowsAll[0].cloneNode(true); c.id = 'fx-prog'; c.querySelector('.msl-prog').innerHTML = '<span class="pbar"><i style="width:40%"></i></span><span class="num">40%</span>'; rowsAll[0].parentNode.appendChild(c); }
  const cs = (e, p) => getComputedStyle(e)[p];
  const rows = [...document.querySelectorAll('.msl-row')];
  const r0 = rows[0], cells = r0.querySelector('.msl-cells'), list = document.querySelector('.msl');
  const probe = (v) => { const e = document.createElement('i'); e.style.borderColor = `var(${v})`; e.style.borderStyle = 'solid'; document.body.appendChild(e); const c = getComputedStyle(e).borderTopColor; e.remove(); return c; };
  const after = getComputedStyle(r0, '::after');
  const num = document.querySelector('.msl-prog .num');
  const box = document.querySelector('.msl-box');
  const states = {};
  for (const c of ['blue', 'green', 'amber', 'red']) {
    const n = document.querySelector('.msl-row .node.c-' + c), t = document.querySelector('.msl-row .mst.c-' + c);
    states[c] = {node: n ? cs(n, 'borderTopColor') : null, text: t ? cs(t, 'color') : null};
  }
  const hd = document.querySelector('.msl-hd'), hc = document.querySelector('.msl-hc');
  const head = hd ? {display: cs(hd,'display'), marginTop: cs(hd,'marginTop'), border: cs(hd,'borderBottomColor'), size: cs(hc,'fontSize'), w: cs(hc,'fontWeight'), ls: cs(hc,'letterSpacing'), pad: [cs(hc,'paddingTop'), cs(hc,'paddingRight'), cs(hc,'paddingBottom'), cs(hc,'paddingLeft')], cols: cs(hc,'gridTemplateColumns'), rowCols: cs(cells,'gridTemplateColumns'), h: hd.getBoundingClientRect().height} : null;
  return {head, pad: [cs(cells,'paddingTop'), cs(cells,'paddingRight'), cs(cells,'paddingBottom'), cs(cells,'paddingLeft')], listTop: cs(list, 'marginTop'), gaps: (() => { const h = document.querySelector('.msl-hdw'), b = document.querySelector('.msl-bar'); return {prev: list.previousElementSibling.className, hdwBottomToList: list.getBoundingClientRect().top - h.getBoundingClientRect().bottom, barToHdw: h.getBoundingClientRect().top - b.getBoundingClientRect().bottom, hdMargin: cs(document.querySelector('.msl-hd'), 'marginTop'), hdwMargin: cs(h, 'marginTop')}; })(),
    divider: after.backgroundColor, rowH: r0.getBoundingClientRect().height,
    name: {w: cs(r0.querySelector('.msl-name'), 'fontWeight'), c: cs(r0.querySelector('.msl-name'), 'color')},
    num: num ? {minW: cs(num, 'minWidth'), w: cs(num, 'fontWeight'), boxW: num.getBoundingClientRect().width} : null,
    states, tokens: {heading: probe('--heading'), grey100: probe('--grey-100'), bandBg: probe('--band-bg')}, pageScroll: document.documentElement.scrollWidth > innerWidth};
})()"""

def open_page(cdp, width, scheme, theme):
    sid = page_target(cdp)
    cdp.call("Page.enable", {}, sid)
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
    return sid

def hover_bg(cdp, sid):
    r = cdp.js("(() => { const b = document.querySelector('.msl-row').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()", sid)
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, sid)
    return cdp.js("getComputedStyle(document.querySelector('.msl-row')).backgroundColor", sid)

RULES = ((ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
TOKENS = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "tokens.css").read_text(encoding="utf-8")
NAME = "prototype-2.0"


def own_block():
    tail = RULES[RULES.index("/* Row 1396:"):]
    return tail[:tail.index("\n/* Row ", 1)]


class Source(unittest.TestCase):
    def test_the_block_sits_before_row_1314_which_stays_the_last_row_line(self):
        rows = [l for l in RULES.splitlines() if l.startswith("/* Row ")]
        self.assertTrue(rows[-1].startswith("/* Row 1314"))
        self.assertTrue(any(r.startswith("/* Row 1396") for r in rows[:-1]))

    def test_no_hex_colour_and_no_tmp_path_in_the_rules(self):
        self.assertIsNone(re.search(r"#[0-9A-Fa-f]{3,8}\b", own_block()))
        self.assertNotIn("/tmp", RULES)

    def test_the_amber_dot_token_is_in_light_and_both_dark_blocks(self):
        self.assertEqual(TOKENS.count("--ms-amber-shape:"), 3)


def settle(cdp, sid, scheme):
    if cdp.js("!!document.querySelector('.msl-all')", sid):
        cdp.js("document.querySelector('.msl-all').click()", sid)
    wait(lambda: cdp.js("document.querySelectorAll('.msl-row').length", sid) > 5)


class Computed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def measure(self, theme, width, scheme):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, width, scheme, theme)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p={CODE}"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)), "the list drew")
            settle(cdp, sid, scheme)
            got = cdp.js(MEASURE, sid)
            got["hover"] = hover_bg(cdp, sid)
            got["out"] = cdp.js("""(() => { const r = document.querySelectorAll('.msl-row')[1]; r.classList.add('out'); const n = r.querySelector('.msl-name');
                return {opacity: getComputedStyle(r).opacity, name: getComputedStyle(n).color}; })()""", sid)
            got["muted"] = cdp.js("(() => { const e = document.createElement('i'); e.style.color = 'var(--text-muted)'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })()", sid)
            got["tone"] = cdp.js("(() => { const p = (v) => { const e = document.createElement('i'); e.style.color = `var(${v})`; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; }; return {blue: p('--tone-blue-text'), green: p('--status-green-text'), red: p('--status-red-text'), amber: p('--ms-amber-shape'), amberText: p('--status-amber-text')}; })()", sid)
            return got

    def check_classic(self, got, where):
        self.assertEqual(got["pad"], ["9px", "8px", "9px", "20px"], where)
        self.assertEqual(got["divider"], got["tokens"]["grey100"], where)
        self.assertEqual(got["name"]["w"], "600", where)
        self.assertEqual(got["name"]["c"], got["tokens"]["heading"], where)
        self.assertEqual(got["hover"], got["tokens"]["bandBg"], where)
        h = got["head"]
        self.assertEqual((h["size"], h["w"], h["pad"][0], h["pad"][2], h["pad"][3]), ("13px", "500", "4px", "4px", "20px"), where)
        self.assertEqual(h["ls"], "1.04px", where)
        self.assertEqual(h["pad"][1], "78px", where + ": 8px plus the 70px the eye and More buttons take (edit.css, editor only); a published list has none of them")
        self.assertEqual((got["gaps"]["barToHdw"], got["gaps"]["hdwBottomToList"]), (6, 0), where + ": the list starts 6px under the bar (ticket row 1, list margin-top 6)")
        self.assertEqual((got["num"]["minW"], got["num"]["w"]), ("36px", "600"), where)
        self.assertEqual(got["num"]["boxW"], 44, where + ": the percent sits in a fixed 44px slot, so every bar is the same length (the 100% row too: test_ms_progress_col_1315)")
        self.assertEqual(got["out"]["opacity"], "1", where)
        self.assertEqual(got["out"]["name"], got["muted"], where)
        t = got["tone"]
        self.assertEqual(got["states"]["blue"], {"node": t["blue"], "text": t["blue"]}, where)
        self.assertEqual(got["states"]["green"]["node"], t["green"], where)
        self.assertEqual(got["states"]["red"]["node"], t["red"], where)
        self.assertEqual(got["states"]["amber"]["node"], t["amber"], where)
        self.assertEqual((got["states"]["green"]["text"], got["states"]["red"]["text"], got["states"]["amber"]["text"]), (t["green"], t["red"], t["amberText"]), where + ": the state words keep the status text colours, which are the prototype's --green, --red and --amber")
        self.assertFalse(got["pageScroll"], where)

    def test_classic_light_1400(self):
        got = self.measure(NAME, 1400, "light")
        self.check_classic(got, "light")
        self.assertEqual(got["divider"], "rgb(233, 237, 246)")
        self.assertEqual(got["hover"], "rgb(243, 245, 251)")
        self.assertEqual(got["states"]["blue"]["node"], "rgb(47, 75, 184)")
        self.assertEqual(got["states"]["amber"]["node"], "rgb(197, 138, 0)")
        self.assertEqual(got["states"]["green"]["node"], "rgb(0, 107, 94)")
        self.assertEqual(got["states"]["red"]["node"], "rgb(163, 48, 31)")
        self.assertEqual([got["states"][c]["text"] for c in ("green", "amber", "red")], ["rgb(0, 107, 94)", "rgb(138, 90, 0)", "rgb(163, 48, 31)"])

    def test_classic_dark_1400(self):
        got = self.measure(NAME, 1400, "dark")
        self.check_classic(got, "dark")

    def dash_head(self, theme):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, 1400, "light", theme)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#dashboard&p={CODE}"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-box[data-place=\"dash\"] .msl-row, .msl-box:not([data-place=\"page\"]) .msl-row')", sid)), "the Dashboard list drew")
            return cdp.js("(() => { const h = document.querySelector('.msl-box:not([data-place=\"page\"]) .msl-hdw'); return h ? getComputedStyle(h).display : 'absent'; })()", sid)

    def test_dashboard_list_has_no_heading_row_in_classic_and_cards_keeps_it(self):
        self.assertEqual(self.dash_head(NAME), "none")
        self.assertNotIn(self.dash_head(None), ("none", "absent"))

    def test_dashboard_list_starts_6px_under_the_bar_in_classic(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, 1400, "light", NAME)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#dashboard&p={CODE}"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-box:not([data-place=\"page\"]) .msl-row')", sid)), "the Dashboard list drew")
            gap = cdp.js("(() => { const b = document.querySelector('.msl-box:not([data-place=\"page\"])'); return b.querySelector('.msl').getBoundingClientRect().top - b.querySelector('.msl-bar').getBoundingClientRect().bottom; })()", sid)
        self.assertEqual(gap, 6)

    def test_plain_class_is_in_classic_dom_only(self):
        src = (ROOT / "src/clark/page/src/components/MsList.jsx").read_text(encoding="utf-8")
        self.assertIn('class={`msl-hdw${classicTheme() ? " plain" : ""}`}', src, "the heading row's plain class is gated with classicTheme()")
        self.assertNotIn('class="msl-hdw plain"', src)

    def test_cards_keeps_the_installed_values(self):
        got = self.measure(None, 1400, "light")
        self.assertEqual(got["pad"], ["14px", "8px", "14px", "22px"])
        self.assertEqual(got["divider"], "rgb(217, 224, 239)")
        self.assertEqual(got["states"]["blue"]["node"], "rgb(91, 71, 216)")
        self.assertEqual(got["states"]["amber"]["node"], "rgb(232, 160, 19)")
        self.assertEqual(got["head"]["w"], "600")
        self.assertEqual(got["num"]["minW"], "auto")


LEGEND = r"""(() => {
  const row = document.querySelector('.msl-bar .mlg-row');
  if (!row) return null;
  const r = row.getBoundingClientRect(), st = getComputedStyle(row), items = [...row.querySelectorAll('[data-legend-state]')];
  const pop = document.querySelector('.msl-bar .mlg');
  return {display: st.display, size: st.fontSize, visible: r.width > 0 && r.height > 0 && st.visibility === 'visible', inView: r.left >= 0 && r.right <= innerWidth,
    words: items.map((e) => e.textContent.trim()), sizes: items.map((e) => getComputedStyle(e).fontSize), marks: items.every((e) => !!e.querySelector('svg')),
    popover: pop ? getComputedStyle(pop).display : 'absent', tracker: !!document.querySelector('[data-tracker]'),
    barTop: document.querySelector('.msl-bar').getBoundingClientRect().bottom <= document.querySelector('.msl').getBoundingClientRect().top + 1,
    pageScroll: document.documentElement.scrollWidth > innerWidth};
})()"""
SIX = ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast"]


class Legend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def legend(self, theme, width, route):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, width, "light", theme)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#{route}&p={CODE}"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)), "the list drew")
            return cdp.js(LEGEND, sid)

    def check_classic(self, got, where):
        self.assertIsNotNone(got, where)
        self.assertEqual(got["words"], SIX, where)
        self.assertEqual(got["display"], "flex", where)
        self.assertEqual(got["size"], "13px", where)
        self.assertEqual(set(got["sizes"]), {"13px"}, where)
        self.assertTrue(got["visible"] and got["inView"] and got["marks"], where)
        self.assertIn(got["popover"], ("none", "absent"), where)
        self.assertTrue(got["barTop"], where)
        self.assertFalse(got["pageScroll"], where)

    def test_classic_page_1400(self):
        self.check_classic(self.legend(NAME, 1400, "milestones"), "page 1400")

    def test_classic_page_900(self):
        self.check_classic(self.legend(NAME, 900, "milestones"), "page 900")

    def test_classic_dashboard_1400_keeps_the_tracker(self):
        got = self.legend(NAME, 1400, "dashboard")
        self.check_classic(got, "dash 1400")
        self.assertTrue(got["tracker"])

    def test_classic_dashboard_900(self):
        self.check_classic(self.legend(NAME, 900, "dashboard"), "dash 900")

    def test_cards_draws_no_legend_row_and_keeps_the_popover(self):
        for route in ("milestones", "dashboard"):
            self.assertIsNone(self.legend(None, 1400, route), route)
        self.assertNotEqual(self.popover(None), "none")

    def popover(self, theme):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, 1400, "light", theme)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p={CODE}"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)), "the list drew")
            return cdp.js("(() => { const p = document.querySelector('.msl-bar .mlg'); return p ? getComputedStyle(p).display : 'absent'; })()", sid)


if __name__ == "__main__":
    unittest.main()

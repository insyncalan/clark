"""Rework 1997, the places the 1396 / 1398 tests left open (found by a diff-only mutation sweep): the Legend row's markup and layout, the list's top gap, the soft divider and
heading rule through the token, the filled green dot, the calendar's outer rules, weekday row and chip rule, and the 900 keep of the 64 high day cell. Chrome required.
Run: python3 dev/run_tests.py test_gap_1997_survivors"""
import shutil
import tempfile
import unittest

from clark import page
from test_gap_1396 import NAME, CODE, open_page, settle
from test_milestones_page import BrowserBase
from test_server import Running, chrome, wait
from test_work_filters import need_chrome
from test_work_items import load_demo

PROBE = "const probe = (v, p) => { const e = document.createElement('i'); e.style[p || 'color'] = `var(${v})`; document.body.appendChild(e); const c = getComputedStyle(e)[p || 'color']; e.remove(); return c; };"
LIST = PROBE + r"""(() => {
  const cs = (e, p) => getComputedStyle(e)[p], list = document.querySelector('.msl'), r0 = document.querySelector('.msl-row'), hd = document.querySelector('.msl-hd');
  const fill = document.querySelector('.msl-row .node.fill.c-green');
  const row = document.querySelector('.msl-bar .mlg-row'), bar = document.querySelector('.msl-bar'), items = row ? [...row.querySelectorAll('[data-legend-state]')] : [];
  return {listTop: cs(list, 'marginTop'), prevIsHead: !!(list.previousElementSibling && list.previousElementSibling.classList.contains('msl-hdw')),
    divider: getComputedStyle(r0, '::after').backgroundColor, soft: probe('--line-soft', 'color'), headRule: hd ? cs(hd, 'borderBottomColor') : null,
    fill: fill ? cs(fill, 'backgroundColor') : null, green: probe('--status-green-text', 'color'),
    attrs: row ? [row.hasAttribute('data-legend-row'), row.getAttribute('role'), row.getAttribute('aria-label')] : null,
    itemColours: items.map((e) => e.className.replace('mst ', '') + ':' + cs(e, 'color')),
    layout: row ? {wrap: cs(row, 'flexWrap'), col: cs(row, 'columnGap'), rowGap: cs(row, 'rowGap'), color: cs(row, 'color'), muted: probe('--text-muted', 'color'),
      right: Math.round(bar.getBoundingClientRect().right - row.getBoundingClientRect().right), ml: cs(row, 'marginLeft')} : null};
})()"""
CAL = r"""(() => { const cs = (e, p) => getComputedStyle(e)[p], g = document.querySelector('.cal-g'), cells = [...g.children], d = document.querySelector('.cal-dow span'), dow = document.querySelector('.cal-dow'),
  chip = document.querySelector('.cal-ms:not(.ghost)'), sp = chip.querySelector('span');
  return {gTop: cs(g, 'borderTopColor'), gLeft: cs(g, 'borderLeftColor'), dTop: cs(dow, 'borderTopWidth') + cs(dow, 'borderTopColor'), dLeft: cs(dow, 'borderLeftWidth'),
    cellR: cs(cells[8], 'borderRightColor'), cellB: cs(cells[8], 'borderBottomColor'), fri: cs(cells[4], 'backgroundColor'), mon: cs(cells[7], 'backgroundColor'), sat: cs(cells[12], 'backgroundColor'), sun: cs(cells[13], 'backgroundColor'),
    dowPad: cs(d, 'paddingTop') + ' ' + cs(d, 'paddingLeft'), dowR: cs(d, 'borderRightWidth'), dowB: cs(d, 'borderBottomWidth'), todayN: (() => { const n = document.querySelector('.cal-d.today .cal-n'); return cs(n, 'color'); })(),
    brand: (() => { const e = document.createElement('i'); e.style.color = 'var(--brand-blue)'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })(),
    minH: cs(cells[8], 'minHeight'), chipBg: cs(chip, 'backgroundColor'), band: (() => { const e = document.createElement('i'); e.style.color = 'var(--band-bg)'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })(),
    chipOv: cs(sp, 'overflow'), chipTo: cs(sp, 'textOverflow'), chipWs: cs(sp, 'whiteSpace'), chipWrap: cs(sp, 'overflowWrap')}; })()"""


class Rework1997Survivors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def list_page(self, width, scheme, route="milestones"):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, width, scheme, NAME)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#{route}&p={CODE}"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)), "the list drew")
            settle(cdp, sid, scheme)
            return cdp.js(LIST, sid)

    def test_list_and_legend_row(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme):
                g = self.list_page(1400, scheme)
                if not g["prevIsHead"]:
                    self.assertEqual(g["listTop"], "6px")
                self.assertEqual(g["divider"], g["soft"], "the row divider is the soft line")
                self.assertEqual(g["headRule"], g["soft"], "the heading rule is the soft line")
                if g["fill"] is not None:
                    self.assertEqual(g["fill"], g["green"], "a filled green dot")
                self.assertEqual(g["attrs"], [True, "group", "Legend"])
                self.assertEqual(len(g["itemColours"]), 6)
                self.assertTrue(all(c.startswith("c-") for c in g["itemColours"]), g["itemColours"])
                self.assertEqual(len({c.split(":")[1] for c in g["itemColours"]}) > 1, True, "the six states do not share one colour")
                lay = g["layout"]
                self.assertEqual((lay["wrap"], lay["col"], lay["rowGap"]), ("wrap", "14px", "4px"))
                self.assertEqual(lay["color"], lay["muted"])
                self.assertLessEqual(lay["right"], 1, "the row sits at the right of the bar")


class Rework1997Calendar(BrowserBase, unittest.TestCase):
    def serve(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
        self.addCleanup(s.close)
        return s.port

    def test_calendar(self):
        need_chrome()
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-d.today .cal-n') && !!document.querySelector('.cal-ms')", sid)))
            g = cdp.js(CAL, sid)
            soft = "rgb(233, 237, 246)"
            self.assertEqual((g["gTop"], g["gLeft"], g["cellR"], g["cellB"]), (soft,) * 4)
            self.assertEqual(g["dTop"], "1px" + soft)
            self.assertEqual(g["dLeft"], "1px")
            self.assertEqual((g["dowR"], g["dowB"], g["dowPad"]), ("1px", "1px", "4px 6px"))
            self.assertEqual(g["fri"], "rgba(0, 0, 0, 0)")
            self.assertEqual(g["mon"], "rgba(0, 0, 0, 0)")
            self.assertEqual((g["sat"], g["sun"]), ("rgb(246, 248, 252)",) * 2)
            self.assertEqual(g["todayN"], g["brand"])
            self.assertEqual(g["chipBg"], g["band"])
            self.assertEqual((g["chipOv"], g["chipTo"], g["chipWs"], g["chipWrap"]), ("hidden", "ellipsis", "nowrap", "normal"))
            for w, h in ((900, "64px"), (901, "78px")):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.cal-g').children[8]).minHeight", sid), h, f"day cell at {w}")


if __name__ == "__main__":
    unittest.main()

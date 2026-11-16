"""Row 1230, part 3: the Dashboard Milestones section's list is a table of five columns, Milestone, State, Agreed, Expected or achieved
and Progress, under a heading row that is drawn in View and in Edit alike. A row still opens the peek; the Hide / Show milestone details toggle stays.

Run: python3 dev/run_tests.py -j 1 test_ms_table_1230   (headless Chrome; fails, never skips, without it)
Fictional data over a real store; "today" is 2026-10-28. Widths 1400 and 900 only; no keyboard walk-through.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark import page, server as sv
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, page_target

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
HEADS = ["Milestone", "State", "Agreed", "Expected or achieved", "Progress"]
ROWS = [  # name, fields, agreed cell, expected-or-achieved date cell, small line (None: no line)
    ("T on track", {"baseline_date": "2030-04-01"}, "01-04-2030", "01-04-2030", None),
    ("T late", {"baseline_date": "2020-05-01", "forecast_date": "2030-05-01"}, "01-05-2020", None, None),
    ("T done", {"baseline_date": "2026-09-10", "status": "Done", "actual_date": "2026-09-15"}, "10-09-2026", "15-09-2026", "Achieved 5 days after the agreed date"),
    ("T dropped", {"baseline_date": "2030-06-01", "status": "Cancelled"}, "01-06-2030", "01-06-2030", "No longer going ahead"),
    ("T maybe", {"forecast_date": "2030-07-01", "state": "Forecast", "state_set": 1}, "No agreed date", "01-07-2030", "Forecast"),
]

SEE = """(() => {
  const box = document.querySelector('.msv[data-place^=sec-] .msl-box');
  if (!box) return null;
  const hd = box.querySelector('.msl-hd'), vis = (e) => !!e && e.getBoundingClientRect().width > 0 && getComputedStyle(e).display !== 'none';
  const rows = {};
  for (const li of box.querySelectorAll('.msl-row')) {
    const c = (k) => { const e = li.querySelector(`[data-col=${k}]`); return e ? e.textContent.trim() : null; };
    const date = li.querySelector('[data-col=date]'), b = date && date.querySelector('b'), sub = date && date.querySelector('.msl-sub');
    const x = (k) => { const e = li.querySelector(`[data-col=${k}]`); return e ? Math.round(e.getBoundingClientRect().left) : null; };
    rows[c('name').replace(/\\s+/g, ' ')] = {state: c('state'), agreed: c('agreed'), date: b && b.textContent.trim(), sub: sub ? sub.textContent.trim() : null,
      late: !!(sub && sub.classList.contains('late')), node: !!li.querySelector('.node'), order: ['name', 'state', 'agreed', 'date', 'prog'].map(x),
      prog: c('prog'), progSpoken: (() => { const e = li.querySelector('[data-col=prog] [aria-label]'); return e ? e.getAttribute('aria-label') : null; })(),
      progVisible: (() => { const e = li.querySelector('[data-col=prog] .muted'); return !!e && e.getBoundingClientRect().width > 0; })()};
  }
  const rb = box.getBoundingClientRect();
  return {heads: hd ? [...hd.querySelectorAll('.msl-hc > span')].map((s) => s.textContent.trim()) : null, headShown: vis(hd), rows,
          inside: box.scrollWidth <= box.clientWidth + 1, noScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
          hdAligned: hd ? [...hd.querySelectorAll('.msl-hc > span')].map((s) => Math.round(s.getBoundingClientRect().left)) : null,
          firstRowCells: (() => { const li = box.querySelector('.msl-row'); return ['name', 'state', 'agreed', 'date', 'prog'].map((k) => Math.round(li.querySelector(`[data-col=${k}]`).getBoundingClientRect().left)); })()};
})()"""


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            for name, f, *_ in ROWS:
                st.create("milestones", {"project": "ABC", "name": name, "source": "demo", **f})
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def visit(self, cdp, width, edit, where="#dashboard&p=ABC"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{where}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msv .msl-row')", sid), 10), "the block drew")
        if edit and not where.startswith("#milestones"):      # the Milestones page has no View mode: it is always the editor
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') === 'true'", sid), 10), "Edit is on")
        cdp.js("(document.querySelector('.msv .msl-all') || {click() {}}).click()", sid)       # every row, not the first five
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 10))
        return sid


class Table(Base):
    def test_five_columns_under_a_heading_row_in_view_and_in_edit(self):
        for width in (1400, 900):
            for edit in (False, True):
                with self.subTest(width=width, edit=edit), chrome() as cdp:
                    sid = self.visit(cdp, width, edit)
                    got = cdp.js(SEE, sid)
                    self.assertEqual(got["heads"], HEADS)
                    self.assertTrue(got["headShown"], "the heading row is drawn")
                    self.assertTrue(got["inside"] and got["noScroll"], "no sideways scroll")
                    for name, _f, agreed, date, sub in ROWS:
                        r = got["rows"][name]
                        self.assertEqual(r["agreed"], agreed, name)
                        if date:
                            self.assertEqual(r["date"], date, name)
                        self.assertEqual(r["sub"], sub, name) if name != "T late" else None
                        self.assertTrue(r["node"], f"{name}: its mark is on the rail")
                        self.assertEqual(r["order"], sorted(r["order"]), f"{name}: the cells run left to right in the heading's order")
                        self.assertEqual(len(set(r["order"])), 5, f"{name}: five columns")
                    for name, r in got["rows"].items():
                        self.assertEqual(r["prog"], "\u2014", f"{name}: no progress shows a dash")
                        self.assertTrue(r["progVisible"], f"{name}: the dash is visible")
                        self.assertEqual(r["progSpoken"], "Progress not set", f"{name}: and is spoken as 'Progress not set'")
                    late = got["rows"]["T late"]
                    self.assertTrue(late["late"] and re.fullmatch(r"\+\d+ days", late["sub"]) and late["date"] == "01-05-2030", f"a slipped row: {late}")
                    self.assertEqual(got["firstRowCells"], got["hdAligned"], "each heading sits over its column")

    def test_a_row_opens_the_peek_and_the_toggle_hides_the_table_and_its_heading(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width, False)
                cdp.js("document.querySelector('.msv [data-ms] .msl-cells').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.peek')", sid), 10), "the row opened the peek")
                cdp.js("document.querySelector('.msv [data-msdet]').click()", sid)
                got = cdp.js("(() => { const b = document.querySelector('.msv [data-msdet]'); return [b.getAttribute('aria-expanded'), b.textContent.trim(), "
                             "document.querySelector('#' + b.getAttribute('aria-controls')).hidden, !!document.querySelector('.msv .msl-hd') && document.querySelector('.msv .msl-hd').getBoundingClientRect().width]; })()", sid)
                self.assertEqual(got, ["false", "Show milestone details", True, 0])


PAGE = """(() => {
  const box = document.querySelector('#milestones .msl-box');
  if (!box) return null;
  const hd = box.querySelector('.msl-hd'), li = box.querySelector('.msl-row'), cells = li.querySelector('.msl-cells');
  const x = (e) => Math.round(e.getBoundingClientRect().left);
  const cols = [...cells.children].filter((e) => e.dataset.col).map((e) => e.dataset.col);
  const sub = cells.querySelector(':scope > .msl-sub');
  return {heads: hd ? [...hd.querySelectorAll('.msl-hc > span')].map((s) => s.textContent.trim()) : null, cols, sub: sub ? sub.textContent.trim() : null,
          agreedCell: !!cells.querySelector('[data-col=agreed]'), dateInside: !!cells.querySelector('.msl-date .msl-sub'),
          first: cols.map((k) => x(cells.querySelector(`[data-col=${k}]`))), place: box.dataset.place};
})()"""


class PageList(Base):
    """The ruling: the Dashboard section only. The Milestones page keeps its list as it was: Date, Milestone, State, Progress, the
    Agreed line under the date and name, and a heading row in Edit only."""

    def test_the_milestones_page_keeps_its_old_columns_and_an_edit_only_heading(self):
        for width in (1400, 900):
            for edit in (True,):
                with self.subTest(width=width, edit=edit), chrome() as cdp:
                    sid = self.visit(cdp, width, edit, "#milestones&p=ABC")
                    got = cdp.js(PAGE, sid)
                    self.assertEqual(got["place"], "page")
                    self.assertEqual(got["cols"], ["date", "name", "state", "prog"], "the old four columns, in the old order")
                    self.assertFalse(got["agreedCell"], "no Agreed column on the page")
                    self.assertFalse(got["dateInside"], "the note is not inside the date cell")
                    self.assertTrue(got["sub"], "the old second line (Agreed, or the Expected date) sits in the row under the date and name")
                    self.assertEqual(got["heads"], ["Date", "Milestone", "State", "Progress"],
                                     "the heading row over the old four")


PAGE_SRC = SRC / "clark" / "page" / "src"
ENTRY = """import { render, h } from "preact";
import { MsList } from "%(src)s/components/MsList.jsx";
import { milestoneRows } from "%(src)s/logic/milestones.js";
import * as TC from "%(src)s/logic/tableColumns.js";
import * as M from "%(src)s/logic/milestones.js";
import { fromFile } from "%(src)s/stores/report.js";
window.T = { TC, M, fromFile, boxes: [], drawN(props, n, extra) {
  const box = document.createElement("div"); document.body.appendChild(box);
  const list = Array.from({ length: n }, (_, i) => ({ id: i + 1, name: "M" + (i + 1), baseline_date: "2030-04-0" + (i + 1), sort_order: i === 0 ? 3 : 0, ...(extra || {}) }));
  const rows = M.milestoneRows(list, "2026-10-28", false);
  render(h(MsList, { rows, ...props }), box);
  const first = box.querySelector(".msl-row");
  return { all: !!box.querySelector(".msl-all"), trimmed: box.querySelectorAll(".msl-row").length, vars: box.querySelector(".msl-box").getAttribute("style"),
           set: !!box.querySelector(".msl-hd.set"), cells: Object.fromEntries([...first.querySelectorAll(".msl-cells [data-col]")].map((e) => [e.dataset.col, e.textContent.trim()])),
           cls: Object.fromEntries([...first.querySelectorAll(".msl-cells [data-col]")].map((e) => [e.dataset.col, e.className])), box };
}, draw(props) {
  const box = document.createElement("div"); document.body.appendChild(box);
  const rows = milestoneRows([{ id: 1, name: "One", baseline_date: "2030-04-01" }, { id: 2, name: "Two", baseline_date: "2030-05-01" }], "2026-10-28", false);
  render(h(MsList, { rows, ...props }), box);
  const hd = box.querySelector(".msl-hd");
  return { hd: !!hd, set: !!hd && hd.classList.contains("set"), cols: [...box.querySelectorAll(".msl-hd [data-col]")].map((e) => e.dataset.col), vars: box.querySelector(".msl-box").getAttribute("style") };
} };
"""
_BUNDLE = {}


def bundle():
    """MsList.jsx itself, drawn by Preact in headless Chrome with a stand-in for Edit's width and column hooks (`CW`, `CM`)."""
    if "js" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            entry, out = Path(tmp) / "entry.jsx", Path(tmp) / "out.js"
            entry.write_text(ENTRY % {"src": str(PAGE_SRC)}, encoding="utf-8")
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", *build_page.preact_flags(),
                                str(entry), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["js"] = out.read_text(encoding="utf-8")
    return _BUNDLE["js"]


STAND_IN = "{ px: () => null, head: () => ({}), grip: () => null }"


class ListUnits(unittest.TestCase):
    """Row 1230 rulings on MsList.jsx and tableColumns.js, drawn for real in Chrome (one browser at a time)."""

    @classmethod
    def setUpClass(cls):
        with chrome() as cdp:
            cls.sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": bundle(), "returnByValue": True}, cls.sid)
            assert "exceptionDetails" not in res, res
            cls.drawn = {}
            for name, props in {
                "page-view": "{ place: 'page' }",
                "dash-view": "{ place: 'sec-1' }",
                "dash-std": "{ place: 'sec-1', CW: () => (%(cw)s), CM: () => ({ shown: T.TC.standardIds('msDash'), rowProps: {}, button: () => null, menu: null }) }",
                "dash-added": "{ place: 'sec-1', CW: () => (%(cw)s), CM: () => ({ shown: T.TC.shownIds('msDash', ['agreed', 'date', 'prog', 'owner']), rowProps: {}, button: () => null, menu: null }) }",
                "dash-removed": "{ place: 'sec-1', CW: () => (%(cw)s), CM: () => ({ shown: T.TC.shownIds('msDash', ['agreed', 'date']), rowProps: {}, button: () => null, menu: null }) }",
            }.items():
                got = cdp.call("Runtime.evaluate", {"expression": f"(() => {{ document.body.innerHTML = ''; return T.draw({props % {'cw': STAND_IN}}); }})()", "returnByValue": True}, cls.sid)
                assert "exceptionDetails" not in got, got
                cls.drawn[name] = got["result"]["value"]
            cls.locked = cdp.call("Runtime.evaluate", {"expression": "({ only: T.TC.shownIds('msDash', ['agreed']), off: T.TC.toggled('msDash', T.TC.standardIds('msDash'), 'name'), offState: T.TC.toggled('msDash', T.TC.standardIds('msDash'), 'state') })",
                                                       "returnByValue": True}, cls.sid)["result"]["value"]

    def test_the_milestones_page_draws_no_heading_row_in_view(self):
        self.assertFalse(self.drawn["page-view"]["hd"], "the page's heading row is Edit's alone")
        self.assertTrue(self.drawn["dash-view"]["hd"], "control: the Dashboard section draws its heading row in View")
        self.assertEqual(self.drawn["dash-view"]["cols"], ["name", "state", "agreed", "date", "prog"])

    def test_the_dashboards_name_column_is_locked(self):
        self.assertIn("name", self.locked["only"], "a choice that leaves the name out still shows it")
        self.assertEqual(self.locked["off"], ["name", "state", "agreed", "date", "prog"], "pressing the name changes nothing")
        self.assertEqual(self.locked["offState"], ["name", "state", "agreed", "date", "prog"], "nor the state")

    def test_sized_marks_the_table_custom_when_a_column_is_added_or_removed(self):
        std = self.drawn["dash-std"]
        self.assertTrue(std["hd"] and not std["set"] and not std["vars"], f"the standard columns are not custom: {std}")
        for name in ("dash-added", "dash-removed"):
            got = self.drawn[name]
            self.assertTrue(got["set"], f"{name}: the heading row is marked set")
            self.assertIn("--msl-cols", got["vars"] or "", f"{name}: the column widths are set")
        self.assertEqual(self.drawn["dash-added"]["cols"], ["name", "state", "agreed", "date", "prog", "owner"])
        self.assertEqual(self.drawn["dash-removed"]["cols"], ["name", "state", "agreed", "date"])


CHEAT = "window.__store = new Map(); Object.defineProperty(window, 'localStorage', {configurable: true, value: {getItem: (k) => window.__store.has(k) ? window.__store.get(k) : null, setItem: (k, v) => window.__store.set(k, String(v)), removeItem: (k) => window.__store.delete(k)}}); 0;"
STD_ALL = "['name', 'state', 'agreed', 'date', 'prog']"


class Logic(unittest.TestCase):
    """Sort order, the 'show all' rail, the Expected cell, the kept column choice and the extra cells, one browser, the list's own code."""

    @classmethod
    def setUpClass(cls):
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Runtime.evaluate", {"expression": bundle() + ";" + CHEAT, "returnByValue": True}, sid)
            ev = lambda js: cdp.call("Runtime.evaluate", {"expression": js, "returnByValue": True, "awaitPromise": True}, sid)["result"].get("value")
            cls.order = ev("""(() => { const L = [
                {id: 'z', name: 'late', baseline_date: '2030-03-01'}, {id: 'y', name: 'early', baseline_date: '2030-01-01', sort_order: 2},
                {id: 'x', name: 'early-first', baseline_date: '2030-01-01', sort_order: 1}, {id: 'w', name: 'forecast', forecast_date: '2030-02-01'},
                {id: 'v', name: 'none'}, {id: 'b', name: 'tie-b', baseline_date: '2030-03-01', sort_order: 9}, {id: 'a', name: 'tie-a', baseline_date: '2030-03-01', sort_order: 9},
                {id: 'u', name: 'gone', baseline_date: '2029-01-01', archived: true}];
                return T.M.milestoneRows(L, '2026-10-28', false).map((r) => r.name); })()""")
            cls.rail = ev("(() => { const r = T.M.milestoneRows(Array.from({length: 7}, (_, i) => ({id: i, name: 'n' + i})), '2026-10-28', false); return [T.M.railRows(r, false).length, T.M.railRows(r, true).length, T.M.railRows(r.slice(0, 5), false).length]; })()")
            cls.expected = ev("""(() => { const c = (r) => T.M.expectedCell(T.M.milestoneRows([r], '2026-10-28', false)[0]).date;
                return {early: c({id: 1, name: 'a', baseline_date: '2030-04-01', forecast_date: '2030-03-01'}), fc: c({id: 2, name: 'b', baseline_date: '2030-04-01', forecast_date: '2030-05-01', state_set: true, state: 'Forecast'})}; })()""")
            cls.toggle = ev(f"""(() => {{ const TC = T.TC, std = TC.standardIds('msDash');
                const off = TC.toggled('msDash', std, 'agreed'); return {{off, back: TC.toggled('msDash', off, 'agreed'), added: TC.toggled('msDash', std, 'owner'),
                  same: TC.isStandard('msDash', std), swapped: TC.isStandard('msDash', ['name', 'state', 'agreed', 'date', 'owner'])}}; }})()""")
            cls.kept = ev(f"""(() => {{ const TC = T.TC, std = TC.standardIds('msDash'), pick = ['agreed', 'owner']; window.__store.clear();
                TC.writeChoice('msDash', 'P1', std); const afterStd = window.__store.size;
                TC.writeChoice('msDash', 'P1', pick); const one = TC.readChoice('msDash', 'P1'), other = TC.readChoice('msDash', 'P2'), keys = [...window.__store.keys()];
                TC.writeChoice('msDash', 'P1', std); return {{afterStd, one, other, keys, gone: window.__store.size}}; }})()""")
            cls.five = ev("(() => { document.body.innerHTML = ''; return [T.drawN({place: 'sec-1'}, 5).all, T.drawN({place: 'sec-1'}, 6).all]; })()")
            cls.extra = ev(f"""(() => {{ document.body.innerHTML = ''; const cw = {STAND_IN};
                const g = T.drawN({{place: 'sec-1', CW: () => cw, CM: () => ({{shown: T.TC.shownIds('msDash', ['agreed', 'date', 'prog', 'id', 'order', 'description']), rowProps: {{}}, button: () => null, menu: null}})}}, 2);
                const lean = T.drawN({{place: 'sec-1', CW: () => cw, CM: () => ({{shown: T.TC.shownIds('msDash', ['date', 'prog']), rowProps: {{}}, button: () => null, menu: null}})}}, 2);
                const px = T.drawN({{place: 'sec-1', CW: () => ({{...cw, px: (id) => (id === 'prog' ? 200 : null)}}), CM: () => ({{shown: T.TC.standardIds('msDash'), rowProps: {{}}, button: () => null, menu: null}})}}, 2);
                return {{cells: g.cells, lean: lean.cls, px: {{set: px.set, vars: px.vars}}}}; }})()""")
            cls.file = ev("""(async () => { const out = {}; const go = async (ff) => { document.body.innerHTML = ''; window.__store.clear(); T.fromFile.value = ff;
                const g = T.drawN({place: 'sec-1'}, 6); g.box.querySelector('.msl-all').click(); await new Promise((r) => setTimeout(r, 80));
                return [g.box.querySelectorAll('.msl-row').length, [...window.__store.keys()]]; };
                out.file = await go(true); out.live = await go(false); T.fromFile.value = false; return out; })()""")
            cls.more = ev(f"""(() => {{ const TC = T.TC, M = T.M, names = (l, client) => M.milestoneRows(l, '2026-10-28', client).map((r) => r.name);
                const mix = [{{id: 1, name: 'cancelled', baseline_date: '2030-01-01', status: 'Cancelled'}}, {{id: 2, name: 'kept', baseline_date: '2030-02-01'}}];
                const cell = (r) => M.expectedCell(M.milestoneRows([r], '2026-10-28', false)[0]);
                window.__store.clear(); TC.writeChoice('msDash', 'P1', ['owner']); const k = [...window.__store.keys()][0];
                return {{editor: names(mix, false), client: names(mix, true),
                  cancelled: cell({{id: 3, name: 'c', baseline_date: '2030-04-01', forecast_date: '2030-03-01', status: 'Cancelled'}}),
                  oneDay: cell({{id: 5, name: 'o', baseline_date: '2026-10-27', forecast_date: '2026-10-28'}}), forecastRow: cell({{id: 6, name: 'f', forecast_date: '2030-08-08', state_set: 1, state: 'Forecast'}}),
                  doneNoDate: cell({{id: 4, name: 'd', baseline_date: '2030-04-01', status: 'Done'}}),
                  unknownPress: TC.toggled('msDash', ['date', 'agreed'], 'nope'),
                  stored: JSON.parse(window.__store.get(k)),
                  lockedLeftOut: TC.isStandard('msDash', ['agreed', 'date', 'prog'])}}; }})()""")
            cls.cols = ev(f"""(() => {{ document.body.innerHTML = ''; const cw = {STAND_IN}, CM = (ids) => () => ({{shown: T.TC.shownIds('msDash', ids), rowProps: {{}}, button: () => null, menu: null}});
                const d = (ids, extra, n = 2) => T.drawN({{place: 'sec-1', CW: () => cw, CM: CM(ids), open: () => {{}}}}, n, extra);
                const nod = (ids) => d(ids, {{}}).box.querySelector('.msl-box').getAttribute('data-nodate');
                const swap = d(['agreed', 'date', 'owner'], {{}});
                const prog = (v) => d(['prog'], {{percent_complete: v}}).cells.prog;
                const lab = d(['agreed', 'date', 'prog', 'owner'], {{owner: 'Sam'}}).box.querySelector('.msl-cells').getAttribute('aria-label');
                return {{noDateWithoutDate: nod(['agreed', 'prog']), noDateWithDate: nod(['date', 'prog']),
                  swapSet: swap.set, swapVars: swap.vars,
                  forecast: d(['forecast'], {{forecast_date: '2030-09-09'}}).cells.forecast, noForecast: d(['forecast'], {{}}).cells.forecast,
                  prog: [prog(100), prog(150), prog(-5), prog('x')], label: lab}}; }})()""")
            cls.fold = ev("""(() => { document.body.innerHTML = ''; window.__store.clear(); T.fromFile.value = true;
                const g = T.drawN({place: 'sec-1'}, 2); g.box.querySelector('.msl-det').click(); const keys = [...window.__store.keys()]; T.fromFile.value = false; return keys; })()""")

    def test_a_published_file_leaves_out_cancelled_rows_and_the_editor_keeps_them(self):
        self.assertEqual(self.more["editor"], ["cancelled", "kept"])
        self.assertEqual(self.more["client"], ["kept"])

    def test_the_expected_cell_of_a_cancelled_row_is_its_agreed_date_and_an_achieved_row_without_a_date_says_so(self):
        self.assertEqual(self.more["cancelled"]["date"], "01-04-2030", "the agreed date, not the forecast")
        self.assertEqual(self.more["doneNoDate"], {"date": "\u2014", "text": "Achieved, date not recorded", "late": False})

    def test_a_forecast_date_has_the_small_line_forecast_and_a_slipped_one_has_plus_n_days_as_in_the_mock_up(self):
        self.assertEqual(self.more["forecastRow"], {"date": "08-08-2030", "text": "Forecast", "late": False})
        self.assertEqual(self.more["oneDay"], {"date": "28-10-2026", "text": "+1 day", "late": True}, "singular for one day")

    def test_pressing_a_column_the_table_does_not_have_changes_nothing_and_a_stored_choice_holds_the_locked_columns(self):
        self.assertEqual(self.more["unknownPress"], ["name", "state", "agreed", "date"], "the choice as it is drawn, not as it was handed in")
        self.assertEqual(self.more["stored"], ["name", "state", "owner"], "what is kept names the locked columns too")
        self.assertTrue(self.more["lockedLeftOut"], "the locked columns are always shown, so a choice of the other three is the standard set")

    def test_the_date_column_alone_decides_whether_the_box_is_marked_without_dates_and_five_other_columns_are_custom(self):
        c = self.cols
        self.assertEqual((c["noDateWithoutDate"], c["noDateWithDate"]), ("1", None))
        self.assertTrue(c["swapSet"] and "--msl-cols" in (c["swapVars"] or ""), f"five columns that are not the standard five are custom: {c['swapVars']}")

    def test_the_forecast_progress_and_extra_cells_read_the_row_and_the_row_label_names_the_extra_columns_only(self):
        c = self.cols
        self.assertEqual((c["forecast"], c["noForecast"]), ("09-09-2030", "\u2014"))
        self.assertEqual([p.replace("Progress ", "", 1) for p in c["prog"]], ["100%", "100%", "0%", "\u2014"], "from 0 to 100, anything else is not set (a dash, spoken as Progress not set)")
        self.assertTrue(c["label"].endswith(", Owner Sam"), c["label"])
        self.assertNotIn("Milestone M1", c["label"], "the standard columns are the row's own words, not repeated")

    def test_a_published_file_does_not_remember_the_fold_either(self):
        self.assertEqual(self.fold, [])

    def test_rows_run_by_agreed_date_then_forecast_then_undated_then_sort_order_then_id_and_archived_ones_are_left_out(self):
        self.assertEqual(self.order, ["early-first", "early", "forecast", "late", "tie-a", "tie-b", "none"], "a date, the forecast when there is none, then no date at all; ties by sort order then id; the archived row is not drawn")

    def test_the_rail_shows_five_rows_until_all_are_asked_for(self):
        self.assertEqual(self.rail, [5, 7, 5])
        self.assertEqual(self.five, [False, True], "Show all appears only above five rows")

    def test_the_expected_cell_is_the_agreed_date_unless_the_row_slipped_or_is_only_a_forecast(self):
        self.assertEqual(self.expected, {"early": "01-04-2030", "fc": "01-05-2030"})

    def test_pressing_a_column_turns_it_off_and_on_and_only_the_exact_standard_set_counts_as_standard(self):
        self.assertEqual(self.toggle["off"], ["name", "state", "date", "prog"])
        self.assertEqual(self.toggle["back"], ["name", "state", "agreed", "date", "prog"])
        self.assertEqual(self.toggle["added"], ["name", "state", "agreed", "date", "prog", "owner"])
        self.assertTrue(self.toggle["same"])
        self.assertFalse(self.toggle["swapped"], "five columns that are not the standard five")

    def test_the_chosen_columns_are_kept_for_each_project_and_the_standard_set_keeps_nothing(self):
        k = self.kept
        self.assertEqual(k["afterStd"], 0, "the standard set is kept as nothing")
        self.assertEqual(k["one"], ["name", "state", "agreed", "owner"], "what was picked, with the locked columns")
        self.assertEqual(k["other"], ["name", "state", "agreed", "date", "prog"], "another project still has the standard set")
        self.assertEqual(len(k["keys"]), 1)
        self.assertEqual(k["gone"], 0, "choosing the standard set again takes the kept choice away")

    def test_the_extra_columns_say_what_the_row_holds_and_a_dash_when_it_holds_nothing(self):
        c = self.extra["cells"]
        self.assertEqual((c["id"], c["order"], c["description"]), ("1", "3", "\u2014"))
        self.assertIn("cols-off", self.extra["lean"]["agreed"], "a column that is off keeps its cell, marked off")
        self.assertNotIn("cols-off", self.extra["lean"]["prog"])
        self.assertTrue(self.extra["px"]["set"] and "200px" in self.extra["px"]["vars"], f"one dragged width sets the widths: {self.extra['px']}")

    def test_a_published_file_does_not_remember_show_all_and_the_editor_does(self):
        self.assertEqual(self.file, {"file": [6, []], "live": [6, ["clark.msAll.sec-1"]]})


if __name__ == "__main__":
    unittest.main()

"""Row 1230, part 3: the Dashboard Milestones section's list is a table of five columns, Milestone, State, Agreed, Expected or achieved
and Progress, under a heading row that is drawn in View and in Edit alike. A row still opens the peek; the Hide / Show milestone details toggle stays.

Run: python3 dev/run_tests.py -j 1 test_ms_table_1230   (headless Chrome; fails, never skips, without it)
Fictional data over a real store; "today" is 2026-10-28. Widths 1400 and 900 only; no keyboard walk-through.
"""
import json
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
    ("T maybe", {"forecast_date": "2030-07-01"}, "No agreed date", "01-07-2030", None),
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
      prog: c('prog')};
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
                    late = got["rows"]["T late"]
                    self.assertTrue(late["late"] and late["sub"].endswith("days later") and late["date"] == "01-05-2030", f"a slipped row: {late}")
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
window.T = { TC, draw(props) {
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


if __name__ == "__main__":
    unittest.main()

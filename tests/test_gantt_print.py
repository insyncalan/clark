"""#990: the Gantt on paper (shell.css, under html.print-all, which stores/print.js sets while the browser prints).
The printed chart and table have no toolbar or menu, are drawn whole inside the page (no box that scrolls, nothing sticky or fixed), keep
the colour of the bars, and the screen is unchanged. Drawn on the bare Gantt page of tests/fixtures/gantt_page_demo.jsx with print media
emulated (never a print box), at A4 portrait and landscape, light and dark, and at the 1400 and 900 px windows.

Run: python3 dev/run_tests.py test_gantt_print
The Static test needs no browser; the rest need Chrome and fail, never skip, without it.
"""
import json
import re
import unittest

from _paths import SRC
import test_gantt_page as rig
from test_gantt_page import Page as _PageRig, lit
from test_server import chrome  # noqa: F401  # this file drives Chrome through test_gantt_page's rig; the runner's text check looks for this import

A4 = {"portrait": 794, "landscape": 1123}      # A4's width in CSS pixels
TAIL = 41      # the canvas ends 40 px after the last day: empty space the clip may take
KEEP = "display position overflowX overflowY maxHeight height backgroundColor borderTopColor color zIndex".split()


def print_block():
    css = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
    start = css.index("html.print-all, html.print-all body")
    return css[start:css.index("\n}\n", start)]


class Static(unittest.TestCase):
    def test_every_gantt_print_rule_is_under_print_all_inside_the_print_block(self):
        block = print_block()
        lines = [ln for ln in block.splitlines() if re.search(r"\.gt-|\.gp-", ln) and not ln.lstrip().startswith("/*")]
        self.assertTrue(lines, "the Gantt has print rules")
        for ln in lines:
            for sel in ln.split("{")[0].split(","):
                self.assertTrue(sel.strip().startswith("html.print-all "), f"only under html.print-all: {sel.strip()}")
        for need in (".gt-bar", ".gp-tools", ".gt-pop", ".gt-gx", ".gt-full", ".gt-lhead", ".gt-b", "break-inside: avoid"):
            self.assertIn(need, block)


class Print(_PageRig):
    def probe(self):
        return json.loads(self.js("""(function () {
          var q = function (s) { return document.querySelector(s); };
          var cs = function (el) { return el ? getComputedStyle(el) : null; };
          var all = Array.prototype.slice.call(document.querySelectorAll('#gantt-page *'));
          var moving = all.filter(function (e) { var p = getComputedStyle(e).position; return (p === 'sticky' || p === 'fixed') && e.getClientRects().length; });
          var gx = q('.gt-gx') || q('.gt-scroll'), inner = q('.gt-in') || q('.gt-scroll table');
          var bar = q('.gt-b:not(.gt-b-phase)');
          var rows = Array.prototype.slice.call(document.querySelectorAll('.gt-ln'));
          return JSON.stringify({
            bar: !!q('.gt-bar') && cs(q('.gt-bar')).display, tools: !!q('.gp-tools') && cs(q('.gp-tools')).display,
            moving: moving.map(function (e) { return e.className + ':' + getComputedStyle(e).position; }),
            overflow: cs(gx).overflowX, scrollW: gx.scrollWidth, clientW: gx.clientWidth,
            right: Math.round(inner.getBoundingClientRect().right),
            canvasRight: q('.gt-canvas') ? Math.round(q('.gt-canvas').getBoundingClientRect().right) : 0, gxRight: Math.round(gx.getBoundingClientRect().right), doc: document.documentElement.clientWidth, docScroll: document.documentElement.scrollWidth,
            barAdjust: bar ? cs(bar).printColorAdjust : 'exact', barBg: bar ? cs(bar).backgroundColor : 'x',
            rowBreak: rows.length ? cs(rows[0]).breakInside : 'avoid', rows: rows.length,
          });
        })()"""))

    def printing(self, width, scheme, on=True):
        self.cdp.call("Emulation.setEmulatedMedia", {"media": "print" if on else "", "features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
        self.js(f"document.documentElement.classList.toggle('print-all', {lit(on)})")
        self.settle()

    def done(self):
        self.printing(0, "light", False)
        self.cdp.call("Emulation.setEmulatedMedia", {"media": "", "features": []}, self.sid)

    def check(self, got, what):
        self.assertEqual(got["bar"], "none", f"{what}: no toolbar")
        self.assertEqual(got["tools"], "none", f"{what}: no page toolbar row")
        self.assertEqual(got["moving"], [], f"{what}: nothing sticky or fixed")
        self.assertIn(got["overflow"], ("visible", "clip"), f"{what}: no scrolling box")
        if got["overflow"] == "visible":
            self.assertLessEqual(got["scrollW"], got["clientW"] + 1, f"{what}: nothing cut at the box edge {got}")
        if got["canvasRight"]:      # a clipping box hides what is drawn past its edge, so the canvas may overhang by no more than its empty tail (GanttChart.jsx: 40 px past the last day)
            self.assertLessEqual(got["canvasRight"], got["gxRight"] + TAIL, f"{what}: the canvas is not cut at the box edge {got}")
        self.assertLessEqual(got["right"], got["doc"] + 1, f"{what}: the chart ends inside the page {got}")
        self.assertLessEqual(got["docScroll"], got["doc"] + 1, f"{what}: no sideways scroll on the page {got}")
        self.assertEqual(got["barAdjust"], "exact", f"{what}: bars keep their colour")
        self.assertNotIn(got["barBg"], ("rgba(0, 0, 0, 0)", "transparent"), f"{what}: the bar has a fill")

    def test_the_printed_chart_and_table_have_no_controls_and_fit_the_page_at_a4_both_ways(self):
        for orient, w in A4.items():
            for scheme in ("light", "dark"):
                for layout in ("chart", "table"):
                    with self.subTest(orient=orient, scheme=scheme, layout=layout):
                        self.look(w, scheme)
                        self.mount(width=w - 60)
                        if layout == "table":
                            self.click("[data-gp-layout]")
                            self.until("document.querySelector('[data-gp-shown=table]')", "table")
                        self.printing(w, scheme)
                        try:
                            got = self.probe()
                            if layout == "table":
                                got["barAdjust"], got["barBg"] = "exact", "x"
                            self.check(got, f"{layout} {orient} {scheme}")
                            if layout == "chart":
                                self.assertEqual(got["rowBreak"], "avoid", "a row is not split across pages")
                        finally:
                            self.done()

    def test_the_full_screen_chart_prints_in_the_flow(self):
        self.look(794, "light")
        self.mount(width=734)
        self.click("[data-g-expand]")
        self.until("document.querySelector('.gt-full')", "full screen")
        self.printing(794, "light")
        try:
            self.assertEqual(self.js("getComputedStyle(document.querySelector('.gt-full')).position"), "static")
            self.check(self.probe(), "full screen")
        finally:
            self.done()
            self.click("[data-g-expand]")

    def test_every_printed_bar_and_milestone_is_drawn_with_a_fill(self):
        # #990 read by eye: the paper had no bars. "html.print-all button { background: none }" outranked the bars (they are buttons).
        for scheme in ("light", "dark"):
            for w in A4.values():
                with self.subTest(scheme=scheme, width=w):
                    self.look(w, scheme)
                    self.mount(width=w - 60)
                    self.printing(w, scheme)
                    try:
                        got = json.loads(self.js("""JSON.stringify([].slice.call(document.querySelectorAll('.gt-b, .gt-ms')).map(function (e) {
                          var b = e.getBoundingClientRect(), c = getComputedStyle(e);
                          return [e.className, Math.round(b.width), Math.round(b.height), c.backgroundColor, c.visibility, c.display]; }))"""))
                        self.assertGreaterEqual(len(got), 3, "the demo draws bars and a milestone")
                        for cls, bw, bh, bg, vis, disp in got:
                            self.assertGreater(bw, 4, f"{cls}: has width")
                            self.assertGreater(bh, 4, f"{cls}: has height")
                            self.assertNotIn(bg, ("rgba(0, 0, 0, 0)", "transparent"), f"{cls}: filled")
                            self.assertEqual((vis, disp), ("visible", "block"), cls)
                    finally:
                        self.done()

    def test_no_printed_label_or_bar_is_cut_at_the_edge_or_runs_into_the_left_columns(self):
        # #990 read by eye: "Migration" lost its first letters in portrait. Every drawn word, bar, milestone and flag lies inside the chart's own area.
        for scheme in ("light", "dark"):
            for orient, w in A4.items():
                with self.subTest(scheme=scheme, orient=orient):
                    self.look(w, scheme)
                    self.mount(width=w - 60)
                    self.printing(w, scheme)
                    try:
                        bad = json.loads(self.js("""(function () {
                          var gx = document.querySelector('.gt-gx').getBoundingClientRect(), cv = document.querySelector('.gt-canvas').getBoundingClientRect(), out = [];
                          document.querySelectorAll('.gt-mslab, .gt-b, .gt-ms, .gt-tflag').forEach(function (e) {
                            var r = e.getBoundingClientRect();
                            if (r.left < cv.left - 1 || r.right > gx.right + 1) out.push([e.className, e.textContent, Math.round(r.left), Math.round(r.right), Math.round(cv.left), Math.round(gx.right)]);
                          });
                          return JSON.stringify(out); })()"""))
                        self.assertEqual(bad, [], "labels and bars sit inside the chart area")
                        self.assertGreaterEqual(self.count(".gt-mslab"), 1, "the demo has labels beside bars")
                    finally:
                        self.done()

    def test_a_chart_measured_on_the_screen_is_fitted_to_the_paper_when_the_print_starts(self):
        # The page is measured at the screen width (1400 or 900) and the browser then lays it out at the paper width without a ResizeObserver
        # callback (stubbed to nothing here): beforeprint must refit the chart, so the scale, the Migration bar end and the labels are on the paper.
        paper = 703      # A4 width 794 less 12 mm margins
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.js("window.__RO = window.__RO || window.ResizeObserver; window.ResizeObserver = function () { this.observe = function () {}; this.disconnect = function () {}; };")
                    lines = ("P.LINES.map(function (l) { return Object.assign({}, l, { show: 1 }); }).concat([{ id: 'GNT-007', name: 'A very long milestone name that cannot fit beside its diamond', type: 'milestone', parent: '', start: '2026-11-10', end: '2026-11-10', pct: 0, "
                             "health: '', depends: [], owner: '', workstream: '', priority: '', baseline_start: '', baseline_end: '', effort: '', budget: '', deliverable: '', show: 1, note: '', sort_order: 7 }])")
                    self.js(f"P.mount({{ lines: {lines}, width: {width - 40} }})")
                    self.until("document.querySelector('#gantt-page .gt-canvas')", "the chart is drawn")
                    self.assertEqual(self.count(".gt-ln"), 7, "seven lines are drawn")
                    self.printing(paper, scheme)
                    self.js(f"document.getElementById('host').style.width = '{paper}px'; window.dispatchEvent(new Event('beforeprint'))")
                    self.settle()
                    try:
                        got = json.loads(self.js("""(function () {
                          var gx = document.querySelector('.gt-gx').getBoundingClientRect(), cv = document.querySelector('.gt-canvas').getBoundingClientRect(), out = { canvas: [Math.round(cv.right), Math.round(gx.right)], cut: [] };
                          var cells = document.querySelectorAll('.gt-rhead .gt-hc'), last = cells[cells.length - 1];
                          out.lastCell = last ? Math.round(last.getBoundingClientRect().left) : null;
                          document.querySelectorAll('.gt-mslab, .gt-b, .gt-ms, .gt-tflag').forEach(function (e) {
                            var r = e.getBoundingClientRect();
                            if (r.right > gx.right + 1 || r.left < cv.left - 1) out.cut.push([e.className, e.textContent, Math.round(r.right)]);
                          });
                          var mig = document.querySelector('[data-g-bar="GNT-004"]'), mv = document.querySelector('[data-g-bar="GNT-006"]');
                          out.mig = mig ? Math.round(mig.getBoundingClientRect().right) : null;
                          var lab = [].slice.call(document.querySelectorAll('.gt-mslab')).filter(function (e) { return /Move applications/.test(e.textContent); })[0];
                          out.move = lab ? [lab.scrollWidth, lab.clientWidth, lab.classList.contains('gt-flip')] : null;
                          var long = [].slice.call(document.querySelectorAll('.gt-mslab')).filter(function (e) { return /very long/.test(e.textContent); })[0];
                          out.long = long ? [long.classList.contains('gt-flip'), long.scrollWidth > long.clientWidth] : null;
                          out.gxRight = Math.round(gx.right);
                          return JSON.stringify(out); })()"""))
                        self.assertLessEqual(got["canvas"][0], got["canvas"][1] + TAIL, f"only the empty tail of the canvas is past the page {got}")
                        self.assertLessEqual(got["lastCell"], got["gxRight"], f"the last month is on the page {got}")
                        self.assertIsNotNone(got["mig"])
                        self.assertLessEqual(got["mig"], got["gxRight"] + 1, f"the Migration bar end is on the page {got}")
                        self.assertEqual(got["cut"], [], "no label, bar or milestone is cut at the page edge")
                        self.assertIsNotNone(got["move"], "Move applications has its word")
                        if not got["move"][2]:      # a word placed left of its bar ends in an ellipsis by design (row 1037); beside its bar it is whole
                            self.assertLessEqual(got["move"][0], got["move"][1] + 1, f"Move applications is whole {got}")
                        self.assertTrue(got["long"] and got["long"][0], f"the long milestone word flips to the left {got}")
                    finally:
                        self.js("window.dispatchEvent(new Event('afterprint')); document.getElementById('host').style.width = ''; window.ResizeObserver = window.__RO")
                        self.done()

    def test_the_screen_is_the_same_with_the_class_on(self):
        # Screen media with html.print-all on: the print rules sit in @media print, so nothing about the screen moves.
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for layout in ("chart", "table"):
                    with self.subTest(width=width, scheme=scheme, layout=layout):
                        self.look(width, scheme)
                        self.mount()
                        if layout == "table":
                            self.click("[data-gp-layout]")
                            self.until("document.querySelector('[data-gp-shown=table]')", "table")
                        snap = ("JSON.stringify([].slice.call(document.querySelectorAll('#gantt-page *')).map(function (e) { var c = getComputedStyle(e); return "
                                + "[" + ",".join(f"c.{k}" for k in KEEP) + ", e.getBoundingClientRect().width, e.getBoundingClientRect().height]; }))")
                        before = self.js(snap)
                        self.js("document.documentElement.classList.add('print-all')")
                        self.settle()
                        after = self.js(snap)
                        self.js("document.documentElement.classList.remove('print-all')")
                        self.assertEqual(before, after, "screen styles and sizes are identical")
                        self.assertGreater(len(json.loads(before)), 50)

    def test_the_printed_left_list_shows_its_values_when_printed_from_edit(self):
        # Edit draws the left list (name, Start, End, Done) as input elements; html.print-all hid every input, so the paper had an empty list.
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(mode="edit")
                    self.printing(width, scheme)
                    try:
                        got = json.loads(self.js("""JSON.stringify([].slice.call(document.querySelectorAll('.gt-ln input.gt-li')).map(function (e) {
                          var r = e.getBoundingClientRect(), c = getComputedStyle(e);
                          return [e.dataset.gEdit, e.value, c.display, Math.round(r.width), Math.round(r.height), c.visibility, parseFloat(e.style.width)]; }))"""))
                        self.assertGreaterEqual(len(got), 8, "Edit draws the list as inputs")
                        for key, val, disp, w, h, vis, drawn in got:
                            self.assertNotEqual(disp, "none", f"{key}: drawn on paper")
                            self.assertGreater(w, 4, f"{key}: has width")
                            self.assertGreater(h, 4, f"{key}: has height")
                            self.assertAlmostEqual(w, drawn, delta=1, msg=f"{key}: keeps the column width it is drawn with, so the value is not squeezed out")
                            self.assertEqual(vis, "visible", key)
                        self.assertTrue(all(v for k, v, *_ in got if k.endswith(":name")), "names have values")
                        self.assertEqual(self.count(".gt-ln input.gt-li:not([data-g-edit])"), 0)
                    finally:
                        self.done()

    def test_the_printed_table_from_edit_leaves_out_the_hidden_columns_and_breaks_no_word(self):
        # Edit draws every column; the hidden ones' header carried gt-hid but their cells carried nothing, so paper printed them all, and the
        # rule that lets cells wrap broke words letter by letter.
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(mode="edit")
                    self.click("[data-gp-layout=table]")
                    self.until("document.querySelector('.gt table td')", "the table is drawn")
                    self.printing(width, scheme)
                    try:
                        got = json.loads(self.js("""(function () {
                          var hid = [].slice.call(document.querySelectorAll('.gt th.gt-hid')).map(function (t) { return t.dataset.k; });
                          var shown = function (e) { return e.getClientRects().length > 0 && getComputedStyle(e).display !== 'none'; };
                          var cells = [].slice.call(document.querySelectorAll('.gt td, .gt th'));
                          var leaked = cells.filter(function (c) { return hid.indexOf(c.dataset.k) >= 0 && shown(c); }).length;
                          var tagged = [].slice.call(document.querySelectorAll('.gt td')).filter(function (c) { return hid.indexOf(c.dataset.k) >= 0 && !c.classList.contains('gt-hid'); }).length;
                          var broken = [], words = 0;
                          cells.filter(shown).forEach(function (c) {
                            var w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT), n;
                            while ((n = w.nextNode())) {
                              if (!n.parentElement.getClientRects().length) continue;
                              var re = /\\S+/g, m;
                              while ((m = re.exec(n.data))) {
                                var r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
                                var tops = {}; [].forEach.call(r.getClientRects(), function (q) { tops[Math.round(q.top)] = 1; });
                                words++; if (Object.keys(tops).length > 1) broken.push(m[0]);
                              }
                            }
                          });
                          return JSON.stringify({hid: hid, leaked: leaked, tagged: tagged, broken: broken, words: words, doc: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth});
                        })()"""))
                        self.assertGreaterEqual(len(got["hid"]), 3, f"Edit marks the hidden columns {got}")
                        self.assertEqual(got["tagged"], 0, f"every hidden column's cells carry gt-hid {got}")
                        self.assertEqual(got["leaked"], 0, f"no hidden column cell prints {got}")
                        self.assertGreater(got["words"], 20)
                        self.assertEqual(got["broken"], [], f"no word breaks mid-word {got}")
                        self.assertLessEqual(got["doc"], got["cw"] + 1, f"no sideways scroll {got}")
                    finally:
                        self.done()

    def test_the_printed_table_keeps_an_id_and_a_date_whole_and_lets_only_the_free_text_cells_break_anywhere(self):
        # The one-token cells are nowrap; only the free-text cells may break inside a word when a narrow page is full; the rest wrap by word.
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(mode="edit")
                    self.click("[data-gp-layout=table]")
                    self.until("document.querySelector('.gt table td')", "the table is drawn")
                    self.printing(width, scheme)
                    try:
                        got = json.loads(self.js("""(function () {
                          var out = {};
                          [].slice.call(document.querySelectorAll('.gt td[data-k]')).forEach(function (c) {
                            if (c.classList.contains('gt-hid')) return;
                            var cs = getComputedStyle(c), k = c.dataset.k;
                            (out[k] = out[k] || {})[cs.whiteSpace + '|' + cs.overflowWrap] = 1;
                          });
                          return JSON.stringify(out);
                        })()"""))
                        for k in ("id", "par", "s", "e"):
                            for combo in got.get(k, {}):
                                self.assertTrue(combo.startswith("nowrap"), f"{k} stays on one line {got}")
                        for k, combos in got.items():
                            if k in ("n", "dep", "o", "ws", "del"):
                                continue
                            for combo in combos:
                                self.assertTrue(combo.endswith("|break-word"), f"{k} breaks only at an overflow, never anywhere {got}")
                        self.assertTrue(any(k in got for k in ("id", "s", "e")), f"id or date cells are drawn {got}")
                    finally:
                        self.done()

    def test_a_pdf_of_the_chart_page_is_made_at_a4_without_a_print_box(self):
        self.look(794, "light")
        self.mount(width=734)
        self.printing(794, "light")
        try:
            got = self.cdp.call("Page.printToPDF", {"paperWidth": 8.27, "paperHeight": 11.69, "printBackground": True, "preferCSSPageSize": False}, self.sid)
            self.assertGreater(len(got["data"]), 1000)
        finally:
            self.done()


for _n in dir(rig.Page):
    if _n.startswith("test_") and _n not in Print.__dict__:
        setattr(Print, _n, None)      # the rig's own tests are not run again here
del _PageRig, rig

if __name__ == "__main__":
    unittest.main()

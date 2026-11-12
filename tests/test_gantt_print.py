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
            right: Math.round(inner.getBoundingClientRect().right), doc: document.documentElement.clientWidth, docScroll: document.documentElement.scrollWidth,
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
                          return [e.dataset.gEdit, e.value, c.display, Math.round(r.width), Math.round(r.height), c.visibility]; }))"""))
                        self.assertGreaterEqual(len(got), 8, "Edit draws the list as inputs")
                        for key, val, disp, w, h, vis in got:
                            self.assertNotEqual(disp, "none", f"{key}: drawn on paper")
                            self.assertGreater(w, 4, f"{key}: has width")
                            self.assertGreater(h, 4, f"{key}: has height")
                            self.assertEqual(vis, "visible", key)
                        self.assertTrue(all(v for k, v, *_ in got if k.endswith(":name")), "names have values")
                        self.assertEqual(self.count(".gt-ln input.gt-li:not([data-g-edit])"), 0)
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

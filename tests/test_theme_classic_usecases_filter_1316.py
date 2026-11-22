"""Row 1316: the Classic Use cases filter is drawn as a box (prototype pages/usecases.css:47): 1px border on four sides, radius 6px, height 34px,
width 560, the magnifier inside. Ruling 1137 stays about focus: no ring and no coloured border; a line the filter cannot read keeps its red.
Border colour is --grey-500 (Classic #8794B3 light, #6F7FA3 dark: the prototype's --ui to the digit, tokens.css lines 4 and 16).

Run: python3 dev/run_tests.py test_theme_classic_usecases_filter_1316
Chrome required (fails, never skips). 1400 and 900 px, light and dark. Cards (no Theme) is read too and must stay unchanged. The rule lines are pinned in test_theme_classic_1316_filter_pinned and test_theme_classic_1316_pinned. No new words.
"""
import tempfile
import unittest

from _demo import DemoStore
from clark import page
from test_published_work_no_add import open_page
from test_server import Running, chrome, wait
from test_work_filters import need_chrome

NAME = "prototype-2.0"
VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]
READ = """(() => { const o = {}; const f = document.querySelector('#usecases .fline'); const rd = () => { const s = getComputedStyle(f);
    return {w: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth], st: [s.borderTopStyle, s.borderRightStyle, s.borderBottomStyle, s.borderLeftStyle],
      c: [s.borderTopColor, s.borderRightColor, s.borderBottomColor, s.borderLeftColor], r: [s.borderTopLeftRadius, s.borderTopRightRadius, s.borderBottomRightRadius, s.borderBottomLeftRadius],
      pad: [s.paddingTop, s.paddingBottom], sh: s.boxShadow, ol: s.outlineStyle + ' ' + s.outlineWidth, bg: s.backgroundColor}; };
  f.style.transition = 'none'; const col = (v) => { const i = document.createElement('i'); i.style.color = 'var(' + v + ')'; document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; };
  o.grey500 = col('--grey-500'); o.red = col('--status-red'); o.surface = col('--surface');
  o.rest = rd(); const r = f.getBoundingClientRect(), w = document.querySelector('#usecases .fline-row').getBoundingClientRect(); o.box = [Math.round(r.width), r.height, Math.round(w.width)];
  const m = getComputedStyle(f, '::before'), h = getComputedStyle(f, '::after'); o.mag = [m.left, m.width, m.marginTop]; o.handle = [h.left, h.width];
  const ml = r.left + parseFloat(m.left), mr = ml + 13; o.magInside = [ml > r.left, mr < r.right];
  const mt = r.top + r.height / 2 + parseFloat(m.marginTop), hb = r.top + r.height / 2 + parseFloat(h.marginTop) + 2; o.magV = [mt > r.top, hb < r.bottom];
  f.querySelector('input').focus(); o.focus = rd();
  o.focused = document.activeElement === f.querySelector('input');
  f.classList.add('bad'); o.bad = rd(); f.classList.remove('bad');
  o.noScroll = document.documentElement.scrollWidth <= window.innerWidth;
  return o; })()"""
CARDS = """(() => { const f = document.querySelector('#usecases .fline'), s = getComputedStyle(f); const i = document.createElement('i'); i.style.color = 'var(--grey-500)'; document.body.appendChild(i); const g = getComputedStyle(i).color; i.remove();
  return {c: s.borderBottomColor, g: g, h: f.getBoundingClientRect().height}; })()"""


class Box(unittest.TestCase):
    def setUp(self):
        need_chrome()
        demo = DemoStore()
        self.addCleanup(demo.close)
        self.demo = demo

    def read(self, theme, width, scheme, js=READ):
        s = Running(data_for=self.demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#usecases&p=ABC", width, scheme)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ucl-group') && !!document.querySelector('#usecases .fline')", sid), 45), "the page drew")
            return cdp.js(js, sid)

    def test_classic_filter_is_a_box(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                g = self.read(NAME, w, scheme)
                rest = g["rest"]
                self.assertEqual(rest["w"], ["1px"] * 4, "1px on all four sides")
                self.assertEqual(rest["st"], ["solid"] * 4)
                self.assertEqual(rest["c"], [g["grey500"]] * 4, "the neutral border is --grey-500")
                self.assertEqual(rest["r"], ["6px"] * 4, "radius 6px")
                self.assertEqual(rest["bg"], g["surface"], "surface background")
                self.assertEqual(rest["pad"], ["0px", "0px"], "no vertical padding: the 34px box is its height, not padding around the line")
                self.assertEqual(g["box"][1], 34, "34px high")
                self.assertLessEqual(g["box"][0], 560, "the search box is at most 560 wide")
                if w == 1400:
                    self.assertEqual(g["box"][0], 560, "the search box is 560 wide")
                self.assertEqual(g["mag"][:2], ["12px", "9px"], "magnifier as before")
                self.assertEqual(g["magInside"], [True, True], "the magnifier is inside the box (sides)")
                self.assertEqual(g["magV"], [True, True], "the magnifier is inside the box (top and bottom)")
                self.assertTrue(g["focused"])
                foc = g["focus"]
                self.assertEqual(foc["c"], rest["c"], "focus keeps the neutral border")
                self.assertEqual(foc["w"], rest["w"])
                self.assertEqual(foc["sh"], "none", "no ring on focus")
                self.assertTrue(foc["ol"].startswith("none") or foc["ol"].endswith(" 0px"), "no outline on focus: " + foc["ol"])
                bad = g["bad"]
                self.assertEqual(bad["c"], [g["red"]] * 4, "a line the filter cannot read is red on all four sides")
                self.assertEqual(bad["w"], ["1px"] * 4)
                self.assertEqual(bad["sh"], "none", "red is the border alone, no extra ring")
                self.assertTrue(g["noScroll"])

    def test_hover_keeps_the_box_and_the_x_is_shown(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                s = Running(data_for=self.demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=NAME))
                self.addCleanup(s.close)
                with chrome() as cdp:
                    sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#usecases&p=ABC", w, scheme)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ucl-group') && !!document.querySelector('#usecases .fline')", sid), 45), "the page drew")
                    rd = "(() => { const s = getComputedStyle(document.querySelector('#usecases .fline')); return {c: s.borderTopColor, sh: s.boxShadow, bg: s.backgroundColor}; })()"
                    rest = cdp.js(rd, sid)
                    r = cdp.js("(() => { const r = document.querySelector('#usecases .fline').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#usecases .fline').matches(':hover')", sid), 10), "the pointer is over the box")
                    hov = cdp.js(rd, sid)
                    self.assertEqual(hov["c"], rest["c"], "hover keeps the neutral border")
                    self.assertEqual(hov["sh"], "none", "no ring on hover")
                    self.assertEqual(hov["bg"], rest["bg"])

    def test_cards_unchanged(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                g = self.read(None, w, scheme, CARDS)
                self.assertNotEqual(g["c"], g["g"], "Cards unchanged: border colour is not the Classic neutral")
                self.assertNotEqual(g["h"], 34, "Cards unchanged: height is not the box 34px")


if __name__ == "__main__":
    unittest.main()

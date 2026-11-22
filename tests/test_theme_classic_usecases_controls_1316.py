"""Row 1316 controls (ruling 19-11): in Classic the Use cases Group by and Sort by buttons are 1px --grey-500 boxes, radius 6, min-height 28,
padding 0 10, no fill; the + (Add use case) is brand-coloured, weight 600. Cards (no Theme) keeps its own look.

Run: python3 dev/run_tests.py test_theme_classic_usecases_controls_1316   Chrome required. 1400 and 900 px, light and dark."""
import tempfile
import unittest

from _demo import DemoStore
from clark import page
from test_published_work_no_add import open_page
from test_server import Running, chrome, wait
from test_work_filters import need_chrome

VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]
READ = """(() => { const col = (v) => { const i = document.createElement('i'); i.style.color = 'var(' + v + ')'; document.body.appendChild(i); const c = getComputedStyle(i).color; i.remove(); return c; };
  const one = (id) => { const e = document.querySelector(id); e.style.transition = 'none'; const s = getComputedStyle(e); return {w: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth],
    st: s.borderTopStyle, c: s.borderTopColor, r: s.borderTopLeftRadius, h: e.getBoundingClientRect().height, w2: e.getBoundingClientRect().width, mh: s.minHeight, pad: [s.paddingLeft, s.paddingRight], bg: s.backgroundColor, fg: s.color, fw: s.fontWeight}; };
  return {g: one('#ucl-group'), s: one('#ucl-sort'), add: one('#ucAddPage'), grey500: col('--grey-500'), blue: col('--brand-blue')}; })()"""


class Controls(unittest.TestCase):
    def read(self, theme, width, scheme):
        need_chrome()
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = Running(data_for=demo.store.data_for, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = open_page(cdp, f"http://127.0.0.1:{s.port}/#usecases&p=ABC", width, scheme)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ucl-group') && !!document.querySelector('#ucAddPage')", sid), 45), "the page drew")
            return cdp.js(READ, sid)

    def test_classic_controls(self):
        for w, scheme in VARIANTS:
            with self.subTest(width=w, scheme=scheme):
                g = self.read("prototype-2.0", w, scheme)
                for k in ("g", "s"):
                    b = g[k]
                    self.assertEqual(b["w"], ["1px"] * 4, k + ": 1px on four sides")
                    self.assertEqual(b["st"], "solid", k)
                    self.assertEqual(b["c"], g["grey500"], k + ": --grey-500 (the prototype --ui)")
                    self.assertEqual(b["r"], "6px", k)
                    self.assertEqual(b["mh"], "28px", k + ": min-height 28")
                    self.assertGreaterEqual(b["h"], 28, k)
                    self.assertGreaterEqual(b["w2"], 38, k + ": the 18px icon sits inside the 10px padding (width not fixed at 34)")
                    self.assertEqual(b["pad"], ["10px", "10px"], k + ": padding 0 10")
                    self.assertEqual(b["bg"], "rgba(0, 0, 0, 0)", k + ": transparent")
                a = g["add"]
                self.assertEqual(a["fg"], g["blue"], "the + is brand coloured")
                self.assertEqual(a["c"], g["blue"], "the + border is brand coloured")
                self.assertEqual(a["fw"], "600", "the + is weight 600")
                self.assertEqual(a["st"], "dashed", "the + is dashed")
                self.assertEqual(a["r"], "6px", "the + radius 6")
                self.assertEqual(a["mh"], "28px", "the + min-height 28")
                self.assertGreaterEqual(a["h"], 28)
                self.assertGreaterEqual(a["w2"], 28, "the + min-width 28")
                self.assertEqual(a["pad"], ["8px", "8px"], "the + padding 0 8")

    def test_cards_unchanged(self):
        g = self.read(None, 1400, "light")
        self.assertNotEqual(g["g"]["r"], "6px" if g["g"]["pad"] == ["10px", "10px"] else "x")
        self.assertNotEqual(g["add"]["fw"], "600")


if __name__ == "__main__":
    unittest.main()

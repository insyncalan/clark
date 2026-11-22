"""Row 1316 follow-up (ruling 19-11, Classic only): Group by and Sort by are labelled buttons (28 high, padding 0 10, 1px --grey-500 border, radius 6, 14px/500); the Use cases table keeps its framed box and heads (Row 1405 owns the heads).
Run: python3 dev/run_tests.py test_gap_1316b   Chrome required."""
import unittest

from test_use_cases_redesign_1325 import Redesign, Base, tearDownModule  # noqa: F401
from clark import theme

JS = """(() => { const q = (s) => document.querySelector(s), g = (e) => getComputedStyle(e), r = (e) => e.getBoundingClientRect();
  const w = q('#usecases .ucl-wrap > .wgroup'), th = q('#usecases thead th'), td = q('#usecases tbody tr[data-uc] td.c-item'), tr = q('#usecases tbody tr[data-uc]');
  const b = (id) => { const e = q('#' + id), s = g(e), x = r(e); return [e.textContent.trim(), Math.round(x.height), s.paddingLeft, s.paddingRight, s.borderTopWidth, s.borderTopColor, s.borderTopLeftRadius, s.fontSize, s.fontWeight, s.backgroundColor, e.querySelectorAll('svg').length]; };
  return { frame: [g(w).borderTopWidth, g(w).borderLeftWidth, g(w).borderBottomWidth, g(w).borderTopLeftRadius],
    head: [g(th).backgroundColor, g(th).fontSize, g(th).fontWeight, g(th).textTransform, g(th).letterSpacing, g(th).borderTopWidth, g(th).borderBottomWidth, g(th).borderBottomColor, g(th).color],
    item: [Math.round(r(tr).height), g(td).borderBottomWidth, g(td).borderBottomColor, g(td).borderTopWidth],
    group: b('ucl-group'), sort: b('ucl-sort'), scroll: document.documentElement.scrollWidth <= window.innerWidth }; })()"""


class Flat1316b(Redesign, Base):
    css = theme.css("prototype-2.0")

    def test_labelled_buttons_at_1400(self):
        with self.subTest(), __import__("test_server").chrome() as cdp:
            p = self.open_page(cdp, 1400)
            g = p.js(JS)
            print("MEASURED", g)
            for k in ("group", "sort"):
                x = g[k]
                self.assertEqual(x[0], "Group by" if k == "group" else "Sort by", "the label")
                self.assertEqual(x[1], 28, "28 high")
                self.assertEqual(x[2:5], ["10px", "10px", "1px"], "padding 0 10, 1px border")
                self.assertEqual(x[6:9], ["6px", "14px", "500"], "radius 6, 14px/500")
                self.assertEqual(x[10], 0, "no icon")
            self.assertTrue(g["scroll"])


for _n in [n for n in dir(Redesign) if n.startswith("test_")]:
    setattr(Flat1316b, _n, None)      # only the Row 1316 follow-up test runs here; the 1325 tests run in their own file


if __name__ == "__main__":
    unittest.main()

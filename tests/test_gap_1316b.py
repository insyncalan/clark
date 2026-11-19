"""Row 1316 follow-up (ruling 19-11, Classic only): the Use cases table is flat (no frame, no grey header; header 13px/500 uppercase .08em muted over a 1px rule; item min 40 high over a hairline) and Group by / Sort by are labelled buttons (28 high, padding 0 10, 1px border, radius 6, 14px/500).
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

    def test_flat_table_and_labelled_buttons_at_1400(self):
        with self.subTest(), __import__("test_server").chrome() as cdp:
            p = self.open_page(cdp, 1400)
            g = p.js(JS)
            print("MEASURED", g)
            self.assertEqual(g["frame"], ["0px", "0px", "0px", "0px"], "no frame round the table")
            self.assertEqual(g["head"][0], "rgba(0, 0, 0, 0)", "no fill on the header")
            self.assertEqual(g["head"][1:5], ["13px", "500", "uppercase", "1.04px"], "header 13px/500 uppercase .08em")
            self.assertEqual([g["head"][5], g["head"][6]], ["0px", "1px"], "header: 1px rule below only")
            self.assertGreaterEqual(g["item"][0], 40, "item min height 40")
            self.assertEqual([g["item"][1], g["item"][3]], ["1px", "0px"], "item hairline under, none over")
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

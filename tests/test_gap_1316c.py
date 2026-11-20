"""Row 1316 gaps (Classic only): the Add use case button border is dashed brand (ruling 19-11), and the Dashboard-section text tabs (.mv-txt) are a grey 1px box with grey dividers, radius 6, 28 high, weight --weight-medium (600 in Classic).
Run: python3 dev/run_tests.py test_gap_1316c   Chrome required."""
import unittest

from test_use_cases_redesign_1325 import Redesign, Base, tearDownModule  # noqa: F401
from clark import theme

JS = """(() => { const q = (s) => document.querySelector(s), g = (e) => getComputedStyle(e);
  const h = document.createElement('div'); h.innerHTML = '<span class="mv-txt" id="t1316c"><button type="button" aria-current="true">Week</button><span aria-hidden="true">.</span><button type="button">Month</button></span><i id="p1316c" style="border:1px solid var(--grey-500)"></i>';
  document.body.appendChild(h);
  const t = q('#t1316c'), b = t.querySelectorAll('button'), a = q('#ucAddPage');
  return { ph: q('#ucl-q').placeholder, add: g(a).borderTopStyle, grey: g(q('#p1316c')).borderTopColor,
    box: [g(t).borderTopWidth, g(t).borderTopColor, g(t).borderTopLeftRadius],
    b0: [Math.round(b[0].getBoundingClientRect().height), g(b[0]).fontWeight],
    b1: [Math.round(b[1].getBoundingClientRect().height), g(b[1]).fontWeight, g(b[1]).borderLeftWidth, g(b[1]).borderLeftColor] }; })()"""


class Gap1316c(Redesign, Base):
    css = theme.css("prototype-2.0")

    def test_add_solid_and_text_tabs_at_1400(self):
        with self.subTest(), __import__("test_server").chrome() as cdp:
            p = self.open_page(cdp, 1400)
            g = p.js(JS)
            print("MEASURED", g)
            self.assertEqual(g["ph"], "Search use cases, or try status:Flag", "Classic search placeholder")
            self.assertEqual(g["add"], "dashed", "Add use case: dashed border (ruling 19-11)")
            self.assertEqual(g["box"], ["1px", g["grey"], "6px"], "text tabs: 1px grey box, radius 6")
            self.assertEqual((g["b0"][0], g["b1"][0]), (28, 28), "28 high")
            self.assertEqual((g["b0"][1], g["b1"][1]), ("600", "600"), "weight var(--weight-medium) = 600 in Classic, on both")
            self.assertEqual(g["b1"][2:], ["1px", g["grey"]], "grey divider between")


for _n in [n for n in dir(Redesign) if n.startswith("test_")]:
    setattr(Gap1316c, _n, None)


if __name__ == "__main__":
    unittest.main()

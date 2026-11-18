"""Row 1269: the Edit-mode section control (.sec-ctl) against the Classic section's 2px gutter rule and 20px padding, as Chrome lays it out.

Run: python3 dev/run_tests.py test_theme_sec_ctl_1269
Real Dashboard in Edit, over the fictional demo data, at 1400 and 900 only, in Classic (the Theme layered) and in Cards (no Theme).
Measured: getBoundingClientRect of every .sec-ctl against its .sec, the section's border box edge, its content edge (border plus padding)
and its heading box. The control must not overlap the heading or any text box in its section, and must stay inside the viewport.
Fails, never skips, without Chrome. The numbers are printed as a table.
"""
import json
import unittest

import test_glance_page as g
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

from clark import page

NAME = "prototype-2.0"
SIZES = (1400, 900)
THEMES = (("classic", NAME), ("cards", None))
DENSITIES = ("compact", "comfortable")      # the standard (One card) and Comfortable, the one where the Classic gutter rule is drawn
TABLE = []

MEASURE = """(() => {
  const R = (e) => { const b = e.getBoundingClientRect(); return { l: b.left, t: b.top, r: b.right, b: b.bottom }; };
  const hit = (a, b) => a.l < b.r - 0.01 && a.r > b.l + 0.01 && a.t < b.b - 0.01 && a.b > b.t + 0.01;
  const out = [];
  for (const sec of document.querySelectorAll('#report .secs > .sec')) {
    const ctl = sec.querySelector(':scope > .sec-ctl'); if (!ctl) continue;
    const cs = getComputedStyle(sec), s = R(sec), c = R(ctl);
    if (c.r - c.l === 0 || s.r - s.l === 0) continue;
    const bl = parseFloat(cs.borderLeftWidth) || 0, pl = parseFloat(cs.paddingLeft) || 0;
    const content = s.l + bl + pl;
    const texts = [];       // every element of the section, outside the control, that holds text of its own
    for (const e of sec.querySelectorAll('*')) {
      if (ctl.contains(e)) continue;
      const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      if (own) { const q = R(e); if (q.r > q.l && q.b > q.t) texts.push(q); }
    }
    const head = sec.querySelector('.sec-head'), h = head ? R(head) : null;
    const rule = { l: s.l, t: s.t, r: s.l + bl, b: s.b };      // the left border line as a thin box
    out.push({ id: sec.dataset.id, right: sec.classList.contains('slot-right'), c, s, content, bl, pl, h,
      overHead: h ? hit(c, h) : false, overText: texts.filter((q) => hit(c, q)).length, texts: texts.length,
      overRule: bl > 0 && hit(c, rule), borderColour: cs.borderLeftColor,
      inView: c.l >= 0 && c.r <= innerWidth, scroll: document.documentElement.scrollWidth <= innerWidth,
      left_of_content: c.r <= content + 0.01 });
  }
  return JSON.stringify(out);
})()"""


class SecCtl(g.Setup):
    def setUp(self):
        super().setUp()
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=self.theme)

    def measure(self, width, theme, density):
        self.theme = theme
        with chrome() as cdp:
            p = self.show(cdp, width=width, standard=True)
            p.js("document.documentElement.dataset.density = %r" % density)
            p.edit()
            return json.loads(p.js(MEASURE))

    def test_the_control_clears_the_gutter_rule_the_padding_and_the_text_at_1400_and_900(self):
        for name, theme in THEMES:
            for width, density in ((w, d) for w in SIZES for d in DENSITIES):
                with self.subTest(theme=name, width=width, density=density):
                    secs = self.measure(width, theme, density)
                    self.assertGreater(len(secs), 5, "the demo dashboard has many sections")
                    for d in secs:
                        where = f"{name} {density} {width} {d['id']}"
                        self.assertFalse(d["overHead"], f"{where}: the control overlaps the heading box")
                        self.assertEqual(d["overText"], 0, f"{where}: the control overlaps text")
                        self.assertFalse(d["overRule"], f"{where}: the control overlaps the section's left rule")
                        self.assertTrue(d["left_of_content"], f"{where}: the control ends before the section's content starts")
                        self.assertTrue(d["inView"], f"{where}: the control is inside the viewport")
                        self.assertTrue(d["scroll"], f"{where}: no sideways scroll")
                        TABLE.append((width, name, density, d))
        print()
        print("width theme   density     rule/pad ctl.left ctl.right sec.left content.left rule.l-r      overlap(rule/head/text)")
        seen = set()
        for width, name, density, d in TABLE:
            key = (width, name, density, d["right"])
            if key in seen:
                continue
            seen.add(key)
            c, s = d["c"], d["s"]
            print("%5d %-8s %-11s %g/%g %8.1f %9.1f %8.1f %12.1f %6.1f-%-6.1f %s/%s/%s (%s%s)" % (
                width, name, density, d["bl"], d["pl"], c["l"], c["r"], s["l"], d["content"], s["l"], s["l"] + d["bl"],
                "yes" if d["overRule"] else "no", "yes" if d["overHead"] else "no", "yes" if d["overText"] else "no",
                d["id"], " slot-right" if d["right"] else ""))


if __name__ == "__main__":
    unittest.main()

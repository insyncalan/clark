"""Row 1043: the Help text a person reads (paragraphs and list items, on every tab) stays a readable measure at 1400 and 900 px.

Run: python3 dev/run_tests.py test_help_text_measure_1043
The real page in headless Chrome. Each tab is opened; for every paragraph and list item the widest drawn line is measured
(the width of the line box divided by the width of one "0" in that font, the "ch" of that text) and must be at most 80.
"""
import unittest

from _paths import TOOLS  # noqa: F401
import test_help_nav_page as nav
from test_report_editor import Base

MAX_CH = 80
TABS = ("start", "howto", "reference")

JS = """(() => {
  const out = [];
  const pane = document.querySelector('#hpPane');
  for (const el of pane.querySelectorAll('p, li')) {
    if (el.closest('.hp-idx, .hp-tabs')) continue;
    const text = (el.textContent || '').trim();
    if (text.length < 90) continue;
    const cs = getComputedStyle(el);
    const c = document.createElement('canvas').getContext('2d');
    c.font = cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
    const ch = c.measureText('0').width;
    const r = document.createRange(); r.selectNodeContents(el);
    const lines = {};
    for (const q of r.getClientRects()) { const k = Math.round(q.top / 4); lines[k] = Math.max(lines[k] || 0, q.right - q.left); }
    const widest = Math.max(...Object.values(lines));
    out.push([widest / ch, text.slice(0, 40)]);
  }
  return out;
})()"""


class TextMeasure(Base):
    def test_paragraphs_and_list_items_stay_a_readable_measure(self):
        from test_server import chrome
        bad = []
        with chrome() as cdp:
            p = nav.Nav.in_help(self, cdp)
            for tab in TABS:
                p.js(f"document.querySelector('#hpTab-{tab}').click()")
                p.until(f"document.querySelector('#hpTab-{tab}').getAttribute('aria-selected') === 'true' && !!document.querySelector('.hp-idx a')", f"the {tab} tab")
                for w in nav.SIZES:
                    nav.set_size(cdp, p, w)
                    got = p.js(JS)
                    self.assertTrue(got, f"{tab} {w}: text is drawn")
                    worst = max(got, key=lambda g: g[0])
                    print(f"MEASURE {tab} {w}: {len(got)} blocks, widest {worst[0]:.0f} ch ({worst[1]!r})")
                    bad.extend(f"{tab} {w}: {g[0]:.0f} characters: {g[1]!r}" for g in got if g[0] > MAX_CH)
        self.assertEqual(bad, [], "lines wider than 80 characters")


if __name__ == "__main__":
    unittest.main()

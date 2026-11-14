"""Row 1043: Help text lines run a readable length (about 65 to 75 characters), not about 130, at 1400 and 900 px.

Run: python3 dev/run_tests.py test_help_line_length
The real page in headless Chrome. The How do I and Reference tabs are opened; the characters on every rendered line of the steps, paragraphs, list items and notes are counted
(one Range per character, grouped by line) and must stay under 80.
"""
import unittest

from _paths import TOOLS  # noqa: F401
import test_help_nav_page as nav
from test_report_editor import Base

MAX_CH = 80


# Every kind of help text the CSS caps with a readable measure, on the tab that shows it.
SELECTORS = {
    "howto": [".hp-task li", ".hp-task > p", ".hp-note"],
    "reference": [".hp-ref p", ".hp-ref li", ".hp-note"],
}

# The characters on each RENDERED line of each matching element: every character gets a Range, and the characters that share a top edge are one line.
MEASURE = """((sels) => {
  const lines = [];
  for (const el of document.querySelectorAll(sels.join(','))) {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const byTop = new Map();
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      if (el.tagName === 'LI' && n.parentElement.closest('li') !== el) continue;   // a nested item is measured on its own
      const r = document.createRange();
      for (let i = 0; i < n.data.length; i++) {
        r.setStart(n, i); r.setEnd(n, i + 1);
        const b = r.getClientRects()[0];
        if (!b || !b.width) continue;
        const key = Math.round(b.top / 4);
        byTop.set(key, (byTop.get(key) || 0) + 1);
      }
    }
    for (const c of byTop.values()) lines.push([c, el.className || el.tagName]);
  }
  return lines;
})(%s)"""


class LineLength(Base):
    def test_help_text_lines_stay_a_readable_measure(self):
        import json
        from test_server import chrome
        with chrome() as cdp:
            p = nav.Nav.in_help(self, cdp, "howto")
            for tab, sels in SELECTORS.items():
                p.js(f"document.querySelector('#hpTab-{tab}').click()")
                p.until(f"document.querySelector('#hpTab-{tab}').getAttribute('aria-selected') === 'true' && !!document.querySelector('.hp-idx a')", f"the {tab} tab")
                for w in nav.SIZES:
                    nav.set_size(cdp, p, w)
                    got = p.js(MEASURE % json.dumps(sels))
                    self.assertTrue(got, f"{tab} {w}: help text is drawn")
                    worst = max(got, key=lambda g: g[0])
                    self.assertLess(worst[0], MAX_CH, f"{tab} {w}: a rendered line of {worst[1]} is {worst[0]} characters")


if __name__ == "__main__":
    unittest.main()

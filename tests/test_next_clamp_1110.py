"""Row 1110: a next step in an opened use case row fills at most two lines (icon, text and id together), a long
description ends in an ellipsis, and a click on the step opens the work item's peek. 1400 and 900 px, light and dark."""
import unittest

from _paths import SRC  # noqa: F401
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

LONGTEXT = "Reconcile every supplier remittance file against the ledger and confirm the totals with each finance owner " * 4

MEASURE = """(() => { const li = document.querySelector('.ucdetail .ucstepl li[data-step]'); const q = (s) => { const b = li.querySelector(s).getBoundingClientRect(); return {top: b.top, bottom: b.bottom, left: b.left, right: b.right}; };
  const t = li.querySelector('.ucstept'), lh = parseFloat(getComputedStyle(t).lineHeight), r = li.getBoundingClientRect();
  return {h: r.height, lh, clipped: t.scrollHeight > t.clientHeight, th: t.clientHeight, av: q('.av'), id: q('[data-stepid]'), tx: q('.ucstept'), row: {top: r.top, bottom: r.bottom}}; })()"""


class NextClamp(Setup):
    def test_a_long_step_is_two_lines_with_icon_and_id_beside_it_and_a_click_opens_the_peek(self):
        self.demo.action(description=LONGTEXT, owner="Pat Demo", due_date="2020-01-01", use_case=self.demo.use_case)
        for width in (1400, 900):
            for dark in (False, True):
                with chrome() as cdp:
                    p = self.show(cdp, width=width, dark=dark)
                    p.js("document.querySelector('.ucrow .ucbar').click()")
                    p.until("!!document.querySelector('.ucdetail [data-stepid]')", "the row opened")
                    p.js("""[...document.querySelectorAll('.ucstepl li')].forEach(l => { if (!l.textContent.includes('Reconcile')) l.remove(); })""")
                    m = p.js(MEASURE)
                    tag = f"{width} dark={dark}"
                    self.assertLessEqual(m["th"], m["lh"] * 2 + 1, f"text at most two lines {tag}")
                    self.assertTrue(m["clipped"], f"the long text is cut {tag}")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.ucstept')).webkitLineClamp"), "2")
                    self.assertLessEqual(m["h"], max(m["lh"] * 2, 26) + 8, f"the step is no taller than two lines {tag}")
                    for k in ("av", "id", "tx"):
                        self.assertGreaterEqual(m[k]["top"], m["row"]["top"] - 1)
                        self.assertLessEqual(m[k]["bottom"], m["row"]["bottom"] + 1, f"{k} inside the step {tag}")
                    self.assertLess(m["av"]["right"], m["tx"]["left"] + 1)
                    self.assertLess(m["tx"]["right"], m["id"]["left"] + 1, f"id after the text, same line {tag}")
                    self.assertFalse(p.js("!!clarkPage.peek()"))
                    p.js("document.querySelector('.ucstepl li[data-step] .ucstept').click()")
                    p.until("!!clarkPage.peek()", f"a click on the step opened the peek {tag}")


if __name__ == "__main__":
    unittest.main()

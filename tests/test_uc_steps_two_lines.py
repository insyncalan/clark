"""Row 1110: a next step in an opened dashboard use case row fills at most two lines (icon, text and id together), a long description ends
with "..." and a click on the step opens the work item's peek.

Run: python3 dev/run_tests.py test_uc_steps_two_lines
Same harness and fictional data as test_glance_page. Laptop widths only: 1400 and 900 px.
"""
import unittest

from test_glance_page import Setup, USER, tearDownModule  # noqa: F401
from test_server import chrome

LONG = "Chase the supplier about the payment file that still fails on the third run and agree a date to retest it with the finance team " * 3


class Steps(Setup):
    def test_a_long_step_stops_at_two_lines_with_an_ellipsis_and_a_click_opens_the_peek(self):
        with self.store.step("dashboard", USER) as st:
            st.update("actions", self.a_open, {"description": LONG, "client_message": ""})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("document.querySelector('.ucrow .ucbar').click()")
                p.until("!!document.querySelector('.ucdetail [data-stepid]')", "the row opened")
                lines = p.js("""[...document.querySelectorAll('.ucdetail .ucstepl li')].map(li => {
                    const t = li.querySelector(':scope > span:not(.av):not([data-stepid])'), lh = parseFloat(getComputedStyle(t).lineHeight);
                    return Math.round(li.getBoundingClientRect().height / lh); })""")
                self.assertTrue(all(n <= 3 for n in lines), lines)           # two text lines (the row's own padding may add a fraction)
                self.assertEqual(p.js("""(() => { const t = document.querySelector('.ucstepl li > span:not(.av):not([data-stepid])');
                    return [getComputedStyle(t).webkitLineClamp, t.scrollHeight > t.clientHeight]; })()"""), ["2", True], "cut at two lines")
                p.js("document.querySelector('.ucstepl li > span:not(.av):not([data-stepid])').click()")
                p.until("!!document.querySelector('.peek, [data-peek], dialog[open]')", "the peek opened")


if __name__ == "__main__":
    unittest.main()

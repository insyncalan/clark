"""Row 1108: the dashboard's Use case summary shows the first 5 use cases, with a discreet "Show all N use cases" / "Show the first 5".

Run: python3 dev/run_tests.py test_uc_summary_five
Same harness and fictional data as test_glance_page. Laptop widths only: 1400 and 900 px.
"""
import unittest

from test_glance_page import Setup, USER, tearDownModule  # noqa: F401
from test_server import chrome

ROWS = "document.querySelectorAll('.ucrows > .ucrow').length"
BUTTON = "(document.querySelector('[data-ucall]') || {}).textContent"


class FirstFive(Setup):
    def more(self, n):
        with self.store.step("dashboard", USER) as st:
            for i in range(n):
                st.create("use_cases", {"project": "ABC", "title": f"Extra {i}", "status": "On track", "ref": f"3.{i}", "source": "demo"})

    def test_with_five_or_fewer_there_is_no_control(self):
        self.more(3)                                                  # 2 + 3 = 5
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js(ROWS), 5)
            self.assertIsNone(p.js(BUTTON))

    def test_with_more_the_first_five_show_and_the_control_expands_and_reduces_while_the_count_stays(self):
        self.more(4)                                                  # 2 + 4 = 6
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                self.assertEqual(p.js(ROWS), 5)
                self.assertEqual(p.js(BUTTON), "Show all 6 use cases")
                self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "6 use cases", "the count covers every use case")
                self.assertEqual(p.js("document.querySelectorAll('.meter i').length"), 6, "so does the meter")
                p.js("document.querySelector('[data-ucall]').click()")
                p.until(f"{ROWS} === 6", "all shown")
                self.assertEqual(p.js(BUTTON), "Show the first 5")
                p.js("document.querySelector('[data-ucall]').click()")
                p.until(f"{ROWS} === 5", "reduced")


if __name__ == "__main__":
    unittest.main()

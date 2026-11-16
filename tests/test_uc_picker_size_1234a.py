"""Row 1234-A: the add-a-use-case picker box size (shell.css .picker.pkt): 1080 px wide, at least 650 px tall. Widths 1400 and 900 only.

Run: python3 dev/run_tests.py test_uc_picker_size_1234a
Same page, store and data as test_uc_picker_table (two use cases on the dashboard, two more that are not on it).
"""
import unittest

from _demo import USER
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome
import test_uc_picker_table as T

Q = T.Q

BOX = "(r => [Math.round(r.width), Math.round(r.height), window.innerWidth])(" + Q + ".getBoundingClientRect())"


class Size(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3, "headline": "No login", "client_visible": 0, "source": "demo"})
            st.create("use_cases", {"project": "ABC", "title": "Month end close", "status": "On track", "ref": "2.1", "sort_order": 4, "headline": "Done in two days", "client_visible": 0, "source": "demo"})
    edit = T.Table.edit
    click = T.Table.click
    show_picker = T.Table.show_picker

    def box_at(self, width):
        with chrome() as cdp:
            p = self.edit(cdp, width)
            self.show_picker(p)
            return p.js(BOX), p.js("(e => Math.round(e.clientWidth - parseFloat(getComputedStyle(e).paddingLeft) - parseFloat(getComputedStyle(e).paddingRight)))(" + Q + ".parentElement)")

    def test_wide_window_gives_the_full_1080_and_at_least_650_tall(self):
        (w, h, win), _ = self.box_at(1400)
        self.assertEqual(w, 1080, "1080 wide when the window has room")
        self.assertGreaterEqual(h, 650, "at least 650 tall, though only a few rows are listed")
        self.assertLessEqual(h, win, "never taller than the window is wide here")

    def test_narrow_window_shrinks_to_its_container_and_keeps_the_height(self):
        (w, h, win), parent = self.box_at(900)
        self.assertLess(w, 1080, "shrinks below 1080 at 900")
        self.assertEqual(w, parent, "fills the room its container leaves")
        self.assertLessEqual(w, win, "fits the window")
        self.assertGreaterEqual(h, 650, "still at least 650 tall")


if __name__ == "__main__":
    unittest.main()

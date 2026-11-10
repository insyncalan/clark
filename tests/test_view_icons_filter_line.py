"""Row 1084: the List, Board and Group by icons sit on the filter box line, at the right end of the box.
The saved-view tab row keeps only the tabs (each with its count and the current tab's chevron) and Save view / Discard changes.
Each icon button has a name and a target of 24 px or more. 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_view_icons_filter_line
"""
import unittest

from test_server import chrome  # noqa: E402
from test_work_board_page import Base  # noqa: E402

ICONS = ("[...document.querySelectorAll('#work .fline .vicons button')].map(b => [b.getAttribute('aria-label'), b.title, "
         "b.getBoundingClientRect().width >= 24 && b.getBoundingClientRect().height >= 24, b.textContent.trim()])")


class IconsOnTheLine(Base):
    def test_three_named_icons_inside_the_filter_box_and_none_on_the_tab_row(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.assertEqual(cdp.js(ICONS, sid), [["List", "List", True, ""], ["Board", "Board", True, ""], ["Group by", "Group by", True, ""]],
                             "List, Board and Group by: icons, named, 24 px or more")
            self.assertEqual(cdp.js("document.querySelectorAll('.fvrow [data-lay], .fvrow #viewMenu').length", sid), 0, "none beside the tabs")
            self.assertEqual(cdp.js("document.querySelectorAll('#work .fline #viewMenu').length", sid), 1)
            self.assertEqual(cdp.js("document.querySelector('#viewMenu .nch') === null", sid), True, "icon only: no chevron, no word")

    def test_they_are_at_the_right_end_of_the_box_on_one_line_with_it(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.visit(cdp, width=width)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    got = cdp.js("(() => { const f = document.querySelector('#work .fline').getBoundingClientRect(), i = document.querySelector('#work .fline #viewMenu').getBoundingClientRect(),"
                                 " x = document.querySelector('#fline-input').getBoundingClientRect();"
                                 " return [i.right <= f.right && f.right - i.right < 24, i.top >= f.top && i.bottom <= f.bottom, i.left > x.left]; })()", sid)
                    self.assertEqual(got, [True, True, True])
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), True)

    def test_the_icons_still_work_and_the_tabs_keep_their_counts(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            cdp.js("document.querySelector('#work .vicons [data-lay=board]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('#work-board')", "the board")
            cdp.js("document.querySelector('#work .vicons [data-lay=table]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('table.items')", "the list")
            self.assertGreaterEqual(cdp.js("document.querySelectorAll('.vtab em.num').length", sid), 1, "tab counts stay")


if __name__ == "__main__":
    unittest.main()

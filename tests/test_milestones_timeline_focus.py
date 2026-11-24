"""Hunt 19: the timeline's Reset keeps keyboard focus, and its scroll box is a named region a screen reader can find.

Run: python3 dev/run_tests.py test_milestones_timeline_focus
"""
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait


class TimelineFocus(BrowserBase, unittest.TestCase):
    def test_reset_leaves_focus_on_the_line_not_on_the_page(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, "#milestones&p=TUL", port)
                h = cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid)
                cdp.js(f"document.querySelector('.mv-wrap').style.height = '{h * 2}px'", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-zreset]')", sid)))
                cdp.js("document.querySelector('[data-zreset]').focus()", sid)
                cdp.js("document.querySelector('[data-zreset]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('[data-zreset]')", sid)))
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.classList.contains('mv-wrap')", sid)), f"{width}: focus after Reset")

    def test_the_scroll_box_has_a_role_so_its_name_is_read(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, "#milestones&p=TUL", port)
                self.assertEqual(cdp.js("document.querySelector('.mv-wrap').getAttribute('role')", sid), "region", width)


if __name__ == "__main__":
    unittest.main()

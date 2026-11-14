"""Row 824 (W1 to W6): the Work items page has no mode. In View, at 1400 and 900 px, light and dark, the client-visible eye is a button
that works, a click on a cell opens its picker, the row menu opens, the peek holds the words box, tabs and Latest update, Enter on a row
opens the peek and the arrows walk the cells, and Export to Excel is drawn. On the Dashboard in View the peek still has none of the
edit parts. Run: python3 dev/run_tests.py test_work_no_mode
"""
import json
import unittest

import test_inline_edits as ie  # noqa: E402
from test_inline_edits import click, key  # noqa: E402
from test_row_menu import right_click  # noqa: E402
from test_server import chrome  # noqa: E402

VARIANTS = [(1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")]
PEEK_PARTS = "'[data-sneak-open],[data-sneak]'"


class WorkNoMode(unittest.TestCase):
    setUp = ie.Live.setUp
    read = ie.Live.read
    open_page = ie.Live.open_page
    until = ie.Live.until

    def themed(self, cdp, sid, theme):
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)

    def test_work_items_edit_in_view_at_both_widths_in_light_and_dark(self):
        for width, theme in VARIANTS:
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                self.themed(cdp, sid, theme)
                self.assertEqual(cdp.js("document.querySelectorAll('[data-mode]').length", sid), 0, "no View | Edit switch off the Dashboard: the page is always editable")
                # W1: the eye is a button
                self.assertEqual(cdp.js("document.querySelector('#work tbody tr[data-id] .weye').tagName", sid), "BUTTON", "the eye is a button in View")
                # W3: no Export icon on the page (item 1142)
                self.assertEqual(cdp.js("document.querySelectorAll('#expBtn').length", sid), 0, "item 1142: no Export icon on the page; it is in the profile menu and Settings")
                # a click on a cell opens its picker
                click(cdp, sid, "#work tbody [data-cell$=':status']")
                self.until(cdp, sid, "!!document.querySelector('[data-pop]')", "a click on a cell in View opens its picker")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('[data-pop]')", "Esc closes it")
                # the row menu opens
                right_click(cdp, sid, "#work tbody tr[data-id] .c-item")
                self.until(cdp, sid, "!!document.querySelector('.rowmenu [role=menu]')", "the row menu opens in View")
                key(cdp, sid, "Escape")
                # W2: Right on the row walks the cells, Enter opens the peek (W6: with its words box and tabs)
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "ArrowRight")
                self.assertFalse(cdp.js("!!document.querySelector('#peek')", sid), "Right no longer opens the peek")
                self.assertTrue(cdp.js("document.activeElement.hasAttribute('data-cell') || document.activeElement.classList.contains('weye')", sid), "Right walks the cells")
                cdp.js("document.querySelector('#work tbody tr[data-id]').focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('#peek')", "Enter opens the peek")
                cdp.js("document.activeElement.blur()", sid)      # row 1015: no sparkle; two slashes open the words box
                for _ in range(2):
                    common = {"key": "/", "code": "Slash", "windowsVirtualKeyCode": 191}
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **common, "text": "/"}, sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)
                self.until(cdp, sid, f"!!document.querySelector({PEEK_PARTS})", "the words box is in the peek in View")
                self.assertTrue(cdp.js("!!document.querySelector('#peek [role=tablist]')", sid), "the tabs are in the peek in View")
                self.assertTrue(cdp.js("!!document.querySelector('#peek [data-pk-client]')", sid), "Client visible line")

    def test_the_eye_click_in_view_writes_and_says_so(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            click(cdp, sid, "#work tbody tr[data-id] .weye")
            self.until(cdp, sid, "!!document.querySelector('.toast-text') && /client/.test(document.querySelector('.toast-text').textContent)", "a click on the eye in View is answered with a toast")

    def test_the_dashboard_in_view_still_has_none_of_it(self):
        for width, theme in VARIANTS:
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                sid = self.open_page(cdp, width, edit=False)
                cdp.js("window.location.hash = '#dashboard&p=TUL'", sid)
                self.until(cdp, sid, "!document.querySelector('#work tbody tr')", "the Dashboard is drawn")
                self.themed(cdp, sid, theme)
                cdp.js("clarkPage.openPeek('TUL-008', 'item')", sid)
                self.until(cdp, sid, "!!document.querySelector('#peek')", "the peek opens")
                self.assertEqual(cdp.js("document.querySelector('[data-mode=view]').getAttribute('aria-pressed')", sid), "true")
                self.assertFalse(cdp.js(f"!!document.querySelector({PEEK_PARTS})", sid), "no words box on the Dashboard in View")
                self.assertFalse(cdp.js("!!document.querySelector('#peek [role=tablist]')", sid), "no tabs on the Dashboard in View")


if __name__ == "__main__":
    unittest.main()

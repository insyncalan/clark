"""Row 1499: the Work items Columns menu (a right click on a column heading in Edit) opens under a visible heading 'Columns to show' (an h5) in Classic
only; Cards draws none. The heading is no menu item (the arrow keys still start on, and wrap between, the column lines) and is hidden from readers
(the menu already carries the aria-label).

Run: python3 dev/run_tests.py test_wil_columns_head_1499
Headless Chrome (required: fails, never skips, without it), at 1400 and 900 px.
"""
import json
import tempfile
import unittest

from _real_server import real_server
from clark import page, theme
from test_server import chrome
import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401

OPEN = "document.querySelector(%s).dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, cancelable: true}))"
HEAD = "[...document.querySelectorAll('.cols-menu h5')].map(h => [h.textContent, h.getAttribute('role'), h.getAttribute('aria-hidden')])"


class Heading(base.PageBase):
    add, show = base.InThePage.add, base.InThePage.show
    theme = "prototype-2.0"

    def setUp(self):
        super().setUp()
        base.plant(self)
        if self.theme:
            self.s.close()
            css = theme.css(self.theme)
            self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=self.seam)
            self.addCleanup(self.s.close)

    def opened(self, width):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        cdp_cm = chrome()
        cdp = cdp_cm.__enter__()
        self.addCleanup(cdp_cm.__exit__, None, None, None)
        p = self.show(cdp, width)
        p.edit()
        head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
        p.until(f"!!document.querySelector({json.dumps(head)})", "the list drew in Edit")
        p.js(OPEN % json.dumps(head))
        p.until("!!document.querySelector('.cols-menu')", "the menu opened")
        return p

    def test_classic_menu_is_headed_columns_to_show_with_an_aria_hidden_presentation_h5(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                p = self.opened(width)
                self.assertTrue(p.js("!!document.getElementById('theme')"), "the Classic layer is on")
                self.assertEqual(p.js(HEAD), [["Columns to show", "presentation", "true"]])
                self.assertEqual(p.js("document.querySelector('.cols-menu').firstElementChild.tagName"), "H5", "the heading is the menu's first line")

    def test_the_heading_is_no_menu_item_and_the_keys_start_on_and_wrap_between_the_column_lines(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                p = self.opened(width)
                self.assertEqual(p.js("document.activeElement.dataset.colName"), "Type", "the focus starts on the first column line")
                key = "document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown', {key: %s, bubbles: true, cancelable: true}))"
                p.js(key % json.dumps("ArrowUp"))
                self.assertEqual(p.js("document.activeElement.dataset.colName"), "Milestone", "Up from the first wraps to the last, not onto the heading")
                p.js(key % json.dumps("ArrowDown"))
                self.assertEqual(p.js("document.activeElement.dataset.colName"), "Type", "Down from the last wraps to the first, not onto the heading")
                p.js(key % json.dumps("End"))
                p.js(key % json.dumps("Home"))
                self.assertEqual(p.js("document.activeElement.dataset.colName"), "Type")
                self.assertEqual(p.js("document.querySelectorAll('.cols-menu [role^=menuitem]').length"), 8, "the eight columns are the only items")


class CardsNoHeading(Heading):
    theme = None

    def test_classic_menu_is_headed_columns_to_show_with_an_aria_hidden_presentation_h5(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                p = self.opened(width)
                self.assertTrue(p.js("!document.getElementById('theme')"), "Cards: no Theme")
                self.assertEqual(p.js(HEAD), [], "Cards draws no heading")
                self.assertEqual(p.js("document.querySelector('.cols-menu').getAttribute('aria-label')"), "Columns to show")

    test_the_heading_is_no_menu_item_and_the_keys_start_on_and_wrap_between_the_column_lines = None


if __name__ == "__main__":
    unittest.main()

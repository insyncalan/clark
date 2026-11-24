"""Import from Excel: after a file is refused the focus stays in the box (Choose a file takes it back), so Esc and Tab still work.
Run: python3 dev/run_tests.py test_import_focus_after_refusal
"""
import base64
import unittest

from test_settings_data_page import Card, WIDTHS
from test_server import chrome


class FocusAfterRefusal(Card):
    def test_focus_is_back_on_choose_a_file_after_a_refused_file(self):
        junk = base64.b64encode(b"this is not a workbook").decode()
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                p.js("document.querySelector('#import-workbook').click()")
                p.until("!!document.querySelector('#import-box')", "the box opened")
                self.settle(p, "document.activeElement && document.activeElement.id === 'import-choose'", "focus on Choose a file")
                self.pick_file(p, junk)
                self.settle(p, "!!document.querySelector('#import-problem').textContent", "the refusal")
                self.settle(p, "document.activeElement && document.activeElement.id === 'import-choose'", "focus back on Choose a file")
                p.js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                self.settle(p, "!document.querySelector('#import-box')", "Esc closed the box")


for _name in [n for n in dir(Card) if n.startswith("test_")]:      # only this class's own test, not the Card's
    setattr(FocusAfterRefusal, _name, None)


if __name__ == "__main__":
    unittest.main()

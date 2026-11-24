"""Row 1304: an unfinished group word (group:status with no space after it) never reaches the applied filter line, after the pause or on Tab/blur.

Run: python3 dev/run_tests.py test_group_in_filter_field_hostile_1304
The real page in headless Chrome against the real server over a demo database.
"""
import time
import unittest

from test_server import chrome, wait  # noqa: E402,F401
from test_work_filters import click, key  # noqa: E402
from test_work_board_page import Base, setUpModule, tearDownModule  # noqa: E402,F401

LINE = "document.querySelector('[data-fline]').dataset.line"


class UnfinishedGroupWord(Base):
    def type(self, cdp, sid, text):
        for ch in text:
            if ch == " ":
                key(cdp, sid, " ")
            else:
                cdp.call("Input.insertText", {"text": ch}, sid)

    def test_unfinished_group_word_is_never_applied_to_the_line(self):
        """group:status typed with no space after it, then the pause: the line must not carry a group word (it would be an unknown field)."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                click(cdp, sid, "#fline-input")
                self.type(cdp, sid, "group:status")
                time.sleep(1.2)
                self.assertNotIn("group", cdp.js(LINE, sid), "the group word leaked into the applied line")
                self.assertEqual(cdp.js("document.querySelectorAll('.fline.bad').length", sid), 0, "no red error on a half-typed group word")

    def test_blur_with_group_word_does_not_leak(self):
        with chrome() as cdp:
            sid = self.visit(cdp, width=1400)
            click(cdp, sid, "#fline-input")
            self.type(cdp, sid, "group:owner")
            key(cdp, sid, "Tab")
            time.sleep(1.0)
            self.assertNotIn("group", cdp.js(LINE, sid))


if __name__ == "__main__":
    unittest.main()

"""Row 1180, prototype of the option 'hide the Open source button': on the peek's Source tab the Open source link shows for a web address and for
a PDF path, and not for any other source (a Word file, plain words). Run: python3 dev/run_tests.py test_peek_source_hide_1180
Widths 1400 and 900 only.
"""
import unittest

from _paths import ROOT  # noqa: F401

import test_peek_latest  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

ITEM = "TUL-A-001"
CASES = (("https://example.com/brief.html", True), ("/Users/x/Folder/brief.pdf", True), ("/Users/x/Folder/brief.docx", False), ("Phone call with the client", False))


class SourceHide(test_peek_latest.Browser):
    def with_source(self, source):
        orig = self.fresh
        self.fresh = lambda: (orig(), self._set(source))
        return self

    def _set(self, source):
        with self.store.step("dashboard", "Demo User") as st:
            st.update("actions", ITEM, {"source": source})

    def test_the_open_source_link_shows_only_where_it_can_work(self):
        for source, shown in CASES:
            for width in (1400, 900):
                with self.subTest(source=source, width=width), chrome() as cdp:
                    self.with_source(source)
                    sent, sid = self.load(cdp, width, ITEM)
                    self.assertTrue(wait(lambda: cdp.js("(t => !!t && !/0$/.test(t.textContent.trim()))(document.querySelector('[data-pk-htab=source]'))", sid)), "the source count arrives")
                    click(cdp, sid, "[data-pk-htab=source]")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-hrow=source]')", sid)))
                    self.assertEqual(cdp.js("!!document.querySelector('[data-pk-open-source]')", sid), shown)
                    if not shown:
                        text = cdp.js("document.querySelector('[data-pk-hrow=source]').textContent", sid)
                        self.assertNotIn("Open source", text)
                        self.assertNotIn("·", text, "no dangling middle dot")


if __name__ == "__main__":
    unittest.main()

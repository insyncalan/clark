"""Row 1582 AP14 (Classic only): the Help entry "Add documents and links" shows in the open Help at 1400 and 900 px.
Run: python3 dev/run_tests.py test_help_doclinks_1582
"""
import unittest
from unittest import mock

import _testpage
from clark import page, theme as themes

from test_help_panel import full_help_from_menu
from test_report_editor import Base as Page
from test_server import chrome


class Help(Page):
    def test_the_add_documents_and_links_entry_shows_at_1400_and_900(self):
        real = _testpage.html
        for width in (1400, 900):
            with self.subTest(width=width), mock.patch.object(_testpage, "html", lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0"))):
                with chrome() as cdp:
                    p = self.visit(cdp)
                    full_help_from_menu(p)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js("window.clarkPage.help.open('howto-add-documents-and-links')")
                    p.until("document.querySelector('#help') && document.querySelector('#help').textContent.includes('Add documents and links')", "the entry opened")
                    text = p.js("document.querySelector('#help').textContent")
                    for words in ("Dashboard › Edit › Documents and links", "Choose the file icon to add a file, or drop files on the box.",
                                  "A section holds up to 20 entries.", "Each row has Open; a file also has Download."):
                        self.assertIn(words, text, words)
                    self.assertTrue(p.js("(() => { const e = [...document.querySelectorAll('#help *')].find(x => x.children.length === 0 && x.textContent.includes('Choose the file icon')); const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })()"))


if __name__ == "__main__":
    unittest.main()

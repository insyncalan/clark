"""Row 1285, ruling of 20-11 (Classic only): Help names the peek's line "Shown to the client" in Classic and keeps "Client visible" in Cards.
Run: python3 dev/run_tests.py test_help_client_line_1285
Real page at 1400 and 900 px, both themes: the open Help text.
"""
import unittest
from unittest import mock

import _testpage
from clark import page, theme as themes

from test_help_panel import full_help_from_menu
from test_report_editor import Base as Page
from test_server import chrome

ENTRIES = ("howto-choose-what-the-client-sees", "howto-update-a-milestone", "ref-milestone-peek")


class Base(Page):
    def counts(self, width, classic):
        """Per entry: how many times the open Help draws Client visible and Shown to the client, in Cards or in Classic."""
        out = {}
        real = _testpage.html
        with mock.patch.object(_testpage, "html", (lambda branding=None: page.layer_theme(real(), themes.css("prototype-2.0"))) if classic else real):
            with chrome() as cdp:
                p = self.visit(cdp)
                full_help_from_menu(p)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for e in ENTRIES:
                    p.js("window.clarkPage.help.open(%r)" % e)
                    p.until("document.querySelector('#help') && document.querySelector('#help').textContent.length > 500", e)
                    out[e] = p.js("(() => { const t = document.querySelector('#help').textContent;"
                                  " return [(t.match(/Client visible/g) || []).length, (t.match(/Shown to the client/g) || []).length]; })()")
        return out


class Help(Base):
    def test_classic_says_shown_to_the_client_and_cards_keeps_client_visible(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                cards, classic = self.counts(width, False), self.counts(width, True)
                for e in ENTRIES:
                    (c_old, c_new), (k_old, k_new) = cards[e], classic[e]
                    self.assertGreater(c_old, 0, e)                       # Cards: the old words are there
                    self.assertEqual(k_old, 0, e)                         # Classic: none left
                    self.assertEqual(k_new, c_new + c_old, e)             # each one became the new words, nothing else moved


if __name__ == "__main__":
    unittest.main()

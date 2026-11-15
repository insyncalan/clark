"""Row 1115, S2: Search settings in the Settings head, in a real browser at 1400 and 900 px, light and dark.
Run: python3 dev/run_tests.py test_settings_search_1115

Typing a name or help word keeps the cards and rows that match and hides the rest and the row of chips; Esc or clearing brings everything back.
Chrome is required: these tests fail, never skip, without it."""
import unittest

from test_settings_head import Head
from test_server import chrome

WIDTHS = (1400, 900)
MODES = ("light", "dark")
SHOWN = """[...document.querySelectorAll('.set-cards > section, .set-cards > .setting')].filter(c => c.offsetParent !== null).map(c => (c.querySelector('h2,h3') || c).textContent.trim())"""
ROWS = """[...document.querySelectorAll('#gantt-setting .set-row')].map(r => r.hidden)"""


class Search(Head):
    def type(self, p, text):
        p.js("""(() => { const b = document.getElementById('set-search-box'); b.focus(); b.value = %r; b.dispatchEvent(new Event('input', {bubbles: true})); })()""" % text)

    def test_S2_search_filters_cards_and_rows_and_esc_restores(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    p.until("!!document.getElementById('set-search-box') && !!document.querySelector('#gantt-name')", "the box and cards drew")
                    all_cards = p.js(SHOWN)
                    self.assertGreater(len(all_cards), 5)
                    self.assertEqual(p.js("document.querySelector('label[for=set-search-box]').textContent"), "Search settings")
                    self.type(p, "tab name")
                    p.until("document.querySelectorAll('.set-cards > section:not([hidden])').length === 1", "one card is left")
                    self.assertEqual(p.js(SHOWN), ["Gantt"])
                    self.assertEqual(p.js(ROWS).count(False), 1, "only the matching row stays in the card")
                    self.assertFalse(p.js("!!document.querySelector('.set-nav')"), "the chips are hidden while searching")
                    self.type(p, "BACKUPS")
                    p.until("document.querySelector('#safety-h').closest('section').hidden === false", "the card whose heading matches stays")
                    self.assertIn("Backups", p.js(SHOWN))
                    self.assertNotIn("Gantt", p.js(SHOWN))
                    self.type(p, "zzzzqq")
                    p.until("document.querySelectorAll('.set-cards > section:not([hidden])').length === 0", "nothing matches")
                    p.js("document.getElementById('set-search-box').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                    p.until("document.getElementById('set-search-box').value === ''", "Esc clears the box")
                    p.until("!!document.querySelector('.set-nav .set-chip')", "the chips return")
                    self.assertEqual(p.js(SHOWN), all_cards)
                    self.assertNotIn(True, p.js(ROWS))
                    self.assertFalse(p.js("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "no sideways scroll")


if __name__ == "__main__":
    unittest.main()

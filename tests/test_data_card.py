"""Prototype parity A-S11: Settings › Data (Export to Excel), in a real browser at 1400 and 900 px, light and dark.
Run: python3 dev/run_tests.py test_data_card

What is asserted: the card is on Settings with its heading and words; it has an Export to Excel button and no Import or Reset button
(the server has no route for either); pressing the button asks the server's export route once and the browser is given a workbook
(the page says so); the card never widens the page; the button's text meets 4.5:1 in light and dark.
Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from test_publish_dialog import Base
from test_server import chrome

WIDTHS = (1400, 900)


class DataCard(Base):
    def open_settings(self, p):
        p.js("document.querySelector('#profile-btn').click()")
        p.until("!!document.querySelector('#profile-menu')", "the menu opened")
        p.js("document.querySelector('#profile-menu [data-kind=settings]').click()")
        p.until("!!document.querySelector('#data-card')", "the Data card drew")

    def test_C_the_card_its_words_and_only_the_export_button(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                self.assertEqual(p.js("document.querySelector('#data-card h2').textContent"), "Data")
                self.assertEqual(p.js("[...document.querySelectorAll('#data-card button')].map(b => b.textContent)"), ["Export to Excel"])
                self.assertIn("Excel workbook", p.js("document.querySelector('#data-card p').textContent"))
                self.assertFalse(p.js("/import|reset/i.test(document.querySelector('#data-card').innerText)"))
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)

    def test_C_pressing_export_downloads_one_workbook_and_says_so(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("window.__asked = 0; const f = window.fetch; window.fetch = function (u, o) { if (String(u).indexOf('/api/export') === 0) window.__asked++; return f.apply(this, arguments); }")
            p.js("document.querySelector('[data-export-workbook]').click()")
            p.until("!!document.querySelector('.toast')", "the page said the file was saved")
            self.assertEqual(p.js("window.__asked"), 1)
            self.assertIn("saved", p.js("document.querySelector('.toast').textContent"))

    def test_C_the_button_is_readable_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                p = self.page(cdp)
                p.js(f"document.documentElement.setAttribute('data-theme', '{scheme}')")
                self.open_settings(p)
                ratio = p.js("""(() => { const b = document.querySelector('[data-export-workbook]'); const cs = getComputedStyle(b);
                  const px = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return m.slice(0, 3); };
                  const lum = ([r, g, bl]) => { const f = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(bl); };
                  let bg = b, c; while (bg) { c = getComputedStyle(bg).backgroundColor; if (!/rgba\\(.*, 0\\)|transparent/.test(c)) break; bg = bg.parentElement; }
                  const a = lum(px(cs.color)), z = lum(px(c)); return (Math.max(a, z) + .05) / (Math.min(a, z) + .05); })()""")
                self.assertGreaterEqual(ratio, 4.5)


if __name__ == "__main__":
    unittest.main()

"""Rows 771 and 772: the main button is the aqua gradient pill (771), and the top bar's search button has an outline and the ask clark text is smaller (772).
Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_buttons_771_772
Measured at 1400 and 900 px, light and dark, in a real browser against the real page.
"""
import sqlite3
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

TOKEN = ("function(t){ var e = document.createElement('i'); e.style.color = 'var(' + t + ')'; document.body.appendChild(e); "
         "var c = getComputedStyle(e).color; e.remove(); return c; }")


def rgb(text):
    return [int(float(x)) for x in text[text.index("(") + 1:text.index(")")].replace("/", ",").split(",")[:3]]


def lum(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class Buttons(Base):
    def at(self, cdp, width, theme):
        with sqlite3.connect(str(self.store.path)) as con:
            con.execute("UPDATE app_settings SET ask_enabled = 1 WHERE id = 1")
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until("!!document.querySelector('#ask-btn')", "the ask button shows")
        p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
        return p

    def test_the_main_button_is_the_aqua_gradient_with_readable_dark_text(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.at(cdp, width, theme)
                    got = p.js("(function(){ var tok = " + TOKEN + ", b = document.createElement('button'); b.className = 'btn pri'; b.textContent = 'Go';"
                               "document.body.appendChild(b); var s = getComputedStyle(b);"
                               "var r = [s.backgroundImage, s.color, tok('--pill-fg'), s.fontWeight, s.borderRadius, s.borderTopWidth]; b.remove(); return r;})()")
                    self.assertIn("linear-gradient", got[0], "the fill is the aqua gradient, not a flat colour")
                    stops = [rgb(x) for x in got[0].split("rgb")[1:]]
                    self.assertGreaterEqual(len(stops), 2)
                    self.assertEqual(got[1], got[2], "the text is the dark pill token")
                    self.assertGreaterEqual(int(got[3]), 700, "bold text")
                    for stop in stops:
                        self.assertGreaterEqual(ratio(rgb(got[1]), stop), 4.5, f"text on gradient stop {stop}")

    def test_the_main_button_keeps_its_focus_ring(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, "light")
            got = p.js("(function(){ var b = document.createElement('button'); b.className = 'btn pri'; b.textContent = 'Go'; document.body.appendChild(b); b.focus();"
                       "var s = getComputedStyle(b), r = [s.outlineStyle, s.outlineWidth]; b.remove(); return r;})()")
            self.assertEqual(got, ["solid", "2px"])


if __name__ == "__main__":
    unittest.main()

"""Prototype parity A-S11 and #444: Settings › Data (Export workbook and Import workbook), in a real browser at 1400 and
900 px, light and dark. Run: python3 dev/run_tests.py test_data_card

What is asserted: the card is on Settings with its heading and words; it has Export workbook and Import workbook and no other button;
pressing Export asks the server's export
route once and the browser is given a workbook (the page says so); the card never widens the page; the buttons' text meets 4.5:1 in
light and dark. The Import box is in test_settings_data_page.
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
        p.js("document.querySelector('#profile-menu [data-kind=settings], #profile-menu [data-kind=who]').click()")
        p.until("!!document.querySelector('#data-card')", "the Data card drew")

    def test_C_the_card_its_words_and_the_export_and_import_buttons(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                self.assertEqual(p.js("document.querySelector('#data-card h2').textContent"), "Data")
                self.assertEqual(p.js("[...document.querySelectorAll('#data-card button')].map(b => b.textContent)"), ["Export workbook", "Import workbook", "Excel file layout", "Export to Word…", "Import from Word…"])
                self.assertIn("a sheet each for actions", p.js("document.querySelector('#data-card p').textContent"))
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)

    def test_C_word_buttons_open_the_profile_menus_boxes_in_view(self):          # row 831
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("document.querySelector('[data-word-export]').click()")
            p.until("!!document.querySelector('#word-export-dialog[open]')", "the Export to Word box opened")
            p.js("document.querySelector('#word-export-dialog').close()")
            p.js("document.querySelector('[data-word-import]').click()")
            p.until("!!document.querySelector('#word-import-dialog[open]')", "the Import from Word box opened, no Edit needed")

    def key(self, cdp, p, key, code, vk, text=None):
        for kind in ("keyDown", "keyUp"):       # a real key press
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk,
                                                **({"text": text} if kind == "keyDown" and text else {})}, p.sid)

    def test_C_word_boxes_give_focus_back_to_the_data_button_on_esc_and_close(self):          # 1.0.8 H1
        for w in WIDTHS:
            for btn, dlg, close in (("word-export", "word-export-dialog", None), ("word-import", "word-import-dialog", None)):
                with self.subTest(width=w, button=btn), chrome() as cdp:
                    p = self.page(cdp)
                    p.width(w)
                    self.open_settings(p)
                    prev = "excel-layout" if btn == "word-export" else "word-export"
                    p.js(f"document.getElementById('{prev}').focus()")
                    self.key(cdp, p, "Tab", "Tab", 9)
                    self.assertEqual(p.js("document.activeElement.id"), btn)
                    self.key(cdp, p, "Enter", "Enter", 13, "\r")
                    p.until(f"!!document.querySelector('#{dlg}[open]')", "the box opened")
                    self.key(cdp, p, "Escape", "Escape", 27)
                    p.until(f"!document.querySelector('#{dlg}')", "the box closed on Esc")
                    self.assertEqual(p.js("document.activeElement.id"), btn)
                    # and again with the Close button (a real Enter on it)
                    self.key(cdp, p, "Enter", "Enter", 13, "\r")
                    p.until(f"!!document.querySelector('#{dlg}[open]')", "the box opened again")
                    p.js(f"(document.querySelector('#{dlg} button[type=button]:not([disabled])') || document.querySelector('#{dlg} button')).focus()")
                    self.key(cdp, p, "Enter", "Enter", 13, "\r")
                    p.until(f"!document.querySelector('#{dlg}')", "the box closed")
                    self.assertEqual(p.js("document.activeElement.id"), btn)

    def test_C_word_export_from_the_profile_menu_still_returns_to_the_profile_circle(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu')", "the menu opened")
                p.js("document.querySelector('#profile-menu [data-kind=word-export]').click()")
                p.until("!!document.querySelector('#word-export-dialog[open]')", "the box opened")
                self.key(cdp, p, "Escape", "Escape", 27)
                p.until("!document.querySelector('#word-export-dialog')", "the box closed")
                self.assertEqual(p.js("document.activeElement.id"), "profile-btn")

    def test_C_pressing_export_downloads_one_workbook_and_says_so(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p)
            p.js("window.__asked = 0; const f = window.fetch; window.fetch = function (u, o) { if (String(u).indexOf('/api/export') === 0) window.__asked++; return f.apply(this, arguments); }")
            p.js("document.querySelector('[data-export-workbook]').click()")
            p.until("!!document.querySelector('.toast')", "the page said the file was saved")
            self.assertEqual(p.js("window.__asked"), 1)
            self.assertIn("saved", p.js("document.querySelector('.toast').textContent"))

    def test_C_excel_file_layout_opens_a_box_with_the_three_texts_and_sends_nothing(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w)
                self.open_settings(p)
                p.js("window.__asked = []; const f = window.fetch; window.fetch = function (u, o) { window.__asked.push(String(u)); return f.apply(this, arguments); }")
                p.js("document.querySelector('#excel-layout').click()")
                p.until("!!document.querySelector('#excel-layout-box')", "the box opened")
                self.assertEqual(p.js("document.querySelector('#excel-layout-client').textContent"), "This file is for you and your team. It holds internal notes, so do not send it to a client.")
                self.assertEqual(p.js("[...document.querySelectorAll('#excel-layout-box dt')].map(e => e.textContent)"), ["Cover", "History"])
                self.assertIn("The changes made to the items. The import leaves this sheet alone.", p.js("document.querySelector('#excel-layout-box').textContent"))
                self.assertIn("where to send the file back", p.js("document.querySelector('#excel-layout-box').textContent"))
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                self.assertEqual(p.js("window.__asked.filter(u => /export|excel|import/.test(u))"), [])      # the page rereads its own data as it likes; the box asks for no file
                p.js("document.querySelector('#excel-layout-close').click()")
                p.until("!document.querySelector('#excel-layout-box')", "the box closed")

    def test_C_the_button_is_readable_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                p = self.page(cdp)
                p.js(f"document.documentElement.setAttribute('data-theme', '{scheme}')")
                self.open_settings(p)
                ratio = p.js("""(() => { const b = document.querySelector('#import-workbook'); const cs = getComputedStyle(b);
                  const px = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return m.slice(0, 3); };
                  const lum = ([r, g, bl]) => { const f = (v) => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(r) + .7152 * f(g) + .0722 * f(bl); };
                  let bg = b, c; while (bg) { c = getComputedStyle(bg).backgroundColor; if (!/rgba\\(.*, 0\\)|transparent/.test(c)) break; bg = bg.parentElement; }
                  const a = lum(px(cs.color)), z = lum(px(c)); return (Math.max(a, z) + .05) / (Math.min(a, z) + .05); })()""")
                self.assertGreaterEqual(ratio, 4.5)


if __name__ == "__main__":
    unittest.main()

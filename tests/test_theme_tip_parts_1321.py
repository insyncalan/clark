"""Row 1321 slice 2: the tool tip of a status tile carries its parts as real elements in the Classic Theme (kind 600, dots muted, Overdue red 600).

Run: python3 dev/run_tests.py test_theme_tip_parts_1321
Real Work items page (demo data, fictional), Chrome, 1400 then 900. Cards draws no parts and keeps its one-string tip. Fails, never skips, without Chrome.
"""
import json
import time
import unittest

from test_server import chrome
from test_work_board_page import Base

from clark import page

NAME = "prototype-2.0"
FIND = """(() => { const all = [...document.querySelectorAll('[data-tip]')].filter((e) => e.matches('.ico, .cell-pick, .ucd-item, .ucf-item'));
  const pick = all.find((e) => /Overdue/.test(e.getAttribute('data-tip'))) || all[0]; if (!pick) return JSON.stringify({found: false});
  pick.scrollIntoView({block: 'center'}); const r = pick.getBoundingClientRect(); return JSON.stringify({found: true, late: /Overdue/.test(pick.getAttribute('data-tip')),
    xy: [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)], parts: !!pick.querySelector(':scope > .tip-parts'), n: all.length}); })()"""
HOVER = """(() => { const h = document.elementFromPoint(%d, %d).closest('[data-tip]'); if (!h) return 'null'; const p = h.querySelector(':scope > .tip-parts');
  if (!p) return JSON.stringify({parts: false}); const cs = (e) => getComputedStyle(e); const k = p.querySelector('.tp-kind'), d = p.querySelector('.tp-dot'), l = p.querySelector('.tp-late');
  return JSON.stringify({parts: true, text: p.textContent, tip: h.getAttribute('data-tip'), hidden: p.getAttribute('aria-hidden'), shown: cs(p).display, after: cs(h, '::after').content,
    card: [cs(p).backgroundColor, cs(p).borderTopWidth, cs(p).borderTopLeftRadius, cs(p).fontWeight], shadow: cs(p).boxShadow, kind: cs(k).fontWeight, dot: cs(d).color, late: l ? [cs(l).color, cs(l).fontWeight] : null, word: cs(p.querySelector('.tp-word') || k).fontWeight}); })()"""


class Parts(Base):
    def run_page(self, theme, width):
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=theme)
        with chrome() as cdp:
            sid = self.visit(cdp, width=width, hash_="#work&p=ABC", wait_for="#work")
            time.sleep(0.4)
            got = json.loads(cdp.js(FIND, sid))
            self.assertTrue(got["found"], "a status tile with a tip is on the Work items page")
            x, y = got["xy"]
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
            time.sleep(0.4)
            return got, json.loads(cdp.js(HOVER % (x, y), sid))

    def test_classic_tip_draws_its_parts(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got, h = self.run_page(NAME, width)
                self.assertTrue(got["late"], "the demo data has an Overdue item")
                self.assertTrue(h["parts"])
                self.assertEqual(h["text"], h["tip"])
                self.assertEqual(h["hidden"], "true")
                self.assertEqual(h["shown"], "block")
                self.assertIn(h["after"], ("none", "normal"))      # no pseudo-element is made
                self.assertEqual(h["card"], ["rgb(255, 255, 255)", "1px", "9px", "500"])
                self.assertEqual(h["shadow"], "rgba(14, 36, 48, 0.12) 0px 6px 18px 0px")   # ruling, Row 1321
                self.assertEqual(h["kind"], "600")
                self.assertEqual(h["late"][1], "600")
                self.assertNotEqual(h["late"][0], h["dot"])
                self.assertNotEqual(h["dot"], "rgb(29, 36, 51)")

    def test_cards_keeps_one_string(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                got, h = self.run_page(None, width)
                self.assertFalse(got["parts"])
                self.assertFalse(h["parts"])


if __name__ == "__main__":
    unittest.main()

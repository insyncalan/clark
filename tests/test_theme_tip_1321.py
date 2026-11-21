"""Row 1321: the tool tip is a light card in the Classic Theme and the global tip (navy block) under Cards.

Run: python3 dev/run_tests.py test_theme_tip_1321
Real Work items page (demo data, fictional), Chrome computed style of the ::after of a hovered [data-tip] element and of a .fi-btn tip, at 1400 then
900, light and dark. Not built here: the per-part weights and the red "Overdue" (a tip is one plain string; see the row's report). Fails, never skips, without Chrome.
"""
import json
import re
import time
import unittest

from _paths import ROOT
from test_server import chrome
from test_work_board_page import Base

from clark import page

NAME = "prototype-2.0"
RULES = ROOT / "src" / "clark" / "themes" / NAME / "rules.css"
SHADOW_CSS = "box-shadow: 0 6px 18px rgba(14,36,48,.12);"      # ruling, Row 1321
SHADOW = "rgba(14, 36, 48, 0.12) 0px 6px 18px 0px"
WANT = {"light": ("rgb(255, 255, 255)", "rgb(217, 224, 239)", "rgb(29, 36, 51)"),      # --surface, --grey-200 (#D9E0EF, the ticket's hairline), --text
        "dark": ("rgb(18, 28, 40)", "rgb(43, 56, 80)", "rgb(230, 235, 245)")}
PROBE = """(() => { const t = document.querySelector('[data-tip]:not([disabled])'); const b = document.createElement('button'); b.className = 'fi-btn'; b.setAttribute('data-tip', 'Crop');
  document.body.appendChild(b); const out = {}; const read = (e) => { const c = getComputedStyle(e, '::after');
    return [c.backgroundColor, c.borderTopWidth, c.borderTopColor, c.borderTopLeftRadius, c.paddingTop, c.paddingLeft, c.fontSize, c.fontWeight, c.color, c.boxShadow, c.content]; };
  out.fi = read(b); b.remove(); out.found = !!t; if (t) { t.scrollIntoView({block: 'center'}); const r = t.getBoundingClientRect(); out.xy = [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)]; }
  return JSON.stringify(out); })()"""
HOVER = """(() => { const e = document.elementFromPoint(%d, %d).closest('[data-tip]'); if (!e) return 'null'; const c = getComputedStyle(e, '::after');
  return JSON.stringify([c.backgroundColor, c.borderTopWidth, c.borderTopColor, c.borderTopLeftRadius, c.paddingTop, c.paddingLeft, c.fontSize, c.fontWeight, c.color, c.boxShadow, c.content]); })()"""


class Source(unittest.TestCase):
    def test_block_is_before_row_1393_and_has_no_colour_literal(self):
        t = RULES.read_text(encoding="utf-8")
        self.assertLess(t.index("/* Row 1321"), t.index("/* Row 1393"))
        b = t[t.index("/* Row 1321"):t.index("/* Row 1393")]
        rules = re.sub(r"/\*.*?\*/", "", b, flags=re.S)
        self.assertEqual(rules.count(SHADOW_CSS), 2, "both tip rules carry the ruled shadow")
        self.assertNotIn("var(--shadow)", rules)
        self.assertNotRegex(rules.replace(SHADOW_CSS, ""), r"#[0-9a-fA-F]{3,8}\b|rgba?\(")
        self.assertLess(len(t.encode()), 131072)

    def test_cards_page_does_not_carry_it(self):
        self.assertNotIn("Row 1321", page.page_html(branding=page.NO_BRAND))


class Computed(Base):
    def run_page(self, theme, width, scheme):
        self.s.httpd.page_html = lambda: page.page_html(branding=page.NO_BRAND, theme=theme)
        with chrome() as cdp:
            sid = self.visit(cdp, width=width, hash_="#work&p=ABC", wait_for="#work")
            cdp.js("document.documentElement.setAttribute('data-theme', %r)" % scheme, sid)
            time.sleep(0.4)
            got = json.loads(cdp.js(PROBE, sid))
            self.assertTrue(got["found"], "a data-tip element is on the Work items page")
            x, y = got["xy"]
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
            time.sleep(0.4)
            hov = cdp.js(HOVER % (x, y), sid)
            self.assertNotEqual(hov, "null")
            return got["fi"], json.loads(hov)

    def test_classic_tip_is_a_light_card_in_both_widths_and_schemes(self):
        for width in (1400, 900):
            for scheme, (bg, line, ink) in WANT.items():
                with self.subTest(width=width, scheme=scheme):
                    fi, hov = self.run_page(NAME, width, scheme)
                    for name, v in (("hover", hov), ("fi-btn", fi)):
                        self.assertEqual(v[:4], [bg, "1px", line, "9px"], name)
                        self.assertEqual(v[4:9], ["7px", "11px", "12.5px", "500", ink], name)
                        self.assertEqual(v[9], SHADOW, name)

    def test_cards_tip_is_unchanged(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    fi, hov = self.run_page(None, width, scheme)
                    self.assertEqual(hov[1], "0px")
                    self.assertEqual(hov[3], "4px")
                    self.assertEqual(hov[9], "none")
                    self.assertEqual(fi[1], "0px")
                    self.assertEqual(fi[4:6], ["3px", "8px"])


if __name__ == "__main__":
    unittest.main()

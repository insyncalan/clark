"""Row 1256 (PR A3): the overdue look on the peek's date chip. The date text is red; the chip keeps its normal (flat, borderless) look and fill; the sub-word
"overdue 2 days" is a bold red-tint pill at the caption size (13 px; the page never goes below 13 px); hover is a soft fill with no border change.

Run: python3 dev/run_tests.py test_peek_overdue_1256   (real browser, 1400 and 900 px, demo data, fixed date 28-10-2026)
"""
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_peek_card import CardBrowser  # noqa: E402
from test_peek_chips_1180 import Chips, OVERDUE  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import hover  # noqa: E402

CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")

PROBE = """(() => { const c = document.querySelector('#peek .pk-chips [data-row=due]'); const v = c.querySelector('.pkc-v'), s = c.querySelector('.pkc-sub');
  const cs = getComputedStyle(c), ss = s ? getComputedStyle(s) : null;
  const probe = (name, prop) => { const e = document.createElement('i'); e.style[prop] = 'var(' + name + ')'; document.body.appendChild(e); const x = getComputedStyle(e)[prop]; e.remove(); return x; };
  return { dateColour: getComputedStyle(v).color, border: cs.borderTopWidth, fill: cs.backgroundColor, red: probe('--status-red-text', 'color'), redTint: probe('--status-red-tint', 'backgroundColor'),
    grey200: probe('--grey-200', 'borderTopColor'), surface: probe('--surface', 'backgroundColor'),
    sub: s ? { text: s.textContent.trim(), size: ss.fontSize, weight: ss.fontWeight, colour: ss.color, bg: ss.backgroundColor, radius: ss.borderTopLeftRadius } : null }; })()"""


class Overdue(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page
    show_item = CardBrowser.show_item
    open_item = Chips.open_item
    with_overdue = Chips.with_overdue

    def test_overdue_look(self):
        for width in (1400, 900):
            with self.with_overdue(), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    with self.subTest(f"{width} {mode}"):
                        self.open_item(cdp, sid, OVERDUE, view=mode == "view")
                        g = cdp.js(PROBE, sid)
                        self.assertEqual(g["dateColour"], g["red"], "the date text is red")
                        self.assertEqual(g["border"], "0px", "the flat chip row has no border round the chip")
                        self.assertEqual(g["fill"], g["surface"], "the chip keeps its normal fill")
                        sub = g["sub"]
                        self.assertEqual(sub["text"], "overdue 2 days")
                        self.assertEqual((sub["size"], sub["weight"]), ("13px", "700"))
                        self.assertEqual(sub["colour"], g["red"])
                        self.assertEqual(sub["bg"], g["redTint"], "a red-tint pill")
                        self.assertNotEqual(sub["radius"], "0px")

    def test_hover_is_a_soft_fill_and_the_border_does_not_change(self):
        for width in (1400, 900):
            with self.with_overdue(), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                self.edit_mode(cdp, sid)
                self.open_item(cdp, sid, OVERDUE)
                before = cdp.js(PROBE, sid)
                hover(cdp, sid, "#peek .pk-chips [data-row=due]")
                self.assertTrue(wait(lambda: cdp.js(PROBE, sid)["fill"] != before["fill"]), f"{width}: hover fills the chip")
                after = cdp.js(PROBE, sid)
                self.assertEqual(after["border"], before["border"], f"{width}: hover leaves the border alone")

    def test_the_rules_in_the_source(self):
        self.assertNotIn(".pkc.late { border-color", CSS, "no red border or fill on the chip")


if __name__ == "__main__":
    unittest.main()

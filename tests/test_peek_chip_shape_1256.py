"""Row 1256 (A1): the peek's chip row is flat. No pill border or radius, a 1px left divider between chips (none on the first),
no gap, and the chips grow to fill the row (the approved mockup, plan repo team-friday-mockups, peek-redesign).

Run: python3 dev/run_tests.py test_peek_chip_shape_1256

Computed styles read in a real browser at 1400 and 900 px with the demo data (fictional), in Edit (buttons) and View (read only).
"""
import unittest

import test_peek as tp  # noqa: E402
import test_peek_card as _test_peek_card
import test_peek_chips_1180 as c1180  # noqa: E402  (helpers borrowed; its tests stay in its own file)
from test_server import chrome  # noqa: E402

SHAPE = """(() => { const row = document.querySelector('#peek .pk-chips'); const kids = [...row.children].filter(c => c.dataset.row);
  const rs = getComputedStyle(row), rr = row.getBoundingClientRect();
  return { gap: rs.columnGap + ' ' + rs.rowGap, rowL: rr.left, rowR: rr.right,
    chips: kids.map(c => { const s = getComputedStyle(c), r = c.getBoundingClientRect(), b = c.querySelector('button');
      return { key: c.dataset.row, top: s.borderTopWidth, right: s.borderRightWidth, bottom: s.borderBottomWidth, left: s.borderLeftWidth,
        radius: [s.borderTopLeftRadius, s.borderTopRightRadius, s.borderBottomRightRadius, s.borderBottomLeftRadius],
        btnRadius: b ? getComputedStyle(b).borderTopLeftRadius : '0px', l: r.left, r: r.right, t: r.top }; }) }; })()"""


class ChipShape(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page
    show_item = _test_peek_card.CardBrowser.show_item
    open_item = c1180.Chips.open_item

    def test_chips_are_flat_with_a_left_divider_and_fill_the_row(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    with self.subTest(f"{width} {mode}"):
                        self.open_item(cdp, sid, item, view=mode == "view")
                        got = cdp.js(SHAPE, sid)
                        chips = got["chips"]
                        self.assertGreaterEqual(len(chips), 2)
                        self.assertEqual(set(got["gap"].split()) - {"0px", "normal"}, set(), "no gap")
                        for i, c in enumerate(chips):
                            k = c["key"]
                            self.assertEqual((c["top"], c["right"], c["bottom"]), ("0px", "0px", "0px"), f"{k}: no pill border")
                            self.assertEqual(c["left"], "0px" if i == 0 else "1px", f"{k}: divider on all but the first")
                            self.assertEqual(set(c["radius"]), {"0px"}, f"{k}: no radius")
                            self.assertEqual(c["btnRadius"], "0px", f"{k}: the button has no radius either")
                        line = [c for c in chips if abs(c["t"] - chips[0]["t"]) < 2]
                        for a, b in zip(line, line[1:]):
                            self.assertLessEqual(abs(b["l"] - a["r"]), 1, "chips touch")
                        self.assertLessEqual(abs(line[0]["l"] - got["rowL"]), 1, "starts at the row's edge")
                        self.assertLessEqual(abs(line[-1]["r"] - got["rowR"]), 1, "chips grow to fill the row")


if __name__ == "__main__":
    unittest.main()

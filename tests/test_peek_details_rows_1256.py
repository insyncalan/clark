"""Row 1256-B2 (ticket item 2c): the peek's Details rows are a plain list. A 130px label and a 1fr value, a 2px by 12px gap, rows at least 36px tall,
no borders, the label 14px in the muted text token, the icon 16px. The four property chips above are not touched.

Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_peek_details_rows_1256

Computed styles and boxes read in a real browser at 1400 and 900 px with the demo data (fictional), in Edit and View, light and dark.
"""
import unittest

import test_peek as tp  # noqa: E402
import test_peek_card as _test_peek_card
import test_peek_chips_1180 as c1180  # noqa: E402
from test_server import chrome, wait  # noqa: E402

READ = """(() => { const body = document.querySelector('#peek [data-pk-details-rows]'); if (!body) return null;
  const probe = (name) => { const e = document.createElement('i'); e.style.color = 'var(' + name + ')'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; };
  const rows = [...body.querySelectorAll('.pk-fields > .pk-row')].map(r => { const s = getComputedStyle(r), rb = r.getBoundingClientRect(), dt = r.querySelector('dt'), dd = r.querySelector('dd');
    const ds = dt ? getComputedStyle(dt) : null, ic = r.querySelector('.pk-rowic svg');
    return { name: dt ? dt.textContent.trim() : '(client line)', cols: s.gridTemplateColumns.split(' ').length, gap: s.columnGap + ' ' + s.rowGap, h: rb.height,
      minH: s.minHeight, borders: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth],
      labelW: dt ? dt.getBoundingClientRect().width : null, valueL: dd.getBoundingClientRect().left, labelL: dt ? dt.getBoundingClientRect().left : null, rowR: rb.right, valueR: dd.getBoundingClientRect().right,
      labelSize: ds ? ds.fontSize : null, labelColour: ds ? ds.color : null, icon: ic ? [ic.getBoundingClientRect().width, ic.getBoundingClientRect().height] : null }; });
  return { rows, muted: probe('--text-muted'), tiles: document.querySelectorAll('#peek .pk-details-body [data-row] .pk-val').length }; })()"""

OPEN = """(() => { const b = document.querySelector('#peek [data-pk-details-rows]'); if (!b) { const h = document.querySelector('#peek [data-pk-details]'); if (h) h.click(); return false; } return true; })()"""


class DetailsRows(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page
    show_item = _test_peek_card.CardBrowser.show_item
    open_item = c1180.Chips.open_item

    def read(self, cdp, sid):
        self.assertTrue(wait(lambda: cdp.js(OPEN, sid)), "Details is open")
        return cdp.js(READ, sid)

    def test_rows_are_a_130px_label_and_a_value_36px_tall_without_borders(self):
        for width in (1400, 900):
            for dark in (False, True):
                with chrome() as cdp:
                    s, sid = self.load_page(cdp, width)
                    if dark:
                        cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
                    item = self.ids_on_page(cdp, sid)[0]
                    for mode in ("view", "edit"):
                        if mode == "edit":
                            self.edit_mode(cdp, sid)
                        with self.subTest(width=width, dark=dark, mode=mode):
                            self.open_item(cdp, sid, item, view=mode == "view")
                            got = self.read(cdp, sid)
                            self.assertGreaterEqual(len(got["rows"]), 2, got)
                            for r in got["rows"]:
                                n = r["name"]
                                self.assertEqual(r["borders"], ["0px"] * 4, f"{n}: no borders")
                                self.assertGreaterEqual(r["h"], 36, f"{n}: at least 36px tall")
                                self.assertEqual(r["minH"], "36px", n)
                                self.assertEqual(r["gap"], "12px 2px", f"{n}: column gap 12, row gap 2")
                                if r["labelW"] is None:
                                    continue          # the client line has no label
                                self.assertEqual(r["cols"], 2, n)
                                self.assertAlmostEqual(r["valueL"] - r["labelL"], 142, delta=1, msg=f"{n}: 130px label plus the 12px gap")
                                self.assertEqual(r["labelSize"], "14px", n)
                                self.assertEqual(r["labelColour"], got["muted"], f"{n}: the muted text token")
                                if r["icon"]:
                                    self.assertEqual(r["icon"], [16, 16], f"{n}: icon 16px")
                            self.assertEqual(got["tiles"], 0, "no property tile inside Details")

    def test_the_value_takes_the_rest_of_the_row(self):
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            item = self.ids_on_page(cdp, sid)[0]
            self.edit_mode(cdp, sid)
            self.open_item(cdp, sid, item, view=False)
            got = self.read(cdp, sid)
            for r in got["rows"]:
                if r["labelW"] is not None:
                    self.assertLessEqual(abs(r["rowR"] - r["valueR"]), 1, f"{r['name']}: the value runs to the row's edge")


if __name__ == "__main__":
    unittest.main()

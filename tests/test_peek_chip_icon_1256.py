"""Item 1256 (peek redesign, PR A2): the chip's lead icon is 20 px, the chevron sits at the cell's right edge, the words are 15 px weight 400.

Run: python3 dev/run_tests.py test_peek_chip_icon_1256

Computed styles in a real browser at 1400 and 900 px (demo data, fictional), on the chips in `.pk-chips > [data-row]`.
"""
import unittest

from _paths import ROOT  # noqa: F401

from test_server import chrome  # noqa: E402
import test_peek_chips_1180 as _test_peek_chips_1180

READ = """(() => { const p = document.querySelector('#peek'); const out = {};
  for (const c of p.querySelectorAll('.pk-chips > [data-row]')) {
    const svgs = [...c.querySelectorAll('svg[data-icn]')], lead = svgs[0], car = svgs[svgs.length - 1], v = c.querySelector('.pkc-v');
    const lb = lead.getBoundingClientRect(), cb = car.getBoundingClientRect(), b = c.getBoundingClientRect(), cs = getComputedStyle(v || c);
    out[c.dataset.row] = { lead: [lb.width, lb.height], car: cb.width, gapRight: b.right - cb.right, size: cs.fontSize, weight: cs.fontWeight, carName: car.dataset.icn }; }
  return out; })()"""


class ChipIcon(_test_peek_chips_1180.Chips):
    def test_icon_20_chevron_at_the_right_edge_text_15_regular(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                self.edit_mode(cdp, sid)
                self.open_item(cdp, sid, item)
                got = cdp.js(READ, sid)
                self.assertTrue(got, width)
                for k, c in got.items():
                    with self.subTest(f"{width} {k}"):
                        self.assertEqual(c["lead"], [20, 20], "lead icon 20 px")
                        self.assertEqual(c["carName"], "chevdown")
                        self.assertEqual(c["car"], 12, "chevron stays 12 px")
                        self.assertLessEqual(c["gapRight"], 14, "chevron at the cell's right edge (border plus padding only)")
                        self.assertEqual(c["size"], "15px")
                        self.assertEqual(c["weight"], "400")


# only the new test runs here; the inherited ones belong to test_peek_chips_1180
for _n in [n for n in dir(_test_peek_chips_1180.Chips) if n.startswith("test_")]:
    setattr(ChipIcon, _n, None)

if __name__ == "__main__":
    unittest.main()

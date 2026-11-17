"""Row 1280: exact spacing and contrast of the Settings menu, in a real browser at 1400 and 900 px, light and dark.
Run: python3 dev/run_tests.py test_settings_menu_1280_pins

The sibling test keeps loose bounds; these pin the measured values so a bound that moved by one step goes red.
"""
import unittest

from test_publish_dialog import Base
from test_server import chrome, wait  # noqa: F401  (the harness: this file drives Chrome, so the tier reader sees it)
import test_settings_menu_1280 as base
from test_settings_menu_1280 import NAME
from test_settings_head import ratio, rgb



class SettingsMenu1280Pins(Base):
    open_settings = base.SettingsMenu1280.open_settings
    each = base.SettingsMenu1280.each

    def measure(self, p):
        rows = p.js(f"""[...document.querySelectorAll('.set-nav .set-group')].map(g => {{ const n = g.querySelector('.set-group-name').getBoundingClientRect();
            const c = [...g.querySelectorAll('.set-chip')].map(b => b.getBoundingClientRect());
            return [n.top, n.bottom, c.map(r => [r.top, r.bottom]), g.querySelector('.set-group-name').textContent]; }})""")
        ground = p.js("getComputedStyle(document.querySelector('.set-bar')).backgroundColor")
        colors = p.js(f"{NAME}.map(e => getComputedStyle(e).color)")
        return rows, ground, colors

    def test_C_the_measured_spacing_and_contrast_are_pinned(self):
        def body(p, w, mode):
            rows, ground, colors = self.measure(p)
            for c in colors:
                self.assertGreaterEqual(ratio(rgb(c), rgb(ground)), 6.5, f"{mode}: a heading is clearly muted but readable on the bar")
            for (_, _, a, _), (top, _, _, _) in zip(rows[:-1], rows[1:]):
                self.assertGreaterEqual(top - a[-1][1], 24, "a heading has at least 24 px above it (28 at 1400, 24 at 900)")
            for top, bottom, chips, name in rows:
                if name != "Advanced":
                    self.assertAlmostEqual(chips[0][0], bottom, delta=0.5, msg="the first page starts right under its heading")
                for a, b in zip(chips, chips[1:]):
                    self.assertAlmostEqual(b[0], a[1], delta=0.5, msg="the pages of a group touch exactly")
        self.each(body)

    def test_D_the_heading_type_and_the_marker_inset_are_pinned(self):
        def body(p, w, mode):
            got = p.js(f"""{NAME}.map(e => {{ const s = getComputedStyle(e); return [s.fontSize, s.letterSpacing, s.paddingBottom, s.paddingLeft, s.paddingTop]; }})""")
            for size, spacing, below, left, above in got:
                self.assertEqual(size, "13px", "the heading is the 13 px caption size")
                self.assertAlmostEqual(float(spacing[:-2]), 0.78, delta=0.01, msg="capitals are spaced .06em, 0.78 px at 13 px")
                self.assertEqual((below, left, above), ("4px", "12px", "0px"), "a heading has 4 px under it and 12 px at the left")
            mark = p.js("""(() => { const c = document.querySelector('.set-nav .set-chip[aria-current]'), s = getComputedStyle(c, '::before'); const r = c.getBoundingClientRect();
                return [s.top, s.bottom, s.height, r.height]; })()""")
            self.assertEqual(mark[0], "4px", "the open-page bar starts 4 px under the top of its row")
            self.assertEqual(mark[1], "4px", "the open-page bar ends 4 px above the foot of its row")
            self.assertAlmostEqual(float(mark[2][:-2]), mark[3] - 8, delta=0.5, msg="the bar is the row less 4 px at each end")
        self.each(body)

if __name__ == "__main__":
    unittest.main()

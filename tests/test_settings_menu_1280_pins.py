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

if __name__ == "__main__":
    unittest.main()

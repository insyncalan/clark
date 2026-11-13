"""Help page tabs by keyboard: arrows, Home/End, wrap, focus ring, Esc, at 900 and 1400 px in real Chrome.

Run: python3 dev/run_tests.py test_help_tabs_keys
"""
import unittest

from _paths import TOOLS  # noqa: F401
from test_report_editor import Base
from test_help_nav_page import set_size, SIZES

TABS = ["start", "howto", "reference"]


class HelpTabsKeys(Base):
    def in_help(self, cdp):
        p = self.visit(cdp)
        p.js("try { localStorage.removeItem('clark.helpTab'); } catch (e) {}")
        from test_help_panel import full_help_from_menu
        full_help_from_menu(p, "Help opened from the profile menu")
        return p

    def key(self, p, name, vk):
        p.key(name, code=name, vk=vk)

    def state(self, p):
        return p.js("[document.activeElement.id, ...[...document.querySelectorAll('.hp-tabs [role=tab]')].map(b => b.getAttribute('aria-selected') + b.tabIndex)].join('|')")

    def test_arrows_home_end_focus_ring_and_esc(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.in_help(cdp)
            for w in SIZES:
                set_size(cdp, p, w)
                p.js("document.querySelector('#hpTab-start').click(); document.querySelector('#hpTab-start').focus()")
                p.until("document.activeElement.id === 'hpTab-start'", f"{w}: Start here focused")
                ring = p.js("(function(){ const s = getComputedStyle(document.activeElement); return [s.outlineStyle, parseFloat(s.outlineWidth)]; })()")
                self.assertEqual(ring[0], "solid", f"{w}: a visible focus ring")
                self.assertGreaterEqual(ring[1], 2)
                seq = [("ArrowRight", 39, "howto"), ("ArrowRight", 39, "reference"), ("ArrowRight", 39, "start"),
                       ("ArrowLeft", 37, "reference"), ("Home", 36, "start"), ("End", 35, "reference"), ("ArrowLeft", 37, "howto")]
                for name, vk, want in seq:
                    self.key(p, name, vk)
                    p.until(f"document.activeElement.id === 'hpTab-{want}' && document.querySelector('#hpTab-{want}').getAttribute('aria-selected') === 'true'", f"{w}: {name} goes to {want}")
                    self.assertEqual(p.js("document.querySelectorAll('.hp-tabs [aria-selected=true]').length"), 1)
                    self.assertEqual(p.js("[...document.querySelectorAll('.hp-tabs [role=tab]')].filter(b => b.tabIndex === 0).length"), 1, "one tab stop")
                    self.assertEqual(p.js("document.querySelector('#hpPane').dataset.tab"), want)
                    vis = p.js("(function(){ const r = document.activeElement.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight && r.width > 0; })()")
                    self.assertTrue(vis, f"{w}: focused tab in view")
                # Esc on a tab takes the reader back to the page Help was opened from
                self.key(p, "Escape", 27)
                p.until("!document.querySelector('#help')", f"{w}: Esc on a tab closes Help")
                from test_help_panel import full_help_from_menu
                full_help_from_menu(p, "Help opened again")


if __name__ == "__main__":
    unittest.main()

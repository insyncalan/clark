"""Row 1064: the top bar does not show the project name; the logo stays, with room between it and the top menu items; the profile circle (Settings
is behind it) stays inside the window at 1400 and 900 px and narrower (#1033), in light and dark. The project switcher stays a button (a chevron),
its name only for a screen reader. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_header_no_project_name
"""
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

MEASURE = """(function(){
  var vis = function(e){ var r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
  var btn = document.querySelector('#project-name'), name = (btn.textContent || '').replace(/\\s+/g, ' ').trim();
  var seen = Array.from(document.querySelectorAll('header.top *')).filter(function(e){ return e.children.length === 0 && vis(e) && (e.textContent || '').trim() && name && (e.textContent || '').indexOf(name) >= 0; }).length;
  var logo = document.querySelector('header.top .logo').getBoundingClientRect(), first = document.querySelector('header.top .tab').getBoundingClientRect();
  var me = document.querySelector('#profile-btn').getBoundingClientRect(), bar = document.querySelector('header.top').getBoundingClientRect();
  return {name: name, shown: seen, hasName: !!document.querySelector('#project-name'), logo: logo.width, gap: first.left - logo.right,
          meRight: me.right, meLeft: me.left, win: window.innerWidth, page: document.documentElement.scrollWidth - document.documentElement.clientWidth, barH: bar.height};
})()"""


class HeaderNoProjectName(Base):
    def measure(self, width, theme):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, width, 700)
            p.until("document.querySelector('#project-name') && document.querySelector('#profile-btn')", "the bar shows")
            p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
            p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            return p.js(MEASURE)

    def test_the_bar_shows_no_project_name_and_keeps_the_logo(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                got = self.measure(width, theme)
                where = f"at {width} px, {theme}"
                self.assertTrue(got["name"], f"{where}: the switcher still carries the name for a screen reader")
                self.assertEqual(got["shown"], 0, f"{where}: the project name {got['name']!r} is drawn in the top bar")
                self.assertGreater(got["logo"], 20, f"{where}: the logo stays")

    def test_room_between_the_logo_and_the_top_menu_items(self):
        for width in (1400, 900):
            got = self.measure(width, "light")
            self.assertGreaterEqual(got["gap"], 24, f"at {width} px: {got['gap']} px between the logo and the first tab")

    def test_the_profile_circle_and_the_page_fit_the_window(self):
        for width in (1400, 900, 420, 360):
            got = self.measure(width, "light")
            self.assertLessEqual(got["meRight"], got["win"] + 0.5, f"at {width} px: the profile circle (Settings) runs past the window")
            self.assertGreaterEqual(got["meLeft"], 0, f"at {width} px")
            self.assertLessEqual(got["page"], 0, f"at {width} px: the page scrolls sideways")
            self.assertAlmostEqual(got["barH"], 56, delta=1, msg=f"at {width} px: the bar is one row")


if __name__ == "__main__":
    unittest.main()

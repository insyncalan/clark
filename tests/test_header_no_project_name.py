"""Row 1064: the top bar does not show the project name; the logo stays, with room between it and the top menu items; the profile circle (Settings
is behind it) stays inside the window at 1400 and 900 px and narrower (#1033), in light and dark. The project switcher stays a button (a chevron),
its name only for a screen reader. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_header_no_project_name
"""
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx
from clark import publish
from clark.store import open_store
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome, wait

MEASURE = """(function(){
  var vis = function(e){ var r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
  var btn = document.querySelector('#project-name'), name = (btn.textContent || '').replace(/\\s+/g, ' ').trim();
  var seen = Array.from(document.querySelectorAll('header.top *')).filter(function(e){ return e.children.length === 0 && vis(e) && (e.textContent || '').trim() && name && (e.textContent || '').indexOf(name) >= 0; }).length;
  var logo = document.querySelector('header.top .logo').getBoundingClientRect(), first = document.querySelector('header.top .tab').getBoundingClientRect();
  var sw = document.querySelector('header.top .projbtn'), swRight = sw ? sw.getBoundingClientRect().right : null;
  var me = document.querySelector('#profile-btn').getBoundingClientRect(), bar = document.querySelector('header.top').getBoundingClientRect();
  return {name: name, shown: seen, hasName: !!document.querySelector('#project-name'), logo: logo.width, gap: first.left - logo.right, swGap: swRight === null ? null : first.left - swRight,
          meRight: me.right, meLeft: me.left, win: window.innerWidth, page: document.documentElement.scrollWidth - document.documentElement.clientWidth, barH: bar.height};
})()"""

FILE_MEASURE = """(function(){
  var vis = function(e){ var r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; };
  var n = document.querySelector('header.top #project-name'), name = (n.textContent || '').replace(/\\s+/g, ' ').trim();
  var seen = Array.from(document.querySelectorAll('header.top *')).filter(function(e){ return e.children.length === 0 && vis(e) && name && (e.textContent || '').indexOf(name) >= 0; }).length;
  return {name: name, shown: seen};
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

    def test_room_between_the_switcher_and_the_top_menu_items(self):
        for width in (1400, 900):
            got = self.measure(width, "light")
            self.assertGreaterEqual(got["swGap"], 22, f"at {width} px: {got['swGap']} px between the switcher and the first tab")

    def test_the_profile_circle_and_the_page_fit_the_window(self):
        for width in (1400, 900):
            got = self.measure(width, "light")
            self.assertLessEqual(got["meRight"], got["win"] + 0.5, f"at {width} px: the profile circle (Settings) runs past the window")
            self.assertGreaterEqual(got["meLeft"], 0, f"at {width} px")
            self.assertLessEqual(got["page"], 0, f"at {width} px: the page scrolls sideways")
            self.assertAlmostEqual(got["barH"], 56, delta=1, msg=f"at {width} px: the bar is one row")

    def test_the_switcher_shows_a_box_on_hover_and_on_keyboard_focus(self):
        sel = "document.querySelector('header.top .projbtn')"
        for width in (1400, 900):
            with chrome() as cdp:
                p = self.visit(cdp)
                size(cdp, p, width, 700)
                p.until("document.querySelector('header.top .projbtn')", "the switcher shows")
                where = f"at {width} px"
                rest = p.js(f"getComputedStyle({sel}).backgroundColor")
                r = p.js(f"(function(){{ var r = {sel}.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }})()")
                p.mouse("mouseMoved", r[0], r[1])
                p.until(f"{sel}.matches(':hover')", "hovered")
                self.assertNotEqual(p.js(f"getComputedStyle({sel}).backgroundColor"), rest, f"{where}: hover draws no box")
                p.mouse("mouseMoved", 1, 1)
                p.js(f"{sel}.focus()")
                p.js("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                got = p.js(f"(function(){{ var c = getComputedStyle({sel}); return [c.outlineStyle, c.outlineWidth, {sel}.matches(':focus-visible')]; }})()")
                self.assertEqual(got[0], "solid", f"{where}: no focus outline")
                self.assertEqual(got[1], "2px", f"{where}: the focus outline is not 2px")


class PublishedFileHasNoProjectName(unittest.TestCase):
    """The published file's bar has no switcher: its name span is kept for a screen reader and is not drawn (row 1064)."""

    def test_the_file_bar_does_not_draw_the_project_name(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as brand:
            store = open_store(fx.build_db(Path(tmp) / "clark.db"), onedrive_roots=[])
            self.addCleanup(store.close)
            done = publish.publish(store, "PUB", tmp, by_user="Demo User", now="2026-10-28", branding=brand)
            for width in (1400, 900):
                with chrome() as cdp:
                    tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                    sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('header.top #project-name')", sid), 15), "the file's bar drew")
                    got = cdp.js(FILE_MEASURE, sid)
                    self.assertTrue(got["name"], f"at {width} px: the name stays for a screen reader")
                    self.assertEqual(got["shown"], 0, f"at {width} px: the file's bar draws the project name {got['name']!r}")


if __name__ == "__main__":
    unittest.main()

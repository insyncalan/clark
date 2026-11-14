"""Row 1176 (browser): in the editor Dashboard the project name in the cover is click-to-change. It is not drawn until hover or focus,
says "Click to change project", and a click opens the project list (the same menu rows as the top-bar switcher); choosing a project
loads that project's page. The cover heading keeps the project name. A published file has none of it, and the Gantt page's cover
has no switcher. Widths 1400 and 900.

Run: python3 dev/run_tests.py test_project_cover_switch_1176      (Chrome required)
"""
import contextlib
import unittest

from test_project_switch import TWO
from test_publish_dialog import Base, WIDTHS
from test_server import chrome, wait

SW = "#cover .cover-switch"
MENU = "#cover-project-menu"
ROWS = "[].map.call(document.querySelectorAll('%s [role=menuitemradio]'), function(e){return e.textContent.replace('✓','')})" % MENU


class CoverSwitch(Base):
    def open_menu(self, p):
        p.until("!!document.querySelector('%s')" % SW, "the cover has the project control")
        p.js("document.querySelector('%s').click()" % SW)
        p.until("!!document.querySelector('%s')" % MENU, "the project list opened")

    def close_menu(self, p):
        """Esc closes the list. A slow runner drops a single key event, so press again while the list is still drawn."""
        gone = lambda: not p.js("!!document.querySelector('%s')" % MENU)

        def press():
            if gone():
                return True
            p.key("Escape", code="Escape", vk=27)
            return wait(gone, 1.5)
        self.assertTrue(wait(press, 15), "Esc closed it")

    def hover(self, p, sel):
        x, y = p.js("(function(){var r=document.querySelector('%s').getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()" % sel)
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)

    def test_C_the_cover_keeps_the_name_and_has_one_control(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('#cover h1')", "the cover is drawn")
            self.assertIn("Harbour", p.js("document.querySelector('#cover h1').textContent"), "the heading is still the project name")
            self.assertEqual(p.js("document.querySelectorAll('%s').length" % SW), 1)
            self.assertEqual(p.js("document.querySelectorAll('#project-name').length"), 1, "the top-bar switcher is kept and its id is not repeated")

    def test_C_invisible_until_hover_and_says_click_to_change(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('%s')" % SW, "the control")
            for w in WIDTHS:
                p.width(w)
                self.assertEqual(p.js("getComputedStyle(document.querySelector('%s')).backgroundColor" % SW), "rgba(0, 0, 0, 0)", "no box drawn at rest")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('%s')).fontSize === getComputedStyle(document.querySelector('#cover h1')).fontSize" % SW), True, "it reads as the heading")
                self.assertEqual(p.js("document.querySelector('%s').closest('#cover').querySelector('h1').getBoundingClientRect().height > 0" % SW), True)
                self.assertIn("Click to change project", p.js("(document.querySelector('%s').title || '') + ' ' + (document.querySelector('%s').getAttribute('aria-label') || '') + ' ' + document.querySelector('%s').textContent" % (SW, SW, SW)))
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways overflow")

    def test_C_the_chevron_and_outline_show_only_on_hover_or_open(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        chev = "getComputedStyle(document.querySelector('%s .nch')).opacity" % SW
        edge = "getComputedStyle(document.querySelector('%s')).outlineStyle" % SW
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('%s')" % SW, "the control")
            for w in WIDTHS:
                p.width(w)
                p.js("document.activeElement && document.activeElement.blur()")      # Esc gave the focus back to the button, which shows the chevron
                p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, p.sid)
                p.until("%s === '0'" % chev, "the chevron is not drawn at rest")
                self.assertEqual(p.js(edge), "none", "no outline at rest")
                self.hover(p, SW)
                p.until("%s === '1'" % chev, "the chevron shows on hover")
                self.assertEqual(p.js(edge), "dashed", "a dashed outline on hover")
                p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, p.sid)
                self.open_menu(p)
                p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 2, "y": 2}, p.sid)
                p.until("%s === '1'" % chev, "the chevron stays while the list is open")
                self.close_menu(p)

    def test_C_the_open_list_is_whole_and_clickable_not_cut_by_the_cover(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                self.open_menu(p)
                p.until("document.querySelectorAll('%s [role=menuitemradio]').length === 2" % MENU, "both rows are drawn")
                got = p.js("""(function(){var m=document.querySelector('%s'),r=m.getBoundingClientRect(),out={inside:r.top>=0&&r.left>=0&&r.bottom<=innerHeight&&r.right<=innerWidth,rows:[]};
                  m.querySelectorAll('[role=menuitemradio]').forEach(function(e){var b=e.getBoundingClientRect(),h=document.elementFromPoint(b.left+b.width/2,b.top+b.height/2);out.rows.push(!!h&&e.contains(h))});
                  var cv=document.querySelector('#cover').getBoundingClientRect();out.cut=r.bottom>cv.bottom&&getComputedStyle(document.querySelector('#cover')).overflow!=='visible'&&!!document.elementFromPoint(r.left+r.width/2,r.bottom-4)&&!m.contains(document.elementFromPoint(r.left+r.width/2,r.bottom-4));return out})()""" % MENU)
                self.assertTrue(got["inside"], "the list is inside the window at %d" % w)
                self.assertEqual(got["rows"], [True, True], "each row is what a click at its middle reaches (not clipped away) at %d" % w)
                self.assertFalse(got["cut"], "the cover does not cut the list's lower edge at %d" % w)
                self.close_menu(p)

    def test_C_a_click_opens_the_project_list(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                self.open_menu(p)
                p.until("document.querySelectorAll('%s [role=menuitemradio]').length === 2" % MENU, "both rows are read")
                self.assertEqual(p.js(ROWS), ["Harbour Bridge Programme3 open items", "Second Programme1 open item"])
                self.assertEqual(p.js("document.querySelector('%s [aria-checked=true] b').textContent" % MENU), "Harbour Bridge Programme")
                self.close_menu(p)

    def test_C_choosing_another_project_loads_its_page(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with self.rig.store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Second Programme"})
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.until("document.querySelectorAll('%s [role=menuitemradio]').length === 2" % MENU, "both rows are read")
            p.js("document.querySelectorAll('%s [role=menuitemradio]')[1].click()" % MENU)
            p.until("new URLSearchParams(location.search).get('project') === 'ABC'", "the page loaded for the chosen project")
            p.until("document.querySelector('#cover h1').textContent.includes('Second Programme')", "the cover names the chosen project")


class NotElsewhere(unittest.TestCase):
    def test_the_published_page_holds_no_cover_switch(self):
        """The text a published file is made from is page.page_html(view=True) (publish.py), built from page-view.html, which is not
        committed: ensure_built makes it, as the other tests' first import does. It must exist and be the real page (it holds the cover),
        or the check below would pass on nothing."""
        import _paths  # noqa: F401  (builds the pages)
        from clark import page
        page.ensure_built()
        self.assertTrue(page.VIEW_PAGE.is_file(), "page-view.html is built")
        html = page.page_html(view=True)
        self.assertIn("Weekly report", html, "it is the real published page, so the words below are really absent")
        for word in ("cover-switch", "Click to change project", "cover-project-menu"):
            self.assertNotIn(word, html)


class GanttCover(unittest.TestCase):
    """The Gantt page's cover, drawn in Chrome (the same demo bundle test_gantt_page uses, with the Edit tools), has no project switcher."""

    def test_the_gantt_page_cover_is_left_alone(self):
        from test_gantt_page import page_html
        from test_server import Running, wait
        with contextlib.closing(Running(page_html=page_html)) as server, chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": "http://127.0.0.1:%d/" % server.port}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!(window.P && window.P.mount)", sid), 15), "the test bundle ran")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.js("P.mount({width: %d})" % (w - 40), sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#gantt-page #cover h1')", sid), 15), "the Gantt cover is drawn at %d" % w)
                self.assertEqual(cdp.js("document.querySelectorAll('.cover-switch').length", sid), 0, "no project switcher in the cover at %d" % w)
                self.assertEqual(cdp.js("document.querySelectorAll('#cover button, #cover [role=button], #cover [role=menuitemradio]').length", sid), 0)
                self.assertNotIn("Click to change project", cdp.js("document.body.innerHTML", sid))


if __name__ == "__main__":
    unittest.main()

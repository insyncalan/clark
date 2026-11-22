"""Row 1176 (browser), as ruled (order WO-M2256, option A): the project switch is the project name in the one slim header
(.hdr-project, item 1177), click-to-change. Its hover text says "Click to change project", a click opens the project list (the same
rows as before), and choosing a project loads that project's page. The done-when: select project A then project B, the work
items, milestones, project data and brand change each time, and B's items are never shown under A. A published file has none
of it, and the Gantt page's cover has no switcher. Widths 1400 and 900.

Run: python3 dev/run_tests.py test_project_header_switch_1176      (Chrome required)
"""
import contextlib
import unittest
from unittest import mock

from test_project_switch import TWO
from test_publish_dialog import Base, WIDTHS
from test_server import chrome, wait
import _testpage as testpage
from clark import page, theme

NAME = "#project-name.hdr-project"
MENU = "#project-menu"
ROWS = "[].map.call(document.querySelectorAll('%s [role=menuitemradio]'), function(e){return e.textContent.replace('\u2713','')})" % MENU
BODY = "document.body.innerText"


class HeaderSwitchClassic(Base):
    """Row 1341 ruling: with the Classic layer the header name's tooltip is the full project name and Click to change project (Cards keeps 'Click to change project')."""
    def setUp(self):
        orig = testpage.html
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), theme.css("prototype-2.0")))
        m.start()
        self.addCleanup(m.stop)
        super().setUp()

    def test_C_the_header_name_tooltip_is_the_full_project_name_in_classic(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('%s')" % NAME, "the header name")
            for w in WIDTHS:
                p.width(w)
                name = p.js("document.querySelector('%s').textContent.trim()" % NAME)
                self.assertEqual(name, 'Bridge & "Harbour" <Programme>', "the full name is shown at %d" % w)
                self.assertEqual(p.js("document.querySelector('%s').title" % NAME), 'Bridge & "Harbour" <Programme>. Click to change project', "Classic tooltip is the full name and Click to change project (row 1305) at %d" % w)


class HeaderSwitch(Base):
    def open_menu(self, p):
        p.until("!!document.querySelector('%s')" % NAME, "the header has the project name button")
        p.js("document.querySelector('%s').click()" % NAME)
        p.until("!!document.querySelector('%s')" % MENU, "the project list opened")

    def test_C_the_header_name_is_the_one_control_and_says_click_to_change(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('%s')" % NAME, "the header name")
            for w in WIDTHS:
                p.width(w)
                self.assertEqual(p.js("document.querySelectorAll('.top .hdr-project').length"), 1, "one project control in the header at %d" % w)
                self.assertEqual(p.js("document.querySelectorAll('#project-name').length"), 1, "its id is not repeated at %d" % w)
                self.assertEqual(p.js("document.querySelectorAll('.cover-switch, #cover .hdr-project').length"), 0, "no second control in a cover band at %d" % w)
                self.assertEqual(p.js("document.querySelector('%s').title" % NAME), "Click to change project", "Cards keeps the click-to-change tooltip at %d" % w)
                self.assertIn("Change project", p.js("document.querySelector('%s').getAttribute('aria-label') || ''" % NAME))
                self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways overflow at %d" % w)

    def test_C_a_click_opens_the_project_list(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                self.open_menu(p)
                p.until("document.querySelectorAll('%s [role=menuitemradio]').length === 2" % MENU, "both rows are read at %d" % w)
                self.assertEqual(p.js(ROWS), ["Harbour Bridge Programme3 open items", "Second Programme1 open item"])
                self.assertEqual(p.js("document.querySelector('%s [aria-checked=true] b').textContent" % MENU), "Harbour Bridge Programme")
                p.js("document.querySelector('%s').click()" % NAME)
                p.until("!document.querySelector('%s')" % MENU, "a second click shut the list at %d" % w)

    def test_C_the_open_list_is_whole_and_clickable_under_the_header(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                self.open_menu(p)
                p.until("document.querySelectorAll('%s [role=menuitemradio]').length === 2" % MENU, "both rows are drawn")
                got = p.js("""(function(){var m=document.querySelector('%s'),r=m.getBoundingClientRect(),out={inside:r.top>=0&&r.left>=0&&r.bottom<=innerHeight&&r.right<=innerWidth,rows:[]};
                  m.querySelectorAll('[role=menuitemradio]').forEach(function(e){var b=e.getBoundingClientRect(),h=document.elementFromPoint(b.left+b.width/2,b.top+b.height/2);out.rows.push(!!h&&e.contains(h))});return out})()""" % MENU)
                self.assertTrue(got["inside"], "the list is inside the window at %d" % w)
                self.assertEqual(got["rows"], [True, True], "each row is what a click at its middle reaches at %d" % w)
                p.js("document.querySelector('%s').click()" % NAME)
                p.until("!document.querySelector('%s')" % MENU, "closed")

    def test_C_select_A_then_B_then_A_the_page_follows_and_B_items_are_never_under_A(self):
        """The done-when of row 1176 in the browser: the header name, the project data and the work items change with each choice."""
        self.rig.httpd.projects = lambda archived=False: TWO
        with self.rig.store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Second Programme"})
            s.create("actions", {"project": "ABC", "description": "Second only action", "raised": "2030-05-01", "source": "demo"})
            s.create("milestones", {"project": "ABC", "name": "Second only milestone", "baseline_date": "2030-05-01", "source": "demo"})
        pick = lambda p, name: p.js("[].filter.call(document.querySelectorAll('%s [role=menuitemradio]'), function(e){return e.textContent.indexOf('%s') === 0})[0].click()" % (MENU, name))
        header = lambda: "document.querySelector('%s').textContent" % NAME
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp, "#dashboard&p=PUB")
                p.width(w)
                p.until("%s.includes('Harbour')" % header(), "A is open: the header names A at %d" % w)
                self.assertNotIn("Second only", p.js(BODY), "A shows none of B's rows")
                self.open_menu(p)
                p.until("document.querySelectorAll('%s [role=menuitemradio]').length === 2" % MENU, "rows read")
                pick(p, "Second Programme")
                p.until("new URLSearchParams(location.search).get('project') === 'ABC'", "the page loaded for B at %d" % w)
                p.until("%s.includes('Second Programme')" % header(), "the header names B")
                self.assertNotIn("Harbour", p.js(header()), "A's name is gone from the header")
                p.until("%s.includes('Second only')" % BODY, "B's own rows are shown")
                self.assertEqual(p.js("document.querySelectorAll('.top .hdr-project').length"), 1)
                self.open_menu(p)
                p.until("document.querySelectorAll('%s [role=menuitemradio]').length === 2" % MENU, "rows read again")
                pick(p, "Harbour Bridge Programme")
                p.until("%s.includes('Harbour')" % header(), "back to A: the header names A")
                p.until("!%s.includes('Second only')" % BODY, "back to A: B's rows are not shown under A")


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

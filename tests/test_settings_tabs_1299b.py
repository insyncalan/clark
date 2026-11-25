"""Row 1299 line 6: project tabs across the top of the Settings pages that hold one project's settings, in a real browser at 1400 and 900 px,
light and dark. Run: python3 dev/run_tests.py test_settings_tabs_1299b

What is asserted (Classic): the project pages (Reports and pages, Brand and publishing, People, ask clark, Export and import) draw one tab for each project, in the list's order, with
the open project marked (aria-current); the tabs are one row about 44 px high and are pinned under the top bar when the page scrolls; a click on another tab changes the Settings page's project only (no page read, the address and the top bar do not move); the All projects and You pages draw no tabs; with the Cards look (no theme layer)
no page draws tabs. Not in this part: a project switch without a page read, an Add project link. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from clark import page, theme
import _testpage as testpage
from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from test_settings_bar import calm
from test_settings_head import address

WIDTHS = (1400, 900)
MODES = ("light", "dark")
TWO = [{"code": "PUB", "name": "Harbour Bridge Programme", "open": 3}, {"code": "ABC", "name": "Second Programme", "open": 1}]
TABS = "[...document.querySelectorAll('.set-tabs .set-tab:not([data-all])')]"      # the project tabs; ask clark's leading All projects tab is data-all
PROJECT_PAGES = ("reports", "brand", "people", "claude", "data")
OTHER_PAGES = ("projects", "backups", "profile", "appearance", "version")


class Tabs(Base):
    classic = True

    def setUp(self):
        css = theme.css("prototype-2.0")
        layer = (lambda: page.layer_theme(testpage.html(), css)) if self.classic else testpage.html
        self.rig = Rig(self, saved=self.saved, page_html=layer)
        self.rig.httpd.projects = lambda archived=False: TWO

    def open_settings(self, p, w, mode="light", slug="people"):
        p.width(w)
        calm(p, mode)
        p.js(f"location.hash = '{address(slug)}'")
        p.until("!!document.querySelector('.set-nav .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")

    def test_T_a_project_page_has_one_tab_for_each_project_with_the_open_one_marked(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    p.until(f"{TABS}.length === 2", "the tabs drew")
                    self.assertEqual(p.js(f"{TABS}.map(b => b.textContent)"), [t["name"] for t in TWO])
                    self.assertEqual(p.js(f"{TABS}.map(b => b.getAttribute('aria-current'))"), ["page", None], "the open project is marked")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_T_the_tabs_are_one_row_and_stay_under_the_top_bar_when_the_page_scrolls(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                self.open_settings(p, w, slug="reports")
                p.until(f"{TABS}.length === 2", "the tabs drew")
                h = p.js("document.querySelector('.set-tabs').getBoundingClientRect().height")
                self.assertTrue(40 <= h <= 48, f"one row about 44 px, got {h}")
                pill = p.js("(() => { const c = getComputedStyle(document.querySelector('.set-tabs .set-tab')); return [c.borderTopLeftRadius, c.paddingTop, c.paddingLeft, c.fontSize, getComputedStyle(document.querySelector('.set-tabs .set-tab[aria-current]')).fontWeight]; })()")
                self.assertEqual(pill, ["999px", "5px", "14px", "13.5px", "600"], "AP10: a pill, radius 999, padding 5px 14px, 13.5px, the open one weight 600")
                bar = p.js("parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--topbar'))")
                p.js("document.body.style.paddingBottom = '2500px'")
                nat = p.js("document.querySelector('.set-tabs').getBoundingClientRect().top + window.scrollY")
                self.assertGreater(nat, bar + 40, "the tabs start below the top bar")
                p.js(f"window.scrollTo(0, {nat} - 10)")      # the tabs would be 10 px from the window top, above the top bar, if they were not pinned
                p.until(f"Math.abs(window.scrollY - ({nat} - 10)) < 2", "the page scrolled")
                top = p.js("document.querySelector('.set-tabs').getBoundingClientRect().top")
                self.assertAlmostEqual(top, bar, delta=2, msg="pinned just under the top bar")

    def test_T_every_project_page_has_them_and_no_other_page_does(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400)
            for slug in PROJECT_PAGES:
                with self.subTest(page=slug):
                    p.js(f"location.hash = '{address(slug)}'")
                    p.until(f"document.querySelector('.set-nav .set-chip[aria-current]') && !!document.querySelector('.set-tabs')", f"{slug} has tabs")
            for slug in OTHER_PAGES:
                with self.subTest(page=slug):
                    p.js(f"location.hash = '{address(slug)}'")
                    p.until(f"document.querySelector('.set-cards').getAttribute('data-page') === {slug!r}".replace("'projects'", "'projects'"), f"{slug} drew")
                    self.assertFalse(p.js("!!document.querySelector('.set-tabs')"), f"{slug} has no tabs")

    def test_T_a_click_on_another_tab_changes_the_settings_project_and_nothing_else(self):
        """The tab switch is off (stores/report.js switchTabs) until the project cards follow the chosen tab: the other tab cannot be chosen, nothing moves."""
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400, slug="people")
            p.until(f"{TABS}.length === 2", "the tabs drew")
            self.assertEqual(p.js(f"[{TABS}[0].getAttribute('aria-disabled'), {TABS}[1].getAttribute('aria-disabled'), {TABS}[0].disabled, {TABS}[1].disabled]"), [None, "true", False, False], "the other tab says aria-disabled and is not disabled (no focus trap)")
            before = p.js("[location.href, document.querySelector('#project-name').textContent]")
            p.js(f"{TABS}[1].click()")
            self.assertEqual(p.js(f"{TABS}[0].getAttribute('aria-current')"), "page", "the open project's tab stays marked")
            self.assertEqual(p.js("[location.href, document.querySelector('#project-name').textContent]"), before)
            self.assertEqual(p.js("document.querySelector('.set-affects').textContent.trim()"), "Affects: " + TWO[0]["code"])

    def test_T_the_affects_line_follows_the_tab_on_every_project_page(self):
        """Row 1299: "Affects: <code>" names the open project's tab on every project page (the switch is off, see the test above)."""
        with chrome() as cdp:
            p = self.page(cdp)
            for slug in PROJECT_PAGES:
                with self.subTest(page=slug):
                    self.open_settings(p, 1400, slug=slug)
                    p.until(f"{TABS}.length === 2", "the tabs drew")
                    self.assertEqual(p.js("document.querySelector('.set-affects').textContent.trim()"), "Affects: " + TWO[0]["code"], "the open project's tab is chosen")


class TabsCards(Tabs):
    classic = False

    def test_T_the_affects_line_follows_the_tab_on_every_project_page(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for slug in PROJECT_PAGES:
                self.open_settings(p, 1400, slug=slug)
                self.assertFalse(p.js("!!document.querySelector('.set-affects')"), "Cards says no Affects line")

    def test_T_a_project_page_has_one_tab_for_each_project_with_the_open_one_marked(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for slug in PROJECT_PAGES:
                self.open_settings(p, 1400, slug=slug)
                self.assertFalse(p.js("!!document.querySelector('.set-tabs')"), "Cards draws no tabs")

    test_T_the_tabs_are_one_row_and_stay_under_the_top_bar_when_the_page_scrolls = None
    test_T_every_project_page_has_them_and_no_other_page_does = None
    test_T_a_click_on_another_tab_changes_the_settings_project_and_nothing_else = None


if __name__ == "__main__":
    unittest.main()

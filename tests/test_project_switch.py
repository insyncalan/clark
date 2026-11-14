"""A-D25 and #439 row 37 (prototype core.js:292-295): the project switcher in the top bar, in a real browser. The name is always a
button with a chevron and a menu, with one project as with two. The menu lists the projects (the open one marked, each with "N open
items"), and nothing else (row 1092); choosing a project changes the address and the page loads for that project (no "Switched to" message: the name is on screen); a published file shows
the name as plain words and holds no switcher.

Run: python3 dev/run_tests.py test_project_switch
"""
import unittest

from test_publish_dialog import Base, WIDTHS
from test_server import chrome

TWO = [{"code": "PUB", "name": "Harbour Bridge Programme", "open": 3}, {"code": "ABC", "name": "Second Programme", "open": 1}]
ITEMS = "[].map.call(document.querySelectorAll('#project-menu [role=menuitemradio]'), function(e){return e.textContent.replace('✓','')})"


class ProjectSwitch(Base):
    def open_menu(self, p):
        p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the name is a menu button")
        p.js("document.querySelector('#project-name').click()")
        p.until("!!document.querySelector('#project-menu')", "the menu opened")

    def test_C_one_project_is_still_a_button_with_its_menu(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('.tabs .tab')", "the page is drawn")
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "a button, as the prototype has it")
            self.assertEqual(p.js("document.querySelector('#project-name').textContent.replace(/\\s+/g, ' ').trim()"), 'Bridge & "Harbour" <Programme>')
            self.assertEqual(p.js("document.querySelector('#project-name').getAttribute('aria-haspopup')"), "menu")
            self.open_menu(p)
            self.assertEqual(len(p.js(ITEMS)), 1, "the one project")
            self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return e.textContent})"), [], "row 1092: only the project list, no New project or Project settings")
            self.assertEqual(p.js("document.querySelectorAll('#project-menu [role=separator]').length"), 0)

    def test_C_the_switcher_is_the_name_button_without_a_box(self):
        """Item 1177 (ProjectSwitch.jsx:33, header prop): the switcher is the header's .hdr-project button, the name drawn and no chevron, no box (shell.css:2600 `all: unset`)."""
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the menu button")
            for w in WIDTHS:
                p.width(w)
                box = p.js("(function(){var b=document.querySelector('#project-name'),r=b.getBoundingClientRect(),"
                           "s=getComputedStyle(b);return {cls:b.classList.contains('hdr-project'),chev:!!b.querySelector('.nch'),w:r.width,bw:parseFloat(s.borderTopWidth),bar:document.documentElement.scrollWidth-window.innerWidth}})()")
                self.assertTrue(box["cls"], "item 1177: the header's project name button")
                self.assertFalse(box["chev"], "item 1177: the name is the button, no chevron")
                self.assertEqual(box["bw"], 0, "no box around the name")
                self.assertGreater(box["w"], 16, "the name is drawn")
                self.assertLessEqual(box["bar"], 0, "no sideways overflow")

    def test_C_the_menu_lists_only_the_projects_with_open_counts(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the menu button")
            for w in WIDTHS:
                p.width(w)
                self.assertTrue(p.js("document.querySelector('#project-name').classList.contains('hdr-project') && !document.querySelector('#project-name .nch')"), "item 1177: the drawn name is the button (ProjectSwitch.jsx:33)")
                self.assertTrue(p.js("document.querySelector('#project-name').getBoundingClientRect().width > 16"), "visible at this width")
                self.open_menu(p)
                self.assertEqual(p.js(ITEMS), ["Harbour Bridge Programme3 open items", "Second Programme1 open item"])
                self.assertEqual(p.js("document.querySelector('#project-menu [aria-checked=true] b').textContent"), "Harbour Bridge Programme")
                self.assertEqual(p.js("document.querySelector('#project-menu [aria-checked=true] small').textContent"), "3 open items")
                self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return e.textContent})"), [], "row 1092: no New project and no Project settings in the menu")
                self.assertEqual(p.js("document.querySelectorAll('#project-menu [role=separator]').length"), 0)
                self.assertNotIn("Project settings", p.js("document.querySelector('#project-menu').textContent"))
                self.assertNotIn("New project", p.js("document.querySelector('#project-menu').textContent"))
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#project-menu')", "Esc closed it")
                p.until("document.activeElement.id === 'project-name'", "focus is back on the name")

    def test_C_the_menu_starts_on_the_open_project(self):
        """Row 856: focus is on the open project (Enter at once keeps it). Row 1092: the project list is all the menu holds."""
        self.rig.httpd.projects = lambda archived=False: [TWO[1], TWO[0]]
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.until("document.activeElement && document.activeElement.getAttribute('aria-checked') === 'true'", "focus is on the open project")
            self.assertEqual(p.js("document.activeElement.querySelector('b').textContent"), "Harbour Bridge Programme")
            self.assertEqual(p.js("document.querySelectorAll('#project-menu [role^=menuitem]').length"), 2, "the two projects and nothing else")

    def test_C_the_counts_are_read_again_each_time_the_menu_opens(self):
        """Work done since the page drew (an item closed or added) shows in the menu's counts without a reload."""
        now = [dict(r) for r in TWO]
        self.rig.httpd.projects = lambda archived=False: [dict(r) for r in now]
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.assertEqual(p.js(ITEMS), ["Harbour Bridge Programme3 open items", "Second Programme1 open item"])
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#project-menu')", "Esc closed it")
            now[0]["open"], now[1]["open"] = 2, 4          # one item closed in the first project, three added to the second
            self.open_menu(p)
            p.until("document.querySelector('#project-menu [aria-checked=true] small').textContent === '2 open items'", "the fresh count")
            self.assertEqual(p.js(ITEMS), ["Harbour Bridge Programme2 open items", "Second Programme4 open items"])

    def test_C_choosing_a_project_changes_the_address_and_says_so(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with self.rig.store.step("dashboard", "tester", place="menu") as s:      # the chosen project is one clark has, so its page opens in View
            s.create("projects", {"code": "ABC", "name": "Second Programme"})
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("document.querySelectorAll('#project-menu [role=menuitemradio]')[1].click()")
            p.until("/p=ABC/.test(location.hash) && new URLSearchParams(location.search).get('project') === 'ABC'", "the address names the chosen project, in the page loaded for it")      # #944: its own page load, so the old page's toast is gone
            p.until("document.getElementById('project-name').textContent.includes('Second Programme')", "the new page says the chosen project is open")
            p.js("document.querySelector('[data-mode=edit]').click()")          # View draws no message on the Dashboard: Edit would show one that came across
            p.until("document.querySelector('#report') && document.querySelector('#report').dataset.mode === 'edit'", "Edit")
            self.assertEqual(p.js("(document.querySelector('.toast-text') || {textContent: ''}).textContent"), "", "no 'Switched to' message: the name is on the screen (#944 ruling)")

class TheFileHasNoSwitcher(unittest.TestCase):
    def test_the_published_page_has_no_menu_words(self):
        from _paths import SRC
        html = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("project-menu", "Project settings", "Switched to", "open items"):
            self.assertNotIn(word, html)


if __name__ == "__main__":
    unittest.main()

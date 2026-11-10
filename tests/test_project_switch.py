"""A-D25 and #439 row 37 (prototype core.js:292-295): the project switcher in the top bar, in a real browser. The name is always a
button with a chevron and a menu, with one project as with two. The menu lists the projects (the open one marked, each with "N open
items"), then Project settings; choosing a project changes the address and the page loads for that project (no "Switched to" message: the name is on screen); a published file shows
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
            self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return e.textContent})"), ["New project...", "Project settings"])

    def test_C_the_switcher_is_the_chevron_alone_without_a_box(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the menu button")
            for w in WIDTHS:
                p.width(w)
                box = p.js("(function(){var b=document.querySelector('#project-name'),r=b.getBoundingClientRect(),c=b.querySelector('.nch').getBoundingClientRect(),"
                           "s=getComputedStyle(b);return {w:r.width,bw:parseFloat(s.borderTopWidth),right:r.right-c.right,bar:document.documentElement.scrollWidth-window.innerWidth}})()")
                self.assertEqual(box["bw"], 0, "row 1064: no box; the name is not drawn")
                self.assertLessEqual(box["w"], 48, "row 1064: the chevron alone")
                self.assertLess(box["right"], 16, "the chevron sits at the right edge of the button")
                self.assertLessEqual(box["bar"], 0, "no sideways overflow")
            p.width(1400)
            self.assertLessEqual(p.js("document.querySelector('#project-name').getBoundingClientRect().width"), 48)

    def test_C_the_menu_lists_the_projects_with_open_counts_and_Project_settings(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the menu button")
            for w in WIDTHS:
                p.width(w)
                self.assertTrue(p.js("!!document.querySelector('#project-name .nch')"), "a chevron")
                self.assertTrue(p.js("document.querySelector('#project-name').getBoundingClientRect().width > 16"), "visible at this width")
                self.open_menu(p)
                self.assertEqual(p.js(ITEMS), ["Harbour Bridge Programme3 open items", "Second Programme1 open item"])
                self.assertEqual(p.js("document.querySelector('#project-menu [aria-checked=true] b').textContent"), "Harbour Bridge Programme")
                self.assertEqual(p.js("document.querySelector('#project-menu [aria-checked=true] small').textContent"), "3 open items")
                self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return e.textContent})"), ["New project...", "Project settings"])
                self.assertEqual(p.js("document.querySelectorAll('#project-menu [role=separator]').length"), 1)
                self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return e.textContent})")[0], "New project...")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#project-menu')", "Esc closed it")
                p.until("document.activeElement.id === 'project-name'", "focus is back on the name")

    def test_C_the_menu_starts_on_the_open_project_and_has_New_project_that_opens_the_form(self):
        """Row 856: focus is on the open project (Enter at once keeps it), and New project... opens the project form."""
        self.rig.httpd.projects = lambda archived=False: [TWO[1], TWO[0]]
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.until("document.activeElement && document.activeElement.getAttribute('aria-checked') === 'true'", "focus is on the open project")
            self.assertEqual(p.js("document.activeElement.querySelector('b').textContent"), "Harbour Bridge Programme")
            self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role^=menuitem]'), function(e){return e.textContent.replace('✓','')}).slice(-2)"),
                             ["New project...", "Project settings"])
            p.js("document.querySelector('#project-menu [role=menuitem]').click()")          # New project... is the first plain item
            p.until("!!document.querySelector('#project-form')", "the project form opened")

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

    def test_C_Project_settings_opens_Settings(self):
        self.rig.httpd.projects = lambda archived=False: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("[].filter.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return /settings/i.test(e.textContent)})[0].click()")
            p.until("/^#settings/.test(location.hash)", "the address is Settings")
            self.assertIn("p=PUB", p.js("location.hash"), "still the same project")


class TheFileHasNoSwitcher(unittest.TestCase):
    def test_the_published_page_has_no_menu_words(self):
        from _paths import SRC
        html = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("project-menu", "Project settings", "Switched to", "open items"):
            self.assertNotIn(word, html)


if __name__ == "__main__":
    unittest.main()

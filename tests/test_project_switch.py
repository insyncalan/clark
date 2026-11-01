"""A-D25 and #439 row 37 (prototype core.js:292-295): the project switcher in the top bar, in a real browser. The name is always a
button with a chevron and a menu, with one project as with two. The menu lists the projects (the open one marked, each with "N open
items"), then Project settings; choosing a project changes the address and the toast says "Switched to <name>"; a published file shows
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
            self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return e.textContent})"), ["Project settings"])

    def test_C_the_menu_lists_the_projects_with_open_counts_and_Project_settings(self):
        self.rig.httpd.projects = lambda: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the menu button")
            for w in WIDTHS:
                p.width(w)
                self.assertTrue(p.js("!!document.querySelector('#project-name .nch')"), "a chevron")
                self.assertTrue(p.js("document.querySelector('#project-name').getBoundingClientRect().width > 40"), "visible at this width")
                self.open_menu(p)
                self.assertEqual(p.js(ITEMS), ["Harbour Bridge Programme3 open items", "Second Programme1 open item"])
                self.assertEqual(p.js("document.querySelector('#project-menu [aria-checked=true] b').textContent"), "Harbour Bridge Programme")
                self.assertEqual(p.js("document.querySelector('#project-menu [aria-checked=true] small').textContent"), "3 open items")
                self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitem]'), function(e){return e.textContent})"), ["Project settings"])
                self.assertEqual(p.js("document.querySelectorAll('#project-menu [role=separator]').length"), 1)
                self.assertNotIn("New project", p.js("document.querySelector('#project-menu').textContent"), "no item that leads nowhere")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#project-menu')", "Esc closed it")
                p.until("document.activeElement.id === 'project-name'", "focus is back on the name")

    def test_C_choosing_a_project_changes_the_address_and_says_so(self):
        self.rig.httpd.projects = lambda: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("document.querySelectorAll('#project-menu [role=menuitemradio]')[1].click()")
            p.until("/p=ABC/.test(location.hash)", "the address names the chosen project")
            p.until("!!document.querySelector('.toast-text')", "the toast")
            self.assertEqual(p.js("document.querySelector('.toast-text').textContent"), "Switched to Second Programme")

    def test_C_Project_settings_opens_Settings(self):
        self.rig.httpd.projects = lambda: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("document.querySelector('#project-menu [role=menuitem]').click()")
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

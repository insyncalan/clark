"""A-D25: the project switcher in the top bar, in a real browser. With more than one project the name has a chevron and a menu of
the projects (the open one marked); choosing one changes the address; with one project the name stays plain words; a published
file shows the name as plain words and holds no switcher.

Run: python3 dev/run_tests.py test_project_switch
"""
import unittest

from test_publish_dialog import Base, WIDTHS
from test_server import chrome

TWO = [{"code": "PUB", "name": "Harbour Bridge Programme"}, {"code": "ABC", "name": "Second Programme"}]


class ProjectSwitch(Base):
    def test_C_one_project_shows_plain_words(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('.tabs .tab')", "the page is drawn")
            self.assertEqual(p.js("document.querySelector('#project-name').textContent"), 'Bridge & "Harbour" <Programme>')
            self.assertEqual(p.js("document.querySelector('#project-name').tagName"), "SPAN", "nothing to switch to")

    def test_C_the_menu_lists_the_projects_and_marks_the_open_one(self):
        self.rig.httpd.projects = lambda: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the name is a menu button")
            for w in WIDTHS:
                p.width(w)
                self.assertEqual(p.js("document.querySelector('#project-name').getAttribute('aria-haspopup')"), "menu")
                self.assertTrue(p.js("!!document.querySelector('#project-name .nch')"), "a chevron")
                self.assertTrue(p.js("document.querySelector('#project-name').getBoundingClientRect().width > 40"), "visible at this width")
                p.js("document.querySelector('#project-name').click()")
                p.until("!!document.querySelector('#project-menu')", "the menu opened")
                self.assertEqual(p.js("[].map.call(document.querySelectorAll('#project-menu [role=menuitemradio]'), function(e){return e.textContent.replace('✓','')})"),
                                 ["Harbour Bridge Programme", "Second Programme"])
                self.assertEqual(p.js("document.querySelector('#project-menu [aria-checked=true]').textContent.replace('✓','')"), "Harbour Bridge Programme")
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#project-menu')", "Esc closed it")
                p.until("document.activeElement.id === 'project-name'", "focus is back on the name")

    def test_C_choosing_a_project_changes_the_address(self):
        self.rig.httpd.projects = lambda: TWO
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("document.querySelector('#project-name').tagName === 'BUTTON'", "the menu button")
            p.js("document.querySelector('#project-name').click()")
            p.until("!!document.querySelector('#project-menu')", "open")
            p.js("document.querySelectorAll('#project-menu [role=menuitemradio]')[1].click()")
            p.until("/p=ABC/.test(location.hash)", "the address names the chosen project")


if __name__ == "__main__":
    unittest.main()

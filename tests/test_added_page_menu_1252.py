"""Row 1252 slice 4a: the editor shows an added page as a tab in the top bar and draws its sections. The tab is named as the page is named, sits
after the Gantt tab (or after Use cases while the Gantt is off) in the menu's order, and is left out while the page is hidden from the menu. Its
address is page:<id>; a page that is gone or hidden opens the Dashboard. Classic, 1400 and 900 only. Fictional data only.

Run: python3 dev/run_tests.py test_added_page_menu_1252
"""
import json
import sqlite3
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

SECS = json.dumps([{"id": "s1", "type": "text", "title": "Supplier notes head", "body": "<p>Supplier notes body text</p>"}])
TABS = "[...document.querySelectorAll('.top .tabs .tab')].map(t => t.textContent.trim())"


class AddedPageTab(Base):
    def add(self, name, **values):
        status, body = self.real_change({"project": "ABC", "kind": "added_pages", "op": "new",
                                         "values": {"name": name, "starter": "blank", "sections": SECS, **values}})
        self.assertEqual(status, 200, body)
        return self.store.read("added_pages", project="ABC")[-1]["id"]

    def open(self, cdp, width, hash_="#dashboard&p=ABC"):
        p = self.visit(cdp, hash_)
        size(cdp, p, width, 800)
        p.until("document.querySelectorAll('.top .tabs .tab').length >= 4", "the tabs show")
        return p

    def check_tab(self, width):
        pid = self.add("Supplier status")
        self.add("Secret page", hidden=1)
        with chrome() as cdp:
            p = self.open(cdp, width)
            tabs = p.js(TABS)
            self.assertEqual(tabs[-1], "Supplier status", tabs)
            self.assertNotIn("Secret page", tabs)
            self.assertEqual(tabs[:4], ["Dashboard", "Work items", "Milestones", "Use cases"], tabs)
            p.js("[...document.querySelectorAll('.top .tabs .tab')].filter(t => t.textContent.trim() === 'Supplier status')[0].click()")
            p.until("[...document.querySelectorAll('.top .tabs .tab')].some(t => t.textContent.trim() === 'Supplier status' && t.getAttribute('aria-selected') === 'true')", "the tab is selected")
            p.until("document.body.textContent.includes('Supplier notes body text')", "its section is drawn")
            self.assertEqual(p.js("location.hash.split('&')[0]"), "#page:" + pid)
            self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, "no sideways scroll")

    def test_tab_1400(self):
        self.check_tab(1400)

    def test_tab_900(self):
        self.check_tab(900)

    def test_after_gantt_in_order(self):
        self.add("Alpha page")
        self.add("Beta page")
        with sqlite3.connect(str(self.store.path)) as con:
            con.execute("UPDATE projects SET show_gantt_editor = 1 WHERE code = 'ABC'")
        with chrome() as cdp:
            p = self.open(cdp, 1400)
            tabs = p.js(TABS)
            self.assertEqual(tabs[-3:], ["Gantt", "Alpha page", "Beta page"], tabs)

    def test_address_opens_the_page_and_a_hidden_one_falls_back(self):
        pid = self.add("Supplier status")
        gone = self.add("Hidden page", hidden=1)
        with chrome() as cdp:
            p = self.open(cdp, 1400, "#page:%s&p=ABC" % pid)
            p.until("document.body.textContent.includes('Supplier notes body text')", "the address opens the page")
            p = self.open(cdp, 1400, "#page:%s&p=ABC" % gone)
            p.until("!!document.querySelector('#report')", "the dashboard")
            self.assertFalse(p.js("document.body.textContent.includes('Supplier notes body text')"))


if __name__ == "__main__":
    unittest.main()

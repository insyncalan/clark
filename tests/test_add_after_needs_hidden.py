"""Item 1174: the Add a section box counts only the sections the Dashboard draws. A Needs from you section that is still stored
(item 1158) sits in the store between two drawn sections but is never drawn, so Add after the section above it must put the new
section directly after that one as the person sees it, and the box must not offer the Needs section as a place.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_add_after_needs_hidden
Needs Chrome (the harness of test_report_editor): the page clark serves, the real change route, a real store with fictional data.
The store has the eleven default sections plus a stored Needs section placed between the first and the second.
"""
import sqlite3
import unittest

from _demo import USER  # noqa: F401
from test_report_editor import Base, IDS
from test_server import chrome

FIRST, NEEDS = "ABC-S-001", "ABC-S-500"
OPEN = "document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: %r, opener: document.activeElement}, cancelable: true, bubbles: true}))"
GONE = "That section isn't in the report any more. Reload the page."      # the words of logic/templates.js for a section that is not in the list


class AddAfterWithStoredNeeds(Base):
    def setUp(self):
        super().setUp()
        rows = {r["id"]: r["sort_order"] for r in self.store.read("report_sections", "ABC")}
        between = (rows[FIRST] + rows["ABC-S-002"]) // 2
        self.assertTrue(rows[FIRST] < between < rows["ABC-S-002"], "room between the first two sections for a stored one")
        con = sqlite3.connect(str(self.store.path))
        try:
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', ?, 'needs', 'Needs from you', ?)", (NEEDS, between))
            con.commit()
        finally:
            con.close()

    def open_box(self, p, after):
        p.js(OPEN % after)
        p.until("!!document.querySelector('[role=dialog]') && document.activeElement.matches('input[type=search]')", "the box opened")

    def test_the_stored_needs_section_is_in_the_store_and_not_on_the_page(self):
        self.assertEqual(self.ids_in_store()[:3], [FIRST, NEEDS, "ABC-S-002"])
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.assertEqual(p.ids(), IDS, "the page draws the eleven sections and not the Needs one")

    def add_after_the_first(self, width):
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.edit()
            self.open_box(p, FIRST)
            p.js("document.querySelector('button[data-place]').click()")
            p.until("document.querySelectorAll('.secs > .sec').length === 12", "added")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(p.ids()[:3], [FIRST, new, "ABC-S-002"], "directly after the first section, before the second")
            self.assertEqual([r[0] for r in self.sent], ["change"], "one request")
            self.assertEqual(self.sent[-1][1]["after"], FIRST)
            self.assertNotIn(NEEDS, p.ids())

    def test_add_after_the_first_section_lands_directly_after_it_as_the_person_sees_it_at_1400(self):
        self.add_after_the_first(1400)

    def test_add_after_the_first_section_lands_directly_after_it_as_the_person_sees_it_at_900(self):
        self.add_after_the_first(900)       # its own test: the first adds a section to the store and the requests are counted per test

    def test_the_box_does_not_offer_the_needs_section_as_a_place(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, FIRST)
            where = p.js("document.querySelector('.ad-where').textContent")
            self.assertNotIn("Needs from you", where, "the choice of place never names the Needs section")
            self.assertFalse(p.js("document.querySelector('input[name=where][value=beside]').disabled"), "beside the first section is offered")
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("!document.querySelector('[role=dialog]')", "closed")
            self.open_box(p, NEEDS)                                        # asked for the Needs section itself: it is not there to place after
            self.assertTrue(p.js("document.querySelector('input[name=where][value=beside]').disabled"))
            self.assertEqual(p.js("document.getElementById('ad-w-why').textContent"), GONE)


if __name__ == "__main__":
    unittest.main()

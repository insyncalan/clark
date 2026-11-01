"""#454: Settings › People, the card of the prototype (system/prototype/views.js, "People"), in a real browser against the real people
routes (desktop widths 1400 and 900 only): the table of everyone who owns a work item or a milestone, the line saying how many need
details with Show only these, and Paste from Excel with its preview and its plain-words refusals.

Run: python3 dev/run_tests.py test_people_card
The Excel import of work items (the buttons, the box, Check the import) is not this card's: it follows #444 and #449.
Chrome is required: fails, never skips. The server's half (one step, the same checks, nothing published) is test_people_paste_route.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_page import navigate
from test_server import Running, chrome, wait

from clark import changes, page, store as st

WIDTHS = (1400, 900)
DATA = {"ABC": {"project": {"code": "ABC", "name": "Example Programme", "health": "On track", "client_name": None},
                "milestones": [{"id": "ABC-M-001", "name": "Pilot live", "owner": "Zed Newman"}], "workstreams": [], "use_cases": [], "links": [],
                "actions": [{"id": "ABC-A-001", "description": "Agree the cut-over plan", "owner": "Sam Rivers"},
                            {"id": "ABC-A-002", "description": "Book the room", "owner": "Jo Park"},
                            {"id": "ABC-A-003", "description": "Nobody yet", "owner": "TBC"}], "raid": [], "decisions": [], "labels": {}}}
INTRO = "Everyone who owns a work item or a milestone. Owners are still picked by name. Add an email, organisation and role so people can be found and emailed."
PASTE = "Name\tEmail\tOrganisation\tRole\nSam Rivers\tsam.rivers@example.com\tSupplier\tDelivery lead\nZed Newman\tzed@example.com\tClient\tSponsor"


class PeopleCard(unittest.TestCase):
    def setUp(self):
        folder = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, folder, True)
        self.db = folder / "clark.db"
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Example Programme"})
            s.add_person(name="Jo Park", email="jo@example.com", organisation="Client", role="Programme manager", source="test")
            s.add_person(name="Sam Rivers", needs_details=1, source="test")
        store.close()
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        who = lambda: "tester"          # noqa: E731
        self.s.httpd.people = changes.make_people(self.db, [], who)
        self.s.httpd.people_undo = changes.make_people_undo(self.db, [], who)
        self.s.httpd.people_list = changes.make_people_list(self.db, [], who)

    def show(self, cdp):
        sid = navigate(cdp, self.s.port, "#settings&p=ABC")
        self.sid = sid
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('#ppTable')"), 20), "the People card is in Settings, with its table")
        return js

    def fill(self, js, text):
        js(f"var t = document.getElementById('ppText'); t.value = {json.dumps(text)}; t.dispatchEvent(new Event('input', {{bubbles: true}}))")

    def test_the_card_has_the_prototypes_words_table_and_count_line_at_both_widths(self):
        with chrome() as cdp:
            js = self.show(cdp)
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"no sideways scroll at {w}")
                self.assertEqual(js("var r = document.querySelector('#people').getBoundingClientRect(); r.width > 0 && r.right <= window.innerWidth"), True)
            self.assertEqual(js("document.querySelector('#people h2').innerText"), "People")
            self.assertEqual(js("document.querySelector('#people .pp-intro').innerText"), INTRO)
            self.assertEqual(js("document.querySelector('#ppPasteBtn').innerText"), "Paste from Excel")
            self.assertEqual(js("document.querySelector('#ppPaste').hidden"), True)
            self.assertEqual(js("[].map.call(document.querySelectorAll('#ppTable th'), function (h) { return h.innerText; }).join()").upper(),
                             "NAME,EMAIL,ORGANISATION,ROLE")
            self.assertEqual(js("[].map.call(document.querySelectorAll('#ppTable tbody tr'), function (r) { return r.dataset.person; }).join()"),
                             "Jo Park,Sam Rivers,Zed Newman", "the people on the list, then the owner on a milestone who is not on it; TBC is no one")
            self.assertEqual(js("document.querySelector('#ppCount span').innerText"), "2 of 3 people need details")
            self.assertEqual(js("document.querySelector('#ppOnly').innerText"), "Show only these")
            self.assertEqual(js("document.querySelectorAll('#ppTable .tag.need').length"), 0, "no chip on the rows until the list is filtered")
            js("document.querySelector('#ppOnly').click()")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('#ppTable tbody tr').length") == 2, 10))
            self.assertEqual(js("document.querySelectorAll('#ppTable .tag.need').length"), 2)
            self.assertEqual(js("document.querySelector('#ppOnly').innerText"), "Show everyone")
            self.assertEqual(js("document.querySelector('#ppOnly').getAttribute('aria-pressed')"), "true")
            js("document.querySelector('#ppOnly').click()")
            self.assertTrue(wait(lambda: js("document.querySelectorAll('#ppTable tbody tr').length") == 3, 10))

    def test_paste_from_excel_previews_adds_in_one_step_and_one_undo_takes_it_back(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('#ppPasteBtn').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ppPaste').hidden") is False, 10))
            self.assertEqual(js("document.querySelector('#ppPasteBtn').getAttribute('aria-expanded')"), "true")
            self.assertEqual(js("document.querySelector('label[for=ppText]').innerText"), "Rows from Excel: name, email, organisation, role, separated by tabs")
            self.assertEqual(js("document.querySelector('#ppText').placeholder"), "Sam Rivers[tab]sam@example.com[tab]Supplier[tab]Delivery lead")
            self.assertEqual(js("document.querySelector('#ppAdd').innerText"), "Add to the list")
            js("document.querySelector('#ppAdd').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ppMsg').innerText") == "Nothing to add. Paste rows copied from Excel: name, email, organisation, role.", 10))
            self.fill(js, PASTE)
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ppPreview')"), 10), "a preview of the rows")
            self.assertEqual(js("document.querySelector('.pp-plan').innerText"), "1 will be added, 1 will be updated.")
            self.assertEqual(js("document.querySelectorAll('#ppPreview tbody tr').length"), 2, "the heading row is skipped")
            js("document.querySelector('#ppAdd').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ppCount span').innerText") == "0 of 3 people need details", 20))
            self.assertIn("sam.rivers@example.com", js("document.querySelector('[data-person=\"Sam Rivers\"]').innerText"))
            self.assertIn("Sponsor", js("document.querySelector('[data-person=\"Zed Newman\"]').innerText"))
            self.assertEqual(js("document.querySelector('#ppPaste').hidden"), True)
            self.assertTrue(wait(lambda: (js("document.querySelector('#ppDone').innerText") or "").startswith("2 people updated"), 10), "said in the card, in View too")
            store = st.open_store(self.db, onedrive_roots=[])
            try:
                self.assertEqual(sorted(p["name"] for p in store.people(archived=None)), ["Jo Park", "Sam Rivers", "Zed Newman"])
                steps = store.con.execute("SELECT count(DISTINCT apply_id) FROM change_log WHERE tbl = 'people' AND apply_id > 1").fetchone()[0]
            finally:
                store.close()
            self.assertEqual(steps, 1, "the whole paste is one step")
            js("document.querySelector('#ppUndo').click()")
            self.assertTrue(wait(lambda: js("document.querySelector('#ppCount span').innerText") == "2 of 3 people need details", 20))
            self.assertEqual(js("document.querySelector('[data-person=\"Zed Newman\"]').innerText.indexOf('zed@example.com')"), -1)
            self.assertTrue(wait(lambda: (js("document.querySelector('#ppDone').innerText") or "").startswith("Undone."), 10))

    def test_a_bad_row_is_named_in_plain_words_and_nothing_is_added(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('#ppPasteBtn').click()")
            self.fill(js, "Li Wen\tli wen@example.com\tClient\tAnalyst\nSam Rivers\tjo@example.com")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ppBad')"), 10))
            bad = js("[].map.call(document.querySelectorAll('#ppBad li'), function (l) { return l.innerText; })")
            self.assertTrue(bad[0].startswith("Row 1: that email can't be used"), bad)
            self.assertEqual(bad[1], "Row 2: that email already belongs to Jo Park. Check the address and try again.")
            js("document.querySelector('#ppAdd').click()")
            self.assertTrue(wait(lambda: "2 rows need fixing" in (js("document.querySelector('#ppMsg').innerText") or ""), 10))
            self.assertEqual(js("document.querySelector('#ppCount span').innerText"), "2 of 3 people need details")
            store = st.open_store(self.db, onedrive_roots=[])
            try:
                self.assertEqual(len(store.people(archived=None)), 2)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()

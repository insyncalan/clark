"""#455: the Dashboard's use case summary in Edit follows the prototype: a status button on each row, the headline and the name changed
in place, the growing Add button with its box "Add a use case", and "Add a use case from your project record (N)".

Run: python3 dev/run_tests.py test_uc_dashboard_edit
Same harness and fictional data as test_glance_page (two use cases on the dashboard, 1.1 and 1.2), with two more that are not on it.
The page is the committed one, served over a real store, so every change is checked in the store. Laptop widths only: 1400 and 900 px,
light and dark. A published file is opened from file:// and checked for nothing of Edit.
"""
import json
import unittest

from _demo import USER
from test_glance_page import Published, Setup, tearDownModule  # noqa: F401
from test_server import chrome

PICKER = "Add a use case from your project record"


class Edit(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.uc3 = st.create("use_cases", {"project": "ABC", "title": "Supplier portal", "status": "High risk", "ref": "1.10", "sort_order": 3,
                                               "headline": "No login for the smallest suppliers", "client_visible": 0, "source": "demo"})
            self.uc4 = st.create("use_cases", {"project": "ABC", "title": "Month end close", "status": "On track", "ref": "2.1", "sort_order": 4,
                                               "headline": "Done in two days", "client_visible": 0, "source": "demo"})

    def edit(self, cdp, width=1400, dark=False):
        p = self.show(cdp, width, dark)
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit shows the status buttons")
        return p

    def row(self, uc):
        return self.store.read("use_cases", ref=uc)

    def click(self, p, selector):
        p.js(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def type_in(self, p, selector, text):
        p.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); e.focus(); e.select(); }})()")
        p.cdp.call("Input.insertText", {"text": text}, p.sid)

    def test_view_has_none_of_it_and_edit_has_the_button_the_status_buttons_and_the_link(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    self.assertEqual(p.js("document.querySelectorAll('.uc textarea, #ucAdd, [data-uc-status], [data-uc-back]').length"), 0, "View has none of Edit's parts")
                    p.js("document.querySelector('[data-mode=edit]').click()")
                    p.until("!!document.querySelector('.uc [data-uc-status]')", "Edit")
                    self.assertEqual(p.js("document.querySelectorAll('.uc [data-uc-status]').length"), 2)
                    self.assertEqual(p.js("document.querySelectorAll('.ucrow textarea.uchead-in').length"), 2)
                    self.assertEqual(p.js("document.querySelector('#ucAdd').getAttribute('aria-label')"), "Add use case")
                    self.assertEqual(p.js("document.querySelector('[data-uc-back]').textContent"), "+ Add a use case from your project record (2)")
                    self.assertEqual(p.js("document.querySelector('[data-uc-status] button').getAttribute('aria-label')"), "Status: On track. Change")

    def test_the_add_button_is_a_plus_that_grows_to_its_words_on_the_pointer_and_the_keyboard(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            width = lambda: p.js("document.querySelector('#ucAdd').getBoundingClientRect().width")
            rest = width()
            self.assertLess(rest, 40, "a plus at rest")
            p.js("document.querySelector('#ucAdd').focus()")
            p.until("document.querySelector('#ucAdd').getBoundingClientRect().width > 90", "it grew with the keyboard on it")
            self.assertEqual(p.js("document.querySelector('#ucAdd .w').textContent"), "Add use case")

    def test_the_status_menu_changes_the_status_in_one_step_with_undo(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            before = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            self.click(p, "[data-uc-status] button")
            p.until("!!document.querySelector('[role=menu] [data-kind=\"High risk\"]')", "the three words")
            self.assertEqual(p.js("[...document.querySelectorAll('[role=menu] [role=menuitemradio]')].map(b => b.textContent)"), ["On track", "Flag", "High risk"])
            p.js("document.querySelector('[role=menu] [data-kind=\"High risk\"]').click()")
            p.saved()
            self.assertEqual(self.row(self.demo.use_case)["status"], "High risk")
            self.assertEqual(p.toast(), "Use case 1.1 set to High risk.")
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], before + 1)
            self.assertEqual(p.js("document.querySelector('[data-uc-status] .ucword').textContent"), "High risk")
            self.undo(p)
            self.assertEqual(self.row(self.demo.use_case)["status"], "On track")

    def test_the_headline_and_the_name_change_in_place_and_a_press_in_them_does_not_open_the_row(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, ".ucrow .uchead-in")
            self.assertEqual(p.js("!!document.querySelector('.ucdetail')"), False, "a press in the headline leaves the row shut")
            self.type_in(p, ".ucrow .uchead-in", "Live for three suppliers")
            p.js("document.querySelector('.ucrow .uchead-in').blur()")
            p.saved()
            self.assertEqual(self.row(self.demo.use_case)["headline"], "Live for three suppliers")
            self.assertEqual(p.toast(), "Use case 1.1 saved.")
            self.click(p, ".ucrow .ucref")
            p.until("!!document.querySelector('.ucdetail .ucx-in')", "the row opened with its name")
            self.assertEqual(p.js("document.querySelector('.ucdetail .ucx-ref').textContent"), "Use case 1.1:")
            self.type_in(p, ".ucdetail .ucx-in", "Invoice matching, live")
            p.js("document.querySelector('.ucdetail .ucx-in').blur()")
            p.saved()
            self.assertEqual(self.row(self.demo.use_case)["title"], "Invoice matching, live")
            self.assertEqual(p.js("!!document.querySelector('.ucdetail')"), True, "the row stays open after a save")

    def test_add_use_case_opens_the_box_adds_it_on_the_dashboard_and_opens_its_row(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            self.click(p, "#ucAdd")
            p.until("!!document.querySelector('#ucF')", "the box")
            self.assertEqual(p.js("document.querySelector('#ucm-title').textContent"), "Add a use case")
            self.assertEqual(p.js("[...document.querySelectorAll('#ucF label')].map(l => l.textContent)"), ["ID", "Use case", "Status", "Headline"])
            self.assertEqual(p.js("document.activeElement.id"), "ucI")
            self.type_in(p, "#ucI", "3.1")
            self.type_in(p, "#ucT", "Report checks")
            p.js("document.querySelector('#ucS').value = 'Flag'")
            self.type_in(p, "#ucH", "Two checks left")
            p.js("document.querySelector('#ucF').requestSubmit()")
            p.until("!document.querySelector('#ucF')", "the box closed")
            p.saved()
            made = {r["ref"]: r for r in self.store.read("use_cases", "ABC")}["3.1"]
            self.assertEqual((made["title"], made["status"], made["headline"], made["client_visible"]), ("Report checks", "Flag", "Two checks left", 1))
            p.until("document.querySelectorAll('.ucrow').length === 3", "the row is on the dashboard")
            p.until("!!document.querySelector('.ucdetail .ucx-in')", "its row opened")
            self.assertEqual(p.js("document.querySelector('.uctotal').textContent"), "3 use cases")

    def test_an_id_already_used_is_not_added(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            before = len(self.store.read("use_cases", "ABC"))
            self.click(p, "#ucAdd")
            p.until("!!document.querySelector('#ucF')", "the box")
            self.type_in(p, "#ucI", "1.2")
            self.type_in(p, "#ucT", "Same ID again")
            p.js("document.querySelector('#ucF').requestSubmit()")
            self.assertEqual(len(self.store.read("use_cases", "ABC")), before, "nothing was added")
            self.assertEqual(p.js("!!document.querySelector('#ucF')"), True, "the box stays")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ucF')", "Esc closed the box")

    def test_add_from_your_project_record_offers_the_use_cases_that_are_off_and_puts_them_on(self):
        with chrome() as cdp:
            p = self.edit(cdp)
            before = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            self.click(p, "[data-uc-back]")
            p.until("!!document.querySelector('form.picker')", "the picker")
            self.assertEqual(p.js("document.querySelector('form.picker h2').textContent"), PICKER)
            self.assertEqual(p.js("document.querySelectorAll('form.picker .pick li').length"), 2)
            self.assertEqual(p.js("document.querySelector('form.picker input[type=search]').placeholder"), "Search by name, ID, owner or use case")
            p.js("document.querySelector('form.picker .pick input[value=\"%s\"]').click()" % self.uc3)
            p.js("document.querySelector('form.picker button[type=submit]').click()")
            p.until("!document.querySelector('form.picker')", "the picker closed")
            p.saved()
            self.assertEqual(self.row(self.uc3)["client_visible"], 1)
            self.assertEqual(self.row(self.uc4)["client_visible"], 0)
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], before + 1, "one step")
            p.until("document.querySelectorAll('.ucrow').length === 3", "the row is on the dashboard")
            self.assertEqual(p.js("document.querySelector('[data-uc-back]').textContent"), "+ Add a use case from your project record (1)")

    def undo(self, p):
        p.js("document.querySelector('[data-undo]').click()")
        p.until("!document.querySelector('[data-undo]')", "undone")


class PublishedFile(Published):
    def test_the_file_has_none_of_edit_for_the_use_cases(self):
        path = self.publish()
        text = path.read_text(encoding="utf-8")
        for edit_only in ("Add a use case", "Add use case", "from your project record", "data-uc-back", "uchead-in"):
            self.assertNotIn(edit_only, text, edit_only)
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertEqual(p.js("document.querySelectorAll('#ucAdd, [data-uc-status], [data-uc-back], .uc textarea, .uc button').length"), 0)


if __name__ == "__main__":
    unittest.main()

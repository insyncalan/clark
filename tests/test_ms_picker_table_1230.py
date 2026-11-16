"""Row 1230 (4)(5): the add-a-milestone picker as a twin of the use-case picker (components/PickerTable.jsx, PickerFilters.jsx, logic/msPicker.js).

Run: python3 dev/run_tests.py test_ms_picker_table_1230
Same page, store and data as test_milestones_eye (three milestones on project ABC). Two are made not shown: Training done is taken off with the eye,
Go live is not for the client. Widths 1400 and 900 only. The empty state and the keyboard are not walked here.
"""
import json
import unittest

from _demo import USER

import test_milestones_eye as base
from test_server import chrome
from test_work_items import page_target  # noqa: F401

Q = "document.querySelector('form.picker')"
ROWS = "document.querySelectorAll('form.picker tbody tr').length"
RESULT = "document.querySelector('form.picker [data-result]').textContent"
COUNT = "document.querySelector('form.picker .pk-foot [aria-live]:not([data-result])').textContent"
SUBMIT = "document.querySelector('form.picker button[type=submit]')"
IDS = "[...document.querySelectorAll('form.picker tbody tr')].map((r) => r.dataset.id).join()"


class MsPicker(unittest.TestCase):
    setUp = base.Editor.setUp
    visit = base.Editor.visit
    js = base.Editor.js
    until = base.Editor.until
    key = base.Editor.key
    store_hide = base.Editor.store_hide
    sent_changes = base.Editor.sent_changes
    left_out = base.Editor.left_out

    def two_off(self):
        if "ABC-M-002" not in self.left_out():
            self.store_hide("ABC-M-002")
        have = [m for m in self.store.data_for("ABC")["milestones"] if m["name"] == "Go live"]
        with self.store.step("dashboard", USER) as st:
            if have:
                st.update("milestones", have[0]["id"], {"client_visible": 0})
            else:
                st.create("milestones", {"project": "ABC", "name": "Go live", "baseline_date": "2029-12-01", "client_visible": 0, "percent_complete": 40, "source": "demo"})

    def opened(self, cdp, width=1400):
        self.two_off()                  # the Add in one width puts them back, so each opening starts from the same two
        self.visit(cdp, width=width)
        self.js("document.querySelector('.secs [data-ms-back]').click()")
        self.until("!!" + Q + " && !!document.querySelector('form.picker tbody tr')", "the picker with its table", 20)
        self.until("!!document.activeElement && !!document.activeElement.closest('form.picker')", "focus went into the picker")

    def test_the_table_its_words_and_its_footer_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.opened(cdp, width)
                self.assertEqual(self.js("document.querySelector('form.picker h2').textContent"), "Add a milestone from your project record")
                self.assertEqual(self.js("document.querySelector('form.picker input[type=search]').placeholder"), "Search by name, ID or state")
                self.assertEqual(self.js("[...document.querySelectorAll('form.picker thead th')].map((h) => h.textContent).join('|')"),
                                 "|Milestone|State|Agreed|Expected or achieved|Progress|Where it is|ID")
                self.assertEqual(self.js("!!document.querySelector('form.picker thead input[type=checkbox]')"), True, "the header tick")
                self.assertEqual(self.js("[...document.querySelectorAll('form.picker button')].some((b) => b.textContent === 'Select all shown')"), False, "the tick is the select-all")
                self.assertEqual(self.js(IDS), "ABC-M-004,ABC-M-002", "earliest agreed date first")
                cells = self.js("[...document.querySelectorAll('form.picker tbody tr')].map((r) => [...r.querySelectorAll('td')].slice(1).map((d) => d.textContent).join('|'))")
                self.assertEqual(cells, ["Go live|On track|01-12-2029|01-12-2029|40%|On the page, not shown to the client|ABC-M-004",
                                         "Training done|On track|01-04-2030|01-04-2030||Taken off the page|ABC-M-002"])
                self.assertEqual(self.js(RESULT), "Result: 2 of 2 shown")
                self.assertEqual(self.js(COUNT), "None selected")
                self.assertEqual(self.js(SUBMIT + ".textContent"), "Add selected")
                self.assertEqual(self.js(SUBMIT + ".disabled"), True)
                self.assertEqual(self.js("document.querySelector('form.picker').getBoundingClientRect().right <= window.innerWidth"), True, "fits the window")
                self.assertEqual(self.js("document.activeElement === document.querySelector('form.picker input[type=search]')"), True, "focus in the search")

    def test_the_filter_panel_fields_values_and_badge_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.opened(cdp, width)
                self.assertEqual(self.js("!!document.querySelector('[data-badge]')"), False)
                self.js("document.querySelector('[data-filter]').click()")
                self.until("!!document.querySelector('.pkt-panel')", "the panel")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-fields > li')].map((l) => l.textContent).join()"), "Status,Due,More fields,On the page,Client-visible")
                self.js("document.querySelector('.pkt-panel [data-field=agreed]').click()")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts label')].map((l) => l.textContent).join()"), "01-12-20291,01-04-20301", "Due, earliest first (not by the digits as text), with counts")
                self.js("document.querySelector('.pkt-panel [data-field=onPage]').click()")
                self.js("document.querySelector('.pkt-panel input[value=\"No\"]').click()")
                self.until("document.querySelector('[data-badge]') && document.querySelector('[data-badge]').textContent === '1'", "the badge says 1")
                self.assertEqual(self.js(IDS), "ABC-M-002")
                self.assertEqual(self.js(RESULT), "Result: 1 of 2 shown")
                self.js("document.querySelector('.pkt-panel [data-not=\"1\"]').click()")
                self.until(ROWS + " === 1 && " + IDS + " === 'ABC-M-004'", "is not any of keeps the other")
                self.js("document.querySelector('.pkt-panel [data-field=client]').click()")
                self.js("document.querySelector('.pkt-panel [data-all]').click()")
                self.until("document.querySelector('[data-badge]').textContent === '2'", "two fields filter")
                self.js("document.querySelector('.pkt-panel [data-done]').click()")
                self.until("!document.querySelector('.pkt-panel')", "Done closed the panel")

    def test_search_header_tick_row_click_and_add_bring_them_back_with_one_toast(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                del self.sent[:]
                self.opened(cdp, width)
                self.js("(() => { const i = document.querySelector('form.picker input[type=search]'); i.value = 'm-004'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
                self.until(ROWS + " === 1", "search by ID")
                self.js("(() => { const i = document.querySelector('form.picker input[type=search]'); i.value = 'on track'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
                self.until(ROWS + " === 2", "search by state")
                self.js("document.querySelector('form.picker tbody tr td:nth-child(3)').click()")       # a click on the row ticks it
                self.until(COUNT + " === '1 selected'", "the row ticked")
                self.until("document.querySelector('form.picker thead input').indeterminate === true", "some, not all: the tick is half")
                self.js("document.querySelector('form.picker thead input').click()")
                self.until(COUNT + " === '2 selected'", "the header tick picks every one shown")
                self.assertEqual(self.js(SUBMIT + ".textContent"), "Add 2")
                self.js("document.querySelector('form.picker thead input').click()")
                self.until(COUNT + " === 'None selected'", "and again takes them off")
                self.js("document.querySelector('form.picker thead input').click()")
                self.until(COUNT + " === '2 selected'", "all again")
                self.js(SUBMIT + ".click()")
                self.until("!" + Q, "the picker closed")
                self.until("document.querySelectorAll('.secs .msl-row').length === 4", "both are on the Dashboard")
                self.assertEqual(self.sent_changes(), [{"project": "ABC", "kind": "report_hidden", "op": "pick", "ids": ["ABC-M-004", "ABC-M-002"], "place": "report"}])
                self.assertEqual(self.js("document.querySelector('.toast .toast-text').textContent"), "2 milestones added to the page.")

    def test_cancel_esc_and_a_click_outside_close_it_and_send_nothing(self):
        with chrome() as cdp:
            self.opened(cdp)
            self.js("document.querySelector('form.picker tbody input').click()")
            self.js("[...document.querySelectorAll('form.picker button')].find((b) => b.textContent === 'Cancel').click()")
            self.until("!" + Q, "Cancel closed it")
            self.js("document.querySelector('.secs [data-ms-back]').click()")
            self.until("!!" + Q + " && !!document.activeElement.closest('form.picker')", "again, with focus in it")
            self.key("Escape", "Escape", 27)
            self.until("!" + Q, "Esc closed it")
            self.js("document.querySelector('.secs [data-ms-back]').click()")
            self.until("!!" + Q, "again")
            for kind in ("mousePressed", "mouseReleased"):
                self.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": 4, "y": 4, "button": "left", "clickCount": 1}, self.sid)
            self.until("!" + Q, "a click outside closed it")
            self.assertEqual(self.sent, [])
            self.assertEqual(sorted(self.left_out()), ["ABC-M-002"])


if __name__ == "__main__":
    unittest.main()

"""Row 1230 (4)(5): the add-a-milestone picker as a twin of the use-case picker (components/PickerTable.jsx, PickerFilters.jsx, logic/msPicker.js).

Run: python3 dev/run_tests.py test_ms_picker_table_1230
Same page, store and data as test_milestones_eye (three milestones on project ABC). Two are made not shown: Training done is taken off with the eye,
Go live is not for the client. Widths 1400 and 900 only. The empty state and the keyboard are not walked here.
"""
import datetime
import json
import unittest

from _demo import USER

import _testpage as testpage
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
                self.assertEqual(self.js("[...document.querySelectorAll('form.picker tbody input')].map((i) => i.getAttribute('aria-label')).join()"), "Add Go live,Add Training done")
                cells = self.js("[...document.querySelectorAll('form.picker tbody tr')].map((r) => [...r.querySelectorAll('td')].slice(1).map((d) => d.textContent).join('|'))")
                self.assertEqual(cells, ["Go live|On track|01-12-2029|01-12-2029|40%|Not on the page|ABC-M-004",
                                         "Training done|On track|01-04-2030|01-04-2030||Taken off with the eye|ABC-M-002"])
                self.assertEqual(self.js("[...document.querySelectorAll('form.picker tbody tr')].every((r) => !!r.querySelector('td:nth-child(2) svg.ms-i'))"), True, "the state mark leads the Milestone cell")
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
                self.assertEqual(self.js("document.querySelector('[data-filter]').textContent"), "Filters")
                self.js("document.querySelector('[data-filter]').click()")
                self.until("!!document.querySelector('.pkt-panel')", "the panel")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-fields > li:not(.pkt-find)')].map((l) => l.textContent).join()"), "Status,Due,More fields,On the page,Client visible")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts label')].map((l) => l.textContent).join()"),
                                 "Achieved0,On track2,At risk0,Slipped0,Overdue0,Forecast0,Cancelled0", "Status: every state, 0 where none holds it")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts label.zero input')].every((i) => i.disabled)"), True, "a state with none is greyed and cannot be ticked")
                self.js("document.querySelector('.pkt-panel [data-field=agreed]').click()")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts label')].map((l) => l.textContent).join()"), "Overdue0,Due in 7 days0,No date0,Later2", "Due: the Work items buckets, in their order")
                self.js("document.querySelector('.pkt-panel [data-field=onPage]').click()")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts label')].map((l) => l.textContent).join()"), "Not on the page1,Taken off with the eye1", "the On the page values are the Where it is words")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-values .isnot')[0].children].map((b) => b.textContent).join()"), "is,is not,any of", "the match: is and is not as two buttons, then any of")
                self.assertEqual(self.js("document.querySelectorAll('.pkt-values .isnot button').length"), 2)
                self.assertEqual(self.js("document.querySelector('.pkt-panel [data-find]').placeholder"), "Find a field\u2026")
                self.js("document.querySelector('.pkt-panel input[value=\"Taken off with the eye\"]').click()")
                self.assertEqual(self.js("document.querySelector('[data-field=onPage] [data-set]').textContent"), "set", "the field that has a filter says set")
                self.assertEqual(self.js("document.querySelector('[data-field=client] [data-set]')"), None, "and the others do not")
                self.assertEqual(self.js("document.querySelector('[data-filter]').textContent"), "Filters, 1 on1", "the icon's name carries the count")
                self.until("document.querySelector('[data-badge]') && document.querySelector('[data-badge]').textContent === '1'", "the badge says 1")
                self.assertEqual(self.js(IDS), "ABC-M-002")
                self.assertEqual(self.js(RESULT), "Result: 1 of 2 shown")
                self.js("document.querySelector('.pkt-panel [data-not=\"1\"]').click()")
                self.until(ROWS + " === 1 && " + IDS + " === 'ABC-M-004'", "is not any of keeps the other")
                self.js("(() => { const i = document.querySelector('.pkt-panel [data-find]'); i.value = 'client'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-fields > li:not(.pkt-find)')].filter((l) => !l.querySelector('input')).map((l) => l.textContent).join()"), "More fields,Client visible", "Find a field narrows the list")
                self.js("document.querySelector('.pkt-panel [data-field=client]').click()")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts label')].map((l) => l.textContent).join()"), "Shown to the client1,Internal only1", "Client visible values")
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

    def extras(self, cdp, rows):
        self.visit(cdp)
        today = datetime.date.fromisoformat(self.js("new Date().toLocaleDateString('en-CA')"))        # the browser's day, which is not always the host's
        with self.store.step("dashboard", USER) as st:
            for name, days, extra in rows:
                day = (today + datetime.timedelta(days=days)).isoformat()
                st.create("milestones", {"project": "ABC", "name": name, "baseline_date": day, "source": "demo", **extra})
        for m in self.store.data_for("ABC")["milestones"]:
            if m["name"] in [r[0] for r in rows]:
                self.store_hide(m["id"])            # off the page, so the picker offers it

    def names(self):
        return self.js("[...document.querySelectorAll('form.picker tbody tr')].map((r) => r.querySelector('td:nth-child(2)').textContent).sort().join()")

    def filter_on(self, field, value):
        self.js("document.querySelector('[data-filter]').click()")
        self.until("!!document.querySelector('.pkt-panel')", "the panel")
        self.js("document.querySelector('.pkt-panel [data-field=%s]').click()" % field)
        self.js("document.querySelector('.pkt-panel input[value=\"%s\"]').click()" % value)

    def test_the_due_filter_keeps_the_rows_in_each_bucket_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                if width == 1400:
                    self.extras(cdp, [("Past due", -5, {}), ("In three days", 3, {}), ("In seven days", 7, {}), ("In twenty days", 20, {})])
                self.opened(cdp, width)
                self.assertEqual(self.js(ROWS), 6)
                self.filter_on("agreed", "Due in 7 days")
                self.until(ROWS + " === 2", "the 7 days bucket")
                self.assertEqual(self.names(), "In seven days,In three days", "up to 7 days ahead, not 20")
                self.js("document.querySelector('.pkt-panel input[value=\"Due in 7 days\"]').click()")
                self.js("document.querySelector('.pkt-panel input[value=\"Later\"]').click()")
                self.until(ROWS + " === 3", "the Later bucket")
                self.assertEqual(self.names(), "Go live,In twenty days,Training done")
                self.js("document.querySelector('.pkt-panel input[value=\"Later\"]').click()")
                self.js("document.querySelector('.pkt-panel input[value=\"Overdue\"]').click()")
                self.until(ROWS + " === 1", "the Overdue bucket")
                self.assertEqual(self.names(), "Past due")

    def test_the_client_visible_filter_keeps_the_rows_that_match_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.opened(cdp, width)
                self.assertEqual(self.names(), "Go live,Training done")
                self.filter_on("client", "Shown to the client")
                self.until(ROWS + " === 1", "only the one shown to the client")
                self.assertEqual(self.names(), "Training done")
                self.js("document.querySelector('.pkt-panel input[value=\"Shown to the client\"]').click()")
                self.js("document.querySelector('.pkt-panel input[value=\"Internal only\"]').click()")
                self.until(ROWS + " === 1 && " + IDS + " === 'ABC-M-004'", "only the internal one")
                self.assertEqual(self.names(), "Go live")

    def test_progress_is_held_between_0_and_100_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                if width == 1400:
                    self.extras(cdp, [("Over the top", 400, {"percent_complete": 50}), ("Below zero", 410, {"percent_complete": 50})])
                self.s.httpd.page_html = lambda: testpage.html()         # the browser tests' copy of the page, which has window.clarkPage
                self.opened(cdp, width)
                self.js("window.clarkPage.changeData((d) => ({ ...d, milestones: d.milestones.map((m) => m.name === 'Over the top' ? { ...m, percent_complete: 150 } : m.name === 'Below zero' ? { ...m, percent_complete: -20 } : m) }))")
                self.until("[...document.querySelectorAll('form.picker tbody tr')].some((r) => r.textContent.includes('100%'))", "the new progress is drawn")
                cells = self.js("Object.fromEntries([...document.querySelectorAll('form.picker tbody tr')].map((r) => [r.querySelector('td:nth-child(2)').textContent, r.querySelector('td:nth-child(6)').textContent]))")
                self.assertEqual(cells["Over the top"], "100%")
                self.assertEqual(cells["Below zero"], "0%")
                self.assertEqual(cells["Go live"], "40%")

    def test_select_all_in_the_panel_ticks_only_the_values_some_milestone_holds_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.opened(cdp, width)
                self.js("document.querySelector('[data-filter]').click()")
                self.until("!!document.querySelector('.pkt-panel')", "the panel")
                self.js("document.querySelector('.pkt-panel [data-field=state]').click()")
                self.js("document.querySelector('.pkt-panel [data-all]').click()")
                self.until("document.querySelector('[data-badge]') && document.querySelector('[data-badge]').textContent === '1'", "one field filters")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts input:checked')].map((i) => i.value).join()"), "On track", "only the state a milestone holds")
                self.assertEqual(self.js("[...document.querySelectorAll('.pkt-opts input:disabled:checked')].length"), 0, "no greyed value is ticked")
                self.assertEqual(self.js(ROWS), 2)

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

    def test_one_added_says_one_milestone_and_an_emptied_list_says_everything_is_on_the_page(self):
        with chrome() as cdp:
            del self.sent[:]
            self.opened(cdp)
            self.js("document.querySelector('form.picker tbody input').click()")
            self.until(COUNT + " === '1 selected'", "one ticked")
            self.assertEqual(self.js(SUBMIT + ".textContent"), "Add 1")
            self.js(SUBMIT + ".click()")
            self.until("!" + Q, "the picker closed")
            self.until("!!document.querySelector('.toast .toast-text')", "the toast")
            self.assertEqual(self.js("document.querySelector('.toast .toast-text').textContent"), "1 milestone added to the page.")
        self.s.httpd.page_html = lambda: testpage.html()         # the browser tests' copy of the page, which has window.clarkPage
        with chrome() as cdp:
            self.opened(cdp)
            self.assertEqual(self.js("!!document.querySelector('form.picker [data-empty]')"), False)
            self.js("window.clarkPage.changeData((d) => ({ ...d, milestones: [] }))")
            self.until("!!document.querySelector('form.picker [data-empty]')", "the empty state")
            self.assertEqual(self.js("document.querySelector('form.picker [data-empty]').textContent"), "Everything is already on the page.")
            self.assertEqual(self.js(ROWS), 0)
            self.assertEqual(self.js(SUBMIT + ".disabled"), True)

    def test_the_box_is_about_1080_wide_and_650_tall_at_1400_and_fits_at_900(self):
        for width, (wide, tall) in ((1400, (1080, 650)), (900, (None, 650))):
            with self.subTest(width=width), chrome() as cdp:
                self.opened(cdp, width)
                w = self.js("Math.round(document.querySelector('form.picker').getBoundingClientRect().width)")
                h = self.js("Math.round(document.querySelector('form.picker').getBoundingClientRect().height)")
                inner = self.js("window.innerHeight")
                if wide:
                    self.assertEqual(w, wide, "box width")
                else:
                    self.assertLessEqual(w, width, "box fits the window")
                self.assertGreaterEqual(h, min(tall, int(inner * 0.9) - 1), "box min height (650, or 90% of the window when shorter)")


if __name__ == "__main__":
    unittest.main()

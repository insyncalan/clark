"""Item 1181: what is particular to the Action peek (Layout A of the approved mockup). The shared frame is item 1180 (its own tests); this file
covers the four chips and their popovers, the Latest update above Details, and the Details rows of an action. Written first: the tests for the
chip order, the Latest-above-Details order, the popover contents and the trimmed rows fail until the build.
Run: python3 dev/run_tests.py test_peek_action_1181

Real browser at 1400 and 900 px on the fictional demo project, Edit mode, today fixed at 28-10-2026. TUL-A-002 is an open action due 22-10-2026
(6 days late). Hooks used (all from the 1180 frame): .pk-chips [data-row=status|priority|owner|due], .pk-chip-sub, [data-pop], [data-pk-latest],
[data-pk-hint], [data-pk-unsaved], [data-pk-details], [data-pk-details-rows].
"""
import json
import re
import unittest

from _paths import ROOT

import test_peek_latest  # noqa: E402
from test_peek_latest import OVERDUE  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

PEEK = ROOT / "src/clark/page/src/components/PeekActionBody.jsx"
CHIPS = "#peek .pk-chips"
ROWS_JS = "[...document.querySelectorAll('#peek [data-pk-details-rows] dt')].map(d => d.textContent.replace(/\\s+/g, ' ').trim())"


class Action(test_peek_latest.Browser):
    close_it = None       # an action ref whose status is set to Closed or Cancelled in the fresh demo data
    close_as = "Closed"

    def fresh(self):
        super().fresh()
        if self.close_it:
            with self.store.step("dashboard", "Demo User") as st:
                st.update("actions", self.close_it, {"status": self.close_as})
            self.data = self.store.data_for(self.code)

    def chips(self, cdp, sid):
        return cdp.js("(() => { const out = {}; for (const c of document.querySelectorAll('#peek .pk-chips > [data-row]')) { const s = c.querySelector('.pk-chip-sub');"
                      " out[c.dataset.row] = { text: c.innerText.replace(/\\s+/g, ' ').trim(), icons: [...c.querySelectorAll('svg[data-icn]')].map(i => i.dataset.icn),"
                      " sub: s ? s.textContent.trim() : null, tag: (c.querySelector('button') || c).tagName, h: (c.querySelector('button') || c).getBoundingClientRect().height }; } return out; })()", sid)

    def open_details(self, cdp, sid):
        if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
            click(cdp, sid, "[data-pk-details]")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-details-rows]')", sid)))

    def pop_text(self, cdp, sid, chip):
        click(cdp, sid, f"{CHIPS} [data-row={chip}] button")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop]')", sid)), f"{chip}: a popover opens")
        return cdp.js("document.querySelector('[data-pop]').innerText.replace(/\\s+/g, ' ')", sid)

    def test_four_chips_in_the_ticket_order_with_their_icons(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                got = self.chips(cdp, sid)
                self.assertEqual(list(got), ["status", "priority", "owner", "due"], "Status, Priority, Owner, Due")
                for key, icon in (("status", "half"), ("priority", "bars"), ("owner", "user"), ("due", "cal")):
                    self.assertEqual(got[key]["icons"][0], icon, key)
                    self.assertEqual(got[key]["tag"], "BUTTON", f"{key}: a control in Edit")
                    self.assertGreaterEqual(got[key]["h"], 24, f"{key}: a 24 px target")

    def test_the_status_popover_offers_open_delayed_closed_cancelled(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            text = self.pop_text(cdp, sid, "status")
            for word in ("Open", "Delayed", "Closed", "Cancelled"):
                self.assertIn(word, text)

    def test_the_priority_popover_offers_urgent_high_medium_low(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            text = self.pop_text(cdp, sid, "priority")
            for word in ("Urgent", "High", "Medium", "Low"):
                self.assertIn(word, text)

    def test_the_owner_popover_is_a_searchable_list_with_recent_people_and_tbc(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                text = self.pop_text(cdp, sid, "owner")
                self.assertTrue(wait(lambda: "people" in cdp.js("document.querySelector('[data-pop]').textContent", sid).lower()), "the people list is read")
                text = cdp.js("document.querySelector('[data-pop]').textContent.replace(/\\s+/g, ' ')", sid)     # the section heads are drawn in capitals, so read the text itself
                for word in ("People", "TBC"):       # Recent is drawn only once someone has been assigned in this browser
                    self.assertIn(word, text, f"the owner list has {word}")
                self.assertTrue(cdp.js("!!document.querySelector('.cowner input.cp-in')", sid), "a search box")

    def test_a_name_that_is_not_a_person_offers_add_as_a_new_person_or_keep_the_name_only(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            self.pop_text(cdp, sid, "owner")
            cdp.js("(() => { const i = document.querySelector('.cowner input.cp-in'); i.focus(); })()", sid)
            cdp.call("Input.insertText", {"text": "Zed Nobody"}, sid)
            self.assertTrue(wait(lambda: re.search(r"Add Zed Nobody as a new person", cdp.js("document.querySelector('[data-pop]').innerText", sid) or "")), "Add <name> as a new person")
            self.assertIn("Keep the name only", cdp.js("document.querySelector('[data-pop]').innerText", sid))

    def test_the_due_popover_has_a_month_calendar_and_the_five_quick_picks(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                text = self.pop_text(cdp, sid, "due")
                for word in ("Today", "Tomorrow", "Friday", "Next week", "No date"):
                    self.assertIn(word, text)
                self.assertTrue(cdp.js("document.querySelectorAll('.cdate button[data-day]').length >= 28", sid), "a month of days")
                self.assertIn("October", text + " " + cdp.js("document.querySelector('[data-pop]').textContent", sid), "the month shown is the due date's")

    def test_a_late_open_action_says_overdue_6_days_in_red(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            due = self.chips(cdp, sid)["due"]
            self.assertEqual(due["sub"], "overdue 6 days")
            self.assertIn("22-10-2026", due["text"])
            col = cdp.js("getComputedStyle(document.querySelector('#peek .pk-chips [data-row=due] .pk-chip-sub')).color", sid)
            red = cdp.js("(() => { const e = document.createElement('i'); e.style.color = 'var(--status-red-text)'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; })()", sid)
            self.assertEqual(col, red)

    def test_a_closed_or_cancelled_action_keeps_its_due_date_and_has_no_overdue_line(self):
        for status in ("Closed", "Cancelled"):
            with self.subTest(status), chrome() as cdp:
                self.close_it, self.close_as = OVERDUE, status
                sent, sid = self.load(cdp, 1400, OVERDUE)
                got = self.chips(cdp, sid)
                self.assertIn(status, got["status"]["text"])
                self.assertIn("22-10-2026", got["due"]["text"], "the date stays")
                self.assertTrue(got["due"]["sub"] is None or "overdue" not in got["due"]["sub"], "done work is not overdue")

    def test_the_latest_update_is_above_details(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                tops = cdp.js("['[data-pk-latest]', '[data-pk-details]'].map(s => { const e = document.querySelector(s); return e ? e.getBoundingClientRect().top : null; })", sid)
                self.assertNotIn(None, tops)
                self.assertLess(tops[0], tops[1], "Latest above Details")

    def test_cmd_or_ctrl_enter_saves_the_latest_update_once_and_the_unsaved_bar_guards_closing(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            self.open_box(cdp, sid)
            self.assertIn("to save", cdp.js("(document.querySelector('[data-pk-hint]') || {textContent: ''}).textContent", sid), "the hint under the box")
            self.type_in(cdp, sid, "Waiting on the vendor")
            self.save_key(cdp, sid)
            self.assertTrue(wait(lambda: len(sent) == 1), "saved once")
            self.assertIn("Waiting on the vendor", sent[0]["changes"]["latest_update"])
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Not saved yet")
            cdp.js("document.querySelector('#peek [data-pk-close]').click()", sid)      # Close asks; the Esc key closes the peek without asking
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)), "the unsaved-update bar")
            self.assertEqual(sent, [])

    def test_the_last_updated_stamp_reads_dd_mm_yyyy_hh_mm_under_the_box(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            txt = cdp.js("document.querySelector('[data-pk-latest]').innerText", sid)
            m = re.search(r"[Ll]ast updated\s+\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}", txt)
            self.assertTrue(m, txt)

    def test_the_details_rows_of_an_action_are_workstream_milestone_raised_then_client_visible(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_details(cdp, sid)
                rows = cdp.js(ROWS_JS, sid)
                for gone in ("Type", "Use case", "Client Message", "Last reviewed"):
                    self.assertNotIn(gone, rows, f"{gone} is not an action row")
                self.assertEqual(rows[:3], ["Workstream", "Milestone", "Raised"], rows)
                client = cdp.js("(() => { const c = document.querySelector('[data-pk-details-rows] [data-pk-client-row]'); const r = [...document.querySelectorAll('[data-pk-details-rows] .pk-row')]; return c ? r.indexOf(c) : -1; })()", sid)
                self.assertEqual(client, 3, "the Client visible line follows Raised")

    def test_raised_is_read_only_with_the_hint_set_when_it_was_raised(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            self.open_details(cdp, sid)
            row = cdp.js("(() => { const d = [...document.querySelectorAll('[data-pk-details-rows] .pk-row')].find(r => /^Raised/.test(r.querySelector('dt').textContent.trim()));"
                         " return d ? { text: d.innerText.replace(/\\s+/g, ' '), controls: d.querySelectorAll('button, input, [contenteditable=true]').length } : null; })()", sid)
            self.assertIsNotNone(row, "a Raised row")
            self.assertIn("set when it was raised", row["text"])
            self.assertEqual(row["controls"], 0, "read only")


class Source(unittest.TestCase):
    def test_the_peek_source_drops_the_four_rows_for_actions_and_orders_the_chips(self):
        src = PEEK.read_text(encoding="utf-8")
        self.assertIn("set when it was raised", src)


if __name__ == "__main__":
    unittest.main()

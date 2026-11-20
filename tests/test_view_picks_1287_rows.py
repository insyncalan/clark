"""Row 1287, killers: the Actions and Risks lists (the item rows) on the Dashboard in View pick status, owner, date and urgency
in place; the title opens the peek in full edit and is never a control. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_rows   (headless Chrome; fails, never skips, without it)
"""
import unittest

import test_tpl_workitems as T
from test_view_picks_1287_more import classic
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome


class ViewPickRows(T.InThePage):
    def section(self, kind, title):
        with self.store.step("dashboard", T.USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 1})

    def fields(self, p, row):
        return p.js(f"[...document.querySelectorAll('{row} .cell-pick')].map(e => e.dataset.cell.split(':').pop())")

    def test_actions_rows_pick_status_owner_and_date_not_the_title(self):
        classic(self)
        ref = self.section("actions", "Fictional actions")
        row = f"[data-id=\"{ref}\"] .wl-row[data-id=\"{self.a_due}\"]"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{row}')", "the actions list drew")
                self.assertEqual(sorted(self.fields(p, row)), ["due", "owner", "status"])
                self.assertEqual(p.js(f"document.querySelectorAll('{row} .c-ico .cell-pick').length"), 1, "one status picker")
                self.assertEqual(p.js(f"document.querySelectorAll('{row} .c-owner .cell-pick').length"), 1)
                self.assertEqual(p.js(f"document.querySelectorAll('{row} .c-date .cell-pick').length"), 1)
                self.assertEqual(p.js(f"document.querySelectorAll('{row} .c-title .cell-pick, {row} .c-title input, {row} .c-title textarea').length"), 0, "the title is never a control")
                p.js(f"document.querySelector('{row} .c-owner .cell-pick').click()")
                p.until("!!document.querySelector('[data-cell$=\":owner\"][aria-expanded=true]')", "the owner picker opened")
                self.assertEqual(p.js("!!document.querySelector('#peek')"), False, "a picker click does not open the peek")
                p.js("(document.activeElement || document).dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                p.until("!document.querySelector('[data-cell][aria-expanded=true]')", "the picker closed")

    def test_actions_title_opens_the_peek_in_edit_and_the_id_button_opens_it_read_only(self):
        classic(self)
        ref = self.section("actions", "Fictional actions")
        row = f"[data-id=\"{ref}\"] .wl-row[data-id=\"{self.a_due}\"]"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{row}')", "the actions list drew")
            p.js(f"document.querySelector('{row} .idl').click()")
            p.until(f"((document.querySelector('#peek') || {{dataset: {{}}}}).dataset.peek || '') === '{self.a_due}'", "the peek opened")
            self.assertEqual(p.js("!!document.querySelector('#peek [data-cell], #peek .cell-pick')"), False, "the ID button opens the read only peek")
            p.js(f"document.querySelector('{row} .c-title').click()")
            p.until("!!document.querySelector('#peek [data-cell], #peek .cell-pick')", "the title opens the editable peek")
            p.js(f"document.querySelector('{row} .idl').click()")
            p.until("!document.querySelector('#peek [data-cell], #peek .cell-pick')", "another open clears the edit")

    def test_risks_rows_pick_the_urgency_too(self):
        classic(self)
        ref = self.section("raid", "Fictional risks")
        row = f"[data-id=\"{ref}\"] .wl-row[data-id=\"{self.risk}\"]"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{row}')", "the risks list drew")
            self.assertEqual(self.fields(p, row).count("priority"), 1)
            self.assertEqual(p.js(f"document.querySelectorAll('{row} .c-prio .cell-pick').length"), 1)

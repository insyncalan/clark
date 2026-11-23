"""Row 1287, writes: a pick made in View saves one step (the store, the row), Undo puts it back; an empty owner or date says "none";
Cancelled and Delayed read in View; Previous and Next leave the full edit peek. Fictional data only.

Run: python3 dev/run_tests.py test_view_picks_1287_writes   (headless Chrome; fails, never skips, without it)
"""
import json
import unittest

import test_tpl_workitems as T
from test_report_editor import Pg, tearDownModule  # noqa: F401
from test_server import chrome
from test_view_picks_1287_more import classic


class ViewPickWrites(T.InThePage):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", T.USER) as st:       # a new project has Work items lists, not the Actions section (row 1193): these tests read the Actions rows, so the section is made
            st.create("report_sections", {"project": "ABC", "type": "actions", "title": "Open actions", "sort_order": 50, "hidden": 0})

    def steps(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def said(self, p, cell):
        return p.js(f"document.querySelector('{cell}').getAttribute('aria-label')")

    def test_a_status_pick_in_view_saves_one_step_and_undo_puts_it_back(self):
        classic(self)
        cell = f".wl-row[data-id=\"{self.a_due}\"] .c-ico .cell-pick"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{cell}')", "the actions list drew")
                self.assertEqual(self.store.read("actions", ref=self.a_due)["status"], "Open")
                before = self.steps()
                was = self.said(p, cell)
                self.press(p, cell)
                p.until("!!document.querySelector('[data-pop] [data-value=Delayed]')", "the status menu opened in View")
                self.press(p, "[data-pop] [data-value=Delayed]")
                p.until("!!document.querySelector('[data-undo]')", "the pick saved, with Undo")
                self.assertEqual(self.store.read("actions", ref=self.a_due)["status"], "Delayed", "the store has the pick")
                self.assertEqual(self.steps(), before + 1, "one pick is one step")
                p.until(f"{json_s(self.said_js(cell))}.includes('Delayed')", "the row says Delayed")
                self.assertEqual(p.js("!!document.querySelector('#peek')"), False, "a pick opens no peek")
                self.press(p, "[data-undo]")
                p.until(f"{json_s(self.said_js(cell))} === {json.dumps(was)}", "Undo draws the row as it was")
                self.assertEqual(self.store.read("actions", ref=self.a_due)["status"], "Open", "Undo puts the store back")
                self.assertEqual(self.steps(), before + 2, "Undo is one step of its own")

    def press(self, p, selector):
        p.js(f"document.querySelector('{selector}').scrollIntoView({{block: 'center'}})")
        x, y, _ = p.box(selector)
        p.mouse("mouseMoved", x, y)
        p.mouse("mousePressed", x, y, 1)
        p.mouse("mouseReleased", x, y)

    def said_js(self, cell):
        return f"document.querySelector('{cell}').getAttribute('aria-label')"

    def test_an_empty_owner_and_date_say_none_and_cancelled_and_delayed_read_in_view(self):
        classic(self)
        with self.store.step("dashboard", T.USER) as st:
            bare = st.create("actions", {"project": "ABC", "description": "Fictional bare step", "raised": "2026-10-01", "source": "demo"})
            gone = st.create("actions", {"project": "ABC", "description": "Fictional dropped step", "raised": "2026-10-01", "source": "demo", "owner": "Pat Demo", "due_date": "2030-02-02", "status": "Cancelled"})
            late = st.create("actions", {"project": "ABC", "description": "Fictional late step", "raised": "2026-10-01", "source": "demo", "owner": "Pat Demo", "due_date": "2030-02-03", "status": "Delayed"})
        row = lambda rid: f".wl-row[data-id=\"{rid}\"]"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{row(bare)} .c-owner .cell-pick')", "the actions list drew")
                self.assertEqual(self.said(p, row(bare) + " .c-owner .cell-pick"), f"Owner of {bare}: none. Change")
                self.assertEqual(self.said(p, row(bare) + " .c-date .cell-pick"), f"Due date of {bare}: none. Change")
                self.assertEqual(p.js(f"document.querySelectorAll('{row(gone)}').length"), 0, "a Cancelled item is not in the open lists")
                self.assertTrue(self.said(p, row(late) + " .c-ico .cell-pick").startswith(f"Status of {late}: Delayed"), self.said(p, row(late) + " .c-ico .cell-pick"))
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{row(late)} .c-ico .cell-pick')", "the actions list drew")
            self.press(p, f"{row(late)} .c-ico .cell-pick")
            p.until("!!document.querySelector('[data-pop] [data-value=Cancelled]')", "the status menu opened")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-pop] [data-value]')].map(b => b.dataset.value).filter((v, i, a) => a.indexOf(v) === i)"), ["Open", "Delayed", "Closed", "Cancelled"])

    def test_previous_and_next_leave_the_edit_peek_a_description_click_opened(self):
        classic(self)
        title = f".wl-row[data-id=\"{self.a_due}\"] .c-title"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{title}')", "the actions list drew")
            p.js(f"document.querySelector('{title}').click()")
            p.until("!!document.querySelector('#peek [data-cell], #peek .cell-pick')", "the description opened the peek in edit")
            p.until("!!document.querySelector('#peek [data-pk-next]:not([disabled])') || !!document.querySelector('#peek [data-pk-prev]:not([disabled])')", "a neighbour exists")
            p.js("(document.querySelector('#peek [data-pk-next]:not([disabled])') || document.querySelector('#peek [data-pk-prev]:not([disabled])')).click()")
            p.until(f"((document.querySelector('#peek') || {{dataset: {{}}}}).dataset.peek || '') !== '{self.a_due}' && !!document.querySelector('#peek')", "the peek moved to the neighbour")
            p.until("!document.querySelector('#peek [data-cell], #peek .cell-pick')", "the neighbour opens read only")

    def test_back_to_the_item_a_click_opened_in_edit_shows_it_read_only(self):
        classic(self)
        title = f".wl-row[data-id=\"{self.a_due}\"] .c-title"
        peeked = "((document.querySelector('#peek') || {dataset: {}}).dataset.peek || '')"
        with chrome() as cdp:
            p = self.show(cdp, 1400)
            p.until(f"!!document.querySelector('{title}')", "the actions list drew")
            p.js(f"document.querySelector('{title}').click()")
            p.until("!!document.querySelector('#peek [data-cell], #peek .cell-pick')", "the description opened the peek in edit")
            p.until("!!document.querySelector('#peek [data-pk-next]:not([disabled])')", "Next is there")
            p.js("document.querySelector('#peek [data-pk-next]:not([disabled])').click()")
            p.until(f"{peeked} !== '{self.a_due}' && !!document.querySelector('#peek')", "the peek moved to the neighbour")
            p.until("!!document.querySelector('#peek [data-pk-prev]:not([disabled])')", "Previous is there")
            p.js("document.querySelector('#peek [data-pk-prev]:not([disabled])').click()")
            p.until(f"{peeked} === '{self.a_due}'", "Previous came back to the first item")
            p.until("!document.querySelector('#peek [data-cell], #peek .cell-pick')", "the first item opens read only again")


def json_s(expr):
    return f"({expr} || '')"


if __name__ == "__main__":
    unittest.main()

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

    def test_a_hostile_owner_typed_into_a_half_width_picker_is_never_run_or_stored_as_markup(self):
        # write path of the pickers on a list set beside another (ruling 23-11 A): markup and oversize text typed in the owner box
        classic(self)
        with self.store.step("dashboard", T.USER) as st:
            left = st.create("report_sections", {"project": "ABC", "type": "actions", "title": "Fictional half", "sort_order": 1, "beside": 1})
            st.create("report_sections", {"project": "ABC", "type": "text", "title": "Fictional notes", "sort_order": 2})
        cell = f"[data-id=\"{left}\"].slot-left .wl-row[data-id=\"{self.a_due}\"] .c-owner .cell-pick"
        before_owner = self.store.read("actions", ref=self.a_due)["owner"]
        hostile = ['<img src=x onerror="window.__pwn=1">', "'; DROP TABLE actions; --", "A" * 400]
        for width in (1400, 900):
            for text in hostile:
                with self.subTest(width=width, text=text[:20]), chrome() as cdp:
                    p = self.show(cdp, width)
                    p.until(f"!!document.querySelector('{cell}')", "the half-width actions list drew its owner picker")
                    self.press(p, cell)
                    p.until("!!document.querySelector('[data-pop] input.cp-in')", "the owner box opened")
                    p.js("document.querySelector('[data-pop] input.cp-in').select()")
                    p.type(text)
                    p.key("Enter", code="Enter", vk=13)
                    p.js("new Promise(r => setTimeout(r, 600))")
                    self.assertIsNone(p.js("window.__pwn === undefined ? null : window.__pwn"), "typed markup never ran")
                    self.assertEqual(p.js("document.querySelectorAll('#report img[src=x], [data-pop] img[src=x]').length"), 0, "typed markup drew no element")
                    owner = self.store.read("actions", ref=self.a_due)["owner"]
                    self.assertTrue(owner == before_owner or owner == text[:200], f"the store holds the old owner or the literal text (the box keeps 200 characters), nothing else: {owner!r}")
                    self.assertLessEqual(len(owner or ""), 200, "oversize text is cut to 200, never stored whole")
                    self.assertGreater(self.store.con.execute("SELECT count(*) FROM actions").fetchone()[0], 0, "the table is intact")
                    with self.store.step("dashboard", T.USER) as st:
                        st.update("actions", self.a_due, {"owner": before_owner})

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

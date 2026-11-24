"""Row 1304: the typed filter line takes the word group:<choice> (the eight choices of the Group by icon menu, Nothing included, the menu's own
spellings). The icon menu and the typed word show and set the same state; a chosen group is a chip reading exactly "Group: <choice>"; Nothing
removes the chip. Logic in node (the pure parts), the page in Chrome at 1400 and 900 px.

Run: python3 dev/run_tests.py test_group_word_1304
"""
import json
import unittest

import test_filter_query_ui as ui
from test_filter_query_ui import ROWS, CTX, lit, run_node
from test_server import chrome  # noqa: F401  (a browser file)
from test_work_board_page import Base

CHOICES = ["workstream", "status", "due", "owner", "priority", "milestone", "type", "nothing"]
LABELS = ["Workstream", "Status", "Due", "Owner", "Priority", "Milestone", "Type", "Nothing"]


def parse(line):
    return run_node(f"Q.parseFor({lit(line)}, {lit(ROWS)}, {lit(CTX)}).tokens.map(t => [t.kind, t.choice || null, t.error ? t.error.code : null])")


class Logic(unittest.TestCase):
    def test_every_choice_of_the_menu_is_read_in_any_case(self):
        for c, lab in zip(CHOICES, LABELS):
            for typed in (c, lab, c.upper()):
                self.assertEqual(parse(f"group:{typed}"), [["group", c, None]], typed)
        self.assertEqual(parse("Group:Status"), [["group", "status", None]], "the word's own case does not matter")

    def test_a_value_that_is_not_a_choice_is_an_error_not_a_guess(self):
        for line in ("group:", "group:colour", "group:status,due", "-group:status"):
            self.assertEqual([t[0] for t in parse(line)], ["error"], line)
            self.assertEqual(parse(line)[0][2], "missing-value", line)

    def test_the_word_filters_nothing(self):
        self.assertEqual(run_node(f"Q.rowsFor({lit(ROWS)}, 'group:status', {lit(CTX)}).length"), len(ROWS))
        self.assertEqual(run_node(f"Q.rowsFor({lit(ROWS)}, 'status:Open group:due', {lit(CTX)}).length"), 2)

    def test_the_chip_reads_exactly_group_colon_choice(self):
        for c, lab in zip(CHOICES, LABELS):
            self.assertEqual(run_node(f"Q.chipText({lit('group:' + c)}, {lit(ROWS)}, {lit(CTX)})"), f"Group: {lab}")
        self.assertEqual(run_node(f"Q.chipText('status:Open', {lit(ROWS)}, {lit(CTX)})"), "status:Open", "other chips are drawn as typed")
        self.assertEqual(run_node(f"Q.chipName('group:due', {lit(ROWS)}, {lit(CTX)})"), "Group")

    def test_groupOf_and_withGroup(self):
        g = lambda line: run_node(f"Q.groupOf({lit(line)}, {lit(ROWS)}, {lit(CTX)})")
        w = lambda line, c: run_node(f"Q.withGroup({lit(line)}, {lit(c)}, {lit(ROWS)}, {lit(CTX)})")
        self.assertEqual(g("is:open"), "")
        self.assertEqual(g("is:open group:Due"), "due")
        self.assertEqual(w("is:open", "status"), "is:open group:status", "added at the end")
        self.assertEqual(w("group:due is:open", "owner"), "group:owner is:open", "replaced in its place")
        self.assertEqual(w("group:due group:owner", "type"), "group:type", "one only")
        self.assertEqual(w("is:open group:due", "nothing"), "is:open", "Nothing removes it")
        self.assertEqual(w("is:open group:due", ""), "is:open")

    def test_the_suggestions_offer_group_and_then_the_eight_choices(self):
        self.assertIn("group:", [o["ins"] for o in ui.sug("gr")])
        self.assertEqual([o["ins"] for o in ui.sug("group:")], [f"group:{c}" for c in CHOICES])
        self.assertEqual([o["ins"] for o in ui.sug("group:s")], ["group:status"])
        self.assertEqual(ui.sug("-group:"), [])
        self.assertNotIn("n", ui.sug("group:")[0], "no counts: it filters nothing")

    def test_a_views_dot_does_not_come_from_the_group_word(self):
        v = {"line": "is:open"}
        self.assertFalse(run_node(f"Q.differsQuery({lit(v)}, 'is:open group:status', {lit(ROWS)}, {lit(CTX)})"))

    def test_a_page_of_its_own_schema_does_not_take_the_word(self):
        own = {"fields": [{"key": "name", "name": "Name", "of": None}], "states": []}
        self.assertEqual(run_node(f"Q.parseFor('group:status', {lit(ROWS)}, {lit(CTX)}, {lit({'fields': [{'key': 'n', 'name': 'N'}], 'states': []})}).tokens.map(t => t.kind)"), ["error"])


CHIPS = "[...document.querySelectorAll('#work [data-fchips] .fchip')].map(c => c.firstChild.textContent.trim())"
LABEL = "document.querySelector('#viewMenu').getAttribute('aria-label')"
OPEN = "document.querySelector('#viewMenu').click()"


class Page(Base):
    def type_in(self, cdp, sid, text):
        cdp.js("document.querySelector('#fline-input').focus()", sid)
        cdp.call("Input.insertText", {"text": text}, sid)

    def test_typing_the_word_sets_the_icon_menu_and_shows_one_chip(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.assertEqual(cdp.js(CHIPS, sid), [] if cdp.js("!document.querySelector('[data-fchips]')", sid) else cdp.js(CHIPS, sid))
                self.type_in(cdp, sid, "group:priority ")
                self.until(cdp, sid, f"{LABEL} === 'Group by: Priority'", "the icon follows the typed word")
                self.until(cdp, sid, f"{CHIPS}.includes('Group: Priority')", "the chip")
                self.assertEqual(cdp.js(f"{CHIPS}.filter(t => /^Group/.test(t))", sid), ["Group: Priority"], "exactly one, exactly that text")
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), True)

    def test_the_icon_menu_writes_the_chip_and_nothing_removes_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                cdp.js(OPEN, sid)
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList [data-kind=\"group:owner\"]')", "the menu")
                cdp.js("document.querySelector('#viewMenuList [data-kind=\"group:owner\"]').click()", sid)
                self.until(cdp, sid, f"{CHIPS}.includes('Group: Owner')", "the chip from the menu")
                self.assertEqual(cdp.js(LABEL, sid), "Group by: Owner")
                cdp.js(OPEN, sid)
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList [data-kind=\"group:nothing\"]')", "the menu again")
                cdp.js("document.querySelector('#viewMenuList [data-kind=\"group:nothing\"]').click()", sid)
                self.until(cdp, sid, f"!{CHIPS}.some(t => /^Group/.test(t))", "Nothing takes the chip away")
                self.assertEqual(cdp.js(LABEL, sid), "Group by: Nothing")

    def test_typing_nothing_sets_nothing_and_leaves_no_chip(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.type_in(cdp, sid, "group:Nothing ")
            self.until(cdp, sid, f"{LABEL} === 'Group by: Nothing'", "the icon says Nothing")
            self.assertEqual(cdp.js(f"{CHIPS}.filter(t => /^Group/.test(t))", sid), [])

    def test_removing_the_chip_ungroups_and_a_new_choice_replaces_the_chip(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.type_in(cdp, sid, "group:due ")
            self.until(cdp, sid, f"{CHIPS}.includes('Group: Due')", "the chip")
            self.type_in(cdp, sid, "group:type ")
            self.until(cdp, sid, f"{LABEL} === 'Group by: Type'", "the later word wins")
            self.until(cdp, sid, f"{CHIPS}.filter(t => /^Group/.test(t)).join() === 'Group: Type'", "one chip, the new one")
            cdp.js("document.querySelector('[data-fchips] .fchip[data-chip^=\"group:\"] button').click()", sid)
            self.until(cdp, sid, f"{LABEL} === 'Group by: Nothing'", "the chip's x removes the grouping")
            self.assertEqual(cdp.js(f"{CHIPS}.filter(t => /^Group/.test(t))", sid), [])

    def test_the_word_changes_the_list_and_the_list_keeps_its_rows(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            before = cdp.js("document.querySelectorAll('table.items tbody tr[data-id], #work-list tr[data-id]').length", sid)
            self.type_in(cdp, sid, "group:status ")
            self.until(cdp, sid, f"{LABEL} === 'Group by: Status'", "regrouped")
            self.assertEqual(cdp.js("document.querySelectorAll('table.items tbody tr[data-id], #work-list tr[data-id]').length", sid), before, "the word filters no row")

    def test_the_words_of_the_suggestions(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.type_in(cdp, sid, "group:")
            self.until(cdp, sid, "document.querySelectorAll('[role=option]').length === 8", "the eight choices")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[role=option]')].map(o => o.textContent.replace(/\\s+/g, ' ').trim())", sid), CHOICES)


if __name__ == "__main__":
    unittest.main()

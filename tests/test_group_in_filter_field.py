"""Row 1304: Group by is also offered in the Work items filter field (the box above the Work items list; the Group by icon stays where it is).
The word `group:` is the last row of the field list; after it the field offers the choices the icon menu has (8, the board 7: no Nothing). A pick
sets the one grouping both places show, and leaves nothing in the box. Classic theme.

Run: python3 dev/run_tests.py test_group_in_filter_field
The real page in headless Chrome against the real server over a demo database, at 1400 and 900 px.
"""
import unittest

from test_server import chrome, wait  # noqa: E402,F401
from test_work_filters import click, key  # noqa: E402
from test_work_board_page import Base, setUpModule, tearDownModule  # noqa: E402,F401

ROWS = "[...document.querySelectorAll('#fline-list .fopt')].map(o => o.dataset.ins)"
LABEL = "document.querySelector('#viewMenu').getAttribute('aria-label')"
EIGHT = [f"group:{g}" for g in ["workstream", "status", "due", "owner", "priority", "milestone", "type", "nothing"]]
BOARD_SENTENCE = "A board is always grouped, so choose one of its seven groupings."


class GroupInField(Base):
    def open_list(self, cdp, sid):
        click(cdp, sid, "#fline-input")
        key(cdp, sid, "ArrowDown")
        self.until(cdp, sid, "!!document.querySelector('#fline-list')", "the field list")

    def type_group(self, cdp, sid):
        self.open_list(cdp, sid)
        cdp.call("Input.insertText", {"text": "group:"}, sid)
        self.until(cdp, sid, "document.querySelectorAll('#fline-list .fopt.value').length > 0", "the choices after group:")

    def test_group_is_the_last_field_row_with_its_note(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.open_list(cdp, sid)
                rows = cdp.js(ROWS, sid)
                self.assertEqual(rows[-1], "group:", "group: is the last row of the field list")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#fline-list .fopt')].pop().querySelector('.fl2').textContent", sid), "How the list is grouped")
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), True)

    def test_after_group_the_eight_choices_with_the_current_one_ticked_and_a_pick_sets_it_in_both_places(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                click(cdp, sid, "#viewMenu")
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "the icon menu")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#viewMenuList [data-kind^=\"group:\"]')].map(b => b.dataset.kind)", sid), EIGHT, "the icon menu keeps its 8 rows")
                key(cdp, sid, "Escape")
                self.assertEqual(cdp.js("document.querySelectorAll('#work .fline-row #viewMenu').length", sid), 1, "the Group by icon is still there")
                self.type_group(cdp, sid)
                self.assertEqual(cdp.js(ROWS, sid), EIGHT, "the 8 choices of the icon menu, in its order")
                self.assertEqual(cdp.js("document.querySelectorAll('#fline-list [data-checked=true]').length", sid), 1, "exactly one ticked")
                self.assertEqual(cdp.js("document.querySelector('#fline-list [data-checked=true]').closest('.fopt').dataset.ins", sid), "group:workstream")
                click(cdp, sid, "#fline-list .fopt[data-ins='group:status']")
                self.until(cdp, sid, f"{LABEL} === 'Group by: Status'", "the icon label follows the pick")
                self.assertEqual(cdp.js("document.querySelector('#fline-input').value.length", sid), 0, "nothing is left in the box")
                self.assertEqual(cdp.js("document.querySelector('[data-fline]').dataset.line", sid), "is:open", "and the line is still the start line, no group word in it")
                self.type_group(cdp, sid)
                self.assertEqual(cdp.js("document.querySelectorAll('#fline-list [data-checked=true]').length", sid), 1)
                self.assertEqual(cdp.js("document.querySelector('#fline-list [data-checked=true]').closest('.fopt').dataset.ins", sid), "group:status")

    def test_the_icon_menu_sets_the_chip_and_the_cross_returns_to_the_start(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.assertEqual(cdp.js("document.querySelectorAll('[data-group-chip]').length", sid), 0, "the start grouping has no chip")
                click(cdp, sid, "#viewMenu")
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList [data-kind=\"group:owner\"]')", "the icon menu")
                click(cdp, sid, "#viewMenuList [data-kind=\"group:owner\"]")
                self.until(cdp, sid, "document.querySelectorAll('[data-group-chip]').length === 1", "the chip")
                self.assertEqual(cdp.js("document.querySelector('[data-group-chip]').dataset.groupChip", sid), "Group by: Owner")
                click(cdp, sid, "[data-gx]")
                self.until(cdp, sid, f"{LABEL} === 'Group by: Workstream'", "the cross returns to the start")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-group-chip]').length", sid), 0)

    def test_on_the_board_seven_choices_and_a_chip_without_a_cross(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status", mode="open")
                self.type_group(cdp, sid)
                self.assertEqual(cdp.js(ROWS, sid), EIGHT[:7], "no Nothing on the board")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-group-chip]').length", sid), 1)
                self.assertEqual(cdp.js("document.querySelectorAll('[data-group-chip] button').length", sid), 0, "no cross on the board")
                key(cdp, sid, "Escape")
                cdp.call("Input.insertText", {"text": "nothing "}, sid)
                self.until(cdp, sid, f"document.querySelector('#fline-msg, .fmsg').textContent.includes({BOARD_SENTENCE!r})", "the board sentence")
                self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "", "the typed word is not kept")

    def test_on_the_board_the_icon_menu_never_offers_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status", mode="open")
                click(cdp, sid, "#viewMenu")
                self.until(cdp, sid, "!!document.querySelector('#viewMenuList')", "the icon menu")
                kinds = cdp.js("[...document.querySelectorAll('#viewMenuList [data-kind^=\"group:\"]')].map(b => b.dataset.kind)", sid)
                self.assertEqual(kinds, EIGHT[:7])


if __name__ == "__main__":
    unittest.main()

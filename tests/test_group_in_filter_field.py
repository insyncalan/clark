"""Row 1304: Group by is offered in the filter field too (`group:`), on Work items. The Group by icon and its menu stay; both set the same choice.
The word `group:` is the last row of the field list, after it come the eight choices (seven on the board) with the current one ticked, a choice sets the
Group by state at once and leaves no text in the box, a neutral chip "Group by: <Name>" shows a grouping other than the start, its cross returns to the
start (the board chip has none), and the box's x (Clear all) resets the grouping too. 1400 and 900 px.

Run: python3 dev/run_tests.py test_group_in_filter_field
"""
import json
import unittest

from test_server import chrome  # noqa: E402
from test_work_board_page import Base  # noqa: E402
from test_work_filters import click  # noqa: E402

INPUT = "#fline-input"
ROWS = "[...document.querySelectorAll('#fline-list .fopt')].map(o => [o.querySelector('.fl1').textContent, !!o.querySelector('.fl-tick')])"
LABEL = "document.querySelector('#viewMenu').getAttribute('aria-label')"
CHIP = "(document.querySelector('.fchip[data-chip-group]') || {}).textContent || ''"
EIGHT = ["Workstream", "Status", "Due", "Owner", "Priority", "Milestone", "Type", "Nothing"]


class GroupInTheField(Base):
    def key(self, cdp, sid, name, code, vk):
        for kind in ("rawKeyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": code, "windowsVirtualKeyCode": vk}, sid)

    def focus(self, cdp, sid):
        click(cdp, sid, INPUT)
        self.until(cdp, sid, "document.activeElement.id === 'fline-input'", "the box has the focus")

    def type(self, cdp, sid, text):
        cdp.call("Input.insertText", {"text": text}, sid)

    def settle(self, cdp, sid):
        cdp.call("Runtime.evaluate", {"expression": "new Promise(f => setTimeout(f, 700))", "awaitPromise": True}, sid)

    def open_list(self, cdp, sid):
        self.key(cdp, sid, "ArrowDown", "ArrowDown", 40)
        self.until(cdp, sid, "!!document.querySelector('#fline-list .fopt')", "the list")

    def test_group_is_the_last_field_row_with_its_note(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.focus(cdp, sid)
                self.open_list(cdp, sid)
                last = cdp.js("(() => { const o = [...document.querySelectorAll('#fline-list .fopt')].pop(); return [o.querySelector('.fl1').textContent, o.querySelector('.fl2').textContent]; })()", sid)
                self.assertEqual(last, ["group:", "How the list is grouped"])

    def test_after_group_the_eight_choices_with_the_current_one_ticked_and_a_pick_sets_it_in_both_places(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.assertEqual(cdp.js(LABEL, sid), "Group by: Workstream")
                self.focus(cdp, sid)
                self.type(cdp, sid, "group:")
                self.key(cdp, sid, "ArrowDown", "ArrowDown", 40)
                self.until(cdp, sid, "document.querySelectorAll('#fline-list .fopt').length === 8", "the eight choices")
                self.assertEqual(cdp.js(ROWS, sid), [[w, w == "Workstream"] for w in EIGHT])
                self.assertEqual(cdp.js("document.querySelectorAll('#fline-list .fopt .c').length", sid), 0, "no counts on the choices")
                cdp.js("[...document.querySelectorAll('#fline-list .fopt')].find(o => o.textContent.startsWith('Status')).click()", sid)
                self.until(cdp, sid, f"{LABEL} === 'Group by: Status'", "the icon menu follows")
                self.assertEqual(cdp.js(CHIP, sid).replace("×", "").strip(), "Group by: Status")
                self.assertEqual(cdp.js("document.querySelector('.fchip[data-chip-group] button').getAttribute('aria-label')", sid), "Remove the Group by filter", "the cross is named")
                self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "", "no text is left in the box")
                self.assertEqual(cdp.js("document.querySelector('.fchip[data-chip-group]').classList.contains('word')", sid), True, "the neutral chip")
                self.assertEqual(cdp.js("document.querySelector('#viewMenu') !== null", sid), True, "the icon stays")

    def test_the_icon_menu_sets_the_chip_and_the_cross_returns_to_the_start(self):
        with chrome() as cdp:
            sid = self.visit(cdp, preset={"group": "owner"})
            self.until(cdp, sid, f"{CHIP}.startsWith('Group by: Owner')", "the chip shows the grouping the icon menu has")
            cdp.js("document.querySelector('.fchip[data-chip-group] button').click()", sid)
            self.until(cdp, sid, f"{LABEL} === 'Group by: Workstream'", "the cross goes back to Workstream")
            self.assertEqual(cdp.js(CHIP, sid), "")

    def test_clear_all_resets_the_grouping_and_a_second_group_word_replaces_the_first(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.focus(cdp, sid)
            self.type(cdp, sid, "group:due group:type ")
            self.until(cdp, sid, f"{LABEL} === 'Group by: Type'", "the second word replaces the first")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "")
            click(cdp, sid, "#fline-x")
            self.until(cdp, sid, f"{LABEL} === 'Group by: Workstream'", "Clear all resets the grouping")
            self.assertEqual(cdp.js(CHIP, sid), "")

    def test_a_word_not_yet_passed_by_the_caret_is_not_taken(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.focus(cdp, sid)
            self.type(cdp, sid, " b")
            self.key(cdp, sid, "Home", "Home", 36)
            self.type(cdp, sid, "group:due")
            self.settle(cdp, sid)
            self.assertEqual(cdp.js(LABEL, sid), "Group by: Workstream", "the caret is still at the end of the word: nothing is taken")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "group:due b")

    def test_another_field_word_offers_its_own_values_not_the_group_choices(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.focus(cdp, sid)
            self.type(cdp, sid, "type:")
            self.key(cdp, sid, "ArrowDown", "ArrowDown", 40)
            self.until(cdp, sid, "!!document.querySelector('#fline-list .fopt')", "the list")
            self.assertEqual(cdp.js("document.querySelector('#fline-list').textContent.includes('Nothing')", sid), False)
            self.assertEqual(cdp.js("document.querySelector('#fline-list').textContent.includes('Action')", sid), True)

    def test_on_the_board_seven_choices_and_a_chip_without_a_cross(self):
        with chrome() as cdp:
            sid = self.visit(cdp, preset={"view": "board", "group": "status"})
            self.until(cdp, sid, f"{CHIP}.startsWith('Group by: Status')", "the chip")
            self.assertEqual(cdp.js("document.querySelectorAll('.fchip[data-chip-group] button').length", sid), 0, "no cross on the board")
            self.focus(cdp, sid)
            self.type(cdp, sid, "group:")
            self.key(cdp, sid, "ArrowDown", "ArrowDown", 40)
            self.until(cdp, sid, "document.querySelectorAll('#fline-list .fopt').length === 7", "seven choices")
            self.assertNotIn("Nothing", [r[0] for r in cdp.js(ROWS, sid)])

    def test_on_the_board_typed_group_nothing_says_a_board_is_always_grouped(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width, preset={"view": "board", "group": "status"})
                self.until(cdp, sid, f"{CHIP}.startsWith('Group by: Status')", "the chip")
                self.focus(cdp, sid)
                self.type(cdp, sid, "group:nothing ")
                self.until(cdp, sid, "document.querySelector('#fline-msg').textContent.includes('always grouped')", "the sentence")
                self.assertEqual(cdp.js("document.querySelector('#fline-msg').textContent", sid), "A board is always grouped, so choose one of its seven groupings.")
                self.assertEqual(cdp.js(CHIP, sid).replace("×", "").strip(), "Group by: Status", "the grouping is unchanged")


if __name__ == "__main__":
    unittest.main()

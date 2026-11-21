"""Row 1304: Group by is offered in the Use cases filter field too (`group:`), with the page's own four choices (Status, Commitment, On the dashboard,
Nothing) and its own state, the same one the Group by icon menu shows. 1400 and 900 px.

Run: python3 dev/run_tests.py test_group_in_filter_field_use_cases
"""
import unittest

from test_use_cases_list import Setup, ON, tearDownModule  # noqa: F401
from test_server import chrome  # noqa: E402

BOX = "#ucl-q"
LABEL = "document.querySelector('#ucl-group').getAttribute('aria-label')"
ROWS = "[...document.querySelectorAll('#ucl-q-list .fopt')].map(o => [o.querySelector('.fl1').textContent, !!o.querySelector('.fl-tick')])"
CHIP = "(document.querySelector('.fchip[data-chip-group]') || {}).textContent || ''"


class GroupInTheUseCasesField(Setup):
    def test_after_group_the_four_choices_a_pick_sets_the_page_grouping_and_the_cross_and_the_x_return_to_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width=width)
                self.assertEqual(p.js(LABEL), "Group by: Nothing")
                self.assertEqual(p.js(CHIP), "", "no chip while the grouping is the start")
                p.js(f"document.querySelector('{BOX}').focus()")
                p.cdp.call("Input.insertText", {"text": "group:"}, p.sid)
                self.press(p, "ArrowDown")
                p.until("document.querySelectorAll('#ucl-q-list .fopt').length === 4", "the four choices")
                self.assertEqual(p.js(ROWS), [["Status", False], ["Commitment", False], [ON, False], ["Nothing", True]])
                p.js("[...document.querySelectorAll('#ucl-q-list .fopt')].find(o => o.textContent.startsWith('Status')).click()")
                p.until(f"{LABEL} === 'Group by: Status'", "the icon menu follows")
                self.assertEqual(p.js(CHIP).replace("×", "").strip(), "Group by: Status")
                self.assertEqual(p.js(f"document.querySelector('{BOX}').value"), "")
                p.js("document.querySelector('.fchip[data-chip-group] button').click()")
                p.until(f"{LABEL} === 'Group by: Nothing'", "the cross returns to Nothing")
                self.pick_via_icon(p, "Commitment")
                p.until(f"{CHIP}.startsWith('Group by: Commitment')", "the chip follows the icon menu")
                p.js("document.querySelector('#ucl-q-x').click()")
                p.until(f"{LABEL} === 'Group by: Nothing'", "Clear all resets the grouping")

    def pick_via_icon(self, p, word):
        self.click(p, "#ucl-group")
        p.until("!!document.querySelector('.ddmenu [role=menuitemradio]')", "the Group by menu")
        p.js(f"[...document.querySelectorAll('.ddmenu [role=menuitemradio]')].find(b => b.textContent.replace('✓', '').trim() === '{word}').click()")


if __name__ == "__main__":
    unittest.main()

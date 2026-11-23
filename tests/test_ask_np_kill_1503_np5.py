"""Row 1503: survivors of the mutation sweep over the All projects row of the new-projects screen (slice 5).

Run: python3 dev/run_tests.py test_ask_np_kill_1503_np5
The All projects row reads the computer-wide starting value, never a project's own value. Chrome is required."""
import unittest

from ask_np_settings_base_1503 import SettingsBase
from test_server import chrome


class AllRow(SettingsBase):
    def test_the_all_projects_row_reads_the_starting_value_and_not_a_projects_own(self):
        """The read for a named project says asking is off; the read with no project says on. The row on the All projects tab shows on."""
        seen = []

        def read(project=None):
            seen.append(project)
            return 200, {"ok": True, "on": project is None, "off_here": False}
        real = self.svc.read_new
        self.svc.read_new = read
        self.addCleanup(setattr, self.svc, "read_new", real)
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]')", "the row's switch")
            self.assertIn(None, seen, "the row asked for the starting value, with no project")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('aria-checked')"), "true", "the row shows the starting value, not a project's own")

    def test_the_row_is_a_real_switch_with_its_look(self):
        """The row's control says it is a switch to a screen reader, wears the switch look (44 wide, round) and the row keeps its box class."""
        with chrome() as cdp:
            js = self.show(cdp)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]')", "the row's switch")
            self.assertEqual(js("document.querySelector('[data-new-switch]').getAttribute('role')"), "switch", "the control has the role switch")
            self.assertEqual(js("document.querySelector('[data-new-switch]').classList.contains('switch')"), True, "the control has the switch class")
            self.assertEqual(js("Math.round(document.querySelector('[data-new-switch]').getBoundingClientRect().width)"), 44, "the control is drawn as a switch, 44 wide")
            self.assertEqual(js("document.querySelector('#ask-new-all').classList.contains('ask-new')"), True, "the row keeps its box class")


if __name__ == "__main__":
    unittest.main()

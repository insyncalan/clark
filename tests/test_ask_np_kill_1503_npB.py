"""Row 1503: the new-projects screen's rows sit in the Settings card, so the card's row layout (a wrapping flex row with a top margin and a gap) applies to them.

Run: python3 dev/run_tests.py test_ask_np_kill_1503_npB
All projects tab and the project's tab, Classic, 1400 only. Chrome is required."""
import unittest

from ask_np_settings_base_1503 import SettingsBase
from test_server import chrome

ROW = ("(() => { const r = document.querySelector('%s > div'); const c = getComputedStyle(r);"
       " return [r.className, c.display, c.flexWrap, c.columnGap, c.marginTop, getComputedStyle(document.documentElement).getPropertyValue('--d-set-row').trim()]; })()")


class NewProjectsRows(SettingsBase):
    def check(self, js, sel, what):
        got = js(ROW % sel)
        self.assertEqual(got[:4], ["row", "flex", "wrap", "8px"], f"{what}: the row keeps the Settings card's row layout")
        self.assertTrue(got[4] != "0px" and got[4] == got[5], f"{what}: the row's top margin is the card's row spacing ({got})")

    def test_the_rows_keep_the_settings_card_row_layout(self):
        with chrome() as cdp:
            js = self.show(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
            self.until(js, "!!document.querySelector('#ask-new-here')", "the project's rows")
            self.check(js, "#ask-new-here", "project tab")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#ask-new-all')", "the all projects rows")
            self.check(js, "#ask-new-all", "all projects tab")

    def test_the_hint_the_state_line_and_the_undo_keep_their_classes_look(self):
        """The grey hint after the switch, the project's state line (long names wrap) and the Undo (a link look, a pointing hand, 24 px to hit)."""
        with chrome() as cdp:
            js = self.show(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
            self.until(js, "!!document.querySelector('#ask-here-state')", "the project's line")
            self.assertEqual(js("getComputedStyle(document.querySelector('#ask-here-state')).overflowWrap"), "anywhere", "the state line wraps long names")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('[data-new-switch]') && !document.querySelector('[data-new-switch]').disabled", "the switch")
            self.assertEqual(js("(() => { const h = getComputedStyle(document.querySelector('#ask-new-line')).color;"
                                " const t = getComputedStyle(document.querySelector('#ask-new-all .folder-now')).color; return h !== t; })()"), True, "the hint is grey, not the text colour")
            js("document.querySelector('[data-new-switch]').click()")
            self.until(js, "!!document.querySelector('[data-new-undo]')", "the Undo")
            got = js("(() => { const c = getComputedStyle(document.querySelector('[data-new-undo]')); return [c.cursor, c.minHeight, c.minWidth]; })()")
            self.assertEqual(got, ["pointer", "24px", "24px"], "the Undo has the link look")


if __name__ == "__main__":
    unittest.main()

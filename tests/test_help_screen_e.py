"""Help against the screen: two places where Help names a control the screen does not have (checked at 1400 and 900 px).

Run: python3 dev/run_tests.py test_help_screen_e
Chrome, one session. The page is the real one with the fictional demo project.
  1. write-the-weekly-report says to click the text under Current state and write. In Edit the Current state section has no editor
     (only Current state, This week and Next week do; edit/richSave.js has no write for the headline).
  2. change-an-item-in-the-peek says Status, Priority, Owner and Due can each be clicked in the peek. Since item 1180 (the chip row) all four
     are chips with one button each (before it, only Status was; Owner, Due and Priority were plain text).
The screen tests are green and say what the screen does today; if the screen changes, they fail and Help is checked against it again.
The Help tests are expected failures: the Help wording needs the owner's approval. When it is changed, they pass, and unittest reports an
unexpected success: remove the expectedFailure line then.
"""
import json
import shutil
import unittest

import _testpage as testpage
from _paths import ROOT
from _real_server import real_server
from test_report_editor import Pg
from test_server import chrome
from test_work_items import FIXED_DATE, load_demo, page_target

HELP = json.loads((ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
TASK = {t["id"]: t for t in HELP["howto"]["tasks"]}
WIDTHS = (1400, 900)


class Screen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def show_at(self, cdp, hash_, width, ready):
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: self.projects, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#{hash_}&p={self.code}"}, sid)
        p = Pg(self, cdp, sid)
        p.until(ready, hash_, 15)
        return p

    def test_in_edit_only_current_state_this_week_and_next_week_have_a_text_editor(self):
        for width in WIDTHS:
            with chrome() as cdp:
                p = self.show_at(cdp, "dashboard", width, "document.querySelectorAll('.sec').length > 0")
                p.edit()
                editors = p.js("[].slice.call(document.querySelectorAll('#report [aria-label^=\"Edit \"][aria-label$=\" text\"]')).map(function (e) { return e.getAttribute('aria-label'); })")
                self.assertEqual(editors, ["Edit Header text", "Edit This week text", "Edit Next week text"], f"{width}: the Header is a text section (item 1188, row 1266), so it has an editor")
                self.assertTrue(p.js("!!document.querySelector('#report [aria-label=\"Move or change Header\"]')"), f"{width}: the section is there")

    def test_in_the_peek_status_priority_owner_and_due_are_each_one_chip_button(self):
        for width in WIDTHS:
            with chrome() as cdp:
                p = self.show_at(cdp, "work", width, "document.querySelectorAll('#work tbody tr[data-id]').length > 0")
                p.js("window.clarkPage.openPeek('TUL-A-002')")
                p.until("!!document.querySelector('#peek')", "the peek")
                row = "(function (k) { var r = document.querySelector('#peek [data-row=' + k + ']'); return r ? r.querySelectorAll('button, [role=button], input, [contenteditable=true]').length : -1; })"
                for key in ("status", "owner", "due", "priority"):
                    self.assertEqual(p.js(row + "('" + key + "')"), 1, f"{width}: {key} is one chip button")


class HelpWords(unittest.TestCase):
    """Help must not promise what the Screen tests above show is not there."""

    def test_write_the_weekly_report_names_the_three_editors_the_screen_has(self):
        """The Header is a text section with an editor (see the screen test above), and the default report has no Summary (row 1266)."""
        steps = " ".join(TASK["write-the-weekly-report"]["s"])
        self.assertIn("text under **Header**, **This week** or **Next week**", steps)
        self.assertNotIn("**Summary**", steps)

    def test_change_an_item_in_the_peek_does_not_say_priority_owner_and_due_can_be_clicked_there(self):
        steps = " ".join(TASK["change-an-item-in-the-peek"]["s"])
        self.assertNotIn("**Status**, **Priority**, **Owner** and **Due**. Click one", steps)


if __name__ == "__main__":
    unittest.main()

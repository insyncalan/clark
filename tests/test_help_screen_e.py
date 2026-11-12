"""Help against the screen: two places where Help names a control the screen does not have (checked at 1400 and 900 px).

Run: python3 dev/run_tests.py test_help_screen_e
Chrome, one session. The page is the real one with the fictional demo project.
  1. write-the-weekly-report says to click the text under Current state and write. In Edit the Current state section has no editor
     (only Summary, This week and Next week do; edit/richSave.js has no write for the headline).
  2. change-an-item-in-the-peek says Status, Priority, Owner and Due can each be clicked in the peek. Only Status can; Owner, Due and
     Priority are plain text there (they change in the list row, or in words with the Sneak peek).
The screen tests are green and say what the screen does today; if the screen gains the control, they fail and Help is then right as it is.
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

    def open(self, cdp, hash_, width, ready):
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

    def test_in_edit_only_summary_this_week_and_next_week_have_a_text_editor(self):
        for width in WIDTHS:
            with chrome() as cdp:
                p = self.open(cdp, "dashboard", width, "document.querySelectorAll('.sec').length > 0")
                p.edit()
                editors = p.js("[].slice.call(document.querySelectorAll('#report [aria-label^=\"Edit \"][aria-label$=\" text\"]')).map(function (e) { return e.getAttribute('aria-label'); })")
                self.assertEqual(editors, ["Edit Summary text", "Edit This week text", "Edit Next week text"], f"{width}: no editor under Current state")
                self.assertTrue(p.js("!!document.querySelector('#report [aria-label=\"Move or change Current state\"]')"), f"{width}: the section is there")

    def test_in_the_peek_only_status_can_be_clicked_of_status_priority_owner_and_due(self):
        for width in WIDTHS:
            with chrome() as cdp:
                p = self.open(cdp, "work", width, "document.querySelectorAll('#work tbody tr[data-id]').length > 0")
                p.js("window.clarkPage.openPeek('TUL-A-002')")
                p.until("!!document.querySelector('#peek')", "the peek")
                row = "(function (k) { var r = document.querySelector('#peek [data-row=' + k + ']'); return r ? r.querySelectorAll('button, [role=button], input, [contenteditable=true]').length : -1; })"
                self.assertEqual(p.js(row + "('owner')"), 0, f"{width}: Owner")
                self.assertEqual(p.js(row + "('due')"), 0, f"{width}: Due")
                self.assertEqual(p.js(row + "('priority')"), 0, f"{width}: Priority")
                self.assertGreater(p.js(row + "('status')"), 0, f"{width}: Status is a button")


class HelpWords(unittest.TestCase):
    """Help must not promise what the Screen tests above show is not there."""

    def test_write_the_weekly_report_does_not_send_you_to_an_editor_under_current_state(self):
        steps = " ".join(TASK["write-the-weekly-report"]["s"])
        self.assertNotIn("text under **Current state**", steps)
        self.assertNotIn("Write the current state", json.dumps(HELP["start"]["loop"]))

    def test_change_an_item_in_the_peek_does_not_say_priority_owner_and_due_can_be_clicked_there(self):
        steps = " ".join(TASK["change-an-item-in-the-peek"]["s"])
        self.assertNotIn("**Status**, **Priority**, **Owner** and **Due**. Click one", steps)


if __name__ == "__main__":
    unittest.main()

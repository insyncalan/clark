"""Row 1455: the saved folders could not be read, so the answer is HTTP 200, ok false, code folders_unreadable, nothing is sent.

Run: python3 dev/run_tests.py test_ask_folders_unreadable_1455
The server side is pinned by the status number and the exact approved sentence (NEW-WORDS.md, row 1455, no exception text and no path);
the screen side by the Ask panel in a real browser at 1400 and 900 px, showing that same sentence in the transcript.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import test_ask_route as tr
import test_ask_panel as tap
from clark import ask_passages, ask_service, reach, store as st
from test_report_editor import Base
from test_server import chrome

SENTENCE = "Your folders could not be read just now, so nothing was sent. Try again, or remove a folder in Settings."


class OnTheServer(tr.Base):
    def setUp(self):
        patch = mock.patch.object(reach.platform, "system", return_value=reach.platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()
        self.mine = Path(tempfile.mkdtemp(prefix="clark-mine-"))
        self.addCleanup(shutil.rmtree, self.mine, True)
        (self.mine / "plan.txt").write_text("ZQ-MINE the cutover is booked", encoding="utf-8")
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("source_folders", {"project": tr.CODE, "path": str(self.mine.resolve()), "sort_order": 1})
        store.close()

    def test_unreadable_folder_list_status_and_sentence(self):
        with mock.patch.object(ask_passages, "folder_data", side_effect=RuntimeError("boom %s" % self.mine)):
            status, got = self.question("What is the cutover plan?")
        self.assertEqual((status, got["ok"], got["code"]), (200, False, "folders_unreadable"))
        self.assertEqual(got["message"], SENTENCE)
        self.assertNotIn("boom", got["message"])
        self.assertNotIn(str(self.mine), got["message"])
        self.assertNotIn(str(self.mine), str(got))
        self.assertEqual(self.provider.sent, [])


class OnThePanel(Base):
    ask = tap.Panel.ask
    opened = tap.Panel.opened

    def setUp(self):
        super().setUp()
        self.stub = tap.Stub()
        self.s.httpd.ask = self.stub

    def test_ask_panel_shows_the_folders_unreadable_sentence(self):
        self.stub.ask = lambda body: (200, {"ok": False, "code": "folders_unreadable", "message": ask_service.MESSAGES["folders_unreadable"]})
        with chrome() as cdp:
            p = self.opened(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js("document.querySelectorAll('.ask-turn.problem').forEach((n) => n.remove())")
                self.ask(p, "What is the plan?")
                p.until("!!document.querySelector('.ask-turn.problem')", f"the sentence came at {width}")
                self.assertEqual(p.js("document.querySelector('.ask-turn.problem .ask-text').textContent.trim()"), SENTENCE, width)
                self.assertTrue(p.js("(function(){var r=document.querySelector('.ask-turn.problem').getBoundingClientRect(),a=document.querySelector('#ask-panel').getBoundingClientRect();return r.left>=a.left&&r.right<=a.right+1})()"), f"inside the panel at {width}")
                p.until("!document.querySelector('#ask-send').disabled", "ready again")
                p.js("document.querySelector('#ask-box').value = ''")


if __name__ == "__main__":
    unittest.main()

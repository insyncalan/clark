"""Row 1294 (ticket order, mock-up A8): on a project's tab the last cards run Standing instructions, Slash commands, Files, then Chats and usage last.

Run: python3 dev/run_tests.py test_ask_order_proj_1294
Real browser at 1400 and 900, Classic. The Files card is the project's own turn-off of the global switch (FilesProject); the usage card is the last section of the page."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import page

WIDTHS = (1400, 900)
IDS = ["ask-instructions-own-card", "slash-project", "ask-files-project", "ask-usage-project"]
ALL_IDS = "[...document.querySelectorAll('#ask-tabs ~ section.frame.setting')].map(s => s.id)"


class ProjectTabEnd(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"))
        self.addCleanup(self.s.close)
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.s.httpd.app_settings = service(make_db(d))

    def test_the_project_tab_ends_with_slash_commands_files_then_usage_at_both_widths(self):
        with chrome() as cdp:
            sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20))
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                js("document.querySelector('[data-ask-tab=project]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-project') && !!document.querySelector('#ask-files-project') && !!document.querySelector('#slash-project')"), 20), f"project tab at {w}")
                got = js(ALL_IDS)
                at = [got.index(i) for i in IDS]
                self.assertEqual(at, sorted(at), f"order at {w}: {got}")
                self.assertEqual(got[-1], "ask-usage-project", f"Chats and usage is the last card at {w}: {got}")
                self.assertEqual(got[-3:], ["slash-project", "ask-files-project", "ask-usage-project"], f"at {w}: {got}")
                self.assertEqual(js("document.querySelector('#ask-files-project h2').textContent"), "Files in ABC")


if __name__ == "__main__":
    unittest.main()

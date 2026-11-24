"""Row 1503, askPanelState.js, the status check on the panel's own-project read.

Run: python3 dev/run_tests.py test_ask_np_kill_1503_aps102
Only a 404 that says not_found means "this server keeps no per-project value" and leaves the panel as it was. The same code word under another status (a server
fault, a 200) is not that answer: the read has failed and the panel reads unknown (box shut, nothing sent). Classic, 1400. Chrome is required."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_ask_panel import Stub
from test_ask_settings import make_db, service
from test_report_editor import Base
from test_server import chrome

BOX = "!!document.querySelector('#ask-box') && !document.querySelector('#ask-box').disabled && !document.querySelector('#ask-send').disabled"
SHUT = "!!document.querySelector('#ask-box') && document.querySelector('#ask-box').disabled"


class Aps102(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.svc = self.s.httpd.app_settings = service(make_db(d))

    def open_panel(self, cdp, status, body):
        self.svc.read_new = lambda project=None: (status, body) if project else (200, {"ok": True, "on": True})
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        return p

    def test_the_not_found_word_under_another_status_is_a_failed_read(self):
        """500 and 200 that carry code not_found: the panel reads unknown (box shut), and nothing is asked."""
        for status in (500, 200):
            with self.subTest(status=status), chrome() as cdp:
                p = self.open_panel(cdp, status, {"ok": False, "code": "not_found"})
                p.until(SHUT, f"{status}: the panel reads as unknown, the box is shut")
                self.assertFalse(p.js("!!document.querySelector('#ask-off, #ask-signed-out')"), "it claims neither off nor signed out")
                self.assertEqual(self.stub.count("ask"), 0, "nothing was asked")

    def test_a_404_that_says_not_found_leaves_the_panel_ready(self):
        """The control: a 404 with code not_found is a server with no per-project value, so the panel stays ready."""
        with chrome() as cdp:
            p = self.open_panel(cdp, 404, {"ok": False, "code": "not_found"})
            p.until(BOX, "the panel is ready")


if __name__ == "__main__":
    unittest.main()

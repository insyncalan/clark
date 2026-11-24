"""Row 1503, askPanelState.js, the state guard of the panel's own-project read.

Run: python3 dev/run_tests.py test_ask_np_kill_1503_aps98
A panel that reads off (asking is off for the computer) or unknown (the connection check failed) claims nothing, so it must not send the read for the
project's own value. Only ready or signed out go on to it. Classic, 1400. Chrome is required."""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from test_ask_panel import Stub
from test_ask_settings import make_db, service
from test_report_editor import Base
from test_server import chrome, wait

SHUT = "!!document.querySelector('#ask-box') && document.querySelector('#ask-box').disabled"


class Aps98(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.svc = self.s.httpd.app_settings = service(make_db(d))
        self.reads = []
        self.svc.read_new = lambda project=None: (self.reads.append(project), (200, {"ok": True, "on": True, "off_here": False}))[1]

    def open_panel(self, cdp, break_status=False):
        p = self.visit(cdp)
        if break_status:
            p.js("(() => { const f = globalThis.fetch; globalThis.fetch = (u, i) => String(u).includes('/api/ask/status') ? Promise.resolve(new Response('{}', {status: 500})) : f(u, i); })()")
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
        return p

    def project_reads(self):
        return [r for r in self.reads if r]

    def test_a_panel_that_reads_off_does_not_send_the_project_read(self):
        """Asking is off for the computer: the panel reads off, and no read for the project's own value goes out."""
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.until("!!document.querySelector('#ask-off')", "it reads off")
            self.assertFalse(wait(lambda: self.project_reads(), 3), "no read for the project was sent from off")
            self.assertEqual(self.stub.count("ask"), 0, "nothing was asked")

    def test_a_panel_that_reads_unknown_does_not_send_the_project_read(self):
        """The connection check fails: the panel reads unknown (box shut), and no read for the project's own value goes out."""
        with chrome() as cdp:
            p = self.open_panel(cdp, break_status=True)
            p.until(SHUT, "the panel reads as unknown: the box is shut")
            self.assertFalse(wait(lambda: self.project_reads(), 3), "no read for the project was sent from unknown")
            self.assertEqual(self.stub.count("ask"), 0, "nothing was asked")

    def test_a_ready_panel_does_send_the_project_read(self):
        """The control: a ready panel does read the project's own value (so the two tests above are not passing on a read that never happens)."""
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.assertTrue(wait(lambda: self.project_reads(), 10), "a ready panel reads the project")
            p.until("!!document.querySelector('#ask-box') && !document.querySelector('#ask-box').disabled", "ready")


if __name__ == "__main__":
    unittest.main()

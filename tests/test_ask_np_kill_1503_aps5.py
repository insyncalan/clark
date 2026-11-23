"""Row 1503: a survivor of the mutation sweep over the panel's read of the project's own value (askPanelState.js, hereCheck), killed by a browser test.

Run: python3 dev/run_tests.py test_ask_np_kill_1503_aps5
Panel: a 404 whose answer is not JSON (no body reaches the page) is not the 'no settings store' answer: the panel stops checking, reads unknown and sends nothing.
Chrome is required."""
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


class Aps5(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        self.svc = self.s.httpd.app_settings = service(make_db(d))

    def test_a_404_that_is_not_json_reads_as_unknown(self):
        """The server answers 404 with words that are not JSON: there is no code to say 'not_found', so the panel reads unknown and stops checking."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("(() => { const f = globalThis.fetch; globalThis.fetch = (u, i) => String(u).includes('ask-new-projects') ? Promise.resolve(new Response('gone', {status: 404})) : f(u, i); })()")
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
            p.until(SHUT, "the panel reads as unknown: the box is shut")
            self.assertTrue(p.js("!document.querySelector('#ask-send') || document.querySelector('#ask-send').disabled"), "send is off")
            self.assertEqual(self.stub.count("ask"), 0, "nothing was asked")
            self.assertFalse(wait(lambda: p.js("document.querySelector('#ask-panel').textContent.indexOf('Checking whether you can ask') >= 0"), 3), "it is no longer checking")

    def test_an_answer_that_is_not_a_200_is_unknown_whatever_else_it_says(self):
        """A 403, a 404 with another code and a 201 that still say ok and a project that is not off are not a read of the value: the panel reads unknown."""
        cases = (("403 with ok and asking on", 403, {"ok": True, "off_here": False}),
                 ("404 with another code, ok and asking on", 404, {"ok": True, "off_here": False, "code": "bad_project"}),
                 ("201 with ok and asking on", 201, {"ok": True, "off_here": False}))
        for name, status, body in cases:
            with self.subTest(name):
                self.svc.read_new = lambda project=None, status=status, body=body: (status, body) if project else (200, {"ok": True, "on": True})
                self.stub.calls.clear()
                with chrome() as cdp:
                    p = self.visit(cdp)
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-panel')", "the panel opened on /")
                    p.until(SHUT, "the panel reads as unknown: the box is shut")
                    self.assertTrue(p.js("!document.querySelector('#ask-send') || document.querySelector('#ask-send').disabled"), "send is off")
                    self.assertEqual(self.stub.count("ask"), 0, "nothing was asked")


if __name__ == "__main__":
    unittest.main()

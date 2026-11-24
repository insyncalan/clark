"""Ask panel: a question sent while Earlier chats is showing must leave the chat (and its answer) visible, not the list.

Run: python3 dev/run_tests.py test_ask_hist_send
Real browser, 1400 and 900 px. The server's `ask` is the stub of test_ask_panel.
"""
import unittest

import test_ask_panel
from test_report_editor import Base
from test_server import chrome

WIDTHS = (1400, 900)


class HistSend(Base):
    def setUp(self):
        super().setUp()
        self.stub = test_ask_panel.Stub()
        self.s.httpd.ask = self.stub

    opened = test_ask_panel.Panel.opened
    ask = test_ask_panel.Panel.ask

    def test_sending_with_history_open_shows_the_answer_afterwards(self):
        for w in WIDTHS:
            with chrome() as cdp:
                p = self.opened(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.js("document.querySelector('#ask-history').click()")
                p.until("!!document.querySelector('#ask-hist')", "history open")
                self.ask(p, "When is go-live?")
                p.until("document.querySelectorAll('.ask-turn').length === 2", f"{w}: the answer")
                p.until("!document.querySelector('#ask-work')", f"{w}: done working")
                self.assertTrue(p.js("document.querySelector('#ask-hist') === null"), f"{w}: the list must not come back over the answer")
                self.assertFalse(p.js("document.querySelector('#ask-log').hidden"), f"{w}: the log is shown")


if __name__ == "__main__":
    unittest.main()

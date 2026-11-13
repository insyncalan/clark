"""Review of the Ask bundle: the Ask history Remove button's words, and the Help rows for it, in the rendered page.

Run: python3 dev/run_tests.py test_ask_history_help_rows
Real browser, 1400 and 900 px. The server's `ask` is the stub of test_ask_panel.
"""
import json
import unittest

import test_ask_panel
from test_report_editor import Base
from test_server import chrome

WIDTHS = (1400, 900)


class Rendered(Base):
    def setUp(self):
        super().setUp()
        self.stub = test_ask_panel.Stub()
        self.s.httpd.ask = self.stub

    opened = test_ask_panel.Panel.opened
    ask = test_ask_panel.Panel.ask

    def width(self, cdp, p, w):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def test_the_history_remove_button_says_remove_and_names_the_chat(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            p.js("document.querySelector('#ask-new').click(); document.querySelector('#ask-history').click()")
            p.until("document.querySelectorAll('.ask-hist-del').length === 1", "one kept chat")
            for w in WIDTHS:
                self.width(cdp, p, w)
                b = json.loads(p.js("JSON.stringify([...document.querySelectorAll('.ask-hist-del')].map(e => ({title: e.title, label: e.getAttribute('aria-label')})))"))
                self.assertEqual(b, [{"title": "Remove", "label": "Remove the chat: When is go-live?"}], str(w))

    def test_help_shows_the_history_row_the_column_drag_per_list_and_the_milestones_heading_row(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in WIDTHS:
                self.width(cdp, p, w)
                p.js("window.clarkPage.help.open('ref-ask-clark')")
                p.until("!!document.querySelector('#hp-ref-ask-clark')", "the ask clark entry")
                t = p.js("document.querySelector('#hp-ref-ask-clark').textContent")
                for need in ("History (the clock button at the top) opens Earlier chats", "Press Remove beside a chat"):
                    self.assertIn(need, t, f"{w}: {need}")
                p.js("window.clarkPage.help.open('ref-work-items')")
                p.until("!!document.querySelector('#hp-ref-work-items')", "the work items entry")
                t = p.js("document.querySelector('#hp-ref-work-items').textContent")
                for need in ("drag the right edge of its heading", "Alt+← or Alt+→",
                             "The Use cases list works the same way",
                             "A Needs from you section in Edit has the same",
                             "The list of archived work items", "on its Type, Item, Owner, Due and Status columns"):
                    self.assertIn(need, t, f"{w}: {need}")
                p.js("window.clarkPage.help.open('ref-milestones-page')")
                p.until("!!document.querySelector('#hp-ref-milestones-page')", "the milestones entry")
                t = p.js("document.querySelector('#hp-ref-milestones-page').textContent")
                self.assertIn("heading row over its columns: Date, Milestone, State and Progress", t, str(w))


if __name__ == "__main__":
    unittest.main()

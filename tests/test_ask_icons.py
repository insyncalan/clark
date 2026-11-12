"""Row 1095: Ask clark's New chat, History and Close are plain icon buttons; History keeps the project's earlier chats on this computer.

Run: python3 dev/run_tests.py test_ask_icons
Real browser, 1400 and 900 px, light and dark. The server's `ask` is the stub of test_ask_panel.
"""
import json
import unittest

import test_ask_panel
from test_report_editor import Base
from test_server import chrome

BTNS = """JSON.stringify(['ask-new','ask-history','ask-close'].map(id => { const b = document.getElementById(id), r = b.getBoundingClientRect(), c = getComputedStyle(b);
  return {id, label: b.getAttribute('aria-label'), title: b.title, text: b.textContent.trim(), w: r.width, h: r.height, border: c.borderTopWidth, bg: c.backgroundColor, svg: !!b.querySelector('svg'), x: r.left}; }))"""


class AskIcons(Base):
    def setUp(self):
        super().setUp()
        self.stub = test_ask_panel.Stub()
        self.s.httpd.ask = self.stub

    opened = test_ask_panel.Panel.opened
    ask = test_ask_panel.Panel.ask

    def test_three_plain_icon_buttons_in_order_at_both_widths_and_themes(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    b = json.loads(p.js(BTNS))
                    what = f"{width} {theme}"
                    self.assertEqual([x["label"] for x in b], ["New chat", "History", "Close"], what)
                    self.assertEqual([x["title"] for x in b], ["New chat", "History", "Close"], what)
                    self.assertEqual([x["text"] for x in b], ["", "", ""], what)
                    self.assertTrue(all(x["svg"] for x in b), what)
                    self.assertTrue(all(x["w"] >= 24 and x["h"] >= 24 for x in b), what)
                    self.assertTrue(all(x["border"] == "0px" for x in b), what + ": no outline")
                    self.assertEqual([x["x"] for x in b], sorted(x["x"] for x in b), what)

    def test_history_is_empty_then_keeps_opens_and_deletes_chats_per_project(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist-empty')", "the empty list")
            self.assertIn("No earlier chats yet", p.js("document.querySelector('#ask-hist-empty').textContent"))
            p.js("document.querySelector('#ask-history').click()")
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            p.js("document.querySelector('#ask-new').click()")
            self.ask(p, "Which risks are red?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the second answer")
            p.js("document.querySelector('#ask-new').click()")
            p.js("document.querySelector('#ask-history').click()")
            p.until("document.querySelectorAll('#ask-hist li').length === 2", "two kept chats")
            titles = p.js("[...document.querySelectorAll('.ask-hist-title')].map(e => e.textContent)")
            self.assertEqual(titles, ["Which risks are red?", "When is go-live?"], "newest first, titled by the first question")
            self.assertTrue(all(p.js("[...document.querySelectorAll('.ask-hist-when')].map(e => e.textContent.length > 6)")))
            p.js("document.querySelectorAll('.ask-hist-open')[1].click()")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the old chat is back")
            self.assertEqual(p.js("document.querySelector('.ask-turn.user .ask-text').textContent"), "When is go-live?")
            p.js("document.querySelector('#ask-history').click()")
            p.js("document.querySelectorAll('.ask-hist-del')[1].click()")
            p.until("document.querySelectorAll('#ask-hist li').length === 1", "one chat deleted")
            self.assertEqual(p.js("document.querySelector('.ask-hist-title').textContent"), "Which risks are red?")
            keys = p.js("Object.keys(localStorage).filter(k => k.startsWith('clark.askChats.'))")
            self.assertEqual(len(keys), 1, "kept under one key per project")


if __name__ == "__main__":
    unittest.main()

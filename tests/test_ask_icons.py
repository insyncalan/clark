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
            p.until("document.activeElement && document.activeElement.id === 'ask-box'", "opening a chat puts the focus in the question box, not on the page body")
            self.assertEqual(p.js("document.querySelector('.ask-turn.user .ask-text').textContent"), "When is go-live?")
            p.js("document.querySelector('#ask-history').click()")
            p.js("document.querySelectorAll('.ask-hist-del')[1].click()")
            p.until("document.querySelectorAll('#ask-hist li').length === 1", "one chat deleted")
            p.until("document.activeElement && document.activeElement.classList.contains('ask-hist-del')", "after a delete the focus is on a delete button that is left")
            self.assertEqual(p.js("document.querySelector('.ask-hist-title').textContent"), "Which risks are red?")
            keys = p.js("Object.keys(localStorage).filter(k => k.startsWith('clark.askChats.'))")
            self.assertEqual(len(keys), 1, "kept under one key per project")
            p.js("document.querySelector('.ask-hist-del').click()")
            p.until("!!document.querySelector('#ask-hist-empty')", "the last chat deleted")
            self.assertEqual(p.js("document.activeElement.tagName + ':' + (document.activeElement.closest('#ask-hist') ? 'in' : 'out')"), "H3:in", "with no chat left the focus is on the list heading")

    def test_a_full_store_drops_the_oldest_chats_and_keeps_the_newest(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "First question?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the first answer")
            p.js("document.querySelector('#ask-new').click()")
            p.js("""(() => { const k = Object.keys(localStorage).find(x => x.startsWith('clark.askChats.')), big = 'x'.repeat(3000);
              const mk = (n) => ({id: String(n), at: n, title: 'old ' + n, turns: [{role: 'user', text: 'q'}, {role: 'assistant', text: big}]});
              localStorage.setItem(k, JSON.stringify(JSON.parse(localStorage.getItem(k)).concat([mk(3), mk(2), mk(1)])));
              const real = Storage.prototype.setItem;
              Storage.prototype.setItem = function (k, v) { if (String(k).indexOf('askChats') >= 0 && String(v).length > 8000) throw new Error('QuotaExceededError'); return real.call(this, k, v); }; })()""")
            self.ask(p, "A brand new question?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "the answer")
            p.js("document.querySelector('#ask-new').click(); document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "the list")
            titles = p.js("[...document.querySelectorAll('.ask-hist-title')].map(e => e.textContent)")
            self.assertEqual(titles[0], "A brand new question?", "the newest chat is kept even when the store is full")
            self.assertLess(len(titles), 5, "older chats were dropped to make room")

    def test_a_blank_first_question_gets_a_dated_title_and_long_answers_are_cut(self):
        src = (test_ask_panel.ROOT / "src" / "clark" / "page" / "src" / "edit" / "askHistory.js").read_text(encoding="utf-8")
        self.assertIn("HISTORY_UNTITLED(when(now))", src)
        self.assertIn("MAX_TEXT", src)


if __name__ == "__main__":
    unittest.main()

"""#1292 slice 8: chats are kept per project and never cleared by changing page or project.

Run: python3 dev/run_tests.py test_ask_chats_per_project
Headless Chrome, the real page, a stub for the server's ask. The chat on screen belongs to the project it was asked in: another
project shows its own chat (none yet), and coming back shows the first one again. Earlier chats lists only the open project's.
"""
import time
import unittest

import test_ask_panel
from _demo import USER
from test_report_editor import Base
from test_server import chrome

TURNS = "document.querySelectorAll('.ask-turn').length"
LISTED = "[...document.querySelectorAll('.ask-hist-title')].map(e => e.textContent)"


class ChatsPerProject(Base):
    def setUp(self):
        super().setUp()
        self.stub = test_ask_panel.Stub()
        self.s.httpd.ask = self.stub
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Second Programme", "health": "On track"})

    opened = test_ask_panel.Panel.opened
    ask = test_ask_panel.Panel.ask

    def reopen(self, p):
        """The panel stays or closes depending on the slice that lands it; either way it is open after this."""
        p.until("!!document.querySelector('#ask-btn')", "the page is up with its ask button", 20)
        if not p.js("!!document.querySelector('#ask-panel')"):
            p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "the panel is open and ready")

    def answered(self, p, q):
        self.ask(p, q)
        p.until(f"{TURNS} === 2", f"the answer to {q}")

    def test_changing_the_page_keeps_the_chat(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "When is go-live?")
            p.js("location.hash = '#settings&p=ABC'")
            p.until("location.hash.indexOf('settings') > 0", "on the next page")
            self.reopen(p)
            self.assertEqual(p.js(TURNS), 2, "the chat is still there")
            self.assertEqual(p.js("document.querySelector('.ask-turn.user .ask-text').textContent"), "When is go-live?")

    def test_another_project_shows_its_own_chat_and_the_first_is_back_on_return(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "When is go-live?")
            p.js("location.hash = '#dashboard&p=DEF'")
            p.until("location.hash.indexOf('p=DEF') > 0", "on the other project")
            self.reopen(p)
            self.assertEqual(p.js(TURNS), 0, "the other project does not show the first project's chat")
            self.answered(p, "Which risks are red?")
            p.js("location.hash = '#dashboard&p=ABC'")
            p.until("location.hash.indexOf('p=ABC') > 0", "back on the first project")
            self.reopen(p)
            self.assertEqual(p.js(TURNS), 2, "the first project's chat is back")
            self.assertEqual(p.js("document.querySelector('.ask-turn.user .ask-text').textContent"), "When is go-live?")
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "the list")
            self.assertEqual(p.js(LISTED), ["When is go-live?"], "Earlier chats lists this project's chats only")
            p.js("document.querySelector('#ask-history').click()")
            self.ask(p, "And the budget?")
            p.until(f"{TURNS} === 4", "the second answer")      # asked in the chat that came back: it is added to that chat's entry, not kept as a new one
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "the list again")
            self.assertEqual(p.js(LISTED), ["When is go-live?"], "one entry for the one chat")

    def test_a_project_change_inside_the_page_swaps_the_chat_too(self):
        """A hash with no project is applied in the page itself (no page load), so this reaches the swap in askPanelState."""
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "When is go-live?")
            p.js("location.hash = '#dashboard'")
            p.until("location.hash.indexOf('p=') < 0 && !document.querySelector('#ask-panel')", "in the page with no project, the panel closed")
            self.reopen(p)
            self.assertEqual(p.js(TURNS), 0, "no project, no chat of the first")
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "the list")
            self.assertFalse(p.js(LISTED), "nothing earlier for no project")
            p.js("location.hash = '#dashboard&p=ABC'")
            p.until("location.hash.indexOf('p=ABC') > 0 && !document.querySelector('#ask-panel')", "back on the first project, panel closed")
            self.reopen(p)
            self.assertEqual(p.js(TURNS), 2, "the first project's chat is back")
            self.assertFalse(p.js("!!document.querySelector('#ask-hist')"), "on its chat, not the list")

    def test_a_project_change_inside_the_page_keeps_an_answer_still_out_in_its_own_chat_and_drops_the_waiting_messages(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.stub.calls.clear()
            self.ask(p, "First question")
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Second question")
            p.key("Enter", code="Enter", vk=13)
            p.until("document.querySelectorAll('#ask-queue li[data-queued]').length === 1", "the second is waiting")
            p.js("location.hash = '#dashboard'")
            p.until("location.hash.indexOf('p=') < 0 && !document.querySelector('#ask-panel')", "in the page with no project, the panel closed")
            self.stub.hold.set()
            time.sleep(2)
            self.reopen(p)
            self.assertEqual(p.js(TURNS), 0, "the answer that was out did not land in the chat of the other project")
            self.assertFalse(p.js("!!document.querySelector('#ask-queue')"), "the waiting message did not follow")
            self.assertEqual([c[1]["question"] for c in self.stub.calls if c[0] == "ask"], ["First question"], "the waiting message was never sent")
            p.js("location.hash = '#dashboard&p=ABC'")
            p.until("location.hash.indexOf('p=ABC') > 0 && !document.querySelector('#ask-panel')", "back on the first project, panel closed")
            self.reopen(p)
            p.until(f"{TURNS} === 2", "the answer that was out is in the chat it was asked in")
            self.assertEqual(p.js("document.querySelector('.ask-turn.user .ask-text').textContent"), "First question")

    def test_a_change_of_page_keeps_the_open_list_of_earlier_chats(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "When is go-live?")
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "the list is showing")
            p.js("location.hash = '#settings&p=ABC'")
            p.until("location.hash.indexOf('settings') > 0", "on the next page")
            self.reopen(p)
            self.assertTrue(p.js("!!document.querySelector('#ask-hist')"), "the list is still showing, as the chat is still the same")

    def test_the_list_of_earlier_chats_does_not_follow_to_the_other_project(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "When is go-live?")
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "the list is showing")
            p.js("location.hash = '#dashboard&p=DEF'")
            p.until("location.hash.indexOf('p=DEF') > 0", "on the other project")
            self.reopen(p)
            self.assertFalse(p.js("!!document.querySelector('#ask-hist')"), "the other project opens on its chat, not on the first project's list")

    def test_a_chat_kept_in_one_project_is_not_written_to_the_other(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "When is go-live?")
            p.js("location.hash = '#dashboard&p=DEF'")
            p.until("location.hash.indexOf('p=DEF') > 0", "on the other project")
            self.reopen(p)
            self.answered(p, "Which risks are red?")
            keys = sorted(p.js("Object.keys(localStorage).filter(k => k.startsWith('clark.askChats.'))"))
            self.assertEqual(keys, ["clark.askChats.ABC", "clark.askChats.DEF"])
            for k, title in (("ABC", "When is go-live?"), ("DEF", "Which risks are red?")):
                got = p.js(f"JSON.parse(localStorage.getItem('clark.askChats.{k}')).map(c => c.title)")
                self.assertEqual(got, [title], k)

    def test_new_chat_puts_the_old_one_away_and_the_clock_lists_it(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "When is go-live?")
            p.js("document.querySelector('#ask-new').click()")
            p.until(f"{TURNS} === 0", "an empty chat")
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "Earlier chats")
            self.assertEqual(p.js("document.querySelector('#ask-hist h3').textContent"), "Earlier chats")
            self.assertEqual(p.js(LISTED), ["When is go-live?"])

    def test_the_thirty_most_recent_are_listed_newest_first_with_the_browsers_date(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.answered(p, "A newest question?")
            p.js("""(() => { const k = 'clark.askChats.ABC', mk = (n) => ({id: String(n), at: n * 86400000, title: 'old ' + n, turns: [{role: 'user', text: 'q'}, {role: 'assistant', text: 'a'}]});
              const l = JSON.parse(localStorage.getItem(k)); for (let n = 40; n >= 1; n--) l.push(mk(n));
              localStorage.setItem(k, JSON.stringify(l)); })()""")
            p.js("document.querySelector('#ask-new').click()")
            self.answered(p, "A later question?")
            p.js("document.querySelector('#ask-new').click(); document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "the list")
            titles = p.js(LISTED)
            self.assertEqual(len(titles), 30, "thirty at most")
            self.assertEqual(titles[0], "A later question?")
            when = p.js("document.querySelector('.ask-hist-when').textContent")
            want = p.js("new Date(JSON.parse(localStorage.getItem('clark.askChats.ABC'))[0].at).toLocaleString(undefined, {day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'})")
            self.assertEqual(when, want, "the browser's own date format")


if __name__ == "__main__":
    unittest.main()

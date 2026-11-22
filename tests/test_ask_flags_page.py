"""#1293 slice A: the claims check is not thrown away. What ask_service sends in `flags` is shown under the answer in the ask panel,
in a real browser against the real page (the answer comes from a STUB provider; nothing here calls a model).

Run: python3 dev/run_tests.py test_ask_flags_page
Covers: a wrong ID, a wrong title and an unreadable reply each show the server's own words under the answer; a clean answer shows
no note; a reply with "CITE: none." and one bad CHANGE line still shows its answer with one line about the dropped change. No new
sentence is written in the page: it shows f.message. Fictional data only.
"""
import unittest
from unittest import mock

from _demo import USER
from _paths import ROOT
from test_report_editor import Base
from test_server import chrome
from clark import ask, ask_apply, ask_passages, ask_service

PANEL = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "AskPanel.jsx").read_text(encoding="utf-8")


class Flags(Base):
    def setUp(self):
        super().setUp()
        self.action = self.demo.action(owner="Sam Lee", client_visible=1)
        self.provider = ask.StubProvider(reply="")
        self.s.httpd.ask = ask_service.AskService(self.store.path, self.provider, [], applier=ask_apply.AskApply(self.store.path, [], USER))
        patch = mock.patch.object(ask_service.ask_passages, "folder_data", lambda *_a, **_k: ask_passages.FolderData(passages=()))
        patch.start()
        self.addCleanup(patch.stop)

    def asked(self, reply):
        self.provider.reply = reply
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "the panel is ready")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("What is late?")
            p.key("Enter", code="Enter", vk=13)
            p.until("document.querySelector('#ask-panel').innerText.includes('Answer line')", "an answer came")
            return p.js("document.querySelector('#ask-panel').innerText")

    def test_a_wrong_id_is_said_under_the_answer(self):
        self.assertIn("ABC-A-777, which isn't in this project", self.asked("Answer line about ABC-A-777."))

    def test_a_wrong_title_is_said_with_what_the_report_says(self):
        text = self.asked(f'Answer line: {self.action} is called "Pay the supplier".')
        self.assertIn("wrong title", text)
        self.assertIn("Draft the cut-over plan", text)

    def test_an_unreadable_reply_is_shown_whole_with_the_unreadable_line(self):
        text = self.asked("Answer line\nCITE: the plan")
        self.assertIn("CITE: the plan", text)
        self.assertIn(ask.UNREADABLE, text)

    def test_a_clean_answer_has_no_note(self):
        text = self.asked("Answer line.\nCITE: none")
        self.assertNotIn("CITE", text)
        self.assertNotIn("left out", text)
        self.assertNotIn(ask.UNREADABLE, text)

    def test_a_bad_change_line_leaves_the_answer_and_one_line(self):
        text = self.asked("Answer line.\nCITE: none.\nCHANGE: not json")
        self.assertIn(ask.CHANGE_UNREADABLE, text)
        self.assertNotIn(ask.UNREADABLE, text)

    def test_the_page_writes_no_sentence_of_its_own_for_flags(self):
        self.assertIn("f.message", PANEL)
        self.assertNotIn("isn't in this project", PANEL)


if __name__ == "__main__":
    unittest.main()

"""#1292 S11: the quick bar's "Ask ... in ask clark" row (Ctrl or Cmd + K, then a typed question).

Run: python3 dev/run_tests.py test_palette_ask_row
Any typed text adds the row; it is first when the text reads like a question and last otherwise; Enter or a click opens the panel with
the words in the box and sends nothing; Ctrl or Cmd + Enter hands the question over and it is asked at once; with nothing typed there is
no row and Ctrl or Cmd + Enter does nothing. Chrome is required.
"""
import unittest

from test_ask_panel import Stub
from test_palette import Base, CTRL
from test_server import chrome, wait


class AskRow(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def asks(self):
        return [c for c in self.stub.calls if c[0] == "ask"]

    def test_the_row_is_last_for_a_plain_word_and_first_for_a_question(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("pilot")
            rows = p.rows(True)
            self.assertEqual([rows[-1][0], rows[-1][1]], ["Ask clark", "Ask “pilot” in ask clark"], "last when it does not read like a question")
            self.assertEqual(rows[0][0], "Milestone", "the search comes first")
            p.find("what is late?")
            self.assertEqual(p.rows(True)[0][:2], ["Ask clark", "Ask “what is late?” in ask clark"], "first when it reads like a question")
            p.find("how do I publish")
            self.assertEqual(p.rows(True)[0][0], "Ask clark", "a question word first also counts")
            p.find("Island")
            self.assertEqual(p.rows(True)[-1][0], "Ask clark", "a word that only starts like a question word does not count")

    def test_nothing_typed_has_no_row_and_nothing_found_still_offers_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            self.assertFalse([r for r in p.rows(True) if r[0] == "Ask clark"], "no row without words")
            p.find("zzqx")
            self.assertEqual([r[:2] for r in p.rows(True)], [["Ask clark", "Ask “zzqx” in ask clark"]])
            self.assertEqual(p.active(), "Ask “zzqx” in ask clark", "it is the one Enter reaches")

    def test_enter_opens_the_panel_with_the_words_and_sends_nothing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("zzqx")
            p.key("Enter", 0, "Enter", 13)
            p.until("!document.querySelector('#palette')", "the bar closed")
            p.until("!!document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled", "the panel is ready")
            p.until("document.querySelector('#ask-box').value === 'zzqx'", "the words are in the box")
            self.assertEqual(self.asks(), [], "Enter alone sends nothing")

    def test_a_click_is_as_enter(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("zzqx")
            p.click("#palette .pal-row")
            p.until("!document.querySelector('#palette')", "the bar closed")
            p.until("!!document.querySelector('#ask-box') && document.querySelector('#ask-box').value === 'zzqx'", "the words are in the box")
            self.assertEqual(self.asks(), [])

    def test_ctrl_enter_hands_it_over_at_once(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("when is the pilot live?")
            p.key("Enter", CTRL, "Enter", 13)
            p.until("!document.querySelector('#palette')", "the bar closed")
            self.assertTrue(wait(lambda: self.asks(), 15), "the question was asked")
            self.assertEqual(self.asks()[0][1]["question"], "when is the pilot live?")
            p.until("/The pilot goes live/.test(document.querySelector('#ask-panel').innerText)", "the answer is in the chat")
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "", "the box is empty after the send")

    def test_a_question_mark_alone_or_a_capital_makes_it_first(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("pilot live?")
            self.assertEqual(p.rows(True)[0][0], "Ask clark", "a question mark at the end")
            p.find("What now")
            self.assertEqual(p.rows(True)[0][0], "Ask clark", "a capital question word")
            p.find("pilot live")
            self.assertEqual(p.rows(True)[-1][0], "Ask clark")

    def test_a_long_text_is_cut_in_the_row_and_handed_over_whole(self):
        long = "when is the pilot going live and who signs it off " * 3
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find(long)
            label = p.rows(True)[0][1]
            self.assertTrue(label.endswith("…” in ask clark"), label)
            self.assertLess(len(label), 90)
            p.key("Enter", CTRL, "Enter", 13)
            self.assertTrue(wait(lambda: self.asks(), 15))
            self.assertEqual(self.asks()[0][1]["question"], long.strip())

    def test_cmd_enter_is_as_ctrl_enter(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("zzqx")
            p.key("Enter", 4, "Enter", 13)
            self.assertTrue(wait(lambda: self.asks(), 15), "the question was asked")

    def test_handed_over_while_an_answer_is_made_it_waits_its_turn(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("first one")
            p.key("Enter", CTRL, "Enter", 13)
            self.assertTrue(wait(lambda: self.asks(), 15), "the first was asked")
            p.show()
            p.find("second one")
            p.key("Enter", CTRL, "Enter", 13)
            p.until("document.querySelectorAll('#ask-panel .ask-queue li').length === 1 || /second one/.test(document.querySelector('#ask-panel').innerText)", "the second waits above the box")
            self.assertEqual(len(self.asks()), 1, "only one is out at a time")
            self.stub.hold.set()
            self.assertTrue(wait(lambda: len(self.asks()) == 2, 20), "the second is sent after the first")

    def test_ctrl_enter_with_nothing_typed_does_nothing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.key("Enter", CTRL, "Enter", 13)
            self.assertTrue(p.js("!!document.querySelector('#palette[open]')"), "still open")
            self.assertEqual(self.asks(), [])
            self.assertFalse(p.js("!!document.querySelector('#ask-panel')"))

    def test_ctrl_enter_when_asking_is_off_keeps_the_words(self):
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("zzqx")
            p.key("Enter", CTRL, "Enter", 13)
            p.until("!!document.querySelector('#ask-box')", "the panel opened")
            p.until("document.querySelector('#ask-box').value === 'zzqx'", "the words are kept, not lost")
            self.assertEqual(self.asks(), [])


if __name__ == "__main__":
    unittest.main()

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
            self.assertEqual([rows[-1][0], rows[-1][1]], ["ask clark", "Ask “pilot” in ask clark"], "last when it does not read like a question")
            self.assertEqual(rows[0][0], "Milestone", "the search comes first")
            p.find("what is late?")
            self.assertEqual(p.rows(True)[0][:2], ["ask clark", "Ask “what is late?” in ask clark"], "first when it reads like a question")
            p.find("how do I publish")
            self.assertEqual(p.rows(True)[0][0], "ask clark", "a question word first also counts")
            p.find("Island")
            self.assertEqual(p.rows(True)[-1][0], "ask clark", "a word that only starts like a question word does not count")

    def test_nothing_typed_has_no_row_and_nothing_found_still_offers_it(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            self.assertFalse([r for r in p.rows(True) if r[0] == "ask clark"], "no row without words")
            p.find("zzqx")
            self.assertEqual([r[:2] for r in p.rows(True)], [["ask clark", "Ask “zzqx” in ask clark"]])
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
            self.assertEqual(p.rows(True)[0][0], "ask clark", "a question mark at the end")
            p.find("What now")
            self.assertEqual(p.rows(True)[0][0], "ask clark", "a capital question word")
            p.find("pilot live")
            self.assertEqual(p.rows(True)[-1][0], "ask clark")

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

    def test_handed_over_with_ctrl_enter_keeps_a_draft_that_was_in_the_box(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("draft words")
            p.key("Enter", 0, "Enter", 13)
            p.until("!!document.querySelector('#ask-box') && document.querySelector('#ask-box').value === 'draft words'", "the draft is in the box")
            p.show()
            p.find("zzqx")
            p.key("Enter", CTRL, "Enter", 13)
            self.assertTrue(wait(lambda: self.asks(), 15), "the question was asked")
            p.until("/The pilot goes live/.test(document.querySelector('#ask-panel').innerText)", "the answer is in the chat")
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "draft words", "the send leaves what was typed in the box")

    def test_a_handed_over_question_is_taken_once_and_not_asked_again_when_the_panel_is_closed_and_opened(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("zzqx")
            p.key("Enter", CTRL, "Enter", 13)
            self.assertTrue(wait(lambda: self.asks(), 15), "the question was asked")
            p.until("/The pilot goes live/.test(document.querySelector('#ask-panel').innerText)", "the answer is in the chat")
            p.js("document.querySelector('#ask-close').click()")
            p.until("!document.querySelector('#ask-panel')", "the panel closed")
            p.show()
            p.find("ask clark")
            p.key("Enter", 0, "Enter", 13)
            p.until("!!document.querySelector('#ask-box')", "the panel opened again")
            self.assertFalse(wait(lambda: len(self.asks()) > 1, 3), "it is not asked a second time")

    def test_ctrl_enter_while_composing_does_nothing_and_a_real_one_is_taken_over_by_the_bar(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("zzqx")
            send = "(function(c){var q=document.querySelector('#palette-q'); return q.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,isComposing:c,bubbles:true,cancelable:true}));})"
            p.js(send + "(true)")
            self.assertTrue(p.js("!!document.querySelector('#palette[open]')"), "a key press that is part of a composition does nothing")
            self.assertEqual(self.asks(), [])
            self.assertFalse(p.js(send + "(false)"), "the real Ctrl + Enter is not left to the browser")
            self.assertTrue(wait(lambda: self.asks(), 15), "and it asks")

    def test_handed_over_when_the_queue_is_full_goes_in_the_box_not_the_queue(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.visit(cdp)
            for n in range(6):
                p.show()
                p.find(f"question {n}")
                p.key("Enter", CTRL, "Enter", 13)
                if n == 0:
                    self.assertTrue(wait(lambda: self.asks(), 15), "the first was asked")
                else:
                    p.until(f"document.querySelectorAll('#ask-queue li[data-queued]').length === {n}", f"{n} wait")
            p.show()
            p.find("question 6")
            p.key("Enter", CTRL, "Enter", 13)
            p.until("document.querySelector('#ask-box').value === 'question 6'", "the one that does not fit is kept in the box")
            self.assertEqual(p.js("document.querySelectorAll('#ask-queue li[data-queued]').length"), 5, "the queue stays at its limit")
            self.stub.hold.set()


if __name__ == "__main__":
    unittest.main()

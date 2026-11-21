"""Row 1292 item 15: while the ask is busy the status line reads 'Working. You can close this: it carries on.' in Classic only.

The Classic working row stays 'Asking Claude · Working Ns'; Cards keeps 'Working' and no sentence. Chrome at 1400 and 900 only.
"""
import unittest

import test_ask_progress_1292 as P
from test_server import chrome

SENTENCE = "Working. You can close this: it carries on."
STATUS = "document.querySelector('#ask-status').textContent.trim()"


def at(cdp, p, width):
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)


class BusyClassic(P.LayeredBase):
    __test__ = True

    def test_the_sentence_shows_only_while_busy_and_the_working_row_is_unchanged(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            for width in (1400, 900):
                at(cdp, p, width)
                self.assertNotIn("carries on", p.js(STATUS), f"{width}: idle shows no sentence")
            self.ask(p, "Anything?")
            p.until("!!document.querySelector('#ask-step')", "the working row")
            for width in (1400, 900):
                at(cdp, p, width)
                self.assertEqual(p.js(STATUS), SENTENCE, f"{width}: busy status line")
                self.assertRegex(p.js("document.querySelector('#ask-step').textContent"), r"^Asking Claude · Working \d+s$", f"{width}: working row")
                self.assertEqual(p.js("document.querySelectorAll('#ask-panel *').length && [].filter.call(document.querySelectorAll('#ask-panel *'), function(e){return e.children.length === 0 && e.textContent.indexOf('carries on') >= 0;}).map(function(e){return e.id;})"), ["ask-status"], f"{width}: sentence only in the status line")
            self.stub.hold.set()
            p.until("document.querySelector('#ask-step') === null", "the answer came")
            self.assertNotIn("carries on", p.js(STATUS), "idle again: no sentence")


class BusyThenClosed(P.LayeredBase):
    """The sentence's promise, tied to what happens: close the panel while the busy line shows and the question carries on."""
    __test__ = True

    def test_closing_while_the_busy_line_shows_keeps_the_question_running_and_the_answer_is_there_on_reopen(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            for n, width in enumerate((1400, 900), start=1):
                at(cdp, p, width)
                self.stub.hold.clear()
                self.ask(p, f"Question {n}?")
                p.until("!!document.querySelector('#ask-step')", f"{width}: the working row")
                self.assertEqual(p.js(STATUS), SENTENCE, f"{width}: the busy line shows")
                p.key("Escape", code="Escape", vk=27)
                p.until("document.querySelector('#ask-panel') === null", f"{width}: closed")
                self.assertEqual(self.stub.count("stop"), 0, f"{width}: closing called no stop route")
                self.assertEqual(self.stub.count("ask"), n, f"{width}: the question is still the one out")
                if width == 1400:        # the top-bar button is not drawn at 900
                    self.assertEqual(p.js("document.querySelector('#ask-btn').getAttribute('aria-label')"), "ask clark, working", f"{width}: still working")
                self.stub.hold.set()
                p.key("/", code="Slash", vk=191)
                p.until("!!document.querySelector('#ask-panel')", f"{width}: reopened")
                p.until(f"document.querySelectorAll('.ask-turn').length === {2 * n}", f"{width}: the answer is there on reopen")
                self.assertEqual(self.stub.count("stop"), 0, f"{width}: no stop route at all")
                self.assertNotIn("carries on", p.js(STATUS), f"{width}: idle again, no sentence")


class BusyCards(P.LayeredBase):
    __test__ = True
    classic = False

    def test_cards_keeps_working_and_no_sentence(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "Anything?")
            p.until("!!document.querySelector('#ask-quip')", "the quip")
            for width in (1400, 900):
                at(cdp, p, width)
                self.assertEqual(p.js(STATUS), "Working", f"{width}: Cards status line")
            self.stub.hold.set()


if __name__ == "__main__":
    unittest.main()

"""Row 1293 AP10 and AP3: the change card in a real browser at 1400 and 900 px (the answer comes from a STUB provider; nothing calls a model).

Run: python3 dev/run_tests.py test_ask_change_card_1293
Covers: the card shows the title of the item it changes; a change with no title is refused and shows no card and saves nothing; "Owner: TBC" is
printed when the stored owner is TBC; the sentence for changes cut at the limit (ask.CHANGE_LIMIT) is on the page with exactly the limit of cards.
No new words: every string checked is already in the code (ask.CHANGE_LIMIT, ask_apply.NOT_A_CHANGE, askWords.js). Fictional data only.
"""
import json
import unittest

from test_ask_change_page import Card
from test_server import chrome
from clark import ask, ask_apply

WIDTHS = (1400, 900)


class ChangeCard(Card):
    def at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)

    def change(self, ref, title, **more):
        body = {"op": "change", "id": ref, "status": "Closed", **more}
        if title is not None:
            body["current_title"] = title
        return "CHANGE: " + json.dumps(body)

    def test_the_card_shows_the_title_of_the_item_it_changes_at_1400_and_900(self):
        self.says(self.change(self.action, "Draft the cut-over plan"))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            for width in WIDTHS:
                self.at(cdp, p, width)
                self.assertEqual(p.js("[...document.querySelectorAll('[data-ask-change] [data-ask-title]')].map(e => e.textContent)"),
                                 ["Draft the cut-over plan"], width)

    def test_a_change_with_no_title_shows_no_card_is_refused_and_saves_nothing(self):
        self.says(self.change(self.action, None))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("!!document.querySelector('[data-ask-refused]')", "the refusal")
            for width in WIDTHS:
                self.at(cdp, p, width)
                self.assertEqual(p.js("document.querySelectorAll('[data-ask-apply]').length"), 0, f"{width}: nothing to Apply")
                self.assertEqual(p.js("document.querySelector('[data-ask-refused]').textContent").strip(), ask_apply.NOT_A_CHANGE, width)
            self.assertEqual(self.status(), "Open", "a change with no title saved nothing")

    def test_owner_tbc_is_printed_when_the_stored_owner_is_tbc_at_1400_and_900(self):
        tbc = self.demo.action(owner="TBC", description="Unassigned job")
        self.says(self.change(tbc, "Unassigned job"))
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            for width in WIDTHS:
                self.at(cdp, p, width)
                self.assertEqual(p.js("[...document.querySelectorAll('[data-ask-change] [data-ask-owner]')].map(e => e.textContent)"),
                                 ["Owner: TBC"], width)

    def test_the_change_limit_line_at_1400_and_900(self):
        self.assertEqual(ask.CHANGE_LIMIT, "Only the first 5 changes are offered. Ask again for the rest.")
        lines = [self.change(self.demo.action(description=f"Job {i}"), f"Job {i}") for i in range(ask.MAX_CHANGES + 1)]
        self.says(*lines)
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until(f"document.querySelectorAll('[data-ask-change]').length === {ask.MAX_CHANGES}", "the cards")
            for width in WIDTHS:
                self.at(cdp, p, width)
                self.assertEqual(p.js("document.querySelectorAll('[data-ask-change]').length"), ask.MAX_CHANGES, width)
                self.assertEqual(p.js("document.querySelector('#ask-panel').innerText.split(%s).length - 1" % json.dumps(ask.CHANGE_LIMIT)), 1,
                                 f"{width}: the limit sentence is on the page once")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), f"{width}: no sideways scroll")

    def test_five_changes_are_at_the_limit_and_say_nothing_of_it(self):
        lines = [self.change(self.demo.action(description=f"Job {i}"), f"Job {i}") for i in range(ask.MAX_CHANGES)]
        self.says(*lines)
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until(f"document.querySelectorAll('[data-ask-change]').length === {ask.MAX_CHANGES}", "the cards")
            self.assertNotIn(ask.CHANGE_LIMIT, p.js("document.querySelector('#ask-panel').innerText"))


if __name__ == "__main__":
    unittest.main()

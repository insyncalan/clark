"""Row 1293 (AP10 of the old ticket, AP6 here): the change card shows the item's title and its owner: "Owner: TBC" when the stored owner is
TBC, and no owner line when the owner is blank or the item is new. At 1400 and 900, Classic.

Run: python3 dev/run_tests.py test_ask_change_card_1293
A real browser, the real page, a stub provider. Fictional data only.
"""
import json
import unittest

from test_ask_change_page import Card
from test_server import chrome


class ChangeCard(Card):
    def line(self, ref, title, **more):
        return "CHANGE: " + json.dumps({"op": "change", "id": ref, "current_title": title, "status": "Closed", **more})

    def test_the_card_shows_title_and_owner_tbc(self):
        tbc = self.demo.action(owner="TBC", description="Unassigned job")
        blank = self.demo.action(description="Blank job")
        self.store.con.execute("UPDATE actions SET owner = '  ' WHERE id = ?", (blank,))
        self.store.con.commit()
        new = "CHANGE: " + json.dumps({"op": "new", "kind": "action", "title": "Book the room", "owner": "Zed Ng"})
        self.says(self.line(tbc, "Unassigned job"), self.line(blank, "Blank job"), new)
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask_it(p)
            self.card(p)
            p.until("document.querySelectorAll('[data-ask-change]').length === 3", "the cards")
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                card = lambda i, sel: p.js(f"[...document.querySelectorAll('[data-ask-change]')[{i}].querySelectorAll('{sel}')].map(e => e.textContent)")
                self.assertEqual(card(0, "[data-ask-title]"), ["Unassigned job"], width)
                self.assertEqual(card(0, "[data-ask-owner]"), ["Owner: TBC"], width)
                self.assertEqual(card(1, "[data-ask-title]"), ["Blank job"], width)
                self.assertEqual(card(1, "[data-ask-owner]"), [], f"{width}: a blank owner shows no owner line")
                self.assertEqual(card(2, "[data-ask-owner]"), [], f"{width}: a new item shows no owner line")


if __name__ == "__main__":
    unittest.main()

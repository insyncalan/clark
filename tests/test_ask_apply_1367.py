"""Row 1367: a Draft that quotes a row the report hides still goes through the approval panel and the client-output checks.

Run: python3 dev/run_tests.py test_ask_apply_1367
Quick tier: a real server and store with a stub provider (as test_ask_route). Fictional data only.
"""
import json
import unittest

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
import test_ask_route as route
from clark import publish, to_client


class DraftQuotingAHiddenItem(route.Base):
    def draft_quoting(self, marker):
        body = json.dumps({"title": "This week", "html": f"<p>{marker} is moving.</p>", "sec": "PUB-S-001"})
        self.provider.reply = f"Here.\nDRAFT: {body}"
        status, got = self.question("Write this week's summary of PUB-A-011")
        self.assertEqual(status, 200, got)
        return got

    def test_a_draft_quoting_a_hidden_item_still_needs_the_approval_panel(self):
        marker = plant.load()["markers"]["PUB-A-011"]
        before = self.counts()
        got = self.draft_quoting(marker)
        # 1. the draft is only data for the panel: nothing is saved, no change is offered, and it holds the quote as written
        self.assertIn(marker, got["draft"]["html"])
        self.assertEqual(got["changes"], [])
        self.assertEqual(self.counts(), before, "the reply wrote nothing; only the panel's choice can")
        # 2. the quote is not an unknown id: the owner may read the hidden row, so it is the panel (the owner's eyes) that decides
        self.assertNotIn(("unknown_id", "PUB-A-011"), [(f["kind"], f["ref"]) for f in got["flags"]])
        # 3. the client-output checks still refuse the quote in a copy for the client, and pass the same copy without it
        data = self.published_with(got["draft"]["html"])
        self.assertEqual(to_client.check_copy(data, markers=(marker,)), ["text that was meant to be left out"])
        self.assertEqual(to_client.check_copy(self.published_with("<p>Nothing to add.</p>"), markers=(marker,)), [])

    def published_with(self, html):
        given = plant.inputs()
        given["sections"] = list(given["sections"]) + [
            {"project": "PUB", "id": "s-draft", "type": "text", "title": "Draft", "body": html, "beside": 0, "hidden": 0, "sort_order": 99}]
        return json.dumps(publish.select(given)).encode("utf-8")


if __name__ == "__main__":
    unittest.main()

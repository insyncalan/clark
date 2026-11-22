"""Row 1367 (AP1, DoD1): archived items are not read by ask clark, whatever the question asks, and the note does not claim they were.

Run: python3 dev/run_tests.py test_ask_1367_archived_1367
Fictional data only (the publish plant). The ruling (22-11): archived items are NOT read, as built (src/clark/ask_data.py own_rows).
"""
import unittest

from _paths import SRC  # noqa: F401

from test_ask_1367 import read, text_of
from clark import ask_data

ASKS = ("show me the archived actions", "what did we archive? list every archived milestone, risk, decision and use case", "include archived items")


def archived_ids(given):
    return {r["id"] for k in ask_data.KIND_ORDER for r in (given["data"].get(k) or ()) if r.get("archived")}


class ArchivedStayOut(unittest.TestCase):
    def test_a_question_that_asks_for_archived_items_still_gets_none_and_the_note_does_not_claim_them(self):
        got, given = read()
        ids = archived_ids(given)
        self.assertTrue(ids, "the plant holds archived rows, or this test proves nothing")
        plain_counts = got.counts
        for question in ASKS:
            got, _ = read(question)
            text = text_of(got)
            for i in ids:
                self.assertNotIn(i, text, f"{i} is archived and is not read, even for: {question}")
            note = " ".join(ask_data.left_out_lines(got.counts)).lower()
            self.assertNotIn("archiv", note, "the note does not claim archived items were read")
            self.assertNotIn("archiv", " ".join(ask_data.partial_lines(got.counts)).lower())
            self.assertEqual(got.counts, plain_counts, "asking for archived items changes no count: the same rows are read")


if __name__ == "__main__":
    unittest.main()

"""Item 1158 (was row 811): the peek has no "Needed from the client" switch any more, in Edit, in View or in a published file, and the
row no longer carries the flag. The flag stays stored (test_changes_client_action). Looked at in the page at 1400 and 900 px.

Run: python3 dev/run_tests.py test_peek_client_action
"""
import unittest

from _paths import ROOT
from test_peek_latest import Browser as _Harness, OVERDUE
from test_server import chrome


class Page(unittest.TestCase):
    setUp = _Harness.setUp
    fresh = _Harness.fresh
    load = _Harness.load

    def test_the_source_has_no_switch_and_the_row_does_not_carry_the_flag(self):
        peek = (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8")
        self.assertNotIn("PeekNeeded", peek)
        self.assertNotIn("Needed from the client", peek)
        items = (ROOT / "src/clark/page/src/workItems.js").read_text(encoding="utf-8")
        self.assertNotIn("client_action", items)

    def test_no_peek_has_the_switch(self):
        risk, decision = self.data["raid"][0]["id"], self.data["decisions"][0]["id"]
        probe = "!!document.querySelector('#peek [data-pk-needed]') || /Needed from the client/.test(document.querySelector('#peek').textContent)"
        for width in (1400, 900):
            for item, edit in ((OVERDUE, True), (risk, True), (decision, True), (OVERDUE, False)):
                with self.subTest(width=width, item=item, edit=edit), chrome() as cdp:
                    sent, sid = self.load(cdp, width, item, edit=edit)
                    self.assertFalse(cdp.js(probe, sid))


if __name__ == "__main__":
    unittest.main()

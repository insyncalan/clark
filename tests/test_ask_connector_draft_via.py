"""Row 1306 F6: a draft written in a run that read a connector says so above the draft (the words are in askWords.js, approved).
The server hands the names of the parts read as `via` (never what they returned); a draft from a run with no connector is unchanged.
Run: flock <lock> ~/bin/clark-chrome-slot env CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_ask_connector_draft_via
Fictional text only.
"""
import unittest

from clark.ask_service import draft_via
from test_ask_draft import DRAFT, Draft, DraftStub
from test_server import chrome

WORDS = "Written using your Mail and Calendar. Read it before you apply it."


class Server(unittest.TestCase):
    def test_a_run_that_read_a_connector_names_the_parts_on_the_draft(self):
        out = draft_via(dict(DRAFT), {"used": ["Mail", "Calendar"], "line": "x"})
        self.assertEqual(out["via"], ["Mail", "Calendar"])
        self.assertEqual({k: v for k, v in out.items() if k != "via"}, DRAFT)

    def test_no_connector_or_nothing_read_leaves_the_draft_as_it_was(self):
        self.assertEqual(draft_via(dict(DRAFT), None), DRAFT)
        self.assertEqual(draft_via(dict(DRAFT), {"used": [], "line": "x"}), DRAFT)
        self.assertIsNone(draft_via(None, {"used": ["Mail"]}))


class ViaStub(DraftStub):
    def ask(self, body):
        status, out = super().ask(body)
        if out.get("ok"):
            out["draft"]["via"] = ["Mail", "Calendar"]
        return status, out


class Page(Draft):
    def setUp(self):
        super().setUp()
        self.stub = ViaStub()
        self.s.httpd.ask = self.stub

    def test_the_card_and_the_draft_say_it_was_written_using_the_connector(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            self.assertIn(WORDS, p.js("document.querySelector('[data-ask-draftcard]').textContent"))
            self.assertEqual(p.js("document.querySelector('#ask-draft-via').textContent"), WORDS)
            self.assertEqual(p.js("document.querySelectorAll('#ask-draft-add').length"), 1, "still a card the person adds")


class Plain(Draft):
    def test_a_draft_with_no_connector_has_no_such_line(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            self.assertEqual(p.js("document.querySelectorAll('#ask-draft-via, [data-ask-draft-via]').length"), 0)


del Draft

if __name__ == "__main__":
    unittest.main()

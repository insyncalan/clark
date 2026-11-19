"""Row 1366 row 7: the answer's note "Still reading N files, so this answer may miss some." is the Classic theme's. The server sends it in its own
field of the answer (`index_note`, with `index_note_at`, the place it takes among the notes), not in the shared notes list, so the Cards page
draws only the notes it had. Classic draws it in the same list, in the same place, with the same words.

Run: python3 dev/run_tests.py test_ask_index_note_1366
Real browser, real page, a stub server; fictional text.
"""
import unittest

from test_ask_first_run_classic_1352 import Classic
from test_ask_panel import Stub
from test_server import chrome

SAID = "Still reading 120 files, so this answer may miss some."


class Reading(Stub):
    def __init__(self, note=SAID):
        super().__init__()
        self.notes = ["Two files were left out.", "Used the Mail connector."]
        self.note = note

    def ask(self, body):
        status, got = super().ask(body)
        if got.get("ok"):
            got["flags"] = [{"kind": "x", "ref": "", "message": "A flag line."}]          # the checks' lines follow all the notes
            if self.note is False:
                got.update(index_note=None, index_note_at=1)
            elif self.note is not None:
                got.update(index_note=self.note, index_note_at=1)          # between the two notes, as the server put it before
        return status, got


class Note(Classic):
    def setUp(self):
        super().setUp()
        self.stub = Reading()
        self.s.httpd.ask = self.stub

    def asked(self, cdp):
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel') && !document.querySelector('#ask-send').disabled", "ready")
        p.js("document.querySelector('#ask-box').focus()")
        p.type("What is the state of the plan?")
        p.js("document.querySelector('#ask-send').click()")
        p.until("!!document.querySelector('[data-ask-notes]')", "the notes block")
        return p

    LINES = "[...document.querySelectorAll('[data-ask-notes] li')].map(e => e.textContent)"

    def test_classic_shows_it_in_its_place_singular_and_plural(self):
        for note in (SAID, "Still reading 1 file, so this answer may miss some."):
            self.stub.note = note
            with chrome() as cdp:
                p = self.asked(cdp)
                self.assertEqual(p.js(self.LINES), ["Two files were left out.", note, "Used the Mail connector.", "A flag line."])


    def test_classic_with_no_note_draws_only_the_notes_it_was_given(self):
        self.stub.note = None
        with chrome() as cdp:
            p = self.asked(cdp)
            self.assertEqual(p.js(self.LINES), ["Two files were left out.", "Used the Mail connector.", "A flag line."])


    def test_classic_draws_nothing_for_an_empty_or_malformed_note(self):
        self.stub.note = False
        with chrome() as cdp:
            p = self.asked(cdp)
            self.assertEqual(p.js(self.LINES), ["Two files were left out.", "Used the Mail connector.", "A flag line."])


class CardsNote(Note):
    THEME = None

    def test_classic_shows_it_in_its_place_singular_and_plural(self):
        pass

    def test_classic_with_no_note_draws_only_the_notes_it_was_given(self):
        pass

    def test_classic_draws_nothing_for_an_empty_or_malformed_note(self):
        pass

    def test_cards_shows_only_the_notes_it_had(self):
        with chrome() as cdp:
            p = self.asked(cdp)
            self.assertEqual(p.js(self.LINES), ["Two files were left out.", "Used the Mail connector.", "A flag line."])


if __name__ == "__main__":
    unittest.main()

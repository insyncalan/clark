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
        self.raw = None                      # fields set as the test says, whatever their type

    def ask(self, body):
        status, got = super().ask(body)
        if got.get("ok"):
            got["flags"] = [{"kind": "x", "ref": "", "message": "A flag line."}]          # the checks' lines follow all the notes
            if self.raw is not None:
                got.update(self.raw)
            elif self.note is False:
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


    TURNS = "[...document.querySelectorAll('.ask-turn')].map(e => e.textContent.trim())"

    def lines_with(self, **raw):
        self.stub.raw = raw
        with chrome() as cdp:
            p = self.asked(cdp)
            self.turns = p.js(self.TURNS)
            return p.js(self.LINES)

    def test_classic_without_a_whole_place_puts_the_note_after_the_other_notes_before_the_flag_line(self):
        last = ["Two files were left out.", "Used the Mail connector.", SAID, "A flag line."]
        self.assertEqual(self.lines_with(index_note=SAID), last, "no index_note_at")
        for at in ("1", 1.5, None, True, [1], {}):
            self.assertEqual(self.lines_with(index_note=SAID, index_note_at=at), last, repr(at))

    def test_classic_places_a_whole_number_place_and_clamps_one_past_the_end(self):
        two = ["Two files were left out.", "Used the Mail connector."]
        self.assertEqual(self.lines_with(index_note=SAID, index_note_at=0), [SAID] + two + ["A flag line."])
        self.assertEqual(self.lines_with(index_note=SAID, index_note_at=2), two + [SAID, "A flag line."])
        self.assertEqual(self.lines_with(index_note=SAID, index_note_at=99), two + [SAID, "A flag line."])

    def test_classic_draws_no_note_for_an_empty_string_a_number_or_an_object(self):
        two = ["Two files were left out.", "Used the Mail connector.", "A flag line."]
        for bad in ("", 5, 0, {}, {"a": 1}, [SAID], True):
            self.assertEqual(self.lines_with(index_note=bad, index_note_at=1), two, repr(bad))
            self.assertEqual(len(self.turns), 3, f"the question, the answer and the notes block, and no turn made of {bad!r}: {self.turns}")


class CardsNote(Note):
    THEME = None

    def test_classic_shows_it_in_its_place_singular_and_plural(self):
        pass

    def test_classic_with_no_note_draws_only_the_notes_it_was_given(self):
        pass

    def test_classic_draws_nothing_for_an_empty_or_malformed_note(self):
        pass

    test_classic_without_a_whole_place_puts_the_note_after_the_other_notes_before_the_flag_line = test_classic_draws_nothing_for_an_empty_or_malformed_note
    test_classic_places_a_whole_number_place_and_clamps_one_past_the_end = test_classic_draws_nothing_for_an_empty_or_malformed_note
    test_classic_draws_no_note_for_an_empty_string_a_number_or_an_object = test_classic_draws_nothing_for_an_empty_or_malformed_note

    def test_cards_shows_only_the_notes_it_had(self):
        with chrome() as cdp:
            p = self.asked(cdp)
            self.assertEqual(p.js(self.LINES), ["Two files were left out.", "Used the Mail connector.", "A flag line."])


if __name__ == "__main__":
    unittest.main()

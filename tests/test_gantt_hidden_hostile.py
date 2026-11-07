"""Hostile gantt_hidden_columns strings, checked on the client copy (publish.select -> data.gantt) by the EXACT set of columns that
reach it, so both a leak (a default-hidden column shown) and over-hiding (a column dropped that nothing asked to hide) fail.
Cases already in test_gantt_publish are not repeated; these add exact sets, odd whitespace, odd names and the owner-specific forms."""
import json
import unittest

import _publish_fixture  # noqa: F401
from _paths import SRC  # noqa: F401
from clark import publish, store as store_module
from test_gantt_publish import SECRET_BUDGET, SECRET_NOTE, chosen, plant

ALL = [f for f in publish.PUBLISH_FIELDS["gantt_lines"] if f != "show"]
DEFAULT = set(store_module.GANTT_DEFAULT_HIDDEN)
OWNER = "A. Builder"
VALUES = {"owner": OWNER, "note": SECRET_NOTE, "budget": str(SECRET_BUDGET)}


def gantt(text):
    return chosen(plant(gantt_hidden_columns=text))["data"]["gantt"]


class HostileHiddenColumns(unittest.TestCase):
    def expect_hidden(self, text, hidden):
        """The copy has every column except `hidden` (and the eye), on the header and on every line; hidden values are in no byte of it."""
        g = gantt(text)
        want = [c for c in ALL if c not in hidden]
        self.assertEqual(g["columns"], want, repr(text))
        for ln in g["lines"]:
            self.assertEqual(list(ln), want, repr(text))
        blob = json.dumps(g)
        for col, val in VALUES.items():
            (self.assertNotIn if col in hidden else self.assertIn)(val, blob, (text, col))

    def test_empty_text_hides_nothing_and_shows_every_value(self):
        self.expect_hidden("", set())

    def test_whitespace_only_text_of_any_kind_hides_exactly_the_default(self):
        for ws in ("  ", "\n", "\r\n", "\t \t", " ", " ", " \n , \t "):
            self.expect_hidden(ws, DEFAULT)

    def test_comma_only_text_hides_exactly_the_default(self):
        for c in (",", ",,,,", ",\n,", "，"):               # the last is a full-width comma: one unknown name
            self.expect_hidden(c, DEFAULT)

    def test_an_unknown_or_hostile_name_anywhere_in_the_list_hides_exactly_the_default(self):
        for bad in ('["note"]', "NOTE", "owner,NOTE", "note,<script>", "owner,__proto__", "owner,note\x00", "'note'", "owner note",
                    "owner,Owner", "show;owner", "owner," + "x" * 5000, "note,​owner"):
            self.expect_hidden(bad, DEFAULT)

    def test_a_legacy_list_with_id_and_name_hides_only_what_is_hideable_in_it(self):
        self.expect_hidden("id,name,owner", {"owner"})          # id and name are tolerated, not hidden, and do not turn the list into the default
        self.assertEqual(gantt("name,id")["columns"], [c for c in ALL if c not in DEFAULT])

    def test_owner_alone_hides_only_owner_and_shows_note_and_budget(self):
        self.expect_hidden("owner", {"owner"})
        self.expect_hidden(" owner ", {"owner"})
        self.expect_hidden("\towner\n", {"owner"})
        self.expect_hidden("owner,owner", {"owner"})

    def test_owner_with_others_hides_both_and_the_rest_stay(self):
        self.expect_hidden("note,owner", {"note", "owner"})
        self.expect_hidden(" note , owner ", {"note", "owner"})
        self.expect_hidden("owner,,note,", {"note", "owner"})

    def test_owner_never_leaks_when_the_default_applies(self):
        for text in (None, 5, ["owner"], {}, " ", ",", "Owner", "OWNER", "owner,bogus"):
            g = gantt(text)
            self.assertNotIn("owner", g["columns"], repr(text))
            self.assertNotIn(OWNER, json.dumps(g), repr(text))
            self.assertTrue(all("owner" not in ln for ln in g["lines"]), repr(text))

    def test_the_default_set_is_pinned(self):
        self.assertEqual(DEFAULT, {"show", "note", "budget", "effort", "baseline_start", "baseline_end", "owner"})


if __name__ == "__main__":
    unittest.main()

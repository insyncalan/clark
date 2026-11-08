"""Row 986: the picker's rules in the page (src/clark/page/src/edit/itemEdit.js, bundled by the pinned esbuild), in headless Chrome.
Run: ~/bin/clark-chrome-slot env CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_assign_new_person_rules

Interface this row adds to itemEdit.js (stub for row 985, which owns the picker's search and recents):
  E.newPersonChange(row, person, today) -> {changes, new_person, words, back} | {error}
  E.CLEAR_ENTRY === "TBC (no one yet)"            (the picker's clear entry; AT words as ruled)
  E.clearChange(row)                              -> the owner change to the stored value "TBC" (no new_person)
Red until the build: none of these exist yet. The live picker (Add {typed} as a new person / Keep the name only / form / Enter
saves / Use this one, at 1400 and 900 px) is written once row 985 has landed, because it is that row's picker (see the test list).
"""
import contextlib
import json
import unittest

import _testpage  # noqa: F401
from _paths import SRC
from test_inline_edits import PAGE_SRC, need_chrome
from test_server import chrome
from test_work_items import TODAY, bundled, page_target


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)
        res = cls.cdp.call("Runtime.evaluate", {"expression": bundled(PAGE_SRC / "edit" / "itemEdit.js", "E") + "; true", "returnByValue": True}, cls.sid)
        assert "exceptionDetails" not in res, res

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        res = self.cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, self.sid)
        self.assertNotIn("exceptionDetails", res, (expr, res))
        return res["result"].get("value")

    def new(self, row, person):
        return self.js(f"E.newPersonChange({json.dumps(row)}, {json.dumps(person)}, {json.dumps(TODAY)})")

    ACTION = {"id": "ABC-A-001", "kind": "action", "owner": "Ada Quillfeather"}
    PENDING = {"id": "ABC-D-001", "kind": "decision", "owner": None}

    def test_a_new_person_sends_the_owner_and_new_person_in_one_change(self):
        """Mutation: send two requests, or the owner without new_person. Cleaned name; the email only when given."""
        got = self.new(self.ACTION, {"name": "  Zelda   Quince ", "email": " Zelda@Example.org "})
        self.assertEqual(got["changes"], {"owner": "Zelda Quince"})
        self.assertEqual(got["new_person"], {"name": "Zelda Quince", "email": "Zelda@Example.org"})
        self.assertIn("Zelda Quince", got["words"])
        self.assertEqual(got["back"], "Owner of ABC-A-001 is back to Ada Quillfeather.")
        self.assertEqual(self.new(self.ACTION, {"name": "Omar Reid"})["new_person"], {"name": "Omar Reid"})

    def test_a_decision_sends_made_by(self):
        """Mutation: send owner for a decision."""
        got = self.new(self.PENDING, {"name": "Omar Reid"})
        self.assertEqual(got["changes"], {"made_by": "Omar Reid"})
        self.assertEqual(got["back"], "Decider of ABC-D-001 is blank again.")

    def test_hostile_names_are_said_in_the_picker_and_send_nothing(self):
        """Same classes as the owner text: blank, TBC, over 120, hidden characters. Mutation: send and let clark refuse."""
        for name in ("", "   ", "TBC", "tbc", "x" * 121, "Zelda​Quince", "Zelda‮Quince", "Zelda\x07"):
            with self.subTest(name=ascii(name[:12])):
                got = self.new(self.ACTION, {"name": name})
                self.assertIn("error", got)
                self.assertNotIn("changes", got)

    def test_a_bad_email_is_said_and_sends_nothing(self):
        """Mutation: send it. The check is the people list's (one @, a dot after it)."""
        for email in ("nope", "a@b", "a@@b.co", "a b@c.co"):
            with self.subTest(email=email):
                self.assertIn("error", self.new(self.ACTION, {"name": "Zelda Quince", "email": email}))

    def test_the_same_name_as_the_current_owner_sends_nothing(self):
        """Mutation: add a duplicate of the owner already shown."""
        self.assertIsNone(self.new(self.ACTION, {"name": " ada  quillfeather"}))

    def test_the_clear_entry_reads_tbc_no_one_yet_and_sends_the_stored_tbc(self):
        """AT clear entry. Mutation: label 'Unassigned'/'TBC', or send the label's words, or send null (an owner is never blank)."""
        self.assertEqual(self.js("E.CLEAR_ENTRY"), "TBC (no one yet)")
        got = self.js(f"E.clearChange({json.dumps(self.ACTION)})")
        self.assertEqual(got["changes"], {"owner": "TBC"})
        self.assertNotIn("new_person", got)
        self.assertEqual(got["back"], "Owner of ABC-A-001 is back to Ada Quillfeather.")
        self.assertIsNone(self.js(f"E.clearChange({json.dumps({**self.ACTION, 'owner': 'TBC'})})"), "already TBC: nothing sent")


if __name__ == "__main__":
    unittest.main()

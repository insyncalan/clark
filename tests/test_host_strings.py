"""v1.1 item 625: every sentence the Windows host-side route adds is a named UNRULED constant in src/clark/host_strings.py (the ticket
gave no wording for them, so the owner has not ruled on them). host_folders.py keeps no sentence of its own.

Run: python3 dev/run_tests.py test_host_strings
"""
import re
import unittest

import _paths  # noqa: F401
from clark import host_folders as hf


class Strings(unittest.TestCase):
    def test_the_constants_are_named_unruled_in_one_file(self):
        from clark import host_strings as hs
        names = [n for n in dir(hs) if n.startswith("UNRULED_")]
        self.assertEqual(sorted(names), ["UNRULED_NOT_A_PATH", "UNRULED_NOT_SHARED", "UNRULED_NOT_SHARED_AT_ALL", "UNRULED_SAVED"])
        self.assertIs(hf.NOT_SHARED, hs.UNRULED_NOT_SHARED)
        self.assertIs(hf.NOT_A_PATH, hs.UNRULED_NOT_A_PATH)
        self.assertIs(hf.NOT_SHARED_AT_ALL, hs.UNRULED_NOT_SHARED_AT_ALL)
        self.assertIs(hf.SAVED, hs.UNRULED_SAVED)

    def test_host_folders_has_no_sentence_literal(self):
        import inspect
        src = inspect.getsource(hf)
        self.assertIsNone(re.search(r"Nothing was changed|Type the full path|Saved as", src))

    def test_the_words_are_plain_and_not_mac_only(self):
        from clark import host_strings as hs
        for n in dir(hs):
            if n.startswith("UNRULED_"):
                text = getattr(hs, n)
                self.assertFalse(text.lower().startswith("clark"), n)
                self.assertNotRegex(text, r"(?i)docker|container|mount|volume|compose|/shares|Finder|Library/|\.command|\bMac\b", n)


if __name__ == "__main__":
    unittest.main()

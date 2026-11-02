"""#410: Help says plainly when ask clark refuses a password, and what it says is what the rule does.

The rule (ask.looks_like_secret, with secret_screen behind it) refuses a named password whose value looks like one: letters mixed
with digits or symbols, or a word in quotes. A plain unquoted word is sent. Help used to read as if any password was refused, so
the words and the rule are pinned together here: change one and this fails until the other agrees.

Run: python3 dev/run_tests.py test_help_ask_secret_words
"""
import json
import unittest

from _paths import ROOT, SRC  # noqa: F401  (puts src/ on the path)

from clark import ask

HELP = ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json"
PROTO_HELP = ROOT / "system" / "prototype" / "help.js"
PLAIN = "password: abcdefghijkl"
MIXED = "password: abc123def456"


def ask_words():
    ref = json.loads(HELP.read_text(encoding="utf-8"))["reference"]["sections"]
    sec = next(s for s in ref if s["id"] == "ask-clark")
    return [b[1] for b in sec["b"] if b[0] == "p" and b[1].startswith("Passwords and keys")]


class TheWordsAgreeWithTheRule(unittest.TestCase):
    def test_help_says_when_a_password_is_refused_and_that_a_plain_word_is_not(self):
        got = ask_words()
        self.assertEqual(len(got), 1, "ask clark's Help entry has one Passwords and keys paragraph")
        text = got[0]
        for must in ("looks like a password or a key", "is not sent when its value looks like one", "letters mixed with digits or symbols", "A plain word", "is still sent"):
            self.assertIn(must, text)
        self.assertIn(f"“{MIXED}”", text)
        self.assertIn(f"“{PLAIN}”", text)

    def test_the_prototype_help_says_the_same(self):
        self.assertIn(ask_words()[0], PROTO_HELP.read_text(encoding="utf-8"))

    def test_the_two_examples_in_the_words_behave_as_they_say(self):
        self.assertFalse(ask.looks_like_secret(PLAIN), "a plain unquoted word is sent")
        self.assertFalse(ask._secret(PLAIN))
        self.assertTrue(ask.looks_like_secret(MIXED), "letters mixed with digits are refused")
        self.assertTrue(ask._secret(MIXED))

    def test_symbols_and_a_quoted_word_are_refused_as_the_words_say(self):
        self.assertTrue(ask._secret("password: abcdefgh!"))
        self.assertTrue(ask._secret('password: "abcdefghijkl"'))


if __name__ == "__main__":
    unittest.main()

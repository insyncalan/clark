"""#332: ask keeps its own older check (`ask.looks_like_secret`) beside the full screen (`secret_screen.looks_like_secret`), and
`ask._secret` refuses when either does. They are meant to be one screen, but the old one still refuses text the full one lets
through, so taking it out today would loosen ask. This file holds that line, so the day the full screen covers every case the
old check does, the old check can go and the gap list below is empty.

COVERED: refused by the old check and by the full screen. GAPS: refused by the old check only. The samples are built from pieces,
so no real-looking secret sits in this file. Fictional data only.

Run: python3 dev/run_tests.py test_ask_one_screen
"""
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import ask, secret_screen

COVERED = {
    "AWS key": "AK" + "IA" + "A" * 16,
    "GitHub token": "gh" + "p_" + "a" * 30,
    "Slack token": "xo" + "xb-" + "1" * 10,
    "address with a password": "see postgres://u:" + "abc" + "@host/db",
    "password is": "pass" + "word is hunter22",
    "password colon, short value": "pass" + "word: abc1",
    "password colon, digits": "pass" + "word: 12345",
    "private key": "-----BEGIN " + "OPENSSH PRIVATE KEY",
    "a long mixed run": "Ab1+/=" * 6,
}
GAPS = {
    "sk- key": "s" + "k-" + "abcdefgh12345678",
    "pk- key": "p" + "k-" + "abcdefgh12345678",
    "rk- key": "r" + "k-" + "abcdefgh12345678",
    "sk- key, letters only": "s" + "k-" + "A" * 20,
    "JWT with two parts": "ey" + "J" + "a" * 10 + "." + "b" * 10 + ".",
    "Bearer, no header": "Bear" + "er " + "a" * 20,
    "bearer, mixed": "bear" + "er " + "Ab1" * 7,
    "token colon, 4 characters": "tok" + "en: ab12",
    "secret equals, punctuation": "sec" + "ret = a_b-c",
    "api key is": "api " + "key is x9y8z7",
    "api_key equals, 4 characters": "api_" + "key=ab12",
    "token is, digits": "tok" + "en is 12345678",
    "access-key colon": "access-" + "key: k9k9k9",
    "a long mixed run of letters and digits": "A" * 10 + "b" * 10 + "1" * 12,
    "private key, other kind": "-----BEGIN " + "CERTIFICATE PRIVATE KEY",
}


class OneScreen(unittest.TestCase):
    def test_every_sample_is_refused_by_the_old_check(self):
        for name, text in {**COVERED, **GAPS}.items():
            with self.subTest(name):
                self.assertTrue(ask.looks_like_secret(text))

    def test_ask_refuses_every_sample_through_its_one_entry_point(self):
        for name, text in {**COVERED, **GAPS}.items():
            with self.subTest(name):
                self.assertTrue(ask._secret(text))

    def test_the_full_screen_refuses_the_covered_samples(self):
        for name, text in COVERED.items():
            with self.subTest(name):
                self.assertTrue(secret_screen.looks_like_secret(text))

    def test_the_gap_list_is_exactly_what_the_full_screen_lets_through(self):
        """When this fails the full screen has learned a case: move it to COVERED. When GAPS is empty, drop the old check."""
        for name, text in GAPS.items():
            with self.subTest(name):
                self.assertFalse(secret_screen.looks_like_secret(text), "the full screen now refuses it: move it to COVERED")


if __name__ == "__main__":
    unittest.main()

"""#311: the ask path uses the one shared secret screen. One sample of EVERY kind the shared tests hold (the 15 plain kinds and
the 23 attack cases, 38 in all) is handed to ask's own `_secret()`, and each must be refused. A second test shows the shared screen
is doing real work: with it switched off, ask's own narrower check lets some kinds through, so the first test would fail if `_secret`
stopped using it. The samples are the ones tests/test_ai_key_refusal.py builds from pieces; none is written whole here.

Run: python3 dev/run_tests.py test_ask_every_kind
"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from test_ai_key_refusal import ATTACKS, REFUSED
from clark import ask, secret_screen

KINDS = {**{"a " + k: v for k, v in REFUSED.items()}, **{"b " + k: v for k, v in ATTACKS.items()}}


class EveryKindIsRefusedByAsk(unittest.TestCase):
    def test_there_are_38_kinds(self):
        self.assertEqual(len(KINDS), 38)

    def test_each_kind_is_refused_by_the_ask_screen(self):
        for name, sample in KINDS.items():
            with self.subTest(name):
                self.assertTrue(ask._secret("Use this: " + sample))

    def test_the_shared_screen_adds_to_the_ask_check(self):
        with mock.patch.object(secret_screen, "looks_like_secret", return_value=False):
            missed = [n for n, s in KINDS.items() if not ask._secret("Use this: " + s)]
        self.assertTrue(missed, "ask's own check alone already refuses every kind, so the shared screen would add nothing")
        for name in missed:
            with self.subTest(name):
                self.assertTrue(secret_screen.looks_like_secret("Use this: " + KINDS[name]))

    def test_an_ordinary_question_passes(self):
        self.assertFalse(ask._secret("What is the state of the plan?"))


if __name__ == "__main__":
    unittest.main()

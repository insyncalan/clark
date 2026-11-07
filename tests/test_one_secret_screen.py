"""Row 469: the suggestions input screen is the one ask clark uses. Both screens' shapes are refused on both paths: the library
path (ai_menu.check_request, and its Ask... line) and the real /api/ai/suggest route. A shape that only ask clark's own screen
caught (a short JWT, a lower-case bearer line) used to pass the suggestions path. Samples are built from pieces; fictional data."""
import unittest

import _paths  # noqa: F401
import test_ai_route as route
from clark import ai_menu, ask, secret_screen

SHAPES = {
    "sk key": "my key is " + "sk" + "-" + "abcdefghijklmnop1234567890",
    "bearer, upper case": "Authorization: " + "Bear" + "er " + "abcdefghijklmnopqrstuvwxyz123456",
    "bearer, lower case": "use " + "bear" + "er " + "abcdefghijklmnopqrstuvwx",
    "short JWT": "ey" + "JhbGciOiJIUzI1NiJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0." + "abc",
    "long JWT": "ey" + "JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." + "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ." + "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
    "api_key =": "api" + "_key" + " = " + "abc123def",
    "live key with underscores": "sk" + "_live_" + "abcdefghijklmnop12",
}


class OneScreen(unittest.TestCase):
    def test_each_shape_is_refused_by_the_union_screen(self):
        for name, text in SHAPES.items():
            with self.subTest(name):
                self.assertTrue(ai_menu.looks_like_secret(text))

    def test_the_union_is_never_weaker_than_either_screen(self):
        for name, text in SHAPES.items():
            with self.subTest(name):
                if ask.looks_like_secret(text) or secret_screen.looks_like_secret(text):
                    self.assertTrue(ai_menu.looks_like_secret(text))

    def test_each_shape_is_refused_in_the_text_and_in_the_ask_line(self):
        for name, text in SHAPES.items():
            with self.subTest(name):
                with self.assertRaises(ai_menu.Refused):
                    ai_menu.check_request("rewrite", text, "plain")
                with self.assertRaises(ai_menu.Refused):
                    ai_menu.check_request("custom", "The supplier confirmed Friday.", "plain", text)

    def test_ordinary_words_pass(self):
        self.assertFalse(ai_menu.looks_like_secret("The supplier confirmed the delivery for Friday."))
        self.assertFalse(ai_menu.looks_like_secret("token: 2026 plan"))


class OneScreenOnTheRoute(route.Base):
    def test_each_shape_is_refused_by_the_route_and_nothing_is_sent(self):
        for name, text in SHAPES.items():
            for field in ("text", "instruction"):
                with self.subTest(name + " in " + field):
                    more = {"text": text} if field == "text" else {"option": "custom", "instruction": text}
                    status, got = self.suggest(**more)
                    self.assertEqual((status, got["code"]), (400, "secret"))
        self.assertEqual(self.provider.requests, [])


if __name__ == "__main__":
    unittest.main()

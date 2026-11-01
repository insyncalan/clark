"""#72 slice 5: a key or password in Ask…'s line, or in the selected text, is refused before anything is sent.

The sample keys are built from pieces so no real-looking key sits in the file."""
import io
import logging
import unittest
from contextlib import redirect_stderr, redirect_stdout

from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import ai_menu as am
from clark.edit_ai import Refused
from test_ai_menu import FakeProvider

BODY = "a1B2c3D4e5F6g7H8i9J0"
# name: (the whole sample, the part that is the secret itself)
REFUSED = {
    "anthropic": "sk-" + "ant-api03-" + BODY + "-xyz",
    "openai": "sk-" + BODY + "K1L2M3N4O5P6Q7",
    "openai project": "sk-" + "proj-" + BODY + "_K1L2",
    "github classic": "gh" + "p_" + BODY + "K1L2",
    "github oauth": "gh" + "o_" + BODY + "K1L2",
    "github server": "gh" + "s_" + BODY + "K1L2",
    "github fine grained": "github" + "_pat_" + BODY + "_K1L2",
    "aws": "AK" + "IA" + "ABCDEFGH12345678",
    "slack": "xo" + "xb-" + "1234567890-abcdefghij",
    "private key": "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIBVwIBADANBgkqhkiG\n-----END RSA PRIVATE KEY-----",
    "private key plain": "-----BEGIN " + "PRIVATE KEY-----\nMIIBVwIBADANBgkqhkiG",
    "password colon": "password: " + "hunter22",
    "password quoted": 'Password = "' + 'swordfish1"',
    "passwd equals": "passwd=" + "s3cret!x",
    "api key": "api_key=" + "zzzz-9999-qqqq-wwww",
}
# what must never come back out, per sample: the secret part (a label such as "password" may)
SECRET_PART = {"private key": "MIIBVwIBADANBgkqhkiG", "private key plain": "MIIBVwIBADANBgkqhkiG", "password colon": "hunter22",
               "password quoted": "swordfish1", "passwd equals": "s3cret!x", "api key": "zzzz-9999-qqqq-wwww"}
ALLOWED = [
    "What is the key risk for the Friday delivery?",
    "The sky is blue and the task list is short.",
    "Ask-ant-sized teams need a plan: sk is two letters.",
    "Use the risk-based approach to the desk-based review.",
    "Reset your password: ask the service desk.",
    "The password policy is on the intranet.",
    "Keep the secret key to success in view: plan early.",
    "The task-force skipped sk-1 and sk-ant-1 in the numbering.",
    "We keep the key for the cupboard with the facilities team.",
    "Send the AKIA team a note about Friday.",
    "Move the ghp_ label to the next card.",
    "api key: needed",
    "He said BEGIN PRIVATE and nothing else.",
]
# #72 review: the attack cases a weaker rule let through; the one hardened screen refuses all of them (built from pieces)
PW = "Welcome" + "2026!"
ATTACKS = {
    "json password": '{"pass' + 'word": "' + PW + '"}',
    "json api key": '{"api_' + 'key": "a1b2c3d4e5f6"}',
    "table cell": "| pass" + "word | " + PW + " |",
    "table header column": "user | pass" + "word\nmail | " + PW,
    "csv column": "user,pass" + "word\nmail," + PW,
    "wifi prose": "the wifi pass" + "word is " + PW,
    "pw colon": "p" + "w: " + PW,
    "token equals": "tok" + "en=" + "a1b2c3d4e5f6a7b8c9",
    "secret colon": "sec" + "ret: " + "a1b2c3d4e5f6a7b8",
    "jwt": "ey" + "J" + "a" * 12 + ".ey" + "J" + "b" * 12 + "." + "c" * 12,
    "stripe live": "sk_" + "live_" + "A1b2C3d4E5f6G7h8",
    "google key": "AI" + "za" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",
    "password in a web address": "postgres://admin:" + PW + "@db.example.org/main",
    "bearer header": "Authorization: " + "Bear" + "er " + "abcDEF123456" * 3,
    "full-width key": "\uff53\uff4b-\uff41\uff4e\uff54-" + "a1B2c3D4e5F6",
    "cyrillic a in the word": "p\u0430ss" + "word: " + PW,
    "key split by a line break": "sk-" + "ant-api03-" + BODY[:10] + "\n" + BODY[10:] + "-xyz",
    "private key block": "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIBVwIBADANBgkqhkiG",
    "aws key": "id AK" + "IA" + "IOSFODNN7EXAMPLE here",
    "github token": "use gh" + "p_" + "A1b2C3d4" * 5,
    "env line": "DB_PASS" + "WORD=" + PW,
    "pass key": "pa" + "ss=" + PW,
    "quoted passphrase": "pass" + 'word: "' + "correct horse 7 battery" + '"',
}
# a key split inside its prefix by a line break (squeezing would turn the break into a space and hide it)
SPLIT_PREFIX = "sk-an\n" + "t-" + BODY + "K1L2"
TEXT = "The supplier confirmed the delivery for Friday."


def captured(fn):
    """Run `fn`; return everything logged at any level and everything printed."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    root = logging.getLogger()
    old = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    out, err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            fn()
    finally:
        root.removeHandler(handler)
        root.setLevel(old)
    return stream.getvalue() + out.getvalue() + err.getvalue()


class KeysInTheInstruction(unittest.TestCase):
    def test_each_kind_is_refused(self):
        for name, key in REFUSED.items():
            with self.subTest(name):
                with self.assertRaises(Refused) as cm:
                    am.check_request("custom", TEXT, "plain", "Use this: " + key + " please")
                self.assertEqual(str(cm.exception), am.SECRET_MESSAGE)

    def test_ordinary_lines_pass(self):
        for line in ALLOWED:
            with self.subTest(line):
                self.assertEqual(am.check_request("custom", TEXT, "plain", line)[3], line)


class TheAttackCases(unittest.TestCase):
    def test_there_are_23(self):
        self.assertEqual(len(ATTACKS), 23)

    def test_each_is_refused_in_ask_and_in_the_selection_and_never_sent(self):
        for name, key in ATTACKS.items():
            with self.subTest(name):
                with self.assertRaises(Refused) as cm:
                    am.check_request("custom", TEXT, "plain", "Use this: " + key)
                self.assertEqual(str(cm.exception), am.SECRET_MESSAGE)
                with self.assertRaises(Refused) as cm:
                    am.check_request("rewrite", "Notes:\n" + key + "\nend", "plain")
                self.assertEqual(str(cm.exception), am.SECRET_MESSAGE)
                prov = FakeProvider()
                r = am.suggest(prov, "custom", TEXT, "plain", "Use this: " + key)
                self.assertEqual((r["ok"], r["message"]), (False, am.SECRET_MESSAGE))
                card = am.AiSession().begin("custom", TEXT, "plain", 0, 5, instruction="Use this: " + key)
                self.assertEqual((card.status, card.message, card.label), ("failed", am.SECRET_MESSAGE, ""))
                card = am.AiSession().begin("rewrite", "Notes:\n" + key, "plain", 0, 5)
                self.assertEqual((card.status, card.message), ("failed", am.SECRET_MESSAGE))
                r = am.suggest(prov, "rewrite", "Notes:\n" + key, "plain")
                self.assertEqual((r["ok"], r["message"]), (False, am.SECRET_MESSAGE))
                self.assertEqual(prov.calls, [])

    def test_the_split_prefix_case_in_both(self):
        with self.assertRaises(Refused):
            am.check_request("custom", TEXT, "plain", SPLIT_PREFIX)
        with self.assertRaises(Refused):
            am.check_request("rewrite", SPLIT_PREFIX, "plain")
        prov = FakeProvider()
        self.assertFalse(am.suggest(prov, "custom", TEXT, "plain", SPLIT_PREFIX)["ok"])
        self.assertFalse(am.suggest(prov, "rewrite", SPLIT_PREFIX, "plain")["ok"])
        self.assertEqual(prov.calls, [])
        card = am.AiSession().begin("custom", TEXT, "plain", 0, 5, instruction=SPLIT_PREFIX)
        self.assertEqual((card.status, card.label), ("failed", ""))
        self.assertNotIn("api03", card.label + card.message)

    def test_one_rule_not_two(self):
        self.assertFalse(hasattr(am, "SECRET"))


class KeysInTheSelection(unittest.TestCase):
    def test_each_kind_is_refused_for_every_kind_of_option(self):
        for name, key in REFUSED.items():
            for option in ("rewrite", "custom"):
                with self.subTest(name + " " + option):
                    with self.assertRaises(Refused) as cm:
                        am.check_request(option, "Notes: " + key + " end", "plain", "Make it kinder")
                    self.assertEqual(str(cm.exception), am.SECRET_MESSAGE)

    def test_ordinary_text_passes(self):
        for text in ALLOWED:
            with self.subTest(text):
                self.assertEqual(am.check_request("rewrite", text, "plain")[1], text)

    def test_a_label_on_its_own_line_is_caught(self):
        with self.assertRaises(Refused):
            am.check_request("rewrite", "Login\npassword: " + "hunter22\nthanks", "plain")


class NothingIsSent(unittest.TestCase):
    def test_the_provider_is_never_asked(self):
        for name, key in REFUSED.items():
            with self.subTest(name):
                prov = FakeProvider()
                r = am.suggest(prov, "custom", TEXT, "plain", "Add " + key)
                self.assertEqual((r["ok"], r["message"]), (False, am.SECRET_MESSAGE))
                r = am.suggest(prov, "rewrite", "Note " + key, "plain")
                self.assertEqual((r["ok"], r["message"]), (False, am.SECRET_MESSAGE))
                self.assertEqual(prov.calls, [])

    def test_a_normal_request_still_reaches_the_provider(self):
        prov = FakeProvider()
        self.assertTrue(am.suggest(prov, "custom", TEXT, "plain", "Say it kindly")["ok"])
        self.assertEqual(len(prov.calls), 1)

    def test_the_card_fails_with_the_one_line_and_runs_nothing(self):
        key = REFUSED["anthropic"]
        card = am.AiSession().begin("custom", TEXT, "plain", 0, 10, instruction=key)
        self.assertEqual((card.status, card.message), ("failed", am.SECRET_MESSAGE))
        card = am.AiSession().begin("rewrite", "Note " + key, "plain", 0, 10)
        self.assertEqual((card.status, card.message), ("failed", am.SECRET_MESSAGE))


class NoPartOfTheKeyIsEchoed(unittest.TestCase):
    def test_the_line_the_error_the_log_and_the_card_heading_hold_none_of_it(self):
        for name, key in REFUSED.items():
            secret = SECRET_PART.get(name, key)
            for where in ("instruction", "text"):
                with self.subTest(name + " " + where):
                    seen = {}
                    option, text, line = ("custom", TEXT, "x " + key) if where == "instruction" else ("rewrite", "x " + key, "")

                    def run():
                        seen["result"] = am.suggest(FakeProvider(), option, text, "plain", line)
                        seen["card"] = am.AiSession().begin(option, text, "plain", 0, 5, instruction=line)
                        try:
                            am.check_request(option, text, "plain", line)
                        except Refused as e:
                            seen["error"] = e

                    log = captured(run)
                    shown = [seen["result"]["message"], seen["card"].message, seen["card"].label, str(seen["error"]),
                             repr(seen["error"].args), repr(seen["error"]), log]
                    for piece in shown:
                        self.assertNotIn(secret, piece)
                        self.assertNotIn(secret[:10], piece)


if __name__ == "__main__":
    unittest.main()

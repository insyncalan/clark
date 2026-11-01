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
    "openai": "sk-" + BODY + "K1L2",
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
    "password quoted": 'Password = "' + 'swordfish"',
    "passwd equals": "passwd=" + "s3cret!x",
    "api key": "api_key=" + "zzzz-9999-qqqq",
    "api key spaced": "API key: " + "abcd1234efgh",
}
# what must never come back out, per sample: the secret part (a label such as "password" may)
SECRET_PART = {"private key": "MIIBVwIBADANBgkqhkiG", "private key plain": "MIIBVwIBADANBgkqhkiG", "password colon": "hunter22",
               "password quoted": "swordfish", "passwd equals": "s3cret!x", "api key": "zzzz-9999-qqqq", "api key spaced": "abcd1234efgh"}
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

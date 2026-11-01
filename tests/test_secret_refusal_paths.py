"""#253: the v0.3 release line "A key or a password typed into a question, or inside the text you selected, is refused before
anything is sent", proved in code instead of by a hand check.

The question path is driven through the REAL server and the REAL /api/ask route (a real store, a real HTTP request) with a fake
provider that records every call. The selected-text path has no server route on main (see SelectionHasNoRoute), so it is driven
through the real library the panel's logic mirrors, ai_menu (one-shot `suggest` and the card's `AiSession.begin`), with the same
kind of fake provider. The sample secrets are built from pieces (and are the ones tests/test_ai_key_refusal.py already uses), so
no real-looking secret sits in this file. Fictional data only.

Run: python3 dev/run_tests.py test_secret_refusal_paths
"""
import inspect
import logging
import re
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401  (puts src/ on the path)

import test_ask_route as route_base
from test_ai_key_refusal import ATTACKS, REFUSED, SECRET_PART, TEXT
from test_ai_menu import FakeProvider
from clark import ai_menu as am, ask, server as sv

CLEAN_Q = "What is the state of the plan?"
CLEAN_SELECTION = "The supplier confirmed the delivery for Friday."
SAMPLES = {**{"a " + k: v for k, v in REFUSED.items()}, **{"b " + k: v for k, v in ATTACKS.items()}}
# FINDING (#253): the question path screens with ask.looks_like_secret (ask.py:96), a narrower list than secret_screen (which the
# selection path uses). These kinds are NOT refused in a question today and so reach the provider; they are kept out of the "is
# refused" tests and listed in the expected-failure test below, which turns into an unexpected success when the gap is closed.
QUESTION_GAPS = {"github classic", "github oauth", "github server", "json password", "json api key", "table cell",
                 "table header column", "csv column", "pw colon", "stripe live", "env line", "pass key", "quoted passphrase"}


def secret_part(name, sample):
    return SECRET_PART.get(name[2:], sample)


class LogCapture(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class QuestionRoute(route_base.Base):
    """POST /api/ask: ask_service.AskService.ask calls ask.build_request (which screens the question and the earlier turns) at
    ask_service.py:162, and only then ask.ask_provider (ask_service.py:168), the one place a provider is called."""

    def setUp(self):
        super().setUp()
        self.log = LogCapture()
        root = logging.getLogger()
        self._level = root.level
        root.addHandler(self.log)
        root.setLevel(logging.DEBUG)
        self.addCleanup(self._unhook)

    def _unhook(self):
        root = logging.getLogger()
        root.removeHandler(self.log)
        root.setLevel(self._level)

    def refused(self, name, sample, **more):
        n = len(self.provider.sent)
        status, got = self.question(**more)
        self.assertEqual(status, 400, (name, got))
        self.assertEqual((got["ok"], got["code"]), (False, "refused"), name)
        self.assertIn(got["message"], (ask.SECRET, ask.SECRET_EARLIER), name)
        self.assertEqual(len(self.provider.sent), n, f"{name}: the provider was called")
        wire = repr(got) + "\n".join(self.log.lines)
        for part in {secret_part(name, sample), sample}:
            self.assertNotIn(part, wire, f"{name}: the secret came back or was logged")
        return got

    def test_each_kind_in_the_question_is_refused_and_nothing_is_sent(self):
        for name, sample in SAMPLES.items():
            if name[2:] in QUESTION_GAPS:
                continue
            with self.subTest(name):
                self.refused(name, sample, q="Please use this: " + sample + " to check the plan")
        self.assertEqual(self.provider.sent, [])

    def test_each_kind_in_an_earlier_turn_is_refused_and_nothing_is_sent(self):
        for name, sample in SAMPLES.items():
            if name[2:] in QUESTION_GAPS:
                continue
            with self.subTest(name):
                earlier = [{"role": "user", "text": "Note: " + sample}, {"role": "assistant", "text": "Noted."}]
                self.refused(name, sample, earlier=earlier)
        self.assertEqual(self.provider.sent, [])

    @unittest.expectedFailure
    def test_FINDING_the_kinds_the_selection_screen_refuses_are_also_refused_in_a_question(self):
        for name, sample in SAMPLES.items():
            if name[2:] in QUESTION_GAPS:
                with self.subTest(name):
                    self.refused(name, sample, q="Please use this: " + sample + " to check the plan")

    def test_the_refusal_is_the_plain_words(self):
        got = self.refused("anthropic", REFUSED["anthropic"], q="key " + REFUSED["anthropic"])
        self.assertEqual(got["message"], ask.SECRET)

    def test_a_clean_question_still_reaches_the_provider_once(self):
        status, got = self.question(CLEAN_Q)
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(len(self.provider.sent), 1)

    def test_a_clean_question_after_a_refusal_still_reaches_the_provider(self):
        self.refused("anthropic", REFUSED["anthropic"], q="key " + REFUSED["anthropic"])
        self.assertEqual(self.question(CLEAN_Q)[0], 200)
        self.assertEqual(len(self.provider.sent), 1)


class SelectedText(unittest.TestCase):
    """The selection and the Ask… line: ai_menu.check_request screens both before build_prompt (ai_menu.py:244), so the provider
    (ai_menu.py:755) is never reached. Driven through suggest (one-shot) and AiSession.begin (the card)."""

    def test_each_kind_in_the_selection_is_refused_and_nothing_is_sent(self):
        for name, sample in SAMPLES.items():
            with self.subTest(name):
                prov = FakeProvider()
                r = am.suggest(prov, "rewrite", "Notes: " + sample + " end", "plain")
                self.assertEqual((r["ok"], r["message"]), (False, am.SECRET_MESSAGE))
                card = am.AiSession().begin("rewrite", "Notes: " + sample, "plain", 0, 5)
                self.assertEqual((card.status, card.message), ("failed", am.SECRET_MESSAGE))
                self.assertEqual(prov.calls, [])
                for part in {secret_part(name, sample), sample}:
                    self.assertNotIn(part, repr(r) + card.message + card.label)

    def test_each_kind_in_the_ask_line_is_refused_and_nothing_is_sent(self):
        for name, sample in SAMPLES.items():
            with self.subTest(name):
                prov = FakeProvider()
                r = am.suggest(prov, "custom", CLEAN_SELECTION, "plain", "Use this: " + sample)
                self.assertEqual((r["ok"], r["message"]), (False, am.SECRET_MESSAGE))
                self.assertEqual(prov.calls, [])

    def test_a_clean_selection_still_reaches_the_provider_once(self):
        prov = FakeProvider()
        self.assertTrue(am.suggest(prov, "rewrite", CLEAN_SELECTION, "plain")["ok"])
        self.assertEqual(len(prov.calls), 1)


class EveryRouteThatSendsText(unittest.TestCase):
    """The inventory, so a new caller cannot appear unscreened: the only call sites of a provider's `ask` in src/clark."""

    def test_the_only_provider_call_sites_are_the_two_screened_ones(self):
        found = {}
        for path in sorted(Path(SRC, "clark").glob("*.py")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\bprovider\.ask\(", line) and not line.lstrip().startswith(("#", "def ", '"""')):
                    found[path.name] = found.get(path.name, 0) + 1
        self.assertEqual(found, {"ai_menu.py": 1, "ask.py": 1})

    def test_ask_provider_is_reached_only_after_build_request(self):
        src = inspect.getsource(route_base.ask_service.AskService.ask)
        self.assertLess(src.index("ask.build_request("), src.index("ask.ask_provider("))

    def test_ai_menu_suggest_screens_before_the_provider(self):
        src = inspect.getsource(am.suggest)
        self.assertLess(src.index("build_prompt("), src.index("provider.ask("))
        self.assertIn("check_request(", inspect.getsource(am.build_prompt))

    def test_the_server_has_no_route_for_the_selection(self):
        routes = set(sv.GET_ROUTES) | set(sv.POST_ROUTES)
        self.assertEqual({r for r in routes if "suggest" in r or "edit" in r or r.startswith("/api/ai")}, set())


if __name__ == "__main__":
    unittest.main()

"""#277: a hidden marker in every suggestion's prompt. A reply that holds it, or 8 or more characters of it in a row, is dropped and
logged (the option, the place and the length only). The marker is never in a log, a card or a result.

Run: python3 dev/run_tests.py test_ai_canary
Fictional data only.
"""
import logging
import re
import unittest

from _paths import SRC  # noqa: F401  (puts src/ on the path)
from clark import ai_menu as am

TEXT = "Chase the supplier by the end of the week."
GOOD = "<<<SUGGESTION\nPlease chase the supplier before the week ends.\nSUGGESTION>>>"


def marker_in(prompt):
    return re.search(r"Hidden marker, for the system only: ([0-9a-f]+)\.", prompt).group(1)


class Recorder(am.Provider):
    """Records the prompt; answers with a reply made from it (or a fixed one)."""
    name = "TestAI"

    def __init__(self, make=None):
        self.make, self.prompts = make, []

    def status(self):
        return "ready"

    def ask(self, prompt, tools=()):
        self.prompts.append(prompt)
        return self.make(prompt) if self.make else GOOD


class Events(logging.Handler):
    """Collects what the clark.ai logger says."""

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


class Base(unittest.TestCase):
    def setUp(self):
        self.events = Events()
        self.logger = logging.getLogger("clark.ai")
        self.logger.addHandler(self.events)
        self.old_level = self.logger.level
        self.logger.setLevel(logging.DEBUG)
        self.addCleanup(self.logger.removeHandler, self.events)
        self.addCleanup(self.logger.setLevel, self.old_level)

    @property
    def logged(self):
        return "\n".join(self.events.lines)


class Marker(Base):
    def test_it_is_16_hex_characters_and_fresh_each_time(self):
        seen = {am.build_prompt("rewrite", TEXT, "plain")["marker"] for _ in range(20)}
        self.assertEqual(len(seen), 20)
        for m in seen:
            self.assertRegex(m, r"^[0-9a-f]{16}$")

    def test_it_is_in_the_prompt_outside_the_text(self):
        req = am.build_prompt("rewrite", TEXT, "plain")
        self.assertEqual(marker_in(req["prompt"]), req["marker"])
        self.assertLess(req["prompt"].index(req["marker"]), req["prompt"].index(TEXT))


class Dropped(Base):
    def test_a_provider_that_echoes_the_prompt_is_dropped_and_logged(self):
        res = am.suggest(Recorder(lambda prompt: prompt), "rewrite", TEXT, "plain")
        self.assertFalse(res["ok"])
        self.assertEqual(res["text"], "")
        self.assertEqual(len(self.events.lines), 1)
        self.assertIn("option rewrite", self.logged)
        self.assertIn("place plain", self.logged)
        self.assertRegex(self.logged, r"length \d+")

    def test_the_marker_is_not_in_the_log_or_the_result(self):
        seen = {}

        def make(prompt):
            seen["m"] = marker_in(prompt)
            return "<<<SUGGESTION\nSee " + seen["m"] + "\nSUGGESTION>>>"
        res = am.suggest(Recorder(make), "rewrite", TEXT, "plain")
        self.assertEqual(len(self.events.lines), 1)
        self.assertNotIn(seen["m"], self.logged)
        self.assertNotIn(seen["m"], repr(res))
        self.assertNotIn("See", self.logged)           # the reply text is not logged either
        self.assertNotIn("See", repr(res))

    def test_a_part_of_eight_or_more_characters_is_dropped(self):
        for start in (0, 4, 8):
            with self.subTest(start=start):
                res = am.suggest(Recorder(lambda prompt: GOOD.replace("Please", marker_in(prompt)[start:start + 8])),
                                 "rewrite", TEXT, "plain")
                self.assertFalse(res["ok"])

    def test_case_and_hidden_characters_do_not_hide_it(self):
        res = am.suggest(Recorder(lambda prompt: GOOD.replace("Please", marker_in(prompt)[:10].upper())), "rewrite", TEXT, "plain")
        self.assertFalse(res["ok"])
        res = am.suggest(Recorder(lambda prompt: GOOD.replace("Please", "​".join(marker_in(prompt)[:9]))), "rewrite", TEXT,
                         "plain")
        self.assertFalse(res["ok"])

    def test_hidden_characters_are_taken_out_before_looking(self):
        marker = "0123456789abcdef"
        self.assertTrue(am.leaked("x" + "\u200b".join(marker[:9]) + "y", marker))
        self.assertTrue(am.leaked("x" + marker[:5] + "\u202e \n" + marker[5:9] + "y", marker))

    def test_seven_characters_is_not_a_leak(self):
        marker = "0123456789abcdef"
        self.assertTrue(am.leaked("x" + marker[:8] + "y", marker))
        self.assertFalse(am.leaked("x" + marker[:7] + "y", marker))

    def test_the_card_path_drops_it_too(self):
        session = am.AiSession()
        card = session.begin("rewrite", TEXT, "plain", 0, len(TEXT))
        req = session.request(card)
        self.assertNotIn("marker", req)
        session.deliver(card, req["prompt"])
        self.assertEqual(card.status, "failed")
        self.assertEqual(card.text, "")
        self.assertEqual(len(self.events.lines), 1)
        self.assertNotIn(card.marker, self.logged)
        self.assertNotIn(card.marker, card.message)


class NormalReplies(Base):
    def test_a_normal_reply_passes_and_nothing_is_logged(self):
        prov = Recorder()
        res = am.suggest(prov, "rewrite", TEXT, "plain")
        self.assertTrue(res["ok"])
        self.assertNotIn(marker_in(prov.prompts[0]), repr(res))
        self.assertEqual(self.events.lines, [])

    def test_a_card_with_a_normal_reply_is_ready(self):
        session = am.AiSession()
        card = session.begin("rewrite", TEXT, "plain", 0, len(TEXT))
        session.request(card)
        session.deliver(card, GOOD)
        self.assertEqual(card.status, "ready")
        self.assertEqual(self.events.lines, [])


if __name__ == "__main__":
    unittest.main()

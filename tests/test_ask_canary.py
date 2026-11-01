"""#277: a canary in the AI system prompt. A random private marker for each request goes into the system prompt; a reply that holds
it (even split into chunks, in other capitals or with hidden characters between) is dropped whole, and the log gets a fixed line
with neither the reply nor the marker. A stub provider only; nothing here calls a model.

Run: python3 dev/run_tests.py test_ask_canary
"""
import logging
import unittest

from _paths import SRC  # noqa: F401

import test_ask_route as tr
from clark import ask, ask_claude as ac

ZW = "​"


class Leaky(ask.StubProvider):
    """Answers with `make(canary)`; keeps the canary of each request it was given."""
    provider = "leaky"

    def __init__(self, make):
        super().__init__(reply="")
        self.make, self.canaries = make, []

    def ask(self, request):
        self.canaries.append(request.canary)
        return self.make(request.canary)


class Records(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


def request():
    return ask.build_request("How is the plan?", [ask.Passage("report: actions", "ABC-A-001 Send the plan | owner: Sam Lee")])


class Canary(tr.Base):
    def setUp(self):
        super().setUp()
        self.log = Records()
        logging.getLogger("clark").addHandler(self.log)
        logging.getLogger("clark").setLevel(logging.DEBUG)
        self.addCleanup(logging.getLogger("clark").removeHandler, self.log)

    def use(self, make):
        self.provider = Leaky(make)
        self.service.provider = self.provider

    def test_the_canary_is_random_for_each_request(self):
        p = Leaky(lambda c: "Fine.\nCITE: P1")
        ask.ask_provider(p, request())
        ask.ask_provider(p, request())
        self.assertEqual(len(p.canaries), 2)
        self.assertNotEqual(p.canaries[0], p.canaries[1])
        self.assertGreaterEqual(len(p.canaries[0]), 20)
        self.assertEqual(request().canary, "", "the request itself never holds one")

    def test_the_canary_is_in_the_system_prompt_and_only_there(self):
        c = "abcDEF123_-xyz"
        prompt = ask.system_prompt(c)
        self.assertTrue(prompt.startswith(ask.RULES))
        self.assertIn(c, prompt)
        self.assertIn("never part of any answer", prompt)
        self.assertEqual(ask.system_prompt(), ask.RULES)
        self.assertEqual(ac.arguments("/x/claude", c)[-1], prompt)
        self.assertEqual(ac.arguments("/x/claude")[-1], ask.RULES)
        self.assertNotIn(c, request().text, "the request text on standard input never holds it")

    def test_a_reply_with_the_canary_is_dropped_and_logged_without_the_text(self):
        self.use(lambda c: "SECRETWORDS the marker is " + c + "\nCITE: P1")
        status, body = self.question()
        self.assertEqual(status, 200)
        self.assertEqual((body["ok"], body["code"], body["message"]), (False, "no_answer", ask.HELD_BACK))
        self.assertNotIn("answer", body)
        canary = self.provider.canaries[0]
        self.assertNotIn(canary, str(body))
        self.assertTrue(any("private marker" in line for line in self.log.lines), self.log.lines)
        for line in self.log.lines:
            self.assertNotIn(canary, line)
            self.assertNotIn("SECRETWORDS", line)

    def test_a_reply_without_it_passes_unchanged(self):
        self.use(lambda c: "The plan is on track.\nCITE: P1")
        status, body = self.question()
        self.assertTrue(body["ok"])
        self.assertEqual(body["answer"], "The plan is on track.")
        self.assertFalse(any("private marker" in line for line in self.log.lines))

    def test_a_reply_that_spells_it_in_chunks_or_with_hidden_characters_is_caught(self):
        c = "Ab3_dEf-9XyZ12345678"
        chunks = [c[:4], " ", c[4:9], ZW, c[9:15].swapcase(), "\n", c[15:]]
        self.assertTrue(ask.leaks("".join(chunks), c))
        self.assertTrue(ask.leaks("x " + " ".join(c) + " y", c))
        self.assertFalse(ask.leaks("A different marker entirely", c))
        self.assertFalse(ask.leaks("anything", ""))
        got = ask.ask_provider(Leaky(lambda canary: "".join(canary[i:i + 3] + ZW for i in range(0, len(canary), 3))), request())
        self.assertEqual(got, ask.Failure(ask.HELD_BACK))

    def test_the_routes_stay_not_found_without_the_service(self):
        self.s.httpd.ask = None
        self.assertEqual(self.question()[0], 404)
        self.assertEqual(self.s.api("GET", "/api/ask/status")[0], 404)


if __name__ == "__main__":
    unittest.main()

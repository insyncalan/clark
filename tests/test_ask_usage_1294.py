"""Row 1294, Usage in tokens (A8): what asking used this month, per project and in all, tokens only, read only, kept on this computer.

The provider's count is read from the command's result object (`usage`); the service counts one answered question per project; GET /api/ask-usage
shows the month so far; the page shows the approved words (each pinned here, in the server's constants and in the page's own file). The command is
faked; nothing is sent. Fictional data only.

Run: python3 dev/run_tests.py test_ask_usage_1294
"""
import datetime
import json
import os
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import SRC

import _publish_fixture as plant
from clark import ask, ask_claude as ac, ask_service, ask_usage, server as sv, store as st
from test_ask_instructions_1294 import Running

DAY = datetime.date(2026, 11, 20)
USAGE = {"input_tokens": 2, "cache_creation_input_tokens": 5911, "cache_read_input_tokens": 3474, "output_tokens": 442}
JSX = (SRC / "clark" / "page" / "src" / "edit" / "UsageSettings.jsx").read_text(encoding="utf-8")


def result(usage=USAGE, text="Fine.\nCITE: P1"):
    got = {"type": "result", "subtype": "success", "is_error": False, "result": text}
    if usage is not None:
        got["usage"] = usage
    return json.dumps(got).encode()


class Counting(unittest.TestCase):
    def test_the_command_reports_tokens_and_all_four_counts_are_added(self):
        self.assertEqual(ac.read_tokens(result()), 2 + 5911 + 3474 + 442)
        self.assertEqual(ac.read_tokens(result({"input_tokens": 10, "output_tokens": 5})), 15)

    def test_no_count_is_guessed(self):
        for usage in (None, {}, {"input_tokens": 3}, {"output_tokens": 3}, {"input_tokens": "3", "output_tokens": 1}, {"input_tokens": True, "output_tokens": 1},
                      {"input_tokens": -1, "output_tokens": 1}, {"input_tokens": 1.5, "output_tokens": 1}, [1, 2]):
            self.assertIsNone(ac.read_tokens(result(usage)), repr(usage))
        self.assertIsNone(ac.read_tokens(b"not json"))
        self.assertIsNone(ac.read_tokens(b"[1]"))

    def test_the_provider_keeps_the_count_of_the_last_answered_question_only(self):
        from unittest import mock
        provider = ac.ClaudeCommand(places=(), env={}, limit=5)
        outs = [("ok", result(), 0), ("ok", result(None), 0), ("ok", b"garbage", 0)]
        with mock.patch.object(ac, "run", side_effect=lambda *a, **k: outs.pop(0)):
            self.assertEqual(provider.answer("/x/claude", "q", system=ask.RULES), "Fine.\nCITE: P1")
            self.assertEqual(provider.last_tokens, 9829)
            provider.answer("/x/claude", "q", system=ask.RULES)
            self.assertIsNone(provider.last_tokens)
            self.assertIsInstance(provider.answer("/x/claude", "q", system=ask.RULES), ask.Failure)
            self.assertIsNone(provider.last_tokens)


class TheFile(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.u = ask_usage.AskUsage(self.d)

    def test_a_question_adds_one_and_its_tokens_per_project(self):
        self.assertTrue(self.u.record("PUB", 100, DAY))
        self.assertTrue(self.u.record("PUB", None, DAY))
        self.assertTrue(self.u.record("OTH", 7, DAY))
        self.assertEqual(self.u.month(DAY), {"PUB": {"questions": 2, "tokens": 100}, "OTH": {"questions": 1, "tokens": 7}})

    def test_only_this_month_shows_and_an_old_month_is_dropped_at_the_next_question(self):
        self.u.record("PUB", 5, datetime.date(2026, 10, 31))
        self.assertEqual(self.u.month(DAY), {})
        self.u.record("PUB", 1, DAY)
        self.assertEqual(list(json.loads((self.d / ask_usage.FILE).read_text())), ["2026-11"])

    def test_a_damaged_file_reads_as_nothing_and_a_bad_code_is_not_kept(self):
        (self.d / ask_usage.FILE).write_text("{not json", encoding="utf-8")
        self.assertEqual(self.u.month(DAY), {})
        self.assertFalse(self.u.record("../x", 1, DAY))
        self.assertTrue(self.u.record("PUB", 1, DAY))
        (self.d / ask_usage.FILE).write_text(json.dumps({"2026-11": {"PUB": {"questions": -3, "tokens": "x"}, "bad": {"questions": 1}}}), encoding="utf-8")
        self.assertEqual(self.u.month(DAY), {"PUB": {"questions": 0, "tokens": 0}})

    def test_a_file_that_cannot_be_written_loses_the_count_and_never_raises(self):
        shutil.rmtree(self.d)
        self.assertFalse(self.u.record("PUB", 1, DAY))

    def test_the_file_holds_counts_and_nothing_else(self):
        self.u.record("PUB", 3, DAY)
        self.assertEqual(json.loads((self.d / ask_usage.FILE).read_text()), {"2026-11": {"PUB": {"questions": 1, "tokens": 3}}})


class Counted(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")
        self.provider = ask.StubProvider(reply="Fine.\nCITE: P1")
        self.provider.last_tokens = 1234
        self.service = ask_service.AskService(self.db, self.provider, [])
        self.service.today = lambda: DAY
        self.s = Running()
        self.s.httpd.ask = self.service
        self.addCleanup(lambda: (self.s.httpd.shutdown(), self.s.httpd.server_close()))

    def ask(self, project="PUB"):
        return self.s.api("POST", "/api/ask", {"project": project, "question": "What is the state of the plan?"})

    def usage(self):
        status, got = self.s.api("GET", "/api/ask-usage")
        self.assertEqual(status, 200, got)
        return got

    def test_nothing_asked_shows_the_month_so_far_with_zeros(self):
        got = self.usage()
        self.assertEqual((got["ok"], got["title"], got["note"]), (True, "Usage, 1 to 20 November 2026", "Read only. Nothing here leaves this computer."))
        self.assertEqual(got["all"], {"questions": 0, "tokens": 0})
        self.assertIn("PUB", [p["code"] for p in got["projects"]])
        self.assertTrue(all(p["questions"] == p["tokens"] == 0 for p in got["projects"]))

    def test_an_answered_question_counts_for_its_project_and_in_all(self):
        self.assertEqual(self.ask()[0], 200)
        self.assertEqual(self.ask()[0], 200)
        got = self.usage()
        mine = [p for p in got["projects"] if p["code"] == "PUB"][0]
        self.assertEqual((mine["questions"], mine["tokens"]), (2, 2468))
        self.assertEqual(got["all"], {"questions": 2, "tokens": 2468})

    def test_a_refused_or_failed_question_counts_for_nothing(self):
        self.provider.failure = "No answer."
        self.assertEqual(self.ask()[1]["ok"], False)
        self.assertEqual(self.ask("NOPE1")[0], 404)
        self.assertEqual(self.usage()["all"], {"questions": 0, "tokens": 0})

    def test_a_question_with_no_count_from_the_command_is_counted_with_no_tokens(self):
        self.provider.last_tokens = None
        self.ask()
        self.assertEqual(self.usage()["all"], {"questions": 1, "tokens": 0})

    def test_asking_on_or_off_is_what_the_page_says_beside_each_project(self):
        self.assertTrue(self.usage()["asking"])
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.update("app_settings", "1", {"ask_enabled": False})
        finally:
            store.close()
        self.assertFalse(self.usage()["asking"])

    def test_reading_changes_nothing_and_the_route_is_get_only(self):
        before = (self.d / "clark.db").read_bytes()
        self.usage()
        self.assertEqual((self.d / "clark.db").read_bytes(), before)
        self.assertFalse((self.d / ask_usage.FILE).exists())
        self.assertNotEqual(self.s.api("POST", "/api/ask-usage", {})[0], 200)


class TheWords(unittest.TestCase):
    """Every approved word, pinned in the server's constants and in the page's own file."""

    def test_the_server_words(self):
        self.assertEqual(ask_usage.group_title(datetime.date(2026, 11, 17)), "Usage, 1 to 17 November 2026")
        self.assertEqual(ask_usage.group_title(datetime.date(2026, 12, 3)), "Usage, 1 to 3 December 2026")
        self.assertEqual((ask_usage.ASKING_ON, ask_usage.ASKING_OFF), ("Asking is on", "Asking is off"))
        self.assertEqual((ask_usage.ALL_ROW, ask_usage.ALL_NOTE), ("All projects", "Tokens used"))
        self.assertEqual(ask_usage.READ_ONLY, "Read only. Nothing here leaves this computer.")
        self.assertEqual((ask_usage.THIS_MONTH, ask_usage.NO_QUESTIONS), ("Usage this month", "No questions: asking is off."))
        self.assertEqual(ask_usage.count_line(12, 3456), "12 questions · 3456 tokens")
        self.assertEqual(ask_usage.count_line(1, 0), "1 question · 0 tokens")

    def test_the_page_holds_the_same_words(self):
        for name, text in (("ASKING_ON", ask_usage.ASKING_ON), ("ASKING_OFF", ask_usage.ASKING_OFF), ("ALL_ROW", ask_usage.ALL_ROW), ("ALL_NOTE", ask_usage.ALL_NOTE),
                           ("READ_ONLY", ask_usage.READ_ONLY), ("THIS_MONTH", ask_usage.THIS_MONTH), ("NO_QUESTIONS", ask_usage.NO_QUESTIONS)):
            self.assertIn(f'const {name} = "{text}";', JSX, name)
        self.assertIn("`${questionsWords(q)} \u00b7 ${t} tokens`", JSX)
        self.assertIn("`${n} question`", JSX)
        self.assertIn("`${n} questions`", JSX)

    def test_the_page_shows_the_server_title_never_a_date_of_its_own(self):
        self.assertIn("usage.title", JSX)
        self.assertNotRegex(JSX, r"November|\b20\d\d\b")

    def test_tokens_only_never_money(self):
        for text in (JSX, (SRC / "clark" / "ask_usage.py").read_text(encoding="utf-8")):
            self.assertNotRegex(text.replace("cost", ""), r"(?i)\$\d|[£€]|\bUSD\b|\bprice\b|\bdollar|\bmoney\b|\bpaid\b")

    def test_the_two_places_the_page_shows_it_and_no_comment_has_hash_digits(self):
        settings = (SRC / "clark" / "page" / "src" / "edit" / "AskSettings.jsx").read_text(encoding="utf-8")
        self.assertIn("<UsageAll />", settings.split("function AllProjects()")[1].split("\n}\n")[0])
        self.assertIn("<UsageProject />", settings.split("function AskProject()")[1].split("\n}\n")[0])
        self.assertNotRegex(JSX, r"#\d")


if __name__ == "__main__":
    unittest.main()

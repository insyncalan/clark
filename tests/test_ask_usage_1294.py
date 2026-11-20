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
import time
import threading
import unittest
from pathlib import Path

from _paths import SRC

import _publish_fixture as plant
from clark import ai_providers, ask, ask_claude as ac, ask_service, ask_usage, server as sv, store as st
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

    def test_a_price_in_the_result_is_never_read_only_the_counts(self):
        got = json.loads(result())
        got["total_cost_usd"] = 0.42
        got["usage"].update({"cost_usd": 9.99, "cost": 3, "price": 1, "service_tier": "standard"})
        got["modelUsage"] = {"sonnet": {"costUSD": 7.5, "inputTokens": 99999, "outputTokens": 99999}}
        self.assertEqual(ac.read_tokens(json.dumps(got).encode()), 9829)
        self.assertEqual(ac.read_tokens(result({"input_tokens": 1, "output_tokens": 1, "total_cost_usd": 5, "cost": 5})), 2)
        self.assertIsNone(ac.read_tokens(json.dumps({"type": "result", "total_cost_usd": 0.42, "usage": {"cost_usd": 3}}).encode()))

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
        self.assertEqual(self.u.month(DAY), {"PUB": {"questions": 2, "tokens": 100, "unreported": 1}, "OTH": {"questions": 1, "tokens": 7, "unreported": 0}})

    def test_only_this_month_shows_and_an_old_month_is_dropped_at_the_next_question(self):
        self.u.record("PUB", 5, datetime.date(2026, 10, 31))
        self.assertEqual(self.u.month(DAY), {})
        self.u.record("PUB", 1, DAY)
        self.assertEqual(list(json.loads((self.d / ask_usage.FILE).read_text(encoding="utf-8"))), ["2026-11"])

    def test_a_damaged_file_reads_as_nothing_and_a_bad_code_is_not_kept(self):
        (self.d / ask_usage.FILE).write_text("{not json", encoding="utf-8")
        self.assertEqual(self.u.month(DAY), {})
        self.assertFalse(self.u.record("../x", 1, DAY))
        self.assertTrue(self.u.record("PUB", 1, DAY))
        (self.d / ask_usage.FILE).write_text(json.dumps({"2026-11": {"PUB": {"questions": -3, "tokens": "x"}, "bad": {"questions": 1}}}), encoding="utf-8")
        self.assertEqual(self.u.month(DAY), {"PUB": {"questions": 0, "tokens": 0, "unreported": 0}})

    def test_the_same_month_of_another_year_is_not_counted(self):
        self.u.record("PUB", 5, datetime.date(2025, 11, 20))
        self.assertEqual(self.u.month(DAY), {})
        self.assertEqual(self.u.month(datetime.date(2025, 11, 3)), {"PUB": {"questions": 1, "tokens": 5, "unreported": 0}})
        (self.d / ask_usage.FILE).write_text(json.dumps({"2025-11": {"PUB": {"questions": 4, "tokens": 40}}, "2026-10": {"PUB": {"questions": 3, "tokens": 30}}}), encoding="utf-8")
        self.assertEqual(self.u.month(DAY), {})
        self.u.record("PUB", 1, DAY)
        self.assertEqual(self.u.month(DAY), {"PUB": {"questions": 1, "tokens": 1, "unreported": 0}})

    def test_a_count_that_is_not_a_whole_number_is_not_kept(self):
        for bad in (1.5, "12", True, False, -1, None, [3], {"n": 3}, ask_usage.MAX_COUNT + 1):
            (self.d / ask_usage.FILE).write_text(json.dumps({"2026-11": {"PUB": {"questions": bad, "tokens": bad}}}), encoding="utf-8")
            self.assertEqual(self.u.month(DAY), {"PUB": {"questions": 0, "tokens": 0, "unreported": 0}}, repr(bad))
        (self.d / ask_usage.FILE).write_text(json.dumps({"2026-11": {"PUB": {"questions": 4, "tokens": 0}, "OTH": {"questions": 2, "tokens": 12}}}), encoding="utf-8")
        self.assertEqual(self.u.month(DAY), {"PUB": {"questions": 4, "tokens": 0, "unreported": 4}, "OTH": {"questions": 2, "tokens": 12, "unreported": 0}})
        self.assertTrue(self.u.record("PUB", 1.5, DAY))
        self.assertTrue(self.u.record("PUB", "12", DAY))
        self.assertTrue(self.u.record("PUB", True, DAY))
        self.assertTrue(self.u.record("PUB", -4, DAY))
        self.assertEqual(self.u.month(DAY)["PUB"], {"questions": 8, "tokens": 0, "unreported": 4})

    def test_a_file_that_cannot_be_written_loses_the_count_and_never_raises(self):
        shutil.rmtree(self.d)
        self.assertFalse(self.u.record("PUB", 1, DAY))

    def test_the_file_holds_counts_and_nothing_else(self):
        self.u.record("PUB", 3, DAY)
        self.assertEqual(json.loads((self.d / ask_usage.FILE).read_text(encoding="utf-8")), {"2026-11": {"PUB": {"questions": 1, "tokens": 3, "unreported": 0}}})


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
        self.assertEqual(got["all"], {"questions": 0, "tokens": 0, "unreported": 0})
        self.assertIn("PUB", [p["code"] for p in got["projects"]])
        self.assertTrue(all(p["questions"] == p["tokens"] == 0 for p in got["projects"]))

    def test_an_answered_question_counts_for_its_project_and_in_all(self):
        self.assertEqual(self.ask()[0], 200)
        self.assertEqual(self.ask()[0], 200)
        got = self.usage()
        mine = [p for p in got["projects"] if p["code"] == "PUB"][0]
        self.assertEqual((mine["questions"], mine["tokens"]), (2, 2468))
        self.assertEqual(got["all"], {"questions": 2, "tokens": 2468, "unreported": 0})

    def test_the_reply_to_a_question_carries_no_tokens_and_no_money(self):
        status, body = self.ask()
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"], body)
        self.assertNotRegex(json.dumps(body), r"(?i)token|usage|cost|price|money|dollar|[$£€]|1234")
        self.assertFalse([k for k in body if re.search(r"(?i)token|usage|cost|price", k)], list(body))

    def test_the_report_has_counts_and_tokens_and_no_money_field(self):
        self.ask()
        got = self.usage()
        self.assertEqual(sorted(got), ["all", "asking", "note", "ok", "projects", "title"])
        self.assertEqual(sorted(got["all"]), ["questions", "tokens", "unreported"])
        self.assertTrue(all(sorted(p) == ["code", "name", "questions", "tokens", "unreported"] for p in got["projects"]))
        self.assertNotRegex(json.dumps(got), r"(?i)cost|price|money|dollar|usd|[$£€]")

    def test_a_refused_or_failed_question_counts_for_nothing(self):
        self.provider.failure = "No answer."
        self.assertEqual(self.ask()[1]["ok"], False)
        self.assertEqual(self.ask("NOPE1")[0], 404)
        self.assertEqual(self.usage()["all"], {"questions": 0, "tokens": 0, "unreported": 0})

    def test_a_question_with_no_count_from_the_command_is_counted_with_no_tokens(self):
        self.provider.last_tokens = None
        self.ask()
        self.assertEqual(self.usage()["all"], {"questions": 1, "tokens": 0, "unreported": 1})

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


class FakeCommand:
    """Stands in for the Claude command: each answer is the command's own JSON result, read with the real read_answer and read_tokens, and the
    count is kept in `last_tokens` as ClaudeCommand.ask does. No `last_tokens` is set by the test."""
    provider = ac.PROVIDER
    models = ("sonnet",)

    def __init__(self, out):
        self.out, self.last_tokens, self.lock = out, None, None

    def status(self):
        return {"connected": True, "why": ""}

    def ask(self, request, model=None, prefer=False):
        self.last_tokens = None
        reply = ac.read_answer(self.out)
        if reply is None:
            return ask.Failure("No answer.")
        self.last_tokens = ac.read_tokens(self.out)
        return reply

    def stop(self, owner=None):
        return False


class ThroughTheChosenProvider(unittest.TestCase):
    """The real path: AskService -> ai_providers.Chosen -> ClaudeSubscription -> the command's result. The count must arrive, not be set on a mock."""
    ask, usage = Counted.ask, Counted.usage

    def setUp(self):
        Counted.setUp(self)
        self.command = FakeCommand(result())
        sub = ai_providers.ClaudeSubscription(self.command)
        self.service.provider = ai_providers.Chosen([sub], lambda: (sub, None, True), "Not connected.")

    def test_the_count_in_the_command_result_reaches_the_usage_record(self):
        self.assertEqual(self.ask()[0], 200)
        self.assertEqual(self.usage()["all"], {"questions": 1, "tokens": 9829, "unreported": 0})

    def test_a_result_with_no_or_a_damaged_count_is_counted_with_no_tokens(self):
        for usage in (None, {"input_tokens": 3}, {"input_tokens": "3", "output_tokens": 1}):
            self.command.out = result(usage)
            self.assertEqual(self.ask()[1]["ok"], True, usage)
        self.assertEqual(self.usage()["all"], {"questions": 3, "tokens": 0, "unreported": 3})

    def test_a_failed_question_does_not_leave_the_last_count_behind(self):
        self.ask()
        self.command.out = b"garbage"
        self.assertEqual(self.ask()[1]["ok"], False)
        self.assertEqual(self.service.provider.last_tokens, None)
        self.assertEqual(self.usage()["all"], {"questions": 1, "tokens": 9829, "unreported": 0})


class ThroughTheChatGPTCommand(unittest.TestCase):
    """The real path for ChatGPT: AskService -> Chosen -> ChatGPTSubscription -> the real CodexCommand running a stand-in script that prints the
    Codex event lines. The command reports no count, so each answer must be counted as unreported, never as a reported 0."""
    ask, usage = Counted.ask, Counted.usage

    def setUp(self):
        from unittest import mock
        from clark import ai_codex
        Counted.setUp(self)
        script = self.d / "codex"
        events = self.d / "events"
        events.write_text(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Fine.\nCITE: P1"}}) + "\n", encoding="utf-8")
        script.write_text(f'#!/bin/sh\ncat > /dev/null\ncat "{events}"\n', encoding="utf-8")
        script.chmod(0o700)
        command = ai_codex.CodexCommand(places=(str(self.d / "none"),), env={}, walled=False)
        for patch in (mock.patch.object(ai_codex.CodexCommand, "usable", return_value=(script, None)), mock.patch.object(ai_codex, "own_home", return_value="/Users/sam"),
                      mock.patch.object(ai_codex.platform, "scratch_parent", return_value=str(self.d))):
            patch.start()
            self.addCleanup(patch.stop)
        sub = ai_providers.ChatGPTSubscription(command)
        self.service.provider = ai_providers.Chosen([sub], lambda: (sub, None, True), "Not connected.")

    def test_a_chatgpt_answer_is_counted_as_a_question_with_no_count_reported(self):
        for _ in range(2):
            status, body = self.ask()
            self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.usage()["all"], {"questions": 2, "tokens": 0, "unreported": 2})
        mine = [p for p in self.usage()["projects"] if p["code"] == "PUB"][0]
        self.assertEqual(ask_usage.count_line(mine["questions"], mine["tokens"], mine["unreported"]), "2 questions · tokens not reported")


class ThroughBothProviders(unittest.TestCase):
    """A month with a Claude answer that reported a count and one that did not: the row says some were not reported."""
    ask, usage = Counted.ask, Counted.usage

    def setUp(self):
        Counted.setUp(self)
        self.command = FakeCommand(result())
        sub = ai_providers.ClaudeSubscription(self.command)
        self.service.provider = ai_providers.Chosen([sub], lambda: (sub, None, True), "Not connected.")

    def test_one_counted_and_one_not_reads_as_some_not_reported(self):
        self.ask()
        self.command.out = result(None)
        self.ask()
        got = self.usage()["all"]
        self.assertEqual(got, {"questions": 2, "tokens": 9829, "unreported": 1})
        self.assertEqual(ask_usage.count_line(got["questions"], got["tokens"], got["unreported"]), "2 questions · 9829 tokens, some not reported")


class TheWords(unittest.TestCase):
    """Every approved word, pinned in the server's constants and in the page's own file."""

    def test_the_server_words(self):
        self.assertEqual(ask_usage.group_title(datetime.date(2026, 11, 17)), "Usage, 1 to 17 November 2026")
        self.assertEqual(ask_usage.group_title(datetime.date(2026, 12, 3)), "Usage, 1 to 3 December 2026")
        self.assertEqual((ask_usage.ASKING_ON, ask_usage.ASKING_OFF), ("Asking is on", "Asking is off"))
        self.assertEqual((ask_usage.ALL_ROW, ask_usage.ALL_NOTE), ("All projects", "Tokens used"))
        self.assertEqual(ask_usage.READ_ONLY, "Read only. Nothing here leaves this computer.")
        self.assertEqual((ask_usage.THIS_MONTH, ask_usage.NO_QUESTIONS), ("Usage this month", "No questions: asking is off."))
        for args, words in (((12, 3456, 0), "12 questions · 3456 tokens"), ((1, 1, 0), "1 question · 1 token"), ((2, 0, 0), "2 questions · 0 tokens"),
                            ((1, 0, 1), "1 question · tokens not reported"), ((2, 0, 2), "2 questions · tokens not reported"),
                            ((2, 40, 1), "2 questions · 40 tokens, some not reported"), ((3, 1, 2), "3 questions · 1 token, some not reported"),
                            ((12, 3456), "12 questions · 3456 tokens")):
            self.assertEqual(ask_usage.count_line(*args), words, args)

    def test_a_file_from_before_the_unreported_count_reads_as_nothing_unreported_unless_it_has_no_tokens_at_all(self):
        d = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, d, True)
        (d / ask_usage.FILE).write_text(json.dumps({"2026-11": {"PUB": {"questions": 3, "tokens": 90}, "OTH": {"questions": 2, "tokens": 0},
                                                              "ABC": {"questions": 2, "tokens": 5, "unreported": 9}}}), encoding="utf-8")
        got = ask_usage.AskUsage(d).month(DAY)
        self.assertEqual([got[c]["unreported"] for c in ("PUB", "OTH", "ABC")], [0, 2, 2])
        self.assertEqual(ask_usage.count_line(3, 90, got["PUB"]["unreported"]), "3 questions · 90 tokens")
        self.assertEqual(ask_usage.count_line(2, 0, got["OTH"]["unreported"]), "2 questions · tokens not reported")

    def test_the_page_holds_the_same_words(self):
        for name, text in (("ASKING_ON", ask_usage.ASKING_ON), ("ASKING_OFF", ask_usage.ASKING_OFF), ("ALL_ROW", ask_usage.ALL_ROW), ("ALL_NOTE", ask_usage.ALL_NOTE),
                           ("READ_ONLY", ask_usage.READ_ONLY), ("THIS_MONTH", ask_usage.THIS_MONTH), ("NO_QUESTIONS", ask_usage.NO_QUESTIONS)):
            self.assertIn(f'const {name} = "{text}";', JSX, name)
        for text in ("`${questionsWords(q)} \u00b7 ${tokensWords(t)}`", "`${questionsWords(q)} \u00b7 tokens not reported`",
                     "`${questionsWords(q)} \u00b7 ${tokensWords(t)}, some not reported`", "`${n} token`", "`${n} tokens`"):
            self.assertIn(text, JSX, text)
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
        self.assertIn("{classicTheme() ? <UsageAll /> : null}", settings.split("function AllProjects()")[1].split("\n}\n")[0])
        self.assertIn("{classicTheme() ? <UsageProject /> : null}", settings.split("function AskProject()")[1].split("\n}\n")[0])
        self.assertNotRegex(JSX, r"#\d")


class OnThePage(unittest.TestCase):
    classic = True
    """The Usage lists in a real browser at 1400 and 900, against the real usage route (the command is faked). Chrome is required."""

    def setUp(self):
        from test_ask_settings import make_db, service
        from test_server import Running as Page
        from clark import page
        from test_page import DATA
        from clark import theme
        css = theme.css("prototype-2.0")
        self.s = Page(data_for=lambda code, archived=None: DATA.get(code),
                      page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css) if self.classic else page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = make_db(self.d)
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as step:
                step.create("projects", {"code": "OTH", "name": "Second Programme"})
                step.create("projects", {"code": "NEW", "name": "Third Programme"})
        finally:
            store.close()
        self.s.httpd.app_settings = service(self.db)
        self.service = ask_service.AskService(self.db, ask.StubProvider(reply="Fine.\nCITE: P1"), [])
        self.service.today = lambda: DAY
        self.service.usage.record("ABC", 1234, DAY)
        self.service.usage.record("ABC", 766, DAY)
        self.service.usage.record("OTH", 1, DAY)
        self.service.usage.record("NEW", None, DAY)
        self.s.httpd.ask = self.service

    def open_tab(self, cdp, tab):
        from _editor_checks import for_project
        from test_page import navigate
        from test_server import wait
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20), "the tabs")
        js(f"document.querySelector('[data-ask-tab={tab}]').click()")
        return sid, js

    def test_the_lists_show_names_and_numbers_and_do_not_overflow_at_1400_and_900(self):
        from test_server import chrome, wait
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                sid, js = self.open_tab(cdp, "all")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-list')"), 20), "the list")
                self.assertEqual(js("document.querySelector('#ask-usage-all h2').innerText"), "Usage, 1 to 20 November 2026")
                rows = js("[...document.querySelectorAll('#ask-usage-list li')].map(li => li.innerText.replace(/\\s+/g, ' ').trim())")
                self.assertEqual(rows, ["ABC Asking is on 2 questions \u00b7 2000 tokens", "NEW Asking is on 1 question \u00b7 tokens not reported",
                                        "OTH Asking is on 1 question \u00b7 1 token",
                                        "All projects Tokens used 4 questions \u00b7 2001 tokens, some not reported"])
                self.assertEqual(js("document.querySelector('#ask-usage-readonly').innerText"), "Read only. Nothing here leaves this computer.")
                self.assertTrue(js("[...document.querySelectorAll('#ask-usage-list li')].every(li => li.scrollWidth <= li.clientWidth + 1 && li.getBoundingClientRect().right <= document.querySelector('#ask-usage-all').getBoundingClientRect().right)"), "each row inside its card")
                self.assertTrue(wait(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), 10), f"no sideways scroll at {w}")
                self.assertNotRegex(js("document.querySelector('#ask-usage-all').innerText"), r"(?i)cost|price|[$\u00a3\u20ac]")
                js("document.querySelector('[data-ask-tab=project]').click()")
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-count')"), 20), "the project's count")
                self.assertEqual(js("document.querySelector('#ask-usage-project h2').innerText"), "Usage this month")
                self.assertEqual(js("document.querySelector('#ask-usage-count').innerText"), "2 questions")
                self.assertTrue(wait(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), 10), f"no sideways scroll on the project tab at {w}")


class CardsUnchanged(OnThePage):
    """Classic only: in Cards (no theme layer) neither Usage card is drawn, on either tab."""
    classic = False

    def test_the_lists_show_names_and_numbers_and_do_not_overflow_at_1400_and_900(self):
        pass

    def test_cards_draws_no_usage_card_on_either_tab(self):
        from test_server import chrome, wait
        with chrome() as cdp:
            for tab in ("all", "project"):
                sid, js = self.open_tab(cdp, tab)
                self.assertFalse(js("!!document.getElementById('theme')"), "Cards has no theme layer")
                self.assertTrue(wait(lambda: js("document.querySelectorAll('section.frame.setting').length > 0"), 20), "the tab drew")
                time.sleep(3)          # the Classic page shows the card once its read answers; give it that long
                self.assertEqual(js("document.querySelectorAll('#ask-usage-all, #ask-usage-project, #ask-usage-list, #ask-usage-count, #ask-usage-readonly').length"), 0, tab)


if __name__ == "__main__":
    unittest.main()

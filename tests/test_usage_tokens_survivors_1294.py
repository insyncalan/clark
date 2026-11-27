"""Row 1294, Usage in tokens: boundary tests for mutants the first test file did not kill (mutation sweep, author side).

Run: python3 dev/run_tests.py test_usage_tokens_survivors_1294
"""
import datetime
import unittest

from clark import ask_usage

DAY = datetime.date(2026, 11, 20)
TOP = ask_usage.MAX_COUNT


class Edges(unittest.TestCase):
    def test_a_zero_count_is_a_count_not_missing(self):
        self.assertEqual(ask_usage.tokens_in({"input_tokens": 0, "output_tokens": 0}), 0)

    def test_the_largest_allowed_count_is_kept_and_one_past_it_is_not(self):
        self.assertEqual(ask_usage.tokens_in({"input_tokens": TOP, "output_tokens": 0}), TOP)
        self.assertIsNone(ask_usage.tokens_in({"input_tokens": TOP + 1, "output_tokens": 0}))

    def test_a_stored_count_at_the_largest_allowed_value_reads_back_and_one_past_reads_as_nothing(self):
        self.assertEqual(ask_usage.whole(TOP), TOP)
        self.assertEqual(ask_usage.whole(TOP + 1), 0)


class Files(unittest.TestCase):
    def setUp(self):
        import os
        import shutil
        import tempfile
        from pathlib import Path
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.u = ask_usage.AskUsage(self.d)

    def put(self, text):
        self.u.path.write_text(text, encoding="utf-8")

    def test_a_file_that_is_a_list_reads_as_nothing_and_the_next_question_still_counts(self):
        self.put("[1, 2]")
        self.assertEqual(self.u.month(DAY), {})
        self.assertTrue(self.u.record("ABC", 5, DAY))
        self.assertEqual(self.u.month(DAY)["ABC"]["tokens"], 5)

    def test_a_code_with_more_after_it_is_not_a_project_code(self):
        self.put('{"2026-11": {"ABCDEFGHI": {"questions": 1, "tokens": 1}, "ABC": {"questions": 2, "tokens": 3}}}')
        self.assertEqual(list(self.u.month(DAY)), ["ABC"])

    def test_a_row_that_is_not_an_object_is_left_out(self):
        self.put('{"2026-11": {"ABC": 5, "OTH": {"questions": 1, "tokens": 2}}}')
        self.assertEqual(list(self.u.month(DAY)), ["OTH"])

    def test_a_code_with_more_after_it_is_not_recorded(self):
        self.assertFalse(self.u.record("ABCDEFGHIJ", 5, DAY))
        self.assertFalse(self.u.path.exists())


import json
import sqlite3
import threading
import time

import test_ask_claude as tc
from clark import ai_providers, ask, ask_service
from test_ask_usage_1294 import DAY as USAGE_DAY
import test_ask_usage_1294 as _test_ask_usage_1294


class Atomic(Files):
    def test_no_temporary_file_is_left_beside_the_count(self):
        self.u.record("ABC", 1, DAY)
        self.assertEqual(sorted(p.name for p in self.d.iterdir()), ["ask_usage.json"])

    def test_two_answers_at_once_are_both_counted(self):
        real = self.u.month

        def slow(day):
            got = real(day)
            time.sleep(0.02)          # a second writer reads while the first still holds its old rows
            return got
        self.u.month = slow
        threads = [threading.Thread(target=self.u.record, args=("ABC", 1, DAY)) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.u.month = real
        self.assertEqual(self.u.month(DAY)["ABC"], {"questions": 6, "tokens": 6, "unreported": 0})


class RealCommand(tc.Fake):
    def test_the_count_of_the_last_answer_is_not_kept_for_a_failed_one(self):
        self.put("reply", tc.result(tc.ANSWER, usage={"input_tokens": 3, "output_tokens": 4}))
        self.assertEqual(self.provider.ask(self.request()), tc.ANSWER)
        self.assertEqual(self.provider.last_tokens, 7)
        self.put("reply", "garbage")
        self.assertIsInstance(self.provider.ask(self.request()), ask.Failure)
        self.assertIsNone(self.provider.last_tokens)

    def test_a_result_that_is_not_an_object_has_no_count(self):
        self.assertIsNone(tc.ac.read_tokens(b'[{"usage": {"input_tokens": 1, "output_tokens": 1}}]'))
        self.assertIsNone(tc.ac.read_tokens(b'{"input_tokens": 1, "output_tokens": 1}'))


class Command:
    provider = tc.ac.PROVIDER
    models = ("sonnet",)

    def __init__(self, tokens, reply, has=True):
        self.reply, self.lock = reply, None
        if has:
            self.last_tokens = tokens

    def status(self):
        return {"connected": True, "why": ""}

    def ask(self, request, model=None, prefer=False):
        return self.reply

    def stop(self, owner=None):
        return False


class Chosen(unittest.TestCase):
    def chosen(self, command, pick=True):
        sub = ai_providers.ClaudeSubscription(command)
        return ai_providers.Chosen([sub], lambda: (sub, None, True) if self.pick else (None, None, False), "Not connected.")

    def test_the_count_is_none_after_a_failure_and_after_the_choice_is_off(self):
        self.pick = True
        chosen = self.chosen(Command(77, ask.Failure("No answer.")))
        chosen.last_tokens = 5
        chosen.ask(ask.build_request("Q?", []))
        self.assertIsNone(chosen.last_tokens)
        good = self.chosen(Command(9, "Fine."))
        self.assertEqual(good.ask(ask.build_request("Q?", [])), "Fine.")
        self.assertEqual(good.last_tokens, 9)
        self.pick = False
        self.assertIsInstance(good.ask(ask.build_request("Q?", [])), ask.Failure)
        self.assertIsNone(good.last_tokens)

    def test_a_command_with_no_count_at_all_gives_none_not_zero(self):
        self.pick = True
        chosen = self.chosen(Command(None, "Fine.", has=False))
        self.assertEqual(chosen.ask(ask.build_request("Q?", [])), "Fine.")
        self.assertIsNone(chosen.last_tokens)


class Report(unittest.TestCase):
    setUp = _test_ask_usage_1294.Counted.setUp
    ask, usage = _test_ask_usage_1294.Counted.ask, _test_ask_usage_1294.Counted.usage

    def db_do(self, sql, *args):
        con = sqlite3.connect(str(self.db))
        try:
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()

    def test_an_archived_project_shows_only_when_it_had_a_question(self):
        self.db_do("INSERT INTO projects (code, name, archived, active) VALUES ('OLD', 'Old Programme', 1, 0)")
        self.db_do("INSERT INTO projects (code, name, archived, active) VALUES ('GON', 'Gone Programme', 1, 0)")
        self.service.usage.record("OLD", 4, USAGE_DAY)
        rows = {p["code"]: p for p in self.usage()["projects"]}
        self.assertNotIn("GON", rows)
        self.assertEqual((rows["OLD"]["questions"], rows["OLD"]["tokens"]), (1, 4))

    def test_the_row_carries_the_project_name_and_exactly_its_counts(self):
        self.ask()
        row = [p for p in self.usage()["projects"] if p["code"] == "PUB"][0]
        self.assertTrue(row["name"])
        self.assertEqual(row, {"code": "PUB", "name": row["name"], "questions": 1, "tokens": 1234, "unreported": 0})
        self.assertEqual(sorted(self.usage()["all"]), ["questions", "tokens", "unreported"])

    def test_a_project_with_no_question_has_exactly_the_four_fields_and_zeros(self):
        rows = self.usage()["projects"]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row, {"code": row["code"], "name": row["name"], "questions": 0, "tokens": 0, "unreported": 0})

    def test_a_store_that_cannot_be_read_answers_busy_with_409_and_a_read_one_is_closed(self):
        closed = []

        class Store:
            def read(self, table):
                return [{"code": "ABC", "name": "A"}]

            def close(self):
                closed.append(1)
        self.service.reader = lambda: Store()
        self.assertEqual(self.service.usage_read()[0], 200)
        self.assertEqual(closed, [1, 1])          # the report's own read and the switch's

        def broken():
            raise sqlite3.OperationalError("locked")
        self.service.reader = broken
        self.assertEqual(self.service.usage_read()[0], 409)

    def test_a_project_row_with_no_text_code_is_left_out(self):
        class Store:
            def read(self, table):
                return [{"code": None, "name": "x"}, {"code": "ABC", "name": "A"}]

            def close(self):
                pass
        self.service.reader = lambda: Store()
        self.assertEqual([p["code"] for p in self.service.usage_read()[1]["projects"]], ["ABC"])


import test_ask_usage_1294 as _test_ask_usage_1294
from clark import store as st


class PageEdges(_test_ask_usage_1294.OnThePage):
    """The Usage cards in a real browser at 1400 and 900 for the cases the first page test does not reach."""

    def test_the_lists_show_names_and_numbers_and_do_not_overflow_at_1400_and_900(self):
        pass

    def at(self, cdp, code, tab):
        from test_page import DATA
        mine = self.s.httpd.data_for
        self.s.httpd.data_for = lambda c, archived=None: {**DATA["ABC"], "project": {**DATA["ABC"]["project"], "code": c}} if c in ("ABC", "OTH", "NIL") else mine(c)
        from _editor_checks import for_project
        from test_page import navigate
        from test_server import wait
        sid = navigate(cdp, self.s.port, for_project(f"#settings&p={code}&s=claude"))
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20), "the tabs")
        js(f"document.querySelector('[data-ask-tab={tab}]').click()")
        return sid, js

    def widths(self, cdp, sid, w):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)

    def switch(self, on):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.update("app_settings", "1", {"ask_enabled": on})
        finally:
            store.close()

    def test_the_project_tab_names_its_own_project_and_one_question_in_the_singular(self):
        from test_server import chrome, wait
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                sid, js = self.at(cdp, "OTH", "project")
                self.widths(cdp, sid, w)
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-count')"), 20), "the count")
                self.assertEqual(js("document.querySelector('#ask-usage-count').innerText"), "1 question")

    def test_with_asking_off_a_project_with_no_question_says_so_and_one_with_questions_shows_them(self):
        from test_server import chrome, wait
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.create("projects", {"code": "NIL", "name": "Fourth Programme"})
        finally:
            store.close()
        self.switch(False)
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                for code, want in (("NIL", "No questions: asking is off."), ("OTH", "1 question")):
                    sid, js = self.at(cdp, code, "project")
                    self.widths(cdp, sid, w)
                    self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-count')"), 20), "the count")
                    self.assertTrue(wait(lambda: js("document.querySelector('#ask-usage-count').innerText") == want, 10), (code, js("document.querySelector('#ask-usage-count').innerText")))

    def test_with_asking_on_a_project_with_no_question_shows_zero_questions(self):
        from test_server import chrome, wait
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.create("projects", {"code": "NIL", "name": "Fourth Programme"})
        finally:
            store.close()
        with chrome() as cdp:
            sid, js = self.at(cdp, "NIL", "project")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-count')"), 20), "the count")
            self.assertEqual(js("document.querySelector('#ask-usage-count').innerText"), "0 questions")

    def test_an_answer_that_is_not_a_good_report_shows_the_could_not_read_line_and_no_list(self):
        from test_server import chrome, wait
        good = {"ok": True, "title": "T", "asking": True, "projects": [{"code": "ABC", "name": "x", "questions": 1, "tokens": 1, "unreported": 0}],
                "all": {"questions": 1, "tokens": 1, "unreported": 0}, "note": "n"}
        cases = {"status": (500, good), "not_ok": (200, {**good, "ok": False}), "no_projects": (200, {k: v for k, v in good.items() if k != "projects"})}
        for name, answer in cases.items():
            service = self.service

            class Stub(ask_service.AskService):
                def usage_read(self, *_ignored):
                    return answer
            stub = Stub(self.db, ask.StubProvider(reply="x"), [])
            self.s.httpd.ask = stub
            for w in (1400, 900):
                with self.subTest(case=name, width=w), chrome() as cdp:
                    sid, js = self.at(cdp, "ABC", "all")
                    self.widths(cdp, sid, w)
                    self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-note')"), 20), name)
                    self.assertEqual(js("document.querySelector('#ask-usage-note').innerText"), "Usage could not be read just now.")
                    self.assertEqual(js("document.querySelectorAll('#ask-usage-list, #ask-usage-readonly').length"), 0)
            self.s.httpd.ask = service


class ZeroWordsAndMonth(unittest.TestCase):
    def test_zero_is_plural_and_one_is_singular_in_both_words(self):
        self.assertEqual(ask_usage.questions_words(0), "0 questions")
        self.assertEqual(ask_usage.tokens_words(0), "0 tokens")
        self.assertEqual(ask_usage.questions_words(1), "1 question")
        self.assertEqual(ask_usage.tokens_words(1), "1 token")
        self.assertEqual(ask_usage.count_line(1, 0), "1 question \u00b7 0 tokens")

    def test_a_month_below_ten_is_kept_under_a_two_digit_key_and_read_back(self):
        import json
        import os
        import shutil
        import tempfile
        from pathlib import Path
        march = datetime.date(2026, 3, 9)
        self.assertEqual(ask_usage.month_key(march), "2026-03")
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        u = ask_usage.AskUsage(d)
        self.assertTrue(u.record("ABC", 5, march))
        self.assertEqual(list(json.loads(u.path.read_text(encoding="utf-8"))), ["2026-03"])
        self.assertEqual(u.month(march)["ABC"], {"questions": 1, "tokens": 5, "unreported": 0})

    def test_a_write_that_cannot_replace_the_file_leaves_the_old_count_whole(self):
        import os
        import shutil
        import tempfile
        from pathlib import Path
        from unittest import mock
        d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, d, True)
        u = ask_usage.AskUsage(d)
        self.assertTrue(u.record("ABC", 5, DAY))
        before = u.path.read_text(encoding="utf-8")
        with mock.patch.object(ask_usage.os, "replace", side_effect=OSError("denied")):
            self.assertFalse(u.record("ABC", 7, DAY))
        self.assertEqual(u.path.read_text(encoding="utf-8"), before)
        self.assertEqual(u.month(DAY)["ABC"]["tokens"], 5)


from test_ask_connector_used import Base as ConnectorBase, mail
from test_ask_connector_wiring import final as final_line, stream as stream_of


class ConnectorRun(ConnectorBase):
    def test_a_connector_run_reads_the_tokens_of_its_result_and_a_refused_one_reads_none(self):
        self.turn_on()
        usage = {"input_tokens": 10, "output_tokens": 5}
        done = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "Fine.\nCITE: P1", "usage": usage})
        self.out = stream_of(*mail(), done)
        self.assertEqual(self.ask()["ok"], True)
        self.assertEqual(self.provider.last_tokens, 15)
        self.out = stream_of(*mail(), final_line("Fine.\nCITE: P1"))
        self.ask()
        self.assertIsNone(self.provider.last_tokens)


class ZeroOnThePage(_test_ask_usage_1294.OnThePage):
    def test_the_lists_show_names_and_numbers_and_do_not_overflow_at_1400_and_900(self):
        pass

    def test_a_real_zero_count_reads_0_tokens_and_none_reads_0_questions_0_tokens(self):
        from test_server import chrome, wait
        self.service.usage.record("ZER", 0, DAY)
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.create("projects", {"code": "ZER", "name": "Zero Programme"})
                s.create("projects", {"code": "NIL", "name": "Fourth Programme"})
        finally:
            store.close()
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                sid, js = self.open_tab(cdp, "all")
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-usage-list')"), 20), "the list")
                rows = js("[...document.querySelectorAll('#ask-usage-list li')].map(li => li.innerText.replace(/\\s+/g, ' ').trim())")
                self.assertIn("NIL Asking is on 0 questions \u00b7 0 tokens", rows)
                self.assertIn("ZER Asking is on 1 question \u00b7 0 tokens", rows)


class SortAndSkip(unittest.TestCase):
    """The report's rows: sorted by code, no cap, archived with no question skipped (row 1294)."""
    setUp = _test_ask_usage_1294.Counted.setUp
    ask, usage = _test_ask_usage_1294.Counted.ask, _test_ask_usage_1294.Counted.usage

    def rows_from(self, projects, kept=None):
        class Store:
            def read(self, table):
                return projects

            def close(self):
                pass
        self.service.reader = lambda: Store()
        for code, n in (kept or {}).items():
            for _ in range(n):
                self.service.usage.record(code, 3, USAGE_DAY)
        return self.service.usage_read()[1]

    def test_twenty_five_projects_all_show_in_code_order_whatever_the_store_order_or_names(self):
        codes = ["P%02d" % i for i in range(25)]
        shuffled = codes[12:] + codes[:12]
        projects = [{"code": c, "name": "N%02d" % (24 - int(c[1:]))} for c in reversed(shuffled)]
        got = self.rows_from(projects, {"P03": 1})
        self.assertEqual([p["code"] for p in got["projects"]], codes)
        self.assertEqual(len(got["projects"]), 25)
        self.assertEqual(got["all"], {"questions": 1, "tokens": 3, "unreported": 0})

    def test_an_archived_project_is_skipped_unless_it_had_a_question(self):
        projects = [{"code": "AAA", "name": "a", "archived": 1}, {"code": "BBB", "name": "b", "archived": 1},
                    {"code": "CCC", "name": "c", "archived": 0}, {"code": "DDD", "name": "d"}]
        got = self.rows_from(projects, {"BBB": 2})
        self.assertEqual([(p["code"], p["questions"]) for p in got["projects"]], [("BBB", 2), ("CCC", 0), ("DDD", 0)])

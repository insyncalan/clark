"""Row 1306 test 7, survivors of the hand sweep and of the earlier sweep: one test per survivor (ask_service.py; guarded).

Run: python3 dev/run_tests.py test_ask_stop_off_survivors
The provider is a stand-in; nothing is sent anywhere. Fictional data only.
"""
import sqlite3
import threading
import unittest
from dataclasses import replace
from unittest import mock

from clark import ask, ask_claude, ask_connectors, ask_service
from test_app_settings_route import Base
from test_ask_connector_off_stops_1306 import Waiting

QUICK = 0.6        # seconds a thread is given to prove it is held back (never more than 2)


class Recording(Waiting):
    def __init__(self):
        super().__init__()
        self.seen = None

    def ask(self, request):
        self.seen = request
        return super().ask(request)


class Survivors(Base):
    def setUp(self):
        super().setUp()
        found = [{"connector": n, "label": n.title(), "server": "x"} for n in ("mail", "calendar", "teams", "sharepoint", "todoist")]
        p = mock.patch.object(ask_connectors, "list_found", lambda *a, **k: [dict(x) for x in found])
        p.start()
        self.addCleanup(p.stop)
        self.provider = Recording()
        self.asking = ask_service.AskService(self.db, self.provider, [])
        self.s.httpd.ask = self.asking
        self.provider.owner = self.asking.owner
        for name in ("mail", "teams"):
            self.assertEqual(self.call("POST", "/api/ask-connectors", {"id": name, "on": True})[0], 200)
        self.addCleanup(self.provider.release.set)

    def post(self, body):
        return self.call("POST", "/api/ask-connectors", body)

    def start(self, project="ABC"):
        got = {}
        t = threading.Thread(target=lambda: got.update(r=self.asking.ask({"project": project, "question": "What is open?"})), daemon=True)
        t.start()
        return t, got

    def mail_off(self):
        self.assertEqual(self.service.change_connectors({"id": "mail", "on": False})[0], 200)

    # ----- connectors_now (M13, M14)
    def test_a_store_that_fails_with_a_database_error_or_a_type_error_gives_no_connector(self):
        for error in (sqlite3.OperationalError("locked"), TypeError("bad")):
            with mock.patch.object(self.asking, "reader", side_effect=error):
                self.assertEqual(self.asking.connectors_now("ABC", ("mail",)), (), repr(error))

    def test_the_store_handle_is_closed_after_the_read_whether_it_worked_or_not(self):
        store = mock.Mock()
        store.connector_allowed.return_value = True
        with mock.patch.object(self.asking, "reader", return_value=store):
            self.assertEqual(self.asking.connectors_now("ABC", ("mail",)), ("mail",))
        self.assertEqual(store.close.call_count, 1)
        store = mock.Mock()
        store.connector_allowed.side_effect = RuntimeError("bad")
        with mock.patch.object(self.asking, "reader", return_value=store):
            self.assertEqual(self.asking.connectors_now("ABC", ("mail",)), ())
        self.assertEqual(store.close.call_count, 1)

    # ----- stop_off against the list (M26)
    def test_stop_off_reaches_every_question_even_when_one_leaves_the_list_as_it_is_stopped(self):
        a, b = ask_service.Run("ABC", ("mail",)), ask_service.Run("ABC", ("mail",))
        real = a.cancel

        class Leaves(ask_service.Started):
            def set(inner):
                super().set()
                self.asking.runs.remove(a)           # the question finishes the moment it is stopped
        a.cancel = Leaves()
        self.asking.runs.extend([a, b])
        self.mail_off()
        self.asking.stop_off()
        self.assertTrue(b.cancel.is_set(), "the second question was not skipped by the list changing under the loop")
        self.assertIsNot(a.cancel, real)

    def test_stop_off_waits_for_the_lock_that_guards_the_list(self):
        run = ask_service.Run("ABC", ("mail",))
        self.asking.runs.append(run)
        self.mail_off()
        done = threading.Event()
        self.asking.using_lock.acquire()
        t = threading.Thread(target=lambda: (self.asking.stop_off(), done.set()), daemon=True)
        t.start()
        try:
            self.assertFalse(done.wait(QUICK), "stop_off read the list without the lock")
        finally:
            self.asking.using_lock.release()
        self.assertTrue(done.wait(10))
        self.assertTrue(run.cancel.is_set())

    def test_a_question_enters_the_list_only_under_the_lock(self):
        self.asking.using_lock.acquire()
        t, got = self.start()
        try:
            self.assertFalse(self.provider.entered.wait(QUICK), "the question put itself in the list without the lock")
            self.assertEqual(self.asking.runs, [])
        finally:
            self.asking.using_lock.release()
        self.assertTrue(self.provider.entered.wait(10))
        self.provider.release.set()
        t.join(10)

    def test_a_question_leaves_the_list_only_under_the_lock(self):
        t, got = self.start()
        self.assertTrue(self.provider.entered.wait(10))
        self.asking.using_lock.acquire()
        self.provider.release.set()
        try:
            t.join(QUICK)
            self.assertTrue(t.is_alive(), "the question took itself out of the list without the lock")
        finally:
            self.asking.using_lock.release()
        t.join(10)
        self.assertFalse(t.is_alive())
        self.assertEqual(self.asking.runs, [])

    # ----- Run (M27)
    def test_a_run_keeps_its_own_tuple_of_the_connectors(self):
        source = ["mail", "teams"]
        run = ask_service.Run("ABC", source)
        self.assertEqual(run.connectors, ("mail", "teams"))
        self.assertIsInstance(run.connectors, tuple)
        source.append("calendar")
        self.assertEqual(run.connectors, ("mail", "teams"))
        self.assertEqual(ask_service.Run("ABC", iter(["mail"])).connectors, ("mail",))
        self.assertEqual(ask_service.Run("ABC", {"mail"}).connectors, ("mail",))

    # ----- Started (M30)
    def test_reading_the_event_marks_it_started_whatever_it_says_and_only_reading(self):
        c = ask_service.Started()
        self.assertFalse(c.started)
        c.set()
        c.wait(0)
        self.assertFalse(c.started, "setting or waiting is not starting")
        self.assertIs(c.is_set(), True)
        self.assertTrue(c.started)
        d = ask_service.Started()
        self.assertIs(d.is_set(), False)
        self.assertTrue(d.started, "a read that says not stopped is the start")
        self.assertIs(d.is_set(), False)
        self.assertTrue(d.started)

    def test_the_real_provider_reads_the_event_once_when_it_starts_and_not_when_busy(self):
        class Counting(ask_service.Started):
            reads = 0

            def is_set(inner):
                Counting.reads += 1
                return super().is_set()
        provider = ask_claude.ClaudeCommand()
        request = ask.Request(text="x", question="x")
        busy = Counting()
        provider.lock.acquire()
        try:
            self.assertEqual(provider.ask(replace(request, cancel=busy)).message, ask_claude.BUSY)
        finally:
            provider.lock.release()
        self.assertFalse(busy.started, "a question that found the provider busy has not started")
        self.assertEqual(Counting.reads, 0)
        stopped = Counting()
        stopped.set()
        self.assertEqual(provider.ask(replace(request, cancel=stopped)).message, ask.STOPPED)
        self.assertTrue(stopped.started)
        self.assertEqual(Counting.reads, 1)

    # ----- stop_off (earlier sweep)
    def test_stop_off_goes_on_past_a_question_the_change_does_not_touch(self):
        untouched, touched = ask_service.Run("ABC", ("teams",)), ask_service.Run("ABC", ("mail",))
        self.asking.runs.extend([untouched, touched])
        self.mail_off()
        self.asking.stop_off()
        self.assertFalse(untouched.cancel.is_set())
        self.assertTrue(touched.cancel.is_set())

    def test_stop_off_reports_what_the_provider_says_it_did(self):
        self.mail_off()
        for said in (True, False):
            run = ask_service.Run("ABC", ("mail",))
            run.cancel.is_set()                                  # started
            self.asking.runs[:] = [run]
            self.provider.stop = lambda owner=None, said=said: said
            self.assertIs(self.asking.stop_off(), said)
        self.asking.runs[:] = []

    # ----- the request (earlier sweep)
    def test_a_question_asks_the_provider_with_the_services_owner_and_connectors_for_its_project(self):
        self.assertEqual(self.post({"id": "teams", "project": "ABC", "off_here": True})[0], 200)
        t, got = self.start("ABC")
        self.assertTrue(self.provider.entered.wait(10))
        self.assertIs(self.provider.seen.owner, self.asking.owner)
        self.assertIsNotNone(self.provider.seen.owner)
        self.assertEqual(self.provider.given, ("mail",), "teams is Off for this project only, and the read is for this project")
        self.provider.release.set()
        t.join(10)
        t2, got2 = self.start("DEF")
        t2.join(10)
        self.assertEqual(self.provider.given, ("mail", "teams"))

    def test_a_connector_turned_off_for_this_project_after_the_data_was_read_is_not_given(self):
        def folder_data(*_a, **_k):                   # the switch goes Off for this project only, after the first read of the connectors
            self.assertEqual(self.post({"id": "teams", "project": "ABC", "off_here": True})[0], 200)
            return ask_service.ask_passages.FolderData(passages=())
        with mock.patch.object(ask_service.ask_passages, "folder_data", folder_data):
            t, got = self.start("ABC")
            self.assertTrue(self.provider.entered.wait(10))
        self.assertEqual(self.provider.given, ("mail",))
        self.assertEqual([r.connectors for r in self.asking.runs], [("mail",)])
        self.provider.release.set()
        t.join(10)


if __name__ == "__main__":
    unittest.main()

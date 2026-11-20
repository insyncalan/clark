"""Row 1306 test 7: turning a connector Off stops a question running on it (ask_service.py, server.py; guarded).

Run: python3 dev/run_tests.py test_ask_connector_off_stops_1306
The provider here is a stand-in that waits until it is stopped; nothing is sent anywhere. Fictional data only.
"""
import threading
import time
import unittest
from unittest import mock

from clark import ask, ask_connectors, ask_service
from test_app_settings_route import Base


class Waiting(ask.StubProvider):
    """Answers only when released; Stop (for the owner that asked) releases it with the stopped failure."""

    def __init__(self):
        super().__init__(reply="Here is what I found.")
        self.entered, self.release, self.stopped = threading.Event(), threading.Event(), 0
        self.last_line = None
        self.given = None

    def ask(self, request):
        self.given = request.connectors
        self.entered.set()
        self.release.wait(10)
        return ask.Failure(ask.STOPPED) if self.stopped else self.reply

    def stop(self, owner=None):
        if not self.entered.is_set() or self.release.is_set():
            return False
        self.stopped += 1
        self.release.set()
        return True


class OffStops(Base):
    def setUp(self):
        super().setUp()
        found = [{"connector": n, "label": n.title(), "server": "x"} for n in ("mail", "calendar", "teams", "sharepoint", "todoist")]
        p = mock.patch.object(ask_connectors, "list_found", lambda *a, **k: [dict(x) for x in found])
        p.start()
        self.addCleanup(p.stop)
        self.provider = Waiting()
        self.asking = ask_service.AskService(self.db, self.provider, [])
        self.s.httpd.ask = self.asking
        for name in ("mail", "teams"):
            self.assertEqual(self.post({"id": name, "on": True})[0], 200)

    def post(self, body):
        return self.call("POST", "/api/ask-connectors", body)

    def running(self, project="ABC"):
        """A question in `project` at the provider; its thread and where its body will be."""
        got = {}
        t = threading.Thread(target=lambda: got.update(r=self.asking.ask({"project": project, "question": "What is open?"})), daemon=True)
        t.start()
        self.assertTrue(self.provider.entered.wait(10), "the question reached the provider")
        self.addCleanup(self.provider.release.set)
        return t, got

    def finish(self, t, got):
        t.join(10)
        self.assertFalse(t.is_alive())
        return got["r"]

    def test_off_for_every_project_stops_a_question_that_was_given_it(self):
        t, got = self.running()
        status, body = self.post({"id": "mail", "on": False})
        self.assertEqual((status, body["ok"]), (200, True), body)
        status, answer = self.finish(t, got)
        self.assertEqual((status, answer["ok"], answer["message"]), (200, False, ask.STOPPED))
        self.assertEqual(self.provider.stopped, 1)

    def test_off_for_one_project_stops_a_question_in_that_project(self):
        t, got = self.running("ABC")
        self.assertEqual(self.post({"id": "teams", "project": "ABC", "off_here": True})[0], 200)
        self.assertEqual(self.finish(t, got)[1]["message"], ask.STOPPED)

    def test_off_for_another_project_stops_nothing(self):
        t, got = self.running("ABC")
        self.assertEqual(self.post({"id": "teams", "project": "DEF", "off_here": True})[0], 200)
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_off_for_a_connector_the_question_did_not_have_stops_nothing(self):
        t, got = self.running()
        self.assertEqual(self.post({"id": "sharepoint", "on": False})[0], 200)       # already Off: the same setting
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_turning_one_on_or_a_refused_change_stops_nothing(self):
        t, got = self.running()
        self.assertEqual(self.post({"id": "calendar", "on": True})[0], 200)
        self.assertEqual(self.post({"id": "mail", "on": "no"})[0], 400)
        self.assertEqual(self.post({"id": "nonsense", "on": False})[0], 400)
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_a_change_that_is_refused_or_already_in_use_stops_nothing(self):
        t, got = self.running()
        with mock.patch.object(self.service, "change_connectors", return_value=(409, {"ok": False, "code": "cant_save", "message": "Not saved."})):
            self.assertEqual(self.post({"id": "mail", "on": False})[0], 409)
        self.assertEqual(self.provider.stopped, 0)
        self.assertEqual(self.post({"id": "mail", "on": True})[1]["message"], "That is the setting already in use.")
        self.assertEqual(self.post({"id": "mail", "project": "ABC", "off_here": False})[0], 200)
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_a_question_with_no_connector_is_not_stopped(self):
        for name in ("mail", "teams"):
            self.post({"id": name, "on": False})
        t, got = self.running()
        self.post({"id": "mail", "on": False})
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_a_connector_turned_off_before_the_send_is_not_given_to_the_provider(self):
        self.post({"id": "mail", "on": False})
        self.assertEqual(self.asking.connectors_now("ABC", ("mail", "teams")), ("teams",))
        self.post({"id": "teams", "project": "ABC", "off_here": True})
        self.assertEqual(self.asking.connectors_now("ABC", ("mail", "teams")), ())
        self.assertEqual(self.asking.connectors_now("DEF", ("teams",)), ("teams",))
        self.assertEqual(self.asking.connectors_now("ABC", ()), ())

    def test_a_connector_turned_off_after_the_data_was_read_is_not_sent_with_the_question(self):
        def folder_data(*_a, **_k):                   # the folders are read after the switches were; the switch goes Off here
            self.post({"id": "mail", "on": False})
            return ask_service.ask_passages.FolderData(passages=())
        with mock.patch.object(ask_service.ask_passages, "folder_data", folder_data):
            t, got = self.running()
        self.assertEqual(self.provider.given, ("teams",))
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_a_switch_that_cannot_be_read_gives_no_connector(self):
        with mock.patch.object(ask_service.Store, "connector_allowed", side_effect=RuntimeError("bad")):
            self.assertEqual(self.asking.connectors_now("ABC", ("mail", "teams")), ())

    def test_a_store_that_cannot_be_read_gives_no_connector(self):
        with mock.patch.object(self.asking, "reader", side_effect=OSError("gone")):
            self.assertEqual(self.asking.connectors_now("ABC", ("mail",)), ())

    def test_nothing_is_stopped_when_nothing_is_running(self):
        self.assertIs(self.asking.stop_using("mail"), False)
        self.assertIsNone(self.asking.using)

    def test_the_marker_is_cleared_when_the_question_is_over(self):
        t, got = self.running()
        self.assertEqual(self.asking.using, ("ABC", frozenset({"mail", "teams"})))
        self.provider.release.set()
        self.finish(t, got)
        self.assertIsNone(self.asking.using)


if __name__ == "__main__":
    unittest.main()

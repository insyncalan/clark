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
        self.lock = threading.Lock()                  # like the real provider: one question at a time, a second finds it busy
        self.owner = None                             # the owner the service asked with; a Stop for any other owner ends nothing
        self.at_door, self.door = threading.Event(), None      # a test may hold a question here, before the provider takes its place

    def ask(self, request):
        if self.door is not None:
            self.at_door.set()
            self.door.wait(10)
        if not self.lock.acquire(blocking=False):
            return ask.Failure("busy")                # a busy question never reads its cancel event, like the real provider
        try:
            if request.cancel is not None and request.cancel.is_set():       # read once, when the run really starts
                return ask.Failure(ask.STOPPED)
            self.given = request.connectors
            self.entered.set()
            self.release.wait(10)
            return ask.Failure(ask.STOPPED) if self.stopped else self.reply
        finally:
            self.lock.release()

    def stop(self, owner=None):
        if owner is not self.owner or not self.entered.is_set() or self.release.is_set() or not self.lock.locked():
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
        self.provider.owner = self.asking.owner
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

    def test_a_refused_answer_stops_nothing_even_when_a_connector_is_already_off(self):
        t, got = self.running()
        self.assertEqual(self.service.change_connectors({"id": "mail", "on": False})[0], 200)      # Off, saved without the route: nothing stopped yet
        self.assertEqual(self.provider.stopped, 0)
        with mock.patch.object(self.service, "change_connectors", return_value=(409, {"ok": False, "code": "cant_save", "message": "Not saved."})):
            self.assertEqual(self.post({"id": "calendar", "on": False})[0], 409)
        self.assertEqual(self.provider.stopped, 0)
        self.assertEqual(self.post({"id": "mail", "on": False})[0], 200)       # the same setting again, answered 200: now the route checks and stops
        self.assertEqual(self.finish(t, got)[1]["message"], ask.STOPPED)

    def test_without_the_settings_service_the_route_is_not_found(self):
        self.s.httpd.app_settings = None
        self.assertEqual(self.post({"id": "mail", "on": False})[0], 404)

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
        self.assertEqual([r.connectors for r in self.asking.runs], [("teams",)])      # the record holds what was really given
        self.assertEqual(self.post({"id": "calendar", "on": True})[0], 200)
        self.assertEqual(self.post({"id": "calendar", "on": False})[0], 200)          # an unrelated change does not stop it
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_an_off_saved_right_after_the_connectors_were_read_still_stops_the_question(self):
        real, state = self.asking.connectors_now, {"in_stop": False, "done": False}

        def read_then_off(code, chosen):              # the Off is saved the moment after the question's own read, before anything else
            got = real(code, chosen)
            if not state["done"] and not state["in_stop"]:
                state["done"] = True
                self.assertEqual(self.post({"id": "mail", "on": False})[0], 200)
            return got
        orig_stop = self.asking.stop_off

        def stop_off():
            state["in_stop"] = True
            try:
                return orig_stop()
            finally:
                state["in_stop"] = False
        with mock.patch.object(self.asking, "connectors_now", read_then_off), mock.patch.object(self.asking, "stop_off", stop_off):
            got = {}
            t = threading.Thread(target=lambda: got.update(r=self.asking.ask({"project": "ABC", "question": "What is open?"})), daemon=True)
            t.start()
            t.join(10)
        self.assertFalse(t.is_alive())
        status, answer = got["r"]
        self.assertEqual((status, answer["ok"], answer["message"]), (200, False, ask.STOPPED))     # the run was in the list, so stop_off cancelled it
        self.assertFalse(self.provider.entered.is_set())
        self.assertEqual(self.asking.runs, [])

    def test_a_switch_that_cannot_be_read_gives_no_connector(self):
        with mock.patch.object(ask_service.Store, "connector_allowed", side_effect=RuntimeError("bad")):
            self.assertEqual(self.asking.connectors_now("ABC", ("mail", "teams")), ())

    def test_a_store_that_cannot_be_read_gives_no_connector(self):
        with mock.patch.object(self.asking, "reader", side_effect=OSError("gone")):
            self.assertEqual(self.asking.connectors_now("ABC", ("mail",)), ())

    def test_the_marker_is_cleared_when_the_question_is_over(self):
        t, got = self.running()
        self.assertEqual([(r.project, r.connectors) for r in self.asking.runs], [("ABC", ("mail", "teams"))])
        self.provider.release.set()
        self.finish(t, got)
        self.assertEqual(self.asking.runs, [])

    def second(self):
        """A second question while the first is at the provider: it gets busy and is over."""
        status, answer = self.asking.ask({"project": "ABC", "question": "And what else?"})
        self.assertEqual((status, answer["ok"]), (200, False))
        self.assertIn("busy", answer["message"])

    def test_a_busy_second_question_does_not_take_the_first_ones_place(self):
        t, got = self.running()
        self.second()
        self.assertEqual(len(self.asking.runs), 1)                       # the first one's own entry is still there
        self.assertEqual(self.post({"id": "mail", "on": False})[0], 200)
        self.assertEqual(self.finish(t, got)[1]["message"], ask.STOPPED)
        self.assertEqual(self.provider.stopped, 1)

    def test_the_first_finishing_clears_only_its_own_entry(self):
        t, got = self.running()
        other = ask_service.Run("DEF", ("mail",))
        self.asking.runs.append(other)
        self.provider.release.set()
        self.finish(t, got)
        self.assertEqual(self.asking.runs, [other])

    def test_off_in_the_window_before_the_provider_starts_means_it_never_starts(self):
        self.provider.door = threading.Event()
        self.addCleanup(self.provider.door.set)
        got = {}
        t = threading.Thread(target=lambda: got.update(r=self.asking.ask({"project": "ABC", "question": "What is open?"})), daemon=True)
        t.start()
        self.assertTrue(self.provider.at_door.wait(10))
        self.assertEqual(self.post({"id": "mail", "on": False})[0], 200)       # the question is marked but has not started
        self.provider.door.set()
        status, answer = self.finish(t, got)
        self.assertEqual((status, answer["ok"], answer["message"]), (200, False, ask.STOPPED))
        self.assertFalse(self.provider.entered.is_set())                 # it never reached the provider's work
        self.assertEqual(self.asking.runs, [])

    def test_off_for_a_question_not_yet_at_the_provider_does_not_stop_the_one_that_is(self):
        t, got = self.running()                                          # the first holds the provider, given mail and teams
        self.assertEqual(self.post({"id": "calendar", "on": True})[0], 200)
        self.provider.door = threading.Event()
        self.addCleanup(self.provider.door.set)
        t2 = threading.Thread(target=lambda: self.asking.ask({"project": "ABC", "question": "And?"}), daemon=True)
        t2.start()                                                       # the second, given calendar too, waits before the provider
        self.assertTrue(self.provider.at_door.wait(10))
        self.assertEqual(self.post({"id": "calendar", "on": False})[0], 200)
        self.assertEqual(self.provider.stopped, 0)                       # only the second held calendar; the first is not its to end
        self.provider.release.set()
        self.provider.door.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)
        t2.join(10)

    def test_stop_off_says_true_when_any_question_was_stopped(self):
        t, got = self.running()
        extra = ask_service.Run("ABC", ("mail",))
        extra.cancel.is_set()                                            # a second entry that has started too: the provider has nothing more to stop for it
        self.asking.runs.append(extra)
        self.assertEqual(self.service.change_connectors({"id": "mail", "on": False})[0], 200)      # not through the route: the answer is read here
        self.assertIs(self.asking.stop_off(), True)
        self.assertTrue(extra.cancel.is_set())
        self.assertEqual(self.finish(t, got)[1]["message"], ask.STOPPED)
        self.asking.runs.remove(extra)

    def test_a_provider_that_cannot_stop_reports_nothing_stopped(self):
        t, got = self.running()
        self.provider.stop = None
        self.assertEqual(self.service.change_connectors({"id": "mail", "on": False})[0], 200)
        self.assertIs(self.asking.stop_off(), False)
        self.provider.release.set()
        self.finish(t, got)

    def test_an_undo_that_returns_a_connector_to_off_stops_the_question(self):
        self.post({"id": "mail", "on": False})
        step = self.post({"id": "mail", "on": True})[1]["apply_id"]
        t, got = self.running()                                          # mail is On again and given to this question
        status, body = self.post({"undo": step})                         # the undo puts mail back to Off
        self.assertEqual((status, body["connectors"][0]["on"]), (200, False), body)
        self.assertEqual(self.finish(t, got)[1]["message"], ask.STOPPED)
        self.assertEqual(self.provider.stopped, 1)

    def test_an_undo_to_on_or_to_off_of_another_connector_stops_nothing(self):
        off = self.post({"id": "teams", "on": False})[1]["apply_id"]
        t, got = self.running()                                          # given mail only
        self.assertEqual(self.post({"undo": off})[0], 200)               # teams back On
        self.assertEqual(self.provider.stopped, 0)
        cal = self.post({"id": "calendar", "on": True})[1]["apply_id"]
        self.assertEqual(self.post({"undo": cal})[0], 200)               # calendar back to Off, never given to this question
        self.assertEqual(self.provider.stopped, 0)
        self.provider.release.set()
        self.assertEqual(self.finish(t, got)[1]["ok"], True)

    def test_nothing_is_stopped_when_nothing_is_running(self):
        self.assertIs(self.asking.stop_off(), False)
        self.assertEqual(self.asking.runs, [])


if __name__ == "__main__":
    unittest.main()

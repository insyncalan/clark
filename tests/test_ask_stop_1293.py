"""Row 1293 line 7: a Stop that comes before the provider starts ends the question, and nothing is sent.

Run: python3 dev/run_tests.py test_ask_stop_1293
The service is called directly with a stub provider; fictional data only (tests/_publish_fixture.py).
"""
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import _publish_fixture as plant
from clark import ask, ask_data, ask_service

CODE = "PUB"


class Recording(ask.StubProvider):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.cancels = []

    honours_cancel = True                        # as ask_claude.py does: a request that is already cancelled is ended before anything is sent
    inside = None                                # a function called from inside the provider (a Stop pressed there)

    def ask(self, request):
        self.cancels.append(request.cancel)
        if self.honours_cancel and request.cancel.is_set():
            return ask.Failure(ask.STOPPED)
        if self.inside:
            self.inside()
        return super().ask(request)


class StopBeforeTheProvider(unittest.TestCase):
    def setUp(self):
        d = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, d, True)
        self.provider = Recording(reply="The plan is on track.\nCITE: P1")
        self.service = ask_service.AskService(plant.build_db(d / "clark.db"), self.provider, [])

    def question(self):
        return self.service.ask({"project": CODE, "question": "What is the state of the plan?"})

    def test_the_request_carries_a_cancel_event_that_is_not_set(self):
        status, got = self.question()
        self.assertEqual((status, got["ok"]), (200, True))
        self.assertEqual(len(self.provider.cancels), 1)
        self.assertIsInstance(self.provider.cancels[0], threading.Event)
        self.assertFalse(self.provider.cancels[0].is_set())

    def test_two_questions_get_two_events(self):
        self.question()
        self.question()
        self.assertIsNot(self.provider.cancels[0], self.provider.cancels[1])

    def test_a_stop_during_the_data_read_sends_nothing(self):
        real = ask_data.project_data
        seen = []

        def read_then_stop(*a, **k):
            seen.append(self.service.stop())            # the person presses Stop while the data is read
            return real(*a, **k)

        with mock.patch.object(ask_data, "project_data", read_then_stop):
            status, got = self.question()
        self.assertEqual(seen[0][1]["stopped"], True)
        self.assertEqual((status, got["ok"], got["code"], got["message"]), (200, False, "no_answer", ask.STOPPED))
        self.assertEqual(self.provider.sent, [], "nothing left the machine")
        self.assertEqual(self.provider.cancels, [])

    def test_a_stop_with_no_question_still_says_nothing_is_running(self):
        self.assertEqual(self.service.stop()[1]["stopped"], False)
        self.question()
        self.assertEqual(self.service.stop()[1]["stopped"], False, "the finished question left nothing behind")
        self.assertEqual(self.service.cancels, set())

    def test_a_stop_after_one_question_does_not_cancel_the_next(self):
        self.service.stop()
        status, got = self.question()
        self.assertTrue(got["ok"])
        self.assertFalse(self.provider.cancels[0].is_set())


    def stop_inside(self, name, after_data=False):
        real, read = getattr(self.service, name), []
        real_data = ask_data.project_data

        def seen_data(*a, **k):
            read.append(1)
            return real_data(*a, **k)

        def stop_then(*a, **k):
            if read or not after_data:
                self.service.stop()
            return real(*a, **k)

        return mock.patch.object(self.service, name, stop_then), mock.patch.object(ask_data, "project_data", seen_data)

    def reaches_the_provider_cancelled(self, name, after_data):
        patch_service, patch_data = self.stop_inside(name, after_data)
        with patch_service, patch_data:
            status, got = self.question()
        self.assertTrue(self.provider.cancels and self.provider.cancels[-1].is_set(), "the provider is handed a cancelled request")
        self.assertEqual((status, got["ok"], got["message"]), (200, False, ask.STOPPED), "the question itself ends as stopped")
        self.assertEqual(self.provider.sent, [], "nothing left the machine")

    def test_a_stop_after_the_data_check_but_before_the_run_is_recorded_reaches_the_provider_cancelled(self):
        self.reaches_the_provider_cancelled("enabled", True)        # the gate is asked again just after the data check, before the run is recorded

    def test_a_stop_once_the_run_is_recorded_reaches_the_provider_cancelled(self):
        self.reaches_the_provider_cancelled("connectors_now", False)    # asked after the run is recorded, before the provider


    def test_a_stop_on_the_way_into_the_provider_reaches_it_cancelled(self):
        real = ask.ask_provider

        def stop_then_ask(*a, **k):
            self.service.stop()                          # after the run is recorded and checked, just before the provider is called
            return real(*a, **k)

        with mock.patch.object(ask, "ask_provider", stop_then_ask):
            status, got = self.question()
        self.assertTrue(self.provider.cancels and self.provider.cancels[-1].is_set(), "the provider is handed a cancelled request")
        self.assertEqual((status, got["ok"], got["message"]), (200, False, ask.STOPPED), "the question itself ends as stopped")
        self.assertEqual(self.provider.sent, [], "nothing left the machine")


if __name__ == "__main__":
    unittest.main()

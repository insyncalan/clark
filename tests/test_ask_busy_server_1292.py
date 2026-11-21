"""Row 1292 item 15, the server side of 'Working. You can close this: it carries on.'

A question that lost its client (a reload: no Stop call) goes on running and still holds the one-at-a-time lock, so a second question
is told BUSY; once the first finishes a new question is accepted again.
"""
import sys
import threading
import time
import unittest
from dataclasses import replace

import test_ask_claude as T
from clark import ask, ask_claude as ac

# the fake model, but its slow mode waits for a file instead of sleeping 60 seconds
GATED = T.FAKE.replace('if mode == "slow":\n    time.sleep(60)',
                       'if mode == "slow":\n    while not os.path.exists(os.path.join(here, "go")):\n        time.sleep(0.05)')


class Carries(T.Fake):
    def setUp(self):
        super().setUp()
        assert GATED != T.FAKE
        self.cmd.write_text(GATED.replace("@PYTHON@", sys.executable), encoding="utf-8")
        self.addCleanup(self.release)

    def release(self):
        (self.bin / "go").write_text("", encoding="utf-8")

    def wait_for(self, what, seconds=15):
        deadline = time.monotonic() + seconds
        while not what() and time.monotonic() < deadline:
            time.sleep(0.05)
        return what()

    def test_a_question_whose_client_went_away_still_holds_the_lock_until_it_ends(self):
        self.mode("slow")
        provider = self.make(limit=30)
        got = []
        gone = threading.Thread(target=lambda: got.append(provider.ask(self.request("First?"))), daemon=True)
        gone.start()                                           # the caller is dropped here: nothing waits on it and Stop is never called
        self.assertTrue(self.wait_for(lambda: self.seen() is not None), "the first question reached the model")
        second = provider.ask(self.request("Second?"))
        self.assertEqual(second, ask.Failure(ac.BUSY))
        self.assertEqual(second.message, "Another question is being answered. Wait for it, or press Stop.")
        self.assertTrue(gone.is_alive(), "the first question is still running")
        self.assertEqual(got, [], "and has not ended")
        self.assertEqual(provider.ask(replace(self.request("Third?"), owner=object())), ask.Failure(ac.BUSY), "still busy a moment later")
        self.mode("ok")
        self.release()
        gone.join(15)
        self.assertFalse(gone.is_alive(), "the first question ended")
        self.assertEqual(len(got), 1)
        self.assertNotEqual(got[0], ask.Failure(ac.BUSY))
        again = provider.ask(self.request("Fourth?"))
        self.assertNotEqual(again, ask.Failure(ac.BUSY), "a new question is accepted once the first has ended")
        self.assertNotIsInstance(again, ask.Failure)


if __name__ == "__main__":
    unittest.main()

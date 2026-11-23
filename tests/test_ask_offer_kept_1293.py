"""Row 1293 AP8: a dry run that fails leaves the reply usable (the reply is not used up by a busy database), and a busy save keeps the offer.

Run: python3 dev/run_tests.py test_ask_offer_kept_1293
Quick tier: a real server on a free port, a stub provider (the same set-up as test_ask_retry_1293). Fictional data only.
"""
import unittest

from test_ask_retry_1293 import Retry as Base


class OfferKept(Base):
    def test_a_failed_dry_run_leaves_the_reply_usable(self):
        reply = self.reply()
        for _ in range(2):                           # it can fail more than once and still be usable
            self.down["dry"] = True
            status, body = self.dry(reply)
            self.assertEqual((status, body["plans"][0]["code"]), (200, "busy"))
        self.down["dry"] = False
        status, body = self.dry(reply)
        self.assertEqual((status, body["ok"], body["plans"][0]["ok"]), (200, True, True), body)
        offer = body["plans"][0]["offer"]
        self.down["save"] = True
        self.assertEqual(self.apply(offer)[1]["code"], "busy")
        self.down["save"] = False
        self.assertEqual(self.apply(offer)[0], 200, "the offer survived the busy save")
        self.assertEqual(self.status_of(self.action), "Closed")


del Base                                             # not collected twice

if __name__ == "__main__":
    unittest.main()

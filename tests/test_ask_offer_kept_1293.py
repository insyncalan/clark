"""Row 1293 (AP8 of the old ticket, AP3 here): a dry run that failed leaves the reply usable. The dry run is kept until it works: a data
fault or a busy store on the first try does not use the reply up, a second try works, and only a dry run that worked is made once.

Run: python3 dev/run_tests.py test_ask_offer_kept_1293
Fictional data only; the answer comes from a stub provider.
"""
import unittest

from test_ask_retry_1293 import Retry as Base


class OfferKept(Base):
    def test_a_failed_dry_run_leaves_the_reply_usable(self):
        reply = self.reply()
        self.down["dry"] = True
        status, body = self.dry(reply)
        self.assertEqual((status, body["plans"][0]["code"]), (200, "busy"), "the first try fails")
        self.down["dry"] = False
        status, body = self.dry(reply)
        self.assertEqual((status, body["ok"]), (200, True), "the same reply works on the second try: " + str(body))
        self.assertEqual(self.dry(reply)[1]["code"], "shown_already", "a dry run that worked is made once")


del Base      # the retry tests are run by their own file, not again here

if __name__ == "__main__":
    unittest.main()

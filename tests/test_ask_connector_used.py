"""Row 1306 C4: the Used line and the provenance flag reach the answer (data only; no connector content is kept or sent on).

Run: python3 dev/run_tests.py test_ask_connector_used
Without a connector hook the answer is exactly what it was. With one, the results are screened (ask_connector_screen) and the answer
carries `used` (the line, the parts used, the parts not used with the reason, and a `from_connector` flag per part used) and the
line also follows the answer as a note. Fictional data only.
"""
import unittest

from test_ask_route import Base, ask_service


class Hooked(Base):
    def hook(self, results):
        self.calls = []

        def run(question):
            self.calls.append(question)
            return results
        self.service.connectors = run

    def got(self):
        status, body = self.question()
        self.assertEqual(status, 200, body)
        return body


class TheUsedLine(Hooked):
    def test_no_hook_changes_nothing(self):
        body = self.got()
        self.assertNotIn("used", body)
        self.assertIsNone(ask_service.AskService(self.db, self.provider, []).connectors)

    def test_hook_returning_nothing_adds_nothing(self):
        self.hook([])
        self.assertNotIn("used", self.got())

    def test_a_used_part_is_named_and_flagged(self):
        self.hook([("outlook_email_search", "Subject: Lunch on Friday")])
        body = self.got()
        self.assertEqual(body["used"]["used"], ["Mail"])
        self.assertEqual(body["used"]["sources"], [{"part": "Mail", "from_connector": True}])
        self.assertIn(body["used"]["line"], body["notes"])
        self.assertNotIn("Lunch", str(body), "no connector content comes back")

    def test_a_refused_result_is_listed_as_not_used_and_never_flagged(self):
        self.hook([("outlook_send_mail", "x"), ("outlook_email_search", "bad‮text")])
        body = self.got()
        self.assertEqual(body["used"]["used"], [])
        self.assertEqual(body["used"]["sources"], [])
        self.assertTrue(body["used"]["not_used"])
        self.assertNotIn("bad", str(body))

    def test_a_hook_that_raises_is_not_used(self):
        def boom(_q):
            raise RuntimeError("secret detail")
        self.service.connectors = boom
        body = self.got()
        self.assertNotIn("used", body)
        self.assertNotIn("secret detail", str(body))

    def test_asking_off_never_calls_the_hook(self):
        self.hook([("outlook_email_search", "x")])
        self.set_switch(False)
        status, _ = self.question()
        self.assertEqual(status, 409)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()

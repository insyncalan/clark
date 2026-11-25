"""Row 1293 (AP11 of the old ticket, AP4 here): today's date is in the request, and an overdue question asked twice on a fixed clock sends
the same request twice.

Run: python3 dev/run_tests.py test_ask_date_1293
A stub provider keeps what it was sent; nothing calls a model. Fictional data only.
"""
import unittest
from unittest import mock

import test_ask_route as route
from clark import milestones


class Date(route.Base):
    def sent(self, day, question="What is overdue?"):
        before = len(self.provider.sent)
        with mock.patch.object(milestones, "today", return_value=day):
            status, got = self.question(question)
        self.assertEqual((status, len(self.provider.sent)), (200, before + 1), got)
        return self.provider.sent[-1]

    def test_the_request_has_today_and_an_overdue_question_repeats(self):
        first = self.sent("2026-11-17")
        self.assertIn("Today is 17-11-2026.", first, "today's date, DD-MM-YYYY, is in the request")
        self.assertEqual(self.sent("2026-11-17"), first, "the same question on the same day sends the same request")
        later = self.sent("2026-11-18")
        self.assertIn("Today is 18-11-2026.", later)
        self.assertNotIn("17-11-2026", later, "the date comes from the clock")


if __name__ == "__main__":
    unittest.main()

"""Row 1293 AP11: every question carries today's date, and on a fixed clock an overdue question puts the same request on the wire twice.

Run: python3 dev/run_tests.py test_ask_date_1293
Quick tier: a real server, a stub provider; nothing calls a model. Fictional data only.
"""
import unittest
from unittest import mock

import test_ask_route as route

from clark import milestones


class Date(route.Base):
    def sent(self, day):
        before = len(self.provider.sent)
        with mock.patch.object(milestones, "today", return_value=day):
            status, got = self.question("What is overdue?")
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(len(self.provider.sent), before + 1)
        return self.provider.sent[-1]

    def test_the_request_has_today_and_an_overdue_question_repeats(self):
        first, second = self.sent("2026-11-17"), self.sent("2026-11-17")
        self.assertIn("Today is 17-11-2026.", first)
        self.assertEqual(first, second, "the same question on a fixed clock is the same request")
        self.assertIn("Today is 24-11-2026.", self.sent("2026-11-24"), "the line comes from the clock")


if __name__ == "__main__":
    unittest.main()

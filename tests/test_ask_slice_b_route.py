"""#1293 slice B through POST /api/ask: the chat's item IDs are added to what ranks the project's data, today's date and the
rows-sent lines reach the request, and the project's share of the budget is the one the service names.

Run: python3 dev/run_tests.py test_ask_slice_b_route
Fictional data only; a stub provider records what would be sent.
"""
import re
import unittest
from unittest import mock

import test_ask_route as route
from clark import ask_data, ask_service


class Through(route.Base):
    def test_the_chats_ids_join_the_question_that_ranks_the_data(self):
        earlier = [{"role": "user", "text": "tell me about ABC-A-001"}, {"role": "assistant", "text": "ABC-A-001 is open; also ABC-R-007"}]
        with mock.patch.object(ask_data, "project_data", wraps=ask_data.project_data) as spy:
            status, got = self.question("and when is it due?", earlier=earlier)
        self.assertEqual(status, 200, got)
        (_store, code, ranked, budget), _kw = spy.call_args
        self.assertEqual((code, ranked), (route.CODE, "and when is it due? ABC-A-001 ABC-R-007"))
        self.assertEqual(budget, ask_service.PROJECT_SHARE)

    def test_no_earlier_turns_leaves_the_question_alone(self):
        with mock.patch.object(ask_data, "project_data", wraps=ask_data.project_data) as spy:
            self.question("what is late?")
        self.assertEqual(spy.call_args[0][2], "what is late?")

    def test_the_request_names_today_as_a_day(self):
        status, got = self.question()
        self.assertEqual(status, 200, got)
        head = self.provider.sent[-1].split("QUESTION")[0]
        self.assertRegex(head, r"Today is \d\d-\d\d-\d{4}\.")

    def test_a_share_too_small_for_every_row_says_how_many_were_sent(self):
        with mock.patch.object(ask_service, "PROJECT_SHARE", 600):
            status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        head = self.provider.sent[-1].split("QUESTION")[0]
        self.assertTrue(re.search(r"\w: \d+ of \d+ rows sent", head), head)
        self.assertIn("give no totals", head)

    def test_a_whole_project_sent_has_no_rows_sent_line(self):
        self.question("what is late?")
        self.assertNotIn("rows sent", self.provider.sent[-1].split("QUESTION")[0])


if __name__ == "__main__":
    unittest.main()

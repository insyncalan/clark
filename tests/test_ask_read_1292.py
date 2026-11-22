"""Row 1292 (reopened): the ask reply says how much of the project it read, for the line under an answer.

Run: python3 dev/run_tests.py test_ask_read_1292
Quick tier: a real server on a free port, a stub provider, no Chrome. `read` is {"work_items", "milestones", "use_cases", "as_at"}:
the rows SENT with the question (a kind sent in part counts what was sent), work items being actions, risks and issues, and decisions;
`as_at` is the report's day as DD-MM-YYYY, or "" when it is not a day. A failed question carries none.
"""
import unittest

import test_ask_route as R


class Read(R.Base):
    def ask_with(self, reply="Fine.", q="What about the plan?"):
        self.provider.reply = reply
        status, got = self.question(q)
        self.assertEqual(status, 200, got)
        return got

    def test_the_reply_carries_what_was_read(self):
        got = self.ask_with()
        self.assertEqual(set(got["read"]), {"work_items", "milestones", "use_cases", "as_at"})
        for key in ("work_items", "milestones", "use_cases"):
            self.assertIsInstance(got["read"][key], int)
            self.assertFalse(isinstance(got["read"][key], bool))
        self.assertGreater(got["read"]["work_items"], 0, "the demo project holds work items")

    def test_work_items_are_the_actions_risks_and_decisions_sent(self):
        from clark import ask_data
        data = ask_data.ProjectData((), {}, 0, 0, "17-11-2026", (("actions", 5, 9), ("raid", 2, 2), ("decisions", 1, 1), ("milestones", 3, 4), ("use_cases", 0, 2)))
        self.assertEqual(ask_data.read_counts(data), {"work_items": 8, "milestones": 3, "use_cases": 0, "as_at": "17-11-2026"})

    def test_an_unreadable_day_is_empty_and_nothing_is_invented(self):
        from clark import ask_data
        data = ask_data.ProjectData((), {}, 0)
        self.assertEqual(ask_data.read_counts(data), {"work_items": 0, "milestones": 0, "use_cases": 0, "as_at": ""})

    def test_a_failed_question_carries_no_read(self):
        self.provider.failure = "Took too long."
        status, got = self.question("What about the plan?")
        self.assertNotIn("read", got)


if __name__ == "__main__":
    unittest.main()

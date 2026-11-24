"""Row 1292 (reopened): the ask reply says how much of the project it read, for the line under an answer.

Run: python3 dev/run_tests.py test_ask_read_1292
Quick tier: a real server on a free port, a stub provider, no Chrome. `read` is {"work_items", "milestones", "use_cases", "as_at"}:
the rows SENT with the question (a kind sent in part counts what was sent), work items being actions, risks and issues, and decisions;
`as_at` is the report's day as DD-MM-YYYY, or "" when it is not a day. A failed question carries none.
"""
import unittest

import test_ask_route as R


def ask_data_counts(data):
    from clark import ask_data
    return ask_data.read_counts(data)


class Read(R.Base):
    def ask_with(self, reply="Fine.", q="What about the plan?"):
        self.provider.reply = reply
        status, got = self.question(q)
        self.assertEqual(status, 200, got)
        return got

    def test_the_reply_carries_what_was_read(self):
        got = self.ask_with()
        self.assertEqual(set(got["read"]), {"work_items", "milestones", "use_cases", "as_at", "items", "left_out"})
        for key in ("work_items", "milestones", "use_cases", "items", "left_out"):
            self.assertIsInstance(got["read"][key], int)
            self.assertFalse(isinstance(got["read"][key], bool))
        self.assertGreater(got["read"]["work_items"], 0, "the demo project holds work items")

    def test_work_items_are_the_actions_risks_and_decisions_sent(self):
        from clark import ask_data
        data = ask_data.ProjectData((), {}, 0, 0, "17-11-2026", (("actions", 5, 9), ("raid", 2, 2), ("decisions", 1, 1), ("milestones", 3, 4), ("use_cases", 0, 2)))
        self.assertEqual(ask_data.read_counts(data), {"work_items": 8, "milestones": 3, "use_cases": 0, "as_at": "17-11-2026", "items": 11, "left_out": 7})      # row 1294: 4 + 1 + 2 (actions, milestones, use cases cut)

    def test_an_unreadable_day_is_empty_and_nothing_is_invented(self):
        from clark import ask_data
        data = ask_data.ProjectData((), {}, 0)
        self.assertEqual(ask_data.read_counts(data), {"work_items": 0, "milestones": 0, "use_cases": 0, "as_at": "", "items": 0, "left_out": 0})

    def test_items_are_every_row_sent_and_left_out_is_every_row_cut_whatever_the_kind(self):      # row 1294: "N items read, M left out"
        from clark import ask_data
        data = ask_data.ProjectData((), {}, 0, 0, "", (("actions", 5, 9), ("workstreams", 2, 7), ("raid", 2, 2)))
        got = ask_data.read_counts(data)
        self.assertEqual((got["items"], got["left_out"]), (9, 9))
        whole = ask_data.read_counts(ask_data.ProjectData((), {}, 0, 0, "", (("actions", 4, 4),)))
        self.assertEqual((whole["items"], whole["left_out"]), (4, 0), "nothing cut: nothing left out")

    def test_a_project_cut_by_a_tight_budget_reports_what_was_cut(self):
        import test_ask_1367 as T
        got, _ = T.read(budget=400)
        counts = ask_data_counts(got)
        self.assertGreater(counts["left_out"], 0)
        self.assertEqual(counts["items"] + counts["left_out"], sum(total for _k, _n, total in got.counts), "read and left out make the project's rows")
        whole, _ = T.read()
        self.assertEqual(ask_data_counts(whole)["left_out"], 0)

    def test_a_failed_question_carries_no_read(self):
        self.provider.failure = "Took too long."
        status, got = self.question("What about the plan?")
        self.assertNotIn("read", got)


if __name__ == "__main__":
    unittest.main()

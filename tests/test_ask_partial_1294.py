"""Row 1294 (rule 4): an answer from a project that was cut says it is partial when the question asks for a count, a total or an overview.

Run: python3 dev/run_tests.py test_ask_partial_1294
Quick tier (no Chrome) for the words, the trigger and the route; the browser tier draws the sentence at 1400 and 900 px.
"""
import unittest
from dataclasses import replace
from unittest import mock

import test_ask_route as R
from clark import ask_data

CUT = (("actions", 5, 9), ("raid", 2, 2))      # 7 read, 4 left out
WHOLE = (("actions", 9, 9), ("raid", 2, 2))
SAYS = "This answer is partial: it covers only the 7 items that were read, not the 4 that were left out."


class Words(unittest.TestCase):
    def test_the_ruled_sentence_with_the_real_numbers(self):
        self.assertEqual(ask_data.partial_answer("How many risks are open?", CUT), SAYS)

    def test_one_read_is_singular_and_one_left_out_is_was(self):
        self.assertEqual(ask_data.partial_answer("Give me an overview", (("actions", 1, 5),)),
                         "This answer is partial: it covers only the 1 item that was read, not the 4 that were left out.")
        self.assertEqual(ask_data.partial_answer("Give me an overview", (("actions", 3, 4),)),
                         "This answer is partial: it covers only the 3 items that were read, not the 1 that was left out.")

    # one hit and one miss for each word or phrase of the ruled list: whole words only, so a longer word that contains it is a miss
    TABLE = (
        ("how many", "How many risks are open?", "How manygood risks are open?"),
        ("how much", "How much is left?", "How muchness is left?"),
        ("how often", "How often is it late?", "How oftenly is it late?"),
        ("count", "Count the decisions", "Who is the account owner?"),
        ("count (country)", "What counts as late?", "Which country is the client in?"),
        ("total", "What is the total of open risks?", "Is it totally late?"),
        ("number of", "What is the number of issues?", "What is the numbering of issues?"),
        ("overview", "Give an overview of the project", "Is there an overviewer?"),
        ("summary", "SUMMARY please", "Is there a summaryless page?"),
        ("summarise", "Summarise the project", "Summarisers are not asked"),
        ("summarize", "Please summarize it", "Summarizer is not asked"),
        ("average", "What is the average delay?", "Who is the averageish owner?"),
        ("percent", "What percent is done?", "What percentless is done?"),
        ("per cent", "What per cent is done?", "What per centre is done?"),
        ("altogether", "What is open altogether?", "Is it altogetherness?"),
        ("in all", "What is there in all?", "What is there in allowance?"),
        ("all of the", "Are all of the risks closed?", "All of there are risks"),
        ("breakdown", "A breakdown by owner", "A breakdownless page"),
        ("list all", "List all risks", "Is it a list allowed?"),
        ("list every", "List every action", "Is it a list everywhere?"),
        ("percentage", "What percentage is done?", "Is there a percentageless page?"),
        ("tally", "What is the tally of open risks?", "Is a tallyman asked?"),
        ("sum", "What is the sum of the budgets?", "Did he assume it was consumed?"),
        ("how large", "How large is the backlog?", "How largely is it late?"),
        ("figures", "Give me the figures for all risks", "Is it a configured page?"),
        ("stats", "Any stats on the issues?", "Is it a statsman?"),
        ("all risks", "What is the owner of all the risks?", "Who is the allrisks person?"),
        ("all items", "Is anything late in all open items?", "Is it small items?"),
        ("every risk", "Is every risk closed?", "Is it everyriskless?"),
        ("more than N", "Are there more than 10 open?", "Is it more thank you?"),
        ("at least N", "Are at least 3 late?", "Is it at least a risk?"),
    )

    def test_each_word_and_phrase_has_one_hit_and_one_miss(self):
        for name, hit, miss in self.TABLE:
            with self.subTest(word=name):
                self.assertEqual(ask_data.partial_answer(hit, CUT), SAYS, "hit: " + hit)
                self.assertEqual(ask_data.partial_answer(miss, CUT), "", "miss: " + miss)

    def test_plurals_of_count_total_overview_average_percent_summary_breakdown_hit(self):
        for q in ("Which counts are there?", "Show totals", "Show the overviews", "Show the averages", "Give percents", "Give the summaries", "Give the breakdowns", "Give the percentages", "Show the tallies", "Show the sums"):
            with self.subTest(q=q):
                self.assertEqual(ask_data.partial_answer(q, CUT), SAYS)

    def test_case_and_spacing_do_not_matter(self):
        for q in ("HOW   MANY are open?", "how\nmany are open?", "PER  CENT done?", "List   ALL risks", "how\nlarge is it?", "HOW   LARGE is it?"):
            with self.subTest(q=q):
                self.assertEqual(ask_data.partial_answer(q, CUT), SAYS)

    def test_nothing_left_out_never_shows_it_whatever_the_question(self):
        for _name, hit, _miss in self.TABLE:
            with self.subTest(q=hit):
                self.assertEqual(ask_data.partial_answer(hit, WHOLE), "")

    def test_a_question_about_one_thing_does_not(self):
        for q in ("Who owns ABC-A-001?", "When is the next milestone?", "What is overdue?", "Is the account of the client right?"):
            with self.subTest(q=q):
                self.assertEqual(ask_data.partial_answer(q, CUT), "")

    def test_nothing_cut_or_no_counts_or_a_bad_question_says_nothing(self):
        self.assertEqual(ask_data.partial_answer("How many risks are open?", WHOLE), "")
        self.assertEqual(ask_data.partial_answer("How many risks are open?", ()), "")
        self.assertEqual(ask_data.partial_answer(None, CUT), "")
        self.assertEqual(ask_data.partial_answer("", CUT), "")


class Route(R.Base):
    def ask_cut(self, q, counts=CUT):
        real = ask_data.project_data
        with mock.patch.object(ask_data, "project_data", lambda *a, **k: replace(real(*a, **k), counts=counts)):
            status, got = self.question(q)
        self.assertEqual(status, 200, got)
        return got

    def test_a_count_question_on_a_cut_project_carries_the_sentence_with_the_answer(self):
        got = self.ask_cut("How many risks are open?")
        self.assertIn(SAYS, got["notes"])
        self.assertEqual(got["read"]["items"], 7)
        self.assertEqual(got["read"]["left_out"], 4)

    def test_a_question_about_one_thing_or_a_whole_project_does_not(self):
        self.assertNotIn(SAYS, self.ask_cut("Who owns the first action?")["notes"])
        self.assertFalse([n for n in self.ask_cut("How many risks are open?", WHOLE)["notes"] if n.startswith("This answer is partial")])


if __name__ == "__main__":
    unittest.main()

"""Mutation killers for publish_flow.hidden_section_markers (row 1151): the exact edges of the limits. A run of exactly MIN_MARKER
characters is a marker, runs that fill the character cap exactly are all kept (the next one is not), and the real cap is the stated
one. Fictional data only.

Run: python3 dev/run_tests.py test_publish_run_marker_limits
"""
from unittest import mock

from clark import publish_flow
from test_gantt_markers import Base


class RunMarkerLimits(Base):
    def hidden(self, runs):
        self.sql("INSERT INTO report_sections (project, id, type, title, body, beside, hidden, sort_order) VALUES ('ABC',?,?,?,?,0,1,9100)",
                 ("s-lim", "text", "Title s-lim", "".join("<p>%s</p>" % r for r in runs)))
        return self.got()[1]

    def test_a_run_of_exactly_the_shortest_length_is_a_marker(self):
        edge = "Zq12" + "x" * (publish_flow.MIN_MARKER - 4)
        self.assertEqual(len(edge), publish_flow.MIN_MARKER)
        got = self.hidden([edge, edge[:-1]])
        self.assertIn(edge, got)
        self.assertNotIn(edge[:-1], got)

    def test_runs_that_fill_the_character_cap_exactly_are_all_kept(self):
        runs = ["Fill%02d" % i + "y" * 14 for i in range(8)]            # 20 characters each
        with mock.patch.object(publish_flow, "MAX_RUN_CHARS", 100):
            got = self.hidden(runs)
        kept = [r for r in runs if r in got]
        self.assertEqual(kept, runs[:5], msg="5 runs of 20 characters fill 100 exactly, the sixth does not fit")

    def test_the_real_character_cap_is_one_hundred_thousand(self):
        runs = ["L%04d" % i + "x" * 995 for i in range(200)]            # 1,000 characters each
        got = self.hidden(runs)
        self.assertEqual(len([m for m in got if len(m) == 1000]), 100)

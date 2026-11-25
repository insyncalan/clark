"""Row 1293 (AP9, DoD9): when a question had to leave rows out, the person is told how many were read and how many left out, and that a
higher size of one question in Settings reads more. Said only when something was left out; "1 item read" in the singular.

Run: python3 dev/run_tests.py test_ask_left_out_1293
Fictional data only. The command is a fake; nothing is sent anywhere.
"""
import datetime
import os
import re
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
from clark import ask, ask_data, ask_passages, ask_service, ask_words

DAY = datetime.date(2026, 11, 20)
OLD = "Left out to keep this question under the size limit"
SENTENCE = "A higher size of one question in Settings reads more."


class Said(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = plant.build_db(self.d / "clark.db")

    def notes(self, counts, passages=0):
        """The reply notes when the data says `counts` and, with `passages` above 0, that many file passages are offered with the request
        limited to two passages (so a passage cut happens)."""
        real = ask_data.project_data

        def data(*a, **k):
            return replace(real(*a, **k), counts=counts)
        service = ask_service.AskService(self.db, ask.StubProvider(reply="Fine.\nCITE: P1"), [])
        service.today = lambda: DAY
        folder = ask_passages.FolderData(passages=tuple(ask.Passage(f"f{i}.md", f"plan number {i}") for i in range(passages)), left_out=0)
        with mock.patch.object(ask_data, "project_data", data), mock.patch.object(ask_service.ask_passages, "folder_data", return_value=folder), \
                mock.patch.object(ask_service, "folder_notes", return_value=[]), mock.patch.object(ask, "MAX_PASSAGES", 2 if passages else ask.MAX_PASSAGES):
            status, got = service.ask({"project": "PUB", "question": "What is the state of the plan?"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        return got["notes"]

    def test_the_person_sees_n_read_and_m_left_out(self):
        notes = self.notes((("actions", 30, 50), ("milestones", 5, 5), ("use_cases", 2, 4)))
        self.assertIn(f"37 items read, 22 left out. {SENTENCE}", notes)
        self.assertEqual(sum(SENTENCE in n for n in notes), 1, "said once")

    def test_one_item_read_is_singular_and_zero_is_plural(self):
        self.assertIn(f"1 item read, 5 left out. {SENTENCE}", self.notes((("actions", 1, 6),)))
        self.assertIn(f"0 items read, 3 left out. {SENTENCE}", self.notes((("actions", 0, 3),)))

    def test_nothing_is_said_when_nothing_was_left_out(self):
        self.assertFalse([n for n in self.notes((("actions", 4, 4), ("milestones", 2, 2))) if SENTENCE in n or "items read" in n])
        self.assertEqual(ask_words.read_left_out(()), "")

    def test_thousands_carry_a_comma(self):
        self.assertEqual(ask_words.read_left_out((("actions", 1200, 3400),)), f"1,200 items read, 2,200 left out. {SENTENCE}")

    FULL = (("actions", 4, 4), ("milestones", 2, 2))
    CUT = (("actions", 3, 5), ("milestones", 2, 2))

    def lines(self, notes):
        return [n for n in notes if n.startswith(OLD)], [n for n in notes if SENTENCE in n]

    def test_a_cut_shows_exactly_one_left_out_line(self):
        old, new = self.lines(self.notes(self.FULL, passages=4))                  # passages cut, no rows cut: the old line only
        self.assertEqual((len(old), len(new)), (1, 0), (old, new))
        old, new = self.lines(self.notes(self.CUT))                               # rows cut, no passages cut: the new line only
        self.assertEqual((len(old), len(new)), (0, 1), (old, new))
        self.assertIn(f"5 items read, 2 left out. {SENTENCE}", new)
        old, new = self.lines(self.notes(self.FULL))                              # nothing cut: neither line
        self.assertEqual((old, new), ([], []))

    def test_a_mixed_cut_shows_each_line_once(self):
        old, new = self.lines(self.notes(self.CUT, passages=4))
        self.assertEqual((len(old), len(new)), (1, 1), (old, new))
        self.assertNotIn("items", old[0], "the passages line says only its own cut")
        self.assertNotIn("passage", new[0], "the rows line says only its own cut")
        self.assertEqual(len(re.findall(r"\d+", new[0])), 2, "N and M only")


if __name__ == "__main__":
    unittest.main()

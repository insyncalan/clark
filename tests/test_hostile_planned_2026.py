"""Hostile tests for row 1061 (Candidate becomes Planned 2026): the reader, the store step and the old word crossing.
Fictional data only.

Run: python3 dev/run_tests.py test_hostile_planned_2026
"""
import shutil
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from clark import changes, sneak, store as store_module
from clark.store import open_store
from test_sneak_milestone_usecase import DATA, NOW
from test_store_migration import version
from test_store_planned_2026_migration import STEP, flags, plant
from test_store_use_case_done_migration import make_at


def read(words):
    return sneak.read(DATA, "U-1", words, NOW)


def commitment_of(r):
    return [c["to"] for c in r.get("changes", []) if c["field"] == "commitment"]


class ReaderHostile(unittest.TestCase):
    def test_a_date_after_planned_2026_is_not_the_flag(self):
        # "planned 2026-12-01" is a date, not the word; \b matches at the hyphen
        for words in ("planned 2026-12-01", "planned 2026/12/01", "planned 2026.5"):
            self.assertEqual(commitment_of(read(words)), [], words)

    def test_the_year_is_a_whole_word_and_so_is_planned(self):
        # mutation hunt on row 1061: with no word edge after 2026 (or before planned), "planned 20261" and "replanned 2026" read as the flag
        for words in ("planned 20261", "planned 2026x", "planned 2026a", "replanned 2026", "unplanned 2026", "planned for 20267"):
            self.assertEqual(commitment_of(read(words)), [], words)
        self.assertEqual(commitment_of(read("planned 2026")), ["Planned 2026"])
        self.assertEqual(commitment_of(read("it is planned for 2026.")), ["Planned 2026"])

    def test_the_old_word_is_no_longer_read_as_a_flag(self):
        for words in ("candidate", "Candidate", "make it a CANDIDATE"):
            r = read(words)
            self.assertNotIn("Candidate", commitment_of(r), words)
            self.assertNotIn("Candidate", str(r.get("changes", [])), words)

    def test_both_years_in_one_sentence_is_refused(self):
        for words in ("planned 2026 or planned 2027", "planned for 2027, planned for 2026", "PLANNED   2026 committed"):
            self.assertEqual(read(words).get("message"), changes.UC_COMMITMENT_WORDS, words)

    def test_odd_input_never_raises(self):
        for words in ("", "   ", "planned 2026" * 400, "planned 2026", "planned 2026\x00", "planned\n2026", "ṗlanned 2026", "planned ２０２６"):
            r = read(words)
            self.assertIn("ok", r)
            self.assertFalse(r["ok"] and commitment_of(r) == ["Planned 2027"], words)

    def test_repeating_the_same_word_twice_is_one_flag_or_a_refusal(self):
        r = read("planned 2026, planned for 2026")
        self.assertTrue(r["ok"] or r["message"] == changes.UC_COMMITMENT_WORDS)


class StepHostile(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_only_the_exact_old_word_is_rewritten(self):
        path = make_at(self.dir, STEP - 1)
        odd = ["candidate", "Candidate ", " Candidate", "Candidate​", "CANDIDATE", "", "Planned 2026", "Candidate"]
        plant(path, odd)
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(flags(path), odd[:-2] + ["Planned 2026", "Planned 2026"])

    def test_many_rows_and_archived_rows(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path), isolation_level=None)
        for n, flag in enumerate(["Candidate"] * 150 + ["Committed"] * 10, 1):
            con.execute("INSERT INTO use_cases (id, project, ref, title, status, headline, standing, sort_order, client_visible, archived, source, updated_at, commitment) "
                        "VALUES (?, 'ABC', ?, ?, 'On track', 'h', '<p>s</p>', ?, 1, ?, 'test', '2026-10-30 09:00:00', ?)",
                        ("ABC-U-%03d" % n, str(n), "Case %d" % n, n, n % 2, flag))
        con.close()
        open_store(path, onedrive_roots=[]).close()
        got = flags(path)
        self.assertEqual(got.count("Candidate"), 0)
        self.assertEqual(got.count("Planned 2026"), 150)
        self.assertEqual(got.count("Committed"), 10)

    def test_a_file_two_steps_behind_crosses_cleanly(self):
        path = make_at(self.dir, STEP - 2)
        plant(path, ["Candidate", None])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
        self.assertEqual(flags(path), ["Planned 2026", None])

    def test_the_step_called_directly_twice_and_out_of_order_is_harmless(self):
        path = make_at(self.dir, STEP - 1)
        plant(path, ["Candidate", "Committed"])
        con = sqlite3.connect(str(path), isolation_level=None)
        store_module.migrate_commitment_planned_2026(con)
        store_module.migrate_commitment_planned_2026(con)
        con.close()
        self.assertEqual(flags(path), ["Planned 2026", "Committed"])
        open_store(path, onedrive_roots=[]).close()
        self.assertEqual(flags(path), ["Planned 2026", "Committed"])

    def test_the_words_have_no_old_word_left(self):
        self.assertNotIn("Candidate", store_module.COMMITMENTS)
        self.assertNotIn("Candidate", changes.UC_COMMITMENTS)


if __name__ == "__main__":
    unittest.main()

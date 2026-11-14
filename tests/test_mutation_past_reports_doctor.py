"""Killer tests for the survivors of a mutation sweep over past_reports.py and doctor.py (and the doctor's use of the launcher's
refusal words, row 1030). Each test names the small change it was written to catch. Fictional data only; no browser.

Run: python3 dev/run_tests.py test_mutation_past_reports_doctor
"""
import hashlib
import sqlite3
import sys
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _paths import ROOT
from _demo import USER
from clark import doctor, launch, past_reports, published_copies
from clark import platform as pl
from test_doctor import DoctorCase
from test_past_reports import Base


class PastReportsEdges(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)

    def edit(self, sql, *args):
        """Change a row the way the store never would (its guard is dropped on this test copy only)."""
        con = sqlite3.connect(str(self.db))
        try:
            con.execute("DROP TRIGGER publications_number_fixed")
            con.execute(sql, args)
            con.commit()
        finally:
            con.close()

    def test_a_refusal_says_ok_false(self):
        status, body = self.past.listing("no")
        self.assertEqual((status, body["ok"]), (400, False))

    def test_the_connection_is_read_only(self):
        con = self.past._con()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute("DELETE FROM publications")
        finally:
            con.close()

    def test_an_unreadable_database_is_a_500_for_the_list_and_for_open(self):
        bad = self.root / "bad.db"
        bad.write_bytes(b"this is not a database" * 100)
        past = past_reports.PastReports(bad)
        self.assertEqual(past.listing("PUB")[0], 500)
        self.assertEqual(past.visit("PUB", 1)[0], 500)
        self.assertEqual(past.visit("PUB", 1)[1]["code"], "db_unreadable")

    def test_a_week_that_is_not_a_day_is_left_out_of_the_list(self):
        self.publish(now="2026-11-02")
        self.edit("UPDATE publications SET week_ending = 'next tuesday'")
        self.assertIsNone(self.past.listing("PUB")[1]["publications"][0]["week"])

    def test_open_with_a_code_that_is_not_text_is_a_400(self):
        for code in (None, 7, b"PUB"):
            with self.subTest(code=code):
                self.assertEqual(self.past.visit(code, 1)[0], 400)

    def test_a_word_copy_is_404_not_kept(self):
        word = self.root / "report.docx"
        word.write_bytes(b"PK word")
        number = self.store.log_publication("PUB", word, "2026-10-23", hashlib.sha256(b"PK word").hexdigest(), USER, word=1)
        number = self.store.con.execute("SELECT number FROM publications WHERE word = 1").fetchone()[0]
        status, got = self.past.visit("PUB", number)
        self.assertEqual((status, got["code"]), (404, "not_kept"))

    def test_a_kept_file_that_is_not_a_clark_page_is_409(self):
        done, body = self.publish()
        path = self.copies / f"PUB-{done['number']}.html"
        junk = b"not a page clark makes"
        path.chmod(0o644)
        path.write_bytes(junk)
        self.edit("UPDATE publications SET file_sha256 = ? WHERE number = ?", hashlib.sha256(junk).hexdigest(), done["number"])
        status, got = self.past.visit("PUB", done["number"])
        self.assertEqual((status, got["code"]), (409, "copy_changed"))

    def test_the_address_is_a_32_character_secret(self):
        done, body = self.publish()
        nonce = self.past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        self.assertEqual(len(nonce), 32)

    def test_take_with_something_that_is_not_text_is_none(self):
        for nonce in (None, 123, b"a" * 32):
            with self.subTest(nonce=nonce):
                self.assertIsNone(self.past.take(nonce))

    def test_an_address_lasts_exactly_the_visit_seconds(self):
        done, body = self.publish()
        clock = [0.0]
        past = past_reports.PastReports(self.db, clock=lambda: clock[0])
        nonce = past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        clock[0] = past_reports.VISIT_SECONDS
        self.assertIsNotNone(past.take(nonce), "still good at exactly the limit")
        nonce = past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        clock[0] = past_reports.VISIT_SECONDS * 2 + 1
        self.assertIsNone(past.take(nonce), "gone just past the limit")

    def test_the_limit_is_120_seconds(self):
        self.assertEqual(past_reports.VISIT_SECONDS, 120)

    def test_an_old_address_is_dropped_by_age_not_by_the_sum_of_times(self):
        done, body = self.publish()
        clock = [100.0]
        past = past_reports.PastReports(self.db, clock=lambda: clock[0])
        first = past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        clock[0] = 101.0
        past.visit("PUB", done["number"])
        self.assertIn(first, past.visits, "one second old is not old")

    def test_an_address_exactly_at_the_limit_is_not_swept_by_the_next_visit(self):
        done, body = self.publish()
        clock = [0.0]
        past = past_reports.PastReports(self.db, clock=lambda: clock[0])
        first = past.visit("PUB", done["number"])[1]["url"].split("=")[1]
        clock[0] = float(past_reports.VISIT_SECONDS)
        past.visit("PUB", done["number"])
        self.assertIn(first, past.visits)


class DoctorEdges(DoctorCase):
    def test_the_app_folder_is_the_one_above_src(self):
        self.assertEqual(doctor.APP, ROOT)

    def test_the_python_seen_is_three_numbers(self):
        self.assertEqual(doctor.Seen().version, tuple(sys.version_info[:3]))

    def test_exactly_the_minimum_python_is_ready(self):
        self.assertEqual(doctor.check_python(doctor.Seen(on=pl.MAC, version=doctor.MIN_PYTHON, sqlite_version="3.37.0")).kind, doctor.READY)

    def test_a_file_where_the_data_folder_should_be_cannot_be_saved_in(self):
        afile = self.home / "afile"
        afile.write_text("x", encoding="utf-8")
        self.assertFalse(doctor._can_save_in(afile))

    def test_a_folder_that_cannot_be_written_in_cannot_be_saved_in(self):
        from unittest import mock
        with mock.patch.object(doctor.tempfile, "TemporaryFile", side_effect=PermissionError("fictional")):
            self.assertFalse(doctor._can_save_in(self.home))

    def test_which_checks_are_required(self):
        required = {doctor.check_id(c): c.required for c in doctor.CHECKS}
        self.assertEqual(required, {"python": True, "data_folder": True, "data_not_in_onedrive": True,
                                    "data_not_in_synced_folder": True, "app_folder": False,
                                    "browser": False, "port": True, "claude": False})

    def test_a_port_that_is_not_ours_and_not_a_clark_is_to_fix_even_when_the_data_folder_is_unknown(self):
        def no_folder():
            raise pl.PlatformError("no folder")
        seen = doctor.Seen(on=pl.MAC, home=self.home, environ={}, data_dir=no_folder, health=lambda port, mark: launch.NOT_CLARK,
                           free=lambda port: False)
        line = doctor.check_port(seen)
        self.assertEqual(line.kind, doctor.FIX)
        self.assertNotIn("\n", line.words)

    def test_another_data_folder_with_the_folder_known_is_to_fix(self):
        seen = doctor.Seen(on=pl.MAC, home=self.home, environ={}, data=str(self.home / "mine"),
                           health=lambda port, mark: launch.OTHER_DATA, free=lambda port: False)
        line = doctor.check_port(seen)
        self.assertEqual(line.kind, doctor.FIX)
        self.assertIn("different data", line.words)

    def test_the_doctor_finds_a_free_number_with_the_launchers_own_check_when_none_is_given(self):
        seen = doctor.Seen(on=pl.MAC, home=self.home, environ={}, data=str(self.home / "mine"),
                           health=lambda port, mark: launch.NOT_CLARK)
        self.assertEqual(doctor.check_port(seen).kind, doctor.FIX)

    def test_an_interrupted_doctor_exits_1(self):
        def stop(*a, **k):
            raise KeyboardInterrupt
        original = doctor.doctor
        doctor.doctor = stop
        try:
            self.assertEqual(doctor.main([], say=lambda s: None, **self.seams()), 1)
        finally:
            doctor.doctor = original


if __name__ == "__main__":
    unittest.main()

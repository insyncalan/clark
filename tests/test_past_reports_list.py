"""Item 713: the earlier reports of a project in a publish folder (src/clark/past_files.py), and through the publish flow.

Run: python3 dev/run_tests.py test_past_reports_list
The list is read from the folder's own names. A name counts only when it is exactly what publish.file_name makes for this project.
"""
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx
from _paths import SRC  # noqa: F401
from clark import past_files, publish, publish_flow
from clark.store import open_store

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
DAY = "2026-10-28"


def tearDownModule():
    Path(EMPTY_BRANDING).rmdir()


def names(rows):
    return [r["file"] for r in rows]


class Listing(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def touch(self, *files):
        for f in files:
            (self.dir / f).write_text("x", encoding="utf-8")

    def test_newest_first_and_the_row_shape(self):
        self.touch("PUB-report-2026-10-09.html", "PUB-report-2026-10-23.html", "PUB-report-2026-10-16.html")
        rows = past_files.listing(self.dir, "PUB")
        self.assertEqual(rows, [{"week_ending": "2026-10-23", "file": "PUB-report-2026-10-23.html"},
                                {"week_ending": "2026-10-16", "file": "PUB-report-2026-10-16.html"},
                                {"week_ending": "2026-10-09", "file": "PUB-report-2026-10-09.html"}])

    def test_the_current_file_is_left_out(self):
        self.touch("PUB-report-2026-10-09.html", "PUB-report-2026-10-23.html")
        self.assertEqual(names(past_files.listing(self.dir, "PUB", "PUB-report-2026-10-23.html")), ["PUB-report-2026-10-09.html"])

    def test_a_file_that_is_gone_is_not_listed(self):
        self.touch("PUB-report-2026-10-09.html", "PUB-report-2026-10-16.html")
        (self.dir / "PUB-report-2026-10-09.html").unlink()
        self.assertEqual(names(past_files.listing(self.dir, "PUB")), ["PUB-report-2026-10-16.html"])

    def test_names_that_are_not_this_projects_reports(self):
        good = "PUB-report-2026-10-09.html"
        bad = ["PUB report 2026-10-16.html", "PUB-report-2026-10-16 copy.html", "PUB-report-2026-10-17.html.bak", "PUB-report-2026-10-18.HTML",
               "PUB-report-2026-10-19.htm", ".PUB-report-2026-10-20.html", "PUB-report-2026-10-21.html.aside", "PUB-report-undated.html",
               "PUB-report-2026-02-30.html", "PUB-report-2026-13-01.html", "OTH-report-2026-10-22.html", "XPUB-report-2026-10-22.html",
               "PUB-report-2026-10-22é.html", "PUB-report-2026-10-22#1.html", "PUB-report-2026-10-22?.html", "pub-report-2026-10-22.html",
               "PUB-report-2026-1-22.html", "PUB-report-٢026-10-22.html"]
        self.touch(good, *bad)
        self.assertEqual(names(past_files.listing(self.dir, "PUB")), [good])

    def test_separators_cannot_be_in_a_listed_name(self):
        for name in ("a/PUB-report-2026-10-09.html", "PUB-report-2026-10-09.html/x", "PUB-report-2026-10-09\\.html"):
            self.assertFalse(re.fullmatch(r"PUB-report-(\d{4}-\d\d-\d\d)\.html", name))
        self.assertEqual(past_files.listing(self.dir, "PUB"), [])

    def test_a_directory_or_a_link_named_like_a_report_is_skipped(self):
        (self.dir / "PUB-report-2026-10-09.html").mkdir()
        target = self.dir / "elsewhere.html"
        target.write_text("x", encoding="utf-8")
        try:
            os.symlink(target, self.dir / "PUB-report-2026-10-16.html")
        except (OSError, NotImplementedError):
            self.skipTest("no symbolic links here")
        self.touch("PUB-report-2026-10-23.html")
        self.assertEqual(names(past_files.listing(self.dir, "PUB")), ["PUB-report-2026-10-23.html"])

    def test_at_most_twenty_the_newest(self):
        self.touch(*[f"PUB-report-2026-09-{d:02d}.html" for d in range(1, 26)])
        rows = past_files.listing(self.dir, "PUB")
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["week_ending"], "2026-09-25")
        self.assertEqual(rows[-1]["week_ending"], "2026-09-06")

    def test_equal_dates_are_in_name_order(self):
        # two names for one date cannot both match; the same date under two codes is two projects, so only this one's is listed
        self.touch("PUB-report-2026-10-09.html", "PUB2-report-2026-10-09.html")
        self.assertEqual(names(past_files.listing(self.dir, "PUB")), ["PUB-report-2026-10-09.html"])
        self.assertEqual(past_files.listing(self.dir, "PUB"), past_files.listing(self.dir, "PUB"))

    def test_a_folder_that_cannot_be_listed_gives_nothing(self):
        self.assertEqual(past_files.listing(self.dir / "missing", "PUB"), [])
        self.assertEqual(past_files.listing(None, "PUB"), [])
        file = self.dir / "a-file"
        file.write_text("x", encoding="utf-8")
        self.assertEqual(past_files.listing(file, "PUB"), [])


class Flow(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.folder = self.root / "Reports"
        self.folder.mkdir()
        data = self.root / "clark-data"
        data.mkdir()
        self.db = data / "clark.db"
        fx.build_db(self.db, fx.load())
        self.store = open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.answer = None
        self.publisher = publish_flow.Publisher(self.db, [], choose_save_file=lambda prompt, default, start=None: self.answer,
                                                choose_folder=lambda *a, **k: None, today=lambda: DAY, by_user=lambda: "Pat Writer",
                                                data_dir=data, branding=EMPTY_BRANDING)

    def go(self, name):
        self.answer = self.folder / name
        status, out = self.publisher.publish({"project": "PUB"})
        self.assertEqual((status, out["ok"]), (200, True), out)
        text = (self.folder / name).read_text(encoding="utf-8")
        return json.loads(re.search(r'id="clark-data">(.*?)</script>', text, re.S).group(1))["data"]

    def test_the_second_report_lists_the_first_and_not_itself(self):
        first = self.go("PUB-report-2026-10-16.html")
        self.assertNotIn("past_reports", first)
        second = self.go("PUB-report-2026-10-23.html")
        self.assertEqual(second["past_reports"], [{"week_ending": "2026-10-16", "file": "PUB-report-2026-10-16.html"}])
        self.assertIn("client_workbook", second)

    def test_a_deleted_first_report_is_not_listed(self):
        self.go("PUB-report-2026-10-16.html")
        (self.folder / "PUB-report-2026-10-16.html").unlink()
        self.assertNotIn("past_reports", self.go("PUB-report-2026-10-23.html"))


class Producer(unittest.TestCase):
    def test_build_without_a_list_is_as_it_was(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = open_store(fx.build_db(Path(tmp.name) / "clark.db", fx.load()), onedrive_roots=[])
        self.addCleanup(store.close)
        a = publish.build(store, "PUB", DAY, EMPTY_BRANDING, number=1)
        b = publish.build(store, "PUB", DAY, EMPTY_BRANDING, number=1, past_reports=[])
        self.assertEqual(a["body"], b["body"])
        c = publish.build(store, "PUB", DAY, EMPTY_BRANDING, number=1,
                          past_reports=[{"week_ending": "2026-10-16", "file": "PUB-report-2026-10-16.html"},
                                        {"week_ending": "2026-10-23", "file": "PUB-report-2026-10-23.html"}])
        self.assertEqual(c["past_reports"], [{"week_ending": "2026-10-16", "file": "PUB-report-2026-10-16.html"}],
                         "the file being made (this project's week 2026-10-23) is not its own earlier report")


if __name__ == "__main__":
    unittest.main()

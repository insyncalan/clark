"""Row 1299 PR A: hostile inputs to the Projects overview read (projects_overview.py and GET /api/projects-overview).

Each test sends what a caller or a file could really send (odd types, odd names, odd files, repeated and parallel reads, odd request lines) and pins
what the code does with it. Sample data only.

Run: python3 dev/run_tests.py test_projects_overview_hostile_1299
"""
import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from _paths import SRC  # noqa: F401

from clark import projects_overview as po, server as sv
from clark.store import open_store

NOW = datetime(2026, 11, 20, 1, 30, tzinfo=timezone(timedelta(hours=4)))


def row(**kw):
    return {**{"code": "SAM", "name": "Sam", "publish_client": "/c", "brand": "generic", "review_after_days": 14}, **kw}


def rows(projects, counts=None, shared=(), asking=True, days=14, backup=0):
    return po.overview_rows(projects, counts or {}, shared, asking, days, backup)


class Pure(unittest.TestCase):
    def test_a_stamp_of_the_wrong_type_or_shape_is_no_time_and_never_a_crash(self):
        for bad in ("", "   ", b"20261119T213000Z", 20261119, [], {}, "2026-13-45T00:00:00Z", "20261319T000000Z", "\x00", "20261119T213000Z\n\n\n x"):
            self.assertIsNone(po.days_since(bad, NOW), repr(bad))

    def test_a_stamp_with_padding_still_counts(self):
        self.assertEqual(po.days_since("  20261117T100000Z\n", NOW), 3)       # timefmt.parse strips the text first

    def test_a_now_without_a_zone_is_read_as_utc_and_a_local_seam_that_fails_is_no_time(self):
        naive = datetime(2026, 11, 20, 1, 30)
        self.assertEqual(po.days_since("20261119T213000Z", naive), 1)         # UTC: 19th 21:30 against 20th
        for exc in (ValueError, OverflowError, OSError):
            def boom(t, exc=exc):
                raise exc("zone")
            self.assertIsNone(po.days_since("20261119T213000Z", NOW, boom))

    def test_attention_survives_a_row_with_odd_values(self):
        got = po.attention_for({"client_folder": None, "last_backup_days": 0, "asking": 0, "folders": 5})
        self.assertEqual(got, [po.NO_CLIENT_FOLDER])
        got = po.attention_for({"client_folder": "x", "last_backup_days": -3, "asking": "yes", "folders": 0})
        self.assertEqual(got, [po.ASKING_NO_FOLDERS])        # a negative age is never old; any truthy asking counts

    def test_attention_needs_every_key_a_row_missing_one_is_a_key_error(self):
        with self.assertRaises(KeyError):
            po.attention_for({"client_folder": "x", "asking": True, "folders": 0})

    def test_folders_with_a_hostile_list_of_paths(self):
        self.assertEqual(po.effective_folders([], []), 0)
        self.assertEqual(po.effective_folders(["/a", "/a", "/a"], ["/a"]), 1)
        self.assertEqual(po.effective_folders(["/a", "/A"], []), 2)                    # paths are compared as text: case counts
        self.assertEqual(po.effective_folders(["", ""], ["", "/x"]), 2)               # an empty path is one path
        self.assertEqual(po.effective_folders(["/é", "/é"], []), 2)             # no Unicode folding
        self.assertEqual(po.effective_folders([f"/f{n}" for n in range(5000)], []), po.ask_folders.MAX_FOLDERS)
        self.assertEqual(po.effective_folders(("/a",), ("/b",)), 2)                    # tuples as lists

    def test_codes_that_are_nearly_project_codes_are_left_out(self):
        near = ["ABC\n", " ABC", "ABC ", "AB", "ABCDEFGH", "abc", "AВC", "ＡＢＣ", "1ABC", "AB-C", "AB_C", "ABC\x00", "", "AB٣", "AßC"]
        self.assertEqual(rows([row(code=c) for c in near]), [])
        edge = rows([row(code=c) for c in ("ABC", "ABCDEFG", "A00", "A1B2C3D")])
        self.assertEqual([r["code"] for r in edge], ["ABC", "ABCDEFG", "A00", "A1B2C3D"])

    def test_rows_that_are_dict_like_but_not_dicts_are_left_out(self):
        class Fake(dict):
            pass
        self.assertEqual(len(rows([Fake(row())])), 1)                    # a dict subclass is a dict
        self.assertEqual(rows([[("code", "ABC")], (row(),), 5, 5.5, True, b"ABC", iter(())]), [])

    def test_names_are_kept_as_stored_unless_blank(self):
        (r,) = rows([row(name="  Sam  ")])
        self.assertEqual(r["name"], "  Sam  ")                              # not stripped when it has text
        (r,) = rows([row(name=" \t\n")])
        self.assertEqual(r["name"], "SAM")                                    # only white space: the code stands in
        (r,) = rows([row(name="x" * 100000)])
        self.assertEqual(len(r["name"]), 100000)                              # no length limit here
        (r,) = rows([row(name="<b>‮\U0001f600</b>")])
        self.assertEqual(r["name"], "<b>‮\U0001f600</b>")                # sent as data; the page escapes

    def test_the_edges_of_what_is_worth_a_look_through_the_rows(self):
        (r,) = rows([row()], {"SAM": ["/a"]}, backup=1)
        self.assertEqual(r["attention"], [])                                   # one whole day old is fine
        (r,) = rows([row()], {"SAM": ["/a"]}, backup=2)
        self.assertEqual(r["attention"], [po.BACKUP_OLD])
        (r,) = rows([row()], asking=False)
        self.assertEqual(r["attention"], [])                                   # no folders only matters while asking is on
        (r,) = rows([row(brand="")])
        self.assertEqual((r["brand"], r["brand_override"]), ("generic", False))

    def test_a_brand_of_white_space_is_a_brand_and_the_default_by_another_case_is_an_override(self):
        (r,) = rows([row(brand="  ")])
        self.assertEqual((r["brand"], r["brand_override"]), ("  ", True))
        (r,) = rows([row(brand="Generic")])
        self.assertEqual((r["brand"], r["brand_override"]), ("Generic", True))
        (r,) = rows([row(brand=["generic"])])
        self.assertEqual((r["brand"], r["brand_override"]), ("generic", False))

    def test_review_days_that_are_not_a_whole_number_in_range_fall_back_to_the_default(self):
        for bad in (True, False, 0, -1, 366, 10 ** 30, 14.0, 30.5, "30", None, [30], float("nan"), float("inf")):
            (r,) = rows([row(review_after_days=bad)], days=14)
            self.assertEqual((r["review_days"], r["review_override"]), (14, False), repr(bad))
        for good in (1, 365):
            (r,) = rows([row(review_after_days=good)], days=14)
            self.assertEqual((r["review_days"], r["review_override"]), (good, True))
        (r,) = rows([row(review_after_days="x")], days=30)
        self.assertEqual((r["review_days"], r["review_override"]), (14, True))   # the code's own default, not the install default

    def test_the_client_folder_of_white_space_or_a_wrong_type_is_none(self):
        for bad in ("", "   ", "\t\n", None, 5, ["/c"], b"/c"):
            (r,) = rows([row(publish_client=bad)])
            self.assertEqual(r["client_folder"], "", repr(bad))
            self.assertIn(po.NO_CLIENT_FOLDER, r["attention"])
        (r,) = rows([row(publish_client=" /with space/é ")])
        self.assertEqual(r["client_folder"], "/with space/é")

    def test_asking_is_on_only_for_exactly_true(self):
        for v, want in ((True, True), (1, False), ("1", False), ("true", False), (None, False), (False, False), ([True], False)):
            self.assertIs(rows([row()], asking=v)[0]["asking"], want, repr(v))

    def test_a_project_missing_every_key_but_the_code_still_gets_a_row(self):
        (r,) = rows([{"code": "ABC"}], backup=None)
        self.assertEqual((r["name"], r["brand"], r["client_folder"], r["review_days"], r["last_backup_days"]), ("ABC", "generic", "", 14, None))
        self.assertEqual(r["attention"], [po.NO_CLIENT_FOLDER, po.NO_BACKUP, po.ASKING_NO_FOLDERS])

    def test_the_limit_counts_rows_kept_not_rows_offered(self):
        junk = [None] * 2000
        good = [row(code="P%03d" % n) for n in range(po.LIMIT + 3)]
        got = rows(junk + good + junk)
        self.assertEqual(len(got), po.LIMIT)
        self.assertEqual(got[-1]["code"], "P%03d" % (po.LIMIT - 1))

    def test_the_same_code_twice_gives_two_rows_and_a_generator_is_read_once(self):
        self.assertEqual([r["code"] for r in rows([row(), row()])], ["SAM", "SAM"])
        self.assertEqual(len(rows(row(code=c) for c in ("ABC", "DEF"))), 2)

    def test_the_counts_of_a_code_that_is_not_there_are_no_folders_and_the_input_is_not_changed(self):
        counts = {"SAM": ["/a"]}
        shared = ["/s"]
        rows([row(), row(code="OTH")], counts, shared)
        self.assertEqual((counts, shared), ({"SAM": ["/a"]}, ["/s"]))
        self.assertEqual(rows([row(code="OTH")], counts, [])[0]["folders"], 0)

    def test_every_row_is_new_and_shares_nothing_with_the_next_call(self):
        a = rows([row()])
        a[0]["attention"].append("x")
        self.assertEqual(rows([row()])[0]["attention"], [po.ASKING_NO_FOLDERS])


class Service(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = self.d / "clark.db"
        self.store = open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.folder = self.d / "planted"
        self.svc = po.ProjectsOverview(self.db, [], backups=self.folder, now=lambda: NOW)

    def make(self, code, **kw):
        with self.store.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": code, "name": kw.pop("name", "Sam " + code), **kw})

    def backup(self, name, data=b"x"):
        self.folder.mkdir(exist_ok=True)
        (self.folder / name).write_bytes(data)

    def test_files_in_the_backup_folder_that_are_not_backups_are_not_read(self):
        self.make("AAA", publish_client="/c")
        self.folder.mkdir()
        for name in ("clark-20261119T200000Z-daily.db.tmp", "clark-20261119T200000Z-daily.sqlite", "CLARK-20261119T200000Z-daily.db", "clark-20261119T200000Z-nonsense.db",
                     "clark-2026111T200000Z-daily.db", "clark-٢٠261119T200000Z-daily.db", "notes.txt", "clark-20261119T200000Z-daily.db\n", " clark-20261119T200000Z-daily.db"):
            (self.folder / name).write_bytes(b"x")
        (self.folder / "clark-20261119T200000Z-daily.db.dir").mkdir()
        self.assertIsNone(self.svc.read()[1]["projects"][0]["last_backup_days"])

    def test_a_folder_a_link_and_a_hard_link_named_like_a_backup_are_not_backups(self):
        self.make("AAA", publish_client="/c")
        self.folder.mkdir()
        (self.folder / "clark-20261119T200000Z-daily.db").mkdir()
        real = self.d / "real.db"
        real.write_bytes(b"x")
        try:
            os.symlink(real, self.folder / "clark-20261119T200000Z-undo.db")
            os.link(real, self.folder / "clark-20261119T200000Z-weekly.db")
        except (OSError, NotImplementedError):
            self.skipTest("this file system has no links")
        self.assertIsNone(self.svc.read()[1]["projects"][0]["last_backup_days"])

    def test_a_backup_with_a_stamp_that_is_not_a_date_is_the_newest_by_text_and_gives_no_age(self):
        self.make("AAA", publish_client="/c")
        self.backup("clark-20261119T200000Z-daily.db")
        self.backup("clark-20269999T999999Z-daily.db")                 # matches the name rule, is no date; sorts last as text
        self.assertIsNone(self.svc.read()[1]["projects"][0]["last_backup_days"])

    def test_the_newest_stamp_wins_not_the_newest_file_time(self):
        self.make("AAA", publish_client="/c")
        self.backup("clark-20261101T000000Z-daily.db")
        self.backup("clark-20261119T200000Z-daily.db")
        os.utime(self.folder / "clark-20261119T200000Z-daily.db", (1, 1))      # the newer name has the older file time
        self.assertEqual(self.svc.read()[1]["projects"][0]["last_backup_days"], 0)

    def test_a_backup_dated_in_the_future_is_today_and_not_flagged(self):
        self.make("AAA", publish_client="/c")
        self.backup("clark-20301231T000000Z-daily.db")
        (a,) = self.svc.read()[1]["projects"]
        self.assertEqual((a["last_backup_days"], po.BACKUP_OLD in a["attention"], po.NO_BACKUP in a["attention"]), (0, False, False))

    def test_an_unreadable_backup_folder_is_no_backup(self):
        self.make("AAA", publish_client="/c")
        self.folder.mkdir()
        os.chmod(self.folder, 0)
        self.addCleanup(os.chmod, self.folder, 0o700)
        got = self.svc.read()
        self.assertEqual(got[0], 200)
        if os.access(self.folder, os.R_OK):
            self.skipTest("this user reads any folder")
        self.assertIsNone(got[1]["projects"][0]["last_backup_days"])

    def test_the_backup_folder_given_as_odd_paths(self):
        self.make("AAA", publish_client="/c")
        for odd in ("a\x00b", "x" * 5000, "../../..//nowhere", "~", " "):
            svc = po.ProjectsOverview(self.db, [], backups=odd, now=lambda: NOW)
            try:
                got = svc.read()
            except ValueError:
                continue                  # an embedded NUL is a ValueError from scandir, not an OSError (see the test below)
            self.assertEqual(got[0], 200, repr(odd))
            self.assertIsNone(got[1]["projects"][0]["last_backup_days"])

    def test_a_backup_folder_path_with_a_nul_shows_no_backup_age(self):
        self.make("AAA", publish_client="/c")
        svc = po.ProjectsOverview(self.db, [], backups="a\x00b", now=lambda: NOW)
        status, got = svc.read()
        self.assertEqual(status, 200)
        self.assertTrue(got["ok"])
        self.assertIsNone(got["projects"][0]["last_backup_days"])

    def test_odd_characters_in_the_database_path_and_a_missing_file(self):
        odd = self.d / "dä ta ; 'q' é \U0001f600 $x"
        odd.mkdir()
        s = open_store(odd / "clark.db", onedrive_roots=[])
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ODD", "name": "Odd"})
        s.close()
        got = po.ProjectsOverview(odd / "clark.db", [], backups=self.folder, now=lambda: NOW).read()
        self.assertEqual((got[0], [p["code"] for p in got[1]["projects"]]), (200, ["ODD"]))

    def test_a_database_that_is_a_folder_or_empty_is_busy_and_the_next_read_still_works(self):
        (self.d / "adir.db").mkdir()
        self.assertEqual(po.ProjectsOverview(self.d / "adir.db", []).read()[0], 409)
        (self.d / "zero.db").write_bytes(b"")
        status, got = po.ProjectsOverview(self.d / "zero.db", []).read()
        self.assertIn(status, (200, 409))                     # an empty file is a new file to the store; either answer is a plain one
        self.assertEqual(self.svc.read()[0], 200)

    def test_a_failed_read_does_not_keep_the_lock(self):
        bad = self.d / "bad.db"
        bad.write_bytes(b"this is not a database" * 50)
        svc = po.ProjectsOverview(bad, [])
        for _ in range(3):
            self.assertEqual(svc.read()[0], 409)
        self.assertFalse(svc.lock.locked())

    def test_a_missing_install_defaults_row_reads_as_the_default_and_the_store_is_still_closed_and_the_lock_free(self):
        self.make("AAA", publish_client="/c")
        self.store.con.execute("DELETE FROM install_defaults")
        self.store.con.commit()
        status, got = self.svc.read()
        self.assertEqual((status, got["ok"], got["default_review_days"]), (200, True, 14))
        self.assertEqual(got["projects"][0]["review_days"], 14)
        self.assertFalse(self.svc.lock.locked())

    def test_repeated_reads_give_the_same_answer_and_change_nothing(self):
        self.make("AAA", publish_client="/c")
        self.folder.mkdir()
        (self.folder / "clark-20261119T200000Z-daily.db").write_bytes(b"x")
        first = self.svc.read()
        before = self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        for _ in range(20):
            self.assertEqual(self.svc.read(), first)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0], before)
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["clark-20261119T200000Z-daily.db"])

    def test_parallel_reads_all_answer_the_same_and_never_overlap_in_the_store(self):
        self.make("AAA", publish_client="/c")
        self.make("BBB")
        want = self.svc.read()
        inside, worst, errors, got = [0], [0], [], []
        guard = threading.Lock()
        real = po.open_store

        def watched(*a, **k):
            with guard:
                inside[0] += 1
                worst[0] = max(worst[0], inside[0])
            return real(*a, **k)

        def done():
            with guard:
                inside[0] -= 1

        orig_read = po.ProjectsOverview.read

        def run():
            try:
                got.append(self.svc.read())
            except Exception as e:  # noqa: BLE001
                errors.append(e)
        po.open_store = watched
        self.addCleanup(setattr, po, "open_store", real)
        orig_now = self.svc.now
        self.svc.now = lambda: (done(), orig_now())[1]            # now() runs after the store is closed: the end of the locked part
        threads = [threading.Thread(target=run) for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(errors, [])
        self.assertEqual(got, [want] * 12)
        self.assertEqual(worst[0], 1, "one read at a time holds the store")
        self.assertIs(po.ProjectsOverview.read, orig_read)

    def test_a_now_that_reads_again_does_not_deadlock_because_now_is_called_outside_the_lock(self):
        self.make("AAA", publish_client="/c")
        depth = []

        def now():
            if not depth:
                depth.append(1)
                self.svc.read()                        # reentrant: the lock is free here
            return NOW
        self.svc.now = now
        self.assertEqual(self.svc.read()[0], 200)

    def test_a_now_that_fails_is_a_fault_after_the_store_is_closed(self):
        def boom():
            raise RuntimeError("clock")
        self.svc.now = boom
        with self.assertRaises(RuntimeError):
            self.svc.read()
        self.assertFalse(self.svc.lock.locked())

    def test_a_shared_folders_file_that_is_hostile_gives_no_shared_folders_or_the_ones_that_are_sound(self):
        self.make("AAA", publish_client="/c")
        self.backup("clark-20261119T200000Z-daily.db")
        for text in ("not json", "", "{}", "null", '"x"', "[1, null, {}]", "\x00\x00", "[1" * 10):
            (self.d / "ask_folders_all.json").write_text(text, encoding="utf-8")
            status, got = self.svc.read()
            self.assertEqual(status, 200, repr(text[:10]))
            self.assertEqual(got["projects"][0]["folders"], 0, repr(text[:10]))
        (self.d / "ask_folders_all.json").write_bytes(b"\xff\xfe\x00bad")
        self.assertEqual(self.svc.read()[0], 200)
        (self.d / "ask_folders_all.json").write_text('["/ok", "rel", 5, null, "/ok2"]', encoding="utf-8")
        self.assertEqual(self.svc.read()[1]["projects"][0]["folders"], 2)       # only text that starts with "/" counts

    def test_a_shared_folders_file_nested_far_too_deep_shows_no_shared_folders(self):
        """ask_folders.shared_folders catches RecursionError (json.loads raises it for a deeply nested array): the overview reads and shows none."""
        self.make("AAA", publish_client="/c")
        (self.d / "ask_folders_all.json").write_text("[" * 100000, encoding="utf-8")
        status, got = self.svc.read()
        self.assertEqual((status, got["ok"], got["projects"][0]["folders"]), (200, True, 0))
        self.assertFalse(self.svc.lock.locked())

    def test_source_folders_of_an_archived_project_or_an_unknown_code_do_not_make_a_row_or_a_count(self):
        self.make("AAA", publish_client="/c")
        self.make("OLD")
        with self.store.step("dashboard", "tester", place="menu") as step:
            step.archive("projects", "OLD")
        self.store.con.execute("PRAGMA foreign_keys = OFF")
        self.store.con.execute("INSERT INTO source_folders (project, path, sort_order) VALUES ('GHOST', '/g', 1)")
        self.store.con.execute("INSERT INTO source_folders (project, path, sort_order) VALUES ('OLD', '/o', 1)")
        self.store.con.commit()
        got = self.svc.read()[1]
        self.assertEqual([p["code"] for p in got["projects"]], ["AAA"])
        self.assertEqual(got["projects"][0]["folders"], 0)

    def test_a_project_code_in_the_file_that_the_page_could_not_use_is_left_out_of_the_rows(self):
        self.make("AAA", publish_client="/c")
        self.store.con.execute("PRAGMA ignore_check_constraints = ON")
        try:
            self.store.con.execute("INSERT INTO projects (code, name) VALUES ('lower', 'x')")
            self.store.con.commit()
        except Exception:  # noqa: BLE001
            self.skipTest("the store refuses a code that is not a project code")
        self.assertEqual([p["code"] for p in self.svc.read()[1]["projects"]], ["AAA"])

    def test_names_with_odd_characters_survive_the_round_trip(self):
        weird = "Zoë <script>\"'&</script> ‮ \U0001f600 \n tab\t"
        self.make("AAA", name=weird, publish_client="/cé \"q\"")
        (a,) = self.svc.read()[1]["projects"]
        self.assertEqual(a["name"], weird)
        self.assertEqual(a["client_folder"], "/cé \"q\"")
        json.dumps(self.svc.read()[1])                          # the whole answer is plain JSON

    def test_many_projects_are_cut_at_the_limit_in_code_order(self):
        for n in range(po.LIMIT + 3):
            self.store.con.execute("INSERT INTO projects (code, name) VALUES (?, ?)", ("P%03d" % n, "n"))
        self.store.con.commit()
        got = self.svc.read()[1]
        self.assertEqual(len(got["projects"]), po.LIMIT)
        self.assertEqual(got["projects"][0]["code"], "P000")
        self.assertEqual(got["attention_count"], po.LIMIT)

    def test_rows_come_in_code_order_whatever_order_they_were_made_in_and_the_count_is_of_flagged_rows_only(self):
        self.make("CCC", publish_client="/c")
        self.make("AAA", publish_client="/c")
        self.make("BBB")
        self.store.con.execute("UPDATE app_settings SET ask_enabled = 0")
        self.store.con.commit()
        self.folder.mkdir()
        (self.folder / "clark-20261119T200000Z-daily.db").write_bytes(b"x")
        got = self.svc.read()[1]
        self.assertEqual([p["code"] for p in got["projects"]], ["AAA", "BBB", "CCC"])
        self.assertEqual(got["attention_count"], 1)

    def test_the_store_is_closed_even_when_a_read_inside_it_fails(self):
        closed = []

        class Broken:
            def read(self, *a, **k):
                raise RuntimeError("read")

            def close(self):
                closed.append(1)
        real = po.open_store
        po.open_store = lambda *a, **k: Broken()
        self.addCleanup(setattr, po, "open_store", real)
        with self.assertRaises(RuntimeError):
            self.svc.read()
        self.assertEqual(closed, [1])
        self.assertFalse(self.svc.lock.locked())

    def test_the_default_review_days_moved_to_an_odd_value_is_sent_as_it_is_in_the_file(self):
        self.make("AAA", publish_client="/c")
        self.store.con.execute("UPDATE install_defaults SET review_days = 7")
        self.store.con.commit()
        got = self.svc.read()[1]
        self.assertEqual((got["default_review_days"], got["projects"][0]["review_days"], got["projects"][0]["review_override"]), (7, 14, True))


class Running:
    def __init__(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def request(self, method, path, token=True, host=None, body=None, headers=()):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=20)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", host or f"127.0.0.1:{self.port}")
            if token:
                conn.putheader(sv.TOKEN_HEADER, sv.TOKEN)
            for k, v in headers:
                conn.putheader(k, v)
            if body is not None:
                conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
            r = conn.getresponse()
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, raw
        finally:
            conn.close()


class Route(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        store = open_store(self.d / "clark.db", onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "SAM", "name": "Sam"})
        store.close()
        self.s = Running()
        self.addCleanup(lambda: (self.s.httpd.shutdown(), self.s.httpd.server_close()))
        self.s.httpd.projects_overview = po.ProjectsOverview(self.d / "clark.db", [], backups=self.d / "none")

    def test_any_query_at_all_even_an_odd_one_is_refused_but_an_empty_one_is_not(self):
        for q in ("?x", "?project=SAM", "?%00", "?a=b&a=c", "?" + "x" * 5000, "?%ff%fe", "?=", "?;"):
            self.assertEqual(self.s.request("GET", "/api/projects-overview" + q)[0], 400, q)
        self.assertEqual(self.s.request("GET", "/api/projects-overview?")[0], 200)

    def test_a_server_with_no_service_answers_not_found_even_with_a_query(self):
        self.s.httpd.projects_overview = None
        self.assertEqual(self.s.request("GET", "/api/projects-overview")[0], 404)
        self.assertEqual(self.s.request("GET", "/api/projects-overview?x=1")[0], 404)

    def test_a_fragment_sent_in_the_request_line_is_part_of_the_path_and_not_found(self):
        self.assertEqual(self.s.request("GET", "/api/projects-overview#x=1")[0], 404)

    def test_the_wrong_paths_are_not_this_route(self):
        for p in ("/api/projects-overview/", "/api/projects-overview/x", "/api/Projects-Overview", "/api/projects-overviews", "/api//projects-overview", "/api/projects-overview%2f"):
            self.assertNotEqual(self.s.request("GET", p)[0], 200, p)

    def test_no_token_or_a_wrong_token_or_a_foreign_host_is_refused_and_nothing_is_read(self):
        calls = []
        self.s.httpd.projects_overview = type("Spy", (), {"read": lambda self: calls.append(1) or (200, {"ok": True})})()
        self.assertNotEqual(self.s.request("GET", "/api/projects-overview", token=False)[0], 200)
        self.assertNotEqual(self.s.request("GET", "/api/projects-overview", host="evil.example")[0], 200)
        self.assertNotEqual(self.s.request("GET", "/api/projects-overview", token=False, headers=[(sv.TOKEN_HEADER, "wrong")])[0], 200)
        self.assertEqual(calls, [])

    def test_other_methods_are_not_this_route_and_read_nothing(self):
        calls = []
        self.s.httpd.projects_overview = type("Spy", (), {"read": lambda self: calls.append(1) or (200, {"ok": True})})()
        for method in ("POST", "PUT", "DELETE", "PATCH"):
            got = self.s.request(method, "/api/projects-overview", body=b"{}")
            self.assertNotEqual(got[0], 200, method)
        self.assertEqual(calls, [])

    def test_a_service_that_raises_is_a_500_in_plain_words_with_no_trace(self):
        def boom(self):
            raise RuntimeError("secret /path/to/clark.db")
        self.s.httpd.projects_overview = type("Boom", (), {"read": boom})()
        status, got = self.s.request("GET", "/api/projects-overview")
        self.assertEqual(status, 500)
        self.assertNotIn("secret", json.dumps(got))
        self.assertNotIn("/path", json.dumps(got))
        self.s.httpd.projects_overview = po.ProjectsOverview(self.d / "clark.db", [], backups=self.d / "none")
        self.assertEqual(self.s.request("GET", "/api/projects-overview")[0], 200)       # the server lives on

    def test_a_busy_file_is_a_409_with_the_plain_message_through_the_route(self):
        bad = self.d / "bad.db"
        bad.write_bytes(b"this is not a database" * 50)
        self.s.httpd.projects_overview = po.ProjectsOverview(bad, [])
        status, got = self.s.request("GET", "/api/projects-overview")
        self.assertEqual((status, got["code"], got["message"]), (409, "busy", po.MESSAGES["busy"]))

    def test_parallel_requests_all_get_the_same_rows(self):
        out = []

        def go():
            out.append(self.s.request("GET", "/api/projects-overview"))
        threads = [threading.Thread(target=go) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        self.assertEqual(len(out), 10)
        self.assertEqual({json.dumps(o, sort_keys=True) for o in out}, {json.dumps(out[0], sort_keys=True)})
        self.assertEqual(out[0][0], 200)

    def test_the_answer_is_json_and_has_no_path_or_secret_of_the_machine(self):
        status, got = self.s.request("GET", "/api/projects-overview")
        text = json.dumps(got)
        self.assertNotIn(str(self.d), text)
        self.assertNotIn("clark.db", text)

    def test_a_service_given_the_wrong_kind_of_thing_is_a_fault_not_a_hang(self):
        self.s.httpd.projects_overview = object()
        self.assertEqual(self.s.request("GET", "/api/projects-overview")[0], 500)
        self.s.httpd.projects_overview = type("Bad", (), {"read": lambda self: "nope"})()
        self.assertEqual(self.s.request("GET", "/api/projects-overview")[0], 500)


if __name__ == "__main__":
    unittest.main()

"""Row 1299, slice S3: the read behind the Projects overview (GET /api/projects-overview, projects_overview.py).

The pure part (days, what is worth a look, the rows) is tested on plain values; the service is tested against a real store file; the route over a
real local server. Sample data only.

Run: python3 dev/run_tests.py test_projects_overview_1299
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

NOW = datetime(2026, 11, 20, 1, 30, tzinfo=timezone(timedelta(hours=4)))      # 20-11, 01:30 in a zone four hours ahead of UTC (19-11, 21:30 UTC)


def row(**kw):
    base = {"code": "SAM", "name": "Sam", "publish_client": "/clients/sam", "brand": "generic", "review_after_days": 14}
    return {**base, **kw}


class Days(unittest.TestCase):
    def test_whole_calendar_days_on_the_users_own_clock(self):
        self.assertEqual(po.days_since("20261119T213000Z", NOW), 0)       # 01:30 on the 20th here
        self.assertEqual(po.days_since("20261119T193000Z", NOW), 1)       # 23:30 on the 19th here
        self.assertEqual(po.days_since("20261117T100000Z", NOW), 3)
        self.assertEqual(po.days_since("20271117T100000Z", NOW), 0)       # a time in the future is today
        self.assertIsNone(po.days_since("nonsense", NOW))
        self.assertIsNone(po.days_since("99991231T235959Z", NOW), "a year too far for the zone is no time")
        self.assertIsNone(po.days_since(None, NOW))


class Attention(unittest.TestCase):
    def one(self, **kw):
        base = {"client_folder": "/c", "last_backup_days": 0, "asking": False, "folders": 0}
        return po.attention_for({**base, **kw})

    def test_each_thing_worth_a_look_alone_and_in_order(self):
        self.assertEqual(self.one(), [])
        self.assertEqual(self.one(client_folder=""), [po.NO_CLIENT_FOLDER])
        self.assertEqual(self.one(last_backup_days=2), [po.BACKUP_OLD])
        self.assertEqual(self.one(asking=True), [po.ASKING_NO_FOLDERS])
        self.assertEqual(self.one(client_folder="", last_backup_days=9, asking=True), [po.NO_CLIENT_FOLDER, po.BACKUP_OLD, po.ASKING_NO_FOLDERS])

    def test_the_edges(self):
        self.assertEqual(self.one(last_backup_days=1), [])                # one day old is fine, two is not
        self.assertEqual(self.one(last_backup_days=None), [po.NO_BACKUP])  # no backup at all is flagged too
        self.assertEqual(self.one(asking=True, folders=1), [])
        self.assertEqual(self.one(asking=False, folders=0), [])


class Rows(unittest.TestCase):
    def rows(self, projects, counts=None, shared=0, asking=True, days=14, backup=0):
        return po.overview_rows(projects, counts or {}, shared, asking, days, backup)

    def test_values_defaults_and_overrides(self):
        (r,) = self.rows([row(brand="atlas", review_after_days=30, publish_client="  /c  ")], {"SAM": 2}, 1, backup=3)
        self.assertEqual(r, {"code": "SAM", "name": "Sam", "asking": True, "brand": "atlas", "brand_override": True, "folders": 3, "review_days": 30,
                             "review_override": True, "client_folder": "/c", "last_backup_days": 3, "attention": [po.BACKUP_OLD]})
        (r,) = self.rows([row()], days=14)
        self.assertEqual((r["brand_override"], r["review_override"], r["folders"], r["client_folder"]), (False, False, 0, "/clients/sam"))
        (r,) = self.rows([row()], days=7)
        self.assertEqual((r["review_days"], r["review_override"]), (14, True))        # the default moved: the project's own 14 is now an override

    def test_odd_values_fall_back(self):
        (r,) = self.rows([row(name="  ", brand=None, publish_client=None, review_after_days="x")], asking=1)
        self.assertEqual((r["name"], r["brand"], r["client_folder"], r["review_days"], r["asking"]), ("SAM", po.BRAND_DEFAULT, "", 14, False))
        self.assertEqual(r["attention"], [po.NO_CLIENT_FOLDER])
        (r,) = self.rows([row(name=5, brand="")])
        self.assertEqual((r["name"], r["brand"]), ("SAM", po.BRAND_DEFAULT))
        self.assertEqual(self.rows([row(brand=5)])[0]["brand"], po.BRAND_DEFAULT)

    def test_rows_that_are_not_projects_are_left_out_and_the_list_stops(self):
        got = self.rows([None, "SAM", {}, row(code="no"), row(code=7), row(code="LONGCODE9"), row(code="ABC")])
        self.assertEqual([r["code"] for r in got], ["ABC"])
        many = [row(code="P%03d" % i) for i in range(po.LIMIT + 5)]
        self.assertEqual(len(self.rows(many)), po.LIMIT)
        self.assertEqual(len(self.rows(many[:po.LIMIT])), po.LIMIT)


class Service(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = self.d / "clark.db"
        self.store = open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.folder = self.d / "planted"                    # the file's own backups (it takes one as it is made) are not the ones read: each test plants its own
        self.svc = po.ProjectsOverview(self.db, [], backups=self.folder, now=lambda: NOW)

    def make(self, code, **kw):
        with self.store.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": code, "name": kw.pop("name", "Sam " + code), **kw})

    def backup(self, stamp, tag="daily"):
        self.folder.mkdir(exist_ok=True)
        (self.folder / f"clark-{stamp}-{tag}.db").write_bytes(b"x")

    def test_the_codes_the_page_reads_and_the_answers_exact_shape(self):
        self.assertEqual((po.NO_CLIENT_FOLDER, po.BACKUP_OLD, po.NO_BACKUP, po.ASKING_NO_FOLDERS), ("no_client_folder", "backup_old", "no_backup", "asking_no_folders"))
        self.assertEqual((po.LIMIT, po.BACKUP_OLD_DAYS, po.BRAND_DEFAULT), (500, 1, "generic"))
        status, got = self.svc.read()
        self.assertIs(got["ok"], True)
        self.assertEqual(sorted(got), ["attention_count", "default_brand", "default_review_days", "ok", "projects"])
        self.assertEqual(po.MESSAGES["busy"], "The saved data could not be opened just now. Wait a moment and try again.")

    def test_the_roots_given_are_kept_and_none_is_no_roots(self):
        self.assertEqual(po.ProjectsOverview(self.db, ["/one", "/two"]).onedrive_roots, ["/one", "/two"])
        self.assertEqual(po.ProjectsOverview(self.db).onedrive_roots, [])

    def test_a_new_file_has_no_projects(self):
        status, got = self.svc.read()
        self.assertEqual((status, got["projects"], got["attention_count"]), (200, [], 0))
        self.assertEqual((got["default_brand"], got["default_review_days"]), ("generic", 14))

    def test_each_value_comes_from_the_store_and_archived_projects_are_left_out(self):
        self.make("BBB", brand="atlas", review_after_days=30, publish_client="/clients/b", name="Alpha")
        self.make("AAA", name="Zulu")
        self.make("CCC", publish_client="/c")
        self.store.con.execute("INSERT INTO source_folders (project, path, sort_order) VALUES ('CCC', '/work/c', 1)")
        self.make("OLD")
        with self.store.step("dashboard", "tester", place="menu") as step:
            step.archive("projects", "OLD")
        for n in (1, 2):                    # past the writer: its place check (reach.py) is the Mac's, and what is tested here is the read
            self.store.con.execute("INSERT INTO source_folders (project, path, sort_order) VALUES ('BBB', ?, ?)", (f"/work/b{n}", n))
        self.store.con.commit()
        self.backup("20261118T090000Z")
        self.backup("20261116T090000Z", "undo")
        status, got = self.svc.read()
        a, b, c = got["projects"]
        self.assertEqual(c["attention"], [po.BACKUP_OLD])
        self.assertEqual((status, a["code"], b["code"]), (200, "AAA", "BBB"))
        self.assertEqual((a["asking"], a["brand"], a["brand_override"], a["folders"], a["review_days"], a["review_override"], a["client_folder"],
                          a["last_backup_days"], a["attention"]), (True, "generic", False, 0, 14, False, "", 2, [po.NO_CLIENT_FOLDER, po.BACKUP_OLD, po.ASKING_NO_FOLDERS]))
        self.assertEqual((b["brand"], b["brand_override"], b["folders"], b["review_days"], b["review_override"], b["client_folder"], b["attention"]),
                         ("atlas", True, 2, 30, True, "/clients/b", [po.BACKUP_OLD]))
        self.assertEqual(got["attention_count"], 3)

    def test_the_computers_switch_the_default_and_the_shared_folders_count(self):
        self.make("AAA", publish_client="/c")
        self.backup("20261119T200000Z")
        self.store.con.execute("UPDATE app_settings SET ask_enabled = 0")
        self.store.con.execute("UPDATE install_defaults SET review_days = 21")
        self.store.con.commit()
        self.assertEqual(self.svc.read()[1]["default_review_days"], 21)
        (self.d / "ask_folders_all.json").write_text(json.dumps(["/shared/one"]), encoding="utf-8")
        (a,) = self.svc.read()[1]["projects"]
        self.assertEqual((a["asking"], a["review_days"], a["review_override"], a["folders"], a["last_backup_days"], a["attention"]), (False, 14, True, 1, 0, []))
        self.store.con.execute("UPDATE app_settings SET ask_enabled = 1")
        self.store.con.commit()
        self.assertEqual(self.svc.read()[1]["projects"][0]["attention"], [])        # asking is on and a shared folder is read
        self.make("BBB")                                                            # no client folder: one of two projects has something to look at
        got = self.svc.read()[1]
        self.assertEqual((len(got["projects"]), got["attention_count"]), (2, 1))

    def test_no_backup_means_last_backup_none_and_flagged_for_attention(self):
        self.make("AAA", publish_client="/c")
        (a,) = self.svc.read()[1]["projects"]
        self.assertIsNone(a["last_backup_days"])
        self.assertEqual(a["attention"], [po.NO_BACKUP, po.ASKING_NO_FOLDERS])
        self.backup("20261119T200000Z")
        self.assertEqual(self.svc.read()[1]["projects"][0]["last_backup_days"], 0)
        self.assertIsNone(po.ProjectsOverview(self.db, [], backups=self.d / "missing", now=lambda: NOW).read()[1]["projects"][0]["last_backup_days"])
        (self.d / "afile").write_bytes(b"x")
        self.assertIsNone(po.ProjectsOverview(self.db, [], backups=self.d / "afile", now=lambda: NOW).read()[1]["projects"][0]["last_backup_days"])
        self.assertEqual(po.ProjectsOverview(self.db, [], backups="").backups, Path(""))
        self.assertEqual(po.ProjectsOverview(self.db, [], now=lambda: NOW).backups, self.d / "backups")

    def test_a_file_that_cannot_be_opened_is_busy_in_plain_words(self):
        bad = self.d / "bad.db"
        bad.write_bytes(b"this is not a database" * 50)
        status, got = po.ProjectsOverview(bad, []).read()
        self.assertEqual((status, got["ok"], got["code"], got["message"]), (409, False, "busy", po.MESSAGES["busy"]))

    def test_it_writes_nothing(self):
        self.make("AAA")
        before = self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        self.svc.read()
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0], before)


class Running:
    def __init__(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def get(self, path):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=20)
        try:
            conn.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}")
            conn.putheader(sv.TOKEN_HEADER, sv.TOKEN)
            conn.endheaders()
            r = conn.getresponse()
            return r.status, json.loads(r.read())
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

    def test_it_is_a_get_route_and_answers_the_rows(self):
        self.assertIs(sv.GET_ROUTES["/api/projects-overview"], sv.projects_overview_route)
        self.assertNotIn("/api/projects-overview", sv.POST_ROUTES)
        self.s.httpd.projects_overview = po.ProjectsOverview(self.d / "clark.db", [])
        status, got = self.s.get("/api/projects-overview")
        self.assertEqual((status, [p["code"] for p in got["projects"]]), (200, ["SAM"]))

    def test_without_the_service_not_found_and_a_query_is_refused(self):
        self.assertEqual(self.s.get("/api/projects-overview")[0], 404)
        self.s.httpd.projects_overview = po.ProjectsOverview(self.d / "clark.db", [])
        self.assertEqual(self.s.get("/api/projects-overview?project=SAM")[0], 400)


if __name__ == "__main__":
    unittest.main()

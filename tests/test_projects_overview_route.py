"""Row 1299 slice 2 (R2a): GET /api/projects-overview (src/clark/overview_read.py, routed by server.py). Every test talks to a real server
on a temporary clark file with fictional projects. Run: python3 dev/run_tests.py test_projects_overview_route

Killers written first: each value comes from ITS project (two projects differ in brand, review days, client folder, folders); an empty client
folder is "" and a missing seam is null (never 0, "", False); the folder count is own plus shared, once each, at most 20; archived projects
are counted but never listed; the newest backup's whole days (today 0, a day ago 1, three days ago 3); no work item text and no other project
field leaves the server; nothing is written; a parameter or body is refused; the route sits behind the token and Host checks.
"""
import datetime
import http.client
import json
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401

from clark import app_settings, ask_folders, overview_read, server as sv, store as st

SECRET_ITEM = "Zebra rollout secret item"


class Running:
    def __init__(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path, token=None, host="default", body=None):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest("GET", path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}" if host == "default" else host)
            conn.putheader(sv.TOKEN_HEADER, sv.TOKEN if token is None else token)
            if body is not None:
                conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
            r = conn.getresponse()
            data = r.read()
            try:
                return r.status, json.loads(data)
            except ValueError:
                return r.status, None
        finally:
            conn.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.db = self.d / "clark.db"
        self.store = st.open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Alpha Programme"})
            s.create("projects", {"code": "DEF", "name": "Delta Programme"})
            s.create("projects", {"code": "OLD", "name": "Old Programme"})
            s.update("projects", "ABC", {"brand": "acme", "review_after_days": 30, "publish_client": "/Users/dana/Clients/Alpha"})
            s.archive("projects", "OLD")
        self.folders = ask_folders.AskFolders(self.db, [], data_dir=self.d, by_user=lambda: "tester")
        self.settings = app_settings.AppSettings(self.db, [], by_user=lambda: "tester")
        self.backups = self.d / "backups"
        self.backups.mkdir(exist_ok=True)
        self.s = Running()
        self.addCleanup(self.s.close)
        h = self.s.httpd
        h.projects = self.projects
        h.data_for = self.data_for
        h.ask_folders, h.app_settings = self.folders, self.settings
        h.safety = type("Safe", (), {"folder": self.backups})()
        for f in self.backups.iterdir():                  # opening the store took its own copy; the tests choose the copies
            f.unlink()

    def data_for(self, code):
        mine = st.open_store(self.db, onedrive_roots=[])           # the server answers on its own thread: a store of its own
        try:
            return mine.data_for(code)
        finally:
            mine.close()

    def projects(self, archived=False):
        mine = st.open_store(self.db, onedrive_roots=[])
        try:
            rows = mine.read("projects", archived=bool(archived))
        finally:
            mine.close()
        return [{"code": r["code"], "name": r["name"]} for r in sorted(rows, key=lambda r: r["code"])]

    def backup(self, days_ago, tag="daily"):
        when = st.clock() - datetime.timedelta(days=days_ago)
        (self.backups / f"clark-{when.strftime('%Y%m%dT%H%M%SZ')}-{tag}.db").write_bytes(b"x")

    def own_folder(self, code, path):
        n = self.store.con.execute("SELECT count(*) FROM source_folders WHERE project = ?", (code,)).fetchone()[0]
        self.store.con.execute("INSERT INTO source_folders (project, path, sort_order) VALUES (?, ?, ?)", (code, path, n + 1))     # straight in: the store's own check of a folder is a macOS-only look
        self.store.con.commit()

    def shared(self, paths):
        (self.d / ask_folders.SHARED_FILE).write_text(json.dumps(paths), encoding="utf-8")

    def get(self, **kw):
        return self.s.get("/api/projects-overview", **kw)

    def row(self, code):
        status, got = self.get()
        self.assertEqual(status, 200, got)
        return {r["code"]: r for r in got["projects"]}[code]


class Values(Base):
    def test_each_project_shows_its_own_brand_review_days_and_client_folder(self):
        a, b = self.row("ABC"), self.row("DEF")
        self.assertEqual((a["name"], a["brand"], a["review_days"], a["client_folder"]), ("Alpha Programme", "acme", 30, "/Users/dana/Clients/Alpha"))
        self.assertEqual((b["name"], b["brand"], b["review_days"], b["client_folder"]), ("Delta Programme", "generic", 14, ""))

    def test_no_client_folder_is_an_empty_text_never_null_or_the_other_projects_folder(self):
        self.assertIs(self.row("DEF")["client_folder"], "")
        self.assertNotEqual(self.row("DEF")["client_folder"], self.row("ABC")["client_folder"])

    def test_a_review_days_value_out_of_range_reads_as_the_default(self):
        real = self.data_for
        self.s.httpd.data_for = lambda code: {"project": {**real(code)["project"], "review_after_days": 999}}     # the file refuses 999 itself; a stand-in row gives it
        self.assertEqual(self.row("DEF")["review_days"], 14)

    def test_live_projects_are_listed_and_archived_ones_only_counted(self):
        status, got = self.get()
        self.assertEqual([r["code"] for r in got["projects"]], ["ABC", "DEF"])
        self.assertEqual(got["archived_count"], 1)
        self.assertNotIn("Old Programme", json.dumps(got))

    def test_the_reply_carries_only_the_overview_fields(self):
        status, got = self.get()
        self.assertEqual(set(got), {"ok", "asking", "last_backup", "projects", "archived_count"})
        self.assertEqual(set(got["projects"][0]), {"code", "name", "brand", "review_days", "client_folder", "read_folders"})

    def test_no_work_item_text_leaves_the_server(self):
        with self.store.step("dashboard", "tester", place="menu") as s:
            s.create("actions", {"project": "ABC", "description": SECRET_ITEM, "raised": "2026-11-01", "source": "test"})
        self.assertIn(SECRET_ITEM, json.dumps(self.store.data_for("ABC")), "the fixture must really hold the item")
        status, got = self.get()
        self.assertEqual(status, 200)
        self.assertNotIn(SECRET_ITEM, json.dumps(got))
        self.assertNotIn("sponsor", json.dumps(got))


class Folders(Base):
    def test_the_count_is_own_plus_shared_once_each(self):
        self.own_folder("ABC", "/Users/dana/Notes")
        self.own_folder("ABC", "/Users/dana/Shared")
        self.shared(["/Users/dana/Shared", "/Users/dana/All"])
        self.assertEqual(self.row("ABC")["read_folders"], 3)

    def test_a_shared_folder_counts_for_a_project_with_none_of_its_own(self):
        self.shared(["/Users/dana/All"])
        self.assertEqual((self.row("ABC")["read_folders"], self.row("DEF")["read_folders"]), (1, 1))

    def test_none_at_all_is_zero(self):
        self.assertEqual(self.row("DEF")["read_folders"], 0)

    def test_a_project_counts_its_own_folders_not_another_projects(self):
        self.own_folder("ABC", "/Users/dana/Notes")
        self.assertEqual((self.row("ABC")["read_folders"], self.row("DEF")["read_folders"]), (1, 0))

    def test_the_count_stops_at_twenty(self):
        self.shared([f"/Users/dana/F{n}" for n in range(25)])
        self.assertEqual(self.row("ABC")["read_folders"], overview_read.MAX_FOLDERS)
        self.assertEqual(overview_read.MAX_FOLDERS, ask_folders.MAX_FOLDERS)

    def test_a_refused_folder_read_is_null_even_when_it_carries_folders(self):
        class Refused:
            read = staticmethod(lambda code: (500, {"folders": ["/Users/dana/A"], "shared": []}))
        self.s.httpd.ask_folders = Refused()
        self.assertIsNone(self.row("ABC")["read_folders"])

    def test_without_the_folder_service_the_count_is_null_never_zero(self):
        self.s.httpd.ask_folders = None
        self.assertIsNone(self.row("ABC")["read_folders"])


class Asking(Base):
    def test_the_switch_is_read_as_true_and_false(self):
        self.assertIs(self.get()[1]["asking"], self.store.ask_enabled())
        status, got = self.settings.change_ask({"enabled": not self.store.ask_enabled()})
        if status == 200:
            self.assertIs(self.get()[1]["asking"], self.store.ask_enabled())

    def test_without_the_settings_service_asking_is_null_never_false(self):
        self.s.httpd.app_settings = None
        self.assertIsNone(self.get()[1]["asking"])


class Backup(Base):
    def test_no_backup_is_null_never_today(self):
        self.assertIsNone(self.get()[1]["last_backup"])

    def test_today_is_zero_days(self):
        self.backup(0)
        self.assertEqual(self.get()[1]["last_backup"]["days"], 0)

    def test_one_day_ago_is_one_and_three_days_ago_is_three(self):
        self.backup(1)
        self.assertEqual(self.get()[1]["last_backup"]["days"], 1)
        for f in self.backups.iterdir():
            f.unlink()
        self.backup(3)
        self.assertEqual(self.get()[1]["last_backup"]["days"], 3)

    def test_a_copy_dated_tomorrow_but_believed_is_zero_days_never_minus_one(self):
        now = st.clock().astimezone()
        tomorrow = (now + datetime.timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
        self.backup((now - tomorrow).total_seconds() / 86400)       # tomorrow 00:01 by this computer's clock, under a day ahead
        entries = [e for e in overview_read.backup.entries(self.backups)]
        if not entries or entries[0].ahead:
            self.skipTest("within a minute of midnight: the copy would be too far ahead to be believed")
        self.assertEqual(self.get()[1]["last_backup"]["days"], 0)

    def test_the_newest_copy_counts_not_the_oldest(self):
        self.backup(5)
        self.backup(1)
        self.backup(9, tag="undo")
        self.assertEqual(self.get()[1]["last_backup"]["days"], 1)

    def test_the_when_text_is_the_listing_text(self):
        self.backup(2)
        got = self.get()[1]["last_backup"]
        self.assertRegex(got["when"], r"^\d\d-\d\d-\d{4} \d\d:\d\d$")

    def test_without_the_backup_service_it_is_null(self):
        self.s.httpd.safety = None
        self.assertIsNone(self.get()[1]["last_backup"])


class Safe(Base):
    def test_nothing_is_written(self):
        before = self.store.con.execute("SELECT (SELECT count(*) FROM change_log), (SELECT count(*) FROM applies)").fetchone()
        self.get()
        self.assertEqual(tuple(self.store.con.execute("SELECT (SELECT count(*) FROM change_log), (SELECT count(*) FROM applies)").fetchone()), tuple(before))

    def test_a_parameter_or_a_body_is_refused(self):
        self.assertEqual(self.s.get("/api/projects-overview?project=ABC")[0], 400)
        self.assertEqual(self.s.get("/api/projects-overview", body=b"{}")[0], 400)

    def test_a_wrong_token_or_host_is_refused_like_every_route(self):
        self.assertIn(self.get(token="wrong")[0], (401, 403))
        self.assertIn(self.get(host="evil.example")[0], (400, 403, 421))

    def test_a_project_whose_data_is_gone_is_left_out(self):
        self.s.httpd.data_for = lambda code: None if code == "DEF" else self.data_for(code)
        self.assertEqual([r["code"] for r in self.get()[1]["projects"]], ["ABC"])

    def test_a_project_with_no_readable_fields_has_null_values_never_invented_ones(self):
        self.s.httpd.data_for = lambda code: {}
        r = self.row("ABC")
        self.assertEqual((r["brand"], r["review_days"], r["client_folder"]), (None, None, None))

    def test_a_restore_in_progress_is_a_503(self):
        def busy(archived=False):
            raise sv.Busy("restoring")
        self.s.httpd.projects = busy
        status, got = self.get()
        self.assertEqual((status, got["code"]), (503, "restore_busy"))


if __name__ == "__main__":
    unittest.main()

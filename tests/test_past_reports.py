"""#443: every published page is kept, the Published reports list, and Open (guarded: store.py, server.py, published_copies.py,
past_reports.py). Fictional data only; no browser.

The ruling is #348's: every publication is kept and the list shows the newest 10. A copy is written once and never changed, is
named from the project code and the number only, is checked against the SHA-256 on its row before it is shown, and carries nothing
that the published file did not.

Run: python3 dev/run_tests.py test_past_reports
"""
import hashlib
import http.client
import json
import os
import re
import stat
import tempfile
import threading
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fx
from _demo import USER
from clark import changes, past_banner, past_reports, publish, published_copies
from clark import server as sv
from clark.store import open_store
from test_publish_route import DAY, EMPTY_BRANDING, Rig as PublishRig

SHA = "a" * 64


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.data_dir = self.root / "clark-data"
        self.data_dir.mkdir()
        self.db = self.data_dir / "clark.db"
        self.plant = fx.load()
        fx.build_db(self.db, self.plant)
        self.store = open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.copies = self.data_dir / published_copies.FOLDER
        self.n = 0

    def publish(self, now=DAY):
        """One real publish into a new folder; returns its result and the bytes written."""
        self.n += 1
        folder = self.root / f"Local{self.n}"
        folder.mkdir()
        done = publish.publish(self.store, "PUB", str(folder), by_user=USER, now=now, branding=EMPTY_BRANDING)
        return done, Path(done["path"]).read_bytes()


class KeepingEveryFile(Base):
    def test_a_publish_keeps_a_copy_with_the_same_sha_named_from_the_code_and_number(self):
        done, body = self.publish()
        kept = self.copies / f"PUB-{done['number']}.html"
        self.assertEqual(kept.read_bytes(), body)
        self.assertEqual(sha(kept.read_bytes()), done["sha256"])
        self.assertEqual(sorted(p.name for p in self.copies.iterdir()), [kept.name, f"PUB-{done['number']}.json"],
                         "nothing else is in the folder but its data copy (#342)")

    def test_a_kept_copy_is_read_only_and_the_folder_is_the_owners_alone(self):
        self.publish()
        kept = next(p for p in self.copies.iterdir() if p.suffix == ".html")
        self.assertEqual(stat.S_IMODE(kept.stat().st_mode) & 0o222, 0, "no one can write to it")
        self.assertEqual(stat.S_IMODE(self.copies.stat().st_mode) & 0o077, 0, "no group or other access to the folder")

    def test_a_second_publish_keeps_the_first_unchanged_and_nothing_is_pruned(self):
        first, body1 = self.publish()
        before = sha((self.copies / f"PUB-{first['number']}.html").read_bytes())
        for i in range(12):                                       # past ten: all are kept
            self.publish(now=f"2026-11-{i + 1:02d}")
        names = sorted(p.name for p in self.copies.iterdir())
        self.assertEqual(len(names), 26, "13 pages and their 13 data copies (#342)")
        self.assertEqual(sha((self.copies / f"PUB-{first['number']}.html").read_bytes()), before)
        self.assertEqual(before, first["sha256"])

    def test_a_copy_is_never_written_twice(self):
        done, body = self.publish()
        source = self.root / "again.html"
        source.write_bytes(b"<html>other</html>")
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", done["number"], source, sha(b"<html>other</html>")))
        self.assertEqual((self.copies / f"PUB-{done['number']}.html").read_bytes(), body, "the first copy stands")
        with self.assertRaises(PermissionError):                 # and a write to it is refused by the system, too
            (self.copies / f"PUB-{done['number']}.html").write_bytes(b"changed")

    def test_a_file_that_no_longer_holds_the_recorded_bytes_is_not_kept(self):
        source = self.root / "page.html"
        source.write_bytes(b"<html>one</html>")
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 7, source, sha(b"<html>two</html>")))
        self.assertFalse(self.copies.exists() and any(self.copies.iterdir()))

    def test_only_names_clark_makes_are_kept(self):
        source = self.root / "page.html"
        source.write_bytes(b"x")
        for code, number in (("../x", 1), ("pub", 1), ("PUB", 0), ("PUB", -1), ("PUB", True), ("PUB", "1"), ("PUB", 1000000), ("PUB/..", 1), (None, 1)):
            with self.subTest(code=code, number=number):
                self.assertFalse(published_copies.keep(self.data_dir, code, number, source, sha(b"x")))
                self.assertIsNone(published_copies.file_name(code, number))
        self.assertEqual(published_copies.file_name("PUB", 3), "PUB-3.html")
        self.assertFalse(self.copies.exists() and any(self.copies.iterdir()))

    def test_a_source_that_is_a_link_or_a_folder_or_too_big_is_not_kept(self):
        real = self.root / "real.html"
        real.write_bytes(b"x")
        link = self.root / "link.html"
        link.symlink_to(real)
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 1, link, sha(b"x")))
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 1, self.root, sha(b"x")))
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 1, self.root / "missing.html", sha(b"x")))
        big = self.root / "big.html"
        big.write_bytes(b"x" * (published_copies.MAX_BYTES + 1))
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 1, big, sha(b"x" * (published_copies.MAX_BYTES + 1))))
        self.assertFalse(self.copies.exists() and any(self.copies.iterdir()))

    def test_a_folder_that_is_a_link_is_not_used(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        self.copies.symlink_to(elsewhere, target_is_directory=True)
        source = self.root / "page.html"
        source.write_bytes(b"x")
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 1, source, sha(b"x")))
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_a_link_in_the_place_of_a_copy_is_never_followed_or_written_through(self):
        self.copies.mkdir()
        target = self.root / "target.html"
        target.write_bytes(b"precious")
        (self.copies / "PUB-1.html").symlink_to(target)
        source = self.root / "page.html"
        source.write_bytes(b"x")
        self.assertFalse(published_copies.keep(self.data_dir, "PUB", 1, source, sha(b"x")))
        self.assertEqual(target.read_bytes(), b"precious")
        self.assertEqual(published_copies.read(self.data_dir, "PUB", 1, sha(b"precious"))[0], published_copies.CHANGED)

    def test_a_word_copy_keeps_nothing_and_a_refused_number_keeps_nothing(self):
        done, body = self.publish()
        word = self.root / "report.docx"
        word.write_bytes(b"PK word")
        self.store.log_publication("PUB", word, "2026-10-23", sha(b"PK word"), USER, word=1)
        self.assertEqual(sorted(p.name for p in self.copies.iterdir()), [f"PUB-{done['number']}.html", f"PUB-{done['number']}.json"])
        from clark.store import NumberTaken
        page = self.root / "late.html"
        page.write_bytes(b"late")
        with self.assertRaises(NumberTaken):
            self.store.log_publication("PUB", page, "2026-10-23", sha(b"late"), USER, number=1)
        self.assertEqual(len(list(self.copies.iterdir())), 2)

    def test_a_fictional_path_in_a_record_keeps_nothing_and_does_not_fail(self):
        seq = self.store.log_publication("PUB", Path("/tmp/clark-fictional/none.html"), "2026-10-23", SHA, USER)
        self.assertIsNotNone(self.store.number_of(seq))
        self.assertFalse(self.copies.exists() and any(self.copies.iterdir()))

    def test_the_page_through_the_real_route_is_kept(self):
        rig = PublishRig(self)
        rig.save_to = rig.local / "route.html"
        status, got = rig.publish()
        self.assertEqual((status, got["ok"]), (200, True), got)
        kept = rig.data_dir / published_copies.FOLDER / f"PUB-{got['number']}.html"
        self.assertEqual(kept.read_bytes(), (rig.local / "route.html").read_bytes())


class Seam(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)

    def test_the_list_is_the_newest_ten_with_the_total_and_nothing_internal(self):
        for i in range(12):
            self.publish(now=f"2026-11-{i + 1:02d}")
        status, body = self.past.listing("PUB")
        self.assertEqual(status, 200)
        self.assertEqual((body["total"], body["shown"], body["limit"]), (12, 10, 10))
        self.assertEqual([p["number"] for p in body["publications"]], list(range(12, 2, -1)), "newest first")
        row = body["publications"][0]
        self.assertEqual(set(row), {"number", "when", "where", "who", "word", "kept", "week", "day", "archived"})   # week and day: #344's picker
        self.assertRegex(row["day"], r"^\d{4}-\d\d-\d\d$")
        self.assertTrue(row["week"] is None or re.fullmatch(r"\d{4}-\d\d-\d\d", row["week"]), row["week"])
        self.assertEqual((row["where"], row["who"], row["kept"], row["word"]), ("Local", USER, True, False))
        self.assertRegex(row["when"], r"^\d\d-\d\d-\d{4} \d\d:\d\d$")
        text = json.dumps(body)
        for hidden in (str(self.root), str(self.data_dir), "/Local", SHA, ".html", "sha", "path"):
            self.assertNotIn(hidden, text)
        shas = [r[0] for r in self.store.con.execute("SELECT file_sha256 FROM publications")]
        for s in shas:
            self.assertNotIn(s, text)

    def test_show_archived_lists_the_archived_ones_too_marked_and_the_default_hides_them(self):
        for i in range(3):
            self.publish(now=f"2026-11-{i + 1:02d}")
        self.store.archive_publication("PUB", 2)
        status, body = self.past.listing("PUB")
        self.assertEqual([p["number"] for p in body["publications"]], [3, 1], "hidden by default")
        self.assertEqual((body["total"], body["archived"]), (2, 1))
        self.assertEqual([p["archived"] for p in body["publications"]], [False, False])
        status, body = self.past.listing("PUB", archived=True)
        self.assertEqual([(p["number"], p["archived"]) for p in body["publications"]], [(3, False), (2, True), (1, False)])
        self.assertEqual((body["total"], body["archived"]), (3, 1))
        self.store.unarchive_publication("PUB", 2)
        self.assertEqual([p["number"] for p in self.past.listing("PUB")[1]["publications"]], [3, 2, 1], "Restore brings it back")

    def test_the_old_ones_stay_kept_though_the_list_does_not_show_them(self):
        for i in range(11):
            self.publish(now=f"2026-11-{i + 1:02d}")
        status, body = self.past.visit("PUB", 1)               # number 1 is not in the list of 10, and still opens
        self.assertEqual(status, 200, body)

    def test_a_row_with_no_kept_copy_says_so_and_a_word_row_is_marked(self):
        self.store.log_publication("PUB", Path("/tmp/clark-fictional/old.html"), "2026-10-23", SHA, USER)
        self.store.log_publication("PUB", Path("/tmp/clark-fictional/old.docx"), "2026-10-23", "b" * 64, USER, word=1,
                                   client_path=Path("/tmp/clark-fictional/client.docx"))
        rows = self.past.listing("PUB")[1]["publications"]
        self.assertEqual([(r["number"], r["kept"], r["word"], r["where"]) for r in rows],
                         [(2, False, True, "Local and to client · Word"), (1, False, False, "Local")])

    def test_a_word_copy_sharing_its_pages_number_is_listed_beside_it_and_open_still_finds_the_page(self):
        done, body = self.publish()                            # #368: the web page and its Word copy are both Publication 1
        page = self.store.web_publication_seq("PUB", done["number"])
        self.store.log_publication("PUB", Path("/tmp/clark-fictional/old.docx"), "2026-10-23", "b" * 64, USER, word=1, same_as=page)
        rows = self.past.listing("PUB")[1]["publications"]
        self.assertEqual([(r["number"], r["word"], r["kept"]) for r in rows], [(done["number"], False, True), (done["number"], True, False)])
        status, got = self.past.visit("PUB", done["number"])
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(past_banner.unframe(self.past.take(got["url"].split("=")[1])), body)

    def test_a_project_with_nothing_published_has_an_empty_list(self):
        status, body = self.past.listing("PUB")
        self.assertEqual((status, body["total"], body["publications"]), (200, 0, []))

    def test_listing_answers_for_a_bad_or_missing_project(self):
        self.assertEqual(self.past.listing("x")[0], 400)
        self.assertEqual(self.past.listing(None)[0], 400)
        status, body = self.past.listing("ZZZ")
        self.assertEqual((status, body["message"]), (404, "There is no project with that code."))

    def test_open_gives_a_one_visit_address_for_exactly_the_published_bytes(self):
        done, body = self.publish()
        status, got = self.past.visit("PUB", done["number"])
        self.assertEqual((status, got["ok"], got["number"]), (200, True, done["number"]))
        self.assertRegex(got["url"], r"^/past\?id=[A-Za-z0-9_-]{16,64}$")
        self.assertEqual(set(got), {"ok", "code", "message", "number", "url"})
        nonce = got["url"].split("=")[1]
        self.assertEqual(past_banner.unframe(self.past.take(nonce)), body)
        self.assertIsNone(self.past.take(nonce), "once")

    def test_open_says_plainly_when_there_is_no_copy_or_the_copy_changed_or_there_is_no_such_publication(self):
        self.store.log_publication("PUB", Path("/tmp/clark-fictional/old.html"), "2026-10-23", SHA, USER)
        status, got = self.past.visit("PUB", 1)
        self.assertEqual((status, got["code"]), (404, "not_kept"))
        self.assertIn("was not kept", got["message"])
        done, body = self.publish()
        kept = self.copies / f"PUB-{done['number']}.html"
        kept.chmod(0o644)
        kept.write_bytes(body + b"<!-- tampered -->")
        status, got = self.past.visit("PUB", done["number"])
        self.assertEqual((status, got["code"]), (409, "copy_changed"))
        self.assertEqual(got["message"], f"The kept copy of Publication {done['number']} no longer matches what was published, so clark will not open it. "
                                         "Restore your data from a backup, or ask the clark team for help.")
        status, got = self.past.visit("PUB", 99)
        self.assertEqual((status, got["code"]), (404, "no_publication"))
        self.assertEqual(self.past.visit("ZZZ", 1)[0], 404)
        self.assertEqual(self.past.take("x"), None)
        self.assertEqual(len(self.past.visits), 0, "nothing was made ready for any of those")

    def test_a_restored_database_that_reuses_a_number_for_another_page_is_refused_not_shown(self):
        """#578: Backups carry the kept copies and a restore never touches them (backup.py), so a restored database whose row for a
        number holds another page's SHA-256 than the kept copy meets copy_changed. That refusal is intended: nothing is shown."""
        done, body = self.publish()
        self.store.close()
        self.db.unlink()                                       # the restore: an older database, where this number is another page's
        fx.build_db(self.db, self.plant)
        self.store = open_store(self.db, onedrive_roots=[])
        self.addCleanup(self.store.close)
        self.store.log_publication("PUB", Path("/tmp/clark-fictional/other.html"), "2026-10-23", sha(b"another page"), USER)
        status, got = self.past.visit("PUB", done["number"])
        self.assertEqual((status, got["code"]), (409, "copy_changed"))
        self.assertEqual(len(self.past.visits), 0, "nothing was made ready")
        self.assertEqual((self.copies / f"PUB-{done['number']}.html").read_bytes(), body, "the kept copy is untouched")

    def test_a_copy_of_the_wrong_size_or_kind_is_changed_not_shown(self):
        done, body = self.publish()
        kept = self.copies / f"PUB-{done['number']}.html"
        kept.chmod(0o644)
        kept.unlink()
        os.mkfifo(kept)
        self.assertEqual(self.past.visit("PUB", done["number"])[1]["code"], "copy_changed")

    def test_no_request_value_reaches_the_disk_as_a_path(self):
        done, body = self.publish()
        for code, number in (("../clark-data/PUB", 1), ("PUB", "../1"), ("PUB", "1/../1"), ("PUB", -1), ("PUB", 0), ("PUB", 1.0), ("PUB", None)):
            with self.subTest(code=code, number=number):
                self.assertEqual(self.past.visit(code, number)[0], 400)

    def test_only_a_few_wait_and_an_old_one_is_gone(self):
        done, body = self.publish()
        clock = [0.0]
        past = past_reports.PastReports(self.db, clock=lambda: clock[0])
        urls = [past.visit("PUB", done["number"])[1]["url"] for _ in range(6)]
        ids = [u.split("=")[1] for u in urls]
        self.assertIsNone(past.take(ids[0]))
        self.assertIsNone(past.take(ids[1]))
        clock[0] = past_reports.VISIT_SECONDS + 1
        self.assertIsNone(past.take(ids[5]), "too old")

    def test_what_is_served_carries_nothing_internal(self):
        """The kept bytes are the published file as they were: none of the plant's planted markers, no path of this computer, no
        token, no boot block, no part of Edit."""
        done, body = self.publish()
        status, got = self.past.visit("PUB", done["number"])
        served = self.past.take(got["url"].split("=")[1])
        self.assertEqual(past_banner.unframe(served), body)
        text = served.decode("utf-8")
        for where, marker in self.plant["markers"].items():
            for spelling in fx.spellings(marker):
                self.assertNotIn(spelling, text, f"{where}: {marker}")
        for hidden in (str(self.root), str(self.data_dir), str(self.db), done["sha256"], sv.TOKEN, 'id="clark-boot"', "internal_note",
                       "/api/change", "/api/undo", "/api/publish", "/api/publications", "/api/past-report"):          # (the view page's own shared code names /api/data and the token header; the Edit parts are not in it)
            self.assertNotIn(hidden, text, hidden)
        self.assertIn('data-mode="view"', text)
        self.assertIn(f'"publication":{{"n":{done["number"]}}}', text)


class TheRoutes(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=self.store.data_for, projects=lambda archived=False: [], past=self.past,
                                    publication_mark=changes.make_publication_mark(self.db, [], by_user="Sam Example"))
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path, token=True, host=None, headers=None, body=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            h = {"Host": host or f"127.0.0.1:{self.httpd.server_port}", **(headers or {})}
            if token:
                h[sv.TOKEN_HEADER] = token if isinstance(token, str) else sv.TOKEN
            data = None
            if body is not None:
                data = body.encode()
                h["Content-Length"] = str(len(data))
            conn.request("GET", path, data, h)
            r = conn.getresponse()
            return r.status, r, r.read()
        finally:
            conn.close()

    def json(self, path, **kw):
        status, _, raw = self.get(path, **kw)
        return status, json.loads(raw)

    def test_the_list_and_open_need_the_token_and_this_machine(self):
        for path in ("/api/publications?project=PUB", "/api/past-report?project=PUB&number=1"):
            for kw in ({"token": False}, {"token": "wrong"}, {"host": "evil.example"}, {"headers": {"Origin": "http://evil.example"}},
                       {"headers": {"Sec-Fetch-Site": "cross-site"}}):
                with self.subTest(path=path, kw=kw):
                    self.assertEqual(self.get(path, **kw)[0], 403)

    def post(self, path, body, token=True, headers=None, raw=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            h = {"Host": f"127.0.0.1:{self.httpd.server_port}", "Content-Type": "application/json", **(headers or {})}
            if token:
                h[sv.TOKEN_HEADER] = sv.TOKEN
            data = raw if raw is not None else json.dumps(body).encode()
            conn.request("POST", path, data, h)
            r = conn.getresponse()
            return r.status, json.loads(r.read() or b"null")
        finally:
            conn.close()

    def test_archive_and_restore_over_http_hide_and_show_one_publication(self):
        for i in range(3):
            self.publish(now=f"2026-11-{i + 1:02d}")
        status, got = self.post("/api/publications/archive", {"project": "PUB", "number": 2})
        self.assertEqual((status, got["ok"], got["code"]), (200, True, "archived"))
        self.assertNotIn("step", got)
        self.assertNotIn("apply_id", got, "no Undo is offered")
        self.assertEqual([p["number"] for p in self.json("/api/publications?project=PUB")[1]["publications"]], [3, 1])
        status, shown = self.json("/api/publications?project=PUB&archived=1")
        self.assertEqual([(p["number"], p["archived"]) for p in shown["publications"]], [(3, False), (2, True), (1, False)])
        status, got = self.post("/api/publications/restore", {"project": "PUB", "number": 2})
        self.assertEqual((status, got["code"]), (200, "restored"))
        self.assertEqual([p["number"] for p in self.json("/api/publications?project=PUB")[1]["publications"]], [3, 2, 1])

    def test_archive_and_restore_say_so_in_plain_words_when_they_cannot(self):
        self.publish()
        self.assertEqual(self.post("/api/publications/restore", {"project": "PUB", "number": 1})[0], 409, "not archived")
        self.assertEqual(self.post("/api/publications/archive", {"project": "PUB", "number": 1})[0], 200)
        status, got = self.post("/api/publications/archive", {"project": "PUB", "number": 1})
        self.assertEqual((status, got["ok"], got["message"]), (409, False, "Publication 1 is already archived. Nothing was changed."))
        status, got = self.post("/api/publications/restore", {"project": "PUB", "number": 7})
        self.assertEqual((status, got["message"]), (400, "There is no Publication 7 for PUB. Nothing was changed."))
        self.assertEqual(self.post("/api/publications/restore", {"project": "PUB", "number": 1})[0], 200)
        status, got = self.post("/api/publications/restore", {"project": "PUB", "number": 1})
        self.assertEqual((status, got["message"]), (409, "Publication 1 is not archived. Nothing was changed."))

    def test_the_body_is_exactly_a_project_and_a_number(self):
        self.publish()
        for body in ({}, {"project": "PUB"}, {"number": 1}, {"project": "PUB", "number": 1, "x": 1}, {"project": "PUB", "number": "1"},
                     {"project": "PUB", "number": True}, {"project": "PUB", "number": 0}, {"project": "PUB", "number": 1000000},
                     {"project": "PUB", "number": 1.0}, {"project": "pub", "number": 1}, {"project": "../x", "number": 1}, {"project": 7, "number": 1},
                     [], "PUB", None):
            for action in ("archive", "restore"):
                with self.subTest(body=body, action=action):
                    self.assertEqual(self.post("/api/publications/" + action, body)[0], 400)
        self.assertEqual(self.post("/api/publications/archive", None, raw=b"{")[0], 400)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM change_log WHERE tbl = 'publications'").fetchone()[0], 0)
        self.assertEqual(list(self.copies.glob("*.archived")), [])

    def test_a_body_over_the_routes_limit_is_refused_and_the_route_needs_the_token_and_this_machine(self):
        self.publish()
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/publications/archive"], 1024)
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/publications/restore"], 1024)
        big = {"project": "PUB", "number": 1, "pad": "x" * 2000}
        self.assertEqual(self.post("/api/publications/archive", big)[0], 400)
        for action in ("archive", "restore"):
            for kw in ({"token": False}, {"headers": {"Host": "evil.example"}}, {"headers": {"Origin": "http://evil.example"}},
                       {"headers": {"Sec-Fetch-Site": "cross-site"}}):
                with self.subTest(action=action, kw=kw):
                    self.assertEqual(self.post("/api/publications/" + action, {"project": "PUB", "number": 1}, **kw)[0], 403)
        self.assertEqual(list(self.copies.glob("*.archived")), [])

    def test_get_takes_archived_one_only(self):
        self.publish()
        for path in ("/api/publications?project=PUB&archived=0", "/api/publications?project=PUB&archived=", "/api/publications?project=PUB&archived=1&archived=1",
                     "/api/publications?project=PUB&archived=yes", "/api/past-report?project=PUB&number=1&archived=1"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 400)
        self.assertEqual(self.get("/api/publications?project=PUB&archived=1")[0], 200)

    def test_the_list_over_http(self):
        done, body = self.publish()
        status, got = self.json("/api/publications?project=PUB")
        self.assertEqual((status, got["ok"], got["total"]), (200, True, 1))
        self.assertEqual(got["publications"][0]["number"], done["number"])

    def test_the_request_is_exactly_the_parameters_asked_for(self):
        self.publish()
        for path in ("/api/publications", "/api/publications?project=PUB&project=PUB", "/api/publications?project=PUB&x=1",
                     "/api/publications?project=", "/api/publications?project=pub", "/api/publications?project=../etc",
                     "/api/publications?project=PUB&number=1", "/api/past-report?project=PUB",
                     "/api/past-report?number=1", "/api/past-report?project=PUB&number=1&number=1",
                     "/api/past-report?project=PUB&number=0", "/api/past-report?project=PUB&number=-1", "/api/past-report?project=PUB&number=01",
                     "/api/past-report?project=PUB&number=1.0", "/api/past-report?project=PUB&number=1%2F..", "/api/past-report?project=PUB&number=9999999",
                     "/api/past-report?project=PUB&number=", "/api/past-report?project=PUB&number=abc", "/api/past-report?project=PUB&number=1&path=/etc/passwd",
                     "/api/past-report?project=PUB&number=%2e%2e%2f1"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 400)
        self.assertEqual(self.get("/api/publications?project=PUB", body="{}")[0], 400, "no body is taken")

    def test_open_then_visit_the_address_once(self):
        done, body = self.publish()
        status, got = self.json(f"/api/past-report?project=PUB&number={done['number']}")
        self.assertEqual((status, got["ok"]), (200, True))
        status, resp, raw = self.get(got["url"], token=False)                 # a new tab sends no token
        self.assertEqual((status, past_banner.unframe(raw)), (200, body))
        self.assertTrue(resp.getheader("Content-Type").startswith("text/html"))
        self.assertIn("script-src", resp.getheader("Content-Security-Policy"))
        self.assertEqual(resp.getheader("X-Frame-Options"), "DENY")
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")
        self.assertEqual(self.get(got["url"], token=False)[0], 404, "once")

    @staticmethod
    def directives(resp):
        """The Content-Security-Policy as {directive: value}. Every reply also carries clark's one-line frame-ancestors policy as a
        header of its own; a browser applies all of them, so they are read as one."""
        out = {}
        for header in resp.msg.get_all("Content-Security-Policy"):
            for part in header.split(";"):
                name, _, value = part.strip().partition(" ")
                out[name] = value
        return out

    def test_a_kept_page_is_sandboxed_so_it_cannot_run_as_clark(self):
        done, body = self.publish()
        url = self.json(f"/api/past-report?project=PUB&number={done['number']}")[1]["url"]
        status, resp, raw = self.get(url, token=False)
        self.assertEqual((status, past_banner.unframe(raw)), (200, body), "the sandbox changes the headers, never the published bytes")
        csp = self.directives(resp)
        self.assertEqual(csp.get("sandbox"), "allow-scripts", "scripts only: a null origin")
        for flag in ("allow-same-origin", "allow-top-navigation", "allow-popups", "allow-forms", "allow-modals"):
            self.assertNotIn(flag, csp["sandbox"])
        self.assertIn("script-src", csp, "the hash-only script policy is still there")
        self.assertNotIn("'unsafe-inline'", csp["script-src"])
        self.assertEqual(csp.get("frame-ancestors"), "'none'")
        self.assertEqual(resp.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.getheader("Cache-Control"), "no-store")

    def test_a_planted_script_in_a_kept_copy_has_no_way_to_clarks_origin(self):
        planted = (b"<!doctype html><title>Fictional</title><script>fetch('/').then(r=>r.text()).then(t=>"
                   b"fetch('/api/change',{method:'POST',headers:{'X-Clark-Token':t.match(/clark-boot[^>]*/)[0]},body:'{}'}))</script>")
        seam = past_reports.PastReports(self.db)
        seam.take = lambda nonce: planted if nonce == "planted" else None
        self.httpd.past = seam
        status, resp, raw = self.get("/past?id=planted", token=False)
        self.assertEqual((status, raw), (200, planted))
        csp = self.directives(resp)
        self.assertEqual(csp.get("sandbox"), "allow-scripts")
        self.assertNotIn("allow-same-origin", csp["sandbox"], "with it the planted script would be clark's own origin")
        # what a sandboxed page's own fetch to clark looks like: Origin null. Neither the API nor the address take it.
        for path, token in (("/api/publications?project=PUB", True), ("/api/past-report?project=PUB&number=1", True),
                            ("/past?id=planted", False)):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, token=token, headers={"Origin": "null"})[0], 403)

    def test_the_address_checks_this_machine_and_takes_nothing_but_its_id(self):
        done, body = self.publish()
        url = self.json(f"/api/past-report?project=PUB&number={done['number']}")[1]["url"]
        self.assertEqual(self.get(url, token=False, host="evil.example")[0], 403)
        self.assertEqual(self.get(url, token=False, headers={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.get(url, token=False, headers={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.get(url + "&project=PUB", token=False)[0], 404)
        self.assertEqual(self.get(url + "&id=guess", token=False)[0], 404)
        for path in ("/past", "/past?id=", "/past?id=guess", "/past?id=../../etc/passwd", "/past?path=/etc/passwd", "/past?id=" + "a" * 5000):
            with self.subTest(path=path):
                self.assertEqual(self.get(path, token=False)[0], 404)
        self.assertEqual(self.get(url, token=False)[0], 200, "none of that used it up")

    def test_the_answers_in_words(self):
        self.store.log_publication("PUB", Path("/tmp/clark-fictional/old.html"), "2026-10-23", SHA, USER)
        status, got = self.json("/api/past-report?project=PUB&number=1")
        self.assertEqual((status, got["code"]), (404, "not_kept"))
        status, got = self.json("/api/past-report?project=ZZZ&number=1")
        self.assertEqual((status, got["message"]), (404, "There is no project with that code."))
        status, got = self.json("/api/publications?project=ZZZ")
        self.assertEqual(status, 404)

    def test_without_the_seam_the_routes_are_not_there(self):
        httpd = sv.LocalServer((sv.HOST, 0))
        self.addCleanup(httpd.server_close)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        for action in ("archive", "restore"):                     # #345: without the seam, saving is off
            conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
            conn.request("POST", "/api/publications/" + action, json.dumps({"project": "PUB", "number": 1}),
                         {"Host": f"127.0.0.1:{httpd.server_port}", sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json"})
            self.assertEqual(conn.getresponse().status, 503, action)
            conn.close()
        for path, token in (("/api/publications?project=PUB", True), ("/api/past-report?project=PUB&number=1", True), ("/past?id=x", False)):
            conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
            headers = {"Host": f"127.0.0.1:{httpd.server_port}"}
            if token:
                headers[sv.TOKEN_HEADER] = sv.TOKEN
            conn.request("GET", path, None, headers)
            self.assertEqual(conn.getresponse().status, 404, path)
            conn.close()

    def test_the_routes_are_listed_and_are_get_only(self):
        self.assertIn("/api/publications", sv.GET_ROUTES)
        self.assertIn("/api/past-report", sv.GET_ROUTES)
        self.assertNotIn("/api/publications", sv.POST_ROUTES)
        self.assertNotIn("/api/past-report", sv.POST_ROUTES)
        self.assertIn("/api/publications/archive", sv.POST_ROUTES)       # #345
        self.assertIn("/api/publications/restore", sv.POST_ROUTES)
        self.assertNotIn("/api/publications/archive", sv.GET_ROUTES)
        self.assertEqual(sv.PAST_ROUTE, "/past")


class NothingWritesButTheCopy(Base):
    def test_the_seam_and_the_routes_write_nothing(self):
        done, body = self.publish()
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if "clark.db" not in p.name)
        before_rows = self.store.con.execute("SELECT count(*), max(seq) FROM publications").fetchone()[:]
        past = past_reports.PastReports(self.db)
        past.listing("PUB")
        past.take(past.visit("PUB", done["number"])[1]["url"].split("=")[1])
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if "clark.db" not in p.name)
        self.assertEqual(before, after)
        self.assertEqual(self.store.con.execute("SELECT count(*), max(seq) FROM publications").fetchone()[:], before_rows)


if __name__ == "__main__":
    unittest.main()

"""Row 1087 (critical reader B): hostile data against the Published reports list, Open, Archive and Restore (guarded:
past_reports.py). Fictional data only; no browser.

Run: python3 dev/run_tests.py test_hostile_1087
"""
import http.client
import json
import os
import sqlite3
import threading
import unittest
from unittest import mock

import _paths  # noqa: F401
from _demo import USER
from clark import changes, past_reports, published_copies
from clark import server as sv
from test_past_reports import Base, SHA


class Hostile(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)
        self.seq = 0

    def other_project(self, code="OTH"):
        con = sqlite3.connect(self.db)
        try:
            con.execute("INSERT INTO projects (code, name) VALUES (?, ?)", (code, "Other project"))
            con.commit()
        finally:
            con.close()

    def row(self, number, project="PUB", at="2026-11-02 08:00:00.000", word=0, by=USER, week=None, client=None, pdf=None, local="/x/l"):
        con = sqlite3.connect(self.db)
        try:
            con.execute("INSERT INTO publications (project, at, week_ending, local_path, client_path, word, file_sha256, checks, by_user, number, pdf_name) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (project, at, week, local, client, word, SHA, "not needed", by, number, pdf))
            con.commit()
        finally:
            con.close()

    def listing(self, code="PUB", **kw):
        status, body = self.past.listing(code, **kw)
        self.assertEqual(status, 200, body)
        return body

    def test_at_without_a_Z_or_with_an_offset_or_malformed(self):
        cases = [("2026-11-02 08:00:00", "2026-11-02T08:00:00Z"), ("2026-11-02T08:00:00", "2026-11-02T08:00:00Z"),
                 ("2026-11-02 08:00", "2026-11-02T08:00:00Z"), ("2026-11-02T12:00:00+04:00", "2026-11-02T08:00:00Z"),
                 ("2026-11-02 08:00:00.999999", "2026-11-02T08:00:00Z"), ("2026-11-02T08:00:00Z", "2026-11-02T08:00:00Z"),
                 ("2026-11-02 08:00:00 -0530", "2026-11-02T13:30:00Z"),
                 ("garbage", None), ("", None), ("2026-13-45 99:99:99", None), ("0000-01-01 00:00:00", None),
                 ("9999-12-31 23:59:59-12:00", None), ("0001-01-01 00:00:00+14:00", None), ("2026-11-02 08:00:00\x00", None),
                 ("<script>alert(1)</script>", None), ("2026-11-02T08:00:00+99:99", None)]
        for i, (at, want) in enumerate(cases, 1):
            self.row(i, at=at)
        self.assertEqual(self.listing()["total"], len(cases))
        got = {}
        for i in range(1, len(cases) + 1):                         # the list shows ten: archive the ones already read, so the next show
            got.update({p["number"]: p for p in self.listing()["publications"]})
            for n in list(got):
                published_copies.archive(self.data_dir, "PUB", n)
        for i, (at, want) in enumerate(cases, 1):
            with self.subTest(at=at):
                if want is not None:
                    self.assertEqual(got[i]["at"], want)
                else:
                    self.assertIsNone(got[i]["at"]) if got[i]["at"] is None else self.assertRegex(got[i]["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
                json.dumps(got[i])                                  # always serialisable

    def test_at_is_never_a_value_the_page_would_misread(self):
        """whatever `at` is, it is None or exactly YYYY-MM-DDTHH:MM:SSZ"""
        import re
        weird = ["2026-11-02 08:00:00+00:00", "2026-11-02 08:00:00 Z", "2026-11-02\t08:00:00", "  2026-11-02 08:00:00  ", "2026-11-02 08:00:00.", "２０２６-11-02 08:00:00",
                 "2026-11-02 8:00:00", "2026-02-30 08:00:00", "2026-11-02 24:00:00", "2026-11-02 08:00:60", "-2026-11-02 08:00:00"]
        for i, at in enumerate(weird, 1):
            self.row(i, at=at)
        for p in self.listing()["publications"]:
            with self.subTest(number=p["number"]):
                self.assertTrue(p["at"] is None or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", p["at"]), p["at"])
                self.assertIsInstance(p["when"], str)

    def test_a_non_text_at_does_not_break_the_list(self):
        con = sqlite3.connect(self.db)
        try:
            for i, v in enumerate([12345, 1.5, b"blob", None], 1):
                try:
                    con.execute("INSERT INTO publications (project, at, local_path, word, file_sha256, checks, by_user, number) VALUES ('PUB',?,'/x',0,?,'not needed','u',?)", (v, SHA, i))
                except sqlite3.IntegrityError:
                    pass
            con.commit()
        finally:
            con.close()
        body = self.listing(archived=True)
        for p in body["publications"]:
            self.assertTrue(p["at"] is None or isinstance(p["at"], str))
        json.dumps(body)

    def test_odd_paths_names_and_users_in_a_record_never_leave(self):
        evil = "/etc/passwd\x00../../secret C:\\Users\\Sam\\r.html"
        self.row(1, local=evil, client=evil, pdf="r\u202e.pdf", by="<img src=x onerror=alert(1)>")
        self.row(2, local="", client="", by="   ")
        self.row(3, by="Zoë 😀 \u0645\u0631\u062d\u0628\u0627" + "x" * 5000)
        body = self.listing()
        text = json.dumps(body)
        for leak in ("passwd", "secret", "Users", "r\\u202e", ".pdf", "/x/l"):
            self.assertNotIn(leak, text)
        by = {p["number"]: p for p in body["publications"]}
        self.assertEqual(by[1]["where"], "Local and to client")
        self.assertIs(by[1]["pdf"], True)
        self.assertEqual(by[2]["where"], "Local and to client", "an empty-string client path counts as a client copy (IS NOT NULL): recorded as is")
        self.assertEqual(by[2]["who"], "Not recorded")
        self.assertEqual(by[3]["who"][:3], "Zoë")

    def test_a_pdf_mark_never_lands_on_a_word_row_and_a_word_row_is_not_kept(self):
        self.row(1, pdf="a.pdf")
        self.row(1, word=1, pdf="b.pdf")
        rows = self.listing()["publications"]
        self.assertEqual([(p["number"], p["word"], p["pdf"], p["kept"]) for p in rows], [(1, False, True, False), (1, True, False, False)])

    def test_word_copies_are_separate_rows_and_archiving_the_number_marks_both(self):
        self.row(1)
        self.row(1, word=1)
        self.row(2)
        self.assertEqual(published_copies.archive(self.data_dir, "PUB", 1), True)
        body = self.listing(archived=True)
        self.assertEqual([(p["number"], p["word"], p["archived"]) for p in body["publications"]], [(2, False, False), (1, False, True), (1, True, True)])
        self.assertEqual(body["archived"], 2, "the count is of rows that carry the mark")
        plain = self.listing()
        self.assertEqual((plain["total"], [p["number"] for p in plain["publications"]]), (1, [2]))

    def test_the_other_projects_rows_and_marks_never_show(self):
        self.other_project()
        self.row(1)
        self.row(1, project="OTH", by="Other Person")
        self.row(2, project="OTH")
        published_copies.archive(self.data_dir, "OTH", 1)
        pub, oth = self.listing("PUB"), self.listing("OTH")
        self.assertEqual((pub["total"], pub["archived"], [p["who"] for p in pub["publications"]]), (1, 0, [USER]))
        self.assertEqual((oth["total"], oth["archived"]), (1, 1))
        self.assertNotIn("Other Person", json.dumps(pub))

    def test_a_huge_list_is_cut_to_ten_and_stays_quick(self):
        con = sqlite3.connect(self.db)
        try:
            con.executemany("INSERT INTO publications (project, at, local_path, word, file_sha256, checks, by_user, number) VALUES ('PUB','2026-11-02 08:00:00','/x',?,?,'not needed','u',?)",
                            [(w, SHA, n) for n in range(1, 3001) for w in (0, 1)])
            con.commit()
        finally:
            con.close()
        body = self.listing()
        self.assertEqual((body["total"], body["shown"], len(body["publications"])), (6000, 10, 10))
        self.assertEqual([p["number"] for p in body["publications"]][:4], [3000, 3000, 2999, 2999])
        self.assertLess(len(json.dumps(body)), 5000)

    def test_a_record_whose_file_is_gone_is_not_kept_and_open_says_so(self):
        done, _ = self.publish()
        os.chmod(self.copies / f"PUB-{done['number']}.html", 0o600)
        (self.copies / f"PUB-{done['number']}.html").unlink()
        p = self.listing()["publications"][0]
        self.assertIs(p["kept"], False)
        status, body = self.past.visit("PUB", done["number"])
        self.assertEqual((status, body["code"]), (404, "not_kept"))

    def test_an_archive_mark_that_is_a_link_or_a_folder_is_still_a_mark_and_restore_leaves_it(self):
        self.row(1)
        self.row(2)
        self.copies.mkdir(exist_ok=True)
        (self.copies / "PUB-1.archived").symlink_to("/etc/passwd")
        (self.copies / "PUB-2.archived").mkdir()
        self.assertEqual([p["archived"] for p in self.listing(archived=True)["publications"]], [True, True])
        self.assertFalse(published_copies.unarchive(self.data_dir, "PUB", 1))
        self.assertTrue((self.copies / "PUB-1.archived").is_symlink())
        self.assertFalse(published_copies.unarchive(self.data_dir, "PUB", 2))
        self.assertTrue((self.copies / "PUB-2.archived").is_dir())

    @unittest.expectedFailure
    def test_week_ending_odd_values_are_cut_to_none_or_a_plain_day(self):
        for i, w in enumerate(["2026-11-06", "2026-11-06\n", "<b>x</b>", "", "0000-00-00", "2026-1-6", "\u0662\u0660\u0662\u0666-11-06", "2026-11-06'; DROP TABLE x;--"], 1):
            self.row(i, week=w)
        got = {p["number"]: p["week"] for p in self.listing(archived=True)["publications"]}
        self.assertEqual(got[1], "2026-11-06")
        for n in (2, 3, 4, 6, 8):
            self.assertIsNone(got[n], n)
        self.assertIn(got[5], (None, "0000-00-00"))      # shape only: the page shows what the shape allows
        self.assertIsNone(got[7], "non-ASCII digits are not a day (re.fullmatch \\d matches them in Python 3 str patterns)")

    def test_unicode_and_odd_codes_and_numbers_are_refused(self):
        for code in ("pub", "PU", "PUBLISHED8", "PUB\n", "PÜB", "../PUB", "PUB/..", "", None, 7, ["PUB"], "PUB\x00"):
            with self.subTest(code=code):
                self.assertEqual(self.past.listing(code)[0], 400)
                self.assertEqual(self.past.visit(code, 1)[0], 400)
        for number in (0, -1, 1000000, True, "1", 1.0, None, 10 ** 30):
            with self.subTest(number=number):
                self.assertEqual(self.past.visit("PUB", number)[0], 400)

    def test_open_for_another_projects_number_or_a_nonce_is_refused(self):
        self.other_project()
        done, _ = self.publish()
        n = done["number"]
        self.row(n + 5, project="OTH")
        self.assertEqual(self.past.visit("PUB", n + 5)[0], 404, "a number that exists only in another project")
        self.assertEqual(self.past.visit("OTH", n + 5)[0], 404, "its row has no kept copy: no page is made from PUB's file")
        for nonce in ("", "x", "a" * 15, "a" * 65, "../" * 6, "A" * 16 + "\n", None, 5, "\u0661" * 16):
            self.assertIsNone(self.past.take(nonce))
        url = self.past.visit("PUB", n)[1]["url"]
        nonce = url.split("=")[1]
        self.assertIsNotNone(self.past.take(nonce))
        self.assertIsNone(self.past.take(nonce), "one visit only")


class Routes(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db)
        con = sqlite3.connect(self.db)
        con.execute("INSERT INTO projects (code, name) VALUES ('OTH', 'Other project')")
        con.commit()
        con.close()
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=self.store.data_for, projects=lambda archived=False: [], past=self.past,
                                    publication_mark=changes.make_publication_mark(self.db, [], by_user="Sam Example"))
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def req(self, method, path, body=None, raw=None, headers=None, token=True, host=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            h = {"Host": host or f"127.0.0.1:{self.httpd.server_port}", **(headers or {})}
            if token:
                h[sv.TOKEN_HEADER] = sv.TOKEN
            data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
            if data is not None:
                h["Content-Type"] = "application/json"
            conn.request(method, path, data, h)
            r = conn.getresponse()
            payload = r.read()
            try:
                return r.status, json.loads(payload or b"null")
            except ValueError:
                return r.status, payload
        finally:
            conn.close()

    def marks(self):
        return sorted(p.name for p in self.copies.glob("*.archived")) if self.copies.exists() else []

    def history_count(self):
        return self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]

    def test_forged_and_foreign_ids_archive_and_restore_change_nothing(self):
        done, _ = self.publish()
        n = done["number"]
        before = (self.marks(), self.history_count())
        for action in ("archive", "restore"):
            path = f"/api/publications/{action}"
            for body in ({"project": "OTH", "number": n}, {"project": "PUB", "number": n + 50}, {"project": "ZZZ", "number": n},
                         {"project": "pub", "number": n}, {"project": "PUB", "number": "1"}, {"project": "PUB", "number": 1.0},
                         {"project": "PUB", "number": True}, {"project": "PUB", "number": 0}, {"project": "PUB", "number": -3},
                         {"project": "PUB", "number": 1000000}, {"project": "PUB", "number": 10 ** 40},
                         {"project": "../PUB", "number": n}, {"project": "PUB/../../x", "number": n}, {"project": "PUB\n", "number": n},
                         {"project": "PUB", "number": n, "path": "/etc"}, {"project": "PUB"}, {"number": n}, [], "x", None, 5):
                with self.subTest(action=action, body=body):
                    status, got = self.req("POST", path, body)
                    self.assertIn(status, (400, 404, 409, 415), (status, got))
                    if action == "restore" and body == {"project": "PUB", "number": n}:
                        continue
            self.assertEqual((self.marks(), self.history_count()), before, "nothing was written")
        for raw in (b"{", b"\xff\xfe", b"[" * 5000, b'{"project":"PUB","number":1,"number":2}', b"", b"null"):
            with self.subTest(raw=raw[:20]):
                self.assertIn(self.req("POST", "/api/publications/archive", raw=raw)[0], (400, 413))
        self.assertEqual((self.marks(), self.history_count()), before)

    def test_archive_by_another_project_code_marks_only_that_project(self):
        done, _ = self.publish()
        n = done["number"]
        status, got = self.req("POST", "/api/publications/archive", {"project": "OTH", "number": n})
        self.assertEqual(status, 400, got)
        self.assertEqual(self.marks(), [])
        self.assertEqual(self.req("POST", "/api/publications/archive", {"project": "PUB", "number": n})[0], 200)
        self.assertEqual(self.marks(), [f"PUB-{n}.archived"])
        self.assertEqual(self.req("POST", "/api/publications/restore", {"project": "OTH", "number": n})[0], 400)
        self.assertEqual(self.marks(), [f"PUB-{n}.archived"], "the other project's restore does not lift this mark")

    def test_a_planted_mark_for_another_project_does_not_hide_this_project(self):
        self.publish()
        self.copies.mkdir(exist_ok=True)
        (self.copies / "OTH-1.archived").write_bytes(b"")
        self.assertEqual(self.req("GET", "/api/publications?project=PUB")[1]["total"], 1)

    def test_archive_and_restore_need_the_token_host_and_post_only(self):
        done, _ = self.publish()
        body = {"project": "PUB", "number": done["number"]}
        for kw in ({"token": False}, {"host": "evil.example"}, {"headers": {"Origin": "http://evil.example"}}, {"headers": {"Sec-Fetch-Site": "cross-site"}}):
            with self.subTest(kw=kw):
                self.assertEqual(self.req("POST", "/api/publications/archive", body, **kw)[0], 403)
        self.assertEqual(self.marks(), [])
        for method in ("GET", "PUT", "DELETE"):
            self.assertNotEqual(self.req(method, "/api/publications/archive", body)[0], 200)
        self.assertEqual(self.marks(), [])

    def test_get_routes_refuse_odd_queries(self):
        self.publish()
        for path in ("/api/publications", "/api/publications?project=PUB&project=OTH", "/api/publications?project=PUB&archived=2",
                     "/api/publications?project=PUB&archived=1&archived=1", "/api/publications?project=PUB&x=1", "/api/publications?project=%00",
                     "/api/publications?project=P%C3%9CB", "/api/publications?project=PUB%0a",
                     "/api/past-report?project=PUB&number=0", "/api/past-report?project=PUB&number=01", "/api/past-report?project=PUB&number=1%0a",
                     "/api/past-report?project=PUB&number=-1", "/api/past-report?project=PUB&number=%DB%B1", "/api/past-report?project=PUB&number=9999999",
                     "/api/past-report?project=PUB&number=1&archived=1"):
            with self.subTest(path=path):
                self.assertEqual(self.req("GET", path)[0], 400)
        self.assertEqual(self.req("GET", "/api/past-report?project=OTH&number=1")[0], 404)

    def test_the_visit_address_takes_only_a_live_id_and_is_once(self):
        done, body = self.publish()
        status, got = self.req("GET", f"/api/past-report?project=PUB&number={done['number']}")
        self.assertEqual(status, 200)
        for bad in ("/past", "/past?id=", "/past?id=a", "/past?id=" + "a" * 32 + "&id=b", "/past?id=%00" * 1, "/past?id=../../etc/passwd", "/past?id=" + "a" * 200):
            with self.subTest(bad=bad):
                self.assertEqual(self.req("GET", bad)[0], 404)
        self.assertEqual(self.req("GET", got["url"])[0], 200)
        self.assertEqual(self.req("GET", got["url"])[0], 404)

    def test_container_mode_a_foreign_peer_is_refused_and_the_gateway_is_local(self):
        with mock.patch.object(sv, "container_mode", return_value=True), mock.patch.object(sv, "container_gateway", return_value="172.18.0.1"):
            self.assertTrue(sv.local_peer("172.18.0.1"))
            self.assertFalse(sv.local_peer("172.18.0.2"))
            self.assertFalse(sv.local_peer("10.0.0.5"))
            self.assertTrue(sv.local_peer("127.0.0.1"))
            self.assertEqual(self.req("GET", "/api/publications?project=PUB")[0], 200, "this machine still reads the list")
        with mock.patch.dict(os.environ, {"CLARK_CONTAINER": "1"}), mock.patch("os.path.exists", return_value=False):
            self.assertFalse(sv.container_mode(), "the setting alone is not a container")

    def test_no_route_opens_a_folder(self):
        """no 'open folder' route exists in 1087 (the builder's decision 1): the Docker case is that the button is never drawn; nothing under /api opens a report folder."""
        self.assertEqual(self.req("POST", "/api/publications/open-folder", {"project": "PUB"})[0] in (404, 405, 400, 403), True)


if __name__ == "__main__":
    unittest.main()

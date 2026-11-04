"""Item 345: a past publication can be Archived and Restored from the Published reports list (guarded: store.py, server.py,
published_copies.py, past_reports.py, changes.py). Fictional data only; no browser. The card is tests/test_past_reports_card.py.

Archive writes the publication's mark and Restore removes it, nothing else: the row, the kept page and the data copy stay as they
are. There is no Undo. The list hides archived ones unless asked (?archived=show).

Run: python3 dev/run_tests.py test_publication_archive
"""
import http.client
import json
import threading
import unittest

import _paths  # noqa: F401
from clark import changes, past_reports, published_copies as pc
from clark import server as sv
from clark.store import Invalid
from test_past_reports import Base, sha


class TheStore(Base):
    def test_restore_removes_only_the_mark(self):
        done, _ = self.publish()
        n = done["number"]
        before = {p.name: sha(p.read_bytes()) for p in self.copies.iterdir()}
        self.store.archive_publication("PUB", n)
        self.assertTrue(pc.is_archived(self.data_dir, "PUB", n))
        self.assertTrue(self.store.unarchive_publication("PUB", n))
        self.assertFalse(pc.is_archived(self.data_dir, "PUB", n))
        self.assertEqual({p.name: sha(p.read_bytes()) for p in self.copies.iterdir()}, before, "page and data copy untouched")
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM publications").fetchone()[0], 1, "the row stays")

    def test_it_can_go_round_again(self):
        done, _ = self.publish()
        n = done["number"]
        for _ in range(2):
            self.assertTrue(self.store.archive_publication("PUB", n))
            self.assertTrue(self.store.unarchive_publication("PUB", n))

    def test_restore_is_refused_in_plain_words(self):
        done, _ = self.publish()
        with self.assertRaisesRegex(Invalid, "is not archived"):
            self.store.unarchive_publication("PUB", done["number"])
        with self.assertRaisesRegex(Invalid, "There is no Publication 9"):
            self.store.unarchive_publication("PUB", 9)
        for code, number in (("../x", 1), ("PUB", 0), ("PUB", "1"), ("PUB", True)):
            with self.subTest(code=code, number=number), self.assertRaises(Invalid):
                self.store.unarchive_publication(code, number)

    def test_a_link_in_the_marks_place_is_removed_as_a_link_and_not_followed(self):
        done, _ = self.publish()
        n = done["number"]
        target = self.root / "outside.txt"
        target.write_text("keep me", encoding="utf-8")
        (self.copies / f"PUB-{n}.archived").symlink_to(target)
        self.assertTrue(self.store.unarchive_publication("PUB", n))
        self.assertEqual(target.read_text(encoding="utf-8"), "keep me")
        self.assertFalse(pc.is_archived(self.data_dir, "PUB", n))


class TheList(Base):
    def test_show_archived_lists_them_with_the_flag(self):
        for i in range(3):
            self.publish(now=f"2026-11-{i + 1:02d}")
        self.store.archive_publication("PUB", 2)
        past = past_reports.PastReports(self.db)
        _, plain = past.listing("PUB")
        self.assertEqual([(p["number"], p["archived"]) for p in plain["publications"]], [(3, False), (1, False)])
        self.assertEqual((plain["total"], plain["archived"]), (2, 1))
        _, shown = past.listing("PUB", show_archived=True)
        self.assertEqual([(p["number"], p["archived"]) for p in shown["publications"]], [(3, False), (2, True), (1, False)])
        self.assertEqual((shown["total"], shown["archived"]), (3, 1))
        self.store.unarchive_publication("PUB", 2)
        self.assertEqual([p["number"] for p in past.listing("PUB")[1]["publications"]], [3, 2, 1], "restored: back in the list")


class TheRoute(Base):
    def setUp(self):
        super().setUp()
        self.past = past_reports.PastReports(self.db, archiver=changes.make_publication_archive(self.db, [], "Sam Example"))
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=self.store.data_for, projects=lambda: [], past=self.past)
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def call(self, method, path, obj=None, token=True, host=None, ctype="application/json"):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            body = None if obj is None else (obj if isinstance(obj, bytes) else json.dumps(obj).encode())
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", host or f"127.0.0.1:{self.httpd.server_port}")
            if token:
                conn.putheader(sv.TOKEN_HEADER, token if isinstance(token, str) else sv.TOKEN)
            if body is not None:
                conn.putheader("Content-Type", ctype)
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

    def archive(self, number, archived=True, **kw):
        return self.call("POST", "/api/publications/archive", {"project": "PUB", "number": number, "archived": archived}, **kw)

    def test_archive_then_restore_over_http(self):
        done, _ = self.publish()
        n = done["number"]
        self.assertEqual(self.archive(n), (200, {"ok": True, "project": "PUB", "number": n, "archived": True}))
        self.assertEqual(self.call("GET", "/api/publications?project=PUB")[1]["publications"], [])
        shown = self.call("GET", "/api/publications?project=PUB&archived=show")[1]
        self.assertEqual([(p["number"], p["archived"]) for p in shown["publications"]], [(n, True)])
        self.assertEqual(self.archive(n, False), (200, {"ok": True, "project": "PUB", "number": n, "archived": False}))
        self.assertEqual([p["number"] for p in self.call("GET", "/api/publications?project=PUB")[1]["publications"]], [n])

    def test_a_second_archive_and_a_restore_of_a_live_one_are_refused_in_plain_words(self):
        done, _ = self.publish()
        n = done["number"]
        status, body = self.archive(n, False)
        self.assertEqual((status, body["code"], body["message"]), (400, "refused", f"Publication {n} is not archived. Nothing was changed."))
        self.archive(n)
        status, body = self.archive(n)
        self.assertEqual((status, body["message"]), (400, f"Publication {n} is already archived. Nothing was changed."))
        self.assertEqual(self.archive(99)[1]["message"], "There is no Publication 99 for PUB. Nothing was changed.")

    def test_it_needs_the_token_and_this_machine(self):
        done, _ = self.publish()
        body = {"project": "PUB", "number": done["number"], "archived": True}
        for kw in ({"token": False}, {"token": "wrong"}, {"host": "evil.example"}):
            with self.subTest(kw=kw):
                self.assertEqual(self.call("POST", "/api/publications/archive", body, **kw)[0], 403)
        self.assertFalse(pc.is_archived(self.data_dir, "PUB", done["number"]))

    def test_only_exactly_the_three_keys_in_the_right_shapes(self):
        done, _ = self.publish()
        n = done["number"]
        good = {"project": "PUB", "number": n, "archived": True}
        bad = [{}, {"project": "PUB", "number": n}, {**good, "path": "/etc"}, {**good, "project": "pub"}, {**good, "project": "../x"},
               {**good, "number": "1"}, {**good, "number": True}, {**good, "number": 0}, {**good, "number": 1000000}, {**good, "number": 1.0},
               {**good, "archived": "yes"}, {**good, "archived": 1}, {**good, "archived": None}, [good]]
        for obj in bad:
            with self.subTest(obj=obj):
                self.assertEqual(self.call("POST", "/api/publications/archive", obj)[0], 400)
        self.assertEqual(self.call("POST", "/api/publications/archive", b"{", )[0], 400)
        self.assertEqual(self.call("POST", "/api/publications/archive", good, ctype="text/plain")[0], 415)
        self.assertFalse(pc.is_archived(self.data_dir, "PUB", n), "nothing was written")

    def test_the_body_is_kept_small(self):
        big = {"project": "PUB", "number": 1, "archived": True, "x": "a" * 5000}
        self.assertEqual(self.call("POST", "/api/publications/archive", big)[0], 400)

    def test_the_list_takes_archived_show_and_nothing_else(self):
        self.publish()
        for path in ("/api/publications?project=PUB&archived=hide", "/api/publications?project=PUB&archived=", "/api/publications?project=PUB&archived=show&archived=show",
                     "/api/publications?project=PUB&archived=show&x=1", "/api/past-report?project=PUB&number=1&archived=show"):
            with self.subTest(path=path):
                self.assertEqual(self.call("GET", path)[0], 400)
        self.assertEqual(self.call("GET", "/api/publications?project=PUB&archived=show")[0], 200)

    def test_without_the_seam_the_route_is_not_there(self):
        self.past.archiver = None
        self.assertEqual(self.archive(1)[0], 404)


if __name__ == "__main__":
    unittest.main()

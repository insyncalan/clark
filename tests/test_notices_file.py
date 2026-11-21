"""Row 1046, piece 3: the notices file set in Settings, read for the bell (src/clark/notices_file.py, settings.notices_path, GET /api/notices).

Run: python3 dev/run_tests.py test_notices_file
No browser. Every place and notice here is made up in a temporary folder.
"""
import http.client
import json
import locale
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import notices_file, server as sv, settings

ONE = {"id": "upgrade-1", "severity": "info", "title": "Upgrade available", "body": "Version 1.2 is ready.", "date": "2026-11-16"}


class Place(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.data.mkdir()
        self.addCleanup(self.tmp.cleanup)

    def put(self, name, value, raw=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if raw else json.dumps(value), encoding="utf-8")
        return path


class SettingTest(Place):
    def test_none_until_set(self):
        self.assertIsNone(settings.notices_path(self.data))

    def test_set_keeps_other_settings_and_turns_off(self):
        settings.set_backups_kept(self.data, 7)
        got = settings.set_notices_path(self.data, str(self.root / "notices.json"))
        self.assertEqual(got, self.root / "notices.json")
        self.assertEqual(settings.notices_path(self.data), self.root / "notices.json")
        self.assertEqual(settings.backups_kept(self.data), 7)
        self.assertIsNone(settings.set_notices_path(self.data, "  "))
        self.assertIsNone(settings.notices_path(self.data))
        self.assertEqual(settings.backups_kept(self.data), 7)

    def test_the_place_need_not_exist_and_is_never_made(self):
        away = self.root / "share" / "notices.json"
        settings.set_notices_path(self.data, str(away))
        self.assertFalse(away.parent.exists())

    def test_not_a_full_path_is_refused_in_plain_words(self):
        for bad in ("notices.json", "../x", "~/n.json", "/a\nb", 5, "/" + "x" * 1001):
            with self.assertRaises(ValueError) as e:
                settings.set_notices_path(self.data, bad)
            self.assertTrue(str(e.exception).endswith("Nothing was changed."))
        self.assertIsNone(settings.notices_path(self.data))

    def test_an_unreadable_settings_file_is_never_replaced(self):
        (self.data / settings.FILE).write_text("not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            settings.set_notices_path(self.data, str(self.root / "n.json"))
        self.assertEqual((self.data / settings.FILE).read_text(encoding="utf-8"), "not json")

    def test_a_bad_saved_value_reads_as_not_set(self):
        for bad in (7, "relative.json", "", ["/x"], "/a\x00b", "/" + "x" * 1001):
            (self.data / settings.FILE).write_text(json.dumps({"notices_path": bad}), encoding="utf-8")
            self.assertIsNone(settings.notices_path(self.data))


class ReaderTest(Place):
    def test_a_list_and_an_object_with_notices(self):
        self.assertEqual(notices_file.read_place(self.put("a.json", [ONE])), [ONE])
        self.assertEqual(notices_file.read_place(self.put("b.json", {"notices": [ONE]})), [ONE])

    def test_a_folder_reads_json_files_by_name_and_ignores_the_rest(self):
        two = dict(ONE, id="refresh-1")
        self.put("n/2.json", [two])
        self.put("n/1.json", [ONE])
        self.put("n/readme.txt", "x", raw=True)
        self.assertEqual(notices_file.read_place(self.root / "n"), [ONE, two])

    def test_a_folder_stops_at_30_files(self):
        for i in range(40):
            self.put(f"n/{i:02d}.json", [dict(ONE, id=f"i{i}")])
        self.assertEqual(len(notices_file.read_place(self.root / "n")), notices_file.MAX_FILES)

    def test_bad_files_give_nothing_and_no_error(self):
        self.assertEqual(notices_file.read_place(self.put("bad.json", "{oops", raw=True)), [])
        self.assertEqual(notices_file.read_place(self.put("num.json", "5", raw=True)), [])
        self.assertEqual(notices_file.read_place(self.put("mixed.json", [ONE, 3, "x", None])), [ONE])
        self.assertEqual(notices_file.read_place(self.root / "missing.json"), [])

    def test_a_large_file_and_a_symlink_are_not_read(self):
        big = self.put("big.json", json.dumps([dict(ONE, body="x" * notices_file.FILE_LIMIT)]), raw=True)
        self.assertEqual(notices_file.read_place(big), [])
        link = self.root / "link.json"
        link.symlink_to(self.put("real.json", [ONE]))
        self.assertEqual(notices_file.read_place(link), [])

    def test_the_place_is_never_changed(self):
        path = self.put("a.json", [ONE])
        before = (path.read_bytes(), path.stat().st_mtime_ns, sorted(p.name for p in self.root.iterdir()))
        notices_file.read_within(path)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns, sorted(p.name for p in self.root.iterdir())))

    def test_a_place_that_does_not_answer_is_given_up_on(self):
        def slow(_):
            time.sleep(2)
            return [ONE]
        with mock.patch.object(notices_file, "read_place", slow):
            start = time.monotonic()
            got = notices_file.read_within(self.root, timeout=0.2)
        self.assertEqual(got, ([], "away"))
        self.assertLess(time.monotonic() - start, 1.0)

    def test_nan_and_infinity_are_never_handed_out(self):
        for i, raw in enumerate(('[{"a": NaN}]', '[{"id": "x", "body": Infinity}]', '[{"id": "x", "body": -Infinity}]', '[{"id": "x", "n": 1e999}]', '[{"id": "x", "n": -1e999}]')):
            self.assertEqual(notices_file.read_place(self.put(f"nan{i}.json", raw, raw=True)), [], raw)
        settings.set_notices_path(self.data, str(self.put("nan.json", '[{"a": NaN}]', raw=True)))
        status, body = notices_file.Notices(self.data).read()
        json.loads(json.dumps(body, allow_nan=False))      # strict: would raise on NaN or Infinity

    def test_only_the_fields_the_page_uses_are_kept_and_each_is_cut(self):
        rich = dict(ONE, expires="2030-01-01", test={"installedBelow": "1.2", "junk": 1},
                    action={"label": "Open", "to": "/settings", "junk": 1}, junk={"deep": [1, 2]}, other="x")
        want = dict(ONE, expires="2030-01-01", test={"installedBelow": "1.2"}, action={"label": "Open", "to": "/settings"})
        self.assertEqual(notices_file.read_place(self.put("r.json", [rich])), [want])
        self.assertEqual(notices_file.FIELD_MAX, 1000)
        long = "y" * 12000      # five of them still fit in a file under FILE_LIMIT
        got = notices_file.read_place(self.put("l.json", [dict(ONE, body=long, title=long, test={"installedBelow": long}, action={"label": long, "to": long})]))[0]
        self.assertEqual(len(got["body"]), 1000)
        self.assertEqual(len(got["title"]), 1000)
        self.assertEqual((len(got["test"]["installedBelow"]), len(got["action"]["label"]), len(got["action"]["to"])), (1000, 1000, 1000))
        self.assertEqual(notices_file.read_place(self.put("t.json", [dict(ONE, title=5, body=None, test=3, action="x")])), [{"id": ONE["id"], "severity": "info", "date": ONE["date"]}])

    def test_the_limits_are_these_numbers(self):
        self.assertEqual((notices_file.FILE_LIMIT, notices_file.MAX_NOTICES, notices_file.MAX_FILES, notices_file.TIMEOUT), (65536, 200, 30, 3.0))

    def test_a_file_of_exactly_the_limit_is_read_one_byte_more_is_not(self):
        base = json.dumps([dict(ONE, body="")])
        for extra, want in ((0, [dict(ONE, body="x" * 0)]), (1, [])):
            pad = notices_file.FILE_LIMIT - len(base) + extra
            raw = json.dumps([dict(ONE, body="x" * pad)])
            self.assertEqual(len(raw.encode()), notices_file.FILE_LIMIT + extra)
            got = notices_file.read_place(self.put(f"edge{extra}.json", raw, raw=True))
            self.assertEqual(len(got), 1 - extra)

    def test_deeply_nested_json_gives_nothing(self):
        self.assertEqual(notices_file.read_place(self.put("deep.json", "[" * 30000 + "]" * 30000, raw=True)), [])

    def test_at_most_200_notices_from_a_folder_and_from_a_file(self):
        many = [dict(ONE, id=f"i{i}") for i in range(250)]
        small = [{"id": f"i{i}"} for i in range(250)]
        self.assertEqual(len(notices_file.read_place(self.put("one.json", small))), 200)
        for i in range(10):
            self.put(f"f/{i}.json", [{"id": f"f{i}-{j}"} for j in range(30)])
        self.assertEqual(len(notices_file.read_place(self.root / "f")), 200)
        self.assertEqual(len(many), 250)

    def test_only_json_files_in_a_folder_are_read(self):
        self.put("m/a.json", [ONE])
        self.put("m/b.txt", [dict(ONE, id="txt")])
        self.put("m/c", [dict(ONE, id="none")])
        self.put("m/d.json.bak", [dict(ONE, id="bak")])
        self.assertEqual(notices_file.read_place(self.root / "m"), [ONE])

    def test_a_utf8_file_is_read_as_utf8_whatever_the_locale(self):
        one = dict(ONE, title="Caf\u00e9 \u2014 \u65e5\u672c\u8a9e")
        path = self.root / "u.json"
        path.write_bytes(json.dumps([one], ensure_ascii=False).encode("utf-8"))
        with mock.patch.object(locale, "getpreferredencoding", lambda *a, **k: "cp1252"), \
             mock.patch("io.text_encoding", lambda enc, *a: "cp1252" if enc is None else enc, create=True):
            self.assertEqual(notices_file.read_place(path), [one])

    def test_a_read_that_outlives_the_timeout_is_given_up_and_the_thread_is_a_daemon(self):
        gate = threading.Event()
        seen = []
        def slow(_):
            seen.append(threading.current_thread())
            gate.wait(5)
            return [ONE]
        with mock.patch.object(notices_file, "read_place", slow):
            got = notices_file.read_within(self.root, timeout=0.2)
        self.assertEqual(got, ([], "away"))
        self.assertTrue(seen[0].daemon)
        gate.set()
        seen[0].join(2)

    def test_a_read_that_just_finished_late_in_time_is_still_not_given_up_when_it_answered(self):
        with mock.patch.object(notices_file, "read_place", lambda _: [ONE]):
            self.assertEqual(notices_file.read_within(self.root, timeout=1), ([ONE], "ok"))


class SeamTest(Place):
    def test_why_words(self):
        seam = notices_file.Notices(self.data, timeout=1)
        self.assertEqual(seam.read(), (200, {"ok": True, "why": "off", "notices": []}))
        settings.set_notices_path(self.data, str(self.root / "a.json"))
        self.assertEqual(seam.read()[1]["why"], "none")
        self.put("a.json", [ONE])
        self.assertEqual(seam.read(), (200, {"ok": True, "why": "ok", "notices": [ONE]}))


class RouteTest(Place):
    def ask(self, method, path, seam, body=None, token=True):
        httpd = sv.LocalServer((sv.HOST, 0), notices=seam)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close()))
        conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
        headers = {"Host": f"127.0.0.1:{httpd.server_port}"}
        if token:
            headers[sv.TOKEN_HEADER] = sv.TOKEN
        conn.request(method, path, body=body, headers=headers)
        r = conn.getresponse()
        data = r.read()
        conn.close()
        return r.status, data

    def test_get_answers_the_notices(self):
        settings.set_notices_path(self.data, str(self.put("a.json", [ONE])))
        status, data = self.ask("GET", "/api/notices", notices_file.Notices(self.data))
        self.assertEqual((status, json.loads(data)), (200, {"ok": True, "why": "ok", "notices": [ONE]}))

    def test_get_tells_the_installed_version(self):
        old = sv.VERSION
        sv.VERSION = "1.2.3"
        self.addCleanup(lambda: setattr(sv, "VERSION", old))
        status, data = self.ask("GET", "/api/notices", notices_file.Notices(self.data))
        self.assertEqual((status, json.loads(data)["installed"]), (200, "1.2.3"))

    def test_without_the_seam_it_is_not_found(self):
        self.assertEqual(self.ask("GET", "/api/notices", None)[0], 404)

    def test_the_token_is_needed_and_a_query_is_refused(self):
        seam = notices_file.Notices(self.data)
        self.assertEqual(self.ask("GET", "/api/notices", seam, token=False)[0], 403)
        self.assertEqual(self.ask("GET", "/api/notices?path=/etc", seam)[0], 400)

    def test_a_body_on_the_get_is_refused(self):
        seam = notices_file.Notices(self.data)
        httpd = sv.LocalServer((sv.HOST, 0), notices=seam)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close()))
        head = f"GET /api/notices HTTP/1.1\r\nHost: 127.0.0.1:{httpd.server_port}\r\n{sv.TOKEN_HEADER}: {sv.TOKEN}\r\nConnection: close\r\n"
        for extra, body in (("Content-Length: 2\r\n", b"{}"), ("Transfer-Encoding: chunked\r\n", b"2\r\n{}\r\n0\r\n\r\n")):
            with socket.create_connection((sv.HOST, httpd.server_port), timeout=10) as conn:
                conn.sendall((head + extra + "\r\n").encode() + body)
                reply = b""
                while chunk := conn.recv(4096):
                    reply += chunk
            self.assertTrue(reply.startswith(b"HTTP/1.1 400") or reply.startswith(b"HTTP/1.0 400"), (extra, reply[:60]))

    def test_post_is_not_a_route(self):
        self.assertNotEqual(self.ask("POST", "/api/notices", notices_file.Notices(self.data), body=b"{}")[0], 200)


if __name__ == "__main__":
    unittest.main()

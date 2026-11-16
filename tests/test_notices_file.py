"""Row 1046, piece 3: the notices file set in Settings, read for the bell (src/clark/notices_file.py, settings.notices_path, GET /api/notices).

Run: python3 dev/run_tests.py test_notices_file
No browser. Every place and notice here is made up in a temporary folder.
"""
import http.client
import json
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
        for bad in (7, "relative.json", "", ["/x"]):
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

    def test_without_the_seam_it_is_not_found(self):
        self.assertEqual(self.ask("GET", "/api/notices", None)[0], 404)

    def test_the_token_is_needed_and_a_query_is_refused(self):
        seam = notices_file.Notices(self.data)
        self.assertEqual(self.ask("GET", "/api/notices", seam, token=False)[0], 403)
        self.assertEqual(self.ask("GET", "/api/notices?path=/etc", seam)[0], 400)

    def test_post_is_not_a_route(self):
        self.assertNotEqual(self.ask("POST", "/api/notices", notices_file.Notices(self.data), body=b"{}")[0], 200)


if __name__ == "__main__":
    unittest.main()

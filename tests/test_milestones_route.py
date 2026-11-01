"""#146: GET /api/milestones (src/clark/server.py, guarded) and its feed (src/clark/milestone_feed.py): the rows the Calendar and
its list draw, read only. No browser. Run: PYTHONPATH=../src python3 test_milestones_route.py"""
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401

import _publish_fixture as fx
from clark import milestone_feed as feed
from clark import milestone_rows as mr
from clark import server as sv
from clark.store import open_store

ON = "2026-10-28"
INTERNAL = "PLANTED-INTERNAL-NOTE-5521"
REASON = "PLANTED-REASON-5522"


def row(**kw):
    base = {"id": "DEMO-M-001", "name": "Pilot live", "status": "Planned", "client_visible": 1, "archived": 0}
    base.update(kw)
    return base


def rows_for_feed():
    return [
        row(id="DEMO-M-001", baseline_date="2026-10-28", owner="Sam Lee", internal_note=INTERNAL,
            description="DESCRIPTION-5523", client_message="CLIENT-5524", movement="hold"),
        row(id="DEMO-M-002", name="Training done", baseline_date="2026-11-05", forecast_date="2026-12-09", state_reason=REASON),
        row(id="DEMO-M-003", name="Contract signed", baseline_date="2026-08-14", status="Done", actual_date="2026-08-20"),
        row(id="DEMO-M-004", name="Old one", baseline_date="2026-08-14", archived=1),
        row(id="DEMO-M-005", name="Later plan", forecast_date="2027-02-01", state="Forecast", state_set=1, client_visible=0),
    ]


class Feed(unittest.TestCase):
    def test_a_project_with_only_archived_milestones_gives_an_empty_list(self):
        got = feed.editor_rows({"milestones": [row(id="DEMO-M-009", baseline_date="2026-08-14", archived=1)]}, ON)
        self.assertEqual(got["milestones"], [])

    def test_only_the_page_fields_leave(self):
        got = feed.editor_rows({"milestones": rows_for_feed(), "workstreams": []}, ON)
        self.assertEqual(got["as_at"], ON)
        for m in got["milestones"]:
            self.assertEqual(set(m), set(feed.PAGE_FIELDS))
        text = json.dumps(got)
        for planted in (INTERNAL, REASON, "DESCRIPTION-5523", "CLIENT-5524", "hold"):
            self.assertNotIn(planted, text)

    def test_the_rows_are_milestone_rows_cut_down_in_its_order_without_archived_ones(self):
        data = {"milestones": rows_for_feed()}
        full = mr.milestone_rows(data["milestones"], ON)
        got = feed.editor_rows(data, ON)["milestones"]
        self.assertEqual([m["id"] for m in got], [m["id"] for m in full])
        self.assertNotIn("DEMO-M-004", [m["id"] for m in got])
        for a, b in zip(got, full):
            self.assertEqual(a, {k: b[k] for k in feed.PAGE_FIELDS})
        words = {m["id"]: (m["state"], m["owner"], m["client_visible"]) for m in got}
        self.assertEqual(words["DEMO-M-001"], ("On track", "Sam Lee", True))
        self.assertEqual(words["DEMO-M-002"][0], "Slipped")
        self.assertEqual(words["DEMO-M-005"][2], False)

    def test_dates_stay_in_the_stored_form_for_the_page_to_show(self):
        got = feed.editor_rows({"milestones": rows_for_feed()}, ON)["milestones"]
        by = {m["id"]: m for m in got}
        self.assertEqual((by["DEMO-M-002"]["baseline"], by["DEMO-M-002"]["forecast"]), ("2026-11-05", "2026-12-09"))
        self.assertEqual(by["DEMO-M-003"]["achieved"], "2026-08-20")

    def test_a_missing_project_gives_none(self):
        seen = []
        self.assertIsNone(feed.make_feed(lambda code: seen.append(code) or None)("NOPE"))
        self.assertEqual(seen, ["NOPE"])

    def test_the_real_store_feeds_it_and_a_client_hidden_row_is_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = open_store(fx.build_db(Path(tmp) / "clark.db"), onedrive_roots=[])
            try:
                got = feed.make_feed(store.data_for)("PUB")
            finally:
                store.close()
        by = {m["id"]: m for m in got["milestones"]}
        self.assertEqual(by["PUB-M-003"]["client_visible"], False)
        self.assertEqual(by["PUB-M-001"]["client_visible"], True)
        self.assertNotIn("internal_note", json.dumps(got))


class Rig:
    def __init__(self, case, seam=True):
        self.body = {"as_at": ON, "milestones": [{"id": "DEMO-M-001", "name": "Pilot live"}]}
        self.calls = []
        read = (lambda code: self.calls.append(code) or (self.body if code == "DEMO" else None)) if seam else None
        self.httpd = sv.LocalServer((sv.HOST, 0), milestones=read)
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        case.addCleanup(self.close)

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def call(self, path, method="GET", token=True, host=None, origin=None, body=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            headers = {"Host": host or f"127.0.0.1:{self.httpd.server_port}"}
            if token:
                headers[sv.TOKEN_HEADER] = sv.TOKEN
            if origin:
                headers["Origin"] = origin
            data = None
            if body is not None:
                data = body.encode()
                headers["Content-Length"] = str(len(data))
            conn.request(method, path, data, headers)
            r = conn.getresponse()
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
        finally:
            conn.close()


class Route(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)

    def test_it_is_a_get_route_only(self):
        self.assertIn("/api/milestones", sv.GET_ROUTES)
        self.assertNotIn("/api/milestones", sv.POST_ROUTES)
        status, _ = self.rig.call("/api/milestones?project=DEMO", method="POST", body="{}")
        self.assertNotEqual(status, 200)
        self.assertEqual(self.rig.calls, [])

    def test_the_shape(self):
        status, got = self.rig.call("/api/milestones?project=DEMO")
        self.assertEqual((status, got), (200, {"ok": True, "project": "DEMO", **self.rig.body}))

    def test_token_host_and_origin_are_checked_before_the_read(self):
        for kw in ({"token": False}, {"host": "example.com"}, {"origin": "http://example.com"}):
            status, _ = self.rig.call("/api/milestones?project=DEMO", **kw)
            self.assertEqual(status, 403, kw)
        self.assertEqual(self.rig.calls, [])

    def test_a_bad_code_extra_parameter_or_body_is_400_and_nothing_is_read(self):
        for bad in ("", "?project=", "?project=abc", "?project=A", "?project=DEMO%0A", "?project=../x", "?project=DEMO&x=1",
                    "?project=DEMO&project=DEMO", "?other=DEMO"):
            status, got = self.rig.call("/api/milestones" + bad)
            self.assertEqual((status, got["code"]), (400, "bad_project_code"), bad)
        status, got = self.rig.call("/api/milestones?project=DEMO", body="{}")
        self.assertEqual((status, got["code"]), (400, "bad_request"))
        self.assertEqual(self.rig.calls, [])

    def test_an_unknown_project_is_404_in_plain_words(self):
        status, got = self.rig.call("/api/milestones?project=NOPE")
        self.assertEqual((status, got["code"], got["message"]), (404, "project_not_found", sv.MESSAGES["project_not_found"]))

    def test_a_very_long_request_line_is_refused_and_nothing_is_read(self):
        # a GET has no body limit of its own: the standard library's 64 KiB request line is the only size limit (414)
        conn = http.client.HTTPConnection(sv.HOST, self.rig.httpd.server_port, timeout=20)
        try:
            conn.request("GET", "/api/milestones?project=DEMO&" + "a" * 70000,
                         headers={"Host": f"127.0.0.1:{self.rig.httpd.server_port}", sv.TOKEN_HEADER: sv.TOKEN})
            self.assertEqual(conn.getresponse().status, 414)
        finally:
            conn.close()
        self.assertEqual(self.rig.calls, [])

    def test_a_long_extra_parameter_is_400_and_nothing_is_read(self):
        status, got = self.rig.call("/api/milestones?project=DEMO&" + "a" * 2048)
        self.assertEqual((status, got["code"]), (400, "bad_project_code"))
        self.assertEqual(self.rig.calls, [])

    def test_without_the_seam_it_is_404(self):
        rig = Rig(self, seam=False)
        status, got = rig.call("/api/milestones?project=DEMO")
        self.assertEqual((status, got["code"]), (404, "not_found"))

    def test_the_route_builds_no_path_from_the_request(self):
        text = Path(sv.__file__).read_text(encoding="utf-8")
        body = text.split("def milestones_route")[1].split("ARCHIVED_VIEWS")[0]
        for word in ("open(", "Path(", "os.path", "read_text"):
            self.assertNotIn(word, body)


if __name__ == "__main__":
    unittest.main()

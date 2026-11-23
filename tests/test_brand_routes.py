"""#944 T2: the brand routes in src/clark/server.py (guarded). RED until the routes exist.

The routes: GET /api/brands (the installed list), POST /api/brands/review, /install, /remove, /undo. The server hands each to its
`brands` seam (an object with listing(), review(body), install(body), remove(body), undo(body), each answering (status, body),
as the `updater` seam does); without one the routes answer 503. The page never sends a path: the file comes from the system
dialog or Downloads, so a "path" field in a body must never reach the seam. Rig as tests/test_server_movement.py.

Run: python3 dev/run_tests.py test_brand_routes
"""
import http.client
import json
import sys
import threading
import traceback
import unittest

from clark import server as sv

POSTS = ("/api/brands/review", "/api/brands/install", "/api/brands/remove", "/api/brands/undo")
BODIES = {"/api/brands/review": {"from": "downloads"}, "/api/brands/install": {"review_id": "r1"},
          "/api/brands/remove": {"id": "example-brand"}, "/api/brands/undo": {}}
SEAM = {"/api/brands/review": "review", "/api/brands/install": "install", "/api/brands/remove": "remove", "/api/brands/undo": "undo"}


class FakeLibrary:
    def __init__(self):
        self.calls = []
        self.listed = 0

    def listing(self):
        self.listed += 1
        return 200, {"ok": True, "brands": [{"id": "example-brand", "name": "Example Brand", "version": "1.0.0"}]}

    def _answer(self, what, body):
        self.calls.append((what, body))
        return 200, {"ok": True}

    def review(self, body):
        return self._answer("review", body)

    def install(self, body):
        return self._answer("install", body)

    def remove(self, body):
        return self._answer("remove", body)

    def undo(self, body):
        return self._answer("undo", body)


class Rig:
    def __init__(self, case, library=True, trace=False):
        self.trace = trace
        self.server_errors = []
        self.library = FakeLibrary() if library else None
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=lambda *a, **k: {}, projects=lambda archived=False: [],
                                    page_html=lambda *a, **k: "<!doctype html><title>t</title>", brands=self.library)
        self.httpd.handle_error = self._print_error if trace else (lambda *a: None)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        case.addCleanup(self.close)

    def _print_error(self, request, client_address):
        # trace=True only (row 1559 diagnostic): a handler crash prints its traceback to stderr and is kept for the failure message.
        text = traceback.format_exc()
        self.server_errors.append(text)
        sys.stderr.write("SERVER HANDLER ERROR (client %s):\n%s\n" % (client_address, text))
        sys.stderr.flush()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def call(self, method, path, body=None, token="good", raw=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            headers = {"Host": "127.0.0.1:%d" % self.httpd.server_port}
            if token == "good":
                headers[sv.TOKEN_HEADER] = sv.TOKEN
            elif token:
                headers[sv.TOKEN_HEADER] = token
            data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
            if data is not None:
                headers["Content-Length"] = str(len(data))
                headers["Content-Type"] = "application/json"
            try:
                conn.request(method, path, data, headers)
                r = conn.getresponse()
                text = r.read()
            except (ConnectionError, http.client.RemoteDisconnected) as e:
                if not self.trace:
                    raise
                raise AssertionError("%s on %s %s: %r; server traceback(s) captured: %s" % (
                    type(e).__name__, method, path, e, "\n".join(self.server_errors) or "none")) from e
            try:
                return r.status, json.loads(text)
            except ValueError:
                return r.status, text
        finally:
            conn.close()


    def call_declared(self, method, path, length, token="good"):
        """Row 1235: a request that declares a body of `length` bytes and sends none of it. The server refuses on the declared length alone, so this
        reads its 400 on every system; a client that sends the whole body while the server answers and closes gets a reset on macOS, and no reply."""
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            conn.putrequest(method, path, skip_host=True)
            conn.putheader("Host", "127.0.0.1:%d" % self.httpd.server_port)
            if token == "good":
                conn.putheader(sv.TOKEN_HEADER, sv.TOKEN)
            conn.putheader("Content-Length", str(length))
            conn.putheader("Content-Type", "application/json")
            conn.endheaders()
            r = conn.getresponse()
            return r.status, json.loads(r.read())
        finally:
            conn.close()


class Routes(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)

    def test_the_list_and_every_post_answer_through_the_seam(self):
        status, got = self.rig.call("GET", "/api/brands")
        self.assertEqual((status, got["ok"]), (200, True))
        self.assertEqual(got["brands"][0]["id"], "example-brand")
        for path in POSTS:
            with self.subTest(path):
                status, got = self.rig.call("POST", path, BODIES[path])
                self.assertEqual((status, got), (200, {"ok": True}))
        self.assertEqual([c[0] for c in self.rig.library.calls], [SEAM[p] for p in POSTS])
        self.assertEqual(self.rig.library.calls[1][1], BODIES["/api/brands/install"])

    def test_no_token_or_a_bad_one_is_refused_and_nothing_changes(self):
        for token, want in ((None, 403), ("wrong", 403)):
            for path in POSTS:
                with self.subTest(path=path, token=token):
                    status, got = self.rig.call("POST", path, BODIES[path], token=token)
                    self.assertEqual(status, want)
                    self.assertFalse(got["ok"])
            status, _ = self.rig.call("GET", "/api/brands", token=token)
            self.assertEqual(status, want)
        self.assertEqual(self.rig.library.calls, [])
        self.assertEqual(self.rig.library.listed, 0)

    def test_a_body_over_the_limit_is_refused_400_too_large_like_every_other_route_and_the_seam_never_hears(self):
        for path in POSTS:
            with self.subTest(path):
                status, body = self.rig.call_declared("POST", path, 100_001)      # row 1235: over every route's limit; see call_declared
                self.assertEqual(status, 400)
                self.assertEqual(body.get("code"), "too_large")
        self.assertEqual(self.rig.library.calls, [])

    def test_the_limits_are_in_the_table_and_small(self):
        for path in POSTS:
            self.assertIn(path, sv.ROUTE_BODY_LIMITS, path)
            self.assertLessEqual(sv.ROUTE_BODY_LIMITS[path], 8 * 1024, path)

    def test_a_path_in_the_body_never_reaches_the_seam(self):
        for path in POSTS:
            with self.subTest(path):
                self.rig.library.calls.clear()
                status, got = self.rig.call("POST", path, dict(BODIES[path], path="/etc/passwd"))
                if status == 200:
                    self.assertTrue(all("path" not in body for _, body in self.rig.library.calls), self.rig.library.calls)
                else:
                    self.assertIn(status, (400, 422))
                    self.assertEqual(self.rig.library.calls, [])

    def test_a_body_that_is_not_json_or_not_an_object_is_a_plain_400(self):
        for raw in (b"{nope", b"[1, 2]", b'"text"'):
            with self.subTest(raw):
                status, got = self.rig.call("POST", "/api/brands/review", raw=raw)
                self.assertEqual(status, 400)
        self.assertEqual(self.rig.library.calls, [])

    def test_an_unknown_review_id_is_the_seams_refusal_passed_on_whole(self):
        self.rig.library.install = lambda body: (409, {"ok": False, "code": "expired", "message": "A plain sentence."})
        status, got = self.rig.call("POST", "/api/brands/install", {"review_id": "nope"})
        self.assertEqual((status, got["code"], got["message"]), (409, "expired", "A plain sentence."))

    def test_the_page_request_does_not_scan_the_library(self):
        for path in ("/", "/index.html"):
            self.rig.call("GET", path, token=None)
        self.assertEqual(self.rig.library.listed, 0, "the list is read by the Settings call, never per page request")
        self.rig.call("GET", "/api/brands")
        self.assertEqual(self.rig.library.listed, 1)

    def test_only_the_right_methods(self):
        self.assertEqual(self.rig.call("GET", "/api/brands/review")[0] in (404, 405), True)
        self.assertEqual(self.rig.call("POST", "/api/brands", {})[0] in (404, 405), True)
        self.assertEqual(self.rig.library.calls, [])


class WithoutALibrary(unittest.TestCase):
    def test_every_route_says_503(self):
        rig = Rig(self, library=False)
        self.assertEqual(rig.call("GET", "/api/brands")[0], 503)
        for path in POSTS:
            self.assertEqual(rig.call("POST", path, BODIES[path])[0], 503, path)


if __name__ == "__main__":
    unittest.main()

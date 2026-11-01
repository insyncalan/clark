"""A progress tracker over the REAL change route with the REAL store (#247; src/clark/server.py SECTION_BODY_LIMIT, guarded; #273 moved a section's content to /api/section-body): the
widest tracker the checker accepts is not stopped by the route's size limit, one line over the checker's cap is answered with the
checker's own words, a request over the route's limit gets the general words, and two writers leave exactly one whole body.

Run: python3 dev/run_tests.py test_tracker_route
"""
import http.client
import json
import threading
import unittest

from _demo import USER, DemoStore
from clark import changes, section_bodies as sb, server as sv
from clark.store import BODY_RULES
from test_tracker_content import biggest, check, line

KIND = "report_sections"
LETTERS = ("a", '"', "\\", "é", "中", "\U00010400")      # plain, escaped twice, accented, CJK, and the four-byte worst case


class Running:
    """A server on a free port in a thread (the same Handler and routes as the real one), with the change seam it is given."""

    def __init__(self, change, undo):
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for={}.get, page_html=None, projects=lambda: [], change=change, undo=undo)
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def api(self, method, path, body):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=30)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for k, v in ((("Host", f"127.0.0.1:{self.port}"), (sv.TOKEN_HEADER, sv.TOKEN), ("Content-Type", "application/json"),
                          ("Content-Length", str(len(body))))):
                conn.putheader(k, v)
            conn.endheaders(body)
            r = conn.getresponse()
            return r.status, r.msg, r.read()
        finally:
            conn.close()


def request(ref, body, ascii_only=True):
    """The bytes a page sends to save a tracker: the body is a string of JSON inside the request, so it is escaped twice."""
    inner = json.dumps(body, ensure_ascii=ascii_only, separators=(",", ":")) if not isinstance(body, str) else body
    return json.dumps({"project": "ABC", "id": ref, "body": inner},
                      ensure_ascii=ascii_only, separators=(",", ":")).encode("utf-8")


class Route(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.running = Running(change=changes.make_change(self.store.path, [], USER), undo=changes.make_undo(self.store.path, [], USER))
        self.addCleanup(self.running.close)
        status, _, data = self.running.api("POST", "/api/change", json.dumps(
            {"project": "ABC", "kind": KIND, "op": "new", "values": {"type": "tracker", "title": "Progress"}}).encode())
        self.assertEqual(status, 200, data)
        self.ref = json.loads(data)["ref"]
        self.running.httpd.section_body = changes.make_section_body(self.store.path, [], USER)

    def post(self, body, route="/api/section-body"):
        status, _, data = self.running.api("POST", route, body)
        return status, json.loads(data)

    def stored(self):
        return self.store.read(KIND, ref=self.ref)["body"]

    def over_the_cap(self, letter="a"):
        tracker = biggest(letter)
        tracker["groups"][0]["lines"].append(line())             # one line more than TRACKER_MAX_LINES
        return tracker

    def test_the_widest_tracker_in_every_kind_of_letter_is_not_stopped_by_the_route_limit(self):
        for letter in LETTERS:
            for ascii_only in (True, False):
                with self.subTest(letter=letter, ascii_only=ascii_only):
                    body = request(self.ref, biggest(letter), ascii_only)
                    self.assertLess(len(body), sv.SECTION_BODY_LIMIT)                     # room to spare, so the checker is what answers
                    status, got = self.post(body)
                    self.assertEqual((status, got["ok"]), (200, True), got)
                    self.assertEqual(self.stored(), check(biggest(letter)))

    def test_a_tracker_at_the_checkers_cap_is_saved_and_one_line_over_gets_the_checkers_own_words(self):
        status, got = self.post(request(self.ref, biggest()))
        self.assertEqual((status, got["ok"]), (200, True), got)
        kept = self.stored()
        self.assertEqual(sum(len(g["lines"]) for g in json.loads(kept)["groups"]), sb.TRACKER_MAX_LINES)
        for letter in LETTERS:
            with self.subTest(letter=letter):
                status, got = self.post(request(self.ref, self.over_the_cap(letter)))
                self.assertEqual((status, got["ok"], got["message"]), (400, False, sb.TRACKER_TOO_MANY_LINES))
                self.assertNotEqual(got.get("code"), "too_large")                         # not the route's general reply
                self.assertNotEqual(got["message"], sv.MESSAGES["change_too_large"])
                self.assertEqual(self.stored(), kept)                                     # nothing was written

    def test_a_request_over_the_route_limit_still_gets_the_general_words_and_nothing_else_is_let_through_larger(self):
        for pad in (sv.SECTION_BODY_LIMIT, sv.SECTION_BODY_LIMIT + 1):
            raw = b'{"project":"ABC","id":"' + self.ref.encode() + b'","body":"' + b"x" * pad + b'"}'
            status, got = self.post(raw)
            self.assertEqual((status, got["code"], got["message"]), (400, "too_large", sv.MESSAGES["change_too_large"]))
        self.assertEqual(self.stored(), "")

    def test_a_17_kb_change_that_is_not_a_tracker_is_the_stores_to_refuse_not_a_larger_door_for_trackers(self):
        before = self.store.read(KIND, ref=self.ref)
        raw = json.dumps({"project": "ABC", "kind": KIND, "op": "update", "id": self.ref, "changes": {"title": "x" * 17 * 1024}}).encode()
        status, got = self.post(raw, "/api/change")
        self.assertEqual((status, got["ok"], got["code"]), (400, False, "too_large"))        # /api/change is 16 KB: no door for a section's content
        self.assertEqual(self.store.read(KIND, ref=self.ref), before)

    def test_the_route_limit_still_covers_the_widest_tracker_with_room_to_spare(self):
        widest = max(len(request(self.ref, biggest(letter), ascii_only)) for letter in LETTERS for ascii_only in (True, False))
        self.assertGreater(sv.SECTION_BODY_LIMIT, widest)
        self.assertGreaterEqual(sv.SECTION_BODY_LIMIT, widest + 4 * 1024)       # the envelope (project, place, ids) is far smaller than 4 KB
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/section-body"], sv.SECTION_BODY_LIMIT)
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/change"], sv.CHANGE_BODY_LIMIT)
        for route, limit in (("/api/undo", 1024), ("/api/sneak/read", 4 * 1024), ("/api/profile", 2 * 1024), ("/api/draft-email", 16 * 1024)):
            self.assertEqual(sv.ROUTE_BODY_LIMITS[route], limit, route)

    def padded(self, size):
        """A valid JSON change body of exactly `size` bytes: the title is padded with plain letters."""
        head = b'{"project":"ABC","kind":"report_sections","op":"update","id":"' + self.ref.encode() + b'","changes":{"title":"'
        tail = b'"}}'
        raw = head + b"x" * (size - len(head) - len(tail)) + tail
        self.assertEqual(len(raw), size)
        json.loads(raw)
        return raw

    def test_a_body_of_exactly_the_route_limit_is_let_in_and_refused_for_another_reason(self):
        before = self.store.read(KIND, ref=self.ref)
        status, got = self.post(self.padded(sv.CHANGE_BODY_LIMIT))
        self.assertEqual((status, got["ok"]), (400, False))                 # the store refuses a title this long
        self.assertNotEqual(got.get("code"), "too_large")
        self.assertNotEqual(got["message"], sv.MESSAGES["change_too_large"])
        self.assertEqual(self.store.read(KIND, ref=self.ref), before)

    def test_a_body_of_one_byte_over_the_route_limit_gets_the_general_words(self):
        before = self.store.read(KIND, ref=self.ref)
        status, got = self.post(self.padded(sv.CHANGE_BODY_LIMIT + 1))
        self.assertEqual((status, got["code"], got["message"]), (400, "too_large", sv.MESSAGES["change_too_large"]))
        self.assertEqual(self.store.read(KIND, ref=self.ref), before)

    def test_two_writers_on_one_tracker_leave_one_whole_body_and_the_cap_cannot_be_passed(self):
        first, second = biggest("a"), biggest("b")
        second["groups"][0]["name"] = "Second"
        mine, theirs = request(self.ref, first), request(self.ref, second)
        over = request(self.ref, self.over_the_cap())
        answers, gate = [], threading.Barrier(6)

        def write(raw):
            gate.wait()
            answers.append(self.post(raw))

        threads = [threading.Thread(target=write, args=(raw,)) for raw in (mine, theirs, over, mine, theirs, over)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(len(answers), 6)
        self.assertEqual(sorted(s for s, _ in answers), [200, 200, 200, 200, 400, 400])      # the over-cap writes fail whole
        self.assertEqual({g["message"] for s, g in answers if s == 400}, {sb.TRACKER_TOO_MANY_LINES})
        kept = self.stored()
        self.assertIn(kept, (check(first), check(second)))                   # exactly one of them, never a mixture
        self.assertEqual(sum(len(g["lines"]) for g in json.loads(kept)["groups"]), sb.TRACKER_MAX_LINES)
        # sequentially the last write wins
        for body in (first, second, first):
            self.assertEqual(self.post(request(self.ref, body))[0], 200)
        self.assertEqual(self.stored(), check(first))
        self.assertEqual(self.post(request(self.ref, self.over_the_cap()))[0], 400)
        self.assertEqual(self.stored(), check(first))


if __name__ == "__main__":
    unittest.main()

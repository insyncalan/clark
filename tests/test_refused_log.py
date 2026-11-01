"""#234: every reply to a request that authorised() did not let in is counted, never a log line of its own.

Run: python3 dev/run_tests.py test_refused_log
A page on another site, or anything else on this machine, can loop requests at clark's port. Before this, a 403 was counted
but a doubled Host or Content-Length (400), an unknown method (501) or an oversized header (431) still wrote one line each, so
the day's ordinary lines could still be filled. Each test runs a real server on a free port with a temporary log folder and
a fixed clock for the counter (server.Refused), so the minute is moved on without waiting or editing the counter's state.
"""
import http.client
import io
import logging
import re
import shutil
import socket
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  puts src/ on the path
from clark import log as clog, server as sv

NOW = datetime(2030, 1, 1, 9, 0, 0)
MARK = "ZQREFUSEDMARK"
FLOOD = 30
SUMMARY = re.compile(r" WARN  server +(\d+) requests were turned away and not logged one by one$")


def planted(handler, req):
    raise RuntimeError("a planted fault")


class Refusals(unittest.TestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-refused-")).resolve()
        self.addCleanup(shutil.rmtree, folder, True)
        self.log = clog.Log(folder / "logs", data=folder, clock=lambda: NOW,
                            routes=set(sv.GET_ROUTES) | set(sv.POST_ROUTES) | {"/api/planted-fault"})
        handler = clog.install(self.log)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        self.ticks = [500.0]
        for p in (mock.patch.object(sv, "REFUSED", sv.Refused(clock=lambda: self.ticks[0])),
                  mock.patch.dict(sv.POST_ROUTES, {"/api/planted-fault": planted})):
            p.start()
            self.addCleanup(p.stop)
        self.httpd = sv.LocalServer((sv.HOST, 0), projects=lambda: [])
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.host = f"127.0.0.1:{self.httpd.server_port}".encode()

    def raw(self, method, path, headers=(), body=b""):
        """Send one request as raw bytes (so a header can be doubled or oversized) and give the reply's status."""
        head = [f"{method} {path} HTTP/1.1".encode()] + [k + b": " + v for k, v in headers]
        with socket.create_connection((sv.HOST, self.httpd.server_port), timeout=10) as s:
            try:
                s.sendall(b"\r\n".join(head) + b"\r\n\r\n" + body)
            except OSError:
                pass                                    # the server may answer and close before an oversized header is sent
            data = b""
            try:
                while chunk := s.recv(65536):
                    data += chunk
            except ConnectionResetError:
                pass
        return int(data.split(b"\r\n", 1)[0].split()[1])

    def ours(self, *extra):
        return ((b"Host", self.host), (sv.TOKEN_HEADER.encode(), sv.TOKEN.encode())) + extra

    def kinds(self):
        """(name, status, request) for every way a request is turned away before it is let in. Each carries MARK."""
        q = f"/api/projects?q={MARK}"
        host, token = (b"Host", self.host), (sv.TOKEN_HEADER.encode(), sv.TOKEN.encode())
        json_body = ((b"Content-Type", b"application/json"), (b"Content-Length", b"2"))
        return [
            ("no token", 403, lambda: self.raw("GET", q, (host,))),
            ("wrong token", 403, lambda: self.raw("GET", q, (host, (sv.TOKEN_HEADER.encode(), MARK.encode())))),
            ("other Origin", 403, lambda: self.raw("GET", q, self.ours((b"Origin", f"http://{MARK}.example".encode())))),
            ("wrong Host", 403, lambda: self.raw("GET", q, ((b"Host", f"{MARK}.example".encode()), token))),
            ("OPTIONS", 403, lambda: self.raw("OPTIONS", q, self.ours())),
            ("doubled Host", 400, lambda: self.raw("GET", q, self.ours((b"Host", f"{MARK}.example".encode())))),
            ("doubled Content-Length", 400, lambda: self.raw("POST", f"/api/change?q={MARK}",
                                                              self.ours(*json_body, (b"Content-Length", b"3")), b"{}")),
            ("PUT", 501, lambda: self.raw("PUT", q, self.ours(*json_body), b"{}")),
            ("DELETE", 501, lambda: self.raw("DELETE", q, self.ours())),
            ("oversized header", 431, lambda: self.raw("GET", q, self.ours((b"X-" + MARK.encode(), b"a" * 70000)))),
        ]

    def entries(self):
        """The log's entries (a traceback's indented lines belong to the entry above)."""
        text = "".join(p.read_text(encoding="utf-8") for p in self.log.files())
        return [x for x in text.splitlines() if clog.ENTRY.match(x)], text

    def fault(self):
        status = self.raw("POST", "/api/planted-fault", self.ours((b"Content-Type", b"application/json"),
                                                                  (b"Content-Length", b"2")), b"{}")
        self.assertEqual(status, 500)

    def test_a_flood_of_every_kind_writes_no_line_and_one_summary_after_the_minute(self):
        total = 0
        for name, status, send in self.kinds():
            for _ in range(FLOOD):
                self.assertEqual(send(), status, name)
            total += FLOOD
            self.assertEqual(self.entries()[0], [], f"{name}: no line per refused request")
        self.ticks[0] += sv.CSP_REPORT_WINDOW + 1                              # the minute is up
        self.assertEqual(self.kinds()[0][2](), 403)                             # the next refusal writes the count
        lines, text = self.entries()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(SUMMARY.search(lines[0]).group(1), str(total))
        self.assertNotIn(MARK.lower(), text.lower())
        self.assertNotIn("/api/", text)

    def test_a_fault_planted_between_floods_is_kept(self):
        kinds = self.kinds()
        for i, (name, status, send) in enumerate(kinds):
            for _ in range(FLOOD):
                self.assertEqual(send(), status, name)
            if i == len(kinds) // 2:
                self.fault()
        lines, text = self.entries()
        self.assertEqual(len([x for x in lines if " ERROR server " in x and "planted-fault failed" in x]), 1, lines)
        self.assertIn("RuntimeError", text)
        self.assertEqual([x for x in lines if " INFO " in x], [x for x in lines if x.endswith(" INFO  server       POST /api/planted-fault")],
                         "the let-in faulted call's own line is the only ordinary line")
        self.assertEqual(len(lines), 2, lines)
        self.assertNotIn(MARK.lower(), text.lower())

    def test_a_call_that_is_let_in_still_writes_its_one_line(self):
        self.assertEqual(self.raw("GET", "/api/projects", self.ours()), 200)
        lines, _ = self.entries()
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], r" INFO  server +GET /api/projects$")

    def test_authenticated_400_411_and_415_keep_their_line(self):
        cases = ((415, (b"Content-Type", b"text/plain"), (b"Content-Length", b"2")),
                 (411, (b"Content-Type", b"application/json")),
                 (400, (b"Content-Type", b"application/json"), (b"Content-Length", b"2")))
        for status, *headers in cases:
            body = b"{}" if status == 415 else (b"[x" if status == 400 else b"")
            self.assertEqual(self.raw("POST", "/api/change", self.ours(*headers), body), status)
        lines, _ = self.entries()
        self.assertEqual(len(lines), 3, lines)
        self.assertTrue(all(re.search(r" INFO  server +POST /api/change$", x) for x in lines), lines)

    def test_the_counter_uses_a_monotonic_clock_by_default(self):
        self.assertIs(sv.Refused().clock, time.monotonic)
        self.assertIs(sv.Refused.__init__.__defaults__[1], time.monotonic)


if __name__ == "__main__":
    unittest.main()

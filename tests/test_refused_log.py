"""Refused calls are counted, not logged one line each (src/clark/server.py, Refused; guarded).

Run: python3 dev/run_tests.py test_refused_log
A call to /api/ that is not let in (a wrong Host, another site's Origin, no token, a wrong token, a doubled Host) used to
write its own log line, so any site could loop requests at clark and fill the day's log until a real fault was no longer
kept. Each test uses a temporary log folder, a small day's limit and a fixed clock, and talks to a real server on a free port.
"""
import http.client
import logging
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  puts src/ on the path
from clark import diagnostics, log as clog, server as sv

NOW = datetime(2030, 1, 1, 9, 0, 0)
FLOOD = 300
SMALL_LIMIT = 4 * 1024          # a day's file stops here in these tests; the old code filled it in under a hundred calls


def boom(handler, req):
    raise RuntimeError("a planted fault")


class Refusals(unittest.TestCase):
    def setUp(self):
        folder = Path(tempfile.mkdtemp())
        self.log = clog.Log(folder / "logs", data=folder, clock=lambda: NOW, routes=set(sv.GET_ROUTES) | set(sv.POST_ROUTES))
        handler = clog.install(self.log)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        self.ticks = [0.0]
        for p in (mock.patch.object(clog, "MAX_BYTES", SMALL_LIMIT),
                  mock.patch.object(sv, "REFUSED", sv.Refused(interval=60, clock=lambda: self.ticks[0])),
                  mock.patch.dict(sv.POST_ROUTES, {"/api/planted-fault": boom})):
            p.start()
            self.addCleanup(p.stop)
        self.httpd = sv.LocalServer((sv.HOST, 0))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def ask(self, method, path, headers=(), body=None, host=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", host or f"127.0.0.1:{self.httpd.server_port}")
            for k, v in headers:
                conn.putheader(k, v)
            conn.endheaders(body)
            r = conn.getresponse()
            r.read()
            return r.status
        finally:
            conn.close()

    def flood(self, n=FLOOD):
        """Refused calls of every kind, in turn: no token, a wrong token, another site's Origin, a wrong Host, a doubled Host."""
        kinds = [dict(headers=()), dict(headers=((sv.TOKEN_HEADER, "not-the-token"),)),
                 dict(headers=((sv.TOKEN_HEADER, sv.TOKEN), ("Origin", "http://example.invalid"))),
                 dict(headers=((sv.TOKEN_HEADER, sv.TOKEN),), host="example.invalid"),
                 dict(headers=((sv.TOKEN_HEADER, sv.TOKEN), ("Host", "127.0.0.1")))]
        for i in range(n):
            status = self.ask("GET", "/api/projects", **kinds[i % len(kinds)])
            self.assertIn(status, (400, 403))

    def fault(self):
        status = self.ask("POST", "/api/planted-fault", ((sv.TOKEN_HEADER, sv.TOKEN), ("Content-Type", "application/json"),
                                                         ("Content-Length", "2")), b"{}")
        self.assertEqual(status, 500)

    def text(self):
        return "".join(p.read_text(encoding="utf-8") for p in self.log.files())

    def test_a_real_fault_survives_a_flood_of_refused_calls(self):
        self.flood()
        self.fault()
        self.flood()
        report = diagnostics.build(self.log, "0.0.0")
        errors = report.split("Errors in the last 7 days\n")[1].split("\n\n")[0]
        self.assertIn("RuntimeError", errors, report)
        self.assertNotIn(clog.FULL_NOTICE, self.text())

    def test_a_flood_writes_one_summary_line_per_interval(self):
        self.flood()
        lines = self.text().splitlines()
        self.assertEqual([x for x in lines if "refused" in x], [lines[0]], "one line, for the first refusal")
        self.assertIn("refused 1 calls", lines[0])
        self.assertFalse([x for x in lines if "/api/projects" in x], "no line per refused call")
        self.ticks[0] += 61
        self.ask("GET", "/api/projects")
        self.assertIn(f"refused {FLOOD} calls", self.text().splitlines()[-1], "the next line counts the calls since the last")

    def test_the_day_cannot_be_filled_by_calls_without_the_token(self):
        for _ in range(3):
            self.flood()
            self.ticks[0] += 61
        self.assertLess(sum(p.stat().st_size for p in self.log.files()), SMALL_LIMIT // 4)
        self.assertNotIn(clog.FULL_NOTICE, self.text())

    def test_a_call_that_is_let_in_is_still_logged(self):
        self.assertEqual(self.ask("GET", "/api/projects", ((sv.TOKEN_HEADER, sv.TOKEN),)), 200)
        lines = self.text().splitlines()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(" server       GET ", lines[0], "the call's own line, as before")
        self.assertNotIn("refused", lines[0])


if __name__ == "__main__":
    unittest.main()

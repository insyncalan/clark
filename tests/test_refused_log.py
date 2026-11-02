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
SECS = int(round(sv.CSP_REPORT_WINDOW))
MANY = re.compile(rf" WARN  server +(\d+) requests were turned away in the last {SECS} seconds\.$")
ONE = re.compile(rf" WARN  server +1 request was turned away in the last {SECS} seconds\.$")


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
        for p in (mock.patch.object(sv, "REFUSED", sv.Refused(clock=lambda: self.ticks[0], timer=None)),
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

    def test_a_flood_of_every_kind_writes_nothing_until_the_window_ends_then_one_line_with_the_count(self):
        total = 0
        for name, status, send in self.kinds():
            for _ in range(FLOOD):
                self.assertEqual(send(), status, name)
            total += FLOOD
            self.assertEqual(self.entries()[0], [], f"{name}: nothing is written while the window is open")
        self.ticks[0] += sv.CSP_REPORT_WINDOW + 1                              # the window is up
        self.assertEqual(self.kinds()[0][2](), 403)                             # the next refusal writes the finished window
        lines, text = self.entries()
        self.assertEqual(len(lines), 1, lines)                                  # one line; the new refusal opens a new window
        self.assertEqual(MANY.search(lines[0]).group(1), str(total))
        self.assertNotIn(MARK.lower(), text.lower())
        self.assertNotIn("/api/", text)

    def test_a_lone_refusal_after_a_quiet_spell_writes_one_line_when_its_window_ends(self):
        self.assertEqual(self.kinds()[0][2](), 403)
        self.assertEqual(self.entries()[0], [], "nothing is written at the refusal itself")
        sv.REFUSED.flush()                                                      # what the timer calls when the window is up
        lines, text = self.entries()
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], ONE)
        self.assertNotIn(MARK.lower(), text.lower())
        sv.REFUSED.flush()                                                      # a window already written is not written twice
        self.assertEqual(len(self.entries()[0]), 1)

    def test_a_last_burst_is_written_by_the_timer_without_another_refusal(self):
        for _ in range(FLOOD):
            self.assertEqual(self.kinds()[0][2](), 403)
        self.assertEqual(self.entries()[0], [])
        sv.REFUSED.flush()                                                      # what the timer calls when the window is up
        lines, _ = self.entries()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(MANY.search(lines[0]).group(1), str(FLOOD))

    def test_a_timer_is_started_with_each_window_and_a_stale_one_does_nothing(self):
        started = []

        class T:
            def __init__(self, interval, fn, args):
                self.interval, self.fn, self.args, self.daemon = interval, fn, args, False
                started.append(self)

            def start(self):
                pass
        r = sv.Refused(clock=lambda: self.ticks[0], timer=T)
        r.count(), r.count()
        self.assertEqual(len(started), 1)
        self.ticks[0] += sv.CSP_REPORT_WINDOW + 1
        r.count()                                                               # the count is written, a new window opens
        self.assertEqual(len(started), 2)
        self.assertTrue(all(t.daemon for t in started))
        self.assertEqual([t.interval for t in started], [sv.CSP_REPORT_WINDOW] * 2, "each timer waits one window")
        before = len(self.entries()[0])
        started[0].fn(*started[0].args)                                         # the first window's timer, late: nothing
        self.assertEqual(len(self.entries()[0]), before)
        self.assertEqual(r.since is not None, True)

    def test_a_fault_planted_between_floods_is_kept(self):
        kinds = self.kinds()
        for i, (name, status, send) in enumerate(kinds):
            for _ in range(FLOOD):
                self.assertEqual(send(), status, name)
            if i == len(kinds) // 2:
                self.fault()
        sv.REFUSED.flush()                                                      # the window ends: its one line is written
        lines, text = self.entries()
        self.assertEqual(len([x for x in lines if " ERROR server " in x and "planted-fault failed" in x]), 1, lines)
        self.assertIn("RuntimeError", text)
        self.assertEqual([x for x in lines if " INFO " in x], [x for x in lines if x.endswith(" INFO  server       POST /api/planted-fault")],
                         "the let-in faulted call's own line is the only ordinary line")
        self.assertEqual(len(lines), 3, lines)                   # its INFO line, its ERROR line, and the window's one line
        self.assertEqual(MANY.search(lines[-1]).group(1), str(FLOOD * len(kinds)))
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
        self.assertIs(sv.Refused.__init__.__defaults__[2], threading.Timer)


class TimerWindows(unittest.TestCase):
    """#328: the timer that writes a window's line, with a fake clock and a fake timer that records what it was given and
    runs only when a test fires it (no real waiting)."""

    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-refused-timer-")).resolve()
        self.addCleanup(shutil.rmtree, folder, True)
        self.log = clog.Log(folder / "logs", data=folder, clock=lambda: NOW, routes=set(sv.GET_ROUTES) | set(sv.POST_ROUTES))
        handler = clog.install(self.log)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        self.ticks, self.timers = [500.0], []
        test = self

        class Fake:
            def __init__(self, interval, fn, args):
                self.interval, self.fn, self.args, self.daemon = interval, fn, args, False
                test.timers.append(self)

            def start(self):
                pass

            def fire(self):
                self.fn(*self.args)
        self.Fake = Fake

    def refused(self, **kw):
        return sv.Refused(clock=lambda: self.ticks[0], **kw)

    def lines(self):
        text = "".join(p.read_text(encoding="utf-8") for p in self.log.files())
        return [x for x in text.splitlines() if clog.ENTRY.match(x)]

    def test_one_refusal_then_the_timer_writes_one_line_with_count_1(self):
        r = self.refused(timer=self.Fake)
        r.count()
        self.assertEqual(self.lines(), [], "nothing at the refusal itself")
        self.assertEqual(len(self.timers), 1)
        self.timers[0].fire()
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], ONE)

    def test_a_burst_then_the_timer_writes_one_line_with_the_burst_count(self):
        r = self.refused(timer=self.Fake)
        for _ in range(9):
            r.count()
        self.assertEqual(len(self.timers), 1, "one timer for the window, not one per refusal")
        self.timers[0].fire()
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(MANY.search(lines[0]).group(1), "9")

    def test_a_steady_flood_writes_one_line_a_window_not_two(self):
        r = self.refused(timer=self.Fake)
        for window in range(3):
            for _ in range(20):
                r.count()
                self.ticks[0] += 1.0
            self.ticks[0] += sv.CSP_REPORT_WINDOW                        # the window is up; the next refusal would close it
            self.timers[-1].fire()                                       # the timer writes it first
            self.assertEqual(len(self.lines()), window + 1, self.lines())
        self.assertEqual([MANY.search(x).group(1) for x in self.lines()], ["20"] * 3)

    def test_a_steady_flood_with_no_timer_firing_still_writes_one_line_a_window(self):
        r = self.refused(timer=self.Fake)
        for _ in range(4):
            for _ in range(5):
                r.count()
            self.ticks[0] += sv.CSP_REPORT_WINDOW + 1
        self.assertEqual(len(self.lines()), 3, "each later request writes the window before it")
        r.flush()
        self.assertEqual(len(self.lines()), 4)

    def test_a_timer_that_cannot_start_is_skipped_without_a_traceback(self):
        class Refuses:
            def __init__(self, interval, fn, args):
                self.daemon = False

            def start(self):
                raise RuntimeError("can't start new thread")
        r = self.refused(timer=Refuses)
        for _ in range(3):
            r.count()                                                    # nothing raised
        self.assertEqual(self.lines(), [])
        self.ticks[0] += sv.CSP_REPORT_WINDOW + 1
        r.count()                                                        # the next request writes the finished window
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(MANY.search(lines[0]).group(1), "3")
        self.assertNotIn("Traceback", "".join(p.read_text(encoding="utf-8") for p in self.log.files()))
        r.flush()                                                        # and the stop writes the last one
        self.assertRegex(self.lines()[-1], ONE)

    def test_a_timer_that_cannot_be_made_is_skipped_too(self):
        def none(interval, fn, args):
            raise OSError("no threads")
        r = self.refused(timer=none)
        r.count()
        r.flush()
        self.assertRegex(self.lines()[-1], ONE)


class ShutdownFlush(unittest.TestCase):
    """#260: when clark stops, the refused-request window still open is written (one line with its count); nothing is
    written when no window is open. serve() has one exit, a finally block, so a normal stop, the idle stop (which calls
    httpd.shutdown) and Ctrl+C all pass through it."""

    def setUp(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-refused-stop-")).resolve()
        self.addCleanup(shutil.rmtree, folder, True)
        self.log = clog.Log(folder / "logs", data=folder, clock=lambda: NOW, routes=set(sv.GET_ROUTES) | set(sv.POST_ROUTES))
        handler = clog.install(self.log)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        p = mock.patch.object(sv, "REFUSED", sv.Refused(timer=None))
        p.start()
        self.addCleanup(p.stop)

    def lines(self):
        text = "".join(p.read_text(encoding="utf-8") for p in self.log.files())
        return [x for x in text.splitlines() if clog.ENTRY.match(x)]

    def stop_by_idle(self, refusals):
        """Run serve() the way the launcher does: the idle watcher calls httpd.shutdown once the refusals are counted."""
        counted = threading.Event()

        class Idle:
            def here(self):
                pass

            def watch(self, shutdown, busy, say):
                counted.wait(10)
                shutdown()

        with mock.patch.object(sv, "IDLE", Idle()):
            t = threading.Thread(target=sv.serve, kwargs=dict(port=0, out=io.StringIO(), projects=lambda: []))
            t.start()
            for _ in range(refusals):
                sv.refused_count()
            self.assertEqual(self.lines(), [], "nothing is written while the window is open")
            counted.set()
            t.join(20)
        self.assertFalse(t.is_alive())

    def test_the_idle_stop_writes_the_open_window_as_one_line_with_its_count(self):
        self.stop_by_idle(FLOOD)
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(MANY.search(lines[0]).group(1), str(FLOOD))

    def test_one_refusal_before_the_stop_is_written_in_the_singular(self):
        self.stop_by_idle(1)
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertRegex(lines[0], ONE)

    def test_ctrl_c_writes_the_open_window_too(self):
        for _ in range(7):
            sv.refused_count()
        with mock.patch.object(sv.LocalServer, "serve_forever", side_effect=KeyboardInterrupt):
            self.assertEqual(sv.serve(port=0, out=io.StringIO(), projects=lambda: []), 0)
        lines = self.lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual(MANY.search(lines[0]).group(1), "7")

    def test_a_stop_with_no_refusals_writes_nothing(self):
        with mock.patch.object(sv.LocalServer, "serve_forever", side_effect=KeyboardInterrupt):
            self.assertEqual(sv.serve(port=0, out=io.StringIO(), projects=lambda: []), 0)
        self.assertEqual(self.lines(), [])

    def test_flushing_twice_writes_the_window_once(self):
        sv.refused_count()
        sv.REFUSED.flush()
        sv.REFUSED.flush()
        self.assertEqual(len(self.lines()), 1)


if __name__ == "__main__":
    unittest.main()

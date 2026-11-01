"""#110 part 2: the log is installed when clark starts, the page-error and diagnostics routes, and the Settings controls.

Run: python3 dev/run_tests.py test_log_wiring
Every test uses a temporary folder and a fake folder opener; nothing reads or writes the real log folder. The routes run on a real
server (LocalServer) with a real Logs seam; the Settings tests run the real page in headless Chrome (required: they fail, never
skip, without it) at 1400 and 900 px wide, in the light and the dark colour scheme.
"""
import http.client
import io
import json
import logging
import shutil
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from _paths import SRC
from test_page import DATA, navigate
from test_server import chrome, wait

from clark import __main__ as launcher, log as clog, log_routes, page, platform as pl, server as sv

NOW = datetime(2026, 10, 29, 9, 30, 0)
MARK = "ZQWIRETITLE"
PAGE_MARK = "ZQWIREPAGE"
WIDTHS = (1400, 900)
SCHEMES = ("light", "dark")


class Rig(unittest.TestCase):
    """A real server with a real Logs seam over a temporary folder and a fake folder opener."""
    counts = {"projects": 2}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-wiring-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "data").mkdir()
        self.log = clog.Log(self.tmp / "logs", data=self.tmp / "data", clock=lambda: NOW)
        self.opened = []
        self.fail_open = False
        self.logs = log_routes.Logs(self.log, counts=lambda: self.counts, opener=self.opener, version="0.4.0")
        self.start(self.logs)

    def opener(self, folder):
        if self.fail_open:
            raise pl.PlatformError("the folder could not be shown")
        self.opened.append(Path(folder))

    def start(self, logs):
        self.httpd = sv.LocalServer((sv.HOST, 0), page_html=page.page_html, logs=logs, data_for=DATA.get,
                                    projects=lambda: [{"code": "ABC", "name": "Example Programme"}])
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.stop)

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def api(self, method, path, body=None, token=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=10)
        try:
            h = {"Host": f"127.0.0.1:{self.httpd.server_port}", sv.TOKEN_HEADER: sv.TOKEN if token is None else token}
            data = json.dumps(body).encode() if body is not None else None
            if data is not None:
                h.update({"Content-Type": "application/json", "Content-Length": str(len(data))})
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            for k, v in h.items():
                conn.putheader(k, v)
            conn.endheaders(data)
            r = conn.getresponse()
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
        finally:
            conn.close()

    def text(self):
        return "\n".join(p.read_text(encoding="utf-8") for p in self.log.files())


class PageErrorRoute(Rig):
    def test_a_fault_becomes_one_line_of_the_browsers_own_words(self):
        status, body = self.api("POST", "/api/page-error", {"kind": "TypeError", "message": f"Cannot read properties of undefined (reading '{PAGE_MARK}')"})
        self.assertEqual((status, body), (200, {"ok": True}))
        (line,) = self.log.lines() if hasattr(self.log, "lines") else self.text().splitlines()
        self.assertIn("ERROR page", line)
        self.assertIn("TypeError", line)
        self.assertNotIn(PAGE_MARK.lower(), self.text().lower())

    def test_a_kind_that_is_not_a_browser_fault_class_is_written_as_error(self):
        self.api("POST", "/api/page-error", {"kind": f"{PAGE_MARK}Title", "message": "x"})
        self.assertNotIn(PAGE_MARK.lower(), self.text().lower())
        self.assertIn("Error:", self.text())

    def test_twenty_a_minute_then_the_rest_are_dropped_and_still_answered(self):
        for _ in range(25):
            status, _ = self.api("POST", "/api/page-error", {"kind": "Error", "message": "failed"})
            self.assertEqual(status, 200)
        self.assertEqual(self.text().count("ERROR page"), 20)

    def test_a_flood_of_reports_leaves_at_most_twenty_lines_about_the_route(self):
        handler = clog.install(self.log)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        for _ in range(25):
            self.api("POST", "/api/page-error", {"kind": "Error", "message": "failed"})
        self.assertLessEqual(len(self.text().splitlines()), 20)       # the capped ERROR lines only: no request line for the route

    def test_a_body_that_is_not_a_report_is_answered_and_writes_nothing_odd(self):
        for body in ({}, {"kind": 5, "message": ["a"]}, {"kind": None}):
            self.assertEqual(self.api("POST", "/api/page-error", body)[0], 200)
        self.assertNotIn(PAGE_MARK, self.text())

    def test_the_token_is_checked_and_a_large_body_refused(self):
        self.assertEqual(self.api("POST", "/api/page-error", {"kind": "Error"}, token="wrong")[0], 403)
        self.assertEqual(self.text(), "")
        self.assertEqual(self.api("POST", "/api/page-error", {"message": "x" * 5000})[0], 400)

    def test_with_no_logs_seam_the_routes_are_not_found(self):
        self.stop()
        self.start(None)
        for method, path in (("POST", "/api/page-error"), ("GET", "/api/diagnostics"), ("POST", "/api/logging")):
            self.assertEqual(self.api(method, path, {} if method == "POST" else None)[0], 404, path)


class RefusedRequests(Rig):
    """#234: a page on another site looping requests at this port (no token, its own Origin) writes no line per request, so
    it cannot fill the day's log and push out a real fault. At most one line a minute says how many were turned away."""

    def setUp(self):
        super().setUp()
        handler = clog.install(self.log)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        self.ticks = [1000.0]
        patch = mock.patch.object(sv, "REFUSED", sv.Refused(clock=lambda: self.ticks[0]))
        patch.start()
        self.addCleanup(patch.stop)
        sv.refused_count()                                    # a minute that has just begun (the first refusal starts it)
        sv.REFUSED.n = 0

    def foreign(self, method, path, host=None):
        """One request as another site's page sends it with mode no-cors: its own Origin, cross-site, no token."""
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", host or f"127.0.0.1:{self.httpd.server_port}")
            conn.putheader("Origin", f"http://{MARK.lower()}.example")
            conn.putheader("Sec-Fetch-Site", "cross-site")
            conn.putheader("Referer", f"http://{MARK.lower()}.example/{MARK}")
            body = b"{}" if method == "POST" else None
            if body is not None:
                conn.putheader("Content-Type", "text/plain")
                conn.putheader("Content-Length", str(len(body)))
            conn.endheaders(body)
            r = conn.getresponse()
            r.read()
            return r.status
        finally:
            conn.close()

    def flood(self, n=25):
        paths = (f"/api/{MARK.lower()}?q={MARK}", "/api/change", f"/api/data?code={MARK}", "/api/diagnostics")
        for i in range(n):
            method = "POST" if i % 2 else "GET"
            host = f"{MARK.lower()}.example" if i % 5 == 4 else None          # some with another site's Host too
            self.assertEqual(self.foreign(method, paths[i % len(paths)], host), 403)

    def test_twenty_five_foreign_requests_write_no_line(self):
        self.flood(25)
        self.assertEqual(self.text(), "")

    def test_the_minute_is_said_in_one_line_with_nothing_of_the_requests(self):
        self.flood(25)
        self.ticks[0] += sv.CSP_REPORT_WINDOW + 1                           # the minute is up
        self.flood(3)
        (line,) = self.text().splitlines()
        self.assertRegex(line, r" WARN  server +25 requests were turned away and not logged one by one$")
        self.assertNotIn(MARK.lower(), line.lower())
        self.assertNotIn("/api/", line)
        self.assertNotIn("example", line)

    def test_a_real_fault_survives_a_flood(self):
        logging.getLogger("clark.server").error("route failed")
        with mock.patch.object(clog, "MAX_BYTES", 4000):
            self.flood(25)
            for _ in range(120):                                             # ordinary lines past the day's limit
                self.assertEqual(self.api("GET", "/api/projects")[0], 200)
            self.flood(25)
            logging.getLogger("clark.server").error("save failed")           # a fault after the limit for ordinary lines
            text = self.text()
            status, b = self.api("GET", "/api/diagnostics")
        self.assertEqual(status, 200)
        self.assertIn("ERROR server       route failed", text)
        self.assertIn("ERROR server       save failed", text)
        self.assertIn(clog.FULL_NOTICE, text)
        self.assertEqual(sorted(e["count"] for e in b["errors"]), [1, 1])
        self.assertIn("server: route failed", b["report"])
        self.assertIn("server: save failed", b["report"])
        self.assertNotIn(MARK.lower(), text.lower())


class SettingsRoutes(Rig):
    def test_diagnostics_gives_the_level_the_errors_and_the_report(self):
        self.log.error("page", "TypeError: reading")
        status, b = self.api("GET", "/api/diagnostics")
        self.assertEqual(status, 200)
        self.assertEqual((b["ok"], b["level"], b["notice"]), (True, "normal", ""))
        self.assertEqual([(e["count"], e["last"]) for e in b["errors"]], [(1, "29-10-2026 09:30")])
        self.assertTrue(b["report"].startswith("Diagnostics report\nMade on 29-10-2026 09:30"))
        self.assertIn("Version: 0.4.0", b["report"])
        self.assertIn("  projects: 2", b["report"])

    def raise_one(self, area, message):
        """Log one fault the way the server does: a real exception with a real stack, so the log holds a class and a file name."""
        self.log.routes = set(sv.GET_ROUTES) | set(sv.POST_ROUTES) | {"/api/backups"}      # the routes the launcher gives the log, so a route is kept
        try:
            raise TypeError("reading x")
        except TypeError as e:
            self.log.exception(area, message, e)

    # one entry of each kind and the sentence the owner approved for it (Romanoff's table on PR 213, 01-11-2026)
    KINDS = [
        ("server", "POST /api/change failed", "Saving a change did not work."),
        ("server", "POST /api/undo failed", "Saving a change did not work."),
        ("server", "POST /api/people failed", "Saving a change did not work."),
        ("server", "POST /api/people/undo failed", "Saving a change did not work."),
        ("server", "POST /api/profile failed", "Saving a change did not work."),
        ("server", "POST /api/section-file failed", "Saving a change did not work."),
        ("server", "POST /api/section-image failed", "Saving a change did not work."),
        ("server", "POST /api/publish failed", "Publishing did not work."),
        ("server", "GET /api/publication failed", "Publishing did not work."),
        ("server", "POST /api/client-folder failed", "Publishing did not work."),
        ("server", "GET /api/export failed", "Making the Excel workbook did not work."),
        ("server", "POST /api/word-export failed", "Making the Word file did not work."),
        ("server", "POST /api/word-import failed", "Reading the Word file did not work."),
        ("server", "POST /api/backups failed", "Making a backup did not work."),
        ("server", "POST /api/backups/restore failed", "Restoring a backup did not work."),
        ("server", "POST /api/draft-email failed", "Drafting the email did not work."),
        ("server", "POST /api/draft-email/sent failed", "Marking the email as sent did not work."),
        ("server", "POST /api/ask failed", "Asking clark did not work."),
        ("server", "POST /api/ask/change/apply failed", "Asking clark did not work."),
        ("server", "POST /api/logging failed", "Changing the log setting did not work."),
        ("server", "GET /api/people failed", "Loading part of the page did not work."),
        ("server", "GET /api/data failed", "Loading part of the page did not work."),
        ("page", "TypeError: reading", "Part of the page stopped working."),
        ("store", "could not write", "Reading or saving your project data did not work."),
        ("server", "POST /api/sneak/read failed", "Something did not work."),
        ("scan", "something odd", "Something did not work."),
    ]

    def test_each_kind_of_error_is_one_plain_line_and_none_gives_technical_text(self):
        for area, message, _ in self.KINDS:
            self.raise_one(area, message)
        status, b = self.api("GET", "/api/diagnostics")
        self.assertEqual(status, 200)
        self.assertEqual(len(b["errors"]), len(self.KINDS))
        for e in b["errors"]:
            self.assertEqual(sorted(e), ["count", "last", "next", "what"])
            self.assertEqual(e["next"], "Try again. If it keeps happening, use Copy diagnostics and send it to the person who is helping you.")
            self.assertEqual(e["last"], "29-10-2026 09:30")
        self.assertEqual(sorted(e["what"] for e in b["errors"]), sorted(k[2] for k in self.KINDS))
        shown = json.dumps(b["errors"])
        for technical in ("Traceback", ".py", "TypeError", "/api/", "POST", "GET", "failed", "server", "store", "run_route", "profile", "people", "scan"):
            self.assertNotIn(technical, shown)
        self.assertIn("server: POST", b["report"])          # Copy diagnostics keeps the detail
        self.assertIn("page: TypeError: reading", b["report"])
        self.assertIn("store: could not write", b["report"])
        self.assertIn("test_log_wiring.py", b["report"])

    def test_a_write_to_a_save_route_is_a_save_but_a_read_of_it_is_a_read(self):
        self.raise_one("server", "POST /api/projects failed")
        self.raise_one("server", "GET /api/projects failed")
        status, b = self.api("GET", "/api/diagnostics")
        self.assertEqual(sorted(e["what"] for e in b["errors"]), ["Loading part of the page did not work.", "Saving a change did not work."])

    def test_plain_error_gives_the_count_and_the_time_and_ignores_the_groups_own_words(self):
        g = {"count": 3, "area": "server", "message": f"GET /api/data failed {MARK}", "last": NOW}
        self.assertEqual(log_routes.plain_error(g), {"count": 3, "last": "29-10-2026 09:30", "what": "Loading part of the page did not work.",
                                                     "next": log_routes.TRY_AGAIN})
        self.assertNotIn(MARK, json.dumps(log_routes.plain_error(g)))

    def test_the_report_holds_no_planted_marker(self):
        self.counts = {"projects": 1, MARK: 3}
        self.log.info("server", "saved", title=MARK, note=f"{MARK} {MARK}")
        self.log.error("server", "failed", project=MARK)
        self.api("POST", "/api/page-error", {"kind": MARK, "message": f"{MARK} is not defined"})
        b = self.api("GET", "/api/diagnostics")[1]
        self.assertNotIn(MARK.lower(), json.dumps(b).lower())

    def test_the_level_is_saved_and_read_back(self):
        self.assertEqual(self.api("POST", "/api/logging", {"level": "debug"})[1]["level"], "debug")
        self.assertEqual(self.api("GET", "/api/diagnostics")[1]["level"], "debug")
        self.assertEqual(self.log.level(), "debug")
        self.assertEqual(self.api("POST", "/api/logging", {"level": "normal"})[1]["level"], "normal")
        self.assertEqual(self.log.level(), "normal")

    def test_debug_for_more_than_seven_days_shows_the_notice(self):
        self.api("POST", "/api/logging", {"level": "debug"})
        later = datetime(2026, 11, 8, 9, 0, 0)
        self.log.clock = lambda: later
        notice = self.api("GET", "/api/diagnostics")[1]["notice"]
        self.assertEqual(notice, "Debug has been on for 10 days. It keeps more detail, so switch it back to Normal when you have finished.")

    def test_a_level_that_is_not_one_of_the_two_is_refused(self):
        for level in ("verbose", "", None, 5, "DEBUG"):
            status, b = self.api("POST", "/api/logging", {"level": level})
            self.assertEqual((status, b["code"]), (400, "bad_level"), level)
        self.assertEqual(self.log.level(), "normal")

    def test_a_level_that_cannot_be_saved_says_so_and_keeps_the_old_one(self):
        with mock.patch.object(pl, "write_file", side_effect=OSError("read-only")):
            status, b = self.api("POST", "/api/logging", {"level": "debug"})
        self.assertEqual((status, b["code"], b["level"]), (409, "not_saved", "normal"))
        self.assertEqual(b["message"], "The logging level could not be saved. Check that the folder can be written to, then try again.")

    def test_open_folder_makes_the_folder_and_shows_it(self):
        self.assertEqual(self.api("POST", "/api/logging/open-folder", {})[0], 200)
        self.assertEqual(self.opened, [self.tmp / "logs"])
        self.assertTrue((self.tmp / "logs").is_dir())

    def test_open_folder_ignores_the_request_body(self):
        other = tempfile.mkdtemp(dir=str(self.tmp))
        for body in ({"folder": other}, {"path": other, "dir": other}):
            self.opened.clear()
            self.assertEqual(self.api("POST", "/api/logging/open-folder", body)[0], 200)
            self.assertEqual(self.opened, [self.tmp / "logs"])

    def test_open_folder_that_fails_says_so_in_plain_words(self):
        self.fail_open = True
        status, b = self.api("POST", "/api/logging/open-folder", {})
        self.assertEqual((status, b["code"]), (503, "not_opened"))
        self.assertEqual(b["message"], "The log folder could not be opened. Try again; if it keeps happening, restart clark.")

    def test_every_new_route_needs_the_token(self):
        for method, path in (("GET", "/api/diagnostics"), ("POST", "/api/logging"), ("POST", "/api/logging/open-folder")):
            self.assertEqual(self.api(method, path, {} if method == "POST" else None, token="wrong")[0], 403, path)


class StartedByTheLauncher(unittest.TestCase):
    """main() installs the log: the production code really writes it, and removes the handler when it stops."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-wiring-main-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)

    def run_main(self, *argv, **kw):
        calls = []

        def serve(**k):
            calls.append(k)
            logging.getLogger("clark.server").info("%s %s", "GET", "/api/projects")
            return 0

        out, err = io.StringIO(), io.StringIO()
        code = launcher.main(list(argv), out=out, err=err, serve=serve, home=self.tmp, environ={}, is_free=lambda p: True, **kw)
        return code, calls, err.getvalue()

    def logs(self):
        return "\n".join(p.read_text(encoding="utf-8") for p in sorted((self.tmp / "Library" / "Logs" / "clark").glob("clark-*.log")))

    def test_a_normal_start_writes_the_log_and_gives_the_server_its_seam(self):
        code, calls, err = self.run_main("--port", "8123")
        self.assertEqual((code, err), (0, ""))
        self.assertIsInstance(calls[0]["logs"], log_routes.Logs)
        text = self.logs()
        self.assertIn("started on port 8123", text)
        self.assertIn("GET /api/projects", text)
        self.assertIn("stopped with code 0", text)

    def test_the_handler_is_taken_off_when_it_stops(self):
        before = list(logging.getLogger("clark").handlers)
        self.run_main("--port", "8123")
        self.assertEqual(list(logging.getLogger("clark").handlers), before)

    def test_a_demo_run_leaves_no_log_in_the_real_log_folder(self):
        code, calls, err = self.run_main("--demo", "--port", "8123")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.logs(), "")
        self.assertFalse((self.tmp / "Library" / "Logs").exists())

    def test_a_system_with_no_log_folder_still_starts(self):
        with mock.patch.object(pl, "log_dir", side_effect=pl.NotBuiltYet("not built")):
            code, calls, err = self.run_main("--port", "8123")
        self.assertEqual((code, err), (0, ""))
        self.assertIsNone(calls[0]["logs"])

    def test_the_launcher_names_every_route_it_may_log(self):
        log, handler, logs = launcher.start_log(self.tmp, lambda: [], home=self.tmp)
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        for route in ("/api/page-error", "/api/diagnostics", "/api/logging", "/api/logging/open-folder", "/api/change"):
            self.assertIn(route, log.routes)


class Settings(Rig):
    """Settings > Logs and diagnostics in the real page, at 1400 and 900 px, in the light and the dark colour scheme."""

    def show(self, cdp, width, scheme):
        sid = navigate(cdp, self.httpd.server_port, "#settings&p=ABC")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        self.sid, self.cdp = sid, cdp
        self.until("!!document.querySelector('#diagnostics [data-level]') && !document.querySelector('[data-level=normal]').disabled", "Settings read")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, seconds=15):
        self.assertTrue(wait(lambda: self.js(expr), seconds), what)

    def each(self):
        with chrome() as cdp:
            for scheme in SCHEMES:
                for width in WIDTHS:
                    self.show(cdp, width, scheme)
                    yield width, scheme

    def test_the_controls_and_the_words(self):
        for width, scheme in self.each():
            text = self.js("document.querySelector('#diagnostics').innerText")
            for want in ("Logs and diagnostics", "never records report text, names, email addresses, notes", "Nothing is sent anywhere.",
                         "Normal", "Debug", "Open folder", "Copy diagnostics", "Errors in the last 7 days", "None."):
                self.assertIn(want, text, f"{want} at {width} {scheme}")
            self.assertEqual(self.js("document.querySelector('[data-level=normal]').getAttribute('aria-pressed')"), "true")
            self.assertTrue(self.js("document.documentElement.scrollWidth <= window.innerWidth"), f"nothing scrolls sideways at {width}")
            self.assertTrue(self.js(f"matchMedia('(prefers-color-scheme: {scheme})').matches"))

    def test_debug_and_back_are_saved(self):
        for width, scheme in self.each():
            self.js("document.querySelector('[data-level=debug]').click()")
            self.until("document.querySelector('[data-level=debug]').getAttribute('aria-pressed') === 'true'", "Debug is chosen")
            self.assertEqual(self.log.level(), "debug")
            self.js("document.querySelector('[data-level=normal]').click()")
            self.until("document.querySelector('[data-level=normal]').getAttribute('aria-pressed') === 'true'", "Normal is chosen")
            self.assertEqual(self.log.level(), "normal")

    def test_the_seven_day_notice_shows(self):
        self.log.set_level("debug")
        self.log.clock = lambda: datetime(2026, 11, 8, 9, 0, 0)
        for width, scheme in self.each():
            self.assertIn("Debug has been on for 10 days.", self.js("document.querySelector('#debug-notice').innerText"))

    def test_a_level_that_cannot_be_saved_is_said_on_the_page(self):
        for width, scheme in self.each():
            with mock.patch.object(pl, "write_file", side_effect=OSError("read-only")):
                self.js("document.querySelector('[data-level=debug]').click()")
                self.until("!!document.querySelector('#diagnostics [role=alert]') && document.querySelector('#diagnostics [role=alert]').innerText.length > 0", "a message")
            self.assertIn("The logging level could not be saved. Check that the folder can be written to, then try again.",
                          self.js("document.querySelector('#diagnostics [role=alert]').innerText"))
            self.assertEqual(self.js("document.querySelector('[data-level=normal]').getAttribute('aria-pressed')"), "true")

    def test_copy_diagnostics_copies_the_report(self):
        self.log.error("page", "TypeError: reading")
        for width, scheme in self.each():
            self.js("window.__copied = null; Object.defineProperty(navigator, 'clipboard', {value: {writeText: function (t) { window.__copied = t; return Promise.resolve(); }}, configurable: true})")
            self.js("document.querySelector('[data-copy-diagnostics]').click()")
            self.until("window.__copied !== null", "something was copied")
            copied = self.js("window.__copied")
            self.assertTrue(copied.startswith("Diagnostics report\nMade on 29-10-2026 09:30"), copied[:60])
            self.assertIn("TypeError: reading", copied)
            self.until("document.querySelector('#diagnostics [role=status] p') !== null", "the line under the buttons")
            self.assertEqual(self.js("document.querySelector('#diagnostics [role=status] p').innerText"),
                             "Copied. Paste it into a message to the person who is helping you.")

    def test_the_errors_list_says_plain_words_and_copy_diagnostics_keeps_the_detail(self):
        self.log.routes = set(sv.GET_ROUTES) | set(sv.POST_ROUTES)
        for _ in range(3):
            try:
                raise TypeError("reading x")
            except TypeError as e:
                self.log.exception("server", "POST /api/profile failed", e)
        try:
            raise TypeError("reading y")
        except TypeError as e:
            self.log.exception("server", "POST /api/publish failed", e)
        self.log.error("page", "TypeError: reading")
        for width, scheme in self.each():
            self.until("document.querySelectorAll('#log-errors li').length === 3", "the three errors")
            shown = self.js("document.querySelector('#log-errors').innerText")
            self.assertIn("Last on 29-10-2026 09:30. Happened 3 times. Saving a change did not work.", shown)
            self.assertIn("Last on 29-10-2026 09:30. Happened once. Publishing did not work.", shown)
            self.assertIn("Last on 29-10-2026 09:30. Happened once. Part of the page stopped working.", shown)
            self.assertEqual(shown.count("Try again. If it keeps happening, use Copy diagnostics and send it to the person who is helping you."), 3)
            for technical in ("Traceback", ".py", "TypeError", "/api/", "POST", "failed", "server", "page:", "run_route"):
                self.assertNotIn(technical, shown, f"{technical} at {width} {scheme}")
            self.js("window.__copied = null; Object.defineProperty(navigator, 'clipboard', {value: {writeText: function (t) { window.__copied = t; return Promise.resolve(); }}, configurable: true})")
            self.js("document.querySelector('[data-copy-diagnostics]').click()")
            self.until("window.__copied !== null", "something was copied")
            copied = self.js("window.__copied")
            self.assertIn("server: POST", copied)
            self.assertIn("failed (TypeError)", copied)
            self.assertIn("page: TypeError: reading", copied)

    def test_open_folder_shows_the_log_folder_and_says_when_it_cannot(self):
        for width, scheme in self.each():
            self.opened.clear()
            self.fail_open = False
            self.js("document.querySelector('[data-open-log]').click()")
            self.until("!document.querySelector('[data-open-log]').disabled", "done")
            self.assertEqual(self.opened, [self.tmp / "logs"])
            self.fail_open = True
            self.js("document.querySelector('[data-open-log]').click()")
            self.until("!!document.querySelector('#diagnostics [role=alert]') && document.querySelector('#diagnostics [role=alert]').innerText.length > 0", "a message")
            self.assertEqual(self.js("document.querySelector('#diagnostics [role=alert]').innerText"),
                             "The log folder could not be opened. Try again; if it keeps happening, restart clark.")

    def test_a_fault_in_the_page_reaches_the_log_without_its_text(self):
        with chrome() as cdp:
            self.show(cdp, 1400, "light")
            self.js(f"setTimeout(function () {{ throw new TypeError('{PAGE_MARK} is not a function') }}, 0)")
            self.until("true", "ran")
            self.assertTrue(wait(lambda: "ERROR page" in self.text(), 15), "the fault was logged")
        self.assertIn("TypeError", self.text())
        self.assertNotIn(PAGE_MARK.lower(), self.text().lower())

    def test_the_published_page_has_none_of_it(self):
        view = (Path(page.PAGE).parent / "page-view.html").read_text(encoding="utf-8")
        for name in ("/api/page-error", "/api/diagnostics", "/api/logging", "Copy diagnostics"):
            self.assertNotIn(name, view)


if __name__ == "__main__":
    unittest.main()

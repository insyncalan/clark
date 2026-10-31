"""The daily log and Copy diagnostics (src/clark/log.py, src/clark/diagnostics.py).

Run: python3 dev/run_tests.py test_log
Every test uses a temporary folder and a fixed clock; nothing reads or writes the real log folder. The planted-marker tests
put a unique string where a person's content would be (a project name, an item title, a note, an ask prompt, an email draft,
a file name, an address with a token, the home folder, a fault's text) and run clark's real code (the server's routes, the
store, the Excel export and import, publish), then read every byte of every log file at both levels.
"""
import http.client
import json
import logging
import os
import re
import stat
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC
from clark import changes, diagnostics, excel, excel_import, log as clog, platform, publish, server as sv

NOW = datetime(2026, 10, 28, 14, 32, 5)
HOME = "/Users/zqhomemarkuser"
MARKERS = ["ZQMARKPROJECT", "ZQMARKTITLE", "ZQMARKNOTE", "ZQMARKASK", "ZQMARKDRAFT", "ZQMARKFILE", "ZQMARKTOKEN",
           "ZQMARKFAULT", "zqhomemarkuser"]
LINE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d (DEBUG|INFO |WARN |ERROR) \S+\s+\S")


class Running:
    """A real server on a free port in a thread (the same LocalServer test_server runs), stopped by close()."""

    def __init__(self, data_for, change, undo):
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=data_for, page_html=None, projects=lambda: [], change=change,
                                    undo=undo)
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def ask(self, method, path, headers=None, body=None):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"127.0.0.1:{self.port}")
            for k, v in (headers or {}).items():
                conn.putheader(k, v)
            conn.endheaders(body)
            r = conn.getresponse()
            return r.status, r.read()
        except OSError:
            return None, b""
        finally:
            conn.close()

    def api(self, method, path, body=None, token=None):
        h = {sv.TOKEN_HEADER: sv.TOKEN if token is None else token}
        if body is not None:
            h.update({"Content-Type": "application/json", "Content-Length": str(len(body))})
        return self.ask(method, path, h, body)


class Clock:
    def __init__(self, at=NOW):
        self.at = at

    def __call__(self):
        return self.at


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-log-test-"))
        self.addCleanup(self.rm, self.tmp)
        self.clock = Clock()
        self.log = clog.Log(self.tmp / "logs", data=self.tmp / "data", clock=self.clock, home=HOME,
                            routes={"/api/change", "/api/undo", "/api/data", "/api/projects", "/csp-report", "/health"})
        (self.tmp / "data").mkdir()

    @staticmethod
    def rm(path):
        import shutil
        for p in Path(path).rglob("*"):
            try:
                p.chmod(0o755)
            except OSError:
                pass
        shutil.rmtree(str(path), ignore_errors=True)

    def text(self):
        return "\n".join(p.read_text(encoding="utf-8") for p in self.log.files())

    def lines(self):
        return [x for x in self.text().splitlines() if x]


class Writing(Base):
    def test_one_file_a_day_with_the_line_shape(self):
        self.log.info("server", "change saved", route="/api/change", status=200, ms=12)
        self.clock.at = NOW + timedelta(days=1)
        self.log.warn("store", "slow write", ms=900)
        names = [p.name for p in self.log.files()]
        self.assertEqual(names, ["clark-2026-10-28.log", "clark-2026-10-29.log"])
        first = self.lines()[0]
        self.assertEqual(first, "2026-10-28 14:32:05 INFO  server       change saved  route=/api/change status=200 ms=12")
        for line in self.lines():
            self.assertRegex(line, LINE)

    def test_each_entry_is_one_append(self):
        calls = []
        real = os.write
        with mock.patch.object(os, "write", side_effect=lambda fd, b: calls.append(b) or real(fd, b)):
            self.log.exception("server", "route failed", ValueError("x"))
        self.assertEqual(len(calls), 1)

    def test_normal_hides_debug_and_debug_shows_it(self):
        self.log.debug("server", "detail one")
        self.log.info("server", "info one")
        self.log.warn("server", "warn one")
        self.log.error("server", "error one")
        self.assertEqual([x.split()[2] for x in self.lines()], ["INFO", "WARN", "ERROR"])
        self.assertEqual(self.log.set_level("debug"), "debug")
        self.log.debug("server", "detail two")
        self.assertIn("DEBUG server       detail two", self.text())
        self.assertEqual(self.log.set_level("normal"), "normal")
        self.log.debug("server", "detail three")
        self.assertNotIn("detail three", self.text())

    def test_level_is_saved_cached_and_a_bad_value_keeps_normal(self):
        self.assertEqual(self.log.level(), "normal")
        self.log.set_level("debug")
        again = clog.Log(self.tmp / "logs", data=self.tmp / "data", clock=self.clock)
        self.assertEqual(again.level(), "debug")
        file = self.tmp / "data" / "diagnostics.json"
        for bad in ('{"level": "verbose"}', "not json", "[1]", '{"level": 5}', ""):
            file.write_text(bad, encoding="utf-8")
            os.utime(str(file), ns=(os.stat(str(file)).st_mtime_ns + 10**9,) * 2)
            self.assertEqual(again.level(), "normal", bad)
        self.assertEqual(self.log.set_level("DeBuG"), "debug")
        self.assertEqual(self.log.set_level("loud"), "normal")
        reads = []
        real = Path.read_text
        with mock.patch.object(Path, "read_text", lambda self_, *a, **k: reads.append(1) or real(self_, *a, **k)):
            self.log.level()
            self.log.level()
        self.assertLessEqual(len(reads), 1, "read once, then from the cache")

    def test_a_missing_data_folder_means_normal(self):
        self.assertEqual(clog.Log(self.tmp / "logs").level(), "normal")

    def test_full_day_stops_with_one_line(self):
        with mock.patch.object(clog, "MAX_BYTES", 400):
            for n in range(40):
                self.log.info("server", "change saved", n=n)
        text = self.text()
        self.assertEqual(text.count(clog.FULL_NOTICE), 1)
        self.assertLess(len(text), 400 + 200)
        self.assertNotIn("n=39", text)

    def test_a_read_only_folder_never_breaks_clark(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores folder permissions")
        folder = self.tmp / "logs"
        folder.mkdir()
        folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.log.info("server", "x")
        self.log.error("server", "y")
        self.log.exception("server", "z", ValueError("q"))
        self.log.page_error("TypeError", "boom")
        self.assertEqual(self.log.files(), [])
        gone = clog.Log(self.tmp / "no" / "such" / "deep" / "folder" / "x" / "y")
        gone.folder = self.tmp / "file-not-folder"
        gone.folder.write_text("a file", encoding="utf-8")
        gone.info("server", "x")                       # the folder is a file: still no error

    def test_set_level_on_a_read_only_folder_never_raises_and_keeps_the_old_level(self):
        if os.geteuid() == 0:
            self.skipTest("root ignores folder permissions")
        folder = self.log.level_file.parent
        folder.mkdir(parents=True, exist_ok=True)
        self.assertEqual(self.log.set_level("debug"), "debug")
        self.addCleanup(folder.chmod, 0o755)
        self.log.level_file.chmod(stat.S_IRUSR)
        folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.assertEqual(self.log.set_level("normal"), "debug")      # not saved: the old level stays
        self.assertEqual(self.log.level(), "debug")

    def test_a_bad_clock_or_setting_never_raises(self):
        broken = clog.Log(self.tmp / "logs", clock=lambda: 1 / 0)
        broken.info("a", "b")
        broken.exception("a", "b")
        self.assertEqual(broken.tail(), [])


class Keeping(Base):
    def make(self, name, text="x\n"):
        folder = self.tmp / "logs"
        folder.mkdir(exist_ok=True)
        (folder / name).write_text(text, encoding="utf-8")

    def test_seven_days_are_kept_and_older_removed_on_the_first_entry_of_a_day(self):
        for n in range(1, 11):
            self.make(f"clark-{(NOW.date() - timedelta(days=n)).isoformat()}.log")
        self.log.info("server", "first of the day")
        kept = sorted(p.name for p in self.log.files())
        self.assertEqual(kept[0], "clark-2026-10-22.log")
        self.assertEqual(len(kept), 7)
        self.assertEqual(kept[-1], "clark-2026-10-28.log")

    def test_prune_only_runs_when_the_days_file_is_new(self):
        self.log.info("server", "first")
        self.make("clark-2026-01-01.log")
        self.log.info("server", "second")
        self.assertTrue((self.tmp / "logs" / "clark-2026-01-01.log").exists(), "not pruned on a later entry the same day")

    def test_only_files_clark_wrote_are_ever_removed(self):
        keep = ["notes.txt", "clark-2026-01-01.log.bak", "debug-2026-01-01.log", "clark-2026-1-1.log", "clark-2026-13-45.log",
                "server.log", "clark-2026-01-01.logx", "xclark-2026-01-01.log"]
        for name in keep:
            self.make(name)
        (self.tmp / "logs" / "clark-2025-01-01.log").mkdir()          # a folder with a log's name
        self.make("clark-2026-01-01.log")
        removed = self.log.prune(NOW.date())
        self.assertEqual(removed, ["clark-2026-01-01.log"])
        for name in keep:
            self.assertTrue((self.tmp / "logs" / name).exists(), name)
        self.assertTrue((self.tmp / "logs" / "clark-2025-01-01.log").is_dir())

    def test_clock_ahead_does_not_delete_recent_logs(self):
        for n in range(0, 7):
            self.make(f"clark-{(NOW.date() - timedelta(days=n)).isoformat()}.log")
        self.clock.at = NOW + timedelta(days=400)                       # a clock 400 days ahead wrote this
        self.log.info("server", "ahead")
        self.clock.at = NOW                                              # the clock is corrected
        self.log.info("server", "back")
        self.assertEqual(len(self.log.files()), 8, "the seven real days and the future file all still there")
        self.assertEqual(self.log.prune(NOW.date()), [])

    def test_a_first_entry_after_a_long_break_keeps_what_is_there_one_day(self):
        self.make("clark-2026-08-01.log")
        self.log.info("server", "back after a break")
        self.assertEqual(len(self.log.files()), 2)
        self.clock.at = NOW + timedelta(days=1)
        self.log.info("server", "next day")
        self.assertEqual([p.name for p in self.log.files()], ["clark-2026-10-28.log", "clark-2026-10-29.log"])

    def test_the_future_file_never_shows_in_the_report_or_errors(self):
        self.make("clark-2030-01-01.log", "2030-01-01 10:00:00 ERROR server       future fault\n")
        self.log.error("server", "real fault")
        report = diagnostics.build(self.log, "0.4.0", now=NOW)
        self.assertNotIn("future fault", report)
        self.assertIn("real fault", report)
        self.assertEqual([g["message"] for g in self.log.errors()], ["real fault"])

    def test_tail_is_the_last_n_lines_across_files(self):
        self.make("clark-2026-10-27.log", "".join(f"2026-10-27 10:00:00 INFO  a            line {n}\n" for n in range(5)))
        for n in range(5):
            self.log.info("a", "today", n=n)
        t = self.log.tail(7)
        self.assertEqual(len(t), 7)
        self.assertTrue(t[-1].endswith("n=4"))
        self.assertIn("line 3", t[0])


class NeverContent(Base):
    def hostile(self):
        """Every way code could hand content to the log."""
        m = MARKERS
        for level in ("normal", "debug"):
            self.log.set_level(level)
            for call in (self.log.debug, self.log.info, self.log.warn, self.log.error):
                call("server", "saved", title=m[1], project=m[0], note=m[2], prompt=m[3], draft=m[4], file=m[5],
                     url=f"https://example.com/x?token={m[6]}", home=f"{HOME}/Documents/{m[5]}", path=f"{HOME}/{m[5]}")
                call("server", f"saved to {HOME}/Documents/{m[5]}")
                call("server", f"opened https://example.com/a/b?token={m[6]} by sara.khan@{m[0].lower()}.example")
                call("server", f"opened {HOME}/{m[5]} and C:\\Users\\x\\{m[5]}")
                call("server", f"title \"{m[1]}\" and 'note {m[2]}' failed")
            try:
                raise ValueError(f"bad value {m[7]} in {HOME}/{m[5]}")
            except ValueError as e:
                self.log.exception("server", "route failed", e)
                self.log.exception("server", "route failed")
            self.log.page_error("TypeError", f"Cannot read 'title' of {m[1]} at {HOME}/{m[5]} user@{m[0]}.com")
            self.log.page_error(f"Evil{m[7]} Error", f"bad {m[3]}")
            logger = logging.getLogger("clark.test")
            handler = clog.install(self.log, "clark.test")
            self.addCleanup(logger.removeHandler, handler)
            logger.info("opened %s for %s", f"{HOME}/{m[5]}", m[0])
            logger.warning("read %s failed", m[4])
            try:
                raise KeyError(m[7])
            except KeyError:
                logger.exception("route %s failed", f"/api/{m[5]}")

    def test_planted_markers_never_reach_a_file_at_either_level(self):
        self.hostile()
        text = self.text()
        self.assertGreater(len(text.splitlines()), 20)
        for marker in MARKERS:
            self.assertNotIn(marker.lower(), text.lower(), marker)
        self.assertNotIn("sara.khan", text)
        self.assertNotIn("example.com", text)
        self.assertNotIn("token=", text)

    def test_text_in_a_detail_becomes_its_length(self):
        self.log.info("server", "saved", title="Quarterly plan")
        self.assertIn("title=<text, 14 characters>", self.text())
        self.log.info("server", "saved", title="x")
        self.assertIn("title=<text, 1 character>", self.text())

    def test_what_a_detail_may_be(self):
        self.log.info("server", "x", n=3, ok=True, bad=False, secs=1.26, none=None, item="ABC-A-003", route="/api/change",
                      other_route="/api/zqmarkroute", CAPS="no", **{"a b": 1})
        line = self.lines()[0]
        for want in ("n=3", "ok=yes", "bad=no", "secs=1.3", "none=none", "item=ABC-A-003", "route=/api/change",
                     "other_route=<text, 16 characters>"):
            self.assertIn(want, line)
        self.assertNotIn("CAPS", line)
        self.assertNotIn("a b", line)

    def test_a_fault_is_its_class_and_where_never_its_text(self):
        try:
            raise ValueError("secret ZQMARKFAULT")
        except ValueError as e:
            self.log.exception("server", "route failed", e)
        text = self.text()
        self.assertIn("route failed (ValueError)", text)
        self.assertRegex(text, r"\n    test_log\.py:\d+ test_a_fault")
        self.assertNotIn("ZQMARKFAULT", text)
        self.assertNotIn("raise ValueError", text, "no source lines")

    def test_home_folder_is_a_tilde_whichever_slash_and_case(self):
        for form in (HOME, HOME.replace("/", "\\"), HOME.upper()):
            self.log.info("files", f"saved to {form}/Documents")
        text = self.text()
        self.assertNotIn("zqhomemark", text.lower())
        self.assertEqual(text.count("saved to ~/…"), 3, "the home folder is written as ~")
        self.assertEqual(clog.home_to_tilde(f"in {HOME}/x", HOME), "in ~/x")

    def test_area_is_made_safe(self):
        self.log.info("a b/c\n" + "x" * 40, "m")
        self.assertRegex(self.lines()[0], r"INFO  a_b_c_xxxxxx m")

    def test_message_is_one_line_and_cut(self):
        self.log.info("a", "first\nsecond\r\nthird " + "w" * 400)
        self.assertEqual(len(self.lines()), 1)
        self.assertLess(len(self.lines()[0]), 200)

    def test_unicode_is_written_as_utf8(self):
        self.log.info("a", "caf\u00e9 saved")
        self.assertIn("caf\u00e9 saved", self.text())


class PageErrors(Base):
    def test_at_most_twenty_a_minute(self):
        wrote = [self.log.page_error("TypeError", "x", now=1000.0 + n * 0.1) for n in range(30)]
        self.assertEqual(wrote.count(True), 20)
        self.assertEqual(self.text().count("ERROR page"), 20)
        self.assertTrue(self.log.page_error("TypeError", "x", now=1061.0), "a new minute starts again")

    def test_quoted_text_addresses_and_paths_are_removed(self):
        self.log.page_error("TypeError", "Cannot read properties of undefined (reading 'title') at /Users/someone/a.js:3 "
                            "for pat@example.org from https://example.com/x?t=abcdefghijklmnopqrstuvwxyz0123")
        line = self.lines()[0]
        for gone in ("title", "someone", "pat@", "example", "abcdefghij", "/Users", "a.js"):
            self.assertNotIn(gone, line)
        self.assertIn("TypeError", line)

    def test_a_bad_error_name_is_replaced(self):
        self.log.page_error("not a name!", "x")
        self.assertIn("ERROR page         Error: …", self.lines()[0])


class Words(Base):
    BANNED = re.compile(r"\b(sweep|proposal|stage|apply|vault|live server|extract|refused|valid|invalid|tracker|Traceback|"
                        r"JSON|script)\b|!", re.IGNORECASE)

    def test_the_words_a_person_reads(self):
        self.log.set_level("debug")
        self.clock.at = NOW + timedelta(days=9)
        (self.tmp / "data" / "diagnostics.json").write_text(json.dumps({"level": "debug", "debug_since": "2026-10-28"}), encoding="utf-8")
        notice = self.log.debug_notice()
        self.assertEqual(notice, "Debug has been on for 9 days. It keeps more detail, so switch it back to Normal when you "
                                 "have finished.")
        self.log.error("server", "route failed")
        report = diagnostics.build(self.log, "0.4.0", now=self.clock.at)
        for text in (notice, report, clog.FULL_NOTICE):
            self.assertIsNone(self.BANNED.search(text), text)
        for line in report.splitlines():
            self.assertFalse(line.lower().startswith("clark"), line)
        self.assertFalse(clog.FULL_NOTICE.lower().startswith("clark"))

    def test_debug_notice_only_after_seven_days(self):
        self.log.set_level("debug")
        self.assertEqual((self.log.debug_days(), self.log.debug_notice()), (0, ""))
        self.clock.at = NOW + timedelta(days=7)
        self.assertEqual(self.log.debug_notice(), "")
        self.clock.at = NOW + timedelta(days=8)
        self.assertIn("8 days", self.log.debug_notice())
        self.log.set_level("normal")
        self.assertEqual((self.log.debug_days(), self.log.debug_notice()), (0, ""))

    def test_switching_debug_on_again_keeps_the_first_day(self):
        self.log.set_level("debug")
        self.clock.at = NOW + timedelta(days=3)
        self.log.set_level("debug")
        self.assertEqual(self.log.debug_days(), 3)


class Report(Base):
    def test_what_the_report_holds(self):
        self.log.info("server", "change saved", route="/api/change", status=200)
        self.log.error("server", "route failed", route="/api/data")
        self.log.error("server", "route failed", route="/api/data")
        report = diagnostics.build(self.log, "0.4.0", settings={"log_level": "normal", "appearance": "dark",
                                                                "profile_name": "Sara Khan", "email": "sara@example.org",
                                                                "update_check": True, "appearance_x": "ZQMARKTITLE"},
                                   counts={"projects": 2, "items": 41, "Bad Key": 3, "title": "ZQMARKTITLE", "flag": True},
                                   now=NOW, python="3.9.6", system="darwin", release="24.0.0")
        for want in ("Diagnostics report", "Made on 28-10-2026 14:32", "Version: 0.4.0", "Python: 3.9.6",
                     "System: macOS 24.0.0", "Logging: normal", "  appearance: dark", "  log_level: normal",
                     "  update_check: yes", "  projects: 2", "  items: 41", "  2 x server: route failed (last 28-10-2026 14:32)",
                     "Last 200 log lines"):
            self.assertIn(want, report)
        for gone in ("Sara", "sara@", "profile_name", "ZQMARKTITLE", "Bad Key", "flag"):
            self.assertNotIn(gone, report)

    def test_no_profile_email_project_or_title_even_after_hostile_logging(self):
        NeverContent.hostile(self)
        report = diagnostics.build(self.log, "0.4.0", settings={"profile": "Sara Khan <sara@example.org>"},
                                   counts={"ZQMARKPROJECT": 1}, now=NOW)
        for marker in MARKERS:
            self.assertNotIn(marker.lower(), report.lower(), marker)
        self.assertNotIn("sara", report.lower())

    def test_old_lines_with_a_path_or_address_are_scrubbed_again(self):
        folder = self.tmp / "logs"
        folder.mkdir()
        (folder / "clark-2026-10-28.log").write_text(
            f"2026-10-28 10:00:00 INFO  files        saved {HOME}/Documents/plan.docx to /Users/other/x for pat@example.org "
            "https://example.com/a?t=1  route=/api/change\n", encoding="utf-8")
        report = diagnostics.build(self.log, "0.4.0", now=NOW)
        for gone in ("zqhomemark", "/Users/other", "pat@", "example.com"):
            self.assertNotIn(gone, report)
        self.assertIn("route=/api/change", report)

    def test_only_the_last_200_lines(self):
        for n in range(300):
            self.log.info("a", "line", n=n)
        report = diagnostics.build(self.log, "0.4.0", now=NOW)
        self.assertIn("n=299", report)
        self.assertIn("n=100", report)
        self.assertNotIn("n=99\n", report)

    def test_empty_log_reads_as_none(self):
        report = diagnostics.build(self.log, "0.4.0", now=NOW)
        self.assertEqual(report.count("  None"), 2)

    def test_errors_are_grouped_and_old_ones_left_out(self):
        folder = self.tmp / "logs"
        folder.mkdir()
        (folder / "clark-2026-10-20.log").write_text("2026-10-20 10:00:00 ERROR server       old fault\n", encoding="utf-8")
        (folder / "clark-2026-10-27.log").write_text("2026-10-27 10:00:00 ERROR server       item 4 failed\n"
                                                     "2026-10-27 11:00:00 ERROR server       item 9 failed\n", encoding="utf-8")
        found = self.log.errors()
        self.assertEqual([(g["count"], g["message"]) for g in found], [(2, "item # failed")])

    def test_safe_settings_allow_list(self):
        self.assertEqual(diagnostics.safe_settings({"log_level": "debug", "appearance": "neon", "update_check": 0,
                                                    "unknown": 1}), [("log_level", "debug"), ("update_check", "0")])
        self.assertEqual(diagnostics.safe_settings(None), [])


class Platform(unittest.TestCase):
    def test_log_folder_is_the_platforms(self):
        self.assertEqual(platform.log_dir("/h", "darwin"), Path("/h/Library/Logs/clark"))
        with self.assertRaises(platform.NotBuiltYet):
            platform.log_dir("/h", "win32")

    def test_open_folder_goes_through_platform(self):
        calls = []
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(os.rmdir, str(folder))
        platform.open_file(folder, run=lambda a, **k: calls.append(a) or mock.Mock(returncode=0, stderr=""), on="darwin")
        self.assertEqual(calls[0][0], "open")

    def test_the_log_modules_start_no_program_and_name_no_system_folder(self):
        for name in ("log.py", "diagnostics.py"):
            src = (SRC / "clark" / name).read_text(encoding="utf-8")
            self.assertNotIn("subprocess", src)
            self.assertNotIn("Library", src.split('"""', 2)[2])


class RealCodePaths(Base):
    """clark's own code, run with the planted markers where a person's content goes, at both levels."""

    def run_everything(self):
        handler = clog.install(self.log, "clark")
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        m = MARKERS
        demo = DemoStore()
        self.addCleanup(demo.close)
        s = demo.store
        demo.action(description=f"Send {m[1]} to {m[0]} at {HOME}/{m[5]}", owner=m[0], latest_update=m[2])
        change = changes.make_change(s.path, [], USER)
        undo = changes.make_undo(s.path, [], USER)

        def boom(code):
            raise KeyError(f"{m[7]} {HOME}/{m[5]}")

        run = Running(data_for=boom, change=change, undo=undo)
        self.addCleanup(run.close)
        for method, path in (("GET", f"/{m[5]}?token={m[6]}"), ("GET", f"/api/{m[5]}"), ("GET", f"/api/data?p={m[0]}"),
                             ("GET", f"/api/data?project={m[0]}&q={m[3]}"), ("POST", f"/api/change?x={m[4]}"),
                             ("POST", "/api/change"), ("POST", "/api/undo")):
            body = json.dumps({"project": "ABC", "kind": "report_sections", "op": "add", "title": m[1], "text": m[4],
                               "prompt": m[3]}).encode() if method == "POST" else None
            run.api(method, path, body=body)                                   # the real token
            run.api(method, path, body=body, token=m[6])                       # a wrong one
        report = json.dumps({"csp-report": {"blocked-uri": f"https://example.com/{m[6]}",
                                             "violated-directive": f"script-src {m[0]}"}}).encode()
        run.ask("POST", sv.CSP_REPORT_ROUTE, {"Content-Type": "application/csp-report", "Content-Length": str(len(report))},
                report)
        tmp = Path(tempfile.mkdtemp(prefix=f"clark-{m[5]}-"))
        self.addCleanup(self.rm, tmp)
        xlsx = tmp / f"{m[5]}.xlsx"
        excel.export_project(s, "ABC", xlsx, tmp / "state.json", on="2026-10-28")
        try:
            plan = excel_import.read_workbook(s, xlsx, "ABC", tmp / "state.json")
            excel_import.apply_import(s, plan, USER, tmp / "state.json")
        except Exception as e:                                         # a refusal here is fine; only the log matters
            logging.getLogger("clark.test").exception("import ended %s", e)
        try:
            publish.publish(s, "ABC", tmp, by_user=USER, now="2026-10-28")
        except Exception:
            logging.getLogger("clark.test").exception("publish ended")

    def test_no_marker_in_any_log_file_at_normal_or_debug(self):
        for level in ("normal", "debug"):
            self.log.set_level(level)
            self.run_everything()
            text = self.text()
            for marker in MARKERS:
                self.assertNotIn(marker.lower(), text.lower(), f"{marker} at {level}")
        self.assertIn("GET", self.text(), "the real server did log something")


LOG_METHODS = {"debug", "info", "warn", "warning", "error", "exception", "critical"}
LOG_NAMES = {"log", "clog", "logger", "LOG", "LOGGER", "_log"}
STDLIB_NAMES = {"logger", "LOG", "LOGGER"}          # the standard library's logger: the message is the first argument


def log_calls(tree):
    """(line, message node or None) for every call on a logger in a parsed file. `Log` methods take the area first and
    the message second; the standard library's logger takes the message first."""
    import ast
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in LOG_METHODS):
            continue
        base = node.func.value
        name = base.id if isinstance(base, ast.Name) else base.attr if isinstance(base, ast.Attribute) else ""
        if name not in LOG_NAMES:
            continue
        index = 0 if name in STDLIB_NAMES else 1
        if name == "log" and isinstance(base, ast.Name) and base.id == "log" and len(node.args) == 1:
            index = 0
        yield node.lineno, node.args[index] if len(node.args) > index else None


class MessagesAreConstants(unittest.TestCase):
    """A bare word in a message is written as it is, so a message must be a fixed text in the code and a value goes in a
    detail (where it is turned into a number or its length)."""

    def offenders(self, source, name="x.py"):
        import ast
        return [line for line, msg in log_calls(ast.parse(source, name))
                if not (isinstance(msg, ast.Constant) and isinstance(msg.value, str))]

    def test_src_log_calls_have_constant_messages(self):
        bad = []
        for path in sorted(Path(SRC).rglob("*.py")):
            if path.name == "log.py" or "vendor" in path.parts:
                continue                                    # log.py is the writer itself (its Bridge passes a template on)
            for line in self.offenders(path.read_text(encoding="utf-8"), str(path)):
                bad.append(f"{path.name}:{line}")
        self.assertEqual(bad, [], "a log message must be a constant; put values in a detail: " + ", ".join(bad))

    def test_the_scan_catches_a_built_message(self):
        for src in ('log.info("server", "saved " + title)', 'log.info("server", f"saved {title}")',
                    'log.warn("server", "saved %s" % title)', 'self.log.error("server", msg)',
                    'LOG.info("saved " + title)', 'LOG.info(f"saved {title}")', 'logger.exception(text)',
                    'clog.info("server", "saved {}".format(title))'):
            self.assertEqual(len(self.offenders(src)), 1, src)
        for src in ('log.info("server", "saved", title=title)', 'LOG.info("%s %s", a, b)', 'logger.warning("a b")'):
            self.assertEqual(self.offenders(src), [], src)


class CountNames(Base):
    def test_only_the_listed_count_names_show(self):
        report = diagnostics.build(self.log, "0.4.0", counts={"projects": 2, "zqmarkword": 5, "secretname": 1}, now=NOW)
        self.assertIn("  projects: 2", report)
        self.assertNotIn("zqmarkword", report)
        self.assertNotIn("secretname", report)


class LongAndOddText(Base):
    """A text far longer than clark writes, a line break other than a newline, and the file's permissions."""

    def test_a_very_long_line_read_back_is_scrubbed_quickly(self):
        import time
        self.log.info("server", "started")
        (path,) = self.log.files()
        with open(path, "a", encoding="utf-8") as f:                 # a damaged or hand-edited file
            f.write("2026-10-28 14:32:05 INFO  server " + "zqlong.mark@corp.example " * 40000 + "\n")
        began = time.monotonic()
        report = diagnostics.build(self.log, "0.4.0", now=NOW)
        self.assertLess(time.monotonic() - began, 2.0)
        self.assertNotIn("zqlong", report)

    def test_a_word_the_cut_goes_through_is_dropped_whole(self):
        text = "https://a.example/x " * 24 + "zqcutname.example@corp.test"
        self.assertGreater(len(text), clog.MESSAGE_LIMIT * 4)
        self.assertNotIn("zqcut", clog.scrub(text))
        self.assertNotIn("zqcut", clog.scrub_line("w " * 999 + "zqcutname.example@corp.test"))

    def test_a_next_line_character_cannot_make_a_second_entry(self):
        self.log.info("server", "one\x85ERROR forged entry\u2028two")
        self.assertEqual(len(self.log.tail(10)), 1)
        self.assertEqual(len(self.lines()), 1)

    @unittest.skipIf(os.name != "posix", "file permissions are a POSIX idea")
    def test_the_file_can_be_read_only_by_its_owner(self):
        self.log.info("server", "started")
        (path,) = self.log.files()
        self.assertEqual(stat.S_IMODE(path.stat().st_mode) & 0o077, 0)


class PathsWherePeopleWrite(Base):
    """One test per path where a person's content enters clark, through the real server with clark's loggers routed into the
    log: plant the markers where the person's text goes, run the path at both levels and check no marker reaches a file. Each
    test also checks the path really ran (a 200), so a refusal cannot pass for a clean log. Ask clark has no route yet, so its
    test waits: when the route exists, remove the skip and run it the same way."""

    def setUp(self):
        super().setUp()
        handler = clog.install(self.log, "clark")
        self.addCleanup(logging.getLogger("clark").removeHandler, handler)
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)

    def serve(self, **seams):
        httpd = sv.LocalServer((sv.HOST, 0), data_for=lambda code: None, page_html=None, projects=lambda: [], **seams)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        conn_port = httpd.server_port

        def post(path, req):
            body = json.dumps(req).encode()
            conn = http.client.HTTPConnection(sv.HOST, conn_port, timeout=30)
            try:
                conn.putrequest("POST", path, skip_host=True, skip_accept_encoding=True)
                for k, v in {"Host": f"127.0.0.1:{conn_port}", sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json",
                             "Content-Length": str(len(body))}.items():
                    conn.putheader(k, v)
                conn.endheaders(body)
                r = conn.getresponse()
                return r.status, json.loads(r.read() or b"null")
            finally:
                conn.close()
        return post

    def check(self, run):
        for level in ("normal", "debug"):
            self.log.set_level(level)
            run()
        text = self.text().lower()
        for marker in MARKERS:
            self.assertNotIn(marker.lower(), text, marker)
        self.assertIn("post /api/", text, "the real server did log the request")

    def test_an_item_title_and_note_saved_from_the_page_log_no_content(self):
        """The change route, the way the page (the table's cells today, the peek later) saves an item's text."""
        m = MARKERS
        ref = self.demo.action(description="Draft the plan")
        post = self.serve(change=changes.make_change(self.demo.store.path, [], USER))

        def run():
            status, got = post("/api/change", {"project": "ABC", "kind": "actions", "op": "update", "id": ref, "place": "cell",
                                               "changes": {"description": f"Send {m[1]} to {m[0]}", "latest_update": f"{m[2]} {HOME}/{m[5]}"}})
            self.assertEqual(status, 200, got)
        self.check(run)

    @unittest.skip("ask clark has no route yet: plant the markers in a question and in the answer, ask, and run this")
    def test_ask_clark_logs_no_content(self):
        self.check(lambda: None)

    def test_word_import_logs_no_content(self):
        """The Word import route, with the markers in the file name and in the document's text and table."""
        import base64
        from clark import word_route
        from test_docx_read import P, TBL, TR, docx
        m = MARKERS
        word_route.PLANS.clear()
        self.addCleanup(word_route.PLANS.clear)
        post = self.serve(word_import=word_route.make_word_import(self.demo.store.path, [], USER))
        body = (P("Actions", style="Heading1") + TBL(TR("Action", "Owner", "Due"), TR(f"Send {m[1]} {m[2]}", m[0], "30-11-2026"))
                + P("Risks", style="Heading1") + P(f"{m[3]} may slip"))
        data = base64.b64encode(docx(body)).decode("ascii")

        def run():
            status, got = post("/api/word-import", {"op": "check", "project": "ABC", "name": f"{HOME}/{m[5]}.docx", "data": data})
            self.assertEqual(status, 200, got)
            status, got = post("/api/word-import", {"op": "apply", "project": "ABC", "plan": got["plan"], "accept": "all"})
            self.assertEqual(status, 200, got)
        self.check(run)


if __name__ == "__main__":
    unittest.main()

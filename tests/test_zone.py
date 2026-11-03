"""#631: in the shipped container clark's clock follows the person's time zone, not UTC (clark/zone.py, wired by server.py and
__main__.py).

Run: python3 dev/run_tests.py test_zone
The zone is frozen where UTC and local disagree on the date: Dubai at 22:00 UTC (already tomorrow there) and New York at 02:00
UTC (still yesterday there). The container is a fake (zone.make's `container`, container_mode's `environ` and `exists`): this
box is not one, and no real data folder is touched (every store is a temporary one).
"""
import calendar
import json
import logging
import os
import time
import unittest
from datetime import date, datetime
from unittest import mock

from _demo import USER, DemoStore
from clark import excel, history, milestones, movement_read, server as sv, sneak, store as store_module, timefmt, zone
from clark import changes
from test_server import Running

DUBAI_NIGHT = (2026, 11, 3, 22, 0, 0)          # 22:00 UTC on 03-11-2026 is 02:00 on 04-11-2026 in Dubai
NEW_YORK_NIGHT = (2026, 11, 4, 2, 0, 0)        # 02:00 UTC on 04-11-2026 is 21:00 on 03-11-2026 in New York (EST, -05:00)
CASES = (("Asia/Dubai", DUBAI_NIGHT, "2026-11-04", "+04:00"), ("America/New_York", NEW_YORK_NIGHT, "2026-11-03", "-05:00"))
NOT_ZONES = ("", " ", "Arabian Standard Time", "Eastern Standard Time", "../../etc/passwd", "/etc/localtime", "Asia/../UTC",
             "Asia/Nowhere", "Mars/Olympus", "Asia/Dubai\n", "Asia/Dubai; rm", "+04:00", "<+04>-4", "x" * 200, None, 4, ["UTC"])


class KeepsTheZone(unittest.TestCase):
    """Puts the process zone (and CLARK_NOW, which sneak.today reads) back as they were after each test."""

    def setUp(self):
        had = os.environ.get("TZ")
        self.addCleanup(self._restore, had)
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("CLARK_NOW", None)
        os.environ.pop("TZ", None)
        time.tzset()

    @staticmethod
    def _restore(had):
        if had is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = had
        time.tzset()


def at(utc):
    """time.time() frozen at the UTC moment `utc` (date.today() reads it)."""
    return mock.patch("time.time", return_value=float(calendar.timegm(utc)))


def utc_clock(utc):
    return datetime(*utc, tzinfo=store_module.timezone.utc)


class Names(unittest.TestCase):
    def test_a_real_iana_name_is_taken(self):
        for name in ("Asia/Dubai", "America/New_York", "Europe/London", "UTC", "America/Argentina/Buenos_Aires", "Etc/GMT+4"):
            self.assertEqual(zone.valid(name), name)

    def test_anything_else_is_not(self):
        for bad in NOT_ZONES:
            with self.subTest(bad=bad):
                self.assertIsNone(zone.valid(bad))

    def test_the_container_needs_the_setting_and_a_marker(self):
        on, marker = {"CLARK_CONTAINER": "1"}, lambda p: p == "/.dockerenv"
        self.assertTrue(zone.container_mode(on, exists=marker))
        self.assertTrue(zone.container_mode(on, exists=lambda p: p == "/run/.containerenv"))
        self.assertFalse(zone.container_mode(on, exists=lambda p: False), "the setting alone is not a container")
        self.assertFalse(zone.container_mode({}, exists=marker), "a marker alone is not either")
        self.assertFalse(zone.container_mode({"CLARK_CONTAINER": "true"}, exists=marker))

    def test_outside_a_container_nothing_is_given_to_the_server(self):
        self.assertIsNone(zone.make({}, tzset=lambda: None, container=False))
        self.assertIsNone(zone.make({"TZ": "Asia/Dubai"}, tzset=lambda: None, container=False), "the Mac route is unchanged")
        self.assertTrue(callable(zone.make({}, tzset=lambda: None, container=True)))


class Apply(unittest.TestCase):
    def setUp(self):
        self.env, self.calls = {}, []
        self.zone = zone.Zone(self.env, tzset=lambda: self.calls.append(self.env.get("TZ")))

    def test_a_real_name_sets_the_process_zone_once(self):
        self.assertTrue(self.zone.apply("Asia/Dubai"))
        self.assertEqual((self.env["TZ"], self.calls), ("Asia/Dubai", ["Asia/Dubai"]))
        self.assertFalse(self.zone.apply("Asia/Dubai"), "the same zone again changes nothing")
        self.assertTrue(self.zone.apply("America/New_York"), "a laptop that travels follows")
        self.assertEqual(self.calls, ["Asia/Dubai", "America/New_York"])

    def test_a_bad_name_is_ignored_and_the_last_good_zone_stays(self):
        self.zone.apply("Asia/Dubai")
        for bad in NOT_ZONES:
            with self.subTest(bad=bad):
                self.assertFalse(self.zone.apply(bad))
        self.assertEqual((self.env["TZ"], self.calls), ("Asia/Dubai", ["Asia/Dubai"]))

    def test_with_no_header_the_zone_stays_as_it_started(self):
        self.assertFalse(self.zone.apply(None))
        self.assertNotIn("TZ", self.env)
        self.assertEqual(self.calls, [])

    def test_a_pinned_tz_wins_over_the_page(self):
        env, calls = {"TZ": "Europe/London"}, []
        pinned = zone.Zone(env, tzset=lambda: calls.append(1))
        self.assertFalse(pinned.apply("Asia/Dubai"))
        self.assertEqual((env["TZ"], calls), ("Europe/London", []))

    def test_an_empty_or_windows_tz_is_no_pin(self):
        for given in ("", "Arabian Standard Time"):
            env = {"TZ": given}
            self.assertTrue(zone.Zone(env, tzset=lambda: None).apply("Asia/Dubai"), given)
            self.assertEqual(env["TZ"], "Asia/Dubai")

    def test_no_tzset_means_nothing_is_set(self):
        env = {}
        with mock.patch.object(zone.time, "tzset", None, create=True):      # as on Windows, where time.tzset does not exist
            windows = zone.Zone(env)
        self.assertIsNone(windows.tzset)
        self.assertFalse(windows.apply("Asia/Dubai"))
        self.assertNotIn("TZ", env)


class TheClockFollows(KeepsTheZone):
    """The real process zone, set through Zone.apply: everything that reads the zone agrees on the person's day."""

    def test_the_four_todays_agree_on_the_local_date(self):
        process = zone.Zone(os.environ)          # one, as the server has: a TZ already set when one is made would be a pin
        for name, utc, want, _ in CASES:
            with self.subTest(zone=name):
                self.assertTrue(process.apply(name))
                with at(utc):
                    got = {"store": store_module.today(), "milestones": milestones.today(), "sneak": sneak.today().isoformat(),
                           "movement": movement_read.today_text()}
                self.assertEqual(set(got.values()), {want}, got)
                self.assertNotEqual(want, "%04d-%02d-%02d" % utc[:3], "UTC's date is the other one")

    def test_utc_gives_utcs_date_without_a_zone(self):
        with at(DUBAI_NIGHT):
            self.assertEqual(store_module.today(), "2026-11-03", "the fallback: the process zone as it started")

    def test_the_offset_history_excel_and_the_log_follow(self):
        process = zone.Zone(os.environ)
        for name, utc, want, offset in CASES:
            with self.subTest(zone=name):
                process.apply(name)
                with mock.patch.object(store_module, "clock", return_value=utc_clock(utc)):
                    self.assertEqual(store_module.local_offset(), offset)
                stamp = "%04d-%02d-%02d %02d:%02d:%02d" % utc
                shown = history.when_text(stamp, offset)
                self.assertEqual((shown[0][:10], shown[1]), (date.fromisoformat(want).strftime("%d-%m-%Y"), ""), "History")
                self.assertEqual(timefmt.local_text(stamp)[:10], date.fromisoformat(want).strftime("%d-%m-%Y"))
                with mock.patch.object(excel, "clock", return_value=datetime(*utc)):
                    cover = excel.exported_text()
                    self.assertEqual(excel.day().isoformat(), want, "the export's day")
                self.assertIn(f"Exported on {date.fromisoformat(want).strftime('%d-%m-%Y')}", cover)
                self.assertTrue(cover.endswith(f"(UTC{offset})"), cover)
                self.assertEqual(datetime.fromtimestamp(calendar.timegm(utc)).date().isoformat(), want,
                                 "the log's local time (datetime.now) is the person's")


class Server(KeepsTheZone):
    """The server hands the page's X-Clark-Tz to apply_zone before the route runs, and only for a call with the token."""

    def setUp(self):
        super().setUp()
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.action = self.demo.action(owner="Ann Lee")
        self.s = Running(data_for=self.store.data_for, change=changes.make_change(self.store.path, [], USER))
        self.addCleanup(self.s.close)

    def post(self, owner, extra=None, token=None):
        code = self.store.read("projects")[0]["code"]
        row = next(r for r in self.store.data_for(code)["actions"] if r["description"] == "Draft the cut-over plan")
        body = {"project": code, "kind": "actions", "op": "update", "id": row["id"], "changes": {"owner": owner}}
        return self.s.api("POST", "/api/change", json.dumps(body).encode(), extra=extra, token=token)[0]

    def offset(self):
        return self.store.con.execute("SELECT utc_offset FROM applies WHERE apply_id = ?", (self.demo.last_step(),)).fetchone()[0]

    def test_a_post_with_the_header_records_the_pages_offset(self):
        with mock.patch.object(sv, "ZONE", zone.make(os.environ, container=True)):
            self.assertEqual(self.post("Bea Moss", {sv.ZONE_HEADER: "Asia/Dubai"}), 200)
            self.assertEqual(self.offset(), "+04:00")
            self.assertEqual(os.environ["TZ"], "Asia/Dubai")
            self.assertEqual(self.post("Cy Dunn", {sv.ZONE_HEADER: "America/New_York"}), 200)
            self.assertIn(self.offset(), ("-05:00", "-04:00"), "New York, in winter or summer time")

    def test_the_header_reaches_apply_zone_before_the_route_and_only_with_the_token(self):
        seen, order = [], []
        real = sv.here_route
        with mock.patch.object(sv, "ZONE", lambda name: (seen.append(name), order.append("zone"))), \
                mock.patch.object(sv, "here_route", lambda h, req: (order.append("route"), real(h, req))[1]):
            self.assertEqual(self.s.api("POST", "/api/here", b"{}", extra={sv.ZONE_HEADER: "Asia/Dubai"})[0], 200)
            self.assertEqual(self.s.api("GET", "/api/projects", extra={sv.ZONE_HEADER: "America/New_York"})[0], 200)
            self.assertEqual(self.s.api("POST", "/api/here", b"{}")[0], 200)
            self.assertEqual(self.s.api("POST", "/api/here", b"{}", token="wrong", extra={sv.ZONE_HEADER: "Europe/Paris"})[0], 403)
        self.assertEqual(seen, ["Asia/Dubai", "America/New_York", None], "a call without the token never sets the zone")
        self.assertEqual(order[:2], ["zone", "route"])

    def test_a_bad_name_is_ignored_and_never_logged(self):
        lines = []
        handler = logging.Handler()
        handler.emit = lambda record: lines.append(record.getMessage())
        logging.getLogger().addHandler(handler)
        self.addCleanup(logging.getLogger().removeHandler, handler)
        with mock.patch.object(sv, "ZONE", zone.make(os.environ, container=True)):
            self.assertEqual(self.post("Bea Moss", {sv.ZONE_HEADER: "Arabian Standard Time"}), 200)
            self.assertEqual(self.post("Cy Dunn", {sv.ZONE_HEADER: "../../etc/passwd"}), 200)
        self.assertNotIn("TZ", os.environ)
        self.assertEqual(self.offset(), "+00:00", "the container's own zone stays")
        self.assertFalse([l for l in lines if "Arabian" in l or "passwd" in l], lines)

    def test_without_apply_zone_the_header_changes_nothing(self):
        with mock.patch.object(sv, "ZONE", None):
            self.assertEqual(self.post("Bea Moss", {sv.ZONE_HEADER: "Asia/Dubai"}), 200)
        self.assertNotIn("TZ", os.environ)
        self.assertEqual(self.offset(), "+00:00")


class Launcher(unittest.TestCase):
    def test_the_launcher_gives_the_server_zone_make(self):
        from _paths import SRC
        main = (SRC / "clark" / "__main__.py").read_text(encoding="utf-8")
        self.assertIn("server.set_zone(zone.make(environ))", main)

    def test_set_zone(self):
        fn = lambda name: None  # noqa: E731
        with mock.patch.object(sv, "ZONE", None):
            sv.set_zone(fn)
            self.assertIs(sv.ZONE, fn)
            sv.set_zone(None)
            self.assertIsNone(sv.ZONE)


if __name__ == "__main__":
    unittest.main()

"""item 631: the time zone in the Docker route (src/clark/zone.py, with the guarded store.py and server.py).

Run: python3 dev/run_tests.py test_zone
A container runs in UTC; the page sends its zone and the server applies it, so 'today' and the offset on History are the person's.
Nothing here starts a container; the container is stood in for by the setting and marker file, as test_server_container does.
"""
import importlib
import json
import logging
import os
import re
import time
import unittest
from datetime import date, datetime, timezone
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401

from _demo import USER, DemoStore
from clark import milestones, movement_read, server as sv, sneak, store as store_module, zone
Running = importlib.import_module("test_server").Running      # by name: a plain server thread, so this file stays in the quick tier

SENTINEL = "ZQ-SENTINEL-631"
from test_server_container import in_container

HERE = datetime(2026, 11, 13, 22, 0, tzinfo=timezone.utc)       # 22:00 UTC: already 02:00 on the 14th in Dubai, still the 13th in New York
PAGE = ROOT / "src" / "clark" / "page" / "src"


class FixedDate(date):
    """date.today() on a newer Python reads the system clock directly and ignores a patched time.time; this one asks time.time, in the process zone."""
    @classmethod
    def today(cls):
        return cls.fromtimestamp(time.time())


class Zoned(unittest.TestCase):
    """Each test leaves the process zone as it found it."""
    def setUp(self):
        self.had = os.environ.get("TZ")
        self.addCleanup(self.restore)
        for patch in (mock.patch.object(store_module, "clock", return_value=HERE), mock.patch("time.time", return_value=HERE.timestamp()),
                      mock.patch.object(zone, "PINNED", None), mock.patch.object(store_module, "date", FixedDate),
                      mock.patch.object(milestones, "date", FixedDate), mock.patch.object(movement_read, "date", FixedDate),
                      mock.patch.object(sneak, "date", FixedDate)):
            patch.start()
            self.addCleanup(patch.stop)

    def restore(self):
        if self.had is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.had
        time.tzset()

    def days(self):
        """What the four today() copies say."""
        return [store_module.today(), milestones.today(), sneak.today().isoformat(), movement_read.today_text()]


class Apply(Zoned):
    def test_the_four_days_agree_on_the_dubai_date(self):
        self.assertTrue(zone.apply_zone("Asia/Dubai"))
        self.assertEqual(self.days(), ["2026-11-14"] * 4)
        self.assertEqual(store_module.local_offset(), "+04:00")

    def test_and_on_the_new_york_date(self):
        self.assertTrue(zone.apply_zone("America/New_York"))
        self.assertEqual(self.days(), ["2026-11-13"] * 4)
        self.assertEqual(store_module.local_offset(), "-05:00")

    def test_a_bad_name_is_ignored(self):
        zone.apply_zone("Asia/Dubai")
        for bad in ("Nowhere/Land", "", "  ", "../etc/passwd", "Asia/../Dubai", "GMT+4 ; rm", "W. Europe Standard Time", "Asia/Dubai\n", "x" * 200,
                    None, 5, ["Asia/Dubai"], "/Asia/Dubai", "Asia//Dubai", "<+04>-4"):
            with self.subTest(bad=bad):
                self.assertFalse(zone.apply_zone(bad))
                self.assertEqual(os.environ["TZ"], "Asia/Dubai")
        self.assertEqual(store_module.local_offset(), "+04:00")

    def test_nothing_is_applied_where_tzset_does_not_exist(self):
        with mock.patch.object(zone, "time", object()):
            self.assertFalse(zone.apply_zone("Asia/Dubai"))
        self.assertEqual(os.environ.get("TZ"), self.had)


class Header(Zoned):
    def test_only_in_the_container(self):
        self.assertFalse(zone.follow_header("Asia/Dubai", False))
        self.assertEqual(os.environ.get("TZ"), self.had)
        self.assertTrue(zone.follow_header(" Asia/Dubai ", True))
        self.assertEqual(self.days(), ["2026-11-14"] * 4)

    def test_a_pinned_zone_is_kept(self):
        with mock.patch.object(zone, "PINNED", "America/New_York"):
            self.assertFalse(zone.follow_header("Asia/Dubai", True))

    def test_a_bad_header_is_ignored_and_not_logged(self):
        with self.assertLogs(level="DEBUG") as seen:       # assertLogs needs one line (Python 3.9 has no assertNoLogs), so the test logs a sentinel
            logging.getLogger().debug(SENTINEL)
            self.assertFalse(zone.follow_header("Mars/Olympus", True))
            self.assertFalse(zone.follow_header(None, True))
        self.assertEqual([r.getMessage() for r in seen.records], [SENTINEL])
        self.assertEqual(os.environ.get("TZ"), self.had)

    def test_two_overlapping_zones_the_last_one_wins_for_the_whole_process(self):
        """Documented limit: the zone is process-wide, so a second page in another zone replaces the first."""
        self.assertTrue(zone.follow_header("Asia/Dubai", True))
        self.assertEqual(self.days(), ["2026-11-14"] * 4)
        self.assertTrue(zone.follow_header("America/New_York", True))      # a second page, a different zone
        self.assertEqual(self.days(), ["2026-11-13"] * 4)                  # now New York for everyone, the first page included
        self.assertEqual(store_module.local_offset(), "-05:00")

    def test_the_docstring_says_one_zone_for_the_whole_process(self):
        self.assertIn("whole process", zone.__doc__)


class Pin(Zoned):
    """Docker Desktop on Windows can pass TZ as a Windows zone id or as an empty string; neither pins the zone (item 631)."""
    def test_a_windows_zone_id_or_an_empty_value_is_no_pin(self):
        for value in ("Dubai Standard Time", "W. Europe Standard Time", ""):
            with self.subTest(tz=value):
                self.assertIsNone(zone.valid(value or ""))
                with mock.patch.dict(os.environ, {"TZ": value}):
                    pinned = zone.valid(os.environ.get("TZ") or "")
                self.assertIsNone(pinned)

    def test_the_page_zone_is_applied_when_the_pin_is_a_windows_id(self):
        os.environ["TZ"] = "Dubai Standard Time"
        self.assertTrue(zone.follow_header("America/New_York", True))
        self.assertEqual(self.days(), ["2026-11-13"] * 4)

    def test_the_image_has_zone_data_for_a_zone_with_daylight_saving(self):
        from zoneinfo import ZoneInfo
        for name in ("Asia/Dubai", "America/New_York"):
            with self.subTest(zone=name):
                ZoneInfo(name)
                self.assertEqual(zone.valid(name), name)


class Recorded(Zoned):
    def test_a_step_made_in_the_dubai_zone_records_plus_four(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        a = demo.action()
        zone.apply_zone("Asia/Dubai")
        with demo.store.step("dashboard", USER) as st:
            st.update("actions", a, {"owner": "Someone"})
        got = demo.store.con.execute("SELECT utc_offset FROM applies WHERE apply_id = ?", (demo.last_step(),)).fetchone()[0]
        self.assertEqual(got, "+04:00")

    def test_history_and_the_excel_cover_show_the_dubai_offset(self):
        from clark import excel, history
        demo = DemoStore()
        self.addCleanup(demo.close)
        a = demo.action()
        zone.apply_zone("Asia/Dubai")
        demo.update("actions", a, {"owner": "Someone"})
        rows = [r for r in history.rows_for_project(demo.store.con, "ABC") if r["step"] == demo.last_step()]
        self.assertTrue(rows)
        self.assertEqual({r["when_text"] for r in rows}, {"14-11-2026 02:00"})          # 22:00 UTC on the 13th, made at +04:00
        with mock.patch.object(excel, "clock", return_value=HERE.replace(tzinfo=None)):
            self.assertEqual(excel.exported_text(), "14-11-2026 02:00 (UTC+04:00)")


class Served(Zoned):
    """Through the real server, as the container runs it."""
    def setUp(self):
        super().setUp()
        stamped = []

        def change(req):
            stamped.append(store_module.checked_offset(store_module.local_offset()))       # the value every step writes as its utc_offset
            return 200, {"ok": True}
        self.stamped = stamped
        self.s = Running(change=change)
        self.addCleanup(self.s.close)
        self.patches = in_container()

    def post(self, tz=None):
        return self.s.api("POST", "/api/change", b"{}", extra={"X-Tz": tz} if tz is not None else None)[0]

    def test_a_post_with_the_header_records_the_dubai_offset(self):
        with self.patches[0], self.patches[1], self.patches[2]:
            os.environ["TZ"] = "UTC"
            time.tzset()
            self.assertEqual(self.post("Asia/Dubai"), 200)
            self.assertEqual(self.post("America/New_York"), 200)
            self.assertEqual(self.post("Not/AZone"), 200)
            self.assertEqual(self.post(), 200)
        self.assertEqual(self.stamped, ["+04:00", "-05:00", "-05:00", "-05:00"])

    def test_outside_the_container_the_header_changes_nothing(self):
        os.environ["TZ"] = "UTC"
        time.tzset()
        self.assertEqual(self.post("Asia/Dubai"), 200)
        self.assertEqual(self.stamped, ["+00:00"])

    def test_the_heartbeat_applies_it_and_a_page_load_does_not(self):
        with self.patches[0], self.patches[1], self.patches[2]:
            os.environ["TZ"] = "UTC"
            time.tzset()
            status = self.s.api("POST", "/api/here", b"{}", extra={"X-Tz": "Asia/Dubai"})[0]
            self.assertEqual(status, 200)
            self.assertEqual(store_module.today(), "2026-11-14")
            self.s.ask("GET", "/health")
            self.assertEqual(store_module.today(), "2026-11-14", "a request with no header leaves the zone as it is")
            self.s.ask("GET", "/", {"X-Tz": "America/New_York"})
            self.assertEqual(store_module.today(), "2026-11-14", "the page is served without a token, so it does not move the zone")

    def test_a_request_without_the_token_does_not_change_the_zone(self):
        with self.patches[0], self.patches[1], self.patches[2]:
            os.environ["TZ"] = "UTC"
            time.tzset()
            self.assertEqual(self.s.api("POST", "/api/here", b"{}", extra={"X-Tz": "Asia/Dubai"})[0], 200)
            for method, path in (("GET", "/api/state"), ("GET", "/api/nothing-here"), ("GET", "/health"), ("GET", "/")):
                self.s.ask(method, path, {"X-Tz": "America/New_York"})                           # no token
                self.s.ask(method, path, {"X-Tz": "America/New_York", sv.TOKEN_HEADER: "wrong-token"})
            status = self.s.api("POST", "/api/change", b"{}", token="wrong-token", extra={"X-Tz": "America/New_York"})[0]
            self.assertEqual(status, 403)
            self.assertEqual(store_module.today(), "2026-11-14")
            self.assertEqual(os.environ["TZ"], "Asia/Dubai")

    def test_a_get_with_the_token_follows_the_zone(self):
        with self.patches[0], self.patches[1], self.patches[2]:
            os.environ["TZ"] = "UTC"
            time.tzset()
            self.s.ask("GET", "/api/nothing-here", {sv.TOKEN_HEADER: sv.TOKEN, "X-Tz": "America/New_York"})
            self.assertEqual(os.environ["TZ"], "America/New_York")


class Source(unittest.TestCase):
    def test_api_js_requests_and_the_heartbeat_carry_the_header(self):
        api, app = (PAGE / "api.js").read_text(encoding="utf-8"), (PAGE / "app.js").read_text(encoding="utf-8")
        self.assertIn('"X-Tz"', api)
        self.assertIn("globalThis.fetch(", api)
        self.assertIn("Intl.DateTimeFormat().resolvedOptions().timeZone", api)
        self.assertIn('"X-Tz"', app)
        self.assertIn("Intl.DateTimeFormat().resolvedOptions().timeZone", app)
        self.assertEqual(zone.HEADER, "X-Tz")

    def test_the_compose_file_offers_an_optional_pin(self):
        text = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn('TZ: "${TZ:-}"', text)

    def test_the_server_reads_the_zone_by_name_and_imports_no_clark_module(self):
        src = (ROOT / "src" / "clark" / "server.py").read_text(encoding="utf-8")
        self.assertIn('importlib.import_module("clark.zone")', src)
        self.assertEqual(src.count("self.follow_zone()"), 3)


class EditFetches(unittest.TestCase):
    """item 631: a call from the editing page to clark goes through zoneFetch (api.js), which adds X-Tz; a bare fetch would skip it."""
    BARE_OK = {"edit/FeedbackTag.jsx"}      # the health check: it asks for no zone and the server follows none on it

    def test_no_edit_file_calls_a_bare_fetch(self):
        bare = []
        for path in sorted((PAGE / "edit").rglob("*.js*")):
            name = path.relative_to(PAGE).as_posix()
            if name in self.BARE_OK:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code = line.split("//")[0]
                if re.search(r"(?<![\w.])fetch\(|\|\| fetch\)", code):
                    bare.append(f"{name}:{n}")
        self.assertEqual(bare, [])

    def test_zone_fetch_is_exported_and_adds_the_header(self):
        src = (PAGE / "api.js").read_text(encoding="utf-8")
        self.assertIn("export const zoneFetch", src)
        self.assertIn('"X-Tz": tz', src)

    def test_the_header_is_named_x_tz_everywhere(self):
        for path in PAGE.rglob("*.js*"):
            self.assertNotIn("X-Clark-Tz", path.read_text(encoding="utf-8"), path.name)


if __name__ == "__main__":
    unittest.main()

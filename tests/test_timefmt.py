"""#75: times are shown in the user's local time, DD-MM-YYYY HH:MM; stored times stay UTC."""
import os
import time
import unittest
from unittest import mock

from clark import store, timefmt


def in_zone(name):
    """Run the body with the process's local time zone set to `name` (POSIX TZ), put back afterwards."""
    class Zone:
        def __enter__(self):
            self.old = os.environ.get("TZ")
            os.environ["TZ"] = name
            time.tzset()

        def __exit__(self, *exc):
            if self.old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = self.old
            time.tzset()
    return Zone()


class LocalTime(unittest.TestCase):
    def test_the_same_moment_reads_as_each_zones_own_time(self):
        stamp = "2026-10-28 22:30:09.123"                      # as the store writes it: UTC
        expect = {"UTC": "28-10-2026 22:30", "Asia/Dubai": "29-10-2026 02:30", "America/New_York": "28-10-2026 18:30",
                  "Pacific/Auckland": "29-10-2026 11:30", "Asia/Kolkata": "29-10-2026 04:00"}
        for zone, text in expect.items():
            with self.subTest(zone=zone), in_zone(zone):
                self.assertEqual(timefmt.local_text(stamp), text)

    def test_the_last_moment_of_year_9999_east_of_utc_is_returned_not_a_crash(self):
        """A backup called clark-99991231T235959Z-daily.db: converting it overflows east of UTC (Medium 4 of the #86 read)."""
        for zone in ("Pacific/Kiritimati", "Asia/Dubai", "UTC", "America/New_York"):
            with self.subTest(zone=zone), in_zone(zone):
                for stamp in ("99991231T235959Z", "9999-12-31 23:59:59.999"):
                    self.assertIsInstance(timefmt.local_text(stamp), str)
        with in_zone("Pacific/Kiritimati"):
            self.assertEqual(timefmt.local_text("99991231T235959Z"), "99991231T235959Z", "shown as it is when it can't be converted")

    def test_summer_time_is_followed(self):
        with in_zone("Europe/London"):
            self.assertEqual(timefmt.local_text("2026-07-01 12:00:00.000"), "01-07-2026 13:00")      # BST
            self.assertEqual(timefmt.local_text("2026-12-01 12:00:00.000"), "01-12-2026 12:00")      # GMT

    def test_a_time_with_a_zone_keeps_it(self):
        with in_zone("Asia/Dubai"):
            self.assertEqual(timefmt.local_text("2026-10-28T10:00:00Z"), "28-10-2026 14:00")
            self.assertEqual(timefmt.local_text("2026-10-28T10:00:00+02:00"), "28-10-2026 12:00")
            self.assertEqual(timefmt.local_text("2026-10-28 10:00"), "28-10-2026 14:00")             # no zone: UTC

    def test_the_store_writes_what_this_module_reads(self):
        with in_zone("Asia/Dubai"):
            self.assertRegex(timefmt.local_text(store.now()), r"^\d\d-\d\d-\d{4} \d\d:\d\d$")

    def test_a_fixed_store_clock_shows_in_local_time(self):
        from datetime import datetime, timezone
        fixed = datetime(2030, 1, 2, 3, 4, 5, 678000, tzinfo=timezone.utc)
        with mock.patch.object(store, "clock", lambda: fixed), in_zone("America/New_York"):
            self.assertEqual(timefmt.local_text(store.now()), "01-01-2030 22:04")

    def test_empty_and_odd_values_do_not_break_a_screen(self):
        self.assertIsNone(timefmt.local_text(None))
        self.assertEqual(timefmt.local_text(""), "")
        self.assertEqual(timefmt.local_text("last Tuesday"), "last Tuesday")
        self.assertEqual(timefmt.local_text("2026-10-28"), "2026-10-28")       # a calendar date alone is never shifted

    def test_calendar_dates_are_not_this_modules_business(self):
        for zone in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):                # the two extremes: +14 and -11
            with in_zone(zone):
                self.assertEqual(timefmt.local_text("2026-10-28"), "2026-10-28")

    def test_a_backups_compact_name_time_is_utc_and_shows_in_local_time(self):        # #86 test 25
        for zone, text in (("UTC", "28-10-2026 14:30"), ("Asia/Dubai", "28-10-2026 18:30"),
                           ("America/New_York", "28-10-2026 10:30"), ("Asia/Kolkata", "28-10-2026 20:00")):
            with self.subTest(zone=zone), in_zone(zone):
                self.assertEqual(timefmt.local_text("20261028T143005Z"), text)

    def test_a_compact_time_needs_its_t_and_z_and_a_real_date(self):                # #86 test 25
        for odd in ("20261028143005", "20261028T143005", "20261028 143005Z", "20261328T143005Z",
                    "20261028T256005Z", "clark-20261028T143005Z-undo.db", "20261028T14:30:05Z"):
            with self.subTest(odd=odd):
                self.assertEqual(timefmt.local_text(odd), odd)


if __name__ == "__main__":
    unittest.main()

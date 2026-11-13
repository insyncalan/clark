"""Calendar days are written DD-MM-YYYY the same way on every screen and export: a real day (29 Feb in a leap year, month ends,
2099) is rewritten, never moved by the time zone; empty, a time-less word or an impossible day (29 Feb 2026, month 13) is shown as stored."""
import os
import time
import unittest

from clark import ask_data, excel_cover, glance, history, milestone_rows, sneak, store, timefmt

SHOWERS = {"glance": glance.show_date, "excel_cover": excel_cover.show_date, "milestone_rows": milestone_rows.shown,
           "store": store.shown, "ask_data": ask_data._shown_date, "history": history._dmy, "sneak": sneak._dmy,
           "timefmt": timefmt.day_text}
REAL = {"2028-02-29": "29-02-2028", "2026-02-28": "28-02-2026", "2026-10-31": "31-10-2026", "2099-12-31": "31-12-2099",
        "2026-03-29": "29-03-2026", "2026-10-25": "25-10-2026"}
IMPOSSIBLE = ["2026-02-29", "2026-13-01", "2026-04-31", "2026-00-10"]


class DayWords(unittest.TestCase):
    def test_real_days_in_every_zone(self):
        old = os.environ.get("TZ")
        try:
            for zone in ("UTC", "Europe/London", "Pacific/Auckland", "America/Los_Angeles"):
                os.environ["TZ"] = zone
                time.tzset()
                for name, show in SHOWERS.items():
                    for iso, want in REAL.items():
                        self.assertEqual(show(iso), want, (name, zone, iso))
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            time.tzset()

    def test_impossible_days_are_shown_as_stored(self):
        for name, show in SHOWERS.items():
            for iso in IMPOSSIBLE:
                self.assertEqual(show(iso), iso, (name, iso))

    def test_words_are_not_cut_up(self):
        for name, show in SHOWERS.items():
            self.assertEqual(show("not a date at all"), "not a date at all", name)
            self.assertEqual(show("soon"), "soon", name)

    def test_empty_never_fails(self):
        for name, show in SHOWERS.items():
            for empty in ("", None):
                self.assertIn(show(empty), ("", None, "—"), (name, empty))

    def test_day_with_a_time_is_read_only_when_asked(self):
        for stamp in ("2026-10-25 14:00:00", "2026-10-25T14:00:00"):
            self.assertEqual(timefmt.day_text(stamp, prefix=True), "25-10-2026", stamp)
            self.assertEqual(timefmt.day_text(stamp), stamp, stamp)
        for stamp in ("2026-10-25x", "2026-10-250", "2026-13-01 14:00"):
            self.assertEqual(timefmt.day_text(stamp, prefix=True), stamp, stamp)


if __name__ == "__main__":
    unittest.main()

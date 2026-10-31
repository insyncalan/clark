"""#75 for the Excel export: a time shown to a person is the user's local time (DD-MM-YYYY HH:MM); a time kept for the
machine stays UTC; a date is never moved by a zone. Two zones (Asia/Dubai, America/New_York) with a fixed clock. Fictional data.

Run: python3 dev/run_tests.py test_excel_time
Needs time.tzset (POSIX); without it these tests are skipped.
"""
import contextlib
import json
import os
import shutil
import tempfile
import time
import unittest
import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401  (puts src/ and vendor/ on the path)
from openpyxl import load_workbook

from clark import excel
from clark import excel_colours as colours

DUBAI, NEW_YORK = "Asia/Dubai", "America/New_York"
ZONES = (DUBAI, NEW_YORK)
NOW = datetime(2030, 6, 1, 20, 30, 45, 123456)    # UTC: 02-06-2030 00:30 in Dubai (UTC+4), 01-06-2030 16:30 in New York (EDT)


@contextlib.contextmanager
def zone(name):
    """The process runs in time zone `name` (TZ and time.tzset), then as it was."""
    before = os.environ.get("TZ")
    os.environ["TZ"] = name
    time.tzset()
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = before
        time.tzset()


@unittest.skipUnless(hasattr(time, "tzset"), "time.tzset is not available on this platform, so a zone cannot be set")
class ExcelTimeTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-excel-time-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.n = 0

    def rows(self, **fields):
        return {"actions": [{"id": "DEMO-A-001", "project": "DEMO", "raised": "2030-01-01", "due_date": "2030-06-01",
                             "status": "Open", "description": "x", "client_message": "", "client_visible": 1, "source": "demo",
                             "updated_at": "2030-01-10 09:30:00.000", **fields}]}

    def export(self, tz, now=NOW, on=None):
        """Export in zone `tz` with the clock fixed at `now` (UTC); returns (bytes, state-file entry, path)."""
        self.n += 1
        path, state = self.dir / f"{self.n}.xlsx", self.dir / f"state{self.n}.json"
        with zone(tz), mock.patch.object(excel, "clock", lambda: now):
            excel.export(path, "DEMO", self.rows(), state, on=on)
        entry = json.loads(state.read_text(encoding="utf-8"))["workbooks"][excel._key(path)]
        return path.read_bytes(), entry, path

    def test_exported_text_is_the_local_time_in_each_zone(self):
        for tz, want in ((DUBAI, "Exported on 02-06-2030 at 00:30 (UTC+04:00)"), (NEW_YORK, "Exported on 01-06-2030 at 16:30 (UTC-04:00)")):
            with self.subTest(tz=tz), zone(tz), mock.patch.object(excel, "clock", lambda: NOW):
                self.assertEqual(excel.exported_text(), want)

    def test_exported_text_follows_the_zone_rules_in_winter(self):
        winter = datetime(2030, 1, 15, 12, 0, 0)             # New York is UTC-5 (EST) then; Dubai has no daylight saving
        for tz, want in ((DUBAI, "Exported on 15-01-2030 at 16:00 (UTC+04:00)"), (NEW_YORK, "Exported on 15-01-2030 at 07:00 (UTC-05:00)")):
            with self.subTest(tz=tz), zone(tz), mock.patch.object(excel, "clock", lambda: winter):
                self.assertEqual(excel.exported_text(), want)

    def test_exported_text_with_a_pinned_day_is_midnight_utc_in_the_local_zone(self):
        for tz, want in ((DUBAI, "Exported on 01-06-2030 at 04:00 (UTC+04:00)"), (NEW_YORK, "Exported on 31-05-2030 at 20:00 (UTC-04:00)")):
            with self.subTest(tz=tz), zone(tz):
                self.assertEqual(excel.exported_text("2030-06-01"), want)

    def test_the_workbook_bytes_are_the_same_in_every_zone(self):
        """The data sheets show no local time (only the Cover's exported line does, and this export has no Cover): the
        same data and clock give the same bytes in any zone. With `on` that holds
        always. Without it the clock's local day sets 'today' (late dates), so the clock is placed where both zones are on
        the same day; test_late_dates_are_drawn_against_the_local_day covers the case where they are not."""
        midday = datetime(2030, 6, 1, 10, 0, 0)            # 14:00 on 01-06 in Dubai, 06:00 on 01-06 in New York
        for on, now in (("2030-06-01", NOW), (None, midday)):
            with self.subTest(on=on):
                a, b = self.export(DUBAI, now=now, on=on)[0], self.export(NEW_YORK, now=now, on=on)[0]
                self.assertEqual(a, b)

    def test_stored_times_stay_utc_in_every_zone(self):
        """exported_at and the workbook's created and modified times are UTC (machine values), whatever the zone."""
        for tz in ZONES:
            with self.subTest(tz=tz):
                data, entry, path = self.export(tz)
                self.assertEqual(entry["exported_at"], "2030-06-01 20:30:45")
                with zipfile.ZipFile(path) as z:
                    core = z.read("docProps/core.xml").decode("utf-8")
                self.assertEqual(core.count("2030-06-01T20:30:45"), 2)

    def test_the_updated_cell_is_the_stored_utc_text_in_every_zone(self):
        """The import compares this cell to the database's UTC text, so it is never converted."""
        for tz in ZONES:
            with self.subTest(tz=tz):
                path = self.export(tz)[2]
                ws = load_workbook(path)["Actions"]
                head = [c.value for c in ws[1]]
                self.assertEqual(ws.cell(row=2, column=head.index("Updated") + 1).value, "2030-01-10 09:30:00.000")
                self.assertEqual(excel.read_workbook(path)["actions"][0]["updated_at"], "2030-01-10 09:30:00.000")

    def test_a_date_only_cell_is_never_shifted_by_a_zone(self):
        for tz in ZONES:
            with self.subTest(tz=tz):
                path = self.export(tz, now=datetime(2030, 6, 1, 23, 59, 59))[2]       # a minute from midnight UTC
                ws = load_workbook(path)["Actions"]
                head = [c.value for c in ws[1]]
                for label, want in (("Due", date(2030, 6, 1)), ("Raised", date(2030, 1, 1))):
                    cell = ws.cell(row=2, column=head.index(label) + 1)
                    self.assertEqual(cell.value, datetime(want.year, want.month, want.day))
                    self.assertEqual(cell.number_format, "dd-mm-yyyy")
                got = excel.read_workbook(path)["actions"][0]
                self.assertEqual((got["due_date"], got["raised"]), ("2030-06-01", "2030-01-01"))

    def test_today_is_the_calendar_day_where_the_user_is(self):
        """22:00 UTC on 01-06-2030 is already 02-06 in Dubai but still 01-06 in New York; `on` is a date and never moves."""
        late = datetime(2030, 6, 1, 22, 0, 0)
        for tz, want in ((DUBAI, date(2030, 6, 2)), (NEW_YORK, date(2030, 6, 1))):
            with self.subTest(tz=tz), zone(tz), mock.patch.object(excel, "clock", lambda: late):
                self.assertEqual(excel.day(), want)
                self.assertEqual(excel.day("2030-06-01"), date(2030, 6, 1))

    def test_lateness_is_a_live_rule_that_does_not_depend_on_the_zone_of_the_export(self):
        """#85c: the red date is a formula rule that Excel works out against its own today, so the export's local day (the
        zone it was made in) no longer decides it: the same rule is written in every zone."""
        late = datetime(2030, 6, 1, 22, 0, 0)
        rules = {}
        for tz in ZONES:
            ws = load_workbook(self.export(tz, now=late)[2])["Actions"]
            found = [r.formula for cf in ws.conditional_formatting for r in cf.rules if r.type == "expression"]
            self.assertEqual(len(found), 1, tz)
            self.assertIn("TODAY()", found[0][0])
            rules[tz] = found
            head = [c.value for c in ws[1]]
            font = ws.cell(row=2, column=head.index("Due") + 1).font
            self.assertFalse(font.color is not None and str(font.color.rgb)[-6:] == colours.LATE_TEXT, tz)   # no static red
        self.assertEqual(len({str(v) for v in rules.values()}), 1)


if __name__ == "__main__":
    unittest.main()

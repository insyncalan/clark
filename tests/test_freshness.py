"""#119 (pure part): the data-freshness rules (src/clark/freshness.py) and the Work items 'Not reviewed' filter value.

Run: python3 dev/run_tests.py test_freshness
Every test fixes "today". All rows are fictional. The history events are shaped as history.history gives them.
"""
import unittest
from datetime import timezone, timedelta
from pathlib import Path

from _paths import ROOT

from clark import freshness as f

try:
    from zoneinfo import ZoneInfo
except ImportError:                                   # pragma: no cover
    ZoneInfo = None

# The same fixtures in Python and in the page: only YYYY-MM-DD is a day (no time part, week date or compact form).
GOOD_DAY = "2026-10-29"
BAD_DAYS = ["2026-W44-3", "20261029", "2026-10-29T10:00:00", "2026-302", "2026-10-29 ", "2026-02-30"]
ROW = {"id": "ABC-A-001", "status": "Open", "archived": 0}


def ev(at, actor="you", route="dashboard", n=[0], **more):
    n[0] += 1
    return {"event_id": n[0], "at": at, "actor": actor, "route": route, "is_undo": False, "undoes": None, **more}


class Rules(unittest.TestCase):
    def test_raised_is_the_first_history_row_whatever_the_order(self):
        h = [ev("2026-10-20 09:00:00.000"), ev("2026-10-01 09:00:00.000", route="excel"), ev("2026-10-10 09:00:00.000")]
        self.assertEqual(f.raised(h, timezone.utc), "2026-10-01")
        self.assertEqual(f.raised(list(reversed(h)), timezone.utc), "2026-10-01")

    def test_last_reviewed_is_the_latest_change_by_a_person(self):
        h = [ev("2026-10-01 09:00:00.000"), ev("2026-10-05 09:00:00.000"), ev("2026-10-09 09:00:00.000", actor="clark", route="assistant"),
             ev("2026-10-12 09:00:00.000", route="excel"), ev("2026-10-13 09:00:00.000", route="migrate"),
             ev("2026-10-14 09:00:00.000", route="undo", is_undo=True)]
        self.assertEqual(f.last_reviewed(h, timezone.utc), "2026-10-05")

    def test_empty_history_has_no_dates_and_no_flag(self):
        self.assertIsNone(f.raised([], timezone.utc))
        self.assertIsNone(f.last_reviewed(None, timezone.utc))
        self.assertFalse(f.not_reviewed(ROW, [], "2026-12-31"))
        self.assertEqual(f.freshness(ROW, [], "2026-10-28"), {"raised": None, "last_reviewed": None, "days_since": None, "not_reviewed": False})

    def test_import_only_history_has_no_last_reviewed_and_is_judged_from_raised(self):
        h = [ev("2026-10-01 09:00:00.000", route="excel"), ev("2026-10-02 09:00:00.000", actor="clark", route="assistant")]
        self.assertIsNone(f.last_reviewed(h, timezone.utc))
        self.assertEqual(f.freshness(ROW, h, "2026-10-20", tz=timezone.utc),
                         {"raised": "2026-10-01", "last_reviewed": None, "days_since": 19, "not_reviewed": True})
        self.assertFalse(f.not_reviewed(ROW, h, "2026-10-15", tz=timezone.utc))

    def test_exactly_n_days_is_not_flagged_and_one_more_is(self):
        h = [ev("2026-10-01 09:00:00.000")]
        self.assertFalse(f.not_reviewed(ROW, h, "2026-10-15", 14, timezone.utc))
        self.assertTrue(f.not_reviewed(ROW, h, "2026-10-16", 14, timezone.utc))
        self.assertTrue(f.not_reviewed(ROW, h, "2026-10-03", 1, timezone.utc))
        self.assertFalse(f.not_reviewed(ROW, h, "2026-10-02", 1, timezone.utc))

    def test_default_is_fourteen_and_n_is_a_parameter(self):
        h = [ev("2026-10-01 09:00:00.000")]
        self.assertEqual(f.DEFAULT_DAYS, 14)
        self.assertTrue(f.not_reviewed(ROW, h, "2026-10-16", tz=timezone.utc))
        self.assertFalse(f.not_reviewed(ROW, h, "2026-10-16", 30, timezone.utc))

    def test_closed_cancelled_made_withdrawn_and_archived_are_never_flagged(self):
        h = [ev("2026-01-01 09:00:00.000")]
        for status in ("Closed", "Cancelled", "Made", "Withdrawn"):
            self.assertFalse(f.not_reviewed({**ROW, "status": status}, h, "2026-10-28", tz=timezone.utc), status)
        self.assertFalse(f.not_reviewed({**ROW, "archived": 1}, h, "2026-10-28", tz=timezone.utc))
        self.assertTrue(f.not_reviewed({**ROW, "status": "Delayed"}, h, "2026-10-28", tz=timezone.utc))

    def test_a_late_evening_change_counts_on_the_users_day(self):
        h = [ev("2026-10-01 23:30:00.000")]                                  # 00:30 on the 2nd in a UTC+1 zone
        self.assertEqual(f.raised(h, timezone(timedelta(hours=1))), "2026-10-02")
        self.assertEqual(f.raised(h, timezone.utc), "2026-10-01")

    def test_midnight_does_not_move_the_count(self):
        a = [ev("2026-10-01 00:00:00.000")]
        b = [ev("2026-10-01 23:59:59.999")]
        for h in (a, b):
            self.assertFalse(f.not_reviewed(ROW, h, "2026-10-15", tz=timezone.utc))
            self.assertTrue(f.not_reviewed(ROW, h, "2026-10-16", tz=timezone.utc))

    @unittest.skipIf(ZoneInfo is None, "no zoneinfo")
    def test_a_clock_change_does_not_move_the_count(self):
        try:
            london = ZoneInfo("Europe/London")
        except Exception:                                                    # no tz database on this machine
            self.skipTest("no tz database")
        # Clocks went back in London that Sunday: the day has 25 hours. The 24th and the 26th are still two calendar days apart.
        h = [ev("2026-10-24 12:00:00.000")]
        self.assertEqual(f.days_between(f.raised(h, london), "2026-10-26"), 2)
        spring = [ev("2026-03-28 12:00:00.000")]                             # clocks go forward the next day (a 23-hour day)
        self.assertEqual(f.days_between(f.raised(spring, london), "2026-04-11"), 14)
        self.assertFalse(f.not_reviewed(ROW, spring, "2026-04-11", tz=london))
        self.assertTrue(f.not_reviewed(ROW, spring, "2026-04-12", tz=london))
        # an evening just before midnight UTC in summer is already the next day in London
        self.assertEqual(f.raised([ev("2026-07-01 23:30:00.000")], london), "2026-07-02")

    def test_odd_values_never_raise(self):
        h = [ev("not a time"), ev(None), ev("2026-10-01 09:00:00.000")]
        self.assertEqual(f.raised(h, timezone.utc), "2026-10-01")
        self.assertFalse(f.not_reviewed(ROW, h, "garbage", tz=timezone.utc))
        self.assertIsNone(f.days_between("2026-02-30", "2026-03-01"))

    def test_only_a_plain_date_is_a_day(self):
        for bad in BAD_DAYS:
            with self.subTest(bad=bad):
                self.assertIsNone(f.days_between(bad, "2026-11-01"))
                self.assertIsNone(f.days_between("2026-10-01", bad))
        self.assertEqual(f.days_between(GOOD_DAY, "2026-11-01"), 3)


class FilterValue(unittest.TestCase):
    """The page's filters.js carries the same rule; its value is checked in node when node is on the machine."""

    def run_js(self, body):
        import json
        import shutil
        import subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        src = ROOT / "src" / "clark" / "page" / "src"
        code = f'import * as F from "{(src / "filters.js").as_uri()}"; import * as W from "{(src / "workItems.js").as_uri()}"; {body}'
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_not_reviewed_reads_dates_when_present_and_flags_nothing_when_absent(self):
        out = self.run_js('''const T = "2026-10-28", v = (r) => F.valueOf(r, "reviewed", T);
          console.log(JSON.stringify([
            v({status: "Open"}), v({status: "Open", raised: "2026-10-14"}), v({status: "Open", raised: "2026-10-13"}),
            v({status: "Open", raised: "2026-01-01", last_reviewed: "2026-10-20"}), v({status: "Open", last_reviewed: "2026-10-13"}),
            v({status: "Closed", raised: "2026-01-01"}), v({status: "Open", not_reviewed: true}), v({status: "Open", raised: "2026-01-01", not_reviewed: false}),
            v({status: "Open", raised: "nonsense"}), F.labelOf("reviewed", "stale"), F.NAMES.reviewed]));''')
        self.assertEqual(out, ["", "", "stale", "", "stale", "", "stale", "", "", "Not reviewed in 14 days", "Freshness"])

    def test_the_page_reads_only_a_plain_date(self):
        import json as _j
        out = self.run_js(f"console.log(JSON.stringify({_j.dumps(BAD_DAYS + [GOOD_DAY])}.map((d) => W.dayNumber(d))));")
        self.assertEqual(out[:-1], [None] * len(BAD_DAYS))
        self.assertIsNotNone(out[-1])

    def test_the_filter_selects_and_counts(self):
        out = self.run_js('''const T = "2026-10-28", rows = [{id: "a", kind: "action", status: "Open", raised: "2026-10-01"}, {id: "b", kind: "action", status: "Open"}];
          const s = F.toggleValue(F.initial(), "reviewed", "stale");
          console.log(JSON.stringify([F.applyFilters(rows, s, T).map((r) => r.id), F.options(rows, "reviewed", s, T), F.encode(s), F.decode(F.encode(s)).filters]));''')
        self.assertEqual(out[0], ["a"])
        self.assertEqual(out[1], [{"value": "stale", "label": "Not reviewed in 14 days", "count": 1, "chosen": True},
                                  {"value": "incomplete", "label": "No owner or no date", "count": 2, "chosen": False}])   # #159: both rows have no owner
        self.assertEqual(out[2], "reviewed:stale")
        self.assertEqual(out[3], {"reviewed": ["stale"]})


if __name__ == "__main__":
    unittest.main()

"""Bundle 2 (row 1006, 1084 and the hostile-input fixes): hostile inputs on every changed Python input path, and one test per
behaviour that goes red when that behaviour is broken (mutation checked).

Run: python3 dev/run_tests.py test_bundle2_hostile_mutants
"""
import importlib.util
import re
import unittest
from pathlib import Path

import _paths  # noqa: F401
from clark import glance, milestones, secret_screen

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("check_release_assets", ROOT / "dev" / "tools" / "check_release_assets.py")
cra = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cra)

HOSTILE = ["", None, 0, 5, 1e99, [], {}, [1], {"a": 1}, True, "x" * 100000, "é‮\x00\n'\"<b>&amp;", "2026-13-45",
           "２０２６-01-01", "9999-99-99", "2026-02-30", "  2026-01-01  "]


class MilestonesHostile(unittest.TestCase):
    def rows(self, h):
        return [{"baseline_date": h, "forecast_date": h, "state": h, "state_set": 1, "status": "Planned"},
                {"baseline_date": "2026-01-01", "forecast_date": h, "state": h, "state_set": 1},
                {"baseline_date": h, "status": h}, {"state": h, "state_set": h, "status": "Planned"}]

    def test_no_function_raises_for_any_hostile_value_in_any_column_or_day(self):
        for h in HOSTILE:
            for fn in (milestones.suggested_state, milestones.milestone_state, milestones.needs_reason, milestones.slip_days):
                for row in self.rows(h):
                    for on in (h, None, "2026-06-01"):
                        with self.subTest(fn=fn.__name__, h=repr(h)[:20], on=repr(on)[:20]):
                            fn(row, on)
            with self.subTest(client_word=repr(h)[:20]):
                self.assertIsInstance(milestones.client_word(h), str)

    def test_a_non_text_date_reads_as_no_date(self):
        for h in (5, [], {}, True, 1e99):
            row = {"baseline_date": h, "forecast_date": h, "status": "Planned"}
            self.assertEqual(milestones.suggested_state(row, "2026-06-01"), "On track")
            self.assertIsNone(milestones.slip_days(row, "2026-06-01"))

    def test_a_bad_day_given_falls_back_to_today_not_a_crash(self):
        row = {"baseline_date": "2000-01-01", "status": "Planned"}
        for bad in ("", "x", "2026-13-45", 7, [], "‮"):
            self.assertEqual(milestones.suggested_state(row, bad), "Overdue", repr(bad))
            self.assertGreater(milestones.slip_days(row, bad), 0)

    def test_a_stored_state_that_is_no_state_is_ignored(self):
        row = {"baseline_date": "2099-01-01", "state_set": 1, "status": "Planned"}
        for bad in ([], {}, "Bogus", "", 3, "At risk\x00", "<b>At risk</b>"):
            self.assertEqual(milestones.milestone_state({**row, "state": bad}, "2026-06-01"), "On track", repr(bad))
            self.assertFalse(milestones.needs_reason({**row, "state": bad}, "2026-06-01"), repr(bad))
        self.assertEqual(milestones.milestone_state({**row, "state": "At risk"}, "2026-06-01"), "At risk")
        self.assertEqual(milestones.milestone_state({**row, "state": "Forecast"}, "2026-06-01"), "Forecast")

    def test_a_state_unhashable_does_not_raise_in_the_in_test(self):
        for bad in ([], {}, [1, 2], {"a": 1}):
            self.assertEqual(milestones.client_word(bad), "")

    def test_client_words(self):
        self.assertEqual(milestones.client_word("Slipped"), "Expected later")
        self.assertEqual(milestones.client_word("Overdue"), "Late")
        self.assertEqual(milestones.client_word("nonsense"), "")

    def test_slip_days_counts_from_the_forecast_and_today(self):
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-01-01", "forecast_date": "2026-01-11", "status": "Planned"}, "2025-12-01"), 10)
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-01-01", "status": "Planned"}, "2026-01-05"), 4)
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-01-01", "forecast_date": "junk", "status": "Planned"}, "2025-12-01"), 0)
        self.assertIsNone(milestones.slip_days({"baseline_date": "2026-01-01", "status": "Done"}, "2026-01-05"))

    def test_needs_reason_when_the_user_is_kinder_than_the_dates(self):
        row = {"baseline_date": "2026-01-01", "state": "On track", "state_set": 1, "status": "Planned"}
        self.assertTrue(milestones.needs_reason(row, "2026-02-01"))
        self.assertFalse(milestones.needs_reason({**row, "state": "Forecast"}, "2026-02-01"))
        self.assertFalse(milestones.needs_reason({**row, "state": "Achieved"}, "2026-02-01"))


class GlanceHostile(unittest.TestCase):
    def test_an_outline_that_is_not_text_keeps_the_automatic_colour(self):
        for bad in ([], {}, [1], {"a": 1}, 5, None, "<b>", "\x00", "x" * 100000):
            with self.subTest(bad=repr(bad)[:20]):
                out = glance.tiles({}, "2026-06-01", outlines={n: bad for n in ("pending", "overdue", "decisions", "milestones")})
                for t in out:
                    self.assertIn(t["colour"], set(glance.COLOUR_CLASS))


class SecretHostile(unittest.TestCase):
    hit = staticmethod(lambda t: bool(re.search(secret_screen.SHORT_SK, t)))

    def test_a_named_long_form_with_a_digit_is_caught_in_any_case(self):
        for t in ("sk-ant-abcdefg1", "Sk-ant-abcdefg1", "PK-admin-x1y2z3w4", "rk-proj-aaaaaaaa9", "SK-svcacct-ab_cd-efg1"):
            self.assertTrue(self.hit(t), t)

    def test_a_named_long_form_without_a_digit_is_a_word_not_a_key(self):
        for t in ("pk-admin-handbook", "Sk-ant-abcdefgh", "pk-proj-overview-page", "pk-admin-" + "‮" * 9):
            self.assertFalse(self.hit(t), t)

    def test_hostile_text_around_a_key_still_hits_and_never_hangs(self):
        for pad in ("\x00", "‮", "'", '"', "<b>", "\n"):
            self.assertTrue(self.hit(f"{pad}sk-ant-abcdefg1{pad}"), repr(pad))
        self.assertFalse(self.hit("pk-admin-" + "a" * 100000))     # no digit: no match, and in linear time
        self.assertFalse(self.hit("sk-ant-" * 20000))


class ReleaseTimes(unittest.TestCase):
    def test_utc_reads_only_real_times(self):
        for bad in (None, 5, [], {}, "", "x", "2026-13-45T00:00:00Z", "‮", "x" * 100000):
            self.assertIsNone(cra._utc(bad), repr(bad)[:20])
        self.assertEqual(cra._utc("2026-11-02T10:00:00Z"), cra._utc("2026-11-02T14:00:00+04:00"))
        self.assertEqual(cra._utc("2026-11-02T10:00:00z"), cra._utc("2026-11-02T10:00:00"))

    def rel(self, published, created):
        v = "0.5.0"
        return {"tag_name": "v0.5.0", "name": f"clark {v} (Beta), Mac", "prerelease": True, "draft": False,
                "body": f"# clark {v} (Beta), Mac\nclark is Beta until version 1.0.\n" + "a1" * 32, "published_at": published,
                "assets": [{"name": f"clark-{v}-mac.zip", "size": 5, "created_at": created}]}

    def late(self, published, created):
        return [p for p in cra.problems([self.rel(published, created)]) if "attached after" in p]

    def test_attached_after_publishing_fails_by_moment_not_by_text(self):
        self.assertTrue(self.late("2026-11-02T10:00:00Z", "2026-11-02T10:00:01Z"))
        # the same moments written in other zones: not late
        self.assertFalse(self.late("2026-11-02T14:00:00+04:00", "2026-11-02T10:00:00Z"))
        self.assertFalse(self.late("2026-11-02T10:00:00Z", "2026-11-02T13:59:59+04:00"))
        # text order would say late (2026-11-02T13 > 2026-11-02T10), the moments say earlier
        self.assertFalse(self.late("2026-11-02T10:00:00Z", "2026-11-02T13:00:00+04:00"))

    def test_hostile_times_never_crash_and_never_raise_the_late_line(self):
        for bad in (None, 5, [], {}, "", "junk", "2026-13-45", "‮", "x" * 10000):
            self.assertFalse(self.late(bad, "2026-11-02T10:00:00Z"), repr(bad)[:20])
            self.assertFalse(self.late("2026-11-02T10:00:00Z", bad), repr(bad)[:20])


if __name__ == "__main__":
    unittest.main()

"""#76 (non-page parts): the milestone Calendar's Week, Month and Quarter (src/clark/calendar_scales.py).

Run: python3 dev/run_tests.py test_calendar_scales
Every test fixes "today" as ON, so nothing depends on the real date. Milestones are fictional. No browser, no database.
"""
import json
import unittest
from datetime import date, timedelta

import _paths  # noqa: F401
from clark import calendar_scales as cs
from clark import milestone_rows as mr

ON = "2026-10-28"                       # a Wednesday; its week starts Monday 26-10-2026
PLANTED = "PLANTED-INTERNAL-5521 vendor wants more money"


def row(**values):
    base = {"id": "DEMO-M-001", "project": "DEMO", "name": "Pilot live", "status": "Planned", "baseline_date": None,
            "forecast_date": None, "state": None, "state_set": 0, "state_reason": None, "sort_order": 0, "archived": 0,
            "client_visible": 1, "workstream": None, "owner": None, "percent_complete": None, "actual_date": None,
            "internal_note": None, "client_message": None, "movement": None, "description": None}
    return {**base, **values}


def display(*rows):
    return mr.milestone_rows(list(rows), ON)


class Scale(unittest.TestCase):
    def test_month_is_the_default(self):
        self.assertEqual(cs.DEFAULT_SCALE, "month")
        self.assertEqual(cs.SCALES, ("week", "month", "quarter"))
        self.assertEqual(cs.pick_scale(None), "month")

    def test_unknown_stored_values_give_month(self):
        for v in ("", "year", "Week", None, 3, "quarterly", ["week"]):
            with self.subTest(v=v):
                self.assertEqual(cs.normalise_scale(v), "month")
                self.assertEqual(cs.pick_scale(v), "month")

    def test_known_values_are_kept(self):
        for v in cs.SCALES:
            self.assertEqual(cs.pick_scale(v), v)

    def test_each_place_remembers_its_own_scale(self):
        self.assertEqual(cs.remember_key("page"), "msv.calv.page")
        self.assertNotEqual(cs.remember_key("page"), cs.remember_key("pub"))
        with self.assertRaises(ValueError):
            cs.remember_key("")

    def test_an_unknown_scale_is_refused_in_plain_words(self):
        with self.assertRaises(ValueError) as e:
            cs.step("year", "2026-10", 1)
        self.assertIn("week, month or quarter", str(e.exception))


class TodayAndTitles(unittest.TestCase):
    def test_today_per_scale(self):
        self.assertEqual([cs.today_key(s, ON) for s in cs.SCALES], ["2026-10-26", "2026-10", "2026-Q4"])

    def test_today_on_a_sunday_and_a_monday(self):
        self.assertEqual(cs.today_key("week", "2026-11-01"), "2026-10-26")
        self.assertEqual(cs.today_key("week", "2026-11-02"), "2026-11-02")

    def test_titles(self):
        self.assertEqual(cs.title("week", "2026-10-05"), "Week of 05-10-2026")
        self.assertEqual(cs.title("month", "2026-10"), "October 2026")
        self.assertEqual(cs.title("quarter", "2026-Q4"), "Q4 2026")

    def test_titles_match_the_buckets_labels(self):
        for scale, key, day in (("week", "2026-10-26", "2026-10-28"), ("month", "2027-02", "2027-02-10"),
                                ("quarter", "2027-Q1", "2027-02-10")):
            label = mr.buckets(scale, day, day)[0]
            self.assertEqual((label["key"], label["label"]), (key, cs.title(scale, key)))

    def test_bad_keys_say_so_in_plain_words(self):
        bad = (("week", "2026-10-06"), ("week", "2026-10"), ("week", "nonsense"), ("month", "2026-13"), ("month", "2026-1"),
               ("month", "2026-10-01"), ("quarter", "2026-Q5"), ("quarter", "2026-Q0"), ("quarter", "2026-10"),
               ("month", None), ("week", ""), ("quarter", "26-Q1"))
        for scale, key in bad:
            for fn in (lambda: cs.title(scale, key), lambda: cs.step(scale, key, 1)):
                with self.subTest(scale=scale, key=key):
                    with self.assertRaises(ValueError) as e:
                        fn()
                    self.assertIn("calendar knows", str(e.exception))

    def test_a_bad_today_is_refused(self):
        with self.assertRaises(ValueError):
            cs.today_key("month", "28-10-2026")

    def test_step_direction_must_be_one_either_way(self):
        with self.assertRaises(ValueError):
            cs.step("month", "2026-10", 2)
        with self.assertRaises(ValueError):
            cs.step("month", "2026-10", 0)


class Stepping(unittest.TestCase):
    def test_week_steps_by_seven_days_across_new_year(self):
        self.assertEqual(cs.step("week", "2026-10-26", 1), "2026-11-02")
        self.assertEqual(cs.step("week", "2026-12-28", 1), "2027-01-04")
        self.assertEqual(cs.step("week", "2027-01-04", -1), "2026-12-28")
        self.assertEqual(cs.step("week", "2026-12-28", -1), "2026-12-21")

    def test_month_steps_across_year_ends_and_short_months(self):
        self.assertEqual(cs.step("month", "2026-12", 1), "2027-01")
        self.assertEqual(cs.step("month", "2027-01", -1), "2026-12")
        self.assertEqual(cs.step("month", "2026-01", 1), "2026-02")
        self.assertEqual(cs.step("month", "2026-02", 1), "2026-03")
        self.assertEqual(cs.step("month", "2028-02", 1), "2028-03")
        self.assertEqual(cs.step("month", "2026-03", -1), "2026-02")

    def test_quarter_steps_across_year_ends(self):
        self.assertEqual(cs.step("quarter", "2026-Q4", 1), "2027-Q1")
        self.assertEqual(cs.step("quarter", "2027-Q1", -1), "2026-Q4")
        self.assertEqual(cs.step("quarter", "2026-Q1", 1), "2026-Q2")
        self.assertEqual(cs.step("quarter", "2026-Q3", 1), "2026-Q4")

    def test_keys_far_outside_any_span_still_step(self):
        self.assertEqual(cs.step("month", "2126-12", 1), "2127-01")
        self.assertEqual(cs.step("month", "1926-01", -1), "1925-12")
        self.assertEqual(cs.step("quarter", "2300-Q4", 1), "2301-Q1")
        self.assertEqual(cs.step("week", "1900-01-01", -1), "1899-12-25")

    def test_stepping_off_the_end_of_time_is_a_plain_error(self):
        for scale, key, d in (("month", "9999-12", 1), ("quarter", "9999-Q4", 1), ("week", "9999-12-27", 1),
                              ("month", "0001-01", -1), ("quarter", "0001-Q1", -1), ("week", "0001-01-01", -1)):
            with self.subTest(scale=scale):
                with self.assertRaises(ValueError) as e:
                    cs.step(scale, key, d)
                self.assertIn("can't go that far", str(e.exception))

    def test_forward_then_back_is_the_same_pane_for_thousands_of_days(self):
        d = date(2024, 1, 1)
        for _ in range(3000):
            iso = d.isoformat()
            for scale in cs.SCALES:
                k = cs.today_key(scale, iso)
                self.assertEqual(cs.step(scale, cs.step(scale, k, 1), -1), k, (scale, iso))
                self.assertEqual(cs.step(scale, cs.step(scale, k, -1), 1), k, (scale, iso))
                self.assertNotEqual(cs.step(scale, k, 1), k)
            d += timedelta(days=1)

    def test_each_step_lands_on_the_next_pane_that_buckets_gives(self):
        for scale in cs.SCALES:
            keys = [b["key"] for b in mr.buckets(scale, "2026-11-20", "2028-03-10")]
            self.assertEqual([cs.step(scale, k, 1) for k in keys[:-1]], keys[1:])

    def test_today_per_scale_returns_after_going_away(self):
        for scale in cs.SCALES:
            k = cs.today_key(scale, ON)
            for _ in range(5):
                k = cs.step(scale, k, 1)
            self.assertNotEqual(k, cs.today_key(scale, ON))
            self.assertEqual(cs.today_key(scale, ON), cs.today_key(scale, ON))


class Weeks(unittest.TestCase):
    def test_seven_days_monday_to_sunday(self):
        days = cs.week_days("2026-10-26", ON)
        self.assertEqual([d["date"] for d in days], ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30",
                                                     "2026-10-31", "2026-11-01"])
        self.assertEqual([d["weekday"] for d in days], list(cs.WEEKDAYS))
        self.assertEqual([d["weekend"] for d in days], [False] * 5 + [True] * 2)
        self.assertEqual([d["today"] for d in days], [False, False, True, False, False, False, False])
        self.assertFalse(any(d["outside"] for d in days))
        self.assertEqual([d["day"] for d in days], [26, 27, 28, 29, 30, 31, 1])

    def test_a_week_across_new_year(self):
        days = cs.week_days("2026-12-28")
        self.assertEqual((days[0]["date"], days[3]["date"], days[4]["date"], days[6]["date"]),
                         ("2026-12-28", "2026-12-31", "2027-01-01", "2027-01-03"))
        self.assertFalse(any(d["today"] for d in days))

    def test_a_week_with_a_leap_day(self):
        self.assertIn("2028-02-29", [d["date"] for d in cs.week_days("2028-02-28")])

    def test_no_today_flag_in_another_week(self):
        self.assertFalse(any(d["today"] for d in cs.week_days("2026-11-02", ON)))


class Months(unittest.TestCase):
    def check(self, key, today=None):
        weeks = cs.month_grid(key, today)
        flat = [d for w in weeks for d in w]
        self.assertTrue(all(len(w) == 7 for w in weeks))
        self.assertEqual(date.fromisoformat(flat[0]["date"]).weekday(), 0, "Monday first")
        self.assertEqual(date.fromisoformat(flat[-1]["date"]).weekday(), 6)
        dates = [date.fromisoformat(d["date"]) for d in flat]
        self.assertEqual([b - a for a, b in zip(dates, dates[1:])], [timedelta(days=1)] * (len(dates) - 1))
        inside = [d for d in flat if not d["outside"]]
        y, m = int(key[:4]), int(key[5:])
        self.assertTrue(all(date.fromisoformat(d["date"]).month == m for d in inside))
        self.assertEqual(inside[0]["date"], "%s-01" % key)
        self.assertTrue(all(date.fromisoformat(d["date"]).month != m for d in flat if d["outside"]))
        return weeks, inside

    def test_every_weekday_can_start_a_month(self):
        starts = {}
        for month in range(1, 13):
            key = "2026-%02d" % month
            weeks, inside = self.check(key)
            starts[date(2026, month, 1).weekday()] = key
            self.assertEqual(sum(1 for d in weeks[0] if d["outside"]), date(2026, month, 1).weekday())
        for y in (2027, 2028, 2029):
            for month in range(1, 13):
                starts[date(y, month, 1).weekday()] = "%d-%02d" % (y, month)
                self.check("%d-%02d" % (y, month))
        self.assertEqual(sorted(starts), list(range(7)))

    def test_february_in_leap_and_ordinary_years(self):
        self.assertEqual(len(self.check("2028-02")[1]), 29)
        self.assertEqual(len(self.check("2027-02")[1]), 28)
        self.assertEqual(len(self.check("2100-02")[1]), 28)       # a century year that is not a leap year
        self.assertEqual(len(self.check("2000-02")[1]), 29)
        # 01-02-2027 is a Monday and the month has 28 days: exactly four whole weeks, with no outside days
        grid = cs.month_grid("2027-02")
        self.assertEqual((len(grid), any(d["outside"] for w in grid for d in w)), (4, False))
        self.assertEqual(len(cs.month_grid("2026-02")), 5)         # a Sunday start: one day in the first row

    def test_five_and_six_week_months(self):
        self.assertEqual(len(cs.month_grid("2026-03")), 6)         # a Sunday start and 31 days
        self.assertEqual(len(cs.month_grid("2026-11")), 6)
        self.assertEqual(len(cs.month_grid("2026-10")), 5)

    def test_weekends_are_flagged(self):
        flat = [d for w in cs.month_grid("2026-10") for d in w]
        for d in flat:
            self.assertEqual(d["weekend"], date.fromisoformat(d["date"]).weekday() >= 5)
        self.assertEqual(sum(d["weekend"] for d in flat), 2 * len(cs.month_grid("2026-10")))

    def test_today_is_flagged_once_and_only_in_its_month(self):
        flat = [d for w in cs.month_grid("2026-10", ON) for d in w]
        self.assertEqual([d["date"] for d in flat if d["today"]], [ON])
        self.assertFalse(any(d["today"] for w in cs.month_grid("2026-12", ON) for d in w))
        # today in a neighbouring month's outside days is still flagged where it appears
        nov = [d for w in cs.month_grid("2026-11", ON) for d in w]
        self.assertEqual([(d["date"], d["outside"]) for d in nov if d["today"]], [("2026-10-28", True)])   # a leading day
        sep = [d for w in cs.month_grid("2026-09", "2026-10-01") for d in w]
        self.assertEqual([(d["date"], d["outside"]) for d in sep if d["today"]], [("2026-10-01", True)])

    def test_year_end_months(self):
        dec = [d for w in cs.month_grid("2026-12") for d in w]
        self.assertEqual(dec[-1]["date"], "2027-01-03")
        jan = cs.month_grid("2027-01")
        self.assertEqual(jan[0][0]["date"], "2026-12-28")
        self.assertTrue(jan[0][0]["outside"])


class Quarters(unittest.TestCase):
    def test_three_months_of_each_quarter(self):
        self.assertEqual(cs.quarter_months("2026-Q1"), ["2026-01", "2026-02", "2026-03"])
        self.assertEqual(cs.quarter_months("2026-Q2"), ["2026-04", "2026-05", "2026-06"])
        self.assertEqual(cs.quarter_months("2026-Q3"), ["2026-07", "2026-08", "2026-09"])
        self.assertEqual(cs.quarter_months("2026-Q4"), ["2026-10", "2026-11", "2026-12"])

    def test_quarter_months_agree_with_buckets(self):
        for b in mr.buckets("quarter", "2026-01-01", "2028-12-31"):
            self.assertEqual(cs.quarter_months(b["key"]), b["months"])

    def test_every_day_belongs_to_the_quarter_whose_months_hold_it(self):
        d = date(2027, 12, 20)
        for _ in range(30):
            iso = d.isoformat()
            self.assertIn(iso[:7], cs.quarter_months(cs.today_key("quarter", iso)))
            d += timedelta(days=1)

    def test_a_months_name_opens_that_month_and_round_trips(self):
        for q in ("2026-Q4", "2027-Q1"):
            for mo in cs.quarter_months(q):
                state = cs.open_month_from_quarter(mo)
                self.assertEqual(state, {"scale": "month", "key": mo})
                self.assertEqual(cs.title(state["scale"], state["key"]), cs.title("month", mo))
                self.assertEqual(cs.today_key("quarter", mo + "-15"), q)      # back to the quarter that holds it

    def test_opening_something_that_is_not_a_month_is_refused(self):
        for bad in ("2026-Q4", "2026-13", "", None):
            with self.assertRaises(ValueError):
                cs.open_month_from_quarter(bad)


class Panes(unittest.TestCase):
    def test_a_calendar_with_no_milestones_still_has_todays_pane(self):
        for scale, key in (("week", "2026-10-26"), ("month", "2026-10"), ("quarter", "2026-Q4")):
            self.assertEqual(cs.panes([], ON, scale), [key])
            self.assertEqual(cs.panes(None, ON, scale), [key])

    def test_panes_cover_every_mark_and_today_in_order(self):
        rows = display(row(id="DEMO-M-001", baseline_date="2026-08-14", status="Done", actual_date="2026-08-20"),
                       row(id="DEMO-M-002", baseline_date="2027-02-01"))
        self.assertEqual(cs.panes(rows, ON, "month"),
                         ["2026-08", "2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02"])
        self.assertEqual(cs.panes(rows, ON, "quarter"), ["2026-Q3", "2026-Q4", "2027-Q1"])
        w = cs.panes(rows, ON, "week")
        self.assertEqual((w[0], w[-1]), ("2026-08-17", "2027-02-01"))      # the achieved mark is 20-08, in the week of 17-08
        self.assertIn("2026-10-26", w)
        self.assertEqual(w, sorted(w))

    def test_every_scale_contains_the_pane_for_today_whatever_the_marks(self):
        for dates in ([], ["2020-01-01"], ["2035-06-01"], ["2026-10-28"], ["2026-01-01", "2030-01-01"]):
            rows = display(*[row(id="DEMO-M-%03d" % i, baseline_date=x) for i, x in enumerate(dates, 1)])
            for scale in cs.SCALES:
                self.assertIn(cs.today_key(scale, ON), cs.panes(rows, ON, scale), (dates, scale))

    def test_a_ghost_far_from_the_solid_mark_extends_the_panes(self):
        rows = display(row(baseline_date="2026-09-01", forecast_date="2027-04-15"))
        self.assertEqual(rows[0]["marks"]["ghost"]["date"], "2027-04-15")
        self.assertEqual(cs.panes(rows, ON, "month")[-1], "2027-04")
        self.assertEqual(cs.panes(rows, ON, "quarter")[-1], "2027-Q2")

    def test_panes_are_consecutive_steps(self):
        rows = display(row(baseline_date="2025-12-30"), row(id="DEMO-M-002", baseline_date="2027-01-05"))
        for scale in cs.SCALES:
            keys = cs.panes(rows, ON, scale)
            self.assertEqual([cs.step(scale, k, 1) for k in keys[:-1]], keys[1:])

    def test_an_unknown_scale_is_refused(self):
        with self.assertRaises(ValueError):
            cs.panes([], ON, "decade")


class Chips(unittest.TestCase):
    def test_chips_appear_on_the_right_day_in_every_scale(self):
        rows = display(row(id="DEMO-M-001", name="Pilot live", baseline_date="2026-10-28"))
        chips = mr.calendar_chips(rows)
        for key in (cs.today_key("week", ON),):
            self.assertIn(ON, [d["date"] for d in cs.week_days(key)])
        month_days = {d["date"] for w in cs.month_grid("2026-10") for d in w}
        quarter_days = {d["date"] for mo in cs.quarter_months("2026-Q4") for w in cs.month_grid(mo) for d in w}
        self.assertIn(ON, month_days)
        self.assertIn(ON, quarter_days)
        self.assertEqual([c["name"] for c in chips[ON]], ["Pilot live"])

    def test_a_ghost_sits_on_the_expected_day_not_the_agreed_day(self):
        rows = display(row(baseline_date="2026-11-05", forecast_date="2026-12-09"))
        chips = mr.calendar_chips(rows)
        self.assertEqual([(c["ghost"], c["state"]) for c in chips["2026-11-05"]], [(False, "Slipped")])
        self.assertEqual([c["ghost"] for c in chips["2026-12-09"]], [True])
        in_week = lambda k: {d["date"] for d in cs.week_days(k)}
        self.assertIn("2026-11-05", in_week("2026-11-02"))
        self.assertIn("2026-12-09", in_week("2026-12-07"))
        self.assertNotIn("2026-12-09", in_week("2026-11-02"))
        # the two marks fall in different months and so in different month panes, the same quarter
        self.assertEqual([cs.today_key("month", d) for d in chips], ["2026-11", "2026-12"])
        self.assertEqual({cs.today_key("quarter", d) for d in chips}, {"2026-Q4"})

    def test_a_milestone_on_a_quarters_first_and_last_day(self):
        rows = display(row(id="DEMO-M-001", baseline_date="2027-01-01"), row(id="DEMO-M-002", baseline_date="2027-03-31"),
                       row(id="DEMO-M-003", baseline_date="2027-04-01"), row(id="DEMO-M-004", baseline_date="2026-12-31"))
        by_q = {}
        for d, cl in mr.calendar_chips(rows).items():
            by_q.setdefault(cs.today_key("quarter", d), []).extend(c["id"] for c in cl)
        self.assertEqual({k: sorted(v) for k, v in by_q.items()},
                         {"2026-Q4": ["DEMO-M-004"], "2027-Q1": ["DEMO-M-001", "DEMO-M-002"], "2027-Q2": ["DEMO-M-003"]})
        days = {d["date"] for mo in cs.quarter_months("2027-Q1") for w in cs.month_grid(mo) for d in w if not d["outside"]}
        self.assertTrue({"2027-01-01", "2027-03-31"} <= days)
        self.assertFalse({"2026-12-31", "2027-04-01"} & days)
        self.assertEqual(cs.panes(rows, ON, "quarter"), ["2026-Q4", "2027-Q1", "2027-Q2"])


class Published(unittest.TestCase):
    def rows(self):
        return display(
            row(id="DEMO-M-001", name="Pilot live", baseline_date="2026-11-30", forecast_date="2027-01-12",
                internal_note=PLANTED, client_message="Pilot goes live in the new year"),
            row(id="DEMO-M-002", name="Contract review", baseline_date="2027-03-15", client_visible=0, internal_note=PLANTED),
            row(id="DEMO-M-003", name="Supplier call-off", baseline_date="2028-06-01", client_visible=0),
            row(id="DEMO-M-004", name="Old idea", baseline_date="2026-12-01", status="Cancelled"))

    def test_published_rows_never_carry_internal_milestones_or_notes_into_any_pane_or_chip(self):
        client = mr.for_client(self.rows())
        self.assertEqual([r["id"] for r in client], ["DEMO-M-001"])
        everything = {}
        for scale in cs.SCALES:
            keys = cs.panes(client, ON, scale)
            everything[scale] = keys
            self.assertTrue(all(isinstance(k, str) for k in keys))
        # the internal milestones' dates (03-2027, 06-2028) must not widen any pane list
        self.assertEqual(everything["month"][-1], "2027-01")
        self.assertEqual(everything["quarter"][-1], "2027-Q1")
        self.assertEqual(everything["week"][-1], "2027-01-11")
        self.assertNotIn("2027-03", everything["month"])
        self.assertNotIn("2028-Q2", everything["quarter"])
        text = json.dumps([everything, mr.calendar_chips(client)])
        for secret in (PLANTED, "PLANTED", "Contract review", "Supplier call-off", "Old idea", "DEMO-M-002", "DEMO-M-003",
                       "DEMO-M-004", "internal_note"):
            self.assertNotIn(secret, text)
        chips = [c for cl in mr.calendar_chips(client).values() for c in cl]
        self.assertEqual({c["id"] for c in chips}, {"DEMO-M-001"})
        self.assertEqual(set(chips[0]), {"id", "name", "state", "colour", "mark", "ghost"})
        self.assertEqual(chips[0]["state"], "Expected later", "the client's word, not the internal state")

    def test_the_internal_rows_do_widen_the_internal_panes(self):
        self.assertEqual(cs.panes(self.rows(), ON, "quarter")[-1], "2028-Q2", "so the test above can fail")

    def test_the_eye_hides_a_milestone_from_every_pane(self):
        client = mr.for_client(self.rows(), hidden_ids={"DEMO-M-001"})
        self.assertEqual(client, [])
        self.assertEqual(cs.panes(client, ON, "month"), ["2026-10"])
        self.assertEqual(mr.calendar_chips(client), {})


if __name__ == "__main__":
    unittest.main()

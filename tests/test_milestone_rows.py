"""#44 (non-page parts): the Milestones view's data (src/clark/milestone_rows.py), by FR-50 to FR-54 and the readiness draft.

Run: python3 dev/run_tests.py test_milestone_rows
Every test fixes "today" as ON, so nothing depends on the real date. Milestones are fictional. Movement is read from a real
store's history (tests/_demo.py), so undo steps come exactly as history() reports them.
"""
import json
import os
import time
import unittest

import _paths  # noqa: F401
from _demo import DemoStore
from clark import milestone_rows as mr
from clark import milestones as ms

ON = "2026-10-28"
PLANTED = "PLANTED-INTERNAL-7731 vendor is asking for more money"
PLANTED_REASON = "PLANTED-REASON-4410 not for clients"


def row(**values):
    base = {"id": "DEMO-M-001", "project": "DEMO", "name": "Pilot live", "status": "Planned", "baseline_date": None,
            "forecast_date": None, "state": None, "state_set": 0, "state_reason": None, "sort_order": 0, "archived": 0,
            "client_visible": 1, "workstream": None, "owner": None, "percent_complete": None, "actual_date": None,
            "internal_note": None, "client_message": None, "movement": None, "description": None}
    return {**base, **values}


def one(**values):
    return mr.milestone_rows([row(**values)], ON)[0]


class States(unittest.TestCase):
    def test_every_state_with_its_words_and_colour(self):
        cases = [
            ("Achieved", row(status="Done", baseline_date="2026-10-01", actual_date="2026-10-02"), "Achieved", "green"),
            ("On track", row(baseline_date="2026-11-30"), "On track", "green"),
            ("At risk", row(baseline_date="2026-12-01", state="At risk", state_set=1, state_reason="vendor"), "At risk", "amber"),
            ("Slipped", row(baseline_date="2026-11-30", forecast_date="2026-12-14"), "Expected later", "red"),
            ("Overdue", row(baseline_date="2026-10-01"), "Late", "red"),
            ("Forecast", row(forecast_date="2027-02-01", state="Forecast", state_set=1), "Forecast", "blue"),
            ("Cancelled", row(status="Cancelled", baseline_date="2026-11-30"), "Cancelled", "grey"),
        ]
        for state, r, word, colour in cases:
            with self.subTest(state):
                d = mr.milestone_rows([r], ON)[0]
                self.assertEqual((d["state"], d["client_word"], d["colour"]), (state, word, colour))

    def test_forecast_has_no_slip_though_slip_days_would_count_one(self):
        r = row(baseline_date="2026-10-01", forecast_date="2027-02-01", state="Forecast", state_set=1)
        self.assertGreater(ms.slip_days(r, ON), 0, "milestones.slip_days doesn't look at the state; the rows do")
        d = mr.milestone_rows([r], ON)[0]
        self.assertEqual((d["state"], d["slip"], d["slip_text"], d["expected"]), ("Forecast", None, None, None))
        self.assertEqual((d["marks"]["ghost"], d["marks"]["line"]), (None, None))

    def test_achieved_and_cancelled_have_no_slip(self):
        done = one(status="Done", baseline_date="2026-09-01", forecast_date="2026-09-20", actual_date="2026-09-25")
        gone = one(status="Cancelled", baseline_date="2026-09-01")
        self.assertEqual((done["slip"], gone["slip"]), (None, None))
        self.assertEqual(done["achieved"], "2026-09-25")
        self.assertIsNone(gone["achieved"])

    def test_slip_numbers_equal_slip_days(self):
        cases = [row(baseline_date="2026-11-30", forecast_date="2026-12-14"),              # forecast later: 14
                 row(baseline_date="2026-10-18"),                                          # overdue, no forecast: 10 to today
                 row(baseline_date="2026-10-18", forecast_date="2026-11-30"),              # overdue and a later forecast: 43
                 row(baseline_date="2026-10-18", forecast_date="2026-10-20"),              # overdue, forecast passed: to today
                 row(baseline_date="2026-11-30"), row(baseline_date="2026-11-30", forecast_date="2026-11-20")]
        for r in cases:
            with self.subTest(dates=(r["baseline_date"], r["forecast_date"])):
                self.assertEqual(mr.milestone_rows([r], ON)[0]["slip"], ms.slip_days(r, ON))
        self.assertEqual([mr.milestone_rows([r], ON)[0]["slip"] for r in cases], [14, 10, 43, 10, 0, 0])

    def test_slip_text_says_days_later(self):
        self.assertEqual(one(baseline_date="2026-11-30", forecast_date="2026-12-01")["slip_text"], "1 day later")
        self.assertEqual(one(baseline_date="2026-11-30", forecast_date="2026-12-14")["slip_text"], "14 days later")
        self.assertIsNone(one(baseline_date="2026-11-30")["slip_text"])

    def test_archived_rows_are_left_out_and_fields_are_carried(self):
        out = mr.milestone_rows([row(id="DEMO-M-001", archived=1, baseline_date="2026-11-01"),
                                 row(id="DEMO-M-002", baseline_date="2026-11-02", percent_complete=40, owner="Sam Example",
                                     workstream="build", description="Scope")],
                                ON, workstreams=[{"name": "Build"}])
        self.assertEqual([r["id"] for r in out], ["DEMO-M-002"])
        r = out[0]
        self.assertEqual((r["percent"], r["owner"], r["workstream"], r["description"]), (40, "Sam Example", "Build", "Scope"))


class AchievedNote(unittest.TestCase):
    def test_how_an_achieved_milestone_compares_with_its_agreed_date(self):
        done = dict(status="Done", baseline_date="2026-09-10")
        self.assertEqual(one(actual_date="2026-09-13", **done)["achieved_note"], "Achieved 3 days after the agreed date")
        self.assertEqual(one(actual_date="2026-09-11", **done)["achieved_note"], "Achieved 1 day after the agreed date")
        self.assertEqual(one(actual_date="2026-09-10", **done)["achieved_note"], "Achieved on the agreed date")
        self.assertEqual(one(actual_date="2026-09-08", **done)["achieved_note"], "Achieved 2 days early")
        self.assertEqual(one(actual_date="2026-09-09", **done)["achieved_note"], "Achieved 1 day early")
        self.assertEqual(one(status="Done", actual_date="2026-09-09")["achieved_note"], "Achieved on 09-09-2026")

    def test_nothing_to_say_when_not_achieved(self):
        for r in (row(baseline_date="2026-09-10"), row(status="Done", baseline_date="2026-09-10"),
                  row(status="Cancelled", baseline_date="2026-09-10", actual_date="2026-09-11")):
            self.assertEqual(mr.milestone_rows([r], ON)[0]["achieved_note"], "")


class Marks(unittest.TestCase):
    def test_solid_on_the_agreed_date_and_ghost_on_the_expected_one(self):
        m = one(baseline_date="2026-11-30", forecast_date="2026-12-14")["marks"]
        self.assertEqual(m["solid"], {"date": "2026-11-30", "kind": "agreed"})
        self.assertEqual(m["ghost"], {"date": "2026-12-14", "label": "Expected 14-12-2026"})
        self.assertEqual(m["line"], {"from": "2026-11-30", "to": "2026-12-14", "days": 14})

    def test_overdue_with_no_forecast_is_expected_today(self):
        d = one(baseline_date="2026-10-18")
        self.assertEqual(d["marks"]["ghost"]["date"], ON)
        self.assertEqual((d["slip"], d["expected"]), (10, ON))

    def test_on_time_has_no_ghost(self):
        m = one(baseline_date="2026-11-30", forecast_date="2026-11-30")["marks"]
        self.assertEqual((m["ghost"], m["line"]), (None, None))
        self.assertEqual(one(baseline_date="2026-11-30", forecast_date="2026-11-10")["marks"]["ghost"], None)

    def test_achieved_sits_on_the_achieved_date_with_no_ghost(self):
        m = one(status="Done", baseline_date="2026-09-01", forecast_date="2026-09-20", actual_date="2026-09-25")["marks"]
        self.assertEqual(m["solid"], {"date": "2026-09-25", "kind": "achieved"})
        self.assertIsNone(m["ghost"])

    def test_no_agreed_date_sits_on_the_forecast_and_neither_means_no_mark(self):
        self.assertEqual(one(forecast_date="2027-02-01")["marks"]["solid"], {"date": "2027-02-01", "kind": "forecast"})
        d = one()
        self.assertEqual((d["marks"]["solid"], d["slip"]), (None, None))

    def test_at_risk_milestone_that_has_slipped_shows_its_ghost(self):
        d = one(baseline_date="2026-11-30", forecast_date="2026-12-10", state="At risk", state_set=1, state_reason="vendor")
        self.assertEqual((d["state"], d["slip"], d["marks"]["ghost"]["date"]), ("At risk", 10, "2026-12-10"))


class Sorting(unittest.TestCase):
    def test_by_agreed_date_then_sort_order_then_id(self):
        rows = [row(id="DEMO-M-004", baseline_date="2026-12-01", sort_order=0),
                row(id="DEMO-M-003", baseline_date="2026-11-01", sort_order=2),
                row(id="DEMO-M-002", baseline_date="2026-11-01", sort_order=1),
                row(id="DEMO-M-001", baseline_date="2026-11-01", sort_order=1),
                row(id="DEMO-M-006"),                                                      # no dates: last
                row(id="DEMO-M-005", forecast_date="2026-11-15")]                          # no agreed date: by its forecast
        self.assertEqual([r["id"] for r in mr.milestone_rows(rows, ON)],
                         ["DEMO-M-001", "DEMO-M-002", "DEMO-M-003", "DEMO-M-005", "DEMO-M-004", "DEMO-M-006"])


class ForClient(unittest.TestCase):
    def rows(self):
        return mr.milestone_rows([
            row(id="DEMO-M-001", baseline_date="2026-11-30", forecast_date="2026-12-14", internal_note=PLANTED,
                state_reason=PLANTED_REASON, movement="escalate", client_message="Expected in mid December"),
            row(id="DEMO-M-002", baseline_date="2026-10-01", internal_note=PLANTED),
            row(id="DEMO-M-003", name="Hidden one", baseline_date="2026-11-01", client_visible=0, internal_note=PLANTED),
            row(id="DEMO-M-004", name="Dropped one", status="Cancelled", baseline_date="2026-11-02"),
            row(id="DEMO-M-005", baseline_date="2026-09-01", status="Done", actual_date="2026-09-02", state_reason=PLANTED_REASON,
                internal_note=PLANTED)], ON)

    def test_internal_note_and_reason_are_nowhere_in_the_output(self):
        out = mr.for_client(self.rows())
        text = json.dumps(out)
        self.assertIn(PLANTED, json.dumps(self.rows()), "the planted note is in the editor rows, so the test can fail")
        for planted in (PLANTED, "PLANTED-", PLANTED_REASON, "escalate", "internal_note", "state_reason", "movement"):
            self.assertNotIn(planted, text)

    def test_hidden_and_cancelled_are_left_out(self):
        self.assertEqual([r["id"] for r in mr.for_client(self.rows())], ["DEMO-M-005", "DEMO-M-002", "DEMO-M-001"])
        text = json.dumps(mr.for_client(self.rows()))
        self.assertNotIn("Hidden one", text)
        self.assertNotIn("Dropped one", text)

    def test_client_words_replace_the_state_names(self):
        out = {r["id"]: r for r in mr.for_client(self.rows())}
        self.assertEqual((out["DEMO-M-001"]["state"], out["DEMO-M-002"]["state"], out["DEMO-M-005"]["state"]),
                         ("Expected later", "Late", "Achieved"))
        text = json.dumps(out)
        self.assertNotIn("Slipped", text)
        self.assertNotIn("Overdue", text)

    def test_the_slip_and_marks_stay(self):
        r = {x["id"]: x for x in mr.for_client(self.rows())}["DEMO-M-001"]
        self.assertEqual((r["slip"], r["slip_text"], r["marks"]["ghost"]["date"], r["client_message"]),
                         (14, "14 days later", "2026-12-14", "Expected in mid December"))

    def test_a_row_that_does_not_say_it_is_client_visible_is_left_out(self):
        self.assertEqual(mr.for_client([{"id": "X", "name": "x", "status": "Planned", "state": "On track"}]), [])

    def test_an_eye_hidden_milestone_is_left_out_even_when_client_visible(self):
        rows = self.rows()
        self.assertIn("DEMO-M-001", [r["id"] for r in mr.for_client(rows)], "visible without the eye, so the test can fail")
        out = mr.for_client(rows, hidden_ids={"DEMO-M-001"})
        self.assertEqual([r["id"] for r in out], ["DEMO-M-005", "DEMO-M-002"])
        self.assertNotIn("DEMO-M-001", json.dumps(out))
        self.assertEqual([r["id"] for r in mr.for_client(rows, hidden_ids=["DEMO-M-001", "DEMO-M-002"])], ["DEMO-M-005"])
        self.assertEqual(len(mr.for_client(rows, hidden_ids=())), 3)
        legend_rows = mr.for_client(rows, hidden_ids={"DEMO-M-001"})
        self.assertNotIn("DEMO-M-001", [c["id"] for chips in mr.calendar_chips(legend_rows).values() for c in chips])

    def test_no_original_date_or_rebaseline_reaches_a_client(self):
        r = mr.milestone_rows([row(baseline_date="2026-12-01")], ON, events={"DEMO-M-001": [
            {"event_id": 1, "table": "milestones", "field": "baseline_date", "after": "2026-11-01", "is_undo": False,
             "in_force": True}]})[0]
        self.assertEqual((r["original"], r["rebaselined"]), ("2026-11-01", True))
        out = mr.for_client([r])[0]
        self.assertNotIn("original", out)
        self.assertNotIn("rebaselined", out)


class Real(unittest.TestCase):
    """Rows and events from a real store, so the shapes are the ones the page will get."""

    def setUp(self):
        self.demo = DemoStore()
        self.s, self.mid = self.demo.store, self.demo.milestone       # Pilot live, agreed 2030-03-01

    def tearDown(self):
        self.demo.close()

    def step(self, changes, **kw):
        with self.s.step("dashboard", "Demo User") as st:
            st.update("milestones", self.mid, changes, **kw)
        return self.demo.last_step()

    def rebaseline(self, to="2030-04-01", **kw):
        return self.step({"baseline_date": to}, rebaseline={"agreed_with": "Sam Example", "reason": "Vendor delay",
                                                            "source": "Steering call"}, **kw)

    def test_original_date_and_rebaselined_from_events(self):
        events = {self.mid: self.s.history(self.mid)}
        d = mr.milestone_rows(self.s.read("milestones", "ABC"), "2030-01-01", events=events)[0]
        self.assertEqual((d["original"], d["rebaselined"]), ("2030-03-01", False))
        self.rebaseline()
        events = {self.mid: self.s.history(self.mid)}
        d = mr.milestone_rows(self.s.read("milestones", "ABC"), "2030-01-01", events=events)[0]
        self.assertEqual((d["original"], d["baseline"], d["rebaselined"]), ("2030-03-01", "2030-04-01", True))
        d = mr.milestone_rows(self.s.read("milestones", "ABC"), "2030-01-01")[0]
        self.assertIsNone(d["original"], "without events the original date isn't known")

    def test_events_passed_but_none_for_the_milestone_fall_back_to_the_agreed_date(self):
        d = mr.milestone_rows([row(baseline_date="2026-12-01")], ON, events={})[0]
        self.assertEqual((d["original"], d["rebaselined"]), ("2026-12-01", False))
        d = mr.milestone_rows([row(baseline_date="2026-12-01")], ON, events={"DEMO-M-001": []})[0]
        self.assertEqual((d["original"], d["rebaselined"]), ("2026-12-01", False))
        d = mr.milestone_rows([row(baseline_date="2026-12-01")], ON)[0]
        self.assertEqual((d["original"], d["rebaselined"]), (None, False))
        d = mr.milestone_rows([row()], ON, events={})[0]
        self.assertIsNone(d["original"])

    def test_original_date_agrees_with_the_store(self):
        from clark import history
        self.rebaseline()
        self.rebaseline("2030-05-01")
        self.assertEqual(mr.original_from_events(self.s.history(self.mid)), history.original_date(self.s.con, self.mid))

    def test_original_skips_an_undone_first_date(self):
        self.assertEqual(mr.original_from_events(self.s.history(self.mid), "x"), "2030-03-01")
        with self.s.step("dashboard", "Demo User") as st:      # the first agreed date went in by a step that is then undone
            st.create("milestones", {"project": "ABC", "name": "Later", "baseline_date": "2030-09-01", "source": "demo"})
        made = self.demo.last_step()
        self.s.undo(made, "Demo User")
        later = "ABC-M-002"
        self.assertIsNone(mr.original_from_events(self.s.history(later)))
        self.assertEqual(mr.original_from_events(self.s.history(later), "2030-09-01"), "2030-09-01")

    def test_movement_newest_first_with_who_and_when(self):
        self.step({"forecast_date": "2030-03-15"})
        self.rebaseline()
        self.step({"forecast_date": "2030-05-01"})
        out = mr.movement(self.s.history(self.mid), self.mid)
        self.assertEqual([e["kind"] for e in out], ["forecast", "rebaseline", "forecast"])
        self.assertEqual([e["event_id"] for e in out], sorted((e["event_id"] for e in out), reverse=True))
        self.assertEqual(out[0]["text"], "Forecast moved from 15-03-2030 to 01-05-2030 (+47 days)")
        self.assertEqual(out[2]["text"], "Forecast set to 15-03-2030")
        self.assertEqual(out[0]["by"], "Demo User")
        self.assertRegex(out[0]["at"], r"^\d{4}-\d{2}-\d{2} ")
        self.assertEqual(mr.moves(out), 3)

    def test_movement_does_not_list_the_creation(self):
        self.assertEqual(mr.movement(self.s.history(self.mid), self.mid), [])

    def test_a_rebaseline_shows_its_reason_and_decision(self):
        self.step({"forecast_date": "2030-04-01"})
        self.rebaseline("2030-04-01")
        out = [e for e in mr.movement(self.s.history(self.mid), self.mid) if e["kind"] == "rebaseline"]
        self.assertEqual(len(out), 1)
        e = out[0]
        self.assertEqual(e["text"], "Rebaselined: agreed date moved from 01-03-2030 to 01-04-2030")
        self.assertEqual(e["decision"], "ABC-D-001")
        self.assertIn("Vendor delay", e["why"])
        self.assertIn("Sam Example", e["why"])
        self.assertEqual((e["from_date"], e["to_date"], e["undone"]), ("2030-03-01", "2030-04-01", False))

    def test_the_decision_is_the_one_the_store_wrote_last_not_one_named_in_the_reason(self):
        self.step({"baseline_date": "2030-04-01"}, rebaseline={
            "agreed_with": "Sam Example", "reason": "Follows ABC-D-099 from steering, see also XYZ-D-004", "source": "Call"})
        e = [x for x in mr.movement(self.s.history(self.mid), self.mid) if x["kind"] == "rebaseline"][0]
        self.assertIn("ABC-D-099", e["why"])
        self.assertEqual(e["decision"], "ABC-D-001")
        self.assertEqual(mr._last_decision("A-D-001 then ABC-D-002"), "ABC-D-002")
        self.assertEqual(mr._last_decision("no decision here"), "")

    def test_a_one_day_forecast_move_says_day_not_days(self):
        for d in ("2030-03-10", "2030-03-11", "2030-03-09", "2030-03-08"):
            self.step({"forecast_date": d})
        self.assertEqual([e["text"] for e in mr.movement(self.s.history(self.mid), self.mid)],
                         ["Forecast moved from 09-03-2030 to 08-03-2030 (-1 day)",
                          "Forecast moved from 11-03-2030 to 09-03-2030 (-2 days)",
                          "Forecast moved from 10-03-2030 to 11-03-2030 (+1 day)",
                          "Forecast set to 10-03-2030"])

    def test_at_is_the_stored_utc_and_at_text_is_local_time(self):
        self.step({"forecast_date": "2030-03-15"})
        evs = [dict(e, at="2026-10-28 14:05:09.123") for e in self.s.history(self.mid)]
        old = os.environ.get("TZ")
        try:
            for zone, want in (("UTC", "28-10-2026 14:05"), ("Asia/Dubai", "28-10-2026 18:05"),
                               ("Pacific/Auckland", "29-10-2026 03:05")):
                if not hasattr(time, "tzset"):
                    self.skipTest("this system cannot change its time zone while running (no time.tzset)")
                os.environ["TZ"] = zone
                time.tzset()
                if zone != "UTC" and time.strftime("%z", time.localtime(1793196309)) == "+0000":
                    self.skipTest("this system has no time zone data for %s" % zone)
                e = mr.movement(evs, self.mid)[0]
                self.assertEqual((e["at"], e["at_text"]), ("2026-10-28 14:05:09.123", want), zone)
        finally:
            if old is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = old
            if hasattr(time, "tzset"):
                time.tzset()

    def test_a_rebaseline_that_moves_the_forecast_too_is_one_entry(self):
        self.step({"forecast_date": "2030-03-20"})
        self.step({"baseline_date": "2030-04-01", "forecast_date": "2030-04-10"},
                  rebaseline={"agreed_with": "Sam Example", "reason": "Vendor delay", "source": "Call"})
        out = mr.movement(self.s.history(self.mid), self.mid)
        self.assertEqual([e["kind"] for e in out], ["rebaseline", "forecast"])
        self.assertTrue(out[0]["text"].endswith(", forecast now 10-04-2030"), out[0]["text"])

    def test_undone_steps_stay_but_are_marked_and_undo_rows_are_not_listed(self):
        self.step({"forecast_date": "2030-03-15"})
        undone = self.rebaseline()
        self.s.undo(undone, "Demo User")
        events = self.s.history(self.mid)
        self.assertTrue(any(e["is_undo"] for e in events), "history reports the undo as events of its own")
        out = mr.movement(events, self.mid)
        self.assertEqual([(e["kind"], e["undone"]) for e in out], [("rebaseline", True), ("forecast", False)])
        self.assertEqual(mr.moves(out), 1, "an undone move isn't counted")
        self.assertEqual([e["kind"] for e in mr.movement(events, self.mid, include_undone=False)], ["forecast"])

    def test_undoing_the_undo_puts_the_change_back_in_force(self):
        undone = self.rebaseline()
        revert = self.s.undo(undone, "Demo User")["step_id"]
        self.s.undo(revert, "Demo User")
        out = mr.movement(self.s.history(self.mid), self.mid)
        self.assertEqual([(e["kind"], e["undone"]) for e in out], [("rebaseline", False)])

    def test_state_status_choice_and_notes(self):
        self.step({"state": "At risk", "state_set": 1, "state_reason": "Waiting on the vendor"})
        self.step({"movement": "hold"}, note="Holding until the vendor answers")
        self.step({"internal_note": PLANTED})
        self.step({"status": "Done"})
        out = mr.movement(self.s.history(self.mid), self.mid)
        self.assertEqual([e["kind"] for e in out], ["achieved", "internal_note", "movement", "state"])
        by = {e["kind"]: e for e in out}
        self.assertEqual(by["state"]["text"], "State changed from following the dates to At risk")
        self.assertEqual(by["state"]["why"], "Waiting on the vendor")
        self.assertEqual((by["movement"]["text"], by["movement"]["why"]),
                         ("Movement choice: Hold", "Holding until the vendor answers"))
        self.assertTrue(by["internal_note"]["internal"])
        self.assertEqual(by["internal_note"]["detail"], PLANTED)
        self.assertTrue(by["achieved"]["text"].startswith("Achieved on "))

    def test_a_note_on_its_own_stands_alone(self):
        self.step({"owner": "Sam Example"}, note="Handed over")
        out = mr.movement(self.s.history(self.mid), self.mid)
        self.assertEqual([(e["kind"], e["text"]) for e in out], [("note", "Handed over")])

    def test_other_milestones_are_not_mixed_in(self):
        events = self.s.history(self.mid)
        self.rebaseline()
        self.assertEqual(mr.movement(self.s.history(self.mid), "ABC-M-009"), [])
        self.assertEqual(mr.movement(events, self.mid), [])


class Axis(unittest.TestCase):
    def test_timeline_span_is_month_aligned_around_the_marks_and_today(self):
        rows = mr.milestone_rows([row(baseline_date="2026-11-30", forecast_date="2026-12-14"),
                                  row(id="DEMO-M-002", baseline_date="2026-09-10")], ON)
        self.assertEqual(mr.timeline_span(rows, ON), ("2026-08-01", "2027-01-01"))
        self.assertEqual(mr.timeline_span([], ON), ("2026-10-01", "2026-12-01"))

    def test_zoom_is_70_to_300_percent(self):
        self.assertEqual([mr.clamp_zoom(z) for z in (0.1, 1, 2.5, 9, "1.5", None, "x")], [0.7, 1.0, 2.5, 3.0, 1.5, 1.0, 1.0])

    def test_weeks_start_on_monday(self):
        b = mr.buckets("week", "2026-10-28", "2026-11-02")      # a Wednesday to the next Monday
        self.assertEqual([(x["key"], x["start"], x["end"]) for x in b],
                         [("2026-10-26", "2026-10-26", "2026-11-01"), ("2026-11-02", "2026-11-02", "2026-11-08")])
        self.assertEqual(b[0]["label"], "Week of 26-10-2026")
        self.assertEqual(len(mr.buckets("week", "2026-10-26", "2026-11-01")), 1, "Monday to Sunday is one week")
        self.assertEqual(mr.buckets("week", "2026-11-01", "2026-11-01")[0]["key"], "2026-10-26", "a Sunday belongs to the week before")

    def test_month_ends_including_a_leap_day(self):
        ends = {x["key"]: x["end"] for x in mr.buckets("month", "2028-01-15", "2028-04-01")}
        self.assertEqual(ends, {"2028-01": "2028-01-31", "2028-02": "2028-02-29", "2028-03": "2028-03-31", "2028-04": "2028-04-30"})
        self.assertEqual(mr.buckets("month", "2027-02-10", "2027-02-10")[0]["end"], "2027-02-28")
        self.assertEqual(mr.buckets("month", "2028-02-29", "2028-02-29")[0]["key"], "2028-02")
        self.assertEqual(mr.buckets("month", "2028-02-01", "2028-02-01")[0]["label"], "February 2028")

    def test_months_across_a_year_end(self):
        self.assertEqual([x["key"] for x in mr.buckets("month", "2026-11-20", "2027-01-05")], ["2026-11", "2026-12", "2027-01"])
        self.assertEqual(mr.buckets("month", "2026-12-01", "2026-12-31")[0]["end"], "2026-12-31")

    def test_quarter_boundaries(self):
        b = mr.buckets("quarter", "2026-09-30", "2026-10-01")
        self.assertEqual([(x["key"], x["start"], x["end"], x["label"]) for x in b],
                         [("2026-Q3", "2026-07-01", "2026-09-30", "Q3 2026"), ("2026-Q4", "2026-10-01", "2026-12-31", "Q4 2026")])
        self.assertEqual(b[1]["months"], ["2026-10", "2026-11", "2026-12"])
        self.assertEqual([x["key"] for x in mr.buckets("quarter", "2026-12-31", "2027-01-01")], ["2026-Q4", "2027-Q1"])
        self.assertEqual(mr.buckets("quarter", "2028-01-01", "2028-03-31")[0]["end"], "2028-03-31")
        self.assertEqual(len(mr.buckets("quarter", "2026-01-01", "2026-12-31")), 4)

    def test_the_bucket_of_a_date_and_bad_input(self):
        self.assertEqual([mr.bucket_key(k, "2028-02-29") for k in ("week", "month", "quarter")], ["2028-02-28", "2028-02", "2028-Q1"])
        self.assertEqual(mr.buckets("month", "2026-11-01", "2026-10-01"), [])
        with self.assertRaises(ValueError):
            mr.buckets("fortnight", "2026-10-01", "2026-10-31")

    def test_calendar_chips_sit_on_the_solid_mark_and_the_ghost(self):
        rows = mr.milestone_rows([row(baseline_date="2026-11-30", forecast_date="2026-12-14"),
                                  row(id="DEMO-M-002", baseline_date="2026-11-30")], ON)
        chips = mr.calendar_chips(rows)
        self.assertEqual([(c["id"], c["ghost"]) for c in chips["2026-11-30"]], [("DEMO-M-001", False), ("DEMO-M-002", False)])
        self.assertEqual([(c["id"], c["ghost"], c["state"]) for c in chips["2026-12-14"]], [("DEMO-M-001", True, "Slipped")])

    def test_legend_lists_the_six_states_then_expected_and_today(self):
        editor, client = mr.legend(), mr.legend(client=True)
        self.assertEqual([e["state"] for e in editor], ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast",
                                                         "Expected", "Today"])
        self.assertEqual([e["word"] for e in client][:6], ["Achieved", "On track", "At risk", "Expected later", "Late", "Forecast"])
        self.assertEqual([e["word"] for e in editor][:6], list(ms.STATES))
        self.assertEqual({e["state"]: e["colour"] for e in editor[:6]},
                         {"Achieved": "green", "On track": "green", "At risk": "amber", "Slipped": "red", "Overdue": "red",
                          "Forecast": "blue"})
        self.assertEqual(len({e["mark"] for e in editor[:6]}), 6, "each state has its own mark")


class Rebaseline(unittest.TestCase):
    slipped = row(baseline_date="2026-11-30", forecast_date="2026-12-14")
    good = dict(agreed_with="Sam Example", reason="Vendor delay", source="Steering call 27-10-2026")

    def test_a_slipped_milestone_defaults_to_its_expected_date(self):
        req, errors = mr.rebaseline_request(self.slipped, today=ON, **self.good)
        self.assertEqual(errors, [])
        self.assertEqual(req, {"changes": {"baseline_date": "2026-12-14"},
                               "rebaseline": {"agreed_with": "Sam Example", "reason": "Vendor delay",
                                              "source": "Steering call 27-10-2026"}})

    def test_overdue_with_no_forecast_moves_to_today_and_the_forecast_goes_with_it(self):
        req, errors = mr.rebaseline_request(row(baseline_date="2026-10-18"), today=ON, **self.good)
        self.assertEqual((errors, req["changes"]), ([], {"baseline_date": ON}))
        req, _ = mr.rebaseline_request(row(baseline_date="2026-10-18", forecast_date="2026-10-20"), today=ON, **self.good)
        self.assertEqual(req["changes"], {"baseline_date": ON, "forecast_date": ON}, "a forecast before the new date moves too")

    def test_a_given_date_in_either_form_and_a_decision_date(self):
        req, errors = mr.rebaseline_request(self.slipped, "31-01-2027", ["Sam Example", " Alex Example "],
                                            "Scope change", "Email", today=ON, decided_on="27-10-2026")
        self.assertEqual(errors, [])
        self.assertEqual(req["changes"], {"baseline_date": "2027-01-31", "forecast_date": "2027-01-31"})
        self.assertEqual(req["rebaseline"], {"agreed_with": "Sam Example, Alex Example", "reason": "Scope change",
                                             "source": "Email", "date": "2026-10-27"})
        self.assertEqual(mr.rebaseline_request(self.slipped, "2027-01-31", today=ON, **self.good)[0]["changes"],
                         {"baseline_date": "2027-01-31", "forecast_date": "2027-01-31"})

    def test_missing_pieces_are_named_in_plain_words(self):
        req, errors = mr.rebaseline_request(self.slipped, today=ON, agreed_with="  ", reason="", source=None)
        self.assertIsNone(req)
        self.assertEqual(errors, ["Say who agreed the new date.", "Give the reason the agreed date is moving.",
                                  "Give the source: where it was agreed, for example the meeting or the email."])

    def test_cases_that_are_not_a_rebaseline(self):
        for r, new, text in [
                (row(baseline_date="2026-11-30"), None, "hasn't slipped"),
                (row(baseline_date="2026-11-30"), "31-01-2027", "hasn't slipped"),
                (self.slipped, "30-11-2026", "same as the current one (30-11-2026)"),
                (self.slipped, "01-11-2026", "must be later than the current one (30-11-2026)"),
                (self.slipped, "01-02-2020", "must be later than the current one (30-11-2026)"),
                (row(baseline_date="2026-10-01"), "20-10-2026", "can't be before today (28-10-2026)"),
                (row(), "30-11-2026", "no agreed date yet"),
                (row(status="Done", baseline_date="2026-10-01", actual_date="2026-10-02"), "30-11-2026", "this one is done"),
                (row(status="Cancelled", baseline_date="2026-10-01"), "30-11-2026", "this one is cancelled"),
                (row(baseline_date="2026-11-30"), "31-02-2027", "isn't a date I can read"),
                (row(baseline_date="2026-11-30"), "next week", "isn't a date I can read")]:
            with self.subTest(text):
                req, errors = mr.rebaseline_request(r, new, today=ON, **self.good)
                self.assertIsNone(req)
                self.assertTrue(any(text in e for e in errors), errors)

    def test_not_slipped_and_no_date_gives_one_error_not_two(self):
        req, errors = mr.rebaseline_request(row(baseline_date="2026-11-30"), None, today=ON, **self.good)
        self.assertIsNone(req)
        self.assertEqual(errors, ["This milestone hasn't slipped, so give the new agreed date."])

    def test_an_overdue_milestone_may_be_given_a_later_date_from_today_on(self):
        overdue = row(baseline_date="2026-10-01")
        self.assertEqual(mr.rebaseline_request(overdue, ON, today=ON, **self.good)[1], [])
        self.assertEqual(mr.rebaseline_request(overdue, "27-10-2026", today=ON, **self.good)[0], None)

    def test_a_decision_dated_in_the_future_is_refused(self):
        req, errors = mr.rebaseline_request(self.slipped, today=ON, decided_on="29-10-2026", **self.good)
        self.assertEqual((req, errors), (None, ["The decision can't be dated in the future (29-10-2026)."]))

    def test_the_request_goes_to_the_writer_and_records_a_decision(self):
        with DemoStore() as s:
            mid = "ABC-M-001"
            row_now = s.read("milestones", ref=mid)
            req, errors = mr.rebaseline_request(row_now, "01-04-2030", today="2030-03-10", **self.good)   # overdue since 01-03
            self.assertEqual(errors, [])
            with s.step("dashboard", "Demo User") as st:
                st.update("milestones", mid, req["changes"], rebaseline=req["rebaseline"])
            self.assertEqual(s.read("milestones", ref=mid)["baseline_date"], "2030-04-01")
            decisions = s.read("decisions", "ABC")
            self.assertEqual([(d["made_by"], d["status"]) for d in decisions], [("Sam Example", "Made")])


class Dates(unittest.TestCase):
    def test_shown_and_parse(self):
        self.assertEqual(mr.shown("2026-10-28"), "28-10-2026")
        self.assertEqual((mr.parse_date("28-10-2026"), mr.parse_date("2026-10-28"), mr.parse_date("29-02-2028")),
                         ("2026-10-28", "2026-10-28", "2028-02-29"))
        self.assertEqual((mr.parse_date("29-02-2027"), mr.parse_date(""), mr.parse_date(None)), (None, None, None))


if __name__ == "__main__":
    unittest.main()

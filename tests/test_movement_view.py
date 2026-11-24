"""#136 (pure parts): the Movement page's view (src/clark/movement_view.py), by design-136 A2 to A5 and D.

Run: python3 dev/run_tests.py test_movement_view
Histories come from tests/fixtures/movement_events.py (made up). "Today" is fixed, so nothing depends on the real date.
"""
import json
import re
import unittest

import _paths  # noqa: F401
from clark import milestone_rows as mr
from clark import movement_view as mv

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("movement_events", Path(__file__).resolve().parent / "fixtures" / "movement_events.py")
fx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fx)

ON = fx.TODAY


def by_id(out):
    return {r["id"]: r for r in out["rows"]}


class Rows(unittest.TestCase):
    def setUp(self):
        self.out = mv.view(fx.rows(), fx.reply(), ON)
        self.by = by_id(self.out)

    def test_only_open_live_milestones_are_rows(self):
        self.assertEqual(set(self.by), {fx.M_REBASED, fx.M_QUIET, fx.M_FORECAST_BACK, fx.M_UNDONE, fx.M_MANY, fx.M_NO_AGREED})
        for gone in (fx.M_ARCHIVED, fx.M_DONE, fx.M_CANCELLED):
            self.assertNotIn(gone, self.by)
        self.assertEqual(len(self.by), 6)

    def test_worst_first(self):
        ids = [r["id"] for r in self.out["rows"]]
        self.assertEqual(ids[:2], [fx.M_REBASED, fx.M_QUIET])           # 14 days, then 8 days (overdue)
        self.assertEqual(ids[-1], fx.M_NO_AGREED)                       # no slip sorts last

    def test_rows_carry_exactly_the_allowed_keys(self):
        for r in self.out["rows"]:
            self.assertEqual(set(r), mv.ALLOWED_KEYS)
        self.assertEqual(set(self.out), set(mv.SUMMARY_KEYS))

    def test_variance_words(self):
        self.assertEqual(self.by[fx.M_REBASED]["variance"], "14 days after the agreed date")
        self.assertEqual(self.by[fx.M_FORECAST_BACK]["variance"], "On the agreed date")
        self.assertEqual(self.by[fx.M_NO_AGREED]["variance"], "No agreed date yet")
        self.assertEqual(mv.variance_text(1), "1 day after the agreed date")
        self.assertEqual(mv.variance_text(-3), "3 days before the agreed date")
        self.assertEqual(mv.variance_text(0), "On the agreed date")

    def test_a_forecast_milestone_has_no_slip_and_no_behind_wording(self):
        r = self.by[fx.M_NO_AGREED]
        self.assertEqual((r["state"], r["slip"], r["can_move"]), ("Forecast", None, False))
        self.assertNotIn("behind", json.dumps(r))

    def test_the_move_button_is_for_a_slipped_milestone(self):
        self.assertTrue(self.by[fx.M_REBASED]["can_move"])
        self.assertTrue(self.by[fx.M_QUIET]["can_move"])
        self.assertFalse(self.by[fx.M_FORECAST_BACK]["can_move"])

    def test_moves_grammar(self):
        self.assertEqual([mv.moves_text(n) for n in (0, 1, 2, 3)], ["Never moved", "Moved 1 time", "Moved 2 times", "Moved 3 times"])
        self.assertEqual(self.by[fx.M_QUIET]["moves_text"], "Never moved")
        self.assertEqual(self.by[fx.M_REBASED]["moves_text"], "Moved 2 times")        # the rebaseline and one forecast move
        self.assertEqual(self.by[fx.M_FORECAST_BACK]["moves_text"], "Moved 2 times")  # moved out and put back: two moves in force

    def test_an_undone_move_is_listed_with_its_tag_and_not_counted(self):
        r = self.by[fx.M_UNDONE]
        self.assertEqual(r["moves"], 0)
        self.assertEqual(r["moves_text"], "Never moved")
        self.assertEqual([(e["kind"], e["tag"]) for e in r["entries"]], [("rebaseline", "Undone")])
        self.assertFalse(any(e["kind"] == "rebaseline" and not e["undone"] for e in r["entries"]))
        self.assertEqual(r["entries"][0]["decision"], "ABC-D-020")

    def test_the_undo_rows_are_not_lines(self):
        self.assertEqual(len(self.by[fx.M_UNDONE]["entries"]), 1)

    def test_newest_first_and_a_rebaseline_folds_its_forecast_move(self):
        entries = self.by[fx.M_REBASED]["entries"]
        self.assertEqual([e["kind"] for e in entries], ["state", "forecast", "rebaseline"])
        self.assertEqual(entries[-1]["text"],
                         "Rebaselined: agreed date moved from 03-11-2026 to 24-11-2026")          # the forecast followed to the same day
        ids = [e["event_id"] for e in entries]
        self.assertEqual(ids, sorted(ids, reverse=True))

    def test_the_decision_is_the_last_one_cited(self):
        rb = [e for e in self.by[fx.M_REBASED]["entries"] if e["kind"] == "rebaseline"][0]
        self.assertEqual(rb["decision"], "ABC-D-011")                  # the reason also names ABC-D-004
        self.assertEqual(self.by[fx.M_FORECAST_BACK]["entries"][0]["decision"], "")

    def test_forecast_lines_follow_the_day_count_grammar(self):
        texts = [e["text"] for e in self.by[fx.M_FORECAST_BACK]["entries"]]
        self.assertEqual(texts, ["Forecast moved from 17-11-2026 to 10-11-2026 (-7 days)",
                                 "Forecast moved from 10-11-2026 to 17-11-2026 (+7 days)"])
        self.assertIn("(+1 day)", self.by[fx.M_MANY]["entries"][0]["text"])

    def test_a_milestone_with_no_history_has_no_lines(self):
        r = self.by[fx.M_QUIET]
        self.assertEqual((r["entries"], r["total"], r["notice"]), ([], 0, ""))
        self.assertEqual(mv.NOTHING_CHANGED, "Nothing has changed since it was first agreed.")

    def test_the_limit_notice(self):
        r = self.by[fx.M_MANY]
        self.assertEqual(r["total"], 120)
        self.assertEqual(r["notice"], "Showing the latest 50 changes. The peek's Activity has them all.")
        self.assertEqual(self.by[fx.M_REBASED]["notice"], "")

    def test_the_count_comes_from_the_read_and_a_cut_row_has_a_notice(self):
        reply = fx.reply()
        block = dict(reply["milestones"][fx.M_REBASED], moves=7, total=999)
        reply["milestones"][fx.M_REBASED] = block
        r = {x["id"]: x for x in mv.view(fx.rows(), reply, ON)["rows"]}[fx.M_REBASED]
        self.assertEqual(r["moves"], 7)
        self.assertEqual(r["moves_text"], "Moved 7 times")
        self.assertIn("Activity has them all", r["notice"])
        self.assertTrue(r["entries"])

    def test_a_card_cut_to_no_lines_says_so_in_plain_words(self):
        self.assertEqual(mv.OVER_LIMIT_PLAIN, "These changes are too old to show here. The peek's Activity has them all.")
        reply = fx.reply()
        reply["milestones"][fx.M_REBASED] = dict(reply["milestones"][fx.M_REBASED], events=[], total=5)
        r = {x["id"]: x for x in mv.view(fx.rows(), reply, ON)["rows"]}[fx.M_REBASED]
        self.assertEqual((r["entries"], r["notice"]), ([], mv.OVER_LIMIT_PLAIN))

    def test_a_missing_reply_still_draws_the_rows(self):
        out = mv.view(fx.rows(), None, ON)
        self.assertEqual(len(out["rows"]), 6)
        self.assertTrue(all(r["entries"] == [] for r in out["rows"]))
        self.assertFalse(out["truncated"])

    def test_truncated_is_passed_on(self):
        self.assertTrue(mv.view(fx.rows(), dict(fx.reply(), truncated=True), ON)["truncated"])


class Original(unittest.TestCase):
    def test_original_is_never_blank(self):
        self.assertEqual(mv.original_of("2026-11-03", "2026-11-24", None), "2026-11-03")        # the first date in force
        self.assertEqual(mv.original_of(None, "2026-11-24", "2026-12-01"), "2026-11-24")        # only the agreed date
        self.assertEqual(mv.original_of(None, None, "2027-02-01"), "2027-02-01")                # only a forecast
        self.assertIsNone(mv.original_of(None, None, None))

    def test_the_rows_say_so_in_words(self):
        by = by_id(mv.view(fx.rows(), fx.reply(), ON))
        self.assertEqual(by[fx.M_REBASED]["original_text"], "03-11-2026")
        self.assertEqual(by[fx.M_REBASED]["moved_label"], "Agreed date moved")
        self.assertEqual(by[fx.M_QUIET]["original_text"], "20-10-2026")                          # the agreed date, never moved
        self.assertEqual(by[fx.M_QUIET]["moved_label"], "Never moved")
        self.assertEqual(by[fx.M_FORECAST_BACK]["moved_label"], "Moved 2 times", "a forecast that moved is not 'Never moved'")
        self.assertEqual(by[fx.M_MANY]["moved_label"], mv.moves_text(by[fx.M_MANY]["moves"]))
        self.assertNotEqual(by[fx.M_MANY]["moved_label"], "Never moved")
        self.assertEqual(by[fx.M_NO_AGREED]["original_text"], "01-02-2027")                      # the forecast
        none = fx.rows() + [fx.row("ABC-M-010", "Not dated")]
        self.assertEqual(by_id(mv.view(none, fx.reply(), ON))["ABC-M-010"]["original_text"], "No date yet")

    def test_an_undone_first_agreement_is_skipped(self):
        reply = fx.reply()
        evs = reply["milestones"][fx.M_REBASED]["events"]
        first = [e for e in evs if e["field"] == "baseline_date" and e["after"] == "2026-11-03"][0]
        first["in_force"] = False
        self.assertEqual(mr.original_from_events(evs, "2026-11-24"), "2026-11-24")


class Sentences(unittest.TestCase):
    def test_more_than_one_open_milestone(self):
        self.assertEqual(mv.view(fx.rows(), fx.reply(), ON)["sentence"],
                         "2 of 6 open milestones are behind their agreed date; 1 overdue.")

    def test_one_open_milestone(self):
        only = [fx.row("ABC-M-001", "Pilot live", baseline_date="2026-11-24", forecast_date="2026-12-08")]
        self.assertEqual(mv.view(only, None, ON)["sentence"], "The open milestone is behind its agreed date.")
        only = [fx.row("ABC-M-001", "Pilot live", baseline_date="2026-11-24")]
        self.assertEqual(mv.view(only, None, ON)["sentence"], "The open milestone is on its agreed date.")
        only = [fx.row("ABC-M-001", "Pilot live", forecast_date="2026-11-24")]
        self.assertEqual(mv.view(only, None, ON)["sentence"], "The open milestone has no agreed date yet.")

    def test_none_open_and_none_at_all(self):
        done = [fx.row("ABC-M-001", "Kick-off", status="Done", baseline_date="2026-10-01", actual_date="2026-10-01")]
        self.assertEqual(mv.view(done, None, ON)["sentence"], "Every milestone is achieved.")
        self.assertEqual(mv.view([], None, ON)["sentence"], "No milestones yet.")
        archived = [fx.row("ABC-M-001", "Old", baseline_date="2026-09-01", archived=1)]
        self.assertEqual(mv.view(archived, None, ON)["sentence"], "No milestones yet.")

    def test_an_archived_milestone_is_not_counted(self):
        rows = [r for r in fx.rows() if r["id"] != fx.M_ARCHIVED]
        self.assertEqual(mv.view(rows, fx.reply(), ON)["sentence"], mv.view(fx.rows(), fx.reply(), ON)["sentence"])

    def test_the_worst_row_sentence(self):
        out = mv.view(fx.rows(), fx.reply(), ON)
        self.assertEqual(out["worst"], "Pilot live is 14 days behind the agreed date and 35 days behind the original.")
        only = [fx.row("ABC-M-001", "Pilot live", baseline_date="2026-10-27")]
        self.assertEqual(mv.view(only, None, ON)["worst"], "Pilot live is 1 day behind the agreed date.")
        on_time = [fx.row("ABC-M-001", "Pilot live", baseline_date="2026-11-27")]
        self.assertEqual(mv.view(on_time, None, ON)["worst"], "")

    def test_days_text(self):
        self.assertEqual((mv.days_text(1), mv.days_text(2), mv.days_text(0)), ("1 day", "2 days", "0 days"))


class Confirm(unittest.TestCase):
    ROW = fx.row("ABC-M-001", "Pilot live", baseline_date="2026-11-24", forecast_date="2026-12-08")

    def test_the_confirm_words(self):
        self.assertEqual(mv.confirm_text(self.ROW, "2026-12-08", ON, original="2026-11-03"),
                         "Move the agreed date of Pilot live from 24-11-2026 to 08-12-2026? The original date (03-11-2026) "
                         "is kept and a decision is recorded. You can undo this.")
        # typed as DD-MM-YYYY, and the original defaults to the current agreed date
        self.assertIn("(24-11-2026) is kept", mv.confirm_text(self.ROW, "08-12-2026", ON))

    def test_toasts(self):
        self.assertEqual(mv.toast_hold(), "Hold recorded in the note. Undo.")
        self.assertEqual(mv.toast_moved("Pilot live", "2026-12-08"), "Pilot live: the agreed date is now 08-12-2026. Undo.")

    def test_a_move_with_everything_is_not_refused(self):
        self.assertEqual(mv.refusal_text(self.ROW, "2026-12-08", "A. Person", "Build ran long", "Steering minutes", ON), [])

    def test_missing_pieces_use_the_existing_words(self):
        errs = mv.refusal_text(self.ROW, "2026-12-08", None, None, None, ON)
        self.assertEqual(errs, ["Say who agreed the new date.", "Give the reason the agreed date is moving.",
                                "Give the source: where it was agreed, for example the meeting or the email."])

    def test_not_slipped_earlier_and_past_dates(self):
        ok = ("A. Person", "Reason", "Source")
        on_time = fx.row("ABC-M-001", "Pilot live", baseline_date="2026-12-24")
        self.assertEqual(mv.refusal_text(on_time, "2027-01-10", *ok, today=ON),
                         ["This milestone hasn't slipped, so its agreed date can't be moved yet."])
        self.assertEqual(mv.refusal_text(self.ROW, "2026-11-10", *ok, today=ON),
                         ["The new agreed date must be later than the current one (24-11-2026)."])
        late = fx.row("ABC-M-001", "Pilot live", baseline_date="2026-10-01")
        self.assertEqual(mv.refusal_text(late, "2026-10-20", *ok, today=ON),
                         ["The new agreed date can't be before today (28-10-2026)."])

    def test_done_cancelled_and_archived(self):
        ok = ("A. Person", "Reason", "Source")
        done = fx.row("ABC-M-001", "Kick-off", status="Done", baseline_date="2026-10-01")
        self.assertEqual(mv.refusal_text(done, "2026-12-08", *ok, today=ON),
                         ["Only a planned milestone can be rebaselined; this one is done."])
        gone = fx.row("ABC-M-001", "Spin-off", status="Cancelled", baseline_date="2026-10-01")
        self.assertEqual(mv.refusal_text(gone, "2026-12-08", *ok, today=ON),
                         ["Only a planned milestone can be rebaselined; this one is cancelled."])
        self.assertEqual(mv.refusal_text(dict(self.ROW, archived=1), "2026-12-08", *ok, today=ON),
                         ["That milestone is archived. Restore it first."])


class NothingInternal(unittest.TestCase):
    """The internal note and its text never come out of the view."""

    def test_the_internal_note_is_absent_from_every_output(self):
        out = mv.view(fx.rows(), fx.reply(), ON)
        text = json.dumps(out)
        self.assertNotIn(fx.INTERNAL_MARKER, text)
        self.assertNotIn("PLANTED-INTERNAL", text)
        self.assertNotIn("Internal note changed", text)
        self.assertNotIn("internal_note", text)
        self.assertNotIn("detail", text)
        for r in out["rows"]:
            for e in r["entries"]:
                self.assertNotEqual(e["kind"], "internal_note")
                self.assertNotIn("detail", e)
                self.assertTrue(set(e) <= set(mv.ENTRY_KEYS))

    def test_a_note_that_stands_alone_is_not_a_line(self):
        reply = fx.reply()
        reply["milestones"][fx.M_QUIET]["events"] = [fx.ev(fx.M_QUIET, 900, "note", None, "dated line from the internal note", 5)]
        by = by_id(mv.view(fx.rows(), reply, ON))
        self.assertEqual(by[fx.M_QUIET]["entries"], [])

    def test_a_planted_internal_note_event_in_the_reply_is_dropped_anyway(self):
        reply = fx.reply()
        reply["milestones"][fx.M_QUIET]["events"] = [fx.ev(fx.M_QUIET, 901, "internal_note", None, fx.INTERNAL_MARKER, 5)]
        self.assertNotIn(fx.INTERNAL_MARKER, json.dumps(mv.view(fx.rows(), reply, ON)))

    def test_the_view_does_not_return_the_internal_note_even_though_the_row_holds_it(self):
        self.assertIn(fx.INTERNAL_MARKER, json.dumps(fx.rows()))       # the owner's row has it, so the test above means something
        self.assertNotIn(fx.INTERNAL_MARKER, json.dumps(mv.view(fx.rows(), fx.reply(), ON)))

    def test_reasons_stay_in_the_view_for_the_owner(self):
        # The view is owner-only: the reason and the state reason are meant to show there. Nothing publishes it.
        text = json.dumps(mv.view(fx.rows(), fx.reply(), ON))
        self.assertIn(fx.REASON_MARKER, text)
        self.assertIn(fx.STATE_REASON_MARKER, text)

    def test_no_publishing_module_uses_the_view(self):
        src = Path(__file__).resolve().parent.parent / "src" / "clark"
        for name in ("publish.py", "publish_flow.py", "to_client.py", "excel_cover.py", "draft_email.py", "store.py"):
            p = src / name
            if p.exists():
                body = p.read_text(encoding="utf-8")
                self.assertNotIn("movement_view", body, name)

    def test_page_view_has_none_of_it(self):
        page = Path(__file__).resolve().parent.parent / "src" / "clark" / "page"
        for p in page.rglob("page-view.html"):
            body = p.read_text(encoding="utf-8")
            for phrase in (mv.TAG_INTERNAL, mv.TAG_UNDONE + "<", "Movement choice", "Rebaselined", mv.HELP_LINE):
                self.assertNotIn(phrase, body, str(p))


class Wording(unittest.TestCase):
    BANNED = ("sweep", "proposal", "stage", "apply", "vault", "live server", "extract", "refused", "valid", "invalid", "tracker")

    def constants(self):
        return {k: v for k, v in vars(mv).items() if k.isupper() and isinstance(v, str)}

    def test_no_sentence_starts_with_the_product_name(self):
        for k, v in self.constants().items():
            self.assertFalse(v.lower().startswith("clark"), k)

    def test_no_banned_word_in_what_a_person_reads(self):
        for k, v in self.constants().items():
            for word in self.BANNED:
                self.assertIsNone(re.search(r"\b%s\b" % re.escape(word), v.lower()), "%s has %r" % (k, word))

    def test_pinned_constants(self):
        self.assertEqual(mv.TAG_INTERNAL, "Internal only: never published")
        self.assertEqual(mv.HELP_LINE, "Movement is for you and the team: it is never published.")
        self.assertEqual(mv.HOLD_LABEL, "Hold: keep the forecast, agreed date unchanged")
        self.assertEqual(mv.MOVE_LABEL, "Move the agreed date")
        self.assertEqual(mv.READ_FAILS, "Movement couldn't be loaded. Check that clark is still running, then try again.")
        self.assertEqual(mv.ARCHIVED, "That milestone is archived. Restore it first.")
        self.assertEqual(mv.NOT_HERE, "That milestone isn't in this project.")

    def test_dates_in_text_are_dd_mm_yyyy(self):
        for r in mv.view(fx.rows(), fx.reply(), ON)["rows"]:
            for e in r["entries"]:
                self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}", e["text"]), e["text"])
                self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}", e["at_text"]), e["at_text"])
        self.assertIsNone(re.search(r"\d{4}-\d{2}-\d{2}", mv.view(fx.rows(), fx.reply(), ON)["worst"]))

    def test_python_39_safe(self):
        src = (Path(__file__).resolve().parent.parent / "src" / "clark" / "movement_view.py").read_text(encoding="utf-8")
        self.assertNotRegex(src, r"(?m)^\s*match\s")
        self.assertNotRegex(src, r"->\s*\w+\s*\|")


if __name__ == "__main__":
    unittest.main()

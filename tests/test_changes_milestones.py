"""#136 G3: the milestone change kinds of POST /api/change and POST /api/undo (src/clark/changes.py; guarded)."""
import unittest

from _demo import USER, DemoStore
from clark import changes, milestone_rows
from clark.store import NEVER_PUBLISH

WHO = {"agreed_with": "Pat Placeholder", "reason": "Build ran long", "source": "Steering, 01-10-2026"}
COUNTS = "SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log), (SELECT count(*) FROM item_events)"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.m = self.demo.milestone                      # agreed 2030-03-01
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def req(self, fields=None, rebaseline=None, ref=None, project="ABC", place="movement", **more):
        body = {"project": project, "kind": "milestones", "op": "update", "id": ref or self.m, "changes": fields or {}, "place": place}
        if rebaseline is not None:
            body["rebaseline"] = rebaseline
        body.update(more)
        return body

    def ok(self, fields=None, **kw):
        status, got = self.change(self.req(fields, **kw))
        self.assertEqual((status, got.get("ok")), (200, True), got)
        return got

    def counts(self):
        return tuple(self.s.con.execute(COUNTS).fetchone())

    def refused(self, body, words=None, status=400):
        before = self.counts()
        got_status, got = self.change(body)
        self.assertEqual((got_status, got["ok"]), (status, False), got)
        if words is not None:
            self.assertEqual(got["message"], words)
        self.assertEqual(self.counts(), before, "a refused change writes nothing")
        return got

    def slip(self):
        """Forecast past the agreed date, so the milestone has slipped and its agreed date may move."""
        self.ok({"forecast_date": "2030-03-20"})

    def row(self):
        return self.s.read("milestones", ref=self.m)


class TheFields(Base):
    def test_each_field_is_one_step_with_one_undo(self):
        self.ok({"status": "Done"})
        self.ok({"status": "Planned"})
        cases = [{"forecast_date": "2030-03-20"}, {"actual_date": None}, {"state": "At risk", "state_reason": "Waiting on the vendor"},
                 {"client_message": "A short delay."}, {"movement": "hold"}]
        for fields in cases:
            with self.subTest(fields=fields):
                before = dict(self.row())
                got = self.ok(fields)
                if got["apply_id"] is None:
                    continue
                self.assertTrue(got["undoable"])
                tables = {r["table"] for r in self.s.step_rows(got["apply_id"])}
                self.assertEqual(tables, {"milestones"})
                status, undone = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
                self.assertEqual((status, undone["ok"], undone["skipped"]), (200, True, []), undone)
                now = self.row()
                for k in fields:
                    self.assertEqual(now[k], before[k], k)

    def test_done_and_reopen_through_status(self):
        got = self.ok({"status": "Done"})
        self.assertEqual((got["milestone"]["status"], got["milestone"]["state"]), ("Done", None))
        self.assertTrue(got["milestone"]["actual_date"])
        got = self.ok({"status": "Planned"})
        self.assertEqual((got["milestone"]["status"], got["milestone"]["actual_date"]), ("Planned", None))

    def test_the_reply_never_carries_the_internal_note_or_the_name(self):
        got = self.ok({"movement": "hold"})
        self.assertEqual(set(got["milestone"]), set(changes.MILESTONE_SHOWN))
        self.assertNotIn("internal_note", got["milestone"])

    def test_several_fields_in_one_request_are_one_step(self):
        got = self.ok({"forecast_date": "2030-03-20", "movement": "hold", "client_message": "A short delay."})
        self.assertEqual(len({r["via"] for r in self.s.step_rows(got["apply_id"])}), 1)
        self.assertEqual(sum(1 for r in self.s.con.execute("SELECT 1 FROM applies")), 2)       # the set-up step and this one
        status, undone = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual(status, 200)
        row = self.row()
        self.assertEqual((row["forecast_date"], row["movement"], row["client_message"]), (None, None, None))

    def test_a_change_that_changes_nothing_is_not_a_step(self):
        got = self.ok({"forecast_date": None})
        self.assertIsNone(got["apply_id"])
        self.assertFalse(got["undoable"])

    def test_a_state_better_than_the_dates_suggest_needs_its_reason(self):
        self.slip()
        self.refused(self.req({"state": "On track"}), changes.STATE_NEEDS_REASON)
        got = self.ok({"state": "On track", "state_reason": "Recovered with extra staff"})
        self.assertEqual(got["milestone"]["state"], "On track")

    def test_a_forecast_never_needs_a_reason(self):
        got = self.ok({"state": "Forecast"})
        self.assertEqual(got["milestone"]["state"], "Forecast")


class TheRefusals(Base):
    def test_fields_outside_the_list_are_refused_and_nothing_is_written(self):
        for field in ("internal_note", "owner", "name", "workstream", "sort_order", "archived", "project", "id", "description",
                      "percent_complete", "client_visible"):
            with self.subTest(field=field):
                self.refused(self.req({field: "x"}))

    def test_values_that_do_not_fit_are_refused_in_plain_words(self):
        for fields, words in (({"forecast_date": "tomorrow"}, changes.NOT_A_DATE), ({"forecast_date": 20300101}, changes.NOT_A_DATE),
                              ({"forecast_date": "2030-13-45"}, changes.NOT_A_DATE),
                              ({"status": "Cancelled"}, changes.NOT_A_STATUS), ({"status": None}, changes.NOT_A_STATUS),
                              ({"state": "Fine"}, changes.BAD_STATE), ({"movement": "escalate"}, changes.BAD_MOVEMENT),
                              ({"movement": "Hold"}, changes.BAD_MOVEMENT), ({"state_set": True}, changes.FLAG_WORDS),
                              ({"state_set": 2}, changes.FLAG_WORDS), ({"client_message": "a\nb"}, changes.ITEM_TEXT_WORDS),
                              ({"client_message": "x" * 501}, changes.ITEM_VALUE_WORDS), ({"state_reason": ["x"]}, changes.ITEM_VALUE_WORDS)):
            with self.subTest(fields=fields):
                self.refused(self.req(fields), words)

    def test_an_empty_request_and_unknown_keys(self):
        self.refused(self.req({}), "Say what to change.")
        self.refused(self.req({"movement": "hold"}, surprise=1))
        self.refused(self.req({"movement": "hold"}, rebaseline={"agreed_with": "x", "mood": "y"}))
        self.refused(self.req({"movement": "hold"}, rebaseline="x"))

    def test_another_projects_a_missing_and_a_nonsense_milestone_get_the_same_words(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            other = st.create("milestones", {"project": "XYZ", "name": "Elsewhere", "baseline_date": "2030-06-01", "source": "demo"})
        for ref in (other, "ABC-M-099", "ABC-A-001", "ABCD-M-001", None, 7, "ABC-M-001\ud800"):
            with self.subTest(ref=ref):
                body = self.req({"movement": "hold"}, ref="x")
                body["id"] = ref
                self.refused(body, changes.NO_MILESTONE)
        self.refused(self.req({"movement": "hold"}, project="XYZ"), changes.NO_MILESTONE)
        self.assertIsNone(self.s.read("milestones", ref=other)["movement"])

    def test_an_archived_milestone_says_restore_it_first(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("milestones", self.m)
        self.refused(self.req({"movement": "hold"}), changes.ARCHIVED_MILESTONE)

    def test_the_place_movement_belongs_to_milestones_only(self):
        a = self.demo.action()
        body = {"project": "ABC", "kind": "actions", "op": "update", "id": a, "changes": {"owner": "Sam Example"}, "place": "movement"}
        self.refused(body, changes.BAD_PLACE)
        self.refused(self.req({"movement": "hold"}, place="elsewhere"), changes.BAD_PLACE)

    def test_the_place_movement_is_for_a_milestone_change_only_never_another_op(self):
        for op in (set(changes.CHANGE_KINDS["milestones"]) - {changes.UPDATE}):
            with self.assertRaises(changes.Refused) as got:
                changes._shape({"project": "ABC", "kind": "milestones", "op": op, "place": "movement"})
            self.assertEqual(str(got.exception), changes.BAD_PLACE, op)
        self.assertEqual(changes._shape({"project": "ABC", "kind": "milestones", "op": changes.UPDATE, "place": "movement"})[3], "movement")

    def test_an_agreed_date_cannot_be_cleared(self):
        self.refused(self.req({"baseline_date": None}), changes.AGREED_STAYS)
        self.refused(self.req({"baseline_date": ""}), changes.AGREED_STAYS)

    def test_the_stores_refusals_are_fixed_words_with_no_field_name_or_value(self):
        self.ok({"status": "Done"})
        got = self.refused(self.req({"state": "On track"}))
        self.assertNotIn("state_set", got["message"])
        self.assertNotIn("On track", got["message"])


class TheAgreedDate(Base):
    def test_moving_it_needs_who_the_reason_and_the_source(self):
        self.slip()
        got = self.refused(self.req({"baseline_date": "2030-04-01"}))
        for words in ("Say who agreed the new date.", "Give the reason the agreed date is moving.",
                      "Give the source: where it was agreed, for example the meeting or the email."):
            self.assertIn(words, got["message"])
        self.assertEqual(self.s.read("decisions", "ABC"), [])

    def test_it_writes_the_date_the_decision_and_the_note_in_one_step_and_one_undo_takes_them_all_back(self):
        self.slip()
        got = self.ok({"baseline_date": "2030-04-01"}, rebaseline=WHO)
        self.assertEqual((got["milestone"]["baseline_date"], got["milestone"]["forecast_date"], got["decision"]),
                         ("2030-04-01", "2030-04-01", "ABC-D-001"))
        rows = self.s.step_rows(got["apply_id"])
        self.assertEqual({r["table"] for r in rows}, {"milestones", "decisions"})
        self.assertTrue(any(r["table"] == "milestones" and r["field"] == "note" for r in rows))
        (decision,) = self.s.read("decisions", "ABC")
        self.assertEqual((decision["made_by"], decision["status"]), ("Pat Placeholder", "Made"))
        self.assertEqual(decision["client_visible"], 0, "it names who agreed the date: owner only, never in a client's file")
        self.assertIn("01-03-2030 to 01-04-2030", decision["decision"])
        status, undone = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual((status, undone["skipped"]), (200, []), undone)
        row = self.row()
        self.assertEqual((row["baseline_date"], row["forecast_date"]), ("2030-03-01", "2030-03-20"))
        self.assertEqual(self.s.read("decisions", "ABC"), [])
        self.assertIn("ABC-D-001 was removed", undone["words"])
        self.assertIn("agreed date of ABC-M-001 is back to 01-03-2030", undone["words"])
        for text in (WHO["reason"], WHO["agreed_with"], WHO["source"]):
            self.assertNotIn(text, undone["words"])

    def test_the_forecast_stays_where_the_request_puts_it(self):
        self.slip()
        got = self.ok({"baseline_date": "2030-04-01", "forecast_date": "2030-05-01"}, rebaseline=WHO)
        self.assertEqual((got["milestone"]["baseline_date"], got["milestone"]["forecast_date"]), ("2030-04-01", "2030-05-01"))

    def test_the_decision_can_be_dated_and_not_in_the_future(self):
        self.slip()
        self.refused(self.req({"baseline_date": "2030-04-01"}, rebaseline={**WHO, "date": "2999-01-01"}))
        self.ok({"baseline_date": "2030-04-01"}, rebaseline={**WHO, "date": "2026-10-01"})
        self.assertEqual(self.s.read("decisions", "ABC")[0]["date"], "2026-10-01")

    def test_it_follows_rebaseline_requests_own_rules(self):
        self.refused(self.req({"baseline_date": "2030-04-01"}, rebaseline=WHO), milestone_rows.rebaseline_request(
            {**self.row(), "forecast_date": None}, "2030-04-01", **WHO)[1][0])             # not slipped
        self.slip()
        self.refused(self.req({"baseline_date": "2030-02-01"}, rebaseline=WHO))            # earlier than the agreed date
        self.refused(self.req({"baseline_date": "2020-01-01"}, rebaseline=WHO))
        self.ok({"status": "Done"})
        got = self.refused(self.req({"baseline_date": "2030-04-01"}, rebaseline=WHO))
        self.assertIn("Only a planned milestone can be rebaselined; this one is done.", got["message"])

    def test_a_rebaseline_without_a_new_date_is_refused(self):
        self.slip()
        self.refused(self.req({"movement": "hold"}, rebaseline=WHO), changes.NEEDS_NEW_DATE)

    def test_the_first_agreed_date_is_not_a_rebaseline(self):
        with self.s.step("dashboard", USER) as st:
            fresh = st.create("milestones", {"project": "ABC", "name": "Fresh", "source": "demo"})
        status, got = self.change(self.req({"baseline_date": "2030-08-01"}, ref=fresh))
        self.assertEqual((status, got["decision"]), (200, None))
        self.assertEqual(self.s.read("decisions", "ABC"), [])

    def test_an_undo_after_a_later_change_to_the_same_field_leaves_it_and_names_it(self):
        first = self.ok({"forecast_date": "2030-03-20"})
        second = self.ok({"forecast_date": "2030-03-25"})
        status, undone = self.undo({"project": "ABC", "apply_id": first["apply_id"]})
        self.assertEqual(status, 200, undone)
        self.assertTrue(undone["skipped"])
        self.assertEqual(self.row()["forecast_date"], "2030-03-25")
        self.assertIn("was changed later", undone["words"])
        self.assertTrue(second["apply_id"])


class TheHold(Base):
    def test_a_hold_is_the_movement_choice_and_a_dated_line_that_holds_only_dates(self):
        self.slip()
        got = self.ok({"movement": "hold"})
        rows = self.s.step_rows(got["apply_id"])
        notes = [r for r in self.s.con.execute("SELECT new_value FROM change_log WHERE apply_id = ? AND field = 'note'", (got["apply_id"],))]
        self.assertEqual(len(notes), 1)
        self.assertRegex(notes[0][0], r"^\d\d-\d\d-\d{4}: holding; agreed date unchanged, forecast 20-03-2030\.$")
        self.assertNotIn("internal_note", {r["field"] for r in rows})
        self.assertIsNone(self.row()["internal_note"])

    def test_a_hold_shows_in_the_movement_read_with_its_line_and_clearing_it_is_a_change(self):
        self.ok({"movement": "hold"})
        got = self.s.milestone_moves("ABC")["milestones"][self.m]["events"]
        self.assertEqual({e["field"] for e in got}, {"movement", "note"})
        cleared = self.ok({"movement": None})
        self.assertIsNone(cleared["milestone"]["movement"])


    def test_a_hold_is_for_a_planned_milestone_only(self):
        with self.s.step("dashboard", USER) as st:
            st.update("milestones", self.m, {"status": "Done", "actual_date": "2026-10-01", "state": "Achieved", "state_set": 1})
        self.refused(self.req({"movement": "hold"}), changes.NOT_PLANNED)
        self.assertIsNone(self.row()["movement"])

    def test_a_new_agreed_date_clears_an_earlier_hold_and_one_undo_puts_it_back(self):
        self.slip()
        self.ok({"movement": "hold"})
        self.assertEqual(self.row()["movement"], "hold")
        got = self.ok({"baseline_date": "2030-04-01"}, rebaseline=WHO)
        self.assertIsNone(got["milestone"]["movement"])
        status, _ = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.row()["movement"], "hold")
        self.assertEqual(self.row()["baseline_date"], "2030-03-01")


class TheHistory(Base):
    def test_a_movement_change_is_the_dashboard_with_the_source_reference_movement_and_the_users_name(self):
        got = self.ok({"forecast_date": "2030-03-20"})
        rows = self.s.con.execute("SELECT e.place, e.src_ref, e.route, e.actor, a.by_user FROM item_events e "
                                  "JOIN applies a ON a.apply_id = e.apply_id WHERE e.apply_id = ?", (got["apply_id"],)).fetchall()
        self.assertTrue(rows)
        self.assertEqual({tuple(r) for r in rows}, {("dashboard", "Movement", "dashboard", "you", USER)})
        events = self.s.milestone_moves("ABC")["milestones"][self.m]["events"]
        self.assertEqual({e["src_ref"] for e in events}, {"Movement"})

    def test_a_change_from_another_place_is_not_in_movement(self):
        got = self.ok({"forecast_date": "2030-03-20"}, place="menu")
        row = self.s.con.execute("SELECT place, src_ref FROM item_events WHERE apply_id = ? LIMIT 1", (got["apply_id"],)).fetchone()
        self.assertEqual(tuple(row), ("menu", None))


class TheUndoBoundary(Base):
    def test_a_step_of_another_project_is_not_undone_here(self):
        got = self.ok({"forecast_date": "2030-03-20"})
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        status, body = self.undo({"project": "XYZ", "apply_id": got["apply_id"]})
        self.assertEqual((status, body["message"]), (400, changes.NO_UNDO))
        self.assertEqual(self.row()["forecast_date"], "2030-03-20")

    def test_a_step_that_changed_a_field_outside_the_list_is_not_undone_here(self):
        step = self.demo.update("milestones", self.m, {"owner": "Someone Else", "forecast_date": "2030-03-20"})
        status, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual((status, body["message"]), (400, changes.NO_UNDO))

    def test_the_internal_note_is_not_in_what_can_be_undone_from_here(self):
        step = self.demo.update("milestones", self.m, {"internal_note": "PLANTED-NOTE", "forecast_date": "2030-03-20"})
        status, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual((status, body["message"]), (400, changes.NO_UNDO))
        self.assertEqual(self.row()["internal_note"], "PLANTED-NOTE")

    def test_archive_and_restore_are_unchanged(self):
        status, got = self.change({"project": "ABC", "kind": "milestones", "op": "archive", "id": self.m})
        self.assertEqual((status, got["archived"]), (200, 1))
        status, undone = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.row()["archived"], 0)


class TheLists(unittest.TestCase):
    def test_the_allow_lists_name_no_internal_field(self):
        fields = set(changes.CHANGE_KINDS["milestones"][changes.UPDATE])
        self.assertEqual(fields, {"baseline_date", "forecast_date", "actual_date", "status", "state", "state_set", "state_reason",
                                  "client_message", "movement"})
        self.assertFalse(fields & {"internal_note", "owner", "name", "workstream", "sort_order", "project", "id", "archived"})
        self.assertEqual(changes.KIND_OP_KEYS["milestones"][changes.UPDATE], ("id", "changes", "rebaseline"))
        self.assertTrue(fields <= set(changes.UNDOABLE["milestones"]))
        self.assertIn("archived", changes.UNDOABLE["milestones"])
        self.assertNotIn("internal_note", changes.UNDOABLE["milestones"])

    def test_the_published_file_still_never_reads_the_internal_note_or_the_choice(self):
        self.assertTrue({"internal_note", "movement"} <= NEVER_PUBLISH)


if __name__ == "__main__":
    unittest.main()

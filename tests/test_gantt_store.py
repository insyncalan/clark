"""Row 926: the Gantt data layer in the store and the one writer (store.py, changes.py: guarded). Fictional data only.

Pinned here: the gantt_lines table and its CHECKs; the writer's rules in fixed sentences (a real date, the end not before the start, a
milestone on one day, the done % from 0 to 100, depends and parent in the same project, no loop, no self); the ids; the project's six
Gantt columns written like review_after_days; every change (new line after an id, a field, the eye, a move, a delete) as ONE step with
ONE Undo through the existing machinery; a delete takes the id out of the lines that depend on it and the parent from the lines under it
and the Undo puts all of it back; the editor's read keeps every line and every column.

Run: python3 dev/run_tests.py test_gantt_store
"""
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC  # noqa: F401
from clark import changes, store as store_module
from clark.store import Invalid

PH, T1, T2, MS = "ABC-GNT-001", "ABC-GNT-002", "ABC-GNT-003", "ABC-GNT-004"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def go(self, kind="gantt_lines", project="ABC", **req):
        return self.change({"project": project, "kind": kind, **req})

    def ok(self, **req):
        status, body = self.go(**req)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def refused(self, words, **req):
        before = self.counts()
        status, body = self.go(**req)
        self.assertEqual((status, body["ok"], body.get("message")), (400, False, words), req)
        self.assertEqual(self.counts(), before, f"nothing was written for {req!r}")

    def counts(self):
        con = self.s.con
        return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log", "item_events", "gantt_lines"))

    def line(self, ref):
        return self.s.read("gantt_lines", ref=ref)

    def plan(self):
        """A phase with two tasks and a milestone: T1 depends on nothing, T2 on T1, the milestone on T2."""
        self.ok(op="new", values={"type": "phase", "name": "Build", "start": "2026-11-02", "end": "2026-12-18"})
        self.ok(op="new", values={"name": "Dig", "start": "2026-11-02", "end": "2026-11-13"}, after=PH)
        self.ok(op="new", values={"name": "Pour", "start": "2026-11-16", "end": "2026-11-27", "depends": T1}, after=T1)
        self.ok(op="new", values={"type": "milestone", "name": "Handover", "start": "2026-12-18", "depends": T2}, after=T2)

    def undo_step(self, apply_id):
        status, body = self.undo({"project": "ABC", "apply_id": apply_id})
        self.assertEqual(status, 200, body)
        return body


class TheTable(Base):
    def test_the_ids_follow_the_project_and_count_on_and_a_second_project_counts_alone(self):
        self.plan()
        self.assertEqual([r["id"] for r in self.s.read("gantt_lines", project="ABC")], [PH, T1, T2, MS])
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme"})
        self.ok(op="new", project="DEF", values={"name": "Only"})
        self.assertEqual([r["id"] for r in self.s.read("gantt_lines", project="DEF")], ["DEF-GNT-001"])

    def test_a_new_line_goes_after_the_one_named_and_inherits_its_place_and_parent(self):
        self.plan()
        body = self.ok(op="new", values={"name": "Between"}, after=T1)
        self.assertEqual([l["id"] for l in body["lines"]], [PH, T1, "ABC-GNT-005", T2, MS])
        new = self.line("ABC-GNT-005")
        self.assertEqual((new["parent"], new["type"], new["start"], new["end"], new["pct"], new["show"]), (PH, "task", "2026-11-13", "2026-11-13", 0, 0))
        self.assertEqual(self.line(PH)["parent"], None)             # a line after a phase goes under it; the phase itself has none

    def test_ids_never_change_when_lines_move_or_go(self):
        self.plan()
        self.ok(op="move", id=MS, before=T1)
        self.ok(op="delete", id=T2)
        self.assertEqual({r["id"] for r in self.s.read("gantt_lines", project="ABC")}, {PH, T1, MS})
        self.ok(op="new", values={"name": "After the gap"})
        self.assertIn("ABC-GNT-005", {r["id"] for r in self.s.read("gantt_lines", project="ABC")})     # a number once used is not used again

    def test_the_schema_refuses_what_the_writer_would_not_write(self):
        self.plan()
        con = self.s.con
        for sql in ("UPDATE gantt_lines SET type = 'epic' WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET pct = 101 WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET health = 'Purple' WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET priority = 'Urgent' WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET show = 2 WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET \"end\" = '2026-01-01' WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET \"end\" = '2026-12-31' WHERE id = 'ABC-GNT-004'",       # a milestone on two days
                    "UPDATE gantt_lines SET parent = id WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET parent = 'ABC-GNT-002' WHERE id = 'ABC-GNT-001'",       # a phase has no parent
                    "UPDATE gantt_lines SET note = hex(zeroblob(2100)) WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET effort = -1 WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET name = '  ' WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET id = 'DEF-GNT-009' WHERE id = 'ABC-GNT-002'",
                    "UPDATE gantt_lines SET project = 'XYZ' WHERE id = 'ABC-GNT-002'"):
            with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                con.execute(sql)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO gantt_lines (id, project, type, name, start, \"end\") VALUES ('ABC-X-001', 'ABC', 'task', 'x', '2026-01-01', '2026-01-02')")

    def test_a_new_line_starts_off_the_client_view_and_with_the_defaults(self):
        self.ok(op="new", values={})
        row = self.line(PH)
        self.assertEqual((row["name"], row["type"], row["show"], row["health"], row["priority"], row["depends"], row["owner"], row["note"]),
                         ("New task", "task", 0, "", "", "", "", ""))
        self.assertEqual((row["parent"], row["baseline_start"], row["effort"], row["budget"]), (None, None, None, None))


class TheRules(Base):
    def test_every_refusal_is_a_fixed_sentence_and_writes_nothing(self):
        self.plan()
        W = store_module
        cases = [
            ({"start": "06-11-2026"}, W.GANTT_BAD_DATE), ({"start": "2026-02-30"}, W.GANTT_BAD_DATE), ({"start": "20261106"}, W.GANTT_BAD_DATE),
            ({"start": ""}, W.GANTT_BAD_DATE), ({"start": 5}, W.GANTT_BAD_DATE),
            ({"end": "2026-11-01"}, W.GANTT_END_BEFORE_START), ({"start": "2026-12-01"}, W.GANTT_END_BEFORE_START),
            ({"pct": 101}, W.GANTT_BAD_PCT), ({"pct": -1}, W.GANTT_BAD_PCT), ({"pct": True}, W.GANTT_BAD_PCT), ({"pct": 50.5}, W.GANTT_BAD_PCT),
            ({"pct": "50"}, W.GANTT_BAD_PCT), ({"name": ""}, W.GANTT_NO_NAME), ({"name": "   "}, W.GANTT_NO_NAME), ({"name": None}, W.GANTT_NO_NAME),
            ({"name": "x" * 201}, W.GANTT_BAD_TEXT), ({"name": "a‮b"}, W.GANTT_BAD_TEXT), ({"name": "a\nb"}, W.GANTT_BAD_TEXT),
            ({"note": "n" * 2001}, W.GANTT_BAD_TEXT), ({"owner": "o" * 201}, W.GANTT_BAD_TEXT), ({"owner": ["x"]}, W.GANTT_BAD_TEXT),
            ({"health": "Purple"}, W.GANTT_BAD_CHOICE), ({"priority": "Urgent"}, W.GANTT_BAD_CHOICE), ({"type": "epic"}, W.GANTT_BAD_TYPE),
            ({"effort": -1}, W.GANTT_BAD_NUMBER), ({"budget": "lots"}, W.GANTT_BAD_NUMBER), ({"effort": True}, W.GANTT_BAD_NUMBER),
            ({"effort": float("nan")}, W.GANTT_BAD_NUMBER),
            ({"effort": 2_000_000}, W.GANTT_BAD_NUMBER), ({"effort": 1_000_000.5}, W.GANTT_BAD_NUMBER), ({"budget": 1e99}, W.GANTT_BAD_NUMBER),
            ({"budget": 10**12 + 1}, W.GANTT_BAD_NUMBER), ({"budget": float("inf")}, W.GANTT_BAD_NUMBER),
            ({"baseline_start": "2026-12-01", "baseline_end": "2026-11-01"}, W.GANTT_BAD_BASELINE),
            ({"show": 2}, changes.FLAG_WORDS), ({"show": True}, changes.FLAG_WORDS), ({"show": "1"}, changes.FLAG_WORDS),
            ({"depends": "ABC-GNT-099"}, 'There is no line "ABC-GNT-099" to depend on.'),
            ({"depends": "DEF-GNT-001"}, 'There is no line "DEF-GNT-001" to depend on.'),
            ({"depends": T2}, W.GANTT_SELF_DEPENDS), ({"depends": MS}, W.GANTT_LOOP),
            ({"parent": "ABC-GNT-099"}, 'There is no line "ABC-GNT-099" to be the parent.'), ({"parent": T1}, W.GANTT_PARENT_PHASE), ({"parent": T2}, 'There is no line "ABC-GNT-003" to be the parent.'),
            ({"days": 3}, "Days is worked out; it cannot be typed over."), ({"status": "Late"}, "Status is worked out; it cannot be typed over."),
            ({"id": "ABC-GNT-009"}, "The field 'id' can't be set here."), ({"project": "DEF"}, "The field 'project' can't be set here."),
            ({"sort_order": 5}, "The field 'sort_order' can't be set here."),
        ]
        for chg, words in cases:
            self.refused(words, op="update", id=T2, changes=chg)
        self.refused(W.GANTT_MILESTONE_ONE_DATE, op="update", id=MS, changes={"end": "2026-12-30"})
        self.refused(W.GANTT_PHASE_TOP, op="update", id=PH, changes={"parent": T1})
        self.refused(W.GANTT_PHASE_KEEPS, op="update", id=PH, changes={"type": "task"})

    def test_effort_and_budget_at_their_limits_are_kept_and_above_them_are_refused_in_words(self):
        self.plan()
        self.ok(op="update", id=T1, changes={"effort": 1_000_000, "budget": 10**12})
        row = self.line(T1)
        self.assertEqual((row["effort"], row["budget"]), (1_000_000.0, 1e12))
        before = self.counts()
        for chg in ({"effort": 2_000_000}, {"budget": 1e99}, {"effort": 1_000_001, "budget": 1}):
            self.refused(store_module.GANTT_BAD_NUMBER, op="update", id=T1, changes=chg)         # a sentence, never a raw database error
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.line(T1)["effort"], 1_000_000.0)

    def test_a_milestone_has_one_date_start_moves_both(self):
        self.plan()
        self.ok(op="update", id=MS, changes={"start": "2026-12-20"})
        row = self.line(MS)
        self.assertEqual((row["start"], row["end"]), ("2026-12-20", "2026-12-20"))
        self.ok(op="update", id=T1, changes={"type": "milestone"})                 # a task made a milestone is on its start
        self.assertEqual(self.line(T1)["end"], self.line(T1)["start"])

    def test_a_note_may_have_line_breaks_a_name_may_not_and_text_is_kept_as_text(self):
        self.plan()
        self.ok(op="update", id=T1, changes={"note": "line one\r\nline two", "name": "<script>alert(1)</script>"})
        row = self.line(T1)
        self.assertEqual((row["note"], row["name"]), ("line one\nline two", "<script>alert(1)</script>"))

    def test_depends_are_stored_as_a_clean_comma_list_and_a_list_is_taken_too(self):
        self.plan()
        self.ok(op="update", id=MS, changes={"depends": [T1, T2, T1]})
        self.assertEqual(self.line(MS)["depends"], f"{T1},{T2}")
        self.ok(op="update", id=MS, changes={"depends": ""})
        self.assertEqual(self.line(MS)["depends"], "")

    def test_a_line_of_another_project_is_not_reachable_and_a_foreign_id_is_not_a_dependency(self):
        self.plan()
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme"})
        self.ok(op="new", project="DEF", values={"name": "Theirs"})
        self.refused(changes.NOT_MINE_RECORD, op="update", id="DEF-GNT-001", changes={"name": "Mine now"})
        self.refused(changes.NOT_MINE_RECORD, op="delete", id="DEF-GNT-001")
        self.refused(changes.NOT_MINE_RECORD, op="move", id="DEF-GNT-001", before=None)
        self.refused('There is no line "DEF-GNT-001" to depend on.', op="update", id=T1, changes={"depends": "DEF-GNT-001"})
        self.refused('There is no line "DEF-GNT-001" to be the parent.', op="update", id=T1, changes={"parent": "DEF-GNT-001"})
        self.assertEqual(self.line("DEF-GNT-001")["name"], "Theirs")

    def test_an_id_in_a_message_is_made_safe(self):
        self.plan()
        status, body = self.go(op="update", id=T1, changes={"depends": "<b>x</b>\"; DROP"})
        self.assertEqual(status, 400)
        self.assertNotIn("<", body["message"])

    def test_a_line_count_limit_and_an_archived_project(self):
        with mock.patch.object(store_module, "MAX_GANTT_LINES", 2):
            self.ok(op="new", values={})
            self.ok(op="new", values={})
            self.refused(store_module.GANTT_TOO_MANY, op="new", values={})
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        self.refused(changes.PROJECT_NOT_ACTIVE, op="new", values={})

    def test_the_store_checks_again_whatever_the_route_sent(self):
        self.plan()
        with self.s.step("dashboard", USER) as st:
            with self.assertRaises(Invalid):
                st.update("gantt_lines", T2, {"depends": f"{MS}"})
            with self.assertRaises(Invalid):
                st.create("gantt_lines", {"project": "ABC", "type": "task", "name": "x", "start": "2026-11-10", "end": "2026-11-01", "sort_order": 9})
            with self.assertRaises(Invalid):
                st.create("gantt_lines", {"id": "ABC-GNT-777", "project": "ABC", "type": "task", "name": "x", "start": "2026-11-01", "end": "2026-11-01", "sort_order": 9})
            with self.assertRaises(Invalid):
                st.update("gantt_lines", T2, {"project": "DEF"})


class OneStepOneUndo(Base):
    def test_a_new_line_is_one_step_and_its_undo_takes_it_away_and_nothing_else(self):
        self.plan()
        before = self.s.read("gantt_lines", project="ABC")
        body = self.ok(op="new", values={"name": "Extra"}, after=T1)
        self.assertEqual(self.s.con.execute("SELECT count(DISTINCT apply_id) FROM change_log WHERE apply_id = ?", (body["apply_id"],)).fetchone()[0], 1)
        out = self.undo_step(body["apply_id"])
        self.assertIn("was removed", out["words"])
        self.assertEqual(self.s.read("gantt_lines", project="ABC"), before)

    def test_a_change_of_several_fields_is_one_step_and_one_undo(self):
        self.plan()
        was = self.line(T1)
        body = self.ok(op="update", id=T1, changes={"name": "Dig deep", "pct": 40, "owner": "A. Builder", "start": "2026-11-03", "show": 1})
        out = self.undo_step(body["apply_id"])
        self.assertEqual({k: v for k, v in self.line(T1).items() if k != "updated_at"}, {k: v for k, v in was.items() if k != "updated_at"})
        self.assertNotIn("Dig deep", out["words"])                       # the words never quote the text
        self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 409)       # undone already

    def test_the_eye_is_one_step_and_goes_back(self):
        self.plan()
        body = self.ok(op="update", id=T1, changes={"show": 1})
        self.assertEqual(self.line(T1)["show"], 1)
        self.assertEqual(self.ok(op="update", id=T1, changes={"show": 1})["apply_id"], None)       # no change, no step, no Undo
        self.assertIn("shown to the client", changes.words([{"ref": "ABC-GNT-002", "field": "show", "change": "set", "to": "1"}], [], {}))
        self.undo_step(body["apply_id"])
        self.assertEqual(self.line(T1)["show"], 0)

    def test_a_move_is_one_step_and_goes_back(self):
        self.plan()
        order = lambda: [r["id"] for r in sorted(self.s.read("gantt_lines", project="ABC"), key=lambda r: (r["sort_order"], r["id"]))]
        body = self.ok(op="move", id=MS, before=T1)
        self.assertEqual(order(), [PH, MS, T1, T2])
        self.undo_step(body["apply_id"])
        self.assertEqual(order(), [PH, T1, T2, MS])
        self.refused("A line can't be moved before itself.", op="move", id=T1, before=T1)

    def test_a_move_that_has_no_room_renumbers_in_the_same_step(self):
        self.plan()
        with self.s.step("dashboard", USER) as st:
            for n, ref in enumerate((PH, T1, T2, MS)):
                st.update("gantt_lines", ref, {"sort_order": 10 + n})
        body = self.ok(op="move", id=MS, before=T2)
        self.assertEqual([l["id"] for l in body["lines"]], [PH, T1, MS, T2])
        self.undo_step(body["apply_id"])
        self.assertEqual([r["sort_order"] for r in sorted(self.s.read("gantt_lines", project="ABC"), key=lambda r: r["id"])], [10, 11, 12, 13])

    def test_a_delete_takes_the_id_from_dependents_and_the_parent_from_children_and_undo_puts_all_back(self):
        self.plan()
        everything = {r["id"]: r for r in self.s.read("gantt_lines", project="ABC")}
        body = self.ok(op="delete", id=T2)
        by = {l["id"]: l for l in body["lines"]}
        self.assertNotIn(T2, by)
        self.assertEqual(by[MS]["depends"], "")                                     # the milestone lost the id
        self.ok(op="update", id=T1, changes={"depends": ""})                        # (a later change of another line)
        body = self.ok(op="delete", id=PH)
        by = {l["id"]: l for l in body["lines"]}
        self.assertEqual((by[T1]["parent"], by[MS]["parent"]), (None, None))        # the children lost the parent
        out = self.undo_step(body["apply_id"])
        self.assertEqual(self.line(PH)["name"], "Build")
        self.assertEqual((self.line(T1)["parent"], self.line(MS)["parent"]), (PH, PH))
        self.assertIn(PH, [e["ref"] for e in out["reversed"]])
        self.assertEqual(everything[PH], self.line(PH))

    def test_the_undo_of_a_delete_gives_back_the_dependencies_it_took(self):
        self.plan()
        body = self.ok(op="delete", id=T2)
        self.undo_step(body["apply_id"])
        self.assertEqual(self.line(MS)["depends"], T2)
        self.assertEqual(self.line(T2)["depends"], T1)

    def test_a_delete_is_one_step(self):
        self.plan()
        n = self.counts()[0]
        self.ok(op="delete", id=T1)
        self.assertEqual(self.counts()[0], n + 1)

    def test_an_undo_of_a_new_line_is_left_alone_when_another_line_depends_on_it_now(self):
        self.plan()
        made = self.ok(op="new", values={"name": "Late one"}, after=MS)
        new = made["ref"]
        self.ok(op="update", id=MS, changes={"depends": new})
        status, out = self.undo({"project": "ABC", "apply_id": made["apply_id"]})
        self.assertEqual(status, 200)
        self.assertIsNotNone(self.line(new))
        self.assertEqual(out["reversed"], [])

    def test_a_step_that_holds_a_gantt_line_is_not_undone_from_another_project(self):
        self.plan()
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme"})
        body = self.ok(op="update", id=T1, changes={"pct": 10})
        status, _ = self.undo({"project": "DEF", "apply_id": body["apply_id"]})
        self.assertEqual(status, 400)
        self.assertEqual(self.line(T1)["pct"], 10)

    def test_history_names_the_line_in_plain_words(self):
        from clark import history
        self.plan()
        self.assertEqual(history.field_name("gantt_lines", "pct"), "Done %")
        self.assertEqual(history.field_name("gantt_lines", "show"), "On dashboard")
        self.assertEqual(history.THING["gantt_lines"], "Gantt line")


class ProjectColumns(Base):
    def proj(self):
        return self.s.read("projects", ref="ABC")

    def change_project(self, **fields):
        return self.go(kind="projects", op="update", changes=fields)

    def test_the_defaults(self):
        p = self.proj()
        self.assertEqual((p["show_gantt_editor"], p["show_gantt_client"], p["gantt_tab_name"], p["gantt_title"], p["gantt_hidden_columns"], p["gantt_default_rows"]),
                         (0, 0, "Gantt", "", "show,note,budget,effort,baseline_start,baseline_end", None))
        self.assertEqual(tuple(p["gantt_hidden_columns"].split(",")), store_module.GANTT_DEFAULT_HIDDEN)

    def test_each_is_one_step_with_one_undo_and_the_echo_carries_them(self):
        for fields in ({"show_gantt_editor": 1}, {"show_gantt_client": 1}, {"gantt_tab_name": "Plan"}, {"gantt_title": "Rollout plan"},
                       {"gantt_hidden_columns": "owner,note"}, {"gantt_default_rows": 12}):
            status, body = self.change_project(**fields)
            self.assertEqual((status, body.get("message")), (200, None), fields)
            key = next(iter(fields))
            self.assertEqual(body["project"][key], self.proj()[key])
            out = self.undo_step(body["apply_id"])
            self.assertIn("Gantt settings", out["words"])
            self.assertEqual(self.proj()[key], self.default_of(key))

    def default_of(self, key):
        return {"show_gantt_editor": 0, "show_gantt_client": 0, "gantt_tab_name": "Gantt", "gantt_title": "",
                "gantt_hidden_columns": "show,note,budget,effort,baseline_start,baseline_end", "gantt_default_rows": None}[key]

    def test_the_hidden_columns_are_a_checked_list_in_the_tables_order(self):
        status, body = self.change_project(gantt_hidden_columns="note, owner,note,health")
        self.assertEqual(status, 200)
        self.assertEqual(self.proj()["gantt_hidden_columns"], "note,owner,health")
        self.change_project(gantt_hidden_columns="")
        self.assertEqual(self.proj()["gantt_hidden_columns"], "")
        for bad in ("id", "name", "nonsense", "owner,id", "Owner", None, 5, ["owner"], "pct;DROP",
                    "type", "start", "end", "pct", "owner,start", "end,note", "pct,type"):         # row 926 read: the chart needs these four, so they cannot be hidden
            status, body = self.change_project(gantt_hidden_columns=bad)
            self.assertEqual((status, body["message"]), (400, store_module.GANTT_BAD_COLUMNS), bad)
        self.assertEqual(set(store_module.GANTT_COLUMNS), {"type", "parent", "start", "end", "pct", "health", "depends", "owner", "workstream",
                                                           "priority", "baseline_start", "baseline_end", "effort", "budget", "deliverable", "show", "note"})

    def test_the_four_columns_the_chart_needs_are_never_hideable(self):
        self.assertEqual(set(store_module.GANTT_NEVER_HIDDEN), {"type", "start", "end", "pct"})
        self.assertTrue(set(store_module.GANTT_NEVER_HIDDEN).isdisjoint(store_module.GANTT_HIDEABLE))
        self.assertTrue(set(store_module.GANTT_NEVER_HIDDEN).isdisjoint(store_module.GANTT_DEFAULT_HIDDEN))
        self.assertEqual(set(store_module.GANTT_HIDEABLE) | set(store_module.GANTT_NEVER_HIDDEN), set(store_module.GANTT_COLUMNS))

    def test_the_two_switches_the_tab_name_the_title_and_the_rows_refuse_what_is_not_theirs(self):
        for field, bad, words in (("show_gantt_editor", (2, True, "1", None, 1.0), changes.FLAG_WORDS),
                                  ("show_gantt_client", (2, True, "1", None, -1), changes.FLAG_WORDS),
                                  ("gantt_tab_name", ("", "  ", "x" * 31, "a‮b", "a\nb", 5, None), store_module.GANTT_BAD_TAB),
                                  ("gantt_title", ("x" * 121, "a‮b", "a\nb", 5), store_module.GANTT_BAD_TITLE),
                                  ("gantt_default_rows", (0, 501, True, 1.5, "10", -3, [5]), store_module.GANTT_BAD_ROWS)):
            for value in bad:
                before = self.counts()
                status, body = self.change_project(**{field: value})
                self.assertEqual((status, body["message"]), (400, words), (field, value))
                self.assertEqual(self.counts(), before)
        self.assertEqual(self.change_project(gantt_tab_name="x" * 30)[0], 200)             # the page's limit is 30
        self.assertEqual(self.change_project(gantt_default_rows=500)[0], 200)
        self.assertEqual(self.change_project(gantt_default_rows=None)[0], 200)
        self.assertIsNone(self.proj()["gantt_default_rows"])
        self.assertEqual(self.change_project(gantt_title="")[0], 200)                       # empty title: the project's name

    def test_the_schema_checks_them_too(self):
        con = self.s.con
        for sql in ("UPDATE projects SET gantt_tab_name = ''", "UPDATE projects SET gantt_tab_name = '" + "x" * 31 + "'",
                    "UPDATE projects SET gantt_default_rows = 0", "UPDATE projects SET gantt_default_rows = 501",
                    "UPDATE projects SET show_gantt_client = 2"):
            with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                con.execute(sql)


class TheRead(Base):
    def test_the_editors_read_keeps_every_line_every_column_and_the_settings_in_order(self):
        self.plan()
        self.ok(op="update", id=T1, changes={"note": "internal", "budget": 5000, "effort": 12.5, "show": 0})
        self.ok(op="move", id=MS, before=PH)
        data = self.s.data_for("ABC")
        self.assertEqual([l["id"] for l in data["gantt_lines"]], [MS, PH, T1, T2])
        row = next(l for l in data["gantt_lines"] if l["id"] == T1)
        self.assertEqual((row["note"], row["budget"], row["effort"], row["show"]), ("internal", 5000.0, 12.5, 0))
        for f in ("show_gantt_editor", "show_gantt_client", "gantt_tab_name", "gantt_title", "gantt_hidden_columns", "gantt_default_rows"):
            self.assertIn(f, data["project"])

    def test_a_project_with_no_lines_reads_an_empty_list(self):
        self.assertEqual(self.s.data_for("ABC")["gantt_lines"], [])


if __name__ == "__main__":
    unittest.main()

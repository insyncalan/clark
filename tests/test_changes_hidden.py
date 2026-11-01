"""#67: the eye (report_hidden), the picker's one step, the headline and work item title edits, and the insert kinds through
POST /api/change and /api/undo (src/clark/changes.py; guarded).

Run: python3 dev/run_tests.py test_changes_hidden
Each test makes a real store in a temporary folder (fictional data) and calls the same functions the server calls.
"""
import sqlite3
import unittest

from _demo import USER, DemoStore
from clark import changes, history, publish, store as store_module


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.path = self.s.path
        self.change = changes.make_change(self.path, [], USER)
        self.undo = changes.make_undo(self.path, [], USER)

    def ok(self, request):
        status, body = self.change(request)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def snapshot(self):
        con = sqlite3.connect(str(self.path))
        try:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                         for t in ("applies", "change_log", "item_events", "report_hidden", "actions", "raid", "decisions",
                                   "milestones", "use_cases", "item_labels", "report_sections"))
        finally:
            con.close()

    def refused(self, request, words, status=400):
        before = self.snapshot()
        got = self.change(request)
        self.assertEqual((got[0], got[1]["ok"], got[1]["message"]), (status, False, words), request)
        self.assertEqual(self.snapshot(), before, "nothing was written")

    def back(self, apply_id, project="ABC"):
        return self.undo({"project": project, "apply_id": apply_id})

    def other_project(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
            return st.create("actions", {"project": "XYZ", "description": "Order the licences", "raised": "2026-10-01", "source": "demo"})

    def hidden(self):
        return sorted(r["item_id"] for r in self.s.read("report_hidden", "ABC"))


def eye(op, item, project="ABC"):
    return {"project": project, "kind": "report_hidden", "op": op, "id": item}


class Eye(Base):
    def test_hide_and_show_each_one_step_one_undo(self):
        a = self.demo.action()
        body = self.ok(eye("new", a))
        self.assertEqual((body["ref"], body["hidden"]), (a, [a]))
        self.assertEqual(self.hidden(), [a])
        shown = self.ok(eye("delete", a))
        self.assertEqual((self.hidden(), shown["hidden"]), ([], []))
        self.assertNotEqual(body["apply_id"], shown["apply_id"])

    def test_every_kind_of_row_the_report_shows_can_be_hidden(self):
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "raised": "2026-10-01",
                                   "source": "demo", "impact": "High", "likelihood": "Low"})
            d = st.create("decisions", {"project": "ABC", "decision": "Use the cloud", "source": "demo", "status": "Made",
                                        "date": "2026-10-02"})
        ids = [self.demo.action(), r, d, self.demo.milestone, self.demo.use_case]
        for item in ids:
            self.ok(eye("new", item))
        self.assertEqual(self.hidden(), sorted(ids))

    def test_undo_of_a_hide_shows_the_row_again(self):
        a = self.demo.action()
        step = self.ok(eye("new", a))["apply_id"]
        status, out = self.back(step)
        self.assertEqual((status, out["hidden"], self.hidden()), (200, [], []), out)
        self.assertEqual(out["words"], f"Put back: {a} is back in the report.")
        self.assertEqual(self.back(out["apply_id"]), (400, {"ok": False, "message": changes.NO_UNDO, "code": "refused"}))   # an undo is not undone from here

    def test_undo_of_a_show_hides_the_row_again(self):
        a = self.demo.action()
        self.ok(eye("new", a))
        step = self.ok(eye("delete", a))["apply_id"]
        status, out = self.back(step)
        self.assertEqual((status, out["hidden"]), (200, [a]))
        self.assertEqual(out["words"], f"Put back: {a} is hidden from the report again.")

    def test_a_second_undo_is_409_and_a_hide_from_another_route_is_not_ours(self):
        a, b = self.demo.action(), self.demo.action()
        step = self.ok(eye("new", a))["apply_id"]
        self.back(step)
        self.assertEqual(self.back(step)[0], 409)
        with self.s.step("excel", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": b})
        status, out = self.back(self.demo.last_step())
        self.assertEqual((status, out["message"]), (400, changes.NO_UNDO))
        self.assertEqual(self.hidden(), [b])

    def test_a_later_change_to_the_same_row_is_skipped_and_named(self):
        a = self.demo.action()
        first = self.ok(eye("new", a))["apply_id"]
        self.ok(eye("delete", a))
        later = self.ok(eye("new", a))["apply_id"]
        status, out = self.back(first)
        self.assertEqual((status, out["reversed"], out["apply_id"]), (200, [], None), out)
        self.assertEqual(out["words"], f"Nothing was put back. {a} was changed later (step {later}), so it was left as it is.")
        self.assertEqual(self.hidden(), [a])
        self.assertEqual(self.back(later)[0], 200)
        self.assertEqual(self.hidden(), [])

    def test_undo_of_a_show_after_the_row_was_hidden_again_is_skipped_and_named(self):
        a = self.demo.action()
        self.ok(eye("new", a))
        shown = self.ok(eye("delete", a))["apply_id"]
        self.ok(eye("new", a))
        status, out = self.back(shown)
        self.assertEqual((status, out["reversed"]), (200, []))
        self.assertIn("so it was left as it is", out["words"])
        self.assertEqual(self.hidden(), [a])

    def test_refusals_write_nothing(self):
        a = self.demo.action()
        other = self.other_project()
        self.refused(eye("delete", a), changes.NOT_HIDDEN)
        self.ok(eye("new", a))
        self.refused(eye("new", a), changes.ALREADY_HIDDEN)
        for bad in (other, "ABC-A-999", "ABC-S-001", "ABC-W-001", "abc-a-001", "", None, 5, ["ABC-A-001"], {"x": 1}, "ABC-A-001|x",
                    "ABC|ABC-A-001", "ABCD-A-001", " ABC-A-001"):
            with self.subTest(bad=bad):
                self.refused(eye("new", bad), changes.ITEM_NOT_MINE)
                self.refused(eye("delete", bad), changes.ITEM_NOT_MINE)
        self.refused({**eye("new", a), "values": {"item_id": a}}, "That change doesn't take 'values'.")
        self.refused({**eye("new", a), "after": None}, "That change doesn't take 'after'.")
        self.refused({"project": "ABC", "kind": "report_hidden", "op": "update", "id": a}, changes.BAD_OP)
        self.refused({"project": "ABC", "kind": "report_hidden", "op": "move", "id": a}, changes.BAD_OP)
        self.refused({"project": "ABC", "kind": "report_hidden", "op": "archive", "id": a}, changes.BAD_OP)
        self.refused({"project": "ABC", "kind": "report_hidden", "op": "new"}, changes.ITEM_NOT_MINE)

    def test_another_projects_row_is_refused_in_the_same_words_as_a_missing_one(self):
        other = self.other_project()
        self.refused(eye("new", other), changes.ITEM_NOT_MINE)
        self.assertEqual(self.s.read("report_hidden", "XYZ"), [])
        self.ok(eye("new", other, project="XYZ"))
        self.assertEqual(self.hidden(), [])
        a = self.demo.action()
        step = self.ok(eye("new", a))["apply_id"]
        status, out = self.undo({"project": "XYZ", "apply_id": step})
        self.assertEqual((status, out["message"]), (400, changes.NO_UNDO))
        self.assertEqual(self.hidden(), [a])

    def test_a_hostile_id_is_never_said_back(self):
        for bad in ("<script>alert(1)</script>", "ABC-A-001\n", "ABC-A-001‮", "ABC-A-00١", "\ud800", "ABC-A-001; DROP TABLE x"):
            with self.subTest(bad=bad):
                status, body = self.change(eye("new", bad))
                self.assertEqual((status, body["message"]), (400, changes.ITEM_NOT_MINE))
                self.assertNotIn(bad[:5], body["message"])
        self.assertEqual(self.hidden(), [])

    def test_an_eye_event_is_in_no_items_activity(self):
        a = self.demo.action()
        before = [e["event_id"] for e in history.history(self.s.con, a)]
        step = self.ok(eye("new", a))["apply_id"]
        self.ok(eye("delete", a))
        self.assertEqual([e["event_id"] for e in history.history(self.s.con, a)], before)
        self.assertTrue(step)

    def test_the_log_says_the_pair_and_the_words_name_the_item(self):
        a = self.demo.action()
        step = self.ok(eye("new", a))["apply_id"]
        keys = {r["key"] for r in self.s.step_rows(step)}
        self.assertEqual(keys, {f"ABC|{a}"})
        self.assertEqual(changes.words([{"ref": f"ABC|{a}", "field": None, "change": "removed", "to": None}], [], {}),
                         f"Put back: {a} is back in the report.")
        left = changes.words([], [{"ref": f"ABC|{a}", "field": None, "why": changes.CHANGED_LATER, "by_step": None}], {})
        self.assertEqual(left, f"Nothing was put back. {a} was changed later, so it was left as it is.")

    def test_a_hidden_row_is_absent_from_what_publish_selects_and_back_after_undo(self):
        a = self.demo.action(description="ZQ-HIDE-ME-9")
        keep = self.demo.action(description="ZQ-KEEP-ME-9")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"client_visible": 1})
            st.update("actions", keep, {"client_visible": 1})

        def ids():
            return [r["id"] for r in publish.select(publish.read_inputs(self.s, "ABC", "2026-10-29"))["data"]["actions"]]
        self.assertEqual(ids(), [a, keep])
        step = self.ok(eye("new", a))["apply_id"]
        self.assertEqual(ids(), [keep])
        self.back(step)
        self.assertEqual(ids(), [a, keep])

    def test_an_archived_item_can_still_be_hidden_and_shown(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", a)
        self.ok(eye("new", a))
        self.ok(eye("delete", a))

    def test_the_reply_carries_ids_only(self):
        a = self.demo.action(description="SECRET-TEXT-1")
        body = self.ok(eye("new", a))
        self.assertNotIn("SECRET-TEXT-1", repr(body))
        self.assertEqual(set(body), {"ok", "apply_id", "ref", "hidden"})


def pick(*ids, project="ABC"):
    return {"project": project, "kind": "report_hidden", "op": "pick", "ids": list(ids)}


class Picker(Base):
    def label(self, item, name):
        with self.s.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": item, "label": name})

    def visible(self, table, item):
        return self.s.read(table, ref=item)["client_visible"]

    def test_an_add_removes_the_hidden_row_and_turns_the_client_flag_on_in_one_step_with_one_undo(self):
        hidden_only, off_only, both = self.demo.action(), self.demo.action(), self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.update("actions", off_only, {"client_visible": 0})
            st.update("actions", both, {"client_visible": 0})
            st.create("report_hidden", {"project": "ABC", "item_id": hidden_only})
            st.create("report_hidden", {"project": "ABC", "item_id": both})
        body = self.ok(pick(hidden_only, off_only, both))
        self.assertEqual((body["added"], body["shown_to_client"], body["hidden"]), ([hidden_only, off_only, both], [off_only, both], []))
        self.assertEqual([self.visible("actions", i) for i in (hidden_only, off_only, both)], [1, 1, 1])
        fields = sorted((r["table"], r["field"]) for r in self.s.step_rows(body["apply_id"]) if r["field"] not in ("updated_at", "note"))
        self.assertEqual(fields, [("actions", "client_visible")] * 2 + [("report_hidden", "(removed)")] * 2)       # all in the one step
        status, out = self.back(body["apply_id"])
        self.assertEqual((status, out["skipped"], out["hidden"]), (200, [], [hidden_only, both]), out)
        self.assertEqual([self.visible("actions", i) for i in (hidden_only, off_only, both)], [1, 0, 0])
        self.assertEqual(out["words"], "Put back: 4 changes to the work items.")       # more than three lines are counted

    def test_the_words_of_an_undo_of_an_add_say_both_halves(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"client_visible": 0})
            st.create("report_hidden", {"project": "ABC", "item_id": a})
        status, out = self.back(self.ok(pick(a))["apply_id"])
        self.assertEqual(out["words"], f"Put back: {a} is hidden from the client again; {a} is hidden from the report again.")

    def test_a_row_added_this_way_is_in_what_publish_selects_and_gone_again_after_undo(self):
        a = self.demo.action(description="ZQ-PICK-ME-9")
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"client_visible": 0})
            st.create("report_hidden", {"project": "ABC", "item_id": a})

        def ids():
            return [r["id"] for r in publish.select(publish.read_inputs(self.s, "ABC", "2026-10-29"))["data"]["actions"]]
        self.assertEqual(ids(), [])
        step = self.ok(pick(a))["apply_id"]
        self.assertEqual(ids(), [a])
        self.back(step)
        self.assertEqual(ids(), [])

    def test_an_off_but_not_hidden_row_is_added_and_undone_for_an_action_and_a_milestone(self):
        a = self.demo.action(description="ZQ-OFF-ONLY-9")
        m = self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"client_visible": 0})
            st.update("milestones", m, {"client_visible": 0})

        def published():
            data = publish.select(publish.read_inputs(self.s, "ABC", "2026-10-29"))["data"]
            return sorted([r["id"] for r in data["actions"]] + [r["id"] for r in data["milestones"]])
        for item, table in ((a, "actions"), (m, "milestones")):
            self.assertNotIn(item, published())
            body = self.ok(pick(item))
            self.assertEqual((self.visible(table, item), item in published()), (1, True))
            status, out = self.back(body["apply_id"])
            self.assertEqual(status, 200, out)
            self.assertEqual((self.visible(table, item), item in published(), self.hidden()), (0, False, []))

    def test_every_kind_of_row_can_be_added(self):
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "raised": "2026-10-01",
                                   "source": "demo", "impact": "High", "likelihood": "Low"})
            d = st.create("decisions", {"project": "ABC", "decision": "Use the cloud", "source": "demo", "status": "Made",
                                        "date": "2026-10-02"})
            a = st.create("actions", {"project": "ABC", "description": "Plan", "raised": "2026-10-01", "source": "demo"})
        rows = [(a, "actions"), (r, "raid"), (d, "decisions"), (self.demo.milestone, "milestones"), (self.demo.use_case, "use_cases")]
        with self.s.step("dashboard", USER) as st:
            for item, table in rows:
                st.update(table, item, {"client_visible": 0})
                st.create("report_hidden", {"project": "ABC", "item_id": item})
        body = self.ok(pick(*[i for i, _ in rows]))
        self.assertEqual((body["hidden"], body["shown_to_client"]), ([], [i for i, _ in rows]))
        self.assertEqual([self.visible(t, i) for i, t in rows], [1] * 5)
        self.assertEqual(self.back(body["apply_id"])[0], 200)
        self.assertEqual([self.visible(t, i) for i, t in rows], [0] * 5)
        self.assertEqual(len(self.hidden()), 5)

    def test_a_sensitive_item_is_refused_and_nothing_is_written(self):
        ok_row, secret = self.demo.action(), self.demo.action()
        with self.s.step("dashboard", USER) as st:
            for item in (ok_row, secret):
                st.create("report_hidden", {"project": "ABC", "item_id": item})
        self.label(secret, "Sensitive")
        self.refused(pick(ok_row, secret), changes.PICK_SENSITIVE)
        self.assertEqual(self.hidden(), sorted([ok_row, secret]))

    def test_the_spelling_and_other_excluding_labels_count_too(self):
        a, b, c = self.demo.action(), self.demo.action(), self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("labels", {"name": "Embargoed", "default_choice": "exclude"})
            st.create("labels", {"name": "Commercial", "behaviour": "exclude"})
            st.create("labels", {"name": "Draft", "behaviour": "warn"})
            for item in (a, b, c):
                st.create("report_hidden", {"project": "ABC", "item_id": item})
        self.label(a, "Embargoed")
        self.label(b, "Commercial")
        self.refused(pick(a), changes.PICK_SENSITIVE)
        self.refused(pick(b), changes.PICK_SENSITIVE)
        self.label(c, "Draft")
        self.ok(pick(c))
        with self.s.step("dashboard", USER) as st:
            st.cancel("item_labels", f"{c}|Draft")

    def test_a_row_that_is_already_on_the_page_is_refused_whole(self):
        shown, hidden = self.demo.action(), self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": hidden})
        self.refused(pick(hidden, shown), changes.PICK_NOT_HIDDEN)
        self.assertEqual(self.hidden(), [hidden])

    def test_the_request_is_checked_before_anything_is_written(self):
        a = self.demo.action()
        other = self.other_project()
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": a})
        self.refused(pick(a, other), changes.ITEM_NOT_MINE)
        self.refused(pick(a, "ABC-A-999"), changes.ITEM_NOT_MINE)
        self.refused(pick(a, "<b>x</b>"), changes.ITEM_NOT_MINE)
        self.refused(pick(a, 5), changes.ITEM_NOT_MINE)
        self.refused(pick(a, None), changes.ITEM_NOT_MINE)
        self.refused(pick(), changes.PICK_NOTHING)
        self.refused({**pick(a), "ids": "ABC-A-001"}, changes.PICK_NOTHING)
        self.refused({**pick(a), "ids": {"a": 1}}, changes.PICK_NOTHING)
        self.refused({"project": "ABC", "kind": "report_hidden", "op": "pick"}, changes.PICK_NOTHING)
        self.refused(pick(*[f"ABC-A-{n:03d}" for n in range(1, changes.MAX_PICK + 2)]), changes.PICK_TOO_MANY)
        self.refused({**pick(a), "id": a}, "That change doesn't take 'id'.")
        self.refused({**pick(a), "values": {}}, "That change doesn't take 'values'.")
        self.assertEqual(self.hidden(), [a])

    def test_an_archived_item_is_refused(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": a})
            st.archive("actions", a)
        self.refused(pick(a), changes.PICK_ARCHIVED)

    def test_another_projects_row_is_never_changed(self):
        other = self.other_project()
        with self.s.step("dashboard", USER) as st:
            st.update("actions", other, {"client_visible": 0})
        self.refused(pick(other), changes.ITEM_NOT_MINE)
        self.assertEqual(self.visible("actions", other), 0)
        self.refused(pick(other, project="XYZ") | {"ids": [self.demo.action()]}, changes.ITEM_NOT_MINE)

    def test_a_repeated_id_is_added_once(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": a})
        body = self.ok(pick(a, a, a))
        self.assertEqual(body["added"], [a])

    def test_undo_when_one_row_changed_later_puts_back_the_rest_and_names_it(self):
        a, b = self.demo.action(), self.demo.action()
        with self.s.step("dashboard", USER) as st:
            for item in (a, b):
                st.update("actions", item, {"client_visible": 0})
                st.create("report_hidden", {"project": "ABC", "item_id": item})
        step = self.ok(pick(a, b))["apply_id"]
        self.demo.update("actions", b, {"client_visible": 0})                 # changed later, by another route
        status, out = self.back(step)
        self.assertEqual(status, 200, out)
        self.assertEqual((self.visible("actions", a), self.visible("actions", b), self.hidden()), (0, 0, sorted([a, b])))
        self.assertIn(f"{b} was changed later", out["words"])
        self.assertIn(f"{a} is hidden from the client again", out["words"])

    def test_an_undo_is_not_offered_for_a_step_that_only_turned_a_client_flag_on_from_another_route(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"client_visible": 0})
        with self.s.step("excel", USER) as st:               # #97: from the page the eye is a work item's own field (test_changes_item_eye), so only another route's step is refused
            st.update("actions", a, {"client_visible": 1})
        status, out = self.back(self.demo.last_step())
        self.assertEqual((status, out["message"]), (400, changes.NO_UNDO))

    def test_a_picker_step_cannot_be_undone_from_another_project(self):
        a = self.demo.action()
        self.other_project()
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": a})
        step = self.ok(pick(a))["apply_id"]
        status, out = self.undo({"project": "XYZ", "apply_id": step})
        self.assertEqual((status, out["message"]), (400, changes.NO_UNDO))

    def test_the_picker_step_leaves_a_work_items_activity_with_its_own_flag_change_only(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"client_visible": 0})
            st.create("report_hidden", {"project": "ABC", "item_id": a})
        before = len(history.history(self.s.con, a))
        self.ok(pick(a))
        events = history.history(self.s.con, a)
        self.assertEqual([(e["table"], e["field"], e["after"]) for e in events[:len(events) - before]], [("actions", "client_visible", "1")])


TITLE = {"actions": "description", "raid": "description", "decisions": "decision"}


class Titles(Base):
    def setUp(self):
        super().setUp()
        self.a = self.demo.action(description="Draft the plan")
        with self.s.step("dashboard", USER) as st:
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                        "likelihood": "Medium", "raised": "2026-10-01", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending",
                                             "needed_by": "2030-01-05", "source": "demo"})
        self.ids = {"actions": self.a, "raid": self.r, "decisions": self.d}

    def edit(self, kind, ref, value, project="ABC"):
        return {"project": project, "kind": kind, "op": "update", "id": ref, "changes": {TITLE[kind]: value}, "place": "cell"}

    def title(self, kind):
        return self.s.read(kind, ref=self.ids[kind])[TITLE[kind]]

    def test_each_kind_changes_its_title_in_one_step_and_undo_puts_it_back(self):
        for kind, ref in self.ids.items():
            with self.subTest(kind=kind):
                was = self.title(kind)
                body = self.ok(self.edit(kind, ref, "  A new title  "))
                self.assertEqual(self.title(kind), "A new title")
                self.assertTrue(body["undoable"])
                self.assertEqual({r["key"] for r in self.s.step_rows(body["apply_id"])}, {ref})
                status, out = self.back(body["apply_id"])
                self.assertEqual((status, self.title(kind)), (200, was), out)
                self.assertEqual(out["words"], f"Put back: the title of {ref} is back as it was.")

    def test_the_reply_never_says_the_title_back(self):
        body = self.ok(self.edit("actions", self.a, "ZQ-TITLE-SECRET-1"))
        self.assertNotIn("ZQ-TITLE-SECRET-1", repr(body))
        self.assertNotIn("description", body["item"])

    def test_the_title_is_nfc_and_markup_stays_text(self):
        self.ok(self.edit("actions", self.a, "Cafe\u0301 <b>x</b> & more"))
        self.assertEqual(self.title("actions"), "Caf\u00e9 <b>x</b> & more")

    def test_a_title_that_is_not_plain_text_is_refused_and_nothing_is_written(self):
        for bad in ("", "   ", None, 5, ["x"], {"a": 1}, True, "x" * 201, "two\nlines", "tab\there", "nul\x00", "bidi\u202eevil",
                    "zero\u200bwidth", "lone\ud800", "sep\u2028x", "private\ue000"):
            for kind, ref in self.ids.items():
                with self.subTest(kind=kind, bad=bad):
                    before = self.snapshot()
                    status, body = self.change(self.edit(kind, ref, bad))
                    self.assertEqual((status, body["ok"]), (400, False), body)
                    self.assertIn(body["message"], (changes.ITEM_VALUE_WORDS, changes.ITEM_TEXT_WORDS))
                    self.assertEqual(self.snapshot(), before)
        self.assertEqual([self.title(k) for k in self.ids], ["Draft the plan", "Supplier slips", "Use the new tool"])

    def test_200_characters_is_the_most(self):
        self.ok(self.edit("actions", self.a, "x" * 200))

    def test_another_projects_item_and_a_missing_one_get_the_same_words(self):
        other = self.other_project()
        self.refused(self.edit("actions", other, "Hijack"), changes.ITEM_NOT_MINE)
        self.refused(self.edit("actions", "ABC-A-099", "Hijack"), changes.ITEM_NOT_MINE)
        self.refused(self.edit("actions", None, "Hijack"), changes.ITEM_NOT_MINE)
        self.refused(self.edit("actions", self.a, "Hijack", project="XYZ"), changes.ITEM_NOT_MINE)
        self.assertEqual(self.s.read("actions", ref=other)["description"], "Order the licences")

    def test_an_archived_item_is_not_edited(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.a)
        self.refused(self.edit("actions", self.a, "New"), changes.ITEM_NOT_MINE)

    def test_the_wrong_kinds_field_is_refused(self):
        self.refused({"project": "ABC", "kind": "actions", "op": "update", "id": self.a, "changes": {"decision": "x"}},
                     "The field 'decision' can't be set here.")
        self.refused({"project": "ABC", "kind": "decisions", "op": "update", "id": self.d, "changes": {"description": "x"}},
                     "The field 'description' can't be set here.")
        self.refused({"project": "ABC", "kind": "raid", "op": "update", "id": self.r, "changes": {"title": "x"}},
                     "The field 'title' can't be set here.")

    def test_a_title_and_other_fields_in_one_request_are_one_step(self):
        body = self.ok({"project": "ABC", "kind": "actions", "op": "update", "id": self.a,
                        "changes": {"description": "Both", "owner": "Sam Example"}})
        self.assertEqual(self.back(body["apply_id"])[0], 200)
        row = self.s.read("actions", ref=self.a)
        self.assertEqual((row["description"], row["owner"]), ("Draft the plan", "TBC"))

    def test_a_title_changed_later_is_skipped_and_named(self):
        body = self.ok(self.edit("actions", self.a, "First"))
        self.demo.update("actions", self.a, {"description": "Second"})
        status, out = self.back(body["apply_id"])
        self.assertEqual((status, out["reversed"], self.title("actions")), (200, [], "Second"))
        self.assertIn(f"{self.a} was changed later", out["words"])

    def test_the_same_title_writes_nothing(self):
        before = self.snapshot()
        body = self.ok(self.edit("actions", self.a, "Draft the plan"))
        self.assertEqual((body["apply_id"], body["undoable"], self.snapshot()), (None, False, before))

    def test_a_closed_items_title_can_be_edited_and_its_dates_are_left(self):
        self.ok({"project": "ABC", "kind": "actions", "op": "update", "id": self.a, "changes": {"status": "Closed"}})
        closed = self.s.read("actions", ref=self.a)["closed"]
        self.ok(self.edit("actions", self.a, "Renamed after closing"))
        self.assertEqual(self.s.read("actions", ref=self.a)["closed"], closed)

    def test_a_title_edit_is_in_that_items_own_history(self):
        before = len(history.history(self.s.con, self.a))
        self.ok(self.edit("actions", self.a, "Seen in Activity"))
        events = history.history(self.s.con, self.a)
        self.assertEqual([(e["table"], e["field"], e["after"]) for e in events[:len(events) - before]],
                         [("actions", "description", "Seen in Activity")])


def add(kind, **values):
    return {"project": "ABC", "kind": kind, "op": "new", "values": values, "place": "report"}


class Inserts(Base):
    def count(self, table, project="ABC"):
        return len(self.s.read(table, project))

    def test_each_kind_adds_one_row_in_one_step_and_undo_removes_it(self):
        cases = (("actions", {"description": "Book the room"}), ("raid", {"type": "Risk", "description": "Supplier slips"}),
                 ("decisions", {"decision": "Use the cloud"}), ("milestones", {"name": "Go live", "baseline_date": "2030-05-01"}))
        for kind, values in cases:
            with self.subTest(kind=kind):
                before = self.count(kind)
                body = self.ok(add(kind, **values))
                self.assertEqual(self.count(kind), before + 1)
                row = self.s.read(kind, ref=body["ref"])
                self.assertEqual((row["project"], row["archived"], row["source"]), ("ABC", 0, changes.NEW_SOURCE))
                self.assertEqual(body["item"]["id"], body["ref"])
                self.assertEqual({r["key"] for r in self.s.step_rows(body["apply_id"])}, {body["ref"]})
                status, out = self.back(body["apply_id"])
                self.assertEqual((status, out["skipped"], self.count(kind)), (200, [], before), out)
                self.assertRegex(out["words"], r"^Put back: the new (action|risk or issue|decision|milestone) ABC-.*was removed\.$")

    def test_ids_come_from_next_id_one_sequence_for_actions_risks_and_decisions_and_none_is_reused(self):
        a = self.ok(add("actions", description="One"))
        r = self.ok(add("raid", type="Issue", description="Two"))
        d = self.ok(add("decisions", decision="Three"))
        m = self.ok(add("milestones", name="Four"))
        self.assertEqual([a["ref"], r["ref"], d["ref"], m["ref"]], ["ABC-A-001", "ABC-002", "ABC-D-003", "ABC-M-002"])      # the demo store has ABC-M-001
        self.back(d["apply_id"])
        self.assertEqual(self.ok(add("actions", description="Five"))["ref"], "ABC-A-004", "a number once used is not used again")

    def test_another_projects_numbers_are_its_own(self):
        other = self.other_project()
        self.assertEqual(other, "XYZ-A-001")
        body = self.ok(add("actions", description="Mine"))
        self.assertEqual(body["ref"], "ABC-A-001")
        status, body = self.change({**add("actions", description="Theirs"), "project": "XYZ"})
        self.assertEqual((status, body["ref"]), (200, "XYZ-A-002"))
        self.assertEqual(self.count("actions", "ABC"), 1)

    def test_the_day_it_was_raised_and_the_open_status_are_clarks(self):
        body = self.ok(add("actions", description="Open"))
        self.assertEqual((body["item"]["status"], body["item"]["raised"]), ("Open", store_module.today()))
        body = self.ok(add("raid", type="Risk", description="A risk", impact="High", likelihood="High"))
        self.assertEqual((body["item"]["priority"], body["item"]["status"]), ("Urgent", "Open"))
        for field, value in (("raised", "2020-01-01"), ("source", "somewhere"), ("project", "XYZ"), ("id", "ABC-A-099"),
                             ("status", "Closed"), ("archived", 1), ("closed", "2026-10-01"),
                             ("client_message", "x"), ("internal_note", "x"), ("updated_at", "x")):
            with self.subTest(field=field):
                words = changes.NO_ARCHIVE if field == "archived" else f"The field '{field}' can't be set here."
                self.refused(add("actions", description="X", **{field: value}), words)
        self.refused(add("raid", type="Risk", description="X", priority="Low"), changes.NO_RAID_PRIORITY)

    def test_a_decision_is_pending_unless_it_is_made_and_a_made_one_needs_its_date(self):
        pending = self.ok(add("decisions", decision="Wait"))
        self.assertEqual((pending["item"]["status"], pending["item"]["date"]), ("Pending", None))
        made = self.ok(add("decisions", decision="Done", status="Made", date="2026-10-02"))
        self.assertEqual(made["item"]["status"], "Made")
        self.refused(add("decisions", decision="No date", status="Made"), changes.DECISION_NEEDS_DATE)
        self.refused(add("decisions", decision="Dated pending", status="Pending", date="2026-10-02"), changes.DECISION_NOT_MADE)

    def test_what_is_needed_is_said_in_plain_words(self):
        self.refused(add("actions"), changes.NEW_NEEDS["actions"])
        self.refused(add("actions", owner="Sam Example"), changes.NEW_NEEDS["actions"])
        self.refused(add("raid", description="No type"), changes.NEW_NEEDS["raid"])
        self.refused(add("raid", type="Risk"), changes.NEW_NEEDS["raid"])
        self.refused(add("decisions", made_by="Sam Example"), changes.NEW_NEEDS["decisions"])
        self.refused(add("milestones", baseline_date="2030-01-01"), changes.NEW_NEEDS["milestones"])
        self.refused({"project": "ABC", "kind": "actions", "op": "new"}, changes.NEW_NEEDS["actions"])
        self.refused({"project": "ABC", "kind": "actions", "op": "new", "values": None}, changes.NEW_NEEDS["actions"])

    def test_text_is_plain_and_clean_like_other_text(self):
        for kind, field, extra in (("actions", "description", {}), ("raid", "description", {"type": "Risk"}), ("decisions", "decision", {}),
                                   ("milestones", "name", {})):
            for bad in ("", "   ", 5, ["x"], {"a": 1}, True, "x" * 201, "two\nlines", "nul\x00", "bidi\u202eevil", "zero\u200bwidth",
                        "lone\ud800", "sep\u2028x", "private\ue000"):
                with self.subTest(kind=kind, bad=bad):
                    before = self.snapshot()
                    status, body = self.change(add(kind, **{field: bad}, **extra))
                    self.assertEqual((status, body["ok"]), (400, False), body)
                    self.assertIn(body["message"], (changes.ITEM_VALUE_WORDS, changes.ITEM_TEXT_WORDS, changes.NEW_NEEDS[kind]))
                    self.assertEqual(self.snapshot(), before)
        body = self.ok(add("actions", description="  Cafe\u0301 <b>x</b> & more  "))
        self.assertEqual(self.s.read("actions", ref=body["ref"])["description"], "Caf\u00e9 <b>x</b> & more")

    def test_a_field_sent_as_null_that_needs_a_value_is_refused(self):
        for field in ("owner", "priority"):
            self.refused(add("actions", description="X", **{field: None}), changes.ITEM_VALUE_WORDS)
        self.refused(add("raid", type=None, description="X"), changes.ITEM_VALUE_WORDS)
        self.ok(add("actions", description="Fine", due_date=None, workstream=None, milestone=None))

    def test_a_closed_set_takes_only_its_words_and_never_says_what_was_sent(self):
        for request in (add("actions", description="X", priority="Whenever"), add("raid", type="Opportunity", description="X"),
                        add("raid", type="Risk", description="X", impact="Huge"), add("raid", type="Risk", description="X", likelihood="Maybe"),
                        add("decisions", decision="X", status="Maybe")):
            with self.subTest(request=request):
                status, body = self.change(request)
                self.assertEqual((status, body["message"]), (400, changes.NOT_A_CHOICE))
        self.assertEqual(self.snapshot()[4:7], (0, 0, 0))

    def test_the_stores_rules_come_back_in_fixed_words_with_nothing_written(self):
        other_ms = None
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
            other_ms = st.create("milestones", {"project": "XYZ", "name": "Theirs", "baseline_date": "2030-01-01", "source": "demo"})
        for request, words in ((add("actions", description="X", due_date="2026-02-31"), changes.NOT_A_DATE),
                               (add("actions", description="X", due_date="soon"), changes.NOT_A_DATE),
                               (add("actions", description="X", workstream="Nowhere"), changes.NO_WORKSTREAM),
                               (add("actions", description="X", milestone=other_ms), changes.NO_MILESTONE),
                               (add("actions", description="X", milestone="ABC-M-099"), changes.NO_MILESTONE),
                               (add("milestones", name="X", baseline_date="not a date"), changes.NOT_A_DATE),
                               (add("milestones", name="X", workstream="Nowhere"), changes.NO_WORKSTREAM)):
            with self.subTest(request=request):
                self.refused(request, words)
        self.ok(add("actions", description="Fine", workstream="Build", milestone=self.demo.milestone, due_date="2030-01-31"))

    def test_the_alien_shapes_are_refused(self):
        self.refused({**add("actions", description="X"), "after": None}, "That change doesn't take 'after'.")
        self.refused({**add("actions", description="X"), "id": "ABC-A-001"}, "That change doesn't take 'id'.")
        self.refused(add("actions", description="X") | {"values": "text"}, "Send the new row's values as an object.")
        self.refused(add("actions", description="X") | {"values": ["x"]}, "Send the new row's values as an object.")
        self.refused(add("use_cases", title="X", headline="Y"), changes.BAD_OP)
        self.refused(add("documents", title="X"), changes.BAD_OP)
        self.refused(add("workstreams", name="X"), changes.BAD_KIND)
        self.refused(add("report_hidden"), "That change doesn't take 'values'.")
        self.assertEqual(self.s.read("use_cases", "ABC")[0]["title"], "Invoice matching")
        self.assertEqual(len(self.s.read("use_cases", "ABC")), 1, "no create path for use cases")

    def test_a_new_row_that_was_changed_later_is_not_removed_by_its_undo(self):
        body = self.ok(add("actions", description="Soon changed"))
        self.demo.update("actions", body["ref"], {"owner": "Sam Example"})
        status, out = self.back(body["apply_id"])
        self.assertEqual(status, 200)
        self.assertEqual((out["reversed"], self.count("actions")), ([], 1))
        self.assertIn(f"{body['ref']} was changed later", out["words"])

    def test_a_new_row_with_a_link_to_it_is_kept_and_named(self):
        a = self.ok(add("actions", description="Blocker"))
        b = self.ok(add("actions", description="Blocked"))
        with self.s.step("dashboard", USER) as st:
            st.create("links", {"from_item": a["ref"], "to_item": b["ref"], "source": "demo"})
        status, out = self.back(a["apply_id"])
        self.assertEqual((status, self.count("actions")), (200, 2))
        self.assertEqual(out["reversed"], [])

    def test_the_reply_is_the_new_row_and_nothing_else(self):
        body = self.ok(add("raid", type="Risk", description="SECRET-FOR-REPLY-1", impact="High"))
        self.assertEqual(set(body), {"ok", "apply_id", "ref", "item"})
        self.assertEqual(set(body["item"]), {"id", "type", "owner", "impact", "likelihood", "due_date", "workstream",
                                             "milestone", "raised", "status", "priority"})      # a title is never said back
        self.assertNotIn("SECRET-FOR-REPLY-1", repr(body))
        for kind, values in (("actions", {"description": "SECRET-A"}), ("decisions", {"decision": "SECRET-D"}),
                             ("milestones", {"name": "SECRET-M", "baseline_date": "2030-05-01"})):
            self.assertNotIn("SECRET", repr(self.ok(add(kind, **values))), kind)

    def test_a_new_row_is_in_its_own_history_and_hiding_it_is_a_separate_step(self):
        body = self.ok(add("actions", description="Hide me too"))
        events = history.history(self.s.con, body["ref"])
        self.assertEqual({e["step"] for e in events}, {body["apply_id"]})
        self.assertEqual(self.ok(eye("new", body["ref"]))["hidden"], [body["ref"]])


class Family(Base):
    """The reviewers' LOW findings: another project's code, words for a use case, an archived project."""

    def archive_project(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")

    def test_hiding_an_item_of_abcd_cannot_be_undone_by_abc(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABCD", "name": "Fourth Programme", "health": "On track"})
            other = st.create("actions", {"project": "ABCD", "description": "Order", "raised": "2026-10-01", "source": "demo"})
        step = self.ok(eye("new", other, project="ABCD"))["apply_id"]
        status, out = self.back(step, project="ABC")
        self.assertEqual((status, out["message"]), (400, changes.NO_UNDO))
        self.assertEqual(sorted(r["item_id"] for r in self.s.read("report_hidden", "ABCD")), [other])
        rows = self.s.step_rows(step)
        self.assertFalse(changes._eligible(rows, "ABC"))
        self.assertTrue(changes._eligible(rows, "ABCD"))

    def test_the_words_for_a_use_case_in_a_pick_name_it(self):
        u = self.demo.use_case
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", u, {"client_visible": 0})
            st.create("report_hidden", {"project": "ABC", "item_id": u})
        status, out = self.back(self.ok(pick(u))["apply_id"])
        self.assertEqual(status, 200, out)
        # #164 words a use case by its name and its eye as the client, as main does for the other kinds
        self.assertIn("is hidden from the client again", out["words"])
        self.assertNotIn("dashboard", out["words"])
        self.assertIn(f"{u} is hidden from the report again", out["words"])
        self.assertNotIn("a record", out["words"])

    def test_more_than_three_changes_including_a_use_case_still_say_work_items(self):
        rows = [self.demo.use_case] + [self.demo.action() for _ in range(3)]
        with self.s.step("dashboard", USER) as st:
            for item in rows:
                st.update(clark_table(item), item, {"client_visible": 0})
                st.create("report_hidden", {"project": "ABC", "item_id": item})
        status, out = self.back(self.ok(pick(*rows))["apply_id"])
        self.assertEqual(status, 200, out)
        self.assertIn("changes to the work items", out["words"])

    def test_an_archived_project_refuses_show_hide_pick_and_new_and_writes_nothing(self):
        a, hidden_one = self.demo.action(), self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": hidden_one})
        self.archive_project()
        for request in (eye("new", a), eye("delete", hidden_one), pick(hidden_one), add("actions", description="Late"),
                        add("raid", type="Risk", description="Late"), add("decisions", decision="Late"),
                        add("milestones", name="Late", baseline_date="2030-01-01")):
            with self.subTest(request=request):
                self.refused(request, changes.PROJECT_NOT_ACTIVE)

    def test_a_new_row_with_an_archive_flag_or_a_risk_priority_gets_the_plain_words(self):
        self.refused(add("actions", description="X", archived=1), changes.NO_ARCHIVE)
        self.refused(add("raid", type="Risk", description="X", priority="Low"), changes.NO_RAID_PRIORITY)

    def test_undoing_an_insert_that_something_refers_to_says_it_is_linked(self):
        m = self.ok(add("milestones", name="Go live", baseline_date="2030-05-01"))
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"milestone": m["ref"]})
        status, out = self.back(m["apply_id"])
        self.assertEqual(status, 200, out)
        self.assertEqual([s["why"] for s in out["skipped"]], [changes.LINKED_NOW])


def clark_table(item):
    return store_module.item_table(item)


class Allowed(Base):
    def test_the_allow_list_has_the_eye_and_it_is_undoable(self):
        self.assertEqual(set(changes.CHANGE_KINDS["report_hidden"]), {"new", "delete", "pick"})
        for op in ("new", "delete", "pick"):
            self.assertEqual(changes.CHANGE_KINDS["report_hidden"][op], ())
        self.assertIn("report_hidden", changes.UNDOABLE)
        self.assertEqual(changes.UNDOABLE["report_hidden"], None)
        self.assertIn("report_hidden", store_module.TABLES)


if __name__ == "__main__":
    unittest.main()

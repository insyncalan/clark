"""#47e part 1: ask clark's dry run and Apply (src/clark/ask_apply.py, and changes.make_ask_change; guarded).

Run: python3 dev/run_tests.py test_ask_apply
Each test makes a real store in a temporary folder (fictional data). A suggestion is what ask.read_reply returns as a change.
"""
import ast
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC
from clark import ask, ask_apply, changes, history, store as store_module


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.path = self.s.path
        with self.s.step("dashboard", USER) as st:              # a second project, which ask clark must never reach
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            self.other = st.create("actions", {"project": "XYZ", "description": "Order the badges", "owner": "Kit Moss",
                                               "raised": "2026-10-01", "source": "demo"})
        self.action = self.demo.action(owner="Sam Lee")
        self.ask = ask_apply.AskApply(self.path, [], USER)
        self.undo = changes.make_undo(self.path, [], USER)

    def counts(self):
        con = sqlite3.connect(str(self.path))
        try:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log", "item_events"))
        finally:
            con.close()

    def planned(self, change, **kw):
        status, body = self.ask.plan("ABC", change, **kw)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def applied(self, offer, **kw):
        status, body = self.ask.apply(offer, "ABC", **kw)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def refused(self, change, code, **kw):
        before = self.counts()
        status, body = self.ask.plan("ABC", change, **kw)
        self.assertEqual((body["ok"], body["code"]), (False, code), body)
        self.assertGreaterEqual(status, 400)
        self.assertIn("nothing was changed", body["message"].lower())
        self.assertEqual(self.counts(), before, "nothing was written")
        return body

    def set_switch(self, on):
        with self.s.step("dashboard", USER) as st:
            st.update("app_settings", "1", {"ask_enabled": on})

    def ask_events(self, ref):
        return [e for e in self.s.history(ref) if e["route"] == "assistant"]


class WorkItems(Base):
    def test_create_an_action_dry_run_then_apply_then_undo(self):
        before = self.counts()
        plan = self.planned({"op": "new", "kind": "action", "title": "Book the training room", "owner": "Sam Lee"})
        self.assertEqual(self.counts(), before, "a dry run saves nothing")
        self.assertIsNone(plan["before"])
        self.assertEqual(plan["after"]["description"], "Book the training room")
        self.assertEqual(plan["after"]["status"], "Open")                  # the store's default, not the suggestion's
        done = self.applied(plan["offer"])
        ref = done["ref"]
        self.assertEqual(self.s.read("actions", ref=ref)["description"], "Book the training room")
        events = self.ask_events(ref)
        self.assertTrue(events)
        self.assertTrue(all(e["actor"] == "clark" for e in events))
        self.assertEqual(history.how_text("assistant", None, None), history.HOW_ASK)
        self.assertIn("ask clark", history.HOW_ASK)
        self.assertEqual(len({e["step"] for e in events}), 1, "one Apply is one step")
        status, body = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.s.read("actions", ref=ref))

    def test_change_an_action_and_undo_puts_the_old_values_back(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan",
                             "current_owner": "Sam Lee", "owner": "Ana Ruiz", "due": "2030-01-15"})
        self.assertEqual((plan["before"]["owner"], plan["after"]["owner"]), ("Sam Lee", "Ana Ruiz"))
        self.assertEqual(sorted(plan["fields"]), ["due_date", "owner"])
        done = self.applied(plan["offer"])
        self.assertTrue(done["undoable"])
        row = self.s.read("actions", ref=self.action)
        self.assertEqual((row["owner"], row["due_date"]), ("Ana Ruiz", "2030-01-15"))
        self.assertTrue(all(e["actor"] == "clark" for e in self.ask_events(self.action)))
        status, body = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, body)
        row = self.s.read("actions", ref=self.action)
        self.assertEqual((row["owner"], row["due_date"]), ("Sam Lee", None))

    def test_an_offer_is_used_once(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.applied(plan["offer"])
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "no_offer"))

    def test_an_offer_is_for_its_own_project_only(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        before = self.counts()
        status, body = self.ask.apply(plan["offer"], "XYZ")
        self.assertEqual((status, body["code"]), (409, "no_offer"))
        self.assertEqual(self.counts(), before)


class Milestones(Base):
    def test_create_a_milestone_and_undo(self):
        plan = self.planned({"op": "new", "kind": "milestone", "title": "Go live", "agreed_date": "2030-06-01"})
        self.assertEqual(plan["after"]["baseline_date"], "2030-06-01")
        done = self.applied(plan["offer"])
        self.assertEqual(self.s.read("milestones", ref=done["ref"])["name"], "Go live")
        self.assertTrue(self.ask_events(done["ref"]))
        status, body = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.s.read("milestones", ref=done["ref"]))

    def test_change_a_milestone_and_undo(self):
        ref = self.demo.milestone
        plan = self.planned({"op": "change", "id": ref, "current_title": "Pilot live", "forecast_date": "2030-04-01"})
        self.assertEqual((plan["before"]["forecast_date"], plan["after"]["forecast_date"]), (None, "2030-04-01"))
        done = self.applied(plan["offer"])
        self.assertEqual(self.s.read("milestones", ref=ref)["forecast_date"], "2030-04-01")
        self.assertTrue(all(e["actor"] == "clark" for e in self.ask_events(ref)))
        status, body = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.s.read("milestones", ref=ref)["forecast_date"])

    def test_the_agreed_date_is_not_moved_by_asking(self):
        self.refused({"op": "change", "id": self.demo.milestone, "agreed_date": "2031-01-01"}, "field_not_allowed")


class Forged(Base):
    def test_a_wrong_title_is_refused(self):
        body = self.refused({"op": "change", "id": self.action, "current_title": "Pay the supplier", "status": "Closed"}, "wrong_title")
        self.assertIn(self.action, body["message"])

    def test_a_wrong_owner_is_refused(self):
        self.refused({"op": "change", "id": self.action, "current_owner": "Kit Moss", "status": "Closed"}, "wrong_owner")

    def test_a_title_matches_however_it_is_spaced_or_cased(self):
        self.planned({"op": "change", "id": self.action, "current_title": "  draft THE cut-over   plan ", "status": "Closed"})

    def test_an_unknown_id_is_refused(self):
        self.refused({"op": "change", "id": "ABC-A-099", "status": "Closed"}, "unknown_id")

    def test_another_projects_item_is_refused(self):
        self.refused({"op": "change", "id": self.other, "status": "Closed"}, "other_project")
        self.refused({"op": "new", "kind": "action", "title": "Book a room", "project": "XYZ"}, "other_project")
        self.assertEqual(self.s.read("actions", ref=self.other)["status"], "Open")

    def test_a_field_not_allowed_is_refused_by_name(self):
        for name in ("internal_note", "client_visible", "use_case", "archived_at", "sort_order", "priority_score"):
            body = self.refused({"op": "change", "id": self.action, name: "x"}, "field_not_allowed")
            self.assertIn(ask_apply._plain_name(name), body["message"])

    def test_the_id_and_kind_must_agree(self):
        self.refused({"op": "change", "kind": "milestone", "id": self.action, "status": "Closed"}, "wrong_kind")

    def test_a_shape_that_isnt_the_form_is_refused(self):
        for change in ({}, {"op": "change"}, {"op": "new", "title": "x"}, {"op": "rewrite", "id": self.action},
                       {"op": "new", "kind": "action", "id": self.action, "title": "x"}, {"op": "change", "id": self.action, "status": 3},
                       {"op": "change", "id": self.action, "status": True}, {"op": "change", "id": self.action, "source": "file.docx", "status": "Closed"}):
            self.refused(change, "not_a_change")

    def test_a_suggestion_from_a_real_reply_is_planned(self):
        reply = ask.read_reply('Closing it.\nCHANGE: {"op": "change", "id": "%s", "status": "Closed"}' % self.action,
                               codes=("ABC",), exists=lambda ref: ref == self.action)
        self.assertEqual(len(reply.changes), 1)
        self.assertEqual(self.planned(reply.changes[0])["after"]["status"], "Closed")


class FromTheData(Base):
    def test_after_is_what_the_store_would_save_not_the_suggestion(self):
        plan = self.planned({"op": "new", "kind": "risk", "title": "  Supplier late ", "owner": "Sam Lee", "impact": "High",
                             "likelihood": "High"})
        after = plan["after"]
        self.assertEqual(after["description"], "Supplier late")             # trimmed by the hand-edit rules
        self.assertEqual(after["type"], "Risk")
        self.assertEqual(after["priority"], "Urgent")                       # worked out by the store; the suggestion had none
        self.assertEqual(after["raised"], store_module.today())
        closing = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.assertEqual(closing["after"]["closed"], store_module.today())   # set by the store's closing rule
        self.assertIsNone(closing["before"]["closed"])

    def test_before_is_read_from_the_data_not_the_claims(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.assertEqual(plan["before"]["description"], "Draft the cut-over plan")
        self.assertEqual(plan["before"]["owner"], "Sam Lee")

    def test_a_row_changed_since_the_dry_run_is_not_saved(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.demo.update("actions", self.action, {"owner": "Ana Ruiz"})
        before = self.counts()
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "changed"), body)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_a_store_rule_is_said_in_plain_words_and_nothing_is_saved(self):
        before = self.counts()
        status, body = self.ask.plan("ABC", {"op": "change", "id": self.action, "due": "not a date"})
        self.assertEqual((status, body["message"]), (400, changes.NOT_A_DATE))      # the hand edit's own words
        self.assertEqual(self.counts(), before)

    def test_nothing_to_change_is_refused(self):
        self.refused({"op": "change", "id": self.action, "owner": "Sam Lee"}, "nothing")


class TheSwitch(Base):
    def test_off_refuses_the_dry_run(self):
        self.set_switch(0)
        self.refused({"op": "change", "id": self.action, "status": "Closed"}, "asking_off")

    def test_off_blocks_apply(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.set_switch(0)
        before = self.counts()
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "asking_off"), body)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_the_switch_is_read_again_inside_the_step(self):
        """Off between the early check and BEGIN IMMEDIATE still writes nothing (the in-step read is the one that counts)."""
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        answers = iter([True, False])
        before = self.counts()
        with mock.patch.object(store_module.Store, "ask_enabled", lambda _self: next(answers, False)):
            status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "asking_off"), body)
        self.assertEqual(self.counts(), before)

    def test_a_switch_that_cant_be_read_is_off(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        with mock.patch.object(store_module.Store, "ask_enabled", lambda _self: 1):     # not exactly True
            status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual(body["code"], "asking_off")


class FromASource(Base):
    def test_a_change_from_a_passage_needs_confirm(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed", "source": "P2"})
        self.assertTrue(plan["needs_confirm"])
        before = self.counts()
        for confirm in (False, None, 1, "yes", "true"):
            status, body = self.ask.apply(plan["offer"], "ABC", confirm=confirm)
            self.assertEqual((status, body["code"]), (409, "needs_confirm"), confirm)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")
        self.applied(plan["offer"], confirm=True)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Closed")

    def test_the_caller_can_mark_it_from_a_source(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"}, from_source=True)
        self.assertTrue(plan["needs_confirm"])
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual(body["code"], "needs_confirm")

    def test_a_change_from_the_report_needs_no_confirm(self):
        plan = self.planned({"op": "change", "id": self.action, "status": "Closed"})
        self.assertFalse(plan["needs_confirm"])
        self.applied(plan["offer"])


class NotYet(Base):
    def test_archive_and_delete_are_refused_in_plain_words(self):
        for op in ("archive", "delete", "Remove", "restore"):
            body = self.refused({"op": op, "id": self.action}, "not_yet")
            self.assertIn("isn't available yet", body["message"])
        self.refused({"op": "change", "id": self.action, "archived": 1}, "not_yet")
        self.assertEqual(self.s.read("actions", ref=self.action)["archived"], 0)

    def test_more_than_five_at_once_is_refused(self):
        many = [{"op": "change", "id": self.action, "status": "Closed"}] * (ask_apply.MAX_AT_ONCE + 1)
        before = self.counts()
        status, body = self.ask.plan_all("ABC", many)
        self.assertEqual((status, body["code"]), (400, "too_many"))
        self.assertIn("isn't available yet", body["message"])
        self.assertEqual(self.counts(), before)
        status, body = self.ask.plan_all("ABC", many[:ask_apply.MAX_AT_ONCE])
        self.assertEqual(status, 200)
        self.assertEqual(len(body["plans"]), ask_apply.MAX_AT_ONCE)

    def test_the_save_path_refuses_anything_but_new_and_changed_items(self):
        ask_change = changes.make_ask_change(self.path, [], USER)
        before = self.counts()
        for req in ({"project": "ABC", "kind": "actions", "op": "archive", "id": self.action},
                    {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"title": "x"}},
                    {"project": "ABC", "kind": "projects", "op": "update", "changes": {"health": "At risk", "health_reason": "x"}},
                    {"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": {"status": "Closed"}, "place": "menu"},
                    {"project": "ABC", "kind": "milestones", "op": "update", "id": self.demo.milestone,
                     "changes": {"baseline_date": "2031-01-01"}, "rebaseline": {"reason": "x"}}):
            for dry in (True, False):
                status, body = ask_change(req, dry=dry)
                self.assertEqual((status, body["ok"]), (400, False), req)
        self.assertEqual(self.counts(), before)

    def test_the_save_path_keeps_to_the_requests_project(self):
        ask_change = changes.make_ask_change(self.path, [], USER)
        status, body = ask_change({"project": "ABC", "kind": "actions", "op": "update", "id": self.other,
                                   "changes": {"status": "Closed"}}, dry=False)
        self.assertEqual((status, body["message"]), (400, changes.ITEM_NOT_MINE))
        self.assertEqual(self.s.read("actions", ref=self.other)["status"], "Open")

    def test_the_save_path_is_dry_unless_told(self):
        ask_change = changes.make_ask_change(self.path, [], USER)
        before = self.counts()
        status, body = ask_change({"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": {"status": "Closed"}})
        self.assertEqual((status, body["dry"]), (200, True))
        status, body = ask_change({"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": {"status": "Closed"}},
                                  dry="no")
        self.assertEqual((status, body["dry"]), (200, True))
        self.assertEqual(self.counts(), before)


class Undo(Base):
    def test_a_dashboard_undo_only_takes_ask_clarks_work_item_and_milestone_steps(self):
        self.assertIn("assistant", store_module.ROUTES)
        self.assertEqual((changes.ASSISTANT, changes.ASK_ACTOR), ("assistant", "clark"))
        self.assertIn(changes.ASK_ACTOR, store_module.ACTORS)
        with self.s.step("assistant", USER, actor="clark") as st:      # an assistant step of another family is not undone from here
            st.update("projects", "ABC", {"name": "Renamed"})
        step = self.demo.last_step()
        status, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual((status, body["message"]), (400, changes.NO_UNDO))

    def test_an_assistant_step_on_a_use_case_is_not_undoable(self):
        with self.s.step("assistant", USER, actor="clark") as st:      # a use case is not one of ask clark's kinds
            st.update("use_cases", self.demo.use_case, {"headline": "Changed by ask clark"})
        step = self.demo.last_step()
        status, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual((status, body["message"]), (400, changes.NO_UNDO))
        self.assertEqual(self.s.read("use_cases", ref=self.demo.use_case)["headline"], "Changed by ask clark")


class Source(unittest.TestCase):
    """The one-writer rule for ask_apply.py: it never opens the database for writing and never makes a step itself."""

    def test_ask_apply_never_opens_the_database_for_writing(self):
        tree = ast.parse((SRC / "clark" / "ask_apply.py").read_text(encoding="utf-8"))
        readonly_connects = 0
        for n in ast.walk(tree):
            self.assertFalse(isinstance(n, ast.Name) and n.id in ("open_store", "sqlite3_connect"), getattr(n, "lineno", 0))
            self.assertFalse(isinstance(n, ast.Attribute) and n.attr in ("open_store", "step", "undo", "executescript", "execute",
                                                                         "make_change", "make_undo"), getattr(n, "lineno", 0))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "connect":
                self.assertTrue([k for k in n.keywords if k.arg == "readonly" and isinstance(k.value, ast.Constant)
                                 and k.value.value is True], n.lineno)
                readonly_connects += 1
        self.assertEqual(readonly_connects, 1)

    def test_its_only_save_is_make_ask_change(self):
        tree = ast.parse((SRC / "clark" / "ask_apply.py").read_text(encoding="utf-8"))
        made = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "changes"
                and n.attr.startswith("make_")]
        self.assertEqual([n.attr for n in made], ["make_ask_change"])


if __name__ == "__main__":
    unittest.main()

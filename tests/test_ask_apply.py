"""#47e part 1: ask clark's dry run and Apply (src/clark/ask_apply.py, and changes.make_ask_change; guarded).

Run: python3 dev/run_tests.py test_ask_apply
Each test makes a real store in a temporary folder (fictional data). A suggestion is what ask.read_reply returns as a change.
"""
import ast
import json
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC
from clark import ask, ask_apply, changes, history, store as store_module



class FoldWords(unittest.TestCase):
    def test_fold_of_nothing_is_empty_and_html_is_read_as_plain_text(self):          # #1293 A
        self.assertEqual(ask_apply._fold(None), "")
        self.assertEqual(ask_apply._fold("<p>Fix  THE   Plan</p>"), "fix the plan")


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
        self.action = self.demo.action(owner="Sam Lee", client_visible=0)      # row 1416: off the client report, so a plain Apply needs no extra tick (test_ask_client_tick_1416 has the client cases)
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
        done = self.applied(plan["offer"], confirm=True)
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

    def test_an_item_ask_clark_creates_has_the_source_added_by_ask_clark(self):      # #1009: not 'by hand'
        for kind, table, title in (("action", "actions", "Book the van"), ("milestone", "milestones", "Pilot starts")):
            plan = self.planned({"op": "new", "kind": kind, "title": title, **({"owner": "Sam Lee"} if kind == "action" else {"agreed_date": "2030-02-01"})})
            done = self.applied(plan["offer"], confirm=True)
            self.assertEqual(self.s.read(table, ref=done["ref"])["source"], changes.ASK_SOURCE)
            self.assertEqual(changes.ASK_SOURCE, "Added by ask clark")
        hand = self.demo.action(owner="Sam Lee")
        self.assertNotEqual(self.s.read("actions", ref=hand)["source"], changes.ASK_SOURCE)

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

    def test_a_plan_carries_the_items_title_and_a_plain_why(self):         # row 1292 step S4: the card's heading and its Why line
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "owner": "Ana Ruiz",
                             "why": "It was handed over on Monday.\x00 <b>x</b>"})
        self.assertEqual(plan["title"], "Draft the cut-over plan")
        self.assertEqual(plan["why"], "It was handed over on Monday. <b>x</b>", "controls dropped; the page draws it as text")
        self.assertNotIn("why", plan["after"], "why is not a field of the item")
        self.assertIsNone(self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "owner": "Kim Roe"})["why"])
        self.assertEqual(len(self.planned({"op": "change", **self.cur(self.action, "actions"), "owner": "Lee Poe", "why": "x" * 900})["why"]), ask_apply.MAX_WHY)
        self.assertEqual(ask_apply.MAX_WHY, 300)
        self.assertEqual(len(self.planned({"op": "change", **self.cur(self.action, "actions"), "owner": "Lee Poe", "why": "y" * 300})["why"]), 300)
        self.assertEqual(self.planned({"op": "change", **self.cur(self.action, "actions"), "owner": "Lee Poe", "why": "a\x7fb~c"})["why"], "ab~c", "DEL dropped, ~ kept")
        self.assertIsNone(self.planned({"op": "change", **self.cur(self.action, "actions"), "owner": "Lee Poe", "why": " \n\x00 "})["why"], "nothing left is no reason")
        self.refused({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "owner": "Lee Poe", "why": 5}, "not_a_change")

    def test_a_plan_carries_the_items_current_owner_for_a_change_only(self):         # row 1293 line 4: the card shows the owner
        with self.s.step("dashboard", USER) as st:
            risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "raised": "2026-10-01",
                                      "owner": "Rita Fox", "source": "demo"})
            dec = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending", "made_by": "Dev Lal",
                                          "source": "demo"})
            st.update("milestones", self.demo.milestone, {"owner": "Mo Ito"})
        self.assertEqual(self.planned({"op": "change", **self.cur(self.action, "actions"), "status": "Closed"})["owner"], "Sam Lee")
        self.assertEqual(self.planned({"op": "change", **self.cur(risk, "raid"), "status": "Closed"})["owner"], "Rita Fox")
        self.assertEqual(self.planned({"op": "change", **self.cur(dec, "decisions"), "needed_by": "2030-01-05"})["owner"], "Dev Lal", "a decision's owner is made_by")
        self.assertEqual(self.planned({"op": "change", **self.cur(self.demo.milestone, "milestones"), "status": "Done"})["owner"], "Mo Ito")
        self.assertIsNone(self.planned({"op": "change", **self.cur(self.demo.use_case, "use_cases"), "status": "Flag"})["owner"], "a use case has none")
        self.assertIsNone(self.planned({"op": "new", "kind": "action", "title": "Book the room", "owner": "Zed Ng"})["owner"], "a new item shows what it creates")

    def cur(self, ref, table):
        """The id and the title the item has now: a change names the title it is about (row 1293)."""
        return {"id": ref, "current_title": self.s.read(table, ref=ref)[ask_apply.TITLE[table]]}

    def blank_owner(self, owner):
        """An action whose stored owner is exactly `owner` (the store makes a missing owner TBC, so a blank one is written straight in)."""
        ref = self.demo.action()
        self.s.con.execute("UPDATE actions SET owner = ? WHERE id = ?", (owner, ref))
        self.s.con.commit()
        return ref

    def test_a_tbc_owner_is_passed_through_as_stored(self):         # ruling 20-11 on 2035: TBC shows 'Owner: TBC'
        with self.s.step("dashboard", USER) as st:
            dec = st.create("decisions", {"project": "ABC", "decision": "Pick a venue", "status": "Pending", "made_by": "TBC", "source": "demo"})
        self.assertEqual(self.planned({"op": "change", **self.cur(self.demo.action(owner="TBC"), "actions"), "status": "Closed"})["owner"], "TBC")
        self.assertEqual(self.planned({"op": "change", **self.cur(self.demo.action(owner=None), "actions"), "status": "Closed"})["owner"], "TBC", "a missing owner is stored as TBC")
        self.assertEqual(self.planned({"op": "change", **self.cur(self.blank_owner("tbc"), "actions"), "status": "Closed"})["owner"], "tbc", "as stored, not respelt")
        self.assertEqual(self.planned({"op": "change", **self.cur(dec, "decisions"), "needed_by": "2030-01-05"})["owner"], "TBC", "a decision's TBC too")

    def test_a_blank_owner_or_a_new_item_has_no_owner_to_show(self):
        for blank in ("", "   "):
            self.assertIsNone(self.planned({"op": "change", **self.cur(self.blank_owner(blank), "actions"), "status": "Closed"})["owner"], f"{blank!r}")
        self.assertIsNone(self.planned({"op": "new", "kind": "action", "title": "Book the room", "owner": "TBC"})["owner"], "a new item, even with TBC")

    def test_the_card_title_is_the_title_now_even_when_the_change_renames_it(self):         # #1292 sweep A: kills after-for-before
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "title": "Cut-over plan v2"})
        self.assertEqual(plan["title"], "Draft the cut-over plan")
        self.assertNotEqual(plan["after"].get("description"), plan["title"])

    def test_the_rule_for_a_change_asks_for_a_short_reason(self):         # #1292 sweep A: the prompt line that makes the model send why
        rule = [r for r in ask.RULES.split("\n") if r.startswith("7.")][0]
        self.assertIn('"status": "Closed", "why": "one short reason"}', rule)

    def test_an_offer_is_used_once(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.applied(plan["offer"])
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "no_offer"))

    def test_an_offer_is_for_its_own_project_only(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        before = self.counts()
        status, body = self.ask.apply(plan["offer"], "XYZ")
        self.assertEqual((status, body["code"]), (409, "no_offer"))
        self.assertEqual(self.counts(), before)


class Milestones(Base):
    def test_create_a_milestone_and_undo(self):
        plan = self.planned({"op": "new", "kind": "milestone", "title": "Go live", "agreed_date": "2030-06-01"})
        self.assertEqual(plan["after"]["baseline_date"], "2030-06-01")
        done = self.applied(plan["offer"], confirm=True)
        self.assertEqual(self.s.read("milestones", ref=done["ref"])["name"], "Go live")
        self.assertTrue(self.ask_events(done["ref"]))
        status, body = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.s.read("milestones", ref=done["ref"]))

    def test_change_a_milestone_and_undo(self):
        ref = self.demo.milestone
        plan = self.planned({"op": "change", "id": ref, "current_title": "Pilot live", "forecast_date": "2030-04-01"})
        self.assertEqual((plan["before"]["forecast_date"], plan["after"]["forecast_date"]), (None, "2030-04-01"))
        done = self.applied(plan["offer"], confirm=True)
        self.assertEqual(self.s.read("milestones", ref=ref)["forecast_date"], "2030-04-01")
        self.assertTrue(all(e["actor"] == "clark" for e in self.ask_events(ref)))
        status, body = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertIsNone(self.s.read("milestones", ref=ref)["forecast_date"])

    def test_a_planted_internal_note_is_in_no_dry_run_apply_or_undo_reply(self):      # #458: the note is the owner's; ask clark neither writes nor says it
        ref, note = self.demo.milestone, "Vendor slipped; do not tell the client SECRETNOTE-458"
        with self.s.step("dashboard", USER) as st:
            st.update("milestones", ref, {"internal_note": note})
        for kind, fields in (("milestones", changes.ASK_SHOWN["milestones"]), ):
            self.assertFalse({"internal_note", "movement"} & set(fields), "ASK_SHOWN leaves out owner-only columns")
        plan = self.planned({"op": "change", "id": ref, "current_title": "Pilot live", "forecast_date": "2030-04-01"})
        done = self.applied(plan["offer"], confirm=True)
        status, undone = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, undone)
        for name, reply in (("dry run", plan), ("apply", done), ("undo", undone)):
            text = json.dumps(reply)
            self.assertNotIn("SECRETNOTE-458", text, name)
            self.assertNotIn("internal_note", text, name)
        self.assertEqual(self.s.read("milestones", ref=ref)["internal_note"], note, "asking never touches the note")
        self.assertEqual(set(plan["before"]) & {"internal_note", "movement"}, set())
        self.refused({"op": "change", "id": ref, "current_title": "Pilot live", "internal_note": "x"}, "field_not_allowed")

    def test_the_agreed_date_is_not_moved_by_asking(self):
        self.refused({"op": "change", "id": self.demo.milestone, "agreed_date": "2031-01-01"}, "field_not_allowed")


class Forged(Base):
    def test_a_wrong_title_is_refused(self):
        body = self.refused({"op": "change", "id": self.action, "current_title": "Pay the supplier", "status": "Closed"}, "wrong_title")
        self.assertIn(self.action, body["message"])

    def test_a_wrong_owner_is_refused(self):
        self.refused({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "current_owner": "Kit Moss", "status": "Closed"}, "wrong_owner")

    def test_a_title_matches_however_it_is_spaced_or_cased(self):
        self.planned({"op": "change", "id": self.action, "current_title": "  draft THE cut-over   plan ", "status": "Closed"})

    def test_a_title_the_editor_saved_with_html_matches_the_plain_words_the_model_was_shown(self):          # #1293 A
        ref = self.demo.action(description="<p>Order the <b>test</b> kit</p>", owner="<p>Sam&nbsp;Lee</p>")
        self.planned({"op": "change", "id": ref, "current_title": "Order the test kit", "current_owner": "Sam Lee", "status": "Closed"})
        self.refused({"op": "change", "id": ref, "current_title": "Order the kit", "status": "Closed"}, "wrong_title")
        self.refused({"op": "change", "id": ref, "current_title": "Order the test kit", "current_owner": "Kit Moss", "status": "Closed"}, "wrong_owner")

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
        self.refused({"op": "change", "kind": "milestone", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"}, "wrong_kind")

    def test_a_shape_that_isnt_the_form_is_refused(self):
        for change in ({}, {"op": "change"}, {"op": "new", "title": "x"}, {"op": "rewrite", "id": self.action},
                       {"op": "new", "kind": "action", "id": self.action, "title": "x"}, {"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": 3},
                       {"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": True}, {"op": "change", "id": self.action, "source": "file.docx", "status": "Closed"}):
            self.refused(change, "not_a_change")

    def test_a_suggestion_from_a_real_reply_is_planned(self):
        reply = ask.read_reply('Closing it.\nCHANGE: {"op": "change", "id": "%s", "current_title": "Draft the cut-over plan", "status": "Closed"}' % self.action,
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
        closing = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.assertEqual(closing["after"]["closed"], store_module.today())   # set by the store's closing rule
        self.assertIsNone(closing["before"]["closed"])

    def test_before_is_read_from_the_data_not_the_claims(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.assertEqual(plan["before"]["description"], "Draft the cut-over plan")
        self.assertEqual(plan["before"]["owner"], "Sam Lee")

    def test_a_row_changed_since_the_dry_run_is_not_saved(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.demo.update("actions", self.action, {"owner": "Ana Ruiz"})
        before = self.counts()
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "changed"), body)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_a_store_rule_is_said_in_plain_words_and_nothing_is_saved(self):
        before = self.counts()
        status, body = self.ask.plan("ABC", {"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "due": "not a date"})
        self.assertEqual((status, body["message"]), (400, changes.NOT_A_DATE))      # the hand edit's own words
        self.assertEqual(self.counts(), before)

    def test_nothing_to_change_is_refused(self):
        self.refused({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "owner": "Sam Lee"}, "nothing")


class TheSwitch(Base):
    def test_off_refuses_the_dry_run(self):
        self.set_switch(0)
        self.refused({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"}, "asking_off")

    def test_off_blocks_apply(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.set_switch(0)
        before = self.counts()
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "asking_off"), body)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_the_switch_is_read_again_inside_the_step(self):
        """Off between the early check and BEGIN IMMEDIATE still writes nothing (the in-step read is the one that counts)."""
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        answers = iter([True, False])
        before = self.counts()
        with mock.patch.object(store_module.Store, "ask_enabled", lambda _self: next(answers, False)):
            status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "asking_off"), body)
        self.assertEqual(self.counts(), before)

    def test_a_switch_that_cant_be_read_is_off(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        with mock.patch.object(store_module.Store, "ask_enabled", lambda _self: 1):     # not exactly True
            status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual(body["code"], "asking_off")


class FromASource(Base):
    def test_a_change_from_a_passage_needs_confirm(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed", "source": "P2"})
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
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"}, from_source=True)
        self.assertTrue(plan["needs_confirm"])
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual(body["code"], "needs_confirm")

    def test_a_change_from_the_report_needs_no_confirm(self):      # row 1416: unless it falls under the client tick (test_ask_client_tick_1416)
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.assertFalse(plan["needs_confirm"], "an item that is off the client report")
        self.applied(plan["offer"])
        visible = self.demo.action(owner="Sam Lee", client_visible=1)
        plan = self.planned({"op": "change", "id": visible, "current_title": "Draft the cut-over plan", "priority": "High"})
        self.assertFalse(plan["needs_confirm"], "a column the client tick does not cover, on a client-visible item")
        self.applied(plan["offer"])


class NotYet(Base):
    def test_archive_and_delete_are_refused_in_plain_words(self):
        for op in ("archive", "delete", "Remove", "restore"):
            body = self.refused({"op": op, "id": self.action}, "not_yet")
            self.assertIn("isn't available yet", body["message"])
        self.refused({"op": "change", "id": self.action, "archived": 1}, "not_yet")
        self.assertEqual(self.s.read("actions", ref=self.action)["archived"], 0)

    def test_more_than_five_at_once_is_refused(self):
        many = [{"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"}] * (ask_apply.MAX_AT_ONCE + 1)
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

    def test_the_save_path_keeps_to_ask_clarks_own_fields(self):
        ask_change = changes.make_ask_change(self.path, [], USER)
        before = self.counts()
        for req in ({"project": "ABC", "kind": "milestones", "op": "update", "id": self.demo.milestone,
                     "changes": {"baseline_date": "2031-01-01"}},
                    {"project": "ABC", "kind": "milestones", "op": "update", "id": self.demo.milestone,
                     "changes": {"client_message": "All is well."}},
                    {"project": "ABC", "kind": "milestones", "op": "update", "id": self.demo.milestone,
                     "changes": {"forecast_date": "2031-01-01", "client_message": "All is well."}},
                    {"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": {"use_case": None}},
                    {"project": "ABC", "kind": "actions", "op": "new", "values": {"description": "x"}, "place": "menu"},
                    {"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": ["status"]}):
            for dry in (True, False):
                status, body = ask_change(req, dry=dry)
                self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.ASK_NOT_YET), req)
        self.assertEqual(self.counts(), before)

    def test_ask_apply_reads_its_fields_from_the_guarded_list(self):
        for table, ops in changes.ASK_FIELDS.items():
            self.assertEqual(ask_apply.ASK_FIELDS[table][ask_apply.OP_CHANGE], ops[changes.UPDATE])
            self.assertEqual(set(ask_apply.ASK_FIELDS[table][ask_apply.OP_NEW]), set(ops[changes.NEW]) - {"type"})
            for op, fields in ops.items():
                self.assertTrue(set(fields) <= set(changes.CHANGE_KINDS[table][op]), (table, op))
        self.assertNotIn("client_message", changes.ASK_FIELDS["milestones"][changes.UPDATE])
        self.assertNotIn("baseline_date", changes.ASK_FIELDS["milestones"][changes.UPDATE])


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

    def test_an_assistant_step_on_a_use_case_is_undoable_now_that_it_is_one_of_ask_clarks_kinds(self):      # issue 729 (it was not before)
        with self.s.step("assistant", USER, actor="clark") as st:
            st.update("use_cases", self.demo.use_case, {"headline": "Changed by ask clark"})
        step = self.demo.last_step()
        status, body = self.undo({"project": "ABC", "apply_id": step})
        self.assertEqual(status, 200, body)
        self.assertNotEqual(self.s.read("use_cases", ref=self.demo.use_case)["headline"], "Changed by ask clark")


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

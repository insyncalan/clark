"""Issue 729: ask clark may suggest changes to a use case, as it does for a work item and a milestone.

Run: python3 dev/run_tests.py test_ask_use_cases
The same route (changes.make_ask_change, a dry run then Apply as one undoable step), the same checks as the use case editor
(changes._checked_use_case_changes), and the model is shown only what the published file carries (ask_data). Fictional data only.
"""
import unittest

from _demo import USER
from test_ask_apply import Base
from clark import ask, ask_apply, ask_data, changes


class UseCaseChanges(Base):
    def setUp(self):
        super().setUp()
        self.uc = self.demo.use_case
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", self.uc, {"headline": "Matches invoices to orders", "client_visible": 1})
            self.other_uc = st.create("use_cases", {"project": "XYZ", "title": "Badge printing", "status": "On track", "source": "demo"})

    def row(self):
        return self.s.read("use_cases", ref=self.uc)

    def test_a_status_headline_and_standing_change_is_applied_once_and_undone_in_one_step(self):
        plan = self.planned({"op": "change", "id": self.uc, "current_title": "Invoice matching", "status": "Flag",
                             "headline": "Late supplier files", "standing": "Two files are late."})
        self.assertEqual(sorted(plan["fields"]), ["headline", "standing", "status"])
        self.assertEqual(self.row()["status"], "On track", "a dry run saves nothing")
        done = self.applied(plan["offer"])
        row = self.row()
        self.assertEqual((row["status"], row["headline"], row["commitment"]), ("Flag", "Late supplier files", None))
        self.assertIn("Two files are late.", row["standing"])
        events = self.ask_events(self.uc)
        self.assertTrue(events)
        self.assertTrue(all(e["actor"] == "clark" for e in events))
        self.assertEqual(len({e["step"] for e in events}), 1, "one Apply is one step, one History entry")
        status, again = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, again["code"]), (409, "no_offer"), "applied once only")
        status, body = self.undo({"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, body)
        row = self.row()
        self.assertEqual((row["status"], row["headline"], row["commitment"]), ("On track", "Matches invoices to orders", None))

    def test_a_word_that_is_not_allowed_is_refused_in_the_editors_words(self):
        for field, value, words in (("status", "Great", changes.UC_STATUS_WORDS), ("headline", "x" * 400, changes.UC_HEADLINE_WORDS)):
            with self.subTest(field=field, value=value[:12]):
                before = self.counts()
                status, body = self.ask.plan("ABC", {"op": "change", "id": self.uc, field: value})
                self.assertEqual((status, body["ok"]), (400, False), body)
                self.assertEqual(body["message"], words)
                self.assertEqual(self.counts(), before)

    def test_the_rules_name_the_three_commitment_words(self):
        self.assertIn("(Planned 2026, Committed or Planned 2027)", ask.RULES)
        self.assertNotIn("Candidate", ask.RULES)

    def test_the_model_may_read_the_commitment_flag_but_a_proposal_to_change_it_is_refused(self):      # the Head's ruling
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", self.uc, {"commitment": "Planned 2026"})
        for word in ("Planned 2026", "Committed", "Planned 2027", "", "Maybe", None):
            with self.subTest(word=word):
                before = self.counts()
                self.refused({"op": "change", "id": self.uc, "commitment": word}, "field_not_allowed")
                self.refused({"op": "change", "id": self.uc, "status": "Flag", "commitment": word}, "field_not_allowed")
                req = {"project": "ABC", "kind": "use_cases", "op": "update", "id": self.uc, "changes": {"commitment": word}}
                status, body = self.ask.ask_change(req, dry=False)      # and the route itself, not only ask_apply
                self.assertGreaterEqual(status, 400)
                self.assertEqual(body["code"], "not_yet")
                self.assertEqual(self.counts(), before)
                self.assertEqual(self.row()["commitment"], "Planned 2026")

    def test_an_unknown_id_and_another_projects_use_case_are_refused(self):
        self.refused({"op": "change", "id": "ABC-U-099", "status": "Flag"}, "unknown_id")
        self.refused({"op": "change", "id": self.other_uc, "status": "Flag"}, "other_project")
        self.assertEqual(self.s.read("use_cases", ref=self.other_uc)["status"], "On track")

    def test_the_route_itself_refuses_another_projects_use_case(self):          # not only ask_apply's own check
        req = {"project": "ABC", "kind": "use_cases", "op": "update", "id": self.other_uc, "changes": {"status": "Flag"}}
        status, body = self.ask.ask_change(req, dry=False)
        self.assertGreaterEqual(status, 400)
        self.assertEqual(body["message"], changes.NO_USE_CASE)
        self.assertEqual(self.s.read("use_cases", ref=self.other_uc)["status"], "On track")

    def test_an_archived_use_case_is_not_changed(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.uc)
        self.refused({"op": "change", "id": self.uc, "status": "Flag"}, "unknown_id")

    def test_only_the_three_fields_may_be_given(self):
        for name in ("title", "ref", "commitment", "client_visible", "sort_order", "archived_at", "internal_note"):
            with self.subTest(name=name):
                self.refused({"op": "change", "id": self.uc, name: "x"}, "field_not_allowed")

    def test_archive_delete_a_new_use_case_and_an_owner_claim_are_still_refused(self):
        for op in ("archive", "delete", "restore", "remove"):
            self.refused({"op": op, "id": self.uc}, "not_yet")
        self.refused({"op": "change", "id": self.uc, "archived": True}, "not_yet")
        self.refused({"op": "new", "kind": "use case", "title": "Another", "status": "Flag"}, "not_a_change")
        self.refused({"op": "change", "id": self.uc, "current_owner": "Sam Lee", "status": "Flag"}, "not_a_change")
        req = {"project": "ABC", "kind": "use_cases", "op": "new", "values": {"title": "Another"}}
        status, body = self.ask.ask_change(req, dry=False)
        self.assertEqual((status, body["code"]), (400, "not_yet"))
        self.assertEqual(len(self.s.read("use_cases", project="ABC")), 1, "no use case was added")

    def test_the_wrong_title_is_refused_and_the_kind_must_agree(self):
        self.refused({"op": "change", "id": self.uc, "current_title": "Pay the supplier", "status": "Flag"}, "wrong_title")
        self.refused({"op": "change", "kind": "milestone", "id": self.uc, "status": "Flag"}, "wrong_kind")
        self.planned({"op": "change", "kind": "use case", "id": self.uc, "status": "Flag"})

    def test_a_suggestion_from_a_real_reply_is_planned(self):
        reply = ask.read_reply('Flagging it.\nCHANGE: {"op": "change", "id": "%s", "status": "Flag"}' % self.uc,
                               codes=("ABC",), exists=lambda ref: ref == self.uc)
        self.assertEqual(len(reply.changes), 1)
        self.assertEqual(self.planned(reply.changes[0])["after"]["status"], "Flag")

    def test_the_rules_name_use_cases_and_their_fields(self):
        self.assertIn("-U-", ask.RULES)
        self.assertIn("Planned 2027", ask.RULES)
        self.assertEqual(changes.ASK_FIELDS["use_cases"][changes.UPDATE], ("headline", "status", "standing"))
        self.assertIn("never suggest changing it", ask.RULES)
        self.assertNotIn("commitment", ask_apply.ASK_FIELDS["use_cases"][ask_apply.OP_CHANGE])
        self.assertNotIn("client_visible", ask_apply.ASK_FIELDS["use_cases"][ask_apply.OP_CHANGE])


class WhatTheModelSees(Base):
    def passages(self):
        store = self.ask.reader()
        self.addCleanup(store.close)
        data = ask_data.project_data(store, "ABC", "use cases", budget=40000)
        return data, "\n".join(p.text for p in data.passages)

    def test_a_shown_use_case_gives_the_model_its_id_status_commitment_headline_and_standing_only(self):
        uc = self.demo.use_case
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", uc, {"headline": "Matches invoices", "standing": "<p>Going well</p>", "commitment": "Planned 2026",
                                        "client_visible": 1})
        data, text = self.passages()
        (line,) = [x for x in text.splitlines() if x.startswith(uc)]
        self.assertEqual(line, f"{uc} Invoice matching | status: On track | commitment: Planned 2026 | headline: Matches invoices"
                               " | standing: Going well")
        self.assertEqual(ask_data.SHOWN["use_cases"], ("ref", "status", "commitment", "headline", "standing"))
        self.assertIn(uc, data.facts)

    def test_a_hidden_use_case_is_not_offered(self):
        uc = self.demo.use_case
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", uc, {"headline": "Hidden words ZQ-HIDDEN", "client_visible": 0})
        data, text = self.passages()
        self.assertNotIn(uc, text)
        self.assertNotIn("ZQ-HIDDEN", text)
        self.assertNotIn(uc, data.facts)

    def test_an_archived_use_case_is_not_offered(self):
        uc = self.demo.use_case
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", uc, {"headline": "Old words ZQ-OLD", "client_visible": 1})
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", uc)
        data, text = self.passages()
        self.assertNotIn("ZQ-OLD", text)
        self.assertNotIn(uc, data.facts)


if __name__ == "__main__":
    unittest.main()

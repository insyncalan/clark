"""Row 1416 (AP5, PM ruling 24-11): asking needs the extra tick when the change is to an item that is on the client report (client_visible)
AND moves its title, owner, a date, the status, the impact or the likelihood, or when it adds a new item. Nothing else needs it. The
server refuses the Apply with 409 needs_confirm until confirm is exactly true.

Run: python3 dev/run_tests.py test_ask_client_tick_1416
"""
import unittest

from _demo import USER
from test_ask_apply import Base, ask_apply

# table -> the changes to an existing item that the ruling lists (a decision's date and a milestone's achieved date only go with their status;
# asking can set a risk's impact and likelihood only on a NEW risk, which is the new-item test)
TICK = {
    "actions": ({"title": "Draft the plan again"}, {"owner": "Kit Moss"}, {"due": "2030-07-01"}, {"status": "Closed"}),
    "raid": ({"title": "Supplier is late again"}, {"owner": "Kit Moss"}, {"due": "2030-07-01"}, {"status": "Closed"}),
    "decisions": ({"title": "Use the shared calendar now"}, {"owner": "Kit Moss"}, {"status": "Made", "date": "2030-07-01"}, {"needed_by": "2030-07-02"}),
    "milestones": ({"forecast_date": "2030-08-02"}, {"status": "Done", "achieved_date": "2020-08-03"}),
    "use_cases": ({"status": "Flag"},),
}
# changes the ruling leaves out, on an item that IS on the report
NO_TICK = {"actions": ({"priority": "High"}, {"workstream": "Build"}), "raid": ({"workstream": "Build"},),
           "use_cases": ({"headline": "Matching is on track"}, {"standing": "Matching runs weekly."})}


class ClientTick(Base):
    def item(self, table, visible):
        """An existing item of `table` with its eye (client_visible) set to `visible`: the claims that name it."""
        if table == "actions":
            ref = self.demo.action(owner="Sam Lee", client_visible=visible)
        else:
            row = {"raid": {"type": "Risk", "description": "Supplier may slip", "owner": "Sam Lee", "raised": "2026-10-01"},
                   "decisions": {"decision": "Use the shared calendar", "status": "Pending"},
                   "milestones": {"name": "Pilot live", "baseline_date": "2030-03-01"},
                   "use_cases": {"title": "Invoice matching", "status": "On track"}}[table]
            with self.s.step("dashboard", USER) as st:
                ref = st.create(table, {"project": "ABC", "source": "demo", "client_visible": visible, **row})
        return {"id": ref, "current_title": self.s.read(table, ref=ref)[ask_apply.TITLE[table]]}

    def plan_of(self, table, visible, **change):
        return self.planned({"op": "change", **self.item(table, visible), **change})

    def test_every_listed_field_on_a_client_visible_item_needs_the_tick(self):
        for table, fields in TICK.items():
            for change in fields:
                with self.subTest(table=table, change=change):
                    shown = self.plan_of(table, 1, **change)
                    self.assertTrue(shown["needs_confirm"] and shown["client"] and not shown["from_source"])
                    before = self.counts()
                    for confirm in (False, None, 1, "yes", "true"):
                        status, body = self.ask.apply(shown["offer"], "ABC", confirm=confirm)
                        self.assertEqual((status, body["code"]), (409, "needs_confirm"), confirm)
                    self.assertEqual(self.counts(), before, "nothing was saved without the tick")
                    self.applied(shown["offer"], confirm=True)

    def test_the_same_change_on_an_item_that_is_off_the_report_needs_no_tick(self):
        for table, fields in TICK.items():
            for change in fields:
                with self.subTest(table=table, change=change):
                    shown = self.plan_of(table, 0, **change)
                    self.assertFalse(shown["needs_confirm"] or shown["client"])
                    self.applied(shown["offer"])

    def test_a_field_the_ruling_leaves_out_needs_no_tick_on_a_client_visible_item(self):
        for table, fields in NO_TICK.items():
            for change in fields:
                with self.subTest(table=table, change=change):
                    shown = self.plan_of(table, 1, **change)
                    self.assertFalse(shown["needs_confirm"] or shown["client"])
                    self.applied(shown["offer"])

    def test_a_change_with_one_listed_field_among_others_needs_the_tick(self):
        self.assertTrue(self.plan_of("actions", 1, priority="High", status="Closed")["needs_confirm"])

    def test_a_new_item_needs_the_tick(self):
        for change in ({"kind": "action", "title": "Book the room", "owner": "Sam Lee"}, {"kind": "risk", "title": "Supplier is late", "owner": "Sam Lee", "impact": "High", "likelihood": "Low"},
                       {"kind": "decision", "title": "Pick the vendor"}, {"kind": "milestone", "title": "Go live", "agreed_date": "2030-06-01"}):
            with self.subTest(kind=change["kind"]):
                shown = self.planned({"op": "new", **change})
                self.assertTrue(shown["needs_confirm"] and shown["client"])
                self.assertEqual(self.ask.apply(shown["offer"], "ABC")[1]["code"], "needs_confirm")
                self.applied(shown["offer"], confirm=True)

    def test_a_change_from_a_file_is_still_marked_from_a_source_and_uses_the_same_refusal(self):
        shown = self.planned({"op": "change", **self.item("actions", 0), "status": "Closed", "source": "P2"})
        self.assertTrue(shown["needs_confirm"] and shown["from_source"] and not shown["client"])
        self.assertEqual(self.ask.apply(shown["offer"], "ABC")[1]["code"], "needs_confirm")

    def test_the_client_words_and_the_eye_stay_out_of_reach(self):
        for field in ("client_message", "client_visible"):
            status, body = self.ask.plan("ABC", {"op": "change", **self.item("actions", 1), field: "x"})
            self.assertEqual((status, body["code"]), (400, "field_not_allowed"), field)

    def test_the_tick_adds_no_new_words(self):      # the refusal is the one the file tick has; the page's box words are the existing CONFIRM_BOX
        self.assertEqual(self.ask.apply(self.plan_of("actions", 1, status="Closed")["offer"], "ABC")[1]["message"], ask_apply.NEEDS_CONFIRM)


if __name__ == "__main__":
    unittest.main()

"""Row 1416 (AP5): a change made by asking needs the extra tick when it alters what a client sees. PM ruling 24-11: the item is on the
client report (client_visible) AND the changed column is one the report needs a tick for (CLIENT_COLUMNS: title, owner, dates, status,
impact, likelihood, a use case's headline and standing text), or the change makes a NEW item that lands on the report. No tick for
workstream, milestone link or priority, nor for an item that is off the report. The server refuses an Apply with 409 needs_confirm until
confirm is exactly true.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_ask_client_tick_1416
"""
import unittest

from test_ask_apply import USER, Base, ask_apply

# table -> (kind word for a new item, [(plain suggestion field, value, the stored column)], [fields with no tick])
TICK = {
    "actions": [("title", "Draft the plan again", "description"), ("owner", "Kit Moss", "owner"), ("due", "2030-07-01", "due_date"),
                ("status", "Closed", "status")],
    "raid": [("title", "Supplier is late again", "description"), ("owner", "Kit Moss", "owner"), ("due", "2030-07-01", "due_date"),
             ("status", "Closed", "status")],      # impact and likelihood are set by asking only on a new risk: see the new-item test
    "decisions": [("title", "Use the shared calendar now", "decision"), ("made_by", "Kit Moss", "made_by"),
                  ("needed_by", "2030-07-02", "needed_by")],
    "milestones": [("forecast_date", "2030-08-02", "forecast_date"), ("status", "Done", "status")],      # asking can't move an existing milestone's title, owner or agreed date
    "use_cases": [("headline", "Matching is on track", "headline"), ("status", "Flag", "status")],
}
NO_TICK = {"actions": [("priority", "High"), ("workstream", "Build"), ("milestone", None)],
           "raid": [("workstream", "Build"), ("milestone", None)]}


class Client(Base):
    def item(self, table, visible):
        """An existing item of `table` and the title the change must name; its eye (client_visible) is `visible`."""
        if table == "actions":
            ref = self.demo.action(owner="Sam Lee", client_visible=visible)
        elif table == "raid":
            with self.s.step("dashboard", USER) as st:
                ref = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may slip", "owner": "Sam Lee", "raised": "2026-10-01",
                                         "source": "demo", "client_visible": visible})
        elif table == "decisions":
            with self.s.step("dashboard", USER) as st:
                ref = st.create("decisions", {"project": "ABC", "decision": "Use the shared calendar", "source": "demo", "status": "Pending",
                                              "needed_by": "2030-01-01", "client_visible": visible})
        elif table == "milestones":
            with self.s.step("dashboard", USER) as st:
                ref = st.create("milestones", {"project": "ABC", "name": "Pilot live", "baseline_date": "2030-03-01", "source": "demo",
                                               "client_visible": visible})
        else:
            with self.s.step("dashboard", USER) as st:
                ref = st.create("use_cases", {"project": "ABC", "title": "Invoice matching", "status": "On track", "source": "demo",
                                              "client_visible": visible})
        return {"id": ref, "current_title": self.s.read(table, ref=ref)[ask_apply.TITLE[table]]}

    def plan_of(self, table, visible, **change):
        status, body = self.ask.plan("ABC", {"op": "change", **self.item(table, visible), **change})
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def check_tick(self, table, field, value, column):
        shown = self.plan_of(table, 1, **{field: value})
        self.assertTrue(shown["needs_confirm"], f"{table}.{field} on a client-visible item needs the tick")
        self.assertTrue(shown["client"])
        self.assertFalse(shown["from_source"])
        before = self.counts()
        for confirm in (False, None, 1, "yes", "true"):
            status, body = self.ask.apply(shown["offer"], "ABC", confirm=confirm)
            self.assertEqual((status, body["code"]), (409, "needs_confirm"), (table, field, confirm))
            self.assertEqual(body["message"], ask_apply.NEEDS_CONFIRM_CLIENT)
        self.assertEqual(self.counts(), before, "nothing was saved without the tick")
        self.applied(shown["offer"], confirm=True)
        hidden = self.plan_of(table, 0, **{field: value})
        self.assertFalse(hidden["needs_confirm"], f"{table}.{field} on an item that is off the report needs no tick")
        self.assertFalse(hidden["client"])
        self.applied(hidden["offer"])

    def test_every_client_column_of_every_table_needs_the_tick(self):
        for table, fields in TICK.items():
            for field, value, column in fields:
                with self.subTest(table=table, field=field):
                    self.assertIn(column, ask_apply.CLIENT_COLUMNS[table])
                    self.check_tick(table, field, value, column)

    def test_a_decision_marked_made_needs_the_tick(self):
        shown = self.plan_of("decisions", 1, status="Made", date="2030-07-01")
        self.assertTrue(shown["needs_confirm"])
        self.assertFalse(self.plan_of("decisions", 0, status="Made", date="2030-07-01")["needs_confirm"])

    def test_the_list_of_columns_is_the_ruled_one(self):
        self.assertEqual(ask_apply.CLIENT_COLUMNS["use_cases"], ("headline", "standing", "status"))
        for table, columns in ask_apply.CLIENT_COLUMNS.items():
            for column in ("workstream", "milestone", "priority"):
                self.assertNotIn(column, columns, table)

    def test_an_achieved_date_on_a_done_milestone_needs_the_tick(self):
        for visible in (1, 0):
            with self.s.step("dashboard", USER) as st:
                ref = st.create("milestones", {"project": "ABC", "name": "Pilot live", "baseline_date": "2030-03-01", "source": "demo",
                                               "status": "Done", "actual_date": "2020-03-01", "client_visible": visible})
            status, shown = self.ask.plan("ABC", {"op": "change", "id": ref, "current_title": "Pilot live", "achieved_date": "2020-08-03"})
            self.assertEqual((status, shown.get("message")), (200, None), shown)
            self.assertEqual(shown["needs_confirm"], bool(visible))

    def test_a_decision_marked_made_needs_the_tick(self):
        shown = self.plan_of("decisions", 1, status="Made", date="2030-07-01")
        self.assertTrue(shown["needs_confirm"])
        self.assertFalse(self.plan_of("decisions", 0, status="Made", date="2030-07-01")["needs_confirm"])

    def test_the_list_of_columns_is_the_ruled_one(self):
        self.assertEqual(ask_apply.CLIENT_COLUMNS["use_cases"], ("headline", "standing", "status"))
        for table, columns in ask_apply.CLIENT_COLUMNS.items():
            for column in ("workstream", "milestone", "priority"):
                self.assertNotIn(column, columns, table)

    def test_an_achieved_date_on_a_done_milestone_needs_the_tick(self):
        shown = self.plan_of("milestones", 1, status="Done", achieved_date="2020-08-03")
        self.assertTrue(shown["needs_confirm"])
        self.assertFalse(self.plan_of("milestones", 0, status="Done", achieved_date="2020-08-03")["needs_confirm"])

    def test_a_use_cases_standing_text_needs_the_tick(self):
        shown = self.plan_of("use_cases", 1, standing="Matching runs weekly.")
        self.assertTrue(shown["needs_confirm"])
        self.assertFalse(self.plan_of("use_cases", 0, standing="Matching runs weekly.")["needs_confirm"])

    def test_workstream_milestone_and_priority_need_no_tick_on_a_client_visible_item(self):
        for table, fields in NO_TICK.items():
            for field, value in fields:
                if value is None:
                    value = self.demo.milestone
                with self.subTest(table=table, field=field):
                    shown = self.plan_of(table, 1, **{field: value})
                    self.assertFalse(shown["needs_confirm"], f"{table}.{field}")
                    self.applied(shown["offer"])

    def test_a_change_that_touches_both_kinds_needs_the_tick(self):
        shown = self.plan_of("actions", 1, priority="High", status="Closed")
        self.assertTrue(shown["needs_confirm"])

    def test_a_new_item_that_lands_on_the_report_needs_the_tick(self):
        for change in ({"kind": "action", "title": "Book the room", "owner": "Sam Lee"}, {"kind": "risk", "title": "Supplier is late", "owner": "Sam Lee", "impact": "High", "likelihood": "Low"},
                       {"kind": "decision", "title": "Pick the vendor", "owner": "Sam Lee"}, {"kind": "milestone", "title": "Go live", "agreed_date": "2030-06-01"}):
            with self.subTest(kind=change["kind"]):
                status, shown = self.ask.plan("ABC", {"op": "new", **change})
                self.assertEqual((status, shown.get("message")), (200, None), shown)
                self.assertTrue(shown["needs_confirm"])
                self.assertEqual(self.ask.apply(shown["offer"], "ABC")[1]["code"], "needs_confirm")
                self.applied(shown["offer"], confirm=True)

    def test_a_change_from_a_file_keeps_its_own_words(self):
        shown = self.plan_of("actions", 0, status="Closed")
        status, body = self.ask.plan("ABC", {"op": "change", **self.item("actions", 0), "status": "Closed", "source": "P2"})
        self.assertTrue(body["needs_confirm"] and body["from_source"] and not body["client"])
        self.assertEqual(self.ask.apply(body["offer"], "ABC")[1]["message"], ask_apply.NEEDS_CONFIRM)
        self.assertFalse(shown["needs_confirm"])


if __name__ == "__main__":
    unittest.main()

"""Row 811b: work items flagged client_action (needed from the client) are listed as generated rows under 'Needs from you' in the
published file, over a real store. Only a flagged item that is open and client-visible, not Sensitive, not archived and not left off
the report; a decision never; the order is stable; a hand-typed list is kept as it is. Fictional data.

Run: python3 dev/run_tests.py test_publish_client_action
"""
import json
import re
import unittest

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import publish

NOW = "2030-01-15"


def hand(*rows):
    return json.dumps({"v": 1, "rows": [{"what": "Choose the pilot site", "kind": "decision", "from": "Steering group", "by": "2030-03-04",
                                          "hidden": 0, **r} for r in rows]})


class Listed(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def action(self, text, **more):
        return self.demo.action(description=text, client_action=1, **more)

    def risk(self, text, **more):
        base = {"project": "ABC", "type": "Risk", "description": text, "raised": "2026-10-01", "impact": "High", "likelihood": "Low",
                "source": "demo", "client_action": 1}
        with self.s.step("dashboard", USER) as st:
            return st.create("raid", {**base, **more})

    def section(self, rows=None, **more):
        with self.s.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": "needs", "title": "Needs from you", "body": hand(*rows) if rows else "",
                                                 "sort_order": 1, "beside": 0, "hidden": 0, **more})

    def built(self):
        return publish.build(self.s, "ABC", now=NOW)

    def rows(self):
        return [r for sec in self.built()["published"]["sections"] if sec["type"] == "needs" for r in sec["rows"]]

    def whats(self):
        return [r["what"] for r in self.rows()]

    def test_a_flagged_open_visible_item_is_listed_with_the_four_fields(self):
        self.action("Send the access list", owner="Pat Quinn", due_date="2030-02-03")
        self.assertEqual(self.rows(), [{"what": "Send the access list", "kind": "information", "from": "", "by": "03-02-2030"}])
        entry = [x for x in self.built()["published"]["sections"] if x["type"] == "needs"]
        self.assertNotIn("Pat Quinn", json.dumps(entry), "an owner is one of our own people: no owner text in the Needs from you section")

    def test_no_owner_and_no_date_read_as_blank_never_the_placeholder(self):
        self.action("Send the access list")
        self.assertEqual(self.rows(), [{"what": "Send the access list", "kind": "information", "from": "", "by": ""}])

    def test_a_flagged_risk_or_issue_is_listed_too(self):
        self.risk("Portal supplier late", owner="Sam Lee")
        self.assertEqual(self.whats(), ["Portal supplier late"])

    def test_a_delayed_action_is_open(self):
        self.action("Delayed one", status="Delayed")
        self.assertEqual(self.whats(), ["Delayed one"])

    def test_a_closed_or_cancelled_item_is_not_listed(self):
        self.action("Closed one", status="Closed", closed="2030-01-01")
        self.action("Cancelled one", status="Cancelled")
        self.risk("Closed risk", status="Closed", closed="2030-01-01")
        self.assertEqual(self.rows(), [])

    def test_an_item_left_off_the_report_is_not_listed_in_any_way_it_can_be_left_off(self):
        eye = self.action("Eye off")
        self.demo.update("actions", eye, {"client_visible": 0})
        gone = self.action("ZQ gone away")
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", gone)
        sens = self.action("Marked Sensitive")
        with self.s.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": sens, "label": "Sensitive"})
        listed = self.risk("Marked Sensitive risk")
        with self.s.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": listed, "label": "Sensitive"})
        self.assertEqual(self.rows(), [])
        text = self.built()["body"].decode("utf-8")
        for word in ("Eye off", "Marked Sensitive", "ZQ gone away"):
            self.assertNotIn(word, text)

    def test_an_item_that_is_not_flagged_is_not_listed(self):
        self.demo.action(description="Plain action")
        self.assertEqual(self.rows(), [])

    def test_a_decision_is_never_listed(self):
        with self.s.step("dashboard", USER) as st:
            st.create("decisions", {"project": "ABC", "decision": "Pick a vendor", "status": "Pending", "needed_by": "2030-02-01", "source": "demo"})
        self.assertEqual(self.rows(), [])

    def test_the_order_is_actions_then_risks_each_by_id_and_the_same_every_time(self):
        self.risk("R one")
        self.action("A one")
        self.action("A two")
        self.risk("R two")
        first = self.whats()
        self.assertEqual(first, ["A one", "A two", "R one", "R two"])
        self.assertEqual(self.whats(), first)

    def test_the_section_never_holds_more_than_a_typed_list_may_typed_rows_win_and_the_order_holds(self):
        cap = publish.section_bodies.NEEDS_MAX_ROWS
        self.section([{"what": "Typed %d" % n} for n in range(cap - 2)])
        for n in range(5):
            self.action("Gen %d" % n)
        got = self.whats()
        self.assertEqual(len(got), cap)
        self.assertEqual(got[:cap - 2], ["Typed %d" % n for n in range(cap - 2)])
        self.assertEqual(got[cap - 2:], ["Gen 0", "Gen 1"], "the first in order are kept")

    def test_a_full_typed_list_leaves_no_room_and_a_cap_over_generated_alone_holds(self):
        cap = publish.section_bodies.NEEDS_MAX_ROWS
        self.section([{"what": "Typed %d" % n} for n in range(cap)])
        self.action("Gen")
        self.assertEqual(len(self.rows()), cap)
        self.assertNotIn("Gen", self.whats())

    def test_generated_rows_alone_are_capped_too(self):
        cap = publish.section_bodies.NEEDS_MAX_ROWS
        with self.s.step("dashboard", USER) as st:
            for n in range(cap + 3):
                st.create("actions", {"project": "ABC", "description": "G%03d" % n, "raised": "2026-10-01", "source": "demo", "client_action": 1})
        got = self.whats()
        self.assertEqual(got, ["G%03d" % n for n in range(cap)])

    def test_the_hand_typed_rows_stay_first_and_are_not_repeated_or_changed(self):
        ref = self.section([{"what": "Hand one"}, {"what": "Hand two", "hidden": 1}])
        before = self.s.read("report_sections", ref=ref)["body"]
        self.action("Generated one")
        self.assertEqual(self.rows(), [{"what": "Hand one", "kind": "decision", "from": "Steering group", "by": "04-03-2030"},
                                       {"what": "Generated one", "kind": "information", "from": "", "by": ""}])
        sections = [s for s in self.built()["published"]["sections"] if s["type"] == "needs"]
        self.assertEqual(len(sections), 1, "one section, not a second beside it")
        self.assertEqual(self.s.read("report_sections", ref=ref)["body"], before,
                         "the stored list is not written to")

    def test_a_hand_typed_section_with_no_rows_still_hosts_the_generated_ones(self):
        ref = self.section()
        self.action("Generated one")
        got = [s for s in self.built()["published"]["sections"] if s["type"] == "needs"]
        self.assertEqual([s["id"] for s in got], [ref])
        self.assertEqual([r["what"] for r in got[0]["rows"]], ["Generated one"])

    def test_without_a_needs_section_one_is_made_for_the_file_with_the_curly_quoted_title_words(self):
        self.action("Generated one")
        got = [s for s in self.built()["published"]["sections"] if s["type"] == "needs"]
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["title"], "Needs from you")

    def test_a_needs_section_the_owner_has_hidden_stays_hidden(self):
        self.section([{"what": "Hand one"}], hidden=1)
        self.action("Generated one")
        self.assertEqual(self.rows(), [])

    def test_the_empty_case_has_no_section_at_all(self):
        self.assertEqual([s for s in self.built()["published"]["sections"] if s["type"] == "needs"], [])
        self.section()
        self.assertEqual([s for s in self.built()["published"]["sections"] if s["type"] == "needs"], [])

    def test_the_flag_itself_is_never_in_the_data_block(self):
        self.action("Generated one")
        text = self.built()["body"].decode("utf-8")
        found = re.findall(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S)
        self.assertEqual(len(found), 1)
        self.assertNotIn("client_action", found[0])
        self.assertIn("Generated one", found[0])


if __name__ == "__main__":
    unittest.main()

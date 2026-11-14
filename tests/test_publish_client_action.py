"""Item 1158 (was row 811b): a work item flagged client_action no longer feeds a 'Needs from you' list. The stored flag is kept, but
the published file never carries a needs section, never copies the flag, and logs nothing about a list that is not there. Over a real
store and the real build. Fictional data.

Run: python3 dev/run_tests.py test_publish_client_action
"""
import json
import logging
import re
import unittest

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import publish

NOW = "2030-01-15"


class Flagged(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def action(self, text, **more):
        return self.demo.action(**{"description": text, "client_message": text, "client_action": 1, **more})

    def risk(self, text, **more):
        base = {"project": "ABC", "type": "Risk", "description": text, "client_message": text, "raised": "2026-10-01", "impact": "High",
                "likelihood": "Low", "source": "demo", "client_action": 1}
        with self.s.step("dashboard", USER) as st:
            return st.create("raid", {**base, **more})

    def stored_section(self, **more):
        body = json.dumps({"v": 1, "rows": [{"what": "Typed row", "kind": "decision", "from": "", "by": "", "hidden": 0}]})
        with self.s.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": "needs", "title": "Needs from you", "body": body,
                                                 "sort_order": 1, "beside": 0, "hidden": 0, **more})

    def built(self):
        return publish.build(self.s, "ABC", now=NOW)

    def needs(self):
        return [s for s in self.built()["published"]["sections"] if s["type"] == "needs"]

    def test_a_flagged_open_item_makes_no_needs_section(self):
        self.action("Generated one")
        self.risk("Client risk")
        self.assertEqual(self.needs(), [])
        self.assertNotIn("Needs from you", self.built()["body"].decode("utf-8"))

    def test_a_stored_needs_section_gets_no_flagged_rows_and_is_not_in_the_file(self):
        ref = self.stored_section()
        self.action("Generated one")
        self.assertEqual(self.needs(), [])
        self.assertNotIn("Typed row", self.built()["body"].decode("utf-8"))
        self.assertIn(ref, [r["id"] for r in self.s.read("report_sections", project="ABC")], "it stays stored")

    def test_the_build_logs_nothing_about_a_list(self):
        self.stored_section()
        self.action("Generated one")
        logger = logging.getLogger("clark.publish")
        with self.assertLogs(logger, level="WARNING") as got:
            self.built()
            logger.warning("sentinel")
        self.assertEqual([line for line in got.output if "Needs from you" in line], [])

    def test_the_flag_itself_is_never_in_the_data_block(self):
        self.action("Generated one")
        text = self.built()["body"].decode("utf-8")
        found = re.findall(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S)
        self.assertEqual(len(found), 1)
        self.assertNotIn("client_action", found[0])
        self.assertIn("Generated one", found[0], "the item itself is published by the usual rules")

    def test_the_stored_flag_is_untouched_by_a_build(self):
        action = self.action("Generated one")
        self.built()
        self.assertEqual(self.s.read("actions", ref=action)["client_action"], 1)


if __name__ == "__main__":
    unittest.main()

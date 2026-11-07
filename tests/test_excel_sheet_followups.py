"""#655: Excel import lets the person choose which sheets to import. Run: python3 dev/run_tests.py test_excel_sheet_followups
#912: the Followups tests, split from test_excel_sheet_choice.
"""
import json
import time
import unittest

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_excel_route import encoded
from _sheet_choice_base import *  # noqa: F401,F403
from _sheet_choice_base import Cached, Sheets, TABLES, SHEET, add_row
from clark import excel_import, excel_route


class Followups(Cached):
    """Issue 723: what a "sheets" call with no check after it leaves behind. A fake clock (self.now) is used, so nothing waits."""

    def listed(self):
        status, got = self.post(op="sheets", project="ABC", name="ABC work items.xlsx", data=encoded(self.path))
        self.assertEqual(status, 200, got)
        return got["file"]

    def test_a_held_workbook_with_no_check_goes_after_the_wait_and_not_before(self):
        key = self.listed()
        held = excel_route.PLANS[key]
        self.assertTrue(held["dir"].exists())
        self.assertEqual(held["timer"].interval, excel_route.PLAN_MINUTES * 60 + 5)   # the timer runs just after the calls' own limit
        self.now[0] += excel_route.PLAN_MINUTES * 60                                  # exactly the wait: still held
        self.assertEqual(self.post(op="check", project="ABC", file=key, sheets=["actions"])[0], 200)
        self.now[0] += excel_route.PLAN_MINUTES * 60 + 1                              # (the check above held it again from now)
        self.assertEqual(self.post(op="check", project="ABC", file=key, sheets=["actions"])[0], 410)
        self.assertEqual((excel_route.PLANS, held["dir"].exists()), ({}, False))

    def test_a_held_workbook_with_no_check_goes_when_its_timer_runs_with_no_later_call(self):
        key = self.listed()
        held = excel_route.PLANS[key]
        excel_route._expire_one(key, held)
        self.assertEqual((excel_route.PLANS, held["dir"].exists()), ({}, False))

    def test_a_new_workbook_pushes_out_a_held_file_before_a_plan_waiting_for_apply(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        self.now[0] += 1
        plan = self.check()[1]["plan"]                                                 # the oldest of all
        files = []
        for _ in range(excel_route.MAX_PLANS - 1):
            self.now[0] += 1
            files.append(self.listed())
        self.assertEqual(len(excel_route.PLANS), excel_route.MAX_PLANS)
        self.now[0] += 1
        newest = self.listed()
        self.assertEqual(len(excel_route.PLANS), excel_route.MAX_PLANS)
        self.assertIn(plan, excel_route.PLANS)
        self.assertNotIn(files[0], excel_route.PLANS)                                  # the oldest file went
        self.assertIn(newest, excel_route.PLANS)
        status, done = self.apply(plan)
        self.assertEqual((status, done["ok"]), (200, True), done)

    def test_when_every_held_one_is_a_plan_the_oldest_plan_still_goes(self):
        self.edit("Actions", self.a1, Description="Draft the cut-over plan, version two")
        plans = []
        for _ in range(excel_route.MAX_PLANS):
            self.now[0] += 1
            plans.append(self.check()[1]["plan"])
        self.now[0] += 1
        self.listed()
        self.assertNotIn(plans[0], excel_route.PLANS)
        self.assertEqual(len(excel_route.PLANS), excel_route.MAX_PLANS)


if __name__ == "__main__":
    unittest.main()

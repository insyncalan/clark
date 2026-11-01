"""#240: each row of an item's Activity says whether the undo of several will take it (`undoable`), and when not, why in a plain line
(`why`). The answer is changes._ours, the rule that undo applies, so the tab never offers a tick the server refuses.

Run: python3 dev/run_tests.py test_activity_undoable
Each test makes a real store in a temporary folder with fictional data.
"""
import json
import re
import shutil
import subprocess
import unittest

from _demo import USER, DemoStore
from _paths import ROOT
from clark import activity_read, changes

JS = ROOT / "src" / "clark" / "page" / "src" / "edit" / "activityUndo.js"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.a = self.demo.action()
        self.read = activity_read.make_read(self.s.path, self.s.data_for)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def step(self, route, actor="you", **fields):
        """One step by `route` that changes the action, as the other routes do; its id."""
        with self.s.step(route, USER, actor=actor) as st:
            st.update("actions", self.a, fields)
        return self.demo.last_step()

    def rows(self):
        return self.read("ABC", self.a)["rows"]

    def row_of(self, step):
        return [r for r in self.rows() if r["step"] == step]


class TheFlag(Base):
    def test_a_dashboard_step_is_tickable_and_has_no_why(self):
        s = self.step("dashboard", owner="Sam Example")
        rows = self.row_of(s)
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual((r["undoable"], r["why"]), (True, ""))

    def test_a_step_from_another_route_is_not_tickable_and_says_why(self):
        for route in ("excel", "client", "team", "migrate", "word"):
            s = self.step(route, owner=f"Sam {route}")
            rows = self.row_of(s)
            self.assertTrue(rows, route)
            for r in rows:
                self.assertEqual((r["undoable"], r["why"]), (False, changes.NOT_FROM_HERE), route)

    def test_an_ask_step_is_tickable_only_when_ask_clark_made_it(self):
        foreign = self.step("assistant", actor="you", owner="Sam Example")
        ours = self.step("assistant", actor="clark", priority="High")
        self.assertEqual([(r["undoable"], r["why"]) for r in self.row_of(foreign)], [(False, changes.NOT_FROM_HERE)])
        self.assertEqual([(r["undoable"], r["why"]) for r in self.row_of(ours)], [(True, "")])

    def test_an_undo_is_not_tickable(self):
        s = self.step("dashboard", owner="Sam Example")
        status, body = self.undo({"project": "ABC", "apply_id": s})
        self.assertEqual(status, 200, body)
        rows = self.row_of(body["apply_id"])
        self.assertTrue(rows)
        for r in rows:
            self.assertFalse(r["undoable"])
            self.assertEqual(r["why"], changes.NOT_FROM_HERE)

    def test_the_answer_is_changes_ours_and_nothing_else(self):
        self.step("dashboard", owner="Sam Example")
        self.step("excel", priority="High")
        self.step("assistant", actor="you", status="Open")
        for r in self.rows():
            want = changes._ours(self.s, r["step"], self.s.step_rows(r["step"]), "ABC")
            self.assertEqual(r["undoable"], want, r)
            self.assertEqual(r["why"], "" if want else changes.NOT_FROM_HERE, r)

    def test_reading_writes_nothing(self):
        self.step("dashboard", owner="Sam Example")
        n = self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        self.rows()
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0], n)


class Parity(Base):
    def test_the_dry_run_takes_every_row_marked_and_refuses_every_row_not(self):
        steps = [self.step("dashboard", owner="Sam Example"), self.step("excel", priority="High"),
                 self.step("assistant", actor="you", status="Open"), self.step("assistant", actor="clark", due_date="2030-01-01"),
                 self.step("client", workstream="Build"), self.step("dashboard", description="Draft the plan")]
        by_step = {r["step"]: r["undoable"] for r in self.rows()}
        self.assertTrue(set(steps) <= set(by_step))
        self.assertTrue(any(by_step.values()) and not all(by_step.values()))
        for step, marked in sorted(by_step.items()):
            status, body = self.undo({"project": "ABC", "steps": [step], "preview": True})
            self.assertEqual(status, 200, body)
            refused = [e for e in body["skipped"] if e["why"] == changes.NOT_FROM_HERE]
            if marked:
                self.assertEqual(refused, [], step)
            else:
                self.assertEqual(body["undo"], [], step)
                self.assertTrue(refused, step)


class ThePage(unittest.TestCase):
    def test_the_page_greys_a_row_the_server_does_not_mark_and_shows_its_why(self):
        js = JS.read_text(encoding="utf-8")
        self.assertRegex(js, re.compile(r"r\.undoable === false\) return String\(r\.why \|\| WHY_NO_STEP\)"))
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        code = (f'import {{ whyNot, chooseable }} from "{JS.as_uri()}";'
                'const a = {step: 5, kind: "Changed", undoable: true, why: ""};'
                'const b = {step: 6, kind: "Changed", undoable: false, why: "Not from here."};'
                'const c = {step: 7, kind: "Changed"};'
                'console.log(JSON.stringify([whyNot(a), whyNot(b), whyNot(c), chooseable([a, b, c])]));')
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), ["", "Not from here.", "", ["5", "7"]])


if __name__ == "__main__":
    unittest.main()

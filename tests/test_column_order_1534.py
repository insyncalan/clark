"""Row 1534, PR 1: the column order of the work item tables is saved with the project (projects.column_orders, schema step 35).

Run: python3 dev/run_tests.py test_column_order_1534
Pins: one saved order for each work item table (actions, risks, issues, decisions), the same for the Work items page and that table's
Dashboard section; a different project or table keeps its own; the order is written by the one writer with Undo and a history line, is read
back from the file (so it survives a reload), and is refused when it is not a list of this table's columns starting with status then item.
The order has no browser key. The drag, the keyboard move and the menu are later PRs. Fictional data only.
"""
import json
import re
import unittest

from _demo import USER, DemoStore
from _paths import ROOT
from clark import changes, history, store as store_module

ORDER = ["status", "item", "due", "owner", "prio", "id"]
JS = ROOT / "src" / "clark" / "page" / "src" / "logic" / "tableColumns.js"


class Saved(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def save(self, value, project="ABC"):
        return self.change({"project": project, "kind": "projects", "op": "update", "changes": {"column_orders": value}})

    def stored(self, project="ABC"):
        return self.s.con.execute("SELECT column_orders FROM projects WHERE code = ?", (project,)).fetchone()[0]

    def test_column_order_is_published(self):
        self.assertEqual(self.stored(), "{}")
        status, body = self.save({"risks": ORDER, "actions": ORDER[:2] + ["owner"]})
        self.assertEqual((status, body.get("message")), (200, None), body)
        want = json.dumps({"actions": ["status", "item", "owner"], "risks": ORDER}, sort_keys=True, separators=(",", ":"))
        self.assertEqual(self.stored(), want)                       # in the file, not the browser: a reload reads this
        self.assertEqual(body["project"]["column_orders"], want)
        self.assertEqual(self.s.read("projects", ref="ABC")["column_orders"], want)
        self.assertNotIn("order", " ".join(re.findall(r'keyOf = [^\n]*', JS.read_text(encoding="utf-8"))), "no browser key for the order")

    def test_a_different_project_keeps_its_own_order(self):
        self.s.con.execute("INSERT INTO projects (code, name) VALUES ('XYZ', 'Second Programme')")
        self.assertEqual(self.save({"issues": ORDER})[0], 200)
        self.assertEqual(self.stored("XYZ"), "{}")
        self.assertEqual(self.stored(), json.dumps({"issues": ORDER}, separators=(",", ":")))

    def test_one_undo_puts_the_old_order_back_and_history_says_so(self):
        self.save({"risks": ORDER})
        status, body = self.save({"risks": ["status", "item", "id"]})
        status, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, back)
        self.assertEqual(back["words"], "Put back: the column order.")
        self.assertEqual(json.loads(self.stored()), {"risks": ORDER})
        self.assertEqual(history.FIELD_NAMES["projects"]["column_orders"], "Column order")

    def test_the_standard_order_is_saved_as_nothing(self):
        self.save({"risks": ORDER})
        self.assertEqual(self.save({})[0], 200)
        self.assertEqual(self.stored(), "{}")

    def test_a_bad_order_is_refused_and_nothing_is_written(self):
        bad = [{"milestones": ORDER}, {"use_cases": ORDER}, {"risks": ["item", "status"]}, {"risks": ["owner", "status", "item"]},
               {"risks": ["status", "item", "item"]}, {"risks": ["status", "item", "nope"]}, {"risks": "status,item"}, {"risks": ["status", "item", 3]},
               {"risks": []}, ["status", "item"], "[1]", "not json", None, 5, True, {"risks": ORDER + ORDER}, {"risks": None}]
        for value in bad:
            with self.subTest(value=value):
                before = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                status, body = self.save(value)
                self.assertEqual((status, body["ok"]), (400, False))
                self.assertEqual(body["message"], store_module.COLUMN_ORDERS_BAD)
                self.assertEqual(self.stored(), "{}")
                self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], before)

    def test_the_text_is_the_same_whatever_the_spelling(self):
        a = store_module.column_orders({"risks": ORDER, "actions": ORDER})
        self.assertEqual(a, store_module.column_orders(json.dumps({"actions": ORDER, "risks": ORDER}, indent=2)))
        self.assertEqual(store_module.column_orders(a), a)

    def test_the_ids_are_the_ids_of_the_pages_work_table(self):
        text = JS.read_text(encoding="utf-8")
        work = text[text.index("work: ["):text.index("uc: [")]
        self.assertEqual(tuple(re.findall(r'id: "([a-z]+)"', work)), store_module.WORK_COLUMN_IDS)


if __name__ == "__main__":
    unittest.main()

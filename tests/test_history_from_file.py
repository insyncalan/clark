"""Row 1009 part 1: Activity says where an update came from. An item an Excel or Word file CHANGED reads
'Updated from <file>, <date>, by <name>' (', by <name>' left out when the name is empty); a Word-route row's how is
'By Word import (<file>)'; the Created row keeps its own wording and the first source stays."""
import unittest

from _demo import USER, DemoStore
from clark import activity_read, history

DATE = "03-02-2026"


class FromFile(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.con = self.demo.store.con
        self.action = self.demo.action()

    def change(self, route, src_ref, who=USER, **fields):
        with self.demo.store.step(route, who, place=None if route == "word" else route, src_ref=src_ref) as st:
            st.update("actions", self.action, fields)
        step = self.demo.last_step()
        self.con.execute("UPDATE change_log SET at = ? WHERE apply_id = ?", ("2026-02-03 10:00:00.000", step))
        self.con.commit()

    def changed(self):
        return [r for r in history.rows_for_project(self.con, "ABC") if r["kind"] == "Changed"]

    def test_word_how_text(self):
        self.assertEqual(history.how_text("word", None, "Added from Word (plan.docx)"), "By Word import (plan.docx)")
        self.assertEqual(history.how_text("word", None, "Added from Word (C:\\x\\a  b.docx)"), "By Word import (a b.docx)")
        self.assertEqual(history.how_text("word", None, None), "By Word import")

    def test_excel_update_row_says_it(self):
        self.change("excel", "by Excel import (plan.xlsx)", priority="High")
        r = self.changed()[0]
        self.assertEqual(r["from_file"], f"Updated from plan.xlsx, {DATE}, by {USER}")
        self.assertEqual(r["how"], "By Excel import (plan.xlsx)")

    def test_word_update_row_says_it(self):
        self.change("word", "Added from Word (notes.docx)", priority="High")
        r = self.changed()[0]
        self.assertEqual(r["from_file"], f"Updated from notes.docx, {DATE}, by {USER}")
        self.assertEqual(r["how"], "By Word import (notes.docx)")

    def test_empty_name_omits_by(self):
        self.assertEqual(history.updated_from("plan.xlsx", "03-02-2026 10:00", ""), "Updated from plan.xlsx, 03-02-2026")
        self.assertEqual(history.updated_from("plan.xlsx", "03-02-2026 10:00", None), "Updated from plan.xlsx, 03-02-2026")
        self.assertEqual(history.updated_from("plan.xlsx", "03-02-2026 10:00", "  "), "Updated from plan.xlsx, 03-02-2026")

    def test_first_source_stays_and_other_routes_have_no_sentence(self):
        self.change("excel", "by Excel import (plan.xlsx)", priority="High")
        self.change("word", "Added from Word (notes.docx)", priority="Low")
        with self.demo.store.step("dashboard", USER, place="peek") as st:
            st.update("actions", self.action, {"owner": "Sam Example"})
        rows = history.rows_for_project(self.con, "ABC")
        created = [r for r in rows if r["kind"] == "Created" and r["item_id"] == self.action][0]
        self.assertEqual(created["from_file"], "")
        self.assertNotIn("Excel", created["how"] + "Word" * ("Word" in created["how"]))
        by_field = {r["field"]: r for r in rows if r["kind"] == "Changed"}
        self.assertEqual(by_field["Owner"]["from_file"], "")
        self.assertEqual(len([r for r in rows if r["kind"] == "Changed" and r["from_file"]]), 2)
        self.assertEqual({r["from_file"] for r in rows if r["from_file"]},
                         {f"Updated from plan.xlsx, {DATE}, by {USER}", f"Updated from notes.docx, {DATE}, by {USER}"})

    def test_tab_row_carries_it_only_when_there_is_one(self):
        self.change("excel", "by Excel import (plan.xlsx)", priority="High")
        row = activity_read._row(dict(self.changed()[0], undo_refused=""))
        self.assertIn("from_file", row)
        row = activity_read._row(dict(self.changed()[0], from_file="", undo_refused=""))
        self.assertNotIn("from_file", row)


if __name__ == "__main__":
    unittest.main()

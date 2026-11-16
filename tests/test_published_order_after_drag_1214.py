"""Row 1214: after a drag on the editor dashboard (one change: a move, with the flags of the pair it makes or breaks), the published page
lists its sections in the editor's new order, pairs included, and the Gantt sections (rows 926, 928 and 1068: the chart and the table)
sit where the drag put them. Over a real store, the real change handler and the real build. Fictional data.

Run: python3 dev/run_tests.py test_published_order_after_drag_1214
"""
import unittest

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import changes, publish

NOW = "2030-01-15"
KIND = "report_sections"


class AfterDrag(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.ids = {}
        with self.s.step("dashboard", USER) as st:
            for old in self.s.read(KIND, project="ABC"):
                st.cancel(KIND, old["id"])
            st.update("projects", "ABC", {"show_gantt_client": 1, "show_gantt_editor": 1})
            for n, (kind, title) in enumerate([("text", "Intro"), ("gantt", "Plan chart"), ("gantttable", "Plan table"),
                                               ("text", "Middle"), ("text", "Closing")], 1):
                self.ids[title] = st.create(KIND, {"project": "ABC", "type": kind, "title": title, "body": "<p>%s words</p>" % title if kind == "text" else "",
                                                   "sort_order": 1024 * n, "beside": 0, "hidden": 0})
            st.create("gantt_lines", {"project": "ABC", "type": "task", "name": "Dig", "start": "2030-01-02", "end": "2030-01-20", "pct": 0,
                                      "show": 1, "sort_order": 1024})

    def move(self, title, before, flags=None):
        req = {"project": "ABC", "kind": KIND, "op": "move", "id": self.ids[title], "before": self.ids[before] if before else None, "place": "report"}
        if flags:
            req["flags"] = {self.ids[k]: v for k, v in flags.items()}
        status, body = self.change(req)
        self.assertEqual((status, body.get("message")), (200, None), body)

    def editor(self):
        rows = sorted(self.s.read(KIND, project="ABC"), key=lambda r: (r["sort_order"], r["id"]))
        return [(r["title"], r["beside"]) for r in rows if not r["hidden"]]

    def published(self):
        built = publish.build(self.s, "ABC", now=NOW)["published"]
        return [(s["title"], s["beside"]) for s in built["sections"]]

    def test_the_file_starts_in_the_editor_order_with_the_gantt_sections_in(self):
        self.assertEqual(self.published(), self.editor())
        self.assertIn(("Plan chart", 0), self.published())
        self.assertIn(("Plan table", 0), self.published())

    def test_one_drag_of_a_text_section_to_the_top_moves_it_in_the_file_too(self):
        self.move("Closing", "Intro")
        self.assertEqual([t for t, _ in self.editor()], ["Closing", "Intro", "Plan chart", "Plan table", "Middle"])
        self.assertEqual(self.published(), self.editor())

    def test_one_drag_of_the_gantt_chart_past_the_table_and_the_table_to_the_end(self):
        self.move("Plan chart", "Middle")
        self.assertEqual([t for t, _ in self.published()], ["Intro", "Plan table", "Plan chart", "Middle", "Closing"])
        self.move("Plan table", None)
        self.assertEqual([t for t, _ in self.published()], ["Intro", "Plan chart", "Middle", "Closing", "Plan table"])
        self.assertEqual(self.published(), self.editor())

    def test_a_drag_that_makes_a_pair_puts_the_pair_in_the_file(self):
        """Closing dropped on the right half of Middle: one move, the flag on Middle (the left half of a pair carries it)."""
        self.move("Closing", None, {"Middle": 1})
        self.assertEqual(self.editor()[-2:], [("Middle", 1), ("Closing", 0)])
        self.assertEqual(self.published(), self.editor())

    def test_a_drag_that_breaks_a_pair_leaves_both_alone_in_the_file(self):
        self.move("Closing", None, {"Middle": 1})
        self.move("Closing", "Intro", {"Middle": 0})
        self.assertEqual([t for t, _ in self.editor()][:2], ["Closing", "Intro"])
        self.assertTrue(all(b == 0 for _, b in self.published()))
        self.assertEqual(self.published(), self.editor())

    def test_a_hidden_section_stays_out_of_the_file_after_a_drag_over_it(self):
        with self.s.step("dashboard", USER) as st:
            st.update(KIND, self.ids["Middle"], {"hidden": 1})
        self.move("Closing", "Plan chart")
        self.assertNotIn("Middle", [t for t, _ in self.published()])
        self.assertEqual(self.published(), self.editor())

    def test_the_gantt_chart_dragged_beside_a_text_section_is_paired_in_the_file(self):
        self.move("Plan chart", None, {"Closing": 1, "Plan chart": 0})
        self.assertEqual(self.published(), self.editor())
        self.assertEqual(self.published()[-2:], [("Closing", 1), ("Plan chart", 0)])


if __name__ == "__main__":
    unittest.main()

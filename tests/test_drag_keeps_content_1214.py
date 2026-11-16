"""Row 1214: a drag moves a section and sets the beside flags, and changes nothing else. Over a real store and the real change handler,
every section keeps its type, title, body and hidden flag, the project keeps its Gantt settings and the Gantt lines stay as they were, and one
Undo puts the whole layout back. Fictional data.

Run: python3 dev/run_tests.py test_drag_keeps_content_1214
"""
import unittest

import _paths  # noqa: F401
from _demo import USER, DemoStore
from clark import changes

KIND = "report_sections"
LAYOUT = ("sort_order", "beside")


class DragKeepsContent(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.ids = {}
        with self.s.step("dashboard", USER) as st:
            for old in self.s.read(KIND, project="ABC"):
                st.cancel(KIND, old["id"])
            st.update("projects", "ABC", {"show_gantt_client": 1, "show_gantt_editor": 1})
            for n, (kind, title, hidden) in enumerate([("text", "Intro", 0), ("gantt", "Plan chart", 0), ("gantttable", "Plan table", 0),
                                                       ("text", "Middle", 0), ("text", "Closing", 0), ("text", "Aside", 1)], 1):
                self.ids[title] = st.create(KIND, {"project": "ABC", "type": kind, "title": title, "hidden": hidden,
                                                   "body": "<p>%s words</p>" % title if kind == "text" else "",
                                                   "sort_order": 1024 * n, "beside": 0})
            st.create("gantt_lines", {"project": "ABC", "type": "task", "name": "Dig", "start": "2030-01-02", "end": "2030-01-20", "pct": 0,
                                      "show": 1, "sort_order": 1024})

    def sections(self):
        return {r["title"]: dict(r) for r in self.s.read(KIND, project="ABC")}

    def rest(self):
        """Everything a drag must not touch: each section without its layout fields, the project row and the Gantt lines."""
        secs = {t: {k: v for k, v in r.items() if k not in LAYOUT} for t, r in self.sections().items()}
        return secs, dict(self.s.read("projects", ref="ABC")), [dict(r) for r in self.s.read("gantt_lines", project="ABC")]

    def move(self, title, before, flags=None):
        req = {"project": "ABC", "kind": KIND, "op": "move", "id": self.ids[title], "before": self.ids[before] if before else None, "place": "report"}
        if flags:
            req["flags"] = {self.ids[k]: v for k, v in flags.items()}
        status, body = self.change(req)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def test_moves_up_down_and_into_a_pair_change_no_content_and_no_setting(self):
        start = self.rest()
        self.move("Closing", "Intro")                                   # up
        self.move("Plan chart", "Aside")                                # a Gantt section down to the end
        self.move("Intro", "Aside", {"Plan chart": 1})                 # beside the chart, half width each
        self.assertEqual(self.sections()["Plan chart"]["beside"], 1, "the drop did make the pair")
        self.assertEqual(self.rest(), start)

    def test_a_pair_made_and_broken_keeps_the_body_of_both_halves(self):
        start = self.rest()
        self.move("Closing", "Aside", {"Middle": 1})
        self.move("Closing", "Intro", {"Middle": 0})
        self.assertEqual(self.rest(), start)
        self.assertEqual(self.sections()["Intro"]["body"], "<p>Intro words</p>")

    def test_a_hidden_section_stays_hidden_when_another_is_dragged_past_it(self):
        self.move("Closing", "Aside")
        self.move("Intro", "Aside")
        self.assertEqual(self.sections()["Aside"]["hidden"], 1)

    def test_one_undo_puts_the_layout_and_the_rest_back(self):
        before = self.sections()
        body = self.move("Closing", "Aside", {"Middle": 1})
        self.assertNotEqual(self.sections(), before)
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, undone)
        self.assertEqual(self.sections(), before)


if __name__ == "__main__":
    unittest.main()

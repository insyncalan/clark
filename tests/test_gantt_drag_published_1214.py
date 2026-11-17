"""Row 1214 (with rows 926, 928 and 1068): the same drag on the sections that hold the Gantt, in real headless Chrome at 1400 and 900 px.
The Gantt chart and the Gantt table are sections of the dashboard's list, so a real mouse drag of one of them is stored as one move, and the
published file lists the sections in the order the drag left in the store. Real server, real change handler, real store and real build; fictional data.
Run: python3 dev/run_tests.py test_gantt_drag_published_1214
"""
import unittest

import test_report_editor as tre
from _demo import USER
from clark import publish
from test_server import chrome

KIND = "report_sections"
NOW = "2030-01-15"
TITLES = ["Intro", "Plan chart", "Plan table", "Middle", "Closing"]


class GanttDrag(tre.Base):
    def setUp(self):
        super().setUp()
        self.ids = {}
        with self.store.step("dashboard", USER) as st:
            for old in self.store.read(KIND, project="ABC"):
                st.cancel(KIND, old["id"])
            st.update("projects", "ABC", {"show_gantt_client": 1, "show_gantt_editor": 1})
            for n, (kind, title) in enumerate(zip(["text", "gantt", "gantttable", "text", "text"], TITLES), 1):
                self.ids[title] = st.create(KIND, {"project": "ABC", "type": kind, "title": title, "body": "<p>%s words</p>" % title if kind == "text" else "",
                                                   "sort_order": 1024 * n, "beside": 0, "hidden": 0})
            st.create("gantt_lines", {"project": "ABC", "type": "task", "name": "Dig", "start": "2030-01-02", "end": "2030-01-20", "pct": 0,
                                      "show": 1, "sort_order": 1024})

    def published(self):
        return [s["title"] for s in publish.build(self.store, "ABC", now=NOW)["published"]["sections"]]

    def test_a_real_drag_of_the_gantt_chart_is_stored_and_published_in_the_same_order(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                with self.store.step("dashboard", USER) as st:             # the same start at each width
                    for n, title in enumerate(TITLES, 1):
                        st.update(KIND, self.ids[title], {"sort_order": 1024 * n, "beside": 0})
                p = self.visit(cdp)
                p.tall(cdp, width)
                p.edit()
                self.assertEqual(p.ids(), [self.ids[t] for t in TITLES], "the Gantt sections are in the editor's list")
                self.assertEqual(self.published(), TITLES)
                rect = p.rect(self.ids["Closing"])
                p.drag(self.ids["Plan chart"], (rect["left"] + rect["right"]) / 2, rect["bottom"] - 2)       # the bottom edge of Closing: a row of its own after it
                want = ["Intro", "Plan table", "Middle", "Closing", "Plan chart"]
                p.order_is([self.ids[t] for t in want])
                self.assertEqual(self.titles_in_store(), want, "the store has the drag")
                self.assertEqual(self.published(), want, "the published file has the order the store has")

    def test_a_drop_above_another_row_keeps_its_place_in_the_editor_the_store_and_the_published_file(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                with self.store.step("dashboard", USER) as st:
                    for n, title in enumerate(TITLES, 1):
                        st.update(KIND, self.ids[title], {"sort_order": 1024 * n, "beside": 0})
                p = self.visit(cdp)
                p.tall(cdp, width)
                p.edit()
                rect = p.rect(self.ids["Middle"])
                p.drag(self.ids["Plan chart"], (rect["left"] + rect["right"]) / 2, rect["top"] + 2)           # the top edge of Middle: a row of its own before it
                want = ["Intro", "Plan table", "Plan chart", "Middle", "Closing"]
                p.order_is([self.ids[t] for t in want])
                self.assertEqual(self.titles_in_store(), want, "the store has the drop above Middle, not at the end")
                self.assertEqual(self.published(), want, "the published file has the same order")


if __name__ == "__main__":
    unittest.main()

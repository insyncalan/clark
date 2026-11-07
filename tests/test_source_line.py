"""#1009 parts 2 and 3: the Peek's read-only Source line. Edit only: it comes from GET /api/activity (activity_read.py), is drawn by
the Edit part (PeekActivity.jsx) and is in no published file.
Run: PYTHONPATH=../src:. python3 test_source_line.py"""
import unittest
from pathlib import Path

from _paths import SRC
import _publish_fixture as fx  # noqa: F401
from _demo import USER, DemoStore
from clark import activity_read
from test_publish_route import USER as PUB_USER, WANTED, Rig

MARK = "ZQ-SOURCE-FILE-6631 Acme Corp plan.xlsx"


class TheLine(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        s = self.demo.store
        self.read = activity_read.make_read(s.path, s.data_for)

    def source(self, ref):
        return self.read("ABC", ref)["source"]

    def test_by_hand_names_the_creator(self):
        a = self.demo.action(source="Added by hand in clark")
        self.assertEqual(self.source(a), "Added by hand in clark by " + USER)

    def test_an_import_line_keeps_its_words_and_adds_by(self):
        a = self.demo.action(source="Excel import, 2026-10-01, plan.xlsx")
        self.assertEqual(self.source(a), "Excel import, 2026-10-01, plan.xlsx by " + USER)

    def test_a_later_editor_is_not_the_creator(self):
        a = self.demo.action(source="demo")
        with self.demo.store.step("dashboard", "Someone Else") as st:
            st.update("actions", a, {"priority": "High"})
        self.assertEqual(self.source(a), "demo by " + USER)

    def test_no_creator_step_shows_no_by(self):
        a = self.demo.action(source="demo")
        con = self.demo.store.con
        con.execute("UPDATE applies SET by_user = ''")
        con.commit()
        self.assertEqual(self.source(a), "demo")

    def test_a_milestone_and_a_decision_have_it_too(self):
        self.assertTrue(self.source(self.demo.milestone).endswith(" by " + USER) or self.source(self.demo.milestone))

    def test_the_text_is_data_not_markup_and_nothing_else_is_added(self):
        a = self.demo.action(source="<b>x</b>")
        self.assertEqual(self.source(a), "<b>x</b> by " + USER)

    def test_the_read_still_has_its_other_keys(self):
        a = self.demo.action()
        self.assertEqual(set(self.read("ABC", a)), {"rows", "empty", "closing", "source"})


class NotPublished(unittest.TestCase):
    def test_the_source_text_is_in_no_published_file(self):
        rig = Rig(self)
        with rig.store.step("dashboard", PUB_USER) as st:
            st.create("actions", {"project": "PUB", "description": "Check the rota", "raised": "2026-10-01", "source": "Excel import, 2026-10-01, " + MARK,
                                  "client_visible": 1})
        status, got = rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        for folder in (rig.local / "chosen.html", rig.client / WANTED):
            text = Path(folder).read_bytes().decode("utf-8")
            for bit in (MARK, "ZQ-SOURCE-FILE-6631", "Excel import, 2026-10-01", "Source line"):
                self.assertNotIn(bit, text, folder)

    def test_the_page_text_for_the_line_is_edit_only(self):
        src = Path(SRC) / "clark" / "page" / "src"
        self.assertIn("source", (src / "edit" / "PeekActivity.jsx").read_text(encoding="utf-8"))
        for f in ("components/Peek.jsx", "components/ItemFields.jsx"):
            p = src / f
            if p.exists():
                self.assertNotIn("data-pk-source", p.read_text(encoding="utf-8"))


    def test_the_view_page_has_no_source_line(self):
        built = Path(SRC) / "clark" / "page" / "page-view.html"
        if built.exists():
            self.assertNotIn("data-pk-source", built.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

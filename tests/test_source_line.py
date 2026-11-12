"""#1009 parts 2 and 3: the Peek's read-only Source line, from GET /api/activity (activity_read.py) on the live page. Row 1077 (the
owner's ruling of 10-11-2026): the line is shown by NAME everywhere, a path never: the live page strips a path to its last part, and a
published file carries the name (publish.select through source_name), drawn by the shared SourceLine (components/Peek.jsx).
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
        self.assertEqual(self.source(a), "Excel import, 01-10-2026, plan.xlsx by " + USER)

    def test_a_word_import_date_is_shown_day_first(self):
        a = self.demo.action(source="Word import, 2026-11-07, notes.docx, under Risks")
        self.assertEqual(self.source(a), "Word import, 07-11-2026, notes.docx, under Risks by " + USER)

    def test_the_stored_column_is_not_changed(self):
        a = self.demo.action(source="Excel import, 2026-10-01, plan.xlsx")
        self.source(a)
        row = self.demo.store.con.execute("SELECT source FROM actions WHERE id = ?", (a,)).fetchone()
        self.assertEqual(row[0], "Excel import, 2026-10-01, plan.xlsx")

    def test_digits_that_are_not_a_date_stay_as_they_are(self):
        for text in ("Ref 12345-67-89 from the PMO", "Ticket 2026-13-45 filed", "Batch 20261001 and 2026-10-1", "Added by hand in clark"):
            a = self.demo.action(source=text)
            self.assertEqual(self.source(a), text + " by " + USER, text)

    def test_no_words_shows_no_by_even_with_a_creator(self):
        a = self.demo.action(source="demo")
        con = self.demo.store.con
        con.execute("UPDATE actions SET source = '' WHERE id = ?", (a,))      # the store requires words; an old row may hold none
        con.commit()
        self.assertEqual(self.source(a), "")

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
        # The read gives every kind the same line; the Peek draws it for items only (Peek.jsx `forItem`), not for milestones.
        self.assertEqual(self.source(self.demo.milestone), "demo by " + USER)
        with self.demo.store.step("dashboard", USER) as st:
            d = st.create("decisions", {"project": "ABC", "decision": "Go with option B", "status": "Pending", "source": "Excel import, 2026-11-07, log.xlsx"})
        self.assertEqual(self.source(d), "Excel import, 07-11-2026, log.xlsx by " + USER)

    def test_a_path_in_the_stored_words_shows_its_last_part_only(self):
        # row 1077: the name, never the path (the column keeps the path)
        a = self.demo.action(source="Excel import, 2026-10-01, /Volumes/share/ZQ-FOLDER/plan.xlsx")
        self.assertEqual(self.source(a), "plan.xlsx by " + USER, "row 1077, strict: a path publishes only its file name, no prefix words")
        row = self.demo.store.con.execute("SELECT source FROM actions WHERE id = ?", (a,)).fetchone()
        self.assertIn("ZQ-FOLDER", row[0])

    def test_the_text_is_data_not_markup_and_nothing_else_is_added(self):
        a = self.demo.action(source="<b>x</b>")
        self.assertEqual(self.source(a), "", "row 1077 (W27): a source is a name, not markup; markup is not plain words, so nothing is shown")
        b = self.demo.action(source="<i>notes</i>.xlsx")
        self.assertEqual(self.source(b), "")

    def test_the_read_still_has_its_other_keys(self):
        a = self.demo.action()
        self.assertEqual(set(self.read("ABC", a)), {"rows", "empty", "closing", "source"})


class PublishedByName(unittest.TestCase):
    """Row 1077 (ruled 10-11-2026, reversing #1009's 'in no published file'): a published file carries the source NAME, never its path, never
    the creator's name after it, and the date day first."""
    def test_the_source_name_is_in_a_published_file_and_its_path_is_not(self):
        rig = Rig(self)
        with rig.store.step("dashboard", PUB_USER) as st:
            st.create("actions", {"project": "PUB", "description": "Check the rota", "raised": "2026-10-01", "client_visible": 1,
                                  "source": "Excel import, 2026-10-01, /Volumes/share/ZQ-SECRET-FOLDER, Inc/sub/" + MARK})   # a comma inside the path (reader A)
        status, got = rig.publish(to_client=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        for folder in (rig.local / "chosen.html", rig.client / WANTED):
            text = Path(folder).read_bytes().decode("utf-8")
            self.assertIn(MARK, text, folder)
            for bit in ("ZQ-SECRET-FOLDER", "ZQ-SECRET-FOLDER, Inc", "Inc/", "sub/" + MARK, "/Volumes", MARK + " by ", "Excel import, 2026-10-01", "Excel import, 01-10-2026"):
                self.assertNotIn(bit, text, folder)

    def test_the_line_is_one_shared_piece_drawn_by_the_edit_part_too(self):
        src = Path(SRC) / "clark" / "page" / "src"
        peek = (src / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("export function SourceLine", peek)
        self.assertEqual(peek.count("data-pk-source"), 1)
        edit = (src / "edit" / "PeekActivity.jsx").read_text(encoding="utf-8")
        self.assertIn("SourceLine", edit)
        self.assertNotIn("data-pk-source", edit, "one piece of markup, in the shared component")

    def test_the_view_page_draws_the_line_from_its_data_and_asks_no_server(self):
        built = Path(SRC) / "clark" / "page" / "page-view.html"
        if built.exists():
            text = built.read_text(encoding="utf-8")
            self.assertIn("data-pk-source", text)
            self.assertNotIn("/api/activity", text)


if __name__ == "__main__":
    unittest.main()

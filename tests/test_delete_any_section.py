"""Row 906: any section may be deleted and a built-in one added again (src/clark/changes.py, store.py and publish.py: guarded).

Run: python3 dev/run_tests.py test_delete_any_section
A section's row goes and comes back with Undo; the records a built-in section shows (milestones, risks, actions, decisions, use cases,
documents, the glance tiles, the current state) are never touched. A deleted built-in is carried nowhere in the published file.
"""
import sqlite3
import unittest

from _demo import USER
from clark import as_at, changes, client_filters, excel_cover, glance, publish, store as store_module
from test_changes import Api, KIND

DATA_TABLES = ("milestones", "actions", "raid", "decisions", "use_cases", "documents", "glance_tiles", "report_hidden", "people", "projects")
BUILT_INS = ("current", "glance", "usecases", "milestones", "raid", "actions", "decisions", "docs")


class Base(Api):
    def counts(self):
        con = sqlite3.connect(str(self.path))
        try:
            out = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in DATA_TABLES}
            out["current_state"] = con.execute("SELECT current_state FROM projects WHERE code = 'ABC'").fetchone()[0]
            return out
        finally:
            con.close()

    def store_needs_row(self):
        con = sqlite3.connect(str(self.path))
        try:
            con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) SELECT 'ABC', 'ABC-S-500', 'needs', 'Made for the test', COALESCE(MAX(sort_order), 0) + 1000 FROM report_sections WHERE project = 'ABC'")
            con.commit()
        finally:
            con.close()

    def of_type(self, kind):
        return [r for r in self.rows() if r["type"] == kind]

    def build(self):
        return publish.build(self.s, "ABC", now="2030-01-15")


class RoundTrip(Base):
    def test_every_type_deletes_and_undo_restores_the_row_and_no_data_table_changes(self):
        for t in ("text",) + tuple(store_module.BODY_TYPES) + BUILT_INS:
            with self.subTest(type=t):
                if not self.of_type(t):
                    if t == "needs":      # item 1158: the page no longer adds a Needs from you section, but one already stored is still a section that can be deleted and undone
                        self.store_needs_row()
                    else:
                        self.ok("new", values={"type": t, "title": "Made for the test"})
                row = self.of_type(t)[0]
                before_rows, before_data = self.s.read(KIND, "ABC"), self.counts()
                gone = self.ok("delete", id=row["id"])
                self.assertNotIn(row["id"], self.ids_now())
                self.assertEqual(self.counts(), before_data, "no record, tile or current state went with the section")
                self.assertEqual(self.undone(gone["apply_id"])[0], 200)
                self.assertEqual(sorted(self.s.read(KIND, "ABC"), key=lambda r: r["id"]), sorted(before_rows, key=lambda r: r["id"]))
                self.assertEqual(self.counts(), before_data)

    def test_each_built_in_is_deleted_by_the_route_with_the_toast_words_and_one_undo(self):
        for t in BUILT_INS:
            with self.subTest(type=t):
                row = self.of_type(t)[0]
                got = self.ok("delete", id=row["id"])
                self.assertIsNotNone(got["apply_id"], "the page shows Undo")
                self.assertEqual([r["type"] for r in self.rows()].count(t), 0)
                self.undone(got["apply_id"])
                self.assertEqual(len(self.of_type(t)), 1)

    def test_a_stale_id_and_another_projects_section_are_refused_alike(self):
        self.refused(self.req("delete", id="ABC-S-999"), changes.NOT_MINE)
        self.refused(self.req("delete", id="ZZZ-S-001"), changes.NOT_MINE)


class Publish(Base):
    def test_a_deleted_milestones_or_risks_section_leaves_nothing_of_it_in_the_file(self):
        with self.s.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High", "likelihood": "High",
                               "raised": "2026-10-01", "source": "demo"})
        self.demo.action(due_date="2030-02-01")
        with_all = self.build()["published"]
        self.assertTrue(with_all["data"]["milestones"] and with_all["data"]["raid"] and with_all["data"]["actions"])
        self.ok("delete", id=self.of_type("milestones")[0]["id"])
        self.ok("delete", id=self.of_type("raid")[0]["id"])
        got = self.build()["published"]
        self.assertEqual((got["data"]["milestones"], got["data"]["raid"]), ([], []))
        self.assertNotIn("milestones", got["tabs"])
        self.assertNotIn("clientreport", got["tabs"])
        self.assertTrue(got["data"]["actions"], "a section that stays keeps its data")

    def test_a_deleted_current_state_glance_and_documents_section_carry_nothing(self):
        self.ok("delete", id=self.of_type("current")[0]["id"])
        self.ok("delete", id=self.of_type("docs")[0]["id"])
        got = self.build()["published"]
        self.assertEqual((got["data"]["project"]["current_state"], got["data"]["documents"]), ("", []))
        self.assertFalse({"current", "docs"} & {s["type"] for s in got["sections"]})

    def test_deleting_every_section_does_not_bring_the_default_sections_back(self):
        for r in self.rows():
            self.ok("delete", id=r["id"])
        self.assertEqual(self.rows(), [])
        got = self.build()["published"]
        self.assertEqual(got["sections"], [])
        self.assertEqual([got["data"][k] for k in ("milestones", "raid", "actions", "decisions", "use_cases")], [[]] * 5)
        self.assertEqual(got["tabs"], ["dashboard"])
        kept = glance.kept_from(got, [], True)
        self.assertEqual(kept["hidden_types"], set(publish.BUILT_IN_SECTIONS))

    def test_the_next_change_after_deleting_every_section_does_not_seed_the_defaults(self):
        for r in self.rows():
            self.ok("delete", id=r["id"])
        self.ok("new", values={"type": "text", "title": "Only this"})
        self.assertEqual(self.titles(), ["Only this"])

    def test_no_sections_ever_still_means_the_defaults(self):
        self.assertEqual(publish.hidden_types([], False), set())
        self.assertEqual(publish.hidden_types(None, False), set())

    def test_a_project_with_section_rows_hides_a_built_in_it_has_no_row_for(self):
        rows = [{"id": "a", "type": "text", "hidden": 0}, {"id": "b", "type": "raid", "hidden": 1}]
        self.assertEqual(publish.hidden_types(rows), set(publish.BUILT_IN_SECTIONS))
        rows[1]["hidden"] = 0
        self.assertEqual(publish.hidden_types(rows), set(publish.BUILT_IN_SECTIONS) - {"raid"})


class ClientPaths(Base):
    """Row 906: every path that decides what a client sees reads a built-in with no section row as hidden, the delete-all case too."""
    def setUp(self):
        super().setUp()
        with self.s.step("dashboard", USER) as st:
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High", "likelihood": "High",
                               "raised": "2026-10-01", "source": "demo"})
        self.demo.action(due_date="2030-02-01")

    def delete(self, *kinds):
        for r in self.rows():
            if not kinds or r["type"] in kinds:
                self.ok("delete", id=r["id"])

    def test_the_editors_data_says_when_every_section_was_deleted(self):
        self.assertFalse(self.s.data_for("ABC")["sections_deleted"])
        self.delete()
        got = self.s.data_for("ABC")
        self.assertEqual((got["report_sections"], got["sections_deleted"]), ([], True))

    def test_the_as_at_read_works_after_every_section_was_deleted(self):
        """as_at.py calls Store.data_for on a bare object: it must not need a method of the store (it once failed with a 500)."""
        self.delete()
        live = self.s.data_for("ABC")
        got = as_at.rebuild(self.path, "ABC", "2099-01-01")
        self.assertEqual((got["report_sections"], got["sections_deleted"]), ([], True))
        self.assertEqual(got["sections_deleted"], live["sections_deleted"])
        self.assertEqual(len(got["milestones"]), len(live["milestones"]), "the records are as the live read has them")

    def test_glance_kept_rows_hides_a_deleted_section_and_the_delete_all_case(self):
        self.delete("raid")
        kept = glance.kept_rows(self.s.data_for("ABC"), "2030-01-15")
        self.assertIn("raid", kept["hidden_types"])
        self.assertEqual(kept["data"]["raid"], [])
        self.assertTrue(kept["data"]["actions"])
        self.delete()
        kept = glance.kept_rows(self.s.data_for("ABC"), "2030-01-15")
        self.assertEqual(kept["hidden_types"], set(publish.BUILT_IN_SECTIONS))
        self.assertEqual([kept["data"][k] for k in ("milestones", "actions", "raid", "decisions", "use_cases")], [[]] * 5)

    def test_the_client_rows_carry_nothing_of_a_deleted_section(self):
        self.assertTrue(client_filters.client_rows(self.s.data_for("ABC"), "2030-01-15"))
        self.delete("actions", "raid")
        self.assertEqual(client_filters.client_rows(self.s.data_for("ABC"), "2030-01-15"), [])

    def test_the_client_tiles_leave_out_a_deleted_sections_tile(self):
        self.delete("raid")
        tiles = [t["tile"] for t in glance.tiles(self.s.data_for("ABC"), "2030-01-15", for_client=True)]
        self.assertNotIn("risks", tiles)

    def test_the_excel_cover_for_the_client_carries_nothing_after_delete_all(self):
        self.delete()
        text = repr(excel_cover.from_store(self.s, "ABC", "2030-01-15 04:00"))
        self.assertNotIn("Phase two", text)
        self.assertNotIn("Supplier slips", text)
        self.assertNotIn("Current state", text)


class ReAdd(Base):
    def test_every_built_in_is_added_again_once_with_its_own_title_and_settings(self):
        for t in BUILT_INS:
            with self.subTest(type=t):
                title = self.of_type(t)[0]["title"]
                self.ok("delete", id=self.of_type(t)[0]["id"])
                got = self.ok("new", values={"type": t, "title": "Something else"})
                row = self.s.read(KIND, ref=got["ref"])
                self.assertEqual((row["type"], row["title"], row["body"], row["hidden"], row["beside"]), (t, title, "", 0, 0))
                self.assertEqual(len(self.of_type(t)), 1)

    def test_a_built_in_already_in_the_report_is_refused_a_second_time_and_nothing_is_written(self):
        for t in BUILT_INS:
            with self.subTest(type=t):
                self.refused(self.req("new", values={"type": t}), changes.NEW_TYPE_WORDS)
        self.ok("delete", id=self.of_type("milestones")[0]["id"])
        self.ok("new", values={"type": "milestones"})
        self.refused(self.req("new", values={"type": "milestones"}), changes.NEW_TYPE_WORDS)

    def test_a_type_outside_the_list_is_still_refused(self):
        for t in ("text ", "MILESTONES", "nope", ""):
            self.refused(self.req("new", values={"type": t}), changes.NEW_TYPE_WORDS)

    def test_the_new_types_are_exactly_text_the_content_types_and_the_built_ins(self):
        self.assertEqual(set(changes.NEW_SECTION_TYPES) - set(store_module.BODY_TYPES), set(BUILT_INS) | {"gantt", "gantttable"})


if __name__ == "__main__":
    unittest.main()

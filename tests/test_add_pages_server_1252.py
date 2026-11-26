"""Row 1252 slice 2: the server side of Add pages (the added_pages table and its migration step 34, the five-page cap, the prebuilt Gantt
page's two switches, the change route's checks, and Undo). Fictional data only.

Run: python3 dev/run_tests.py test_add_pages_server_1252
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, store as store_module
from clark.store import open_store
from test_store_use_case_done_migration import make_at, schema_of

STEP = store_module.ADDED_PAGES_STEP
SECTIONS = json.dumps([{"id": "s1", "type": "text", "title": "About", "body": "<p>Hello there</p>"}])


class Server(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def page(self, name="Notes", starter="blank", **values):
        return self.change({"project": "ABC", "kind": "added_pages", "op": "new", "values": {"name": name, "starter": starter, **values}})

    def project(self, **changes_):
        return self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": changes_})

    def rows(self):
        return self.s.read("added_pages", project="ABC")


class FullCap(Server):
    def test_cap_the_gantt_page_counts_one_so_four_more_fit_and_the_fifth_is_refused(self):
        """The server half (PM ruling 24-11): the prebuilt Gantt page always counts one of the five, hidden or shown, so four added pages are
        kept and the fifth is refused with the approved sentence and nothing is written."""
        self.assertEqual(self.s.read("projects", ref="ABC")["show_gantt_editor"], 0)                # hidden: it still counts
        self.assertEqual(store_module.added_page_count(self.s.con, "ABC"), 1)
        for n in range(4):
            status, body = self.page(f"Page {n}")
            self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(len(self.rows()), 4)
        before = self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        status, body = self.page("Fifth")
        self.assertEqual((status, body["ok"], body["message"]), (400, False, "You have 5 added pages. Remove one to add another."), body)
        self.assertEqual(len(self.rows()), 4)
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0], before)
        self.assertEqual(self.project(show_gantt_editor=1)[0], 200)                  # shown: the same five, nothing more is taken
        self.assertEqual(store_module.added_page_count(self.s.con, "ABC"), 5)
        self.assertEqual(self.project(show_gantt_editor=0)[0], 200)
        self.assertEqual(store_module.added_page_count(self.s.con, "ABC"), 5)        # hiding the Gantt page frees nothing
        self.assertEqual(self.page("Fifth")[0], 400)

    def test_removing_an_added_page_frees_one_place_whatever_the_gantt_switches_say(self):
        for n in range(4):
            self.assertEqual(self.page(f"Page {n}")[0], 200)
        self.assertEqual(self.project(show_gantt_editor=1)[0], 200)
        self.assertEqual(self.page("Fifth")[0], 400)
        self.assertEqual(self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": self.rows()[0]["id"]})[0], 200)
        self.assertEqual(self.page("Fifth")[0], 200)

    def test_a_page_is_checked_on_the_server(self):
        for values in ({"name": ""}, {"name": "x" * 41}, {"starter": "gantt"}, {"starter": "nope"}, {"client": 2}, {"hidden": True},
                       {"sections": "not json"}, {"sections": json.dumps([{"id": "g", "type": "gantt", "title": "G"}])},
                       {"sections": json.dumps([{"id": "w", "type": "workitems", "title": "W"}])}):
            with self.subTest(values=values):
                status, body = self.page(**{"name": "Ok", "starter": "blank", **values})
                self.assertEqual((status, body["ok"]), (400, False), body)
        self.assertEqual(self.rows(), [])


class PrebuiltGantt(Server):
    def test_prebuilt_gantt_page_counts_one_hidden_and_can_be_added_again(self):
        """The server half: hidden by default (both switches 0, values kept, no migration), added = show_gantt_editor 1, Hide and Remove = 0, Undo restores, client switch apart."""
        p = self.s.read("projects", ref="ABC")
        self.assertEqual((p["show_gantt_editor"], p["show_gantt_client"]), (0, 0))
        self.assertEqual(store_module.added_page_count(self.s.con, "ABC"), 1)         # the Gantt page counts one even while hidden
        status, body = self.project(show_gantt_editor=1)                              # Add page > Gantt
        self.assertEqual(status, 200, body)
        self.assertEqual(store_module.added_page_count(self.s.con, "ABC"), 1)         # shown or hidden, one of the five
        self.assertEqual(self.project(show_gantt_client=1)[0], 200)                    # Shown to the client
        status, body = self.project(show_gantt_editor=0)                              # Remove
        apply_id = body["apply_id"]
        p = self.s.read("projects", ref="ABC")
        self.assertEqual((p["show_gantt_editor"], p["show_gantt_client"]), (0, 1))     # the client value is kept
        self.assertEqual(store_module.added_page_count(self.s.con, "ABC"), 1)         # still one: the page is hidden, not gone
        self.assertEqual(self.undo({"project": "ABC", "apply_id": apply_id})[0], 200)  # Undo restores
        self.assertEqual(self.s.read("projects", ref="ABC")["show_gantt_editor"], 1)
        self.assertEqual(self.project(show_gantt_editor=0)[0], 200)
        self.assertEqual(self.project(show_gantt_editor=1)[0], 200)                    # added again
        self.assertEqual(self.s.read("projects", ref="ABC")["show_gantt_editor"], 1)

    def test_the_two_switches_are_flags_only(self):
        for v in (2, True, "1", 1.0):
            self.assertEqual(self.project(show_gantt_editor=v)[0], 400, v)


class Stored(unittest.TestCase):
    def test_added_pages_survive_reopen_and_old_project_opens_unchanged(self):
        folder = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = make_at(folder, STEP - 1)
        before = sqlite3.connect(str(path))
        try:
            self.assertIsNone(before.execute("SELECT 1 FROM sqlite_master WHERE name = 'added_pages'").fetchone())
            old = {t: before.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in ("projects", "documents")}
        finally:
            before.close()
        s = open_store(path, onedrive_roots=[])
        self.assertEqual(s.read("projects", ref="ABC")["name"], "Example Programme")
        self.assertEqual(s.read("added_pages", project="ABC"), [])
        self.assertEqual(s.data_for("ABC")["added_pages"], [])
        s.close()
        con = sqlite3.connect(str(path))
        try:
            for t, rows in old.items():
                self.assertEqual(con.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()[:len(rows)], rows, t)
            self.assertEqual(con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
            self.assertEqual(con.execute("SELECT count(*) FROM added_pages").fetchone()[0], 0)
        finally:
            con.close()
        new = folder / "new" / "clark.db"
        new.parent.mkdir()
        open_store(new, onedrive_roots=[]).close()
        self.assertEqual(schema_of(path, "added_pages"), schema_of(new, "added_pages"))      # the step makes what schema.sql makes
        change = changes.make_change(path, [], USER)
        status, body = change({"project": "ABC", "kind": "added_pages", "op": "new",
                               "values": {"name": "Notes", "starter": "documents", "client": 1, "hidden": 1, "sort_order": 7, "sections": SECTIONS}})
        self.assertEqual(status, 200, body)
        again = open_store(path, onedrive_roots=[])                                    # closed and opened again
        try:
            row = again.read("added_pages", project="ABC")[0]
            self.assertEqual((row["id"], row["name"], row["starter"], row["client"], row["hidden"], row["sort_order"], row["sections"]),
                             ("ABC-PG-001", "Notes", "documents", 1, 1, 7, json.dumps(json.loads(SECTIONS), separators=(",", ":"))))
            self.assertEqual(again.data_for("ABC")["added_pages"][0]["name"], "Notes")
        finally:
            again.close()
        again = open_store(path, onedrive_roots=[])
        self.assertEqual(len(again.read("added_pages", project="ABC")), 1)             # a second open runs no step and changes nothing
        again.close()


class Undo(Server):
    def test_remove_page_is_undone_whole_and_hide_keeps_sections(self):
        ref = self.page("Notes", sections=SECTIONS)[1]["ref"]
        self.change({"project": "ABC", "kind": "added_pages", "op": "update", "id": ref, "changes": {"hidden": 1}})
        self.assertEqual(self.rows()[0]["sections"], json.dumps(json.loads(SECTIONS), separators=(",", ":")))
        status, body = self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": ref})
        self.assertEqual((status, body["undoable"]), (200, True), body)
        self.assertEqual(self.rows(), [])
        status, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, back)
        row = self.rows()[0]
        self.assertEqual((row["id"], row["name"], row["hidden"], row["sections"]), (ref, "Notes", 1, json.dumps(json.loads(SECTIONS), separators=(",", ":"))))

    def test_undo_of_a_new_page_takes_it_away_and_another_project_is_refused(self):
        status, body = self.page("Notes")
        self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 200)
        self.assertEqual(self.rows(), [])
        ref = self.page("Notes")[1]["ref"]
        self.assertEqual(ref, "ABC-PG-002")                                           # a number once used is not used again
        status, body = self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": "XYZ-PG-001"})
        self.assertEqual(status, 400, body)

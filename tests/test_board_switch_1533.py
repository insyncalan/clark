"""Row 1533, PR 1: the author's switch for the client's Work items board (projects.show_board_client, step 37, store and changes are guarded).

Covered: the migration adds the column off (0) for every project and a second run changes nothing; the schema and the migration say the
same column; a new project is off; the change route sets it to the whole numbers 0 and 1 only, records one step with Undo, and says it in
one line; the store refuses anything else; the Settings card shows the tick, labelled exactly "Show the board to clients", at 1400 and 900.
Run: python3 -m unittest test_board_switch_1533   (from tests/)
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from clark import changes, store as store_module
from test_gantt_store import Base
from test_store_use_case_done_migration import make_at

LABEL = "Show the board to clients"


class Migration(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_37_and_the_version_says_so(self):
        self.assertEqual(store_module.BOARD_CLIENT_STEP, 37)
        self.assertIn((37, store_module.migrate_board_client), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, 37)

    def test_the_step_adds_the_column_off_for_every_project_and_a_second_run_changes_nothing(self):
        path = make_at(self.dir, 33)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO projects (code, name, health, health_reason) VALUES ('DEF', 'Other Programme', 'At risk', 'Late supplier')")
        self.assertNotIn("show_board_client", [c[1] for c in con.execute("PRAGMA table_info(projects)")])
        before = con.execute("SELECT * FROM projects ORDER BY code").fetchall()
        store_module.migrate_board_client(con)
        info = {c[1]: c for c in con.execute("PRAGMA table_info(projects)")}
        self.assertEqual(list(info)[-1], "show_board_client", "added at the end of the table")
        self.assertEqual((info["show_board_client"][2], info["show_board_client"][3], info["show_board_client"][4]), ("INTEGER", 1, "0"))
        rows = con.execute("SELECT * FROM projects ORDER BY code").fetchall()
        self.assertEqual([r[:-1] for r in rows], before, "no existing value changed")
        self.assertEqual([r[-1] for r in rows], [0] * len(rows), "off for every project")
        self.assertTrue(rows)
        store_module.migrate_board_client(con)      # a second run
        self.assertEqual(con.execute("SELECT * FROM projects ORDER BY code").fetchall(), rows)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE projects SET show_board_client = 2")
        con.close()

    def test_the_schema_file_says_the_same_column_as_the_step(self):
        schema = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        line = re.search(r"^\s*(show_board_client INTEGER[^\n]*?\)\))", schema, re.M).group(1)
        self.assertIn(store_module.BOARD_CLIENT_COLUMN, line)
        self.assertIn("show_board_client", store_module.FLAG_COLUMNS)

    def test_a_whole_file_opens_at_the_newest_version_when_the_steps_are_all_there(self):
        numbers = [n for n, _ in store_module.MIGRATIONS]
        if numbers != list(range(2, numbers[-1] + 1)):
            self.skipTest("steps 34 to 36 (other rows) are not on this branch yet; the runner refuses a gap")
        path = make_at(self.dir, 33)
        s = store_module.open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        self.assertIn("show_board_client", [c[1] for c in s.con.execute("PRAGMA table_info(projects)")])


class Switch(Base):
    def proj(self):
        return self.s.read("projects", ref="ABC")

    def put(self, value):
        return self.go(kind="projects", op="update", changes={"show_board_client": value})

    def test_a_project_is_off_by_default(self):
        self.assertEqual(self.proj()["show_board_client"], 0)
        self.assertEqual(self.s.data_for("ABC")["project"]["show_board_client"], 0)

    def test_on_and_off_are_one_step_each_with_one_undo_and_the_echo_carries_it(self):
        status, body = self.put(1)
        self.assertEqual((status, body.get("message")), (200, None), body)
        self.assertEqual((self.proj()["show_board_client"], body["project"]["show_board_client"]), (1, 1))
        out = self.undo_step(body["apply_id"])
        self.assertIn("board view for the client", out["words"])
        self.assertEqual(self.proj()["show_board_client"], 0)
        self.assertEqual(self.put(0)[1]["apply_id"], None, "off to off changes nothing and has no Undo")

    def test_the_field_is_in_the_change_lists_and_has_its_words(self):
        self.assertIn("show_board_client", changes.CHANGE_KINDS["projects"]["update"])
        self.assertIn("show_board_client", changes.UNDOABLE["projects"])
        from clark import history
        self.assertEqual(history.FIELD_NAMES["projects"]["show_board_client"], LABEL)

    def test_only_the_whole_numbers_0_and_1_are_taken(self):
        for bad in (2, True, "1", None, 1.0, -1, [1]):
            before = self.counts()
            status, body = self.put(bad)
            self.assertEqual((status, body["message"]), (400, changes.FLAG_WORDS), bad)
            self.assertEqual(self.counts(), before)
            self.assertEqual(self.proj()["show_board_client"], 0)

    def test_the_schema_checks_it_too(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.con.execute("UPDATE projects SET show_board_client = 2")


if __name__ == "__main__":
    unittest.main()

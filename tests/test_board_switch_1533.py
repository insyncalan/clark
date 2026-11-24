"""Row 1533, PR 1: the author's switch for the client's Work items board (projects.show_board_client, step 35, store and changes are guarded).

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
from test_publish_dialog import Base as PageBase
from test_server import chrome
from test_settings_head import Head
from test_store_use_case_done_migration import make_at

LABEL = "Show the board to clients"


class Migration(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    @staticmethod
    def migrate(con):
        con.row_factory = sqlite3.Row      # the store's own connections read columns by name
        try:
            store_module.migrate_board_client(con)
        finally:
            con.row_factory = None

    def test_the_step_is_35_and_the_version_says_so(self):
        self.assertEqual(store_module.BOARD_CLIENT_STEP, 35)
        self.assertIn((35, store_module.migrate_board_client), store_module.MIGRATIONS)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, 35)

    def test_the_step_adds_the_column_off_for_every_project_and_a_second_run_changes_nothing(self):
        path = make_at(self.dir, 33)
        con = sqlite3.connect(str(path), isolation_level=None)
        con.execute("INSERT INTO projects (code, name, health, health_reason) VALUES ('DEF', 'Other Programme', 'At risk', 'Late supplier')")
        self.assertNotIn("show_board_client", [c[1] for c in con.execute("PRAGMA table_info(projects)")])
        before = con.execute("SELECT * FROM projects ORDER BY code").fetchall()
        self.migrate(con)
        info = {c[1]: c for c in con.execute("PRAGMA table_info(projects)")}
        self.assertEqual(list(info)[-1], "show_board_client", "added at the end of the table")
        self.assertEqual((info["show_board_client"][2], info["show_board_client"][3], info["show_board_client"][4]), ("INTEGER", 1, "0"))
        rows = con.execute("SELECT * FROM projects ORDER BY code").fetchall()
        self.assertEqual([r[:-1] for r in rows], before, "no existing value changed")
        self.assertEqual([r[-1] for r in rows], [0] * len(rows), "off for every project")
        self.assertTrue(rows)
        self.migrate(con)      # a second run
        self.assertEqual(con.execute("SELECT * FROM projects ORDER BY code").fetchall(), rows)
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE projects SET show_board_client = 2")
        con.close()

    def test_a_file_with_no_projects_table_is_left_alone(self):
        con = sqlite3.connect(":memory:", isolation_level=None)
        self.migrate(con)
        self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0], 0)
        con.close()

    def test_the_schema_file_says_the_same_column_as_the_step(self):
        schema = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        line = re.search(r"^\s*(show_board_client INTEGER[^\n]*?\)\))", schema, re.M).group(1)
        self.assertIn(store_module.BOARD_CLIENT_COLUMN, line)
        self.assertIn("show_board_client", store_module.FLAG_COLUMNS)

    def test_a_whole_file_opens_at_the_newest_version_when_the_steps_are_all_there(self):
        numbers = [n for n, _ in store_module.MIGRATIONS]
        if numbers != list(range(2, numbers[-1] + 1)):
            self.skipTest("steps 35 to 36 (other rows) are not on this branch yet; the runner refuses a gap")
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
        self.assertEqual(out["project"]["show_board_client"], 0, "the Undo's echo carries it too")
        self.assertEqual(self.proj()["show_board_client"], 0)
        self.assertEqual(self.put(0)[1]["apply_id"], None, "off to off changes nothing and has no Undo")

    def test_the_undo_sentence_is_exactly_one_line_and_said_once_for_two_entries(self):
        def entry(ref, to):
            return {"field": "show_board_client", "ref": ref, "to": to, "change": "changed"}
        one = changes.words([entry("ABC", "0")], [], {})
        self.assertEqual(one, "Put back: the board view for the client.")      # not a second, generic phrase after it
        two = changes.words([entry("ABC", "0"), entry("DEF", "1")], [], {})
        self.assertEqual(two, "Put back: the board view for the client.")      # one line however many entries

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


class SettingsTick(PageBase):
    """The Settings tick, in Chrome at 1400 and 900, light and dark: on the Reports page, under the Gantt card, labelled exactly as approved."""

    def drawn(self, cdp, w, mode):
        p = self.page(cdp)
        Head.open_settings(self, p, w, mode, "reports")
        p.until("!!document.getElementById('board-client')", "the board tick is drawn")
        return p

    def test_the_reports_page_shows_the_tick_off_with_its_label_under_the_gantt_card(self):
        for w in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.drawn(cdp, w, mode)
                    self.assertEqual(p.js("document.querySelector('#board-client').closest('.set-row').textContent.includes(%r)" % LABEL), True)
                    self.assertEqual(p.js("document.getElementById('board-setting-h').textContent"), "Work items board")
                    self.assertFalse(p.js("document.getElementById('board-client').checked"), "off by default")
                    self.assertTrue(p.js("document.getElementById('gantt-setting').compareDocumentPosition(document.getElementById('board-setting')) & Node.DOCUMENT_POSITION_FOLLOWING"), "under the Gantt card")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")

    def test_a_click_saves_it_and_reset_puts_it_back_off(self):
        for w in (1400, 900):
            with self.subTest(width=w), chrome() as cdp:
                p = self.drawn(cdp, w, "light")
                p.js("document.getElementById('board-client').click()")
                p.until("document.getElementById('board-client').checked && !!document.querySelector('#board-client').closest('.set-row').querySelector('.set-reset')", "the tick saved and Reset is offered")
                p.js("document.querySelector('#board-client').closest('.set-row').querySelector('.set-reset').click()")
                p.until("!document.getElementById('board-client').checked", "Reset put it back off")


if __name__ == "__main__":
    unittest.main()

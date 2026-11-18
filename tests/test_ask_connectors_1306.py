"""Row 1306, slice C1: the connector switches (migration step 32, store methods, GET and POST /api/ask-connectors). Switch state only.

Every connector starts Off for this computer; a project can keep one Off, and Off wins. Only the five known names are accepted. Nothing but
state is stored. A file made before the step gets the tables with every switch Off. Fictional data only.

Run: python3 dev/run_tests.py test_ask_connectors_1306
"""
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from clark import store as store_module
from clark.store import CONNECTORS, Invalid, open_store
from test_app_settings_route import Base
from test_store_migration import version
from test_store_use_case_done_migration import make_at

STEP = 32
NAMES = ("mail", "calendar", "teams", "sharepoint", "todoist")


def switch_rows(path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute("SELECT connector, is_on FROM connector_switches ORDER BY rowid").fetchall()
    finally:
        con.close()


class Migrating(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_the_step_is_in_the_table_at_its_number(self):
        self.assertIn((STEP, store_module.migrate_connector_switches), store_module.MIGRATIONS)
        self.assertEqual(store_module.CONNECTOR_SWITCHES_STEP, STEP)
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, STEP)
        self.assertEqual(CONNECTORS, NAMES)
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_a_new_file_has_the_five_switches_all_off_and_no_project_rows(self):
        open_store(self.dir / "clark.db", onedrive_roots=[]).close()
        self.assertEqual(switch_rows(self.dir / "clark.db"), [(n, 0) for n in NAMES])
        con = sqlite3.connect(str(self.dir / "clark.db"))
        self.assertEqual(con.execute("SELECT count(*) FROM project_connectors").fetchone()[0], 0)
        con.close()

    def test_an_old_file_is_migrated_with_the_copy_taken_every_row_kept_and_every_switch_off(self):
        path = make_at(self.dir, STEP - 1)
        con = sqlite3.connect(str(path))
        self.assertIsNone(con.execute("SELECT 1 FROM sqlite_master WHERE name IN ('connector_switches', 'project_connectors')").fetchone())
        before = con.execute("SELECT code, name FROM projects ORDER BY code").fetchall()
        con.close()
        s = open_store(path, onedrive_roots=[])
        try:
            self.assertEqual(version(path), str(store_module.SCHEMA_VERSION))
            self.assertEqual(switch_rows(path), [(n, 0) for n in NAMES])
            self.assertEqual([tuple(r) for r in s.con.execute("SELECT code, name FROM projects ORDER BY code")], before)
            self.assertEqual(s.con.execute("SELECT count(*) FROM applies").fetchone()[0], 0)      # a migration is not a step: no Undo
            self.assertEqual(s.con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(s.connector_switches(), {n: False for n in NAMES})
        finally:
            s.close()

    def test_a_second_run_keeps_a_switch_that_was_set(self):
        path = self.dir / "clark.db"
        open_store(path, onedrive_roots=[]).close()
        con = sqlite3.connect(str(path))
        con.execute("UPDATE connector_switches SET is_on = 1 WHERE connector = 'mail'")
        con.commit()
        store_module.migrate_connector_switches(con)
        con.commit()
        self.assertEqual(con.execute("SELECT is_on FROM connector_switches WHERE connector = 'mail'").fetchone(), (1,))
        con.close()

    def test_the_tables_hold_state_and_nothing_else(self):
        open_store(self.dir / "clark.db", onedrive_roots=[]).close()
        con = sqlite3.connect(str(self.dir / "clark.db"))
        cols = lambda t: [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        self.assertEqual(cols("connector_switches"), ["connector", "is_on", "updated_at"])
        self.assertEqual(cols("project_connectors"), ["project_id", "connector", "off", "updated_at"])
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO connector_switches (connector) VALUES ('slack')")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE connector_switches SET is_on = 2")
        con.close()

    def test_the_frozen_statements_match_schema_sql(self):
        text = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        norm = lambda t: re.sub(r"\s+", " ", t.replace(";", "")).strip()
        for i, name in ((0, "connector_switches"), (2, "project_connectors")):
            want = re.search(rf"CREATE TABLE IF NOT EXISTS {name} \(.*?\n\);", text, re.S).group(0)
            self.assertEqual(norm(store_module.CONNECTOR_SWITCHES_DDL[i]), norm(want), name)
        self.assertIn(norm(store_module.CONNECTOR_SWITCHES_DDL[1]), norm(text))


class StoreMethods(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.s = open_store(self.dir / "clark.db", onedrive_roots=[])
        self.addCleanup(self.s.close)
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme"})

    def test_everything_is_off_to_start_with(self):
        for c in NAMES:
            self.assertFalse(self.s.connector_allowed(c, "ABC"), c)
        self.assertEqual(self.s.project_connectors_off("ABC"), ())

    def test_a_project_off_wins_over_the_global_on(self):
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.update("connector_switches", "mail", {"is_on": True})
            st.update("connector_switches", "teams", {"is_on": True})
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("project_connectors", {"project_id": "ABC", "connector": "mail", "off": True})
        self.assertFalse(self.s.connector_allowed("mail", "ABC"))
        self.assertTrue(self.s.connector_allowed("teams", "ABC"))
        self.assertTrue(self.s.connector_allowed("mail", "OTHER"))      # another project's code: not that project's Off
        self.assertFalse(self.s.connector_allowed("calendar", "ABC"))   # global Off stays Off
        self.assertEqual(self.s.project_connectors_off("ABC"), ("mail",))

    def test_an_unknown_name_is_refused_by_the_writer_and_allowed_nowhere(self):
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", "tester", place="menu") as st:
                st.update("connector_switches", "slack", {"is_on": True})
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", "tester", place="menu") as st:
                st.create("project_connectors", {"project_id": "ABC", "connector": "slack", "off": True})
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", "tester", place="menu") as st:
                st.create("project_connectors", {"project_id": "NOPE", "connector": "mail", "off": True})
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", "tester", place="menu") as st:
                st.create("connector_switches", {"connector": "mail"})
        self.assertFalse(self.s.connector_allowed("slack", "ABC"))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM project_connectors").fetchone()[0], 0)

    def test_a_file_without_the_tables_reads_as_all_off(self):
        self.s.con.execute("DROP TABLE project_connectors")
        self.assertFalse(self.s.connectors_ready())
        self.assertEqual(self.s.connector_switches(), {n: False for n in NAMES})
        self.assertFalse(self.s.connector_allowed("mail", "ABC"))

    def test_only_state_is_ever_logged(self):
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.update("connector_switches", "todoist", {"is_on": True})
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("project_connectors", {"project_id": "ABC", "connector": "todoist", "off": True})
        fields = {r[0] for r in self.s.con.execute("SELECT field FROM change_log WHERE tbl IN ('connector_switches', 'project_connectors')")}
        self.assertLessEqual(fields, {"is_on", "off", "project_id", "connector", "updated_at"})


class Route(Base):
    def post(self, body):
        return self.call("POST", "/api/ask-connectors", body)

    def stored(self):
        store = open_store(self.db, onedrive_roots=[])
        try:
            return store.connector_switches(), store.project_connectors_off("ABC"), store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        finally:
            store.close()

    def test_get_gives_five_connectors_all_off(self):
        status, got = self.call("GET", "/api/ask-connectors")
        self.assertEqual(status, 200)
        self.assertEqual((got["ok"], got["saved"], list(got["connectors"])), (True, True, list(NAMES)))
        self.assertTrue(all(v == {"on": False} for v in got["connectors"].values()))
        status, got = self.call("GET", "/api/ask-connectors?project=ABC")
        self.assertEqual(got["project"], "ABC")
        self.assertTrue(all(v == {"on": False, "project_off": False, "allowed": False} for v in got["connectors"].values()))

    def test_global_on_then_a_projects_off_wins_then_allowed_again_then_undo(self):
        status, got = self.post({"connector": "mail", "on": True})
        self.assertEqual((status, got["connectors"]["mail"]["on"]), (200, True))
        self.assertIsInstance(got["apply_id"], int)
        self.assertTrue(self.call("GET", "/api/ask-connectors?project=ABC")[1]["connectors"]["mail"]["allowed"])
        status, got = self.post({"connector": "mail", "project": "ABC", "off": True})
        self.assertEqual(status, 200)
        self.assertEqual(got["connectors"]["mail"], {"on": True, "project_off": True, "allowed": False})
        self.assertTrue(self.call("GET", "/api/ask-connectors?project=DEF")[1]["connectors"]["mail"]["allowed"])
        status, got = self.post({"connector": "mail", "project": "ABC", "off": False})
        self.assertEqual(got["connectors"]["mail"], {"on": True, "project_off": False, "allowed": True})
        status, got = self.post({"connector": "mail", "project": "ABC", "off": True})        # the row is there now: changed, not made again
        self.assertTrue(got["connectors"]["mail"]["project_off"])
        status, got = self.post({"undo": got["apply_id"]})
        self.assertEqual((status, got["connectors"]["mail"]["project_off"]), (200, False))
        self.assertEqual(self.stored()[1], ())

    def test_a_first_project_off_can_be_undone(self):
        status, got = self.post({"connector": "todoist", "project": "DEF", "off": True})
        self.assertEqual(status, 200)
        status, got = self.post({"undo": got["apply_id"]})
        self.assertEqual((status, got["connectors"]["todoist"]["project_off"]), (200, False))

    def test_the_same_value_changes_nothing(self):
        was = self.stored()
        status, got = self.post({"connector": "mail", "on": False})
        self.assertEqual((status, got["message"]), (200, "That is the setting already in use."))
        self.assertEqual(self.stored(), was)

    def test_an_unknown_connector_is_refused_and_nothing_changes(self):
        was = self.stored()
        for body in ({"connector": "slack", "on": True}, {"connector": "", "on": True}, {"connector": None, "on": True}, {"connector": ["mail"], "on": True},
                     {"connector": "MAIL", "on": True}, {"connector": "slack", "project": "ABC", "off": True}):
            status, got = self.post(body)
            self.assertEqual((status, got["ok"], got["code"]), (400, False, "bad_connector"), body)
        self.assertEqual(self.stored(), was)

    def test_other_bodies_are_refused_and_nothing_changes(self):
        was = self.stored()
        for body in ({"connector": "mail", "on": "true"}, {"connector": "mail", "on": 1}, {"connector": "mail", "on": None},
                     {"connector": "mail", "project": "ABC", "off": "yes"}, {"connector": "mail", "project": "abc", "off": True},
                     {"connector": "mail", "project": 7, "off": True}, {"connector": "mail"}, {"on": True}, {}, [], "mail",
                     {"connector": "mail", "on": True, "token": "x"}, {"connector": "mail", "on": True, "project": "ABC"},
                     {"connector": "mail", "project": "ABC", "off": True, "on": True}, {"undo": 0}, {"undo": "1"}, {"undo": True}):
            status, got = self.post(body)
            self.assertEqual((status, got["ok"]), (400, False), body)
        self.assertEqual(self.post({"connector": "mail", "project": "ZZZ", "off": True})[0], 404)
        self.assertEqual(self.post({"undo": 99999})[0], 409)
        self.assertEqual(self.stored(), was)

    def test_an_undo_of_another_setting_is_refused(self):
        step = self.ask(False)[1]["apply_id"]
        status, got = self.post({"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertFalse(self.stored_ask())

    def test_get_refuses_other_parameters_and_a_missing_project(self):
        self.assertEqual(self.call("GET", "/api/ask-connectors?project=abc")[0], 400)
        self.assertEqual(self.call("GET", "/api/ask-connectors?other=1")[0], 400)
        self.assertEqual(self.call("GET", "/api/ask-connectors?project=ZZZ")[0], 404)

    def test_the_body_limit_and_the_token_are_checked(self):
        self.assertEqual(self.call("POST", "/api/ask-connectors", b"x" * 2000)[0], 400, "over the 1 KB limit")
        self.assertEqual(self.call("POST", "/api/ask-connectors", {"connector": "mail", "on": True}, token="wrong")[0], 403)
        self.assertEqual(self.stored()[0]["mail"], False)

    def test_asking_itself_is_not_touched(self):
        self.post({"connector": "mail", "on": True})
        self.assertTrue(self.stored_ask())
        self.assertEqual(self.call("GET", "/api/ask-enabled")[1], {"ok": True, "ask_enabled": True, "saved": True})


if __name__ == "__main__":
    unittest.main()

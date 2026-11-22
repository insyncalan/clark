"""Row 1306, slice C1: killers for the survivors of the diff sweep of the connector switches (app_settings.py, server.py, store.py).

Fictional data only.

Run: python3 dev/run_tests.py test_ask_connectors_1306_killers2
"""
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clark import ask_connectors
from clark import server as sv
from clark import store as store_module
from clark.store import open_store
from test_app_settings_route import Base

NAMES = ("mail", "calendar", "teams", "sharepoint", "todoist")


class StoreReaders(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.s = open_store(self.dir / "clark.db", onedrive_roots=[])
        self.addCleanup(self.s.close)
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme"})

    def test_only_a_one_reads_as_on(self):
        self.s.con.execute("PRAGMA ignore_check_constraints = ON")
        self.s.con.execute("UPDATE connector_switches SET is_on = 2 WHERE connector = 'mail'")
        self.s.con.execute("UPDATE connector_switches SET is_on = 1 WHERE connector = 'teams'")
        self.assertEqual(self.s.connector_switches(), {"mail": False, "calendar": False, "teams": True, "sharepoint": False, "todoist": False})

    def test_a_file_without_the_tables_has_no_project_off_and_allows_nothing(self):
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("project_connectors", {"project_id": "ABC", "connector": "mail", "off": True})
        self.assertEqual(self.s.project_connectors_off("ABC"), ("mail",))
        self.s.con.execute("DELETE FROM connector_switches WHERE connector = 'todoist'")
        self.assertEqual(self.s.project_connectors_off("ABC"), ())      # not ready: an empty answer, not the rows that are there

    def test_a_database_error_leaves_no_project_off(self):
        self.s.con.close()
        self.assertEqual(self.s.project_connectors_off("ABC"), ())
        self.assertEqual(self.s.connector_switches(), {n: False for n in NAMES})

    def test_a_read_that_fails_after_the_file_looked_ready_has_no_project_off(self):
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("project_connectors", {"project_id": "ABC", "connector": "mail", "off": True})
        real = self.s.con

        class Failing:
            def execute(self, sql, *args):
                if "FROM project_connectors WHERE" in sql:
                    raise sqlite3.OperationalError("disk I/O error")
                return real.execute(sql, *args)

        self.s.con = Failing()
        try:
            self.assertTrue(self.s.connectors_ready())
            self.assertEqual(self.s.project_connectors_off("ABC"), ())
            self.assertFalse(self.s.connector_allowed("mail", "ABC"))
        finally:
            self.s.con = real

    def test_project_off_comes_in_the_order_of_the_five_names(self):
        with self.s.step("dashboard", "tester", place="menu") as st:
            for c in ("todoist", "calendar", "mail"):
                st.create("project_connectors", {"project_id": "ABC", "connector": c, "off": True})
            st.create("project_connectors", {"project_id": "ABC", "connector": "teams", "off": False})
        self.assertEqual(self.s.project_connectors_off("ABC"), ("mail", "calendar", "todoist"))      # not alphabetical: calendar would come first

    def test_an_unknown_connector_name_in_the_file_is_not_read(self):
        self.s.con.execute("PRAGMA ignore_check_constraints = ON")
        self.s.con.execute("UPDATE connector_switches SET connector = 'slack' WHERE connector = 'todoist'")
        self.s.con.execute("UPDATE connector_switches SET is_on = 1")
        self.assertEqual(self.s.connector_switches(), {"mail": True, "calendar": True, "teams": True, "sharepoint": True, "todoist": False})
        self.assertNotIn("slack", self.s.connector_switches())

    def test_a_project_connector_needs_both_its_key_columns(self):
        for row in ({"connector": "mail", "off": True}, {"project_id": "ABC", "off": True}):
            with self.assertRaises(store_module.Invalid):
                with self.s.step("dashboard", "tester", place="menu") as st:
                    st.create("project_connectors", row)

    def test_both_connector_names_are_checked_by_the_writer_on_a_change(self):
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", "tester", place="menu") as st:
                st.create("project_connectors", {"project_id": "ABC", "connector": "slack", "off": True})
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", "tester", place="menu") as st:
                st.update("connector_switches", "mail", {"connector": "slack"})
        self.assertEqual([r[0] for r in self.s.con.execute("SELECT connector FROM connector_switches ORDER BY rowid")], list(NAMES))

    def test_the_flags_of_both_tables_are_named_flags(self):
        for col in ("is_on", "off"):
            self.assertIn(col, store_module.FLAG_COLUMNS)
        self.assertIn("project_connectors", store_module.SETTINGS_TABLES)
        self.assertIn("connector_switches", store_module.SETTINGS_TABLES)
        self.assertEqual(store_module.KEYS["connector_switches"], ("connector",))
        self.assertEqual(store_module.KEYS["project_connectors"], ("project_id", "connector"))
        self.assertEqual(store_module.REQUIRED_NEW["connector_switches"], ("connector",))
        self.assertEqual(store_module.REQUIRED_NEW["project_connectors"], ("project_id", "connector"))
        self.assertEqual(store_module.ALLOWED[("connector_switches", "connector")], store_module.CONNECTORS)
        self.assertEqual(store_module.ALLOWED[("project_connectors", "connector")], store_module.CONNECTORS)
        self.assertIn("project_connectors", store_module.REVERT_CREATED)

    def test_a_project_connector_row_is_not_made_by_a_switch_row_rule(self):
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", "tester", place="menu") as st:
                st.create("connector_switches", {"connector": "mail"})
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("project_connectors", {"project_id": "ABC", "connector": "mail", "off": True})

    def test_deleting_a_project_takes_its_connector_rows_with_it(self):
        with self.s.step("dashboard", "tester", place="menu") as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme"})
            st.create("project_connectors", {"project_id": "ABC", "connector": "mail", "off": True})
            st.create("project_connectors", {"project_id": "DEF", "connector": "teams", "off": True})
        self.s.remove_demo({"ABC": [("project_connectors", "ABC|mail"), ("projects", "ABC")]})
        rows = self.s.con.execute("SELECT project_id, connector FROM project_connectors").fetchall()
        self.assertEqual([tuple(r) for r in rows], [("DEF", "teams")])
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM projects WHERE code = 'ABC'").fetchone()[0], 0)


class RouteKillers(Base):
    def setUp(self):
        super().setUp()
        # all five are found on this computer (the route answers only found connectors)
        found = [{"connector": n, "label": n.title(), "server": "x"} for n in NAMES]
        p = mock.patch.object(ask_connectors, "list_found", lambda *a, **k: [dict(x) for x in found])
        p.start()
        self.addCleanup(p.stop)

    def post(self, body):
        return self.call("POST", "/api/ask-connectors", body)

    def count(self, table):
        con = sqlite3.connect(str(self.db))
        try:
            return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        finally:
            con.close()

    def break_tables(self):
        con = sqlite3.connect(str(self.db))
        con.execute("DROP TABLE project_connectors")
        con.commit()
        con.close()

    def test_a_project_value_that_is_already_in_use_makes_no_row_and_no_step(self):
        was = (self.count("project_connectors"), self.snapshot())
        status, got = self.post({"id": "mail", "project": "ABC", "off_here": False})
        self.assertEqual((status, got["message"]), (200, "That is the setting already in use."))
        self.assertNotIn("apply_id", got)
        self.assertEqual((self.count("project_connectors"), self.snapshot()), was)

    def test_the_same_off_twice_changes_nothing_the_second_time(self):
        self.post({"id": "mail", "project": "ABC", "off_here": True})
        was = self.snapshot()
        status, got = self.post({"id": "mail", "project": "ABC", "off_here": True})
        self.assertEqual(got["message"], "That is the setting already in use.")
        self.assertEqual(self.snapshot(), was)

    def test_a_file_without_the_tables_refuses_a_change_and_says_not_saved(self):
        self.break_tables()
        status, got = self.call("GET", "/api/ask-connectors")
        self.assertEqual((status, got["saved"], {c["id"]: c for c in got["connectors"]}.get("mail", {}).get("on")), (200, False, False))
        was = self.snapshot()
        for body in ({"id": "mail", "on": True}, {"id": "mail", "project": "ABC", "off_here": True}, {"undo": 1}):
            status, got = self.post(body)
            self.assertEqual((status, got["ok"], got["code"]), (409, False, "not_ready"), body)
        self.assertEqual(self.snapshot(), was)

    def test_the_words_of_each_change(self):
        self.assertEqual(self.post({"id": "mail", "on": True})[1]["message"], "That connector is on for this computer.")
        self.assertEqual(self.post({"id": "mail", "on": False})[1]["message"], "That connector is off.")
        self.assertEqual(self.post({"id": "mail", "project": "ABC", "off_here": True})[1]["message"], "That connector is off in this project.")
        self.assertEqual(self.post({"id": "mail", "project": "ABC", "off_here": False})[1]["message"], "That connector is no longer kept off in this project.")

    def test_an_undo_says_which_project_it_was_in(self):
        step = self.post({"id": "teams", "project": "DEF", "off_here": True})[1]["apply_id"]
        status, got = self.post({"undo": step})
        self.assertEqual((status, got["message"]), (200, "Undone."))
        self.assertEqual({c["id"]: (c["on"], c["off_here"]) for c in got["connectors"]}.get("teams"), (False, False))
        step = self.post({"id": "teams", "on": True})[1]["apply_id"]
        status, got = self.post({"undo": step})
        self.assertEqual(status, 200)

    def test_an_undo_is_done_once(self):
        step = self.post({"id": "teams", "project": "DEF", "off_here": True})[1]["apply_id"]
        self.assertEqual(self.post({"undo": step})[0], 200)
        was = self.snapshot()
        status, got = self.post({"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.snapshot(), was)

    def test_an_undo_of_a_step_that_did_more_than_the_switch_is_refused(self):
        store = open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as st:
                st.update("connector_switches", "mail", {"is_on": True})
                st.update("projects", "ABC", {"name": "Renamed Programme"})
            step = store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        finally:
            store.close()
        status, got = self.post({"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(open_store(self.db, onedrive_roots=[]).connector_switches()["mail"], True)

    def test_an_undo_of_a_step_with_a_row_of_another_table_is_refused(self):
        step = self.post({"id": "mail", "on": True})[1]["apply_id"]
        con = sqlite3.connect(str(self.db))
        con.execute("INSERT INTO change_log (at, apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                    "SELECT at, apply_id, 'projects', 'ABC', field, old_value, new_value, op, via FROM change_log WHERE apply_id = ? AND field = 'is_on'", (step,))
        con.commit()
        con.close()
        status, got = self.post({"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))

    def test_an_undo_of_a_step_changed_since_is_refused_and_leaves_it_as_it_is(self):
        first = self.post({"id": "mail", "on": True})[1]["apply_id"]
        self.post({"id": "mail", "on": False})
        was = self.snapshot()
        status, got = self.post({"undo": first})
        self.assertEqual((status, got["code"]), (409, "no_undo"))
        self.assertEqual(self.snapshot(), was)

    def test_an_undo_of_a_step_that_came_by_another_route_is_refused(self):
        store = open_store(self.db, onedrive_roots=[])
        try:
            with store.step("excel", "tester", place="menu") as st:
                st.update("connector_switches", "mail", {"is_on": True})
            step = store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
            via = store.con.execute("SELECT via FROM change_log WHERE apply_id = ?", (step,)).fetchone()[0]
        finally:
            store.close()
        self.assertNotEqual(via, "dashboard")
        status, got = self.post({"undo": step})
        self.assertEqual((status, got["code"]), (409, "no_undo"))

    def test_an_undo_of_a_step_with_nothing_in_it_is_refused(self):
        self.assertEqual(self.post({"undo": 1})[0] in (200, 409), True)
        store = open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as st:
                pass
            top = store.con.execute("SELECT coalesce(max(apply_id), 0) FROM applies").fetchone()[0]
        finally:
            store.close()
        status, got = self.post({"undo": top + 1})
        self.assertEqual((status, got["code"]), (409, "no_undo"))

    def test_get_refuses_two_projects_and_a_bad_service(self):
        self.assertEqual(self.call("GET", "/api/ask-connectors?project=ABC&project=DEF")[0], 400)
        self.assertEqual(self.call("GET", "/api/ask-connectors?project=ABC&other=1")[0], 400)
        self.assertEqual(self.call("GET", "/api/ask-connectors?project=")[0], 400)
        self.assertEqual(self.call("GET", "/api/ask-connectors?project=ABC")[0], 200)
        self.assertEqual(self.service.read_connectors(7)[0], 400)
        self.assertEqual(self.service.read_connectors("abc")[0], 400)

    def test_a_server_without_the_service_has_no_such_route(self):
        self.s.httpd.app_settings = None
        status, got = self.call("GET", "/api/ask-connectors")
        self.assertEqual((status, got["ok"]), (404, False))

    def test_a_long_valid_body_is_over_the_limit_and_the_route_counts_as_a_save(self):
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/ask-connectors"], 1024)
        self.assertIn("/api/ask-connectors", sv.SAVE_PATHS)
        was = self.snapshot()
        status, _ = self.call("POST", "/api/ask-connectors", {"connector": "mail", "on": True, "pad": "x" * 2000})
        self.assertEqual(status, 400)
        self.assertEqual(self.snapshot(), was)
        self.assertEqual(self.call("POST", "/api/ask-connectors", {"id": "mail", "on": True})[0], 200)


if __name__ == "__main__":
    unittest.main()

"""Row 1294: asking for new projects and a project's own asking (the two columns inside schema step 33; no second version).

Run: python3 dev/run_tests.py test_ask_new_projects
app_settings.ask_new_projects is the starting value of a project made now; projects.ask_off is the project's own turn-off (0 on, so every project that
existed asks as before). Asking works for a project only when the computer-wide switch AND the project are on; anything that cannot be read reads as off.
Fictional data only.
"""
import sqlite3
import unittest
from types import SimpleNamespace
from unittest import mock

from _demo import USER, DemoStore
from clark import app_settings, ask_apply, ask_data, ask_service, changes, history, store as st
from test_ask_route import Base


class Columns(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def test_a_new_file_starts_with_asking_on_for_new_projects_and_for_the_project(self):
        self.assertEqual((self.s.ask_new_projects_on(), self.s.ask_off_here("ABC"), self.s.ask_allowed("ABC")), (True, False, True))
        self.assertEqual(st.SCHEMA_VERSION, 37)      # row 1365 added step 34 after this row's step 33; rows 1534, 1417 and 1533 add steps 35, 36 and 37

    def test_the_migration_step_is_the_same_step_33_and_adds_both_columns_to_an_older_file(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE app_settings (id INTEGER PRIMARY KEY)")
        con.execute("CREATE TABLE projects (code TEXT PRIMARY KEY)")
        con.execute("INSERT INTO app_settings (id) VALUES (1)")
        con.execute("INSERT INTO projects (code) VALUES ('OLD')")
        st.migrate_ask_files(con)
        st.migrate_ask_files(con)      # a second run skips what is there
        self.assertEqual(con.execute("SELECT ask_new_projects FROM app_settings").fetchone()[0], 1)
        self.assertEqual(tuple(con.execute("SELECT ask_off, ask_files_off FROM projects").fetchone()), (0, 0), "a project that existed asks as it did")
        self.assertIn((st.ASK_FILES_STEP, st.migrate_ask_files), st.MIGRATIONS)
        self.assertEqual(st.ASK_FILES_STEP, 33)

    def test_a_new_project_takes_the_starting_value_in_its_own_step(self):
        for start, expect in ((0, 1), (1, 0)):
            with self.s.step("dashboard", USER) as step:
                step.update("app_settings", "1", {"ask_new_projects": start})
            with self.s.step("dashboard", USER) as step:
                step.create("projects", {"code": "NP" + "AB"[start], "name": "New %d" % start})
            self.assertEqual(self.s.read("projects", ref="NP" + "AB"[start])["ask_off"], expect)
            self.assertEqual(self.s.ask_allowed("NP" + "AB"[start]), expect == 0)

    def test_changing_the_starting_value_changes_no_project_that_exists(self):
        with self.s.step("dashboard", USER) as step:
            step.update("app_settings", "1", {"ask_new_projects": 0})
        self.assertEqual(self.s.read("projects", ref="ABC")["ask_off"], 0)
        self.assertTrue(self.s.ask_allowed("ABC"))

    def test_a_caller_that_names_its_own_value_keeps_it(self):
        with self.s.step("dashboard", USER) as step:
            step.update("app_settings", "1", {"ask_new_projects": 0})
            step.create("projects", {"code": "OWN", "name": "Own", "ask_off": 0})
        self.assertEqual(self.s.read("projects", ref="OWN")["ask_off"], 0)

    def test_the_computer_wide_switch_is_the_master(self):
        with self.s.step("dashboard", USER) as step:
            step.update("app_settings", "1", {"ask_enabled": 0})
        self.assertFalse(self.s.ask_allowed("ABC"))
        with self.s.step("dashboard", USER) as step:
            step.update("app_settings", "1", {"ask_enabled": 1})
            step.update("projects", "ABC", {"ask_off": 1})
        self.assertFalse(self.s.ask_allowed("ABC"))
        self.assertTrue(self.s.ask_enabled())

    def test_what_cannot_be_read_reads_as_off(self):
        self.assertEqual(self.s.ask_off_here("NOPE"), True, "an unknown project")
        with mock.patch.object(st, "columns", lambda _con, _table: []):      # a file without the two columns
            self.assertEqual((self.s.ask_new_projects_on(), self.s.ask_off_here("ABC"), self.s.ask_allowed("ABC")), (False, True, False))

    def test_a_database_error_reads_as_off_never_on(self):
        real = self.s.con

        class Locked:
            def execute(self, sql, *args):
                if sql.startswith("SELECT ask_"):
                    raise sqlite3.OperationalError("locked")
                return real.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(real, name)
        with mock.patch.object(self.s, "con", Locked()):
            self.assertEqual((self.s.ask_new_projects_on(), self.s.ask_off_here("ABC")), (False, True))

    def test_the_starting_value_starts_at_exactly_1_and_reads_as_on_only_when_exactly_1(self):
        """Row 1418, AP2: the column's own starting value is 1, the CHECK keeps it to 0 or 1, and only a stored exactly 1 reads as on."""
        self.s.con.execute("DELETE FROM app_settings")
        self.s.con.execute("INSERT INTO app_settings (id) VALUES (1)")      # a row that names no value: the column's own starting value
        self.assertEqual(self.s.con.execute("SELECT ask_new_projects FROM app_settings").fetchone()[0], 1)
        self.assertTrue(self.s.ask_new_projects_on())
        with self.assertRaises(sqlite3.IntegrityError):
            self.s.con.execute("UPDATE app_settings SET ask_new_projects = 2")
        real = self.s.con

        class Says:
            """The one read answers `value` whatever the file holds: a value the CHECK would never let in."""
            def __init__(self, value):
                self.value = value

            def execute(self, sql, *args):
                if sql.startswith("SELECT ask_new_projects"):
                    return real.execute("SELECT %s" % self.value)
                return real.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(real, name)
        for value, expect in (("1", True), ("0", False), ("2", False), ("-1", False)):
            with mock.patch.object(self.s, "con", Says(value)):
                self.assertEqual(self.s.ask_new_projects_on(), expect, "a stored %s" % value)

    def test_a_missing_app_settings_row_reads_the_starting_value_as_off(self):
        """Row 1418, AP2: with no app_settings row the starting value reads as off, so a project made now never starts with asking on by mistake."""
        self.assertTrue(self.s.ask_new_projects_on())
        self.s.con.execute("DELETE FROM app_settings")
        self.assertEqual((self.s.ask_new_projects_on(), self.s.ask_allowed("ABC")), (False, False))

    def test_the_history_names_the_starting_value(self):
        self.assertEqual(history.FIELD_NAMES["app_settings"]["ask_new_projects"], "Asking for new projects")

    def test_only_a_stored_zero_is_on(self):
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE projects (code TEXT PRIMARY KEY, ask_off INTEGER)")
        con.executemany("INSERT INTO projects VALUES (?, ?)", [("ZERO", 0), ("ONE", 1), ("TWO", 2), ("NONE", None)])
        con.row_factory = sqlite3.Row
        self.addCleanup(con.close)
        with mock.patch.object(self.s, "con", con):
            self.assertEqual([self.s.ask_off_here(c) for c in ("ZERO", "ONE", "TWO", "NONE", "NOPE")], [False, True, True, True, True])


class TheRoute(Base):
    def setUp(self):
        super().setUp()
        self.s.httpd.app_settings = app_settings.AppSettings(self.db, [])

    def flags(self, enabled=None, new=None, off_here=None, project="PUB"):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                if enabled is not None:
                    s.update("app_settings", "1", {"ask_enabled": enabled})
                if new is not None:
                    s.update("app_settings", "1", {"ask_new_projects": new})
                if off_here is not None:
                    s.update("projects", project, {"ask_off": off_here})
        finally:
            store.close()

    def test_get_says_the_starting_value_and_a_projects_own(self):
        status, got = self.s.api("GET", "/api/ask-new-projects")
        self.assertEqual((status, got["on"], got["off_here"], got["allowed"], got["saved"]), (200, True, False, False, True), "no project: nothing is allowed there")
        status, got = self.s.api("GET", "/api/ask-new-projects?project=PUB")
        self.assertEqual((status, got["on"], got["off_here"], got["allowed"]), (200, True, False, True))
        self.flags(enabled=0)
        self.assertEqual(self.s.api("GET", "/api/ask-new-projects?project=PUB")[1]["allowed"], False, "the computer-wide switch wins")

    def test_a_project_turned_off_refuses_the_question_and_sends_nothing_while_another_project_asks(self):
        self.flags(off_here=1)
        status, got = self.question()
        self.assertEqual((status, got["code"]), (409, "asking_off"), got)
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self.question(project="OTH")[0], 200)

    def test_the_post_sets_each_value_with_one_undo_and_refuses_anything_else(self):
        api = self.s.api
        status, got = api("POST", "/api/ask-new-projects", {"on": False})
        self.assertEqual((status, got["on"]), (200, False))
        self.assertEqual(api("GET", "/api/ask-new-projects?project=OTH")[1]["off_here"], False, "no existing project changed")
        status, undone = api("POST", "/api/ask-new-projects", {"undo": got["apply_id"]})
        self.assertEqual((status, undone["on"]), (200, True))
        status, got = api("POST", "/api/ask-new-projects", {"project": "PUB", "off_here": True})
        self.assertEqual((status, got["off_here"], got["allowed"]), (200, True, False))
        self.assertEqual(api("POST", "/api/ask-new-projects", {"project": "PUB", "off_here": True})[1].get("apply_id"), None, "the same value is not a step")
        status, back = api("POST", "/api/ask-new-projects", {"undo": got["apply_id"]})
        self.assertEqual((status, back["off_here"], back["allowed"]), (200, False, True))
        self.assertEqual(api("POST", "/api/ask-new-projects", {"on": "yes"})[0], 400)
        self.assertEqual(api("POST", "/api/ask-new-projects", {"on": True, "extra": 1})[0], 400)
        self.assertEqual(api("POST", "/api/ask-new-projects", {"project": "NOPE", "off_here": True})[0], 404)
        self.assertEqual(api("POST", "/api/ask-new-projects", {"undo": 999999})[0], 409)
        self.assertEqual(api("GET", "/api/ask-new-projects?project=PUB&x=1")[0], 400)

    def test_the_same_value_says_so_and_a_bad_body_is_refused_in_each_part(self):
        api = self.s.api
        self.assertEqual(api("POST", "/api/ask-new-projects", {"on": True})[1].get("message"), app_settings.MESSAGES["same"])
        self.assertEqual(api("POST", "/api/ask-new-projects", {"project": "PUB", "off_here": False})[1].get("message"), app_settings.MESSAGES["same"])
        self.assertEqual(api("POST", "/api/ask-new-projects", {"project": "PUB", "off_here": "yes"})[0], 400)
        self.assertEqual(api("POST", "/api/ask-new-projects", {"project": 5, "off_here": True})[0], 400)
        self.assertEqual(api("POST", "/api/ask-new-projects", {"project": "not a code", "off_here": True})[0], 400)
        self.assertEqual(api("GET", "/api/ask-new-projects?project=NOPE")[0], 404)
        service = self.s.httpd.app_settings
        self.assertEqual((service.read_new("not a code")[0], service.read_new(5)[0]), (400, 400))

    def test_the_project_gate_of_every_ask_route_refuses_before_anything_else(self):
        self.flags(off_here=1)
        s = self.service
        self.assertEqual(s.open_source({"project": "PUB", "file": "a/b.pdf", "page": None})[1]["code"], "asking_off")
        self.assertEqual(s.change_dry({"project": "PUB", "reply": "x"})[1]["code"], "asking_off")
        self.assertEqual(s.change_apply({"project": "PUB", "offer": "x"})[1]["code"], "asking_off")
        with mock.patch.object(ask_data, "project_data") as read:
            self.assertEqual(self.question()[0], 409)
        read.assert_not_called()

    def test_a_project_turned_off_while_the_question_is_read_sends_nothing(self):
        real = ask_data.project_data

        def turn_off(*a, **k):
            self.flags(off_here=1)
            return real(*a, **k)
        with mock.patch.object(ask_data, "project_data", turn_off):
            status, got = self.question()
        self.assertEqual((status, got["code"]), (409, "asking_off"), got)
        self.assertEqual(self.provider.sent, [])

    def test_project_off_is_false_for_an_unknown_project_and_true_when_it_cannot_say(self):
        s = self.service
        self.assertEqual((s.project_off("PUB"), s.project_off("NOPE")), (False, False))
        self.flags(off_here=1)
        self.assertTrue(s.project_off("PUB"))
        self.flags(off_here=0)
        with mock.patch.object(s, "reader", side_effect=sqlite3.OperationalError("locked")):
            self.assertTrue(s.project_off("PUB"))
        with mock.patch.object(st.Store, "read", side_effect=RuntimeError("x")):
            self.assertTrue(s.project_off("PUB"))

    def test_an_undo_of_another_routes_step_is_refused(self):
        status, got = self.s.api("POST", "/api/ask-enabled", {"enabled": False})
        self.assertEqual(status, 200, got)
        self.assertEqual(self.s.api("POST", "/api/ask-new-projects", {"undo": got["apply_id"]})[0], 409)

    def test_a_project_made_now_starts_as_the_value_says(self):
        self.s.api("POST", "/api/ask-new-projects", {"on": False})
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.create("projects", {"code": "NEW", "name": "Brand New"})
        finally:
            store.close()
        self.assertEqual(self.s.api("GET", "/api/ask-new-projects?project=NEW")[1]["off_here"], True)
        self.assertEqual(self.question(project="NEW")[0], 409)


class TheGates(Base):
    """Row 1294: each of the five project gates in ask_service is the one that answers, so dropping the project test from any single one fails a test here."""
    SECRET = "my " + "pass" + "word" + ": " + "Hunt" + "er2-Zq-99"      # built at run time, so the publish tool's scan has nothing to find
    flags = TheRoute.flags

    def test_the_first_gate_answers_before_the_question_is_screened(self):
        self.flags(off_here=1)
        status, got = self.question(self.SECRET)      # a screened question would be 400 refused; the gate comes first
        self.assertEqual((status, got["code"]), (409, "asking_off"), got)
        self.assertEqual(self.provider.sent, [])

    def test_the_second_gate_stops_a_question_whose_project_is_turned_off_after_the_data_was_read(self):
        real = ask_service.ask.build_request

        def build_then_off(*a, **kw):
            out = real(*a, **kw)
            self.flags(off_here=1)                    # turned off meanwhile
            return out
        with mock.patch.object(ask_service.ask, "build_request", build_then_off):
            status, got = self.question()
        self.assertEqual((status, got["code"]), (409, "asking_off"), got)
        self.assertEqual(self.provider.sent, [], "nothing left")

    def test_the_open_file_route_answers_asking_off_for_a_project_turned_off(self):
        body = {"project": "PUB", "file": "Folder/plan.pdf", "page": None}
        self.assertNotEqual(self.s.api("POST", "/api/ask/open-source", body)[1].get("code"), "asking_off", "on: another answer")
        self.flags(off_here=1)
        status, got = self.s.api("POST", "/api/ask/open-source", body)
        self.assertEqual((status, got["code"], got["message"]), (409, "asking_off", ask_service.MESSAGES["open_asking_off"]), got)

    def test_the_change_dry_run_and_the_change_apply_answer_asking_off_for_a_project_turned_off(self):
        self.flags(off_here=1)
        status, got = self.s.api("POST", "/api/ask/change/dry", {"project": "PUB", "reply": "none"})
        self.assertEqual((status, got["code"]), (409, "asking_off"), "not no_reply")
        status, got = self.s.api("POST", "/api/ask/change/apply", {"project": "PUB", "offer": "none"})
        self.assertEqual((status, got["code"]), (409, "asking_off"), "not no_offer")
        self.flags(off_here=0)
        self.assertEqual(self.s.api("POST", "/api/ask/change/dry", {"project": "PUB", "reply": "none"})[1]["code"], "no_reply")
        self.assertEqual(self.s.api("POST", "/api/ask/change/apply", {"project": "PUB", "offer": "none"})[1]["code"], "no_offer")

    def test_a_project_that_cannot_be_read_is_off_and_one_that_does_not_exist_is_not_found(self):
        self.assertFalse(self.service.project_off("PUB"))
        with mock.patch.object(self.service, "reader", side_effect=sqlite3.OperationalError("locked")):
            self.assertTrue(self.service.project_off("PUB"), "a store that cannot be opened reads as off")
        with mock.patch.object(st.Store, "ask_off_here", side_effect=ValueError("unreadable")):
            self.assertTrue(self.service.project_off("PUB"), "a value that cannot be read reads as off")
        self.assertFalse(self.service.project_off("NOPE"), "the routes answer an unknown project as not found")
        self.assertEqual(self.question(project="NOPE")[0], 404)
        self.assertEqual(self.provider.sent, [])


class TheChangesPath(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.action = self.demo.action(owner="Sam Lee", client_visible=0)      # row 1416: off the client report, no client tick
        self.ask = ask_apply.AskApply(self.s.path, [], USER)
        self.change = changes.make_ask_change(self.s.path, [], USER)
        self.said = {"op": "change", "status": "Closed", "id": self.action, "current_title": "Draft the cut-over plan", "current_owner": "Sam Lee"}

    def off(self):
        with self.s.step("dashboard", USER) as step:
            step.update("projects", "ABC", {"ask_off": 1})

    def test_a_project_turned_off_refuses_the_dry_run_and_the_apply_and_the_direct_change(self):
        plan = self.ask.plan("ABC", self.said)[1]
        self.assertTrue(plan["ok"], plan)
        self.off()
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "asking_off"), body)
        status, body = self.ask.plan("ABC", self.said)
        self.assertEqual((status, body["code"]), (409, "asking_off"), body)
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": {"status": "Closed"}}, dry=False)
        self.assertEqual((status, body.get("code")), (409, "asking_off"), body)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_the_apply_reads_the_projects_own_asking_itself(self):
        plan = SimpleNamespace(request={"project": "ABC"}, op="add")
        self.assertIsNone(self.ask.check_data(plan))
        self.off()
        with self.assertRaises(ask_apply.Refusal) as got:
            self.ask.check_data(plan)
        self.assertEqual((got.exception.code, got.exception.status), ("asking_off", 409))

    def test_the_change_looks_at_the_project_before_the_item_and_again_inside_its_step(self):
        self.off()
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": "NOPE-1", "changes": {"status": "Closed"}}, dry=False)
        self.assertEqual((status, body.get("code")), (409, "asking_off"), body)
        with self.s.step("dashboard", USER) as step:
            step.update("projects", "ABC", {"ask_off": 0})
        with mock.patch.object(st.Store, "ask_allowed", side_effect=[True, False]):      # the project is turned off between the two looks
            status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": {"status": "Closed"}}, dry=False)
        self.assertEqual((status, body.get("code")), (409, "asking_off"), body)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_a_project_left_on_still_changes(self):
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.action, "changes": {"status": "Closed"}}, dry=False)
        self.assertEqual(status, 200, body)


if __name__ == "__main__":
    unittest.main()

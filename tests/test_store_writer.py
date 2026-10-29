"""#31: the one writer. Steps, logging, IDs, the rules, two writers, and the source rules that keep store.py the only writer."""
import ast
import re
import tempfile
import threading
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import ROOT, SRC
from clark import store as store_module
from clark.store import Invalid, connect, open_store

SAID = ("This item can't be closed or cancelled before the day it was raised. "
        "Check the raised date, then try again.")
STORE = SRC / "clark" / "store.py"


def dump(store):
    return list(store.con.iterdump())


class Steps(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def test_an_update_of_three_fields_logs_one_step_three_changes_three_events(self):
        a = self.demo.action()
        before = self.s.read("actions", ref=a)
        step = self.demo.update("actions", a, {"owner": "Sam Example", "priority": "High", "due_date": "2030-01-31"})
        applies = self.s.con.execute("SELECT * FROM applies WHERE apply_id = ?", (step,)).fetchall()
        self.assertEqual(len(applies), 1)
        self.assertEqual(applies[0]["by_user"], USER)
        self.assertEqual(applies[0]["device"], self.s.device)
        rows = self.s.con.execute("SELECT rowid, * FROM change_log WHERE apply_id = ? AND field != 'updated_at' ORDER BY rowid",
                                  (step,)).fetchall()
        self.assertEqual([(r["field"], r["old_value"], r["new_value"], r["op"]) for r in rows],
                         [("owner", before["owner"], "Sam Example", "update"),
                          ("priority", "Medium", "High", "update"),
                          ("due_date", None, "2030-01-31", "update")])
        events = self.s.con.execute("SELECT * FROM item_events WHERE apply_id = ?", (step,)).fetchall()
        self.assertEqual(sorted(e["change"] for e in events), [r["rowid"] for r in rows])
        self.assertTrue(all(e["route"] == "dashboard" and e["actor"] == "you" and e["item_id"] == a for e in events))

    def test_an_update_to_the_same_value_writes_nothing(self):
        a = self.demo.action(owner="Sam Example")
        before = dump(self.s)
        with self.s.step("dashboard", USER) as st:
            st.update("actions", a, {"owner": "Sam Example"})
        self.assertEqual(dump(self.s), before)

    def test_an_error_inside_a_step_leaves_the_database_as_it_was(self):
        a = self.demo.action()
        before = dump(self.s)
        with self.assertRaises(RuntimeError):
            with self.s.step("dashboard", USER) as st:
                st.update("actions", a, {"owner": "Sam Example"})
                st.create("actions", {"project": "ABC", "description": "x", "raised": "2026-10-01", "source": "demo"})
                raise RuntimeError("stop")
        self.assertEqual(dump(self.s), before)
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.update("actions", a, {"owner": "Sam Example"})
                st.update("actions", a, {"status": "Finished"})
        self.assertEqual(dump(self.s), before)

    def test_null_and_empty_text_stay_different_in_the_log(self):
        a = self.demo.action(latest_update="")
        step = self.demo.update("actions", a, {"latest_update": None})
        r = self.s.con.execute("SELECT old_value, new_value FROM change_log WHERE apply_id = ? AND field = 'latest_update'",
                               (step,)).fetchone()
        self.assertEqual((r["old_value"], r["new_value"]), ("", None))

    def test_a_step_needs_who_and_a_known_route(self):
        with self.assertRaises(Invalid):
            Steps_step = self.s.step("dashboard", " ")
            Steps_step.__enter__()
        with self.assertRaises(Invalid):
            self.s.step("email", USER).__enter__()

    def test_field_names_come_from_the_table_only(self):
        a = self.demo.action()
        for bad in ({"owner = 'x' --": "y"}, {"nonsense": 1}, {"id": "ABC-A-099"}, {"updated_at": "now"}):
            with self.subTest(bad=bad), self.assertRaises(Invalid):
                self.demo.update("actions", a, bad)
        with self.assertRaises(Invalid):
            self.s.read("actions; DROP TABLE actions", "ABC")


class Ids(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def test_actions_raid_and_decisions_share_one_sequence(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01", "source": "s"})
            d = st.create("decisions", {"project": "ABC", "decision": "Go", "date": "2026-10-01", "source": "s"})
            m = st.create("milestones", {"project": "ABC", "name": "Second", "source": "s"})
            u = st.create("use_cases", {"project": "ABC", "title": "Second", "status": "Flag", "source": "s"})
        self.assertEqual((a, r, d, m, u), ("ABC-A-001", "ABC-002", "ABC-D-003", "ABC-M-002", "ABC-U-002"))

    def test_an_undone_creation_never_frees_its_number(self):
        self.assertEqual(self.demo.action(), "ABC-A-001")
        self.s.undo(self.demo.last_step(), USER)
        self.assertIsNone(self.s.read("actions", ref="ABC-A-001"))
        self.assertEqual(self.demo.action(), "ABC-A-002")

    def test_a_new_item_carries_no_id(self):
        with self.assertRaises(Invalid):
            self.demo.action(id="ABC-A-050")


class Rules(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store

    def tearDown(self):
        self.demo.close()

    def test_rules_refuse_with_a_plain_message(self):
        cases = [
            ({"workstream": "Testing"}, "isn't an active workstream"),
            ({"use_case": "ABC-U-009"}, "use case ABC-U-009 isn't here"),
            ({"milestone": "ABC-M-009"}, "milestone ABC-M-009 isn't here"),
            ({"due_date": "2030-02-30"}, "is not a real date"),
            ({"priority": "Critical"}, "priority must be one of"),
            ({"labels": "Unknown"}, "unknown label"),
            ({"project": "XYZ"}, "project XYZ isn't here"),
        ]
        for values, words in cases:
            with self.subTest(values=values):
                with self.assertRaises(Invalid) as e:
                    self.demo.action(**values)
                self.assertIn(words, str(e.exception))

    def test_workstream_and_use_case_take_their_own_spelling(self):
        a = self.demo.action(workstream="build", use_case=self.demo.use_case)
        row = self.s.read("actions", ref=a)
        self.assertEqual((row["workstream"], row["use_case"]), ("Build", "ABC-U-001"))

    def test_a_milestone_workstream_is_checked_like_an_action(self):
        with self.assertRaises(Invalid):
            self.demo.update("milestones", self.demo.milestone, {"workstream": "Nope"})
        self.demo.update("milestones", self.demo.milestone, {"workstream": "BUILD"})
        self.assertEqual(self.s.read("milestones", ref=self.demo.milestone)["workstream"], "Build")

    def test_a_rebaseline_needs_who_why_and_where_and_records_a_decision(self):
        with self.assertRaises(Invalid):
            self.demo.update("milestones", self.demo.milestone, {"baseline_date": "2030-04-01"})
        self.demo.update("milestones", self.demo.milestone, {"baseline_date": "2030-04-01"},
                         rebaseline={"agreed_with": "Sponsor", "reason": "Scope grew", "source": "Steering, 01-10-2026"})
        d = self.s.read("decisions", "ABC")
        self.assertEqual(len(d), 1)
        self.assertIn("01-03-2030 to 01-04-2030", d[0]["decision"])

    def test_work_items_are_never_deleted(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.cancel("actions", a)
        self.assertEqual(self.s.read("actions", ref=a)["status"], "Cancelled")
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.cancel("milestones", self.demo.milestone)

    def test_closing_an_item_raised_in_the_future_is_refused_in_plain_words_and_writes_nothing(self):
        """#135: the table's closed >= raised rule used to surface as a bare database error."""
        for kind, extra in (("actions", {}), ("raid", {"type": "Risk"})):
            with self.s.step("dashboard", USER) as st:
                ref = st.create(kind, {"project": "ABC", "description": "d", "raised": "2999-01-01", "source": "demo", **extra})
            before = self.s.con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log)").fetchone()
            with self.assertRaises(Invalid) as got:
                self.demo.update(kind, ref, {"status": "Closed"})
            self.assertEqual(str(got.exception), SAID)
            self.assertEqual(self.s.con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log)").fetchone(), before)
            row = self.s.read(kind, ref=ref)
            self.assertEqual((row["status"], row["closed"]), ("Open", None))
            self.demo.update(kind, ref, {"owner": "Sam Example"})       # the connection is usable and a valid update still works
            self.assertEqual(self.s.read(kind, ref=ref)["owner"], "Sam Example")

    def test_cancelling_an_item_raised_in_the_future_says_closed_or_cancelled(self):
        with self.s.step("dashboard", USER) as st:
            ref = st.create("actions", {"project": "ABC", "description": "d", "raised": "2999-01-01", "source": "demo"})
        with self.assertRaises(Invalid) as got:
            self.demo.update("actions", ref, {"status": "Cancelled"})
        self.assertEqual(str(got.exception), SAID)

    def test_raised_moved_past_the_closing_date_is_refused_in_plain_words(self):
        for kind, extra in (("actions", {}), ("raid", {"type": "Risk"})):
            with self.s.step("dashboard", USER) as st:
                ref = st.create(kind, {"project": "ABC", "description": "d", "raised": "2026-10-01", "source": "demo", **extra})
            self.demo.update(kind, ref, {"status": "Closed"})
            with self.assertRaises(Invalid) as got:
                self.demo.update(kind, ref, {"raised": "2999-01-01"})
            self.assertEqual(str(got.exception), SAID)
            self.assertEqual(self.s.read(kind, ref=ref)["raised"], "2026-10-01")

    def test_an_item_created_closed_with_a_future_raised_date_is_refused_in_plain_words(self):
        for kind, extra in (("actions", {}), ("raid", {"type": "Risk"})):
            with self.assertRaises(Invalid) as got:
                with self.s.step("dashboard", USER) as st:
                    st.create(kind, {"project": "ABC", "description": "d", "raised": "2999-01-01", "status": "Closed",
                                     "source": "demo", **extra})
            self.assertEqual(str(got.exception), SAID)

    def test_closed_set_earlier_than_raised_is_refused_in_plain_words(self):
        a = self.demo.action(raised="2026-10-05")
        self.demo.update("actions", a, {"status": "Closed"})
        with self.assertRaises(Invalid) as got:
            self.demo.update("actions", a, {"closed": "2026-10-01"})
        self.assertEqual(str(got.exception), SAID)

    def test_closing_on_the_day_it_was_raised_is_allowed(self):
        a = self.demo.action(raised=store_module.today())
        self.demo.update("actions", a, {"status": "Closed"})
        self.assertEqual(self.s.read("actions", ref=a)["closed"], store_module.today())

    def test_closing_sets_closed_and_raid_priority_is_worked_out(self):
        a = self.demo.action()
        self.demo.update("actions", a, {"status": "Closed"})
        self.assertTrue(self.s.read("actions", ref=a)["closed"])
        with self.s.step("dashboard", USER) as st:
            r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01",
                                   "source": "s", "impact": "High", "likelihood": "Low"})
        self.assertEqual(self.s.read("raid", ref=r)["priority"], "High")


class Opening(unittest.TestCase):
    def test_a_folder_inside_onedrive_is_refused(self):
        demo = DemoStore()
        try:
            with self.assertRaises(Exception) as e:
                open_store(demo.dir / "clark2.db", onedrive_roots=[demo.dir])
            self.assertIn("OneDrive", str(e.exception))
        finally:
            demo.close()

    def test_a_newer_database_is_refused(self):
        demo = DemoStore()
        try:
            demo.store.con.execute("UPDATE meta SET v = '99' WHERE k = 'schema_version'")
            with self.assertRaises(Invalid):
                open_store(demo.dir / "clark.db", onedrive_roots=[])
        finally:
            demo.close()

    def test_opening_again_keeps_the_data_and_the_device(self):
        demo = DemoStore()
        try:
            again = open_store(demo.dir / "clark.db", onedrive_roots=[])
            self.assertEqual(again.device, demo.store.device)
            self.assertEqual(again.read("projects", ref="ABC")["name"], "Example Programme")
            again.close()
        finally:
            demo.close()

    def test_data_for_reads_one_project_without_writing(self):
        demo = DemoStore()
        try:
            a = demo.action(milestone=demo.milestone, labels="Sensitive")
            data = demo.store.data_for("ABC")
            self.assertEqual(data["project"]["code"], "ABC")
            self.assertEqual([x["id"] for x in data["actions"]], [a])
            self.assertEqual(data["labels"], {a: ["Sensitive"]})
            self.assertIsNone(demo.store.data_for("XYZ"))
            ro = connect(demo.dir / "clark.db", readonly=True)
            with self.assertRaises(Exception):
                ro.execute("DELETE FROM actions")
            ro.close()
        finally:
            demo.close()


class TwoWriters(unittest.TestCase):
    def test_two_connections_writing_at_once_both_land(self):
        demo = DemoStore()
        try:
            started, done = threading.Event(), []

            def second():
                other = open_store(demo.dir / "clark.db", onedrive_roots=[])
                started.wait(5)
                with other.step("excel", USER) as st:
                    done.append(st.create("actions", {"project": "ABC", "description": "from import", "raised": "2026-10-01",
                                                      "source": "demo"}))
                other.close()

            t = threading.Thread(target=second)
            t.start()
            with demo.store.step("dashboard", USER) as st:
                first = st.create("actions", {"project": "ABC", "description": "from page", "raised": "2026-10-01",
                                              "source": "demo"})
                started.set()
                t.join(0.3)                     # the import waits for this step's lock
                self.assertTrue(t.is_alive())
            t.join(10)
            self.assertEqual((first, done), ("ABC-A-001", ["ABC-A-002"]))
            self.assertEqual(len(demo.store.read("actions", "ABC")), 2)
        finally:
            demo.close()


SQL_WORDS = ("INSERT", "UPDATE", "DELETE", "REPLACE", "DROP", "ALTER", "CREATE")
# The only expressions store.py may put inside SQL it builds: table names that went through _table() or were checked in
# TABLES, key clauses, and column lists taken from the table (test 14; Head ruling on #31). A change here is a guarded review.
STORE_SQL_PARTS = {
    "_table(table)", "_table(t)", "_table(kind)", "where_key(table)", "', '.join(values)", "', '.join('?' * len(values))",
    "', '.join((f'{f} = ?' for f in diff))", "col", "order", "f'{f} = ?'", "f", "k", "project", "ID_PREFIX[table]", "n + 1",
    "picked_columns", "PUBLISH_ORDER[t]",         # publish_inputs (#39): `picked_columns` is a column list that pick() checked against the table and against NEVER_PUBLISH
}


def _is_sql(literal):
    """SQL is written in capitals here: a statement word as a whole word, in capitals, marks a string as SQL."""
    return any(re.search(rf"\b{w}\b", literal) for w in SQL_WORDS + ("SELECT", "PRAGMA", "WHERE"))


def _sql_fstrings(tree):
    """(line, [formatted expressions]) for every f-string or % / .format string in `tree` that holds an SQL word."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            literal = "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
            if _is_sql(literal):
                out.append((node.lineno, [ast.unparse(v.value) for v in node.values if isinstance(v, ast.FormattedValue)]))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Constant) \
                and isinstance(node.left.value, str) and _is_sql(node.left.value):
            out.append((node.lineno, ["%"]))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format" \
                and isinstance(node.func.value, ast.Constant) and isinstance(node.func.value.value, str) \
                and _is_sql(node.func.value.value):
            out.append((node.lineno, [".format"]))
    return out


def writes_sql(value):
    """Whether a string starts like a statement that writes: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE (in any case), or
    REPLACE INTO. A lone word "replace" (an error handler's name) is not SQL, and lower-case SQL is still caught."""
    words = value.upper().split()
    if not words:
        return False
    if words[0] == "REPLACE":
        return len(words) > 1 and words[1] == "INTO"
    return words[0] in SQL_WORDS


class OneWriter(unittest.TestCase):
    def modules(self):
        for path in sorted((SRC / "clark").rglob("*.py")):
            yield path, ast.parse(path.read_text(encoding="utf-8"))

    def test_only_store_py_writes_or_opens_the_database_for_writing(self):
        problems = []
        for path, tree in self.modules():
            if path == STORE:
                continue
            rel = path.relative_to(SRC).as_posix()
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if writes_sql(node.value):
                        problems.append(f"{rel}:{node.lineno}: writes SQL")
                if isinstance(node, ast.Attribute) and node.attr == "connect" and isinstance(node.value, ast.Name) \
                        and node.value.id == "sqlite3":
                    problems.append(f"{rel}:{node.lineno}: opens a database (only store.py may)")
        self.assertEqual(problems, [])

    def test_no_sql_is_built_from_a_name_outside_store_py(self):
        problems = []
        for path, tree in self.modules():
            if path == STORE:
                continue
            for line, parts in _sql_fstrings(tree):
                problems.append(f"{path.relative_to(SRC).as_posix()}:{line}: builds SQL from {parts}")
        self.assertEqual(problems, [])

    def test_store_py_builds_sql_only_from_checked_names(self):
        tree = ast.parse(STORE.read_text(encoding="utf-8"))
        self.assertGreater(len(_sql_fstrings(tree)), 10)        # the checker is reading store.py's SQL
        problems = [f"store.py:{line}: {p}" for line, parts in _sql_fstrings(tree) for p in parts if p not in STORE_SQL_PARTS]
        self.assertEqual(problems, [])

    def test_the_writer_check_is_case_insensitive_and_tells_a_word_from_a_statement(self):
        for sql in ("INSERT INTO x VALUES (1)", "insert into x values (1)", "Update x set y = 1", "delete from x", "DROP TABLE x",
                    "alter table x add y", "create table x (y)", "replace into x values (1)", "  REPLACE   INTO x VALUES (1)"):
            self.assertTrue(writes_sql(sql), sql)
        for word in ("replace", "REPLACE", "replace the name", "updated", "inserted text", "created", "deleted by", "", "  "):
            self.assertFalse(writes_sql(word), word)
        with tempfile.TemporaryDirectory() as tmp:                       # and a scratch module planted in a copy of src/
            (Path(tmp) / "clark").mkdir()
            (Path(tmp) / "clark" / "sneaky.py").write_text('x = "insert into actions (id) values (\'a\')"\n', encoding="utf-8")
            found = [n for n in ast.walk(ast.parse((Path(tmp) / "clark" / "sneaky.py").read_text(encoding="utf-8")))
                     if isinstance(n, ast.Constant) and isinstance(n.value, str) and writes_sql(n.value)]
            self.assertEqual(len(found), 1)

    def test_the_checker_finds_sql_built_from_a_request(self):
        tree = ast.parse('def f(con, field, table):\n'
                         '    con.execute(f"UPDATE {table} SET {field} = ?")\n'
                         '    con.execute("DELETE FROM %s" % table)\n'
                         '    con.execute("SELECT * FROM {}".format(table))\n')
        self.assertEqual([p for _, p in _sql_fstrings(tree)], [["table", "field"], ["%"], [".format"]])


class Reuse(unittest.TestCase):
    def test_the_copy_is_recorded(self):
        text = (ROOT / "docs" / "REUSE-FROM-CREAITE.md").read_text(encoding="utf-8")
        for path in ("system/scripts/tracker.py", "system/scripts/schema.sql", "system/scripts/item_history.py", "system/scripts/backup.py"):
            with self.subTest(path=path):
                row = next((line for line in text.splitlines() if f"`{path}`" in line and line.startswith("|")), "")
                self.assertIn("db5adb2", row)
                self.assertIn("Yes", row)


if __name__ == "__main__":
    unittest.main()

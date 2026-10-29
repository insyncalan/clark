"""#89: a flag written as True or False is logged as the whole number the column holds, so Undo and Undo of the Undo work
(a bool used to be logged as "True" or "False", which the column never holds, so Undo skipped the row as "changed since")."""
import re
import unittest

from _demo import USER, DemoStore
from _paths import SRC
from clark import store as store_module

CASES = ((True, 1), (False, 0), (1, 1), (0, 0))
FLAG_FIELDS = (("actions", "client_visible"), ("raid", "client_visible"), ("decisions", "client_visible"),
               ("milestones", "client_visible"), ("use_cases", "client_visible"))


class Flags(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        with self.s.step("dashboard", USER) as st:
            self.refs = {
                "actions": st.create("actions", {"project": "ABC", "description": "d", "raised": "2026-10-01", "source": "demo"}),
                "raid": st.create("raid", {"project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01",
                                           "source": "demo"}),
                "decisions": st.create("decisions", {"project": "ABC", "decision": "Go", "date": "2026-10-01", "source": "demo"}),
                "milestones": self.demo.milestone,
                "use_cases": self.demo.use_case,
            }

    def tearDown(self):
        self.demo.close()

    def log_of(self, step, field):
        r = self.s.con.execute("SELECT old_value, new_value FROM change_log WHERE apply_id = ? AND field = ?",
                               (step, field)).fetchone()
        return (r["old_value"], r["new_value"]) if r else None

    def test_text_says_what_the_column_holds(self):
        self.assertEqual([store_module.text(v) for v in (True, False, 1, 0, None, "", "x", 5)],
                         ["1", "0", "1", "0", None, "", "x", "5"])

    def test_a_flag_written_as_true_false_1_or_0_logs_the_number_and_undoes_and_undoes_again(self):
        for table, field in FLAG_FIELDS:
            ref = self.refs[table]
            for first in (False, 0):                       # off; then back on with True and 1
                for back in (True, 1):
                    with self.subTest(table=table, off=first, on=back):
                        self.assertEqual(self.s.read(table, ref=ref)[field], 1)
                        off = self.demo.update(table, ref, {field: first})
                        self.assertEqual(self.log_of(off, field), ("1", "0"))
                        self.assertEqual(self.s.read(table, ref=ref)[field], 0)
                        undone = self.s.undo(off, USER)
                        self.assertEqual(undone["skipped"], [])
                        self.assertEqual(self.s.read(table, ref=ref)[field], 1)
                        redone = self.s.undo(undone["step_id"], USER)
                        self.assertEqual(redone["skipped"], [])
                        self.assertEqual(self.s.read(table, ref=ref)[field], 0)
                        on = self.demo.update(table, ref, {field: back})
                        self.assertEqual(self.log_of(on, field), ("0", "1"))
                        self.assertEqual(self.s.undo(on, USER)["skipped"], [])
                        self.assertEqual(self.s.read(table, ref=ref)[field], 0)
                        self.demo.update(table, ref, {field: 1})        # leave it on for the next case

    def test_a_flag_set_to_what_it_already_is_writes_nothing(self):
        ref = self.refs["actions"]
        before = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        for same in (True, 1):
            with self.s.step("dashboard", USER) as st:
                st.update("actions", ref, {"client_visible": same})
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], before)

    def test_other_flags_log_the_number_too(self):
        step = self.demo.update("projects", "ABC", {"active": False})
        self.assertEqual(self.log_of(step, "active"), ("1", "0"))
        self.assertEqual(self.s.undo(step, USER)["skipped"], [])
        self.assertEqual(self.s.read("projects", ref="ABC")["active"], 1)

    def test_a_flag_changed_twice_in_one_step_with_mixed_types_goes_back_to_the_original(self):
        ref = self.refs["actions"]
        with self.s.step("dashboard", USER) as st:
            st.update("actions", ref, {"client_visible": False})
            st.update("actions", ref, {"client_visible": 1})
            st.update("actions", ref, {"client_visible": False})
        out = self.s.undo(self.demo.last_step(), USER)
        self.assertEqual(out["skipped"], [])
        self.assertEqual(self.s.read("actions", ref=ref)["client_visible"], 1)


REFUSED = (0.0, 1.0, None, "", "1", "0", "True", 2, -1, 1.5, [], [1], {"a": 1})


class FlagRule(unittest.TestCase):
    """One rule for every 0/1 column: a bool becomes 0 or 1, anything else is refused in words and writes nothing (#89)."""

    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.ref = self.demo.action()

    def tearDown(self):
        self.demo.close()

    def test_every_zero_one_column_in_the_schema_is_in_the_rule(self):
        """Read schema.sql: a new CHECK (x IN (0,1)) column that is not in FLAG_COLUMNS (or named as handled elsewhere) fails."""
        sql = (SRC / "clark" / "schema.sql").read_text(encoding="utf-8")
        in_schema = set(re.findall(r"\b(\w+)\s+IN\s*\(\s*0\s*,\s*1\s*\)", sql))
        self.assertTrue({"client_visible", "active", "hidden", "beside", "word", "state_set"} <= in_schema, in_schema)
        missed = in_schema - store_module.FLAG_COLUMNS - store_module.FLAGS_ELSEWHERE
        self.assertEqual(sorted(missed), [], "a flag column the rule doesn't know")
        self.assertEqual(store_module.FLAGS_ELSEWHERE, {"archived"})
        self.assertFalse(store_module.FLAG_COLUMNS - in_schema, "the rule names a column the schema doesn't have")

    def test_flag_value_turns_bools_into_numbers_and_refuses_the_rest(self):
        self.assertEqual([store_module.flag_value("x", v) for v in (True, False, 1, 0)], [1, 0, 1, 0])
        self.assertTrue(all(type(store_module.flag_value("x", v)) is int for v in (True, False, 1, 0)))
        for bad in REFUSED:
            with self.subTest(bad=bad), self.assertRaisesRegex(store_module.Invalid, "x must be 0 or 1"):
                store_module.flag_value("x", bad)

    def test_check_values_refuses_every_bad_value_for_every_flag_column(self):
        for column in sorted(store_module.FLAG_COLUMNS):
            for bad in REFUSED:
                with self.subTest(column=column, bad=bad), self.assertRaisesRegex(store_module.Invalid, f"{column} must be 0 or 1"):
                    store_module.check_values("actions", {column: bad})
            values = {column: True}
            store_module.check_values("actions", values)
            self.assertEqual(values, {column: 1})
            self.assertIs(type(values[column]), int)

    def test_through_the_writer_a_bad_flag_is_refused_in_words_and_nothing_is_written(self):
        writes = (("actions", self.ref, "client_visible"), ("milestones", self.demo.milestone, "client_visible"),
                  ("milestones", self.demo.milestone, "state_set"), ("use_cases", self.demo.use_case, "client_visible"),
                  ("projects", "ABC", "active"))
        for table, ref, field in writes:
            for bad in REFUSED:
                before = list(self.s.con.iterdump())
                with self.subTest(table=table, field=field, bad=bad):
                    with self.assertRaisesRegex(store_module.Invalid, f"{field} must be 0 or 1"):
                        with self.s.step("dashboard", USER) as st:
                            st.update(table, ref, {field: bad})
                    self.assertEqual(list(self.s.con.iterdump()), before)

    def test_a_new_row_refuses_a_bad_flag_and_takes_a_bool(self):
        with self.assertRaisesRegex(store_module.Invalid, "client_visible must be 0 or 1"):
            self.demo.action(client_visible=None)
        with self.assertRaisesRegex(store_module.Invalid, "client_visible must be 0 or 1"):
            self.demo.action(client_visible=1.0)
        ref = self.demo.action(client_visible=False)
        self.assertEqual(self.s.read("actions", ref=ref)["client_visible"], 0)
        row = self.s.con.execute("SELECT new_value FROM change_log WHERE item_id = ? AND field = 'client_visible'", (ref,)).fetchone()
        self.assertEqual(row["new_value"], "0")

    def test_a_label_flag_and_a_project_flag_are_checked_too(self):
        with self.assertRaisesRegex(store_module.Invalid, "suggested must be 0 or 1"):
            store_module.check_values("item_labels", {"suggested": "yes"})
        with self.assertRaisesRegex(store_module.Invalid, "builtin must be 0 or 1"):
            store_module.check_values("labels", {"builtin": 2})

    def test_sort_order_must_be_a_whole_number_and_is_logged_as_one(self):
        for bad in (3.0, 2.5, "3", True, [3]):
            with self.subTest(bad=bad), self.assertRaisesRegex(store_module.Invalid, "sort_order must be a whole number"):
                self.demo.update("milestones", self.demo.milestone, {"sort_order": bad})
        step = self.demo.update("milestones", self.demo.milestone, {"sort_order": 3})
        self.assertEqual(self.s.con.execute("SELECT new_value FROM change_log WHERE apply_id = ? AND field = 'sort_order'",
                                            (step,)).fetchone()[0], "3")
        self.assertEqual(self.s.undo(step, USER)["skipped"], [])


if __name__ == "__main__":
    unittest.main()

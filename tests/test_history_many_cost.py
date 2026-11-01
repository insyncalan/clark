"""#251: history_many (what the freshness read calls on every data_for) must not walk the whole change_log or item_events table.
The cost is judged by the query plan, never by seconds: a plan line that SCANs the table itself reads every row, whatever else
is in the file, so the read grows with the log. The same answers as history() must come back (a link from another project
is the case a prefix test alone would miss)."""
import re
import unittest

from _demo import USER, DemoStore

TABLE_SCAN = re.compile(r"^SCAN (c|e|change_log|item_events)( AS \w+)?$")     # a SCAN of the table; "USING COVERING INDEX" is a narrow one


def _row_statements(con, run):
    """The expanded text of every statement `run()` sends that reads the log rows (the join of change_log to item_events that
    also reads the old and new values), found with the connection's trace."""
    seen = []
    con.set_trace_callback(lambda sql: seen.append(sql))
    try:
        run()
    finally:
        con.set_trace_callback(None)
    return [s for s in seen if s.lstrip().startswith("SELECT") and "FROM change_log c JOIN item_events e" in s
            and "c.old_value" in s]


def _two_projects(demo):
    s = demo.store
    with s.step("dashboard", USER) as st:
        st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
    mine = [demo.action(description="Mine %d" % n) for n in range(3)]
    other = [demo.action(project="XYZ", description="Other %d" % n) for n in range(3)]
    for n, a in enumerate(mine + other):
        demo.update("actions", a, {"owner": "Sam Example"})
        demo.update("actions", a, {"priority": "High"})
    return mine, other


class HistoryManyCost(unittest.TestCase):
    def test_the_row_read_does_not_scan_the_log_tables(self):
        from clark import history
        demo = DemoStore()
        try:
            mine, other = _two_projects(demo)
            con = demo.store.con
            statements = _row_statements(con, lambda: history.history_many(con, mine))
            self.assertTrue(statements, "history_many sent no row read")
            for sql in statements:
                plan = [r[3] for r in con.execute("EXPLAIN QUERY PLAN " + sql)]
                scans = [p for p in plan if TABLE_SCAN.match(p)]
                self.assertEqual(scans, [], "full scan in the plan: %s" % plan)
        finally:
            demo.close()

    def test_the_batch_equals_history_with_other_projects_and_a_cross_project_link(self):
        from clark import history
        demo = DemoStore()
        try:
            mine, other = _two_projects(demo)
            with demo.store.step("dashboard", USER) as st:
                st.create("links", {"from_item": other[0], "to_item": mine[0], "source": "demo"})   # ABC item at the END of the key
                st.create("links", {"from_item": mine[1], "to_item": other[1], "source": "demo"})   # ABC item at the front
            later = demo.update("actions", mine[2], {"status": "Delayed"})
            demo.store.undo(later, USER)
            con = demo.store.con
            ids = mine + other + ["ABC-A-999"]
            many = history.history_many(con, ids)
            for i in ids:
                with self.subTest(item=i):
                    self.assertEqual(many[i], history.history(con, i))
            self.assertTrue(any(e["table"] == "links" for e in many[mine[0]]))
            self.assertTrue(any(e["table"] == "links" for e in many[other[1]]))
            only_mine = history.history_many(con, mine)
            for i in mine:
                self.assertEqual(only_mine[i], many[i])
        finally:
            demo.close()


if __name__ == "__main__":
    unittest.main()

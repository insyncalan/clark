"""Hostile tests, row 1417. Fictional data only."""
import unittest

from _paths import SRC  # noqa: F401

from _demo import DemoStore
from clark import ask_data, publish
from clark import store as st

ALL = {"projects": ("code",), **{t: ("id",) for t in ("milestones", "workstreams", "actions", "raid", "decisions", "use_cases")}}


class Hostile(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.ws = self.s.con.execute("SELECT id FROM workstreams WHERE project='ABC'").fetchone()["id"]
        self.s.con.execute("UPDATE workstreams SET lead='Pat Placeholder', start='2026-10-01', latest_update='Qx7Marker' WHERE id=?", (self.ws,))
        self.s.con.commit()

    def link(self, a, b):
        self.s.con.execute("INSERT INTO links (from_item,to_item,kind,source) VALUES (?,?,'blocks','demo')", (a, b))
        self.s.con.commit()

    def asked(self):
        return "\n".join(p.text for p in ask_data.project_data(self.s, "ABC", "workstreams?").passages)

    def test_default_read_inputs_has_no_ask_data(self):
        got = publish.read_inputs(self.s, "ABC")
        self.assertNotIn("ask_links", got)
        for w in got["data"]["workstreams"]:
            for k in ("lead", "start", "end", "latest_update"):
                self.assertNotIn(k, w)

    def test_default_publish_inputs_refuses_lead_and_has_no_ask_links(self):
        with self.assertRaises(st.Invalid):
            self.s.publish_inputs("ABC", {**ALL, "workstreams": ("id", "lead")})
        self.assertNotIn("ask_links", self.s.publish_inputs("ABC", ALL))

    def test_ask_still_refuses_other_never_publish_columns(self):
        with self.assertRaises(st.Invalid):
            self.s.publish_inputs("ABC", {**ALL, "workstreams": ("id", "keywords")}, ask=True)
        with self.assertRaises(st.Invalid):
            self.s.publish_inputs("ABC", {**ALL, "milestones": ("id", "internal_note")}, ask=True)

    def test_ask_allows_lead_only_on_workstreams(self):
        with self.assertRaises(st.Invalid):
            self.s.publish_inputs("ABC", {**ALL, "actions": ("id", "lead")}, ask=True)

    def test_other_project_link_not_named(self):
        with self.s.step("dashboard", "t") as w:
            w.create("projects", {"code": "XYZ", "name": "Other", "health": "On track"})
            other = w.create("milestones", {"project": "XYZ", "name": "Elsewhere", "baseline_date": "2030-03-01", "source": "demo"})
        self.link(self.ws, other)
        self.assertNotIn(other, self.asked())

    def test_link_either_direction_and_sorted_once(self):
        self.link(self.demo.milestone, self.ws)
        self.link(self.ws, self.demo.use_case)
        line = [x for x in self.asked().split("\n") if self.ws in x][0]
        tail = line.split("links:")[1]
        self.assertEqual(tail.count(self.demo.milestone), 1)
        self.assertLess(tail.index(self.demo.milestone), tail.index(self.demo.use_case)) if self.demo.milestone < self.demo.use_case else None

    def test_archived_use_case_link_not_named(self):
        self.link(self.ws, self.demo.use_case)
        self.s.con.execute("UPDATE use_cases SET archived=1 WHERE id=?", (self.demo.use_case,))
        self.s.con.commit()
        self.assertNotIn(self.demo.use_case, self.asked())

    def test_lead_not_in_any_publish_output(self):
        body = publish.build(self.s, "ABC", now="2026-11-17", number=0)["body"]
        for m in (b"Pat Placeholder", b"Qx7Marker", b"2026-10-01"):
            self.assertNotIn(m, body)

    def test_old_file_without_columns_reads(self):
        con = self.s.con
        con.execute("ALTER TABLE workstreams DROP COLUMN latest_update")
        con.commit()
        self.assertIn(self.ws, self.asked())

    def test_ask_unknown_field_still_raises(self):
        with self.assertRaises(st.Invalid):
            self.s.publish_inputs("ABC", {**ALL, "workstreams": ("id", "nosuchcolumn")}, ask=True)

    def test_ask_links_hold_only_this_projects_workstreams(self):
        with self.s.step("dashboard", "t") as w:
            w.create("projects", {"code": "XYZ", "name": "Other", "health": "On track"})
            ow = w.create("workstreams", {"project": "XYZ", "name": "Their build", "source": "demo"})
            om = w.create("milestones", {"project": "XYZ", "name": "Elsewhere", "baseline_date": "2030-03-01", "source": "demo"})
        self.link(ow, om)
        got = self.s.publish_inputs("ABC", {**ALL, "workstreams": ("id", "lead")}, ask=True)
        self.assertEqual([l for l in got["ask_links"] if ow in (l["from_item"], l["to_item"])], [])

    def test_link_to_an_action_is_not_named(self):
        act = self.demo.action()
        self.link(self.ws, act)
        line = [x for x in self.asked().split("\n") if x.startswith(self.ws)][0]
        self.assertNotIn(act, line)
        self.assertNotIn("links:", line)

    def test_workstream_without_links_has_no_links_word(self):
        line = [x for x in self.asked().split("\n") if x.startswith(self.ws)][0]
        self.assertNotIn("links", line)


class MigrationHostile(unittest.TestCase):
    def test_missing_table_is_skipped(self):
        import sqlite3
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        st.migrate_workstream_columns(con)      # no workstreams table: no error, none made
        self.assertEqual(con.execute("SELECT count(*) FROM sqlite_master").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()

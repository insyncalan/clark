"""Row 1417: ask clark reads a workstream's lead, start, end, latest update and links (for 1.4); the published file does not change.

Run: python3 dev/run_tests.py test_ask_1417_workstreams
Ruling on the ticket (22-11 02:38): ask clark may read a workstream lead; the lead is read on the read side only; store.NEVER_PUBLISH keeps it for the publish side.
Fictional data only.
"""
import sqlite3
import unittest

from _paths import SRC  # noqa: F401

from _demo import DemoStore
import test_ask_1367 as base
from clark import ask_data, publish
from clark import store as st

NEW = ("lead", "start", "end", "latest_update", "links")


def line_of(text, ref):
    return [x for x in text.split("\n") if ref in x][0]


class Real(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.ws = self.s.con.execute("SELECT id FROM workstreams WHERE project = 'ABC'").fetchone()["id"]

    def fill(self):
        self.s.con.execute("UPDATE workstreams SET lead = 'Pat Placeholder', start = '2026-10-01', end = '2027-03-31', "
                           "latest_update = 'Supplier signed' WHERE id = ?", (self.ws,))
        self.s.con.execute("INSERT INTO links (from_item, to_item, kind, source) VALUES (?, ?, 'blocks', 'demo')",
                           (self.ws, self.demo.milestone))
        self.s.con.execute("INSERT INTO links (from_item, to_item, kind, source) VALUES (?, ?, 'blocks', 'demo')",
                           (self.ws, self.demo.use_case))
        self.s.con.commit()

    def asked(self):
        return "\n".join(p.text for p in ask_data.project_data(self.s, "ABC", "workstreams?").passages)

    def test_lead_is_read_only_if_ruled_yes_and_never_published(self):
        self.fill()
        self.assertIn("lead: Pat Placeholder", line_of(self.asked(), self.ws))
        self.assertIn("lead", st.NEVER_PUBLISH)
        self.assertNotIn("lead", publish.PUBLISH_FIELDS["workstreams"])
        for w in publish.select(publish.read_inputs(self.s, "ABC"))["data"]["workstreams"]:
            self.assertNotIn("lead", w)
        with self.assertRaises(st.Invalid):             # the publish read still refuses the lead
            self.s.publish_inputs("ABC", {**{t: ("id",) for t in ("projects", "milestones", "workstreams", "actions", "raid",
                                                                   "decisions", "use_cases")}, "workstreams": ("id", "lead")})

    def test_each_new_column_is_read_by_name(self):
        self.fill()
        line = line_of(self.asked(), self.ws)
        self.assertIn("start: 01-10-2026", line)
        self.assertIn("end: 31-03-2027", line)
        self.assertIn("latest update: Supplier signed", line)
        self.assertIn("lead: Pat Placeholder", line)
        self.assertIn(self.demo.milestone, line.split("links:")[1])
        self.assertIn(self.demo.use_case, line.split("links:")[1])
        for name in NEW:
            self.assertIn(name, ask_data.SHOWN["workstreams"])
        self.assertEqual(ask_data.SHOWN["workstreams"][:2], ("status", "created"))
        self.assertEqual(publish.ASK_WORKSTREAM_FIELDS, st.WORKSTREAM_ASK)

    def test_published_file_unchanged_by_new_columns(self):
        before = publish.build(self.s, "ABC", now="2026-11-17", number=0)["body"]
        self.fill()
        after = publish.build(self.s, "ABC", now="2026-11-17", number=0)["body"]
        self.assertEqual(before, after)
        for marker in (b"Pat Placeholder", b"Supplier signed", b"2027-03-31", b"31-03-2027"):
            self.assertNotIn(marker, after)

    def test_a_link_to_a_row_the_report_excludes_is_not_read(self):
        self.fill()
        self.s.con.execute("UPDATE milestones SET archived = 1 WHERE id = ?", (self.demo.milestone,))
        self.s.con.commit()
        self.assertNotIn(self.demo.milestone, line_of(self.asked(), self.ws).split("links:")[1])


class Migration(unittest.TestCase):
    def test_workstreams_migration_adds_columns(self):
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("CREATE TABLE workstreams (id TEXT PRIMARY KEY, name TEXT)")
        con.execute("INSERT INTO workstreams (id, name) VALUES ('OLD-W-001', 'Old')")
        st.migrate_workstream_columns(con)
        st.migrate_workstream_columns(con)      # a second run skips what is there
        self.assertTrue({"start", "end", "latest_update"} <= set(st.columns(con, "workstreams")))
        self.assertEqual(tuple(con.execute('SELECT start, "end", latest_update FROM workstreams').fetchone()), (None, None, None))
        self.assertEqual(st.SCHEMA_VERSION, 35)
        self.assertEqual(st.WORKSTREAM_COLUMNS_STEP, 35)
        self.assertIn((35, st.migrate_workstream_columns), st.MIGRATIONS)
        for name in ("start", "end"):
            self.assertIn(name, st.DATE_FIELDS)


class Before(unittest.TestCase):
    def test_workstream_line_has_only_the_four_fields_before_the_columns(self):
        def bare(given):      # a file before step 35: no new column, and no lead a person has typed
            given["data"]["workstreams"] = [{k: v for k, v in w.items() if k not in ("lead", "start", "end", "latest_update")}
                                            for w in given["data"]["workstreams"]]
        got, _ = base.read("workstreams?", edit=bare)
        line = line_of(base.text_of(got), "PUB-W-001")
        self.assertEqual([p.split(":")[0] for p in line.split(" | ")[1:]], ["status", "created"])
        self.assertTrue(line.startswith("PUB-W-001 Delivery | status: Active | created: "))
        for name in ("lead", "start", "end", "latest update", "links"):
            self.assertNotIn(name + ":", line)


if __name__ == "__main__":
    unittest.main()

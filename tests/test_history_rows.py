"""#123: the display rows the peek's Activity tab and the Excel History sheet share (history.rows_for_project)."""
import re
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import history
from clark.store import REMOVED

NO_ZONE = "Time zone not recorded (shown as UTC)"


def stamp(demo, step, at, offset=None):
    """Put a known time (and, when the column exists, offset) on a step's rows, so a test can say what it expects."""
    con = demo.store.con
    con.execute("UPDATE change_log SET at = ? WHERE apply_id = ?", (at, step))
    con.execute("UPDATE item_events SET at = ? WHERE apply_id = ?", (at, step))
    con.execute("UPDATE applies SET utc_offset = ? WHERE apply_id = ?", (offset, step))      # None: the zone was not recorded
    con.commit()


class Rows(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.con = self.demo.store.con

    def rows(self, kind="all", **kw):
        return history.rows_for_project(self.con, "ABC", kind, **kw)

    def of(self, kind, **kw):
        return [r for r in self.rows(**kw) if r["kind"] == kind]

    def step(self, place, route="dashboard", src_ref=None, **changes):
        a = changes.pop("action", None) or self.action
        with self.demo.store.step(route, USER, place=place, src_ref=src_ref) as st:
            st.update("actions", a, changes)
        return self.demo.last_step()

    def make_action(self):
        self.action = self.demo.action()

    # -- how and where
    def test_each_phrase_pinned(self):
        self.assertEqual(
            [history.how_text("dashboard", p, None) for p in ("peek", "cell", "bulk", "menu", "board", "report", "eye", "draft", "email", "text")],
            ["In the peek", "In the table", "In the table", "In the table", "On the board", "In the report", "With the eye",
             "From a draft email", "By a sent email", "From selected text"])
        self.assertEqual(history.how_text("assistant", "ask", "ask clark chat 3"), "By ask clark")
        self.assertEqual(history.how_text("excel", "excel", "Excel import: plan.xlsx"), "By Excel import (plan.xlsx)")
        self.assertEqual(history.how_text("undo", "cell", None), "Undo")
        self.assertEqual(history.how_text("undo", None, None), "Undo")

    def test_excel_file_name_is_cleaned_and_unknown_values_are_plain(self):
        self.assertEqual(history.how_text("excel", "excel", "Excel import: C:\\x\\a  b.xlsx"), "By Excel import (a b.xlsx)")
        self.assertEqual(len(history.how_text("excel", "excel", "Excel import: " + "z" * 300)), len("By Excel import ()") + 60)
        self.assertEqual(history.how_text("excel", "excel", None), "By Excel import")
        for route, place in (("dashboard", None), ("dashboard", "dashboard"), ("client", "zzz"), ("migrate", None), ("team", "peek1")):
            self.assertEqual(history.how_text(route, place, None), "Other")

    def test_phrases_from_real_rows(self):
        self.make_action()
        self.step("peek", owner="A One")
        self.step("cell", owner="B Two")
        self.step("report", owner="C Three")
        self.step("board", status="Delayed")
        with self.demo.store.step("excel", USER, place="excel", src_ref="Excel import: plan.xlsx") as st:
            st.update("actions", self.action, {"priority": "High"})
        got = {r["field"]: r["how"] for r in self.of("Changed")}
        self.assertEqual(got["Status"], "On the board")
        self.assertEqual(got["Priority"], "By Excel import (plan.xlsx)")
        self.assertEqual({r["how"] for r in self.of("Changed")},
                         {"In the peek", "In the table", "In the report", "On the board", "By Excel import (plan.xlsx)"})

    # -- kinds
    def test_created_is_one_line_with_the_title(self):
        self.make_action()
        created = self.of("Created")
        mine = [r for r in created if r["item_id"] == self.action]
        self.assertEqual(len(mine), 1)
        self.assertEqual((mine[0]["field"], mine[0]["to"], mine[0]["title"]), ("Action", "Draft the cut-over plan", "Draft the cut-over plan"))
        self.assertEqual(mine[0]["item"], f"{self.action} Draft the cut-over plan")
        self.assertEqual(mine[0]["who"], USER)

    def test_changed_undone(self):
        self.make_action()
        step = self.step("peek", owner="Sam Example")
        self.demo.store.undo(step, USER, place="cell")
        ch = [r for r in self.of("Changed") if r["field"] == "Owner"]
        self.assertEqual((len(ch), ch[0]["to"], ch[0]["how"]), (1, "Sam Example", "In the peek"))
        und = self.of("Undone")
        self.assertEqual(len(und), 1)
        self.assertEqual((und[0]["field"], und[0]["from"], und[0]["how"]), ("Owner", "Sam Example", "Undo"))
        self.assertEqual(self.rows()[0]["kind"], "Undone")

    def test_undoing_a_create_is_creation_undone_with_values_in_from(self):
        self.make_action()
        step = self.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        self.demo.store.undo(step, USER)
        gone = self.of("Creation undone")
        self.assertEqual(len(gone), 1)
        self.assertEqual((gone[0]["item_id"], gone[0]["how"], gone[0]["to"]), (self.action, "Undo", ""))
        self.assertIn("Description: Draft the cut-over plan", gone[0]["from"])
        self.assertNotIn("{", gone[0]["from"])
        self.assertEqual(gone[0]["title"], "Draft the cut-over plan")      # the item has gone; its last title still shows
        self.assertNotIn("Removed", {r["kind"] for r in self.rows()})

    def test_removed_link_and_label(self):
        self.make_action()
        with self.demo.store.step("dashboard", USER, place="cell") as st:
            st.create("links", {"from_item": self.action, "to_item": self.demo.milestone, "source": "demo"})
        link = [r for r in self.rows() if r["table"] == "links"]
        self.assertEqual([r["kind"] for r in link], ["Created"])
        self.assertEqual([i["id"] for i in link[0]["items"]], [self.action, self.demo.milestone])
        self.assertEqual(link[0]["items"][1]["title"], "Pilot live")
        self.assertEqual(link[0]["to"], f"{self.action} blocks {self.demo.milestone}")
        with self.demo.store.step("dashboard", USER, place="cell") as st:
            st.cancel("links", f"{self.action}|{self.demo.milestone}|blocks")
        rem = self.of("Removed")
        self.assertEqual(len(rem), 1)
        self.assertEqual(rem[0]["field"], "Link")
        self.assertIn(self.demo.milestone, rem[0]["from"])
        self.assertEqual([i["id"] for i in rem[0]["items"]], [self.action, self.demo.milestone])
        self.assertNotIn(REMOVED, str(rem[0].values()))
        # the link shows on the project through either end, and a label on its item
        with self.demo.store.step("dashboard", USER, place="cell") as st:
            st.update("actions", self.action, {"labels": "Sensitive"})
        lab = [r for r in self.rows() if r["table"] == "item_labels"]
        self.assertEqual((len(lab), lab[0]["kind"], lab[0]["to"]), (1, "Created", "Sensitive"))

    def test_archived_and_restored(self):
        self.make_action()
        rows = [{"tbl": "actions", "item_id": self.action, "old": "0", "new": "1"},
                {"tbl": "actions", "item_id": self.action, "old": "1", "new": "0"}]
        step = self.demo.last_step()
        for r in rows:         # the archive writer is #126's; read what it will write
            cur = self.con.execute("INSERT INTO change_log (apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                                   "VALUES (?,?,?,?,?,?,?,?)", (step, r["tbl"], r["item_id"], "archived", r["old"], r["new"], "update", "x"))
            self.con.execute("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, place, actor) "
                             "VALUES (datetime('now'), ?, ?, ?, 'change', 'dashboard', 'menu', 'you')", (step, r["item_id"], cur.lastrowid))
        self.assertEqual([r["field"] for r in self.of("Archived") + self.of("Restored")], ["Archived", "Archived"])
        self.assertEqual((len(self.of("Archived")), len(self.of("Restored"))), (1, 1))
        self.assertNotIn("Deleted", {r["kind"] for r in self.rows()})
        self.assertTrue(set(r["kind"] for r in self.rows()) <= set(history.KINDS))

    def test_seeded_default_sections_are_left_out(self):
        self.make_action()
        n = self.con.execute("SELECT count(*) FROM change_log WHERE via = 'seed'").fetchone()[0]
        self.assertGreater(n, 0)
        self.assertFalse([r for r in self.rows() if r["table"] == "report_sections"])
        self.assertTrue(self.of("Created"))

    # -- when
    def test_null_offset_words_and_offset_as_made(self):
        self.make_action()
        step = self.step("peek", owner="Sam Example")
        stamp(self.demo, step, "2026-10-28 22:30:00.000")           # UTC, offset unknown
        r = [x for x in self.rows() if x["field"] == "Owner"][0]
        self.assertEqual((r["when"], r["zone_note"]), ("28-10-2026 22:30", NO_ZONE))
        self.assertEqual(r["when_text"], "28-10-2026 22:30 - " + NO_ZONE)
        stamp(self.demo, step, "2026-10-28 22:30:00.000", "+04:00")
        r = [x for x in self.rows() if x["field"] == "Owner"][0]
        self.assertEqual((r["when"], r["zone_note"], r["when_text"]), ("29-10-2026 02:30", "", "29-10-2026 02:30"))
        stamp(self.demo, step, "2026-10-28 22:30:00.000", "-05:30")
        self.assertEqual([x for x in self.rows() if x["field"] == "Owner"][0]["when"], "28-10-2026 17:00")
        with self.assertRaises(Exception):                                  # the schema now refuses an odd offset
            stamp(self.demo, step, "2026-10-28 22:30:00.000", "garbage")

    def test_works_whether_or_not_the_offset_column_exists(self):
        self.make_action()
        self.assertEqual(self.of("Created")[0]["zone_note"], "")             # a step made now carries its offset
        with mock.patch.object(history, "_has_column", return_value=False):   # a copy without the column
            self.assertEqual(self.of("Created")[0]["zone_note"], NO_ZONE)

    # -- fields
    def test_plain_field_names(self):
        self.make_action()
        self.step("peek", due_date="2030-01-31", latest_update="Sent", client_visible=0)
        names = {r["field"] for r in self.of("Changed")}
        self.assertEqual(names, {"Due date", "Latest update", "Shown to the client"})
        for table in ("projects", "milestones", "workstreams", "actions", "raid", "decisions", "use_cases", "links", "item_labels",
                      "updates"):
            for col in (r[1] for r in self.con.execute("PRAGMA table_info(" + table + ")")):
                if col in ("updated_at", "id", "code", "project"):
                    continue
                name = history.FIELD_NAMES.get(table, {}).get(col) or history.COMMON.get(col)
                self.assertTrue(name, (table, col))
                self.assertNotIn("_", name)
        self.assertEqual(history.field_name("actions", "some_new_column"), "Some new column")

    def test_rich_text_kept_whole(self):
        self.make_action()
        html = "<p>Line one</p>\n<p>Line <b>two</b> " + "x" * 6000 + "</p>"
        self.step("peek", latest_update=html)
        self.assertEqual([r["to"] for r in self.of("Changed")], [html])

    # -- filter
    def test_filter_and_empty_state(self):
        self.make_action()
        self.assertEqual(self.rows("comments"), [])
        v = history.view_for_project(self.con, "ABC", "comments")
        self.assertEqual((v["rows"], v["empty"]), ([], "No comments or updates yet."))
        self.assertEqual(history.FILTERS, {"all": "All", "changes": "Changes", "comments": "Comments and updates"})
        with self.demo.store.step("dashboard", USER, place="report") as st:
            st.create("updates", {"week_ending": "2026-10-30", "project": "ABC", "health": "At risk", "summary": "Slipping"})
        self.con.execute("INSERT INTO comments (project, item_id, author, text) VALUES ('ABC', ?, 'Pat Client', 'Looks fine')", (self.action,))
        c = self.rows("comments")
        self.assertEqual({r["table"] for r in c}, {"updates", "comments"})
        com = [r for r in c if r["kind"] == "Comment"][0]
        self.assertEqual((com["who"], com["field"], com["to"], com["item_id"], com["zone_note"]),
                         ("Pat Client", "Comment", "Looks fine", self.action, NO_ZONE))
        upd = [r for r in c if r["table"] == "updates"]
        self.assertTrue(upd and all(r["item_id"] == "ABC" for r in upd))
        self.assertIn("Slipping", {r["to"] for r in upd})
        ch = self.rows("changes")
        self.assertFalse({r["table"] for r in ch} & {"updates", "comments"})
        self.assertEqual(len(self.rows("all")), len(c) + len(ch))
        self.assertEqual(history.view_for_project(self.con, "ABC", "changes")["empty"], "")
        with self.assertRaises(ValueError):
            self.rows("nonsense")

    def test_footnote_constant(self):
        self.assertEqual(history.FOOTNOTE, "Names come from this computer until you add your name in Settings \u203a Profile.")
        self.assertEqual(history.view_for_project(self.con, "ABC")["footnote"], history.FOOTNOTE)

    # -- order, scope, limit
    def test_newest_first_and_project_scope(self):
        self.make_action()
        s1 = self.step("peek", owner="A One")
        s2 = self.step("peek", owner="B Two")
        stamp(self.demo, s1, "2026-10-28 10:00:00.000")
        stamp(self.demo, s2, "2026-10-28 11:00:00.000")
        owners = [r["to"] for r in self.of("Changed") if r["field"] == "Owner"]
        self.assertEqual(owners, ["B Two", "A One"])
        with self.demo.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABD", "name": "Other", "health": "On track"})
            other = st.create("actions", {"project": "ABD", "description": "Elsewhere", "raised": "2026-10-01", "source": "demo"})
        self.assertNotIn(other, {r["item_id"] for r in self.rows()})
        abd = {r["item_id"] for r in history.rows_for_project(self.con, "ABD")}
        self.assertTrue({"ABD", other} <= abd)
        self.assertFalse([i for i in abd if not i.startswith("ABD")])
        one = history.rows_for_item(self.con, self.action)
        self.assertEqual({r["item_id"] for r in one}, {self.action})
        self.assertEqual(len(one), len([r for r in self.rows() if r["item_id"] == self.action]))

    def test_limit_and_closing_line(self):
        self.make_action()
        for i in range(5):
            self.step("peek", owner=f"Owner {i}")
        total = len(self.rows())
        v = history.view_for_project(self.con, "ABC", "all", limit=total - 2)
        self.assertEqual((len(v["rows"]), v["closing"]), (total - 2, "Older history is kept in clark. Showing the newest 20,000 changes."))
        self.assertEqual(v["rows"], self.rows()[:total - 2])
        self.assertEqual(history.view_for_project(self.con, "ABC", "all", limit=total)["closing"], "")
        self.assertEqual(len(self.rows(limit=3)), 3)
        self.assertEqual(history.ROW_LIMIT, 20000)
        self.assertEqual(history.view_for_project(self.con, "ABC")["closing"], "")

    def test_reading_changes_nothing(self):
        self.make_action()
        self.step("peek", owner="A One")
        self.con.commit()
        before, changes = list(self.con.iterdump()), self.con.total_changes
        for kind in history.FILTERS:
            history.rows_for_project(self.con, "ABC", kind)
            history.view_for_project(self.con, "ABC", kind, limit=1)
        history.rows_for_item(self.con, self.action)
        self.assertEqual((list(self.con.iterdump()), self.con.total_changes), (before, changes))
        self.assertFalse(self.con.in_transaction)

    def test_no_raw_codes_in_any_row(self):
        self.make_action()
        step = self.step("peek", owner="A One")
        self.demo.store.undo(step, USER)
        for r in self.rows():
            for key in ("how", "field", "kind"):
                self.assertNotIn("_", r[key])
                self.assertNotIn(REMOVED, r[key])

    # -- #123 readers' findings (undo wording, on/off fields, left-out items, odd comment times)
    def label_steps(self):
        self.make_action()
        with self.demo.store.step("dashboard", USER, place="cell") as st:
            st.update("actions", self.action, {"labels": "Sensitive"})
        with self.demo.store.step("dashboard", USER, place="cell") as st:
            st.update("actions", self.action, {"labels": ""})
        return self.demo.last_step()

    def lines(self, table):
        return [(r["kind"], r["field"], r["from"], r["to"]) for r in self.rows() if r["table"] == table]

    def test_undoing_a_label_removal_is_one_plain_line(self):
        removal = self.label_steps()
        self.demo.store.undo(removal, USER)
        undone = [r for r in self.rows() if r["table"] == "item_labels" and r["kind"] == "Undone"]
        self.assertEqual([(r["field"], r["from"], r["to"]) for r in undone], [("Label", "", "put back: Sensitive")])
        self.assertEqual(undone[0]["how"], "Undo")
        for r in self.rows():
            for key in ("from", "to"):
                self.assertFalse(re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", r[key]), r)      # no raw stamp anywhere

    def test_a_removed_label_shows_its_added_on_as_dd_mm_yyyy(self):
        self.label_steps()
        rem = self.of("Removed")[0]
        self.assertRegex(rem["from"], r"Added on: \d\d-\d\d-\d{4} \d\d:\d\d(,|$)")
        self.assertIn("Suggested: No", rem["from"])

    def test_undoing_an_undo_reads_differently(self):
        removal = self.label_steps()
        first = self.demo.store.undo(removal, USER)["step_id"]
        self.demo.store.undo(first, USER)
        top = [r for r in self.rows() if r["table"] == "item_labels"][0]
        self.assertEqual((top["kind"], top["field"]), ("Undo undone", "Label"))
        self.assertIn("Sensitive", top["from"])

    def test_undoing_an_undone_field_change_reads_undo_undone(self):
        self.make_action()
        step = self.step("peek", owner="Sam Example")
        first = self.demo.store.undo(step, USER)["step_id"]
        self.demo.store.undo(first, USER)
        top = self.rows()[0]
        self.assertEqual((top["kind"], top["field"]), ("Undo undone", "Owner"))
        self.assertIn("Undo undone", history.KINDS)

    def test_undoing_an_archive_or_restore_reads_plainly(self):
        self.make_action()
        with self.demo.store.step("dashboard", USER, place="menu") as st:
            st.archive("actions", self.action)
        archive = self.demo.last_step()
        self.assertEqual(self.rows()[0]["kind"], "Archived")
        self.demo.store.undo(archive, USER)
        top = self.rows()[0]
        self.assertEqual((top["kind"], top["field"], top["from"], top["to"]), ("Undone", "Restored", "", ""))

    def test_on_off_fields_read_yes_and_no(self):
        self.make_action()
        step = self.step("peek", client_visible=0)
        ch = [r for r in self.of("Changed") if r["field"] == "Shown to the client"]
        self.assertEqual({(r["from"], r["to"]) for r in ch}, {("Yes", "No")})
        self.demo.store.undo(step, USER)
        top = self.rows()[0]
        self.assertEqual((top["kind"], top["from"], top["to"]), ("Undone", "No", "Yes"))
        for name in ("hidden", "active", "builtin", "suggested", "state_set", "beside"):
            self.assertEqual(history.plain_value(name, "1"), "Yes")
            self.assertEqual(history.plain_value(name, "0"), "No")
        self.assertEqual(history.plain_value("priority", "1"), "1")      # a number in an ordinary field stays

    def test_hiding_an_item_shows_in_the_item_view_with_plain_words(self):
        key = f"ABC|{self.demo.milestone}"
        with self.demo.store.step("dashboard", USER, place="report") as st:
            st.create("report_hidden", {"project": "ABC", "item_id": self.demo.milestone})
        proj = [r for r in self.rows() if r["table"] == "report_hidden"]
        item = [r for r in history.rows_for_item(self.con, self.demo.milestone) if r["table"] == "report_hidden"]
        self.assertEqual(len(proj), 1)
        self.assertEqual(len(item), 1)
        self.assertEqual((item[0]["field"], item[0]["to"]), ("Published page", "Left out of the published page"))
        with self.demo.store.step("dashboard", USER, place="report") as st:
            st.cancel("report_hidden", key)
        back = history.rows_for_item(self.con, self.demo.milestone)[0]
        self.assertEqual((back["kind"], back["field"], back["to"]), ("Changed", "Published page", "Put back on the published page"))
        self.assertEqual(back["from"], "")
        self.demo.store.undo(self.demo.last_step(), USER)
        top = history.rows_for_item(self.con, self.demo.milestone)[0]
        self.assertEqual((top["kind"], top["to"]), ("Undone", "Left out of the published page"))

    def test_one_bad_comment_time_does_not_break_the_view(self):
        self.make_action()
        self.con.execute("INSERT INTO comments (project, item_id, author, at, text) VALUES ('ABC', ?, 'Pat Client', '29/10/2026', 'Odd')",
                         (self.action,))
        rows = self.rows()
        com = [r for r in rows if r["kind"] == "Comment"]
        self.assertEqual((len(com), com[0]["when"]), (1, "29/10/2026"))
        self.assertTrue(history.rows_for_item(self.con, self.action))
        self.assertTrue(history.activity_for_project(self.con, "ABC")["rows"])

    def test_no_raw_codes_in_from_and_to_of_any_row(self):
        removal = self.label_steps()
        first = self.demo.store.undo(removal, USER)["step_id"]
        self.demo.store.undo(first, USER)
        self.step("peek", client_visible=1)
        with self.demo.store.step("dashboard", USER, place="report") as st:
            st.create("report_hidden", {"project": "ABC", "item_id": self.demo.milestone})
        for r in self.rows():
            for key in ("from", "to"):
                self.assertNotIn(REMOVED, r[key])
                self.assertNotRegex(r[key], r"(^|: )[01]( |,|$)", r)
                self.assertNotRegex(r[key], r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", r)


if __name__ == "__main__":
    unittest.main()

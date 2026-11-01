"""#50 item 5: the "I sent it" record (Store.log_email_sent, Store.email_sent_for, schema version 7, after the settings step 6). Design:
docs/handoff/design-50-sent.md. Fictional data only. Run: python3 dev/run_tests.py test_store_email_sent

What is asserted: a version-2, a version-5 and a version-6 file move up through 7 keeping every row and match a new database; one press is one row and its item rows in
one transaction, and each refusal (the project, the mode, no or too many ids, an id that is not this project's work item, a bad or
far-future day, nobody named, a step open) writes nothing; the tables cannot be updated or deleted; the newest come first; the
chase counts for the tone come from the record; the email's own words are in no column.
"""
import hashlib
import re
import sqlite3
import unittest
from datetime import date, timedelta
from pathlib import Path

import _paths  # noqa: F401
from _demo import DemoStore, USER
from clark import draft_email as de
from clark import history
from clark import store as store_module
from clark.store import Invalid, open_store

TODAY = date(2026, 10, 28)


def fingerprint(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        counts = {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()}
    finally:
        con.close()
    return hashlib.sha256(Path(path).read_bytes()).hexdigest(), counts


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.a = self.demo.action(description="Share the plan")
        self.b = self.demo.action(description="Book the room")
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            self.other = st.create("actions", {"project": "XYZ", "description": "Elsewhere", "raised": "2026-10-01", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Which phase", "status": "Pending", "needed_by": "2030-01-05", "source": "demo"})
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                        "likelihood": "Medium", "raised": "2026-10-01", "source": "demo"})

    def send(self, ids=None, mode="chase", day="2026-10-28", who="Sam Lee", code="ABC"):
        return self.store.log_email_sent(code, [self.a, self.b] if ids is None else ids, mode, day, who, today=TODAY)

    def refuses(self, words, **kw):
        before = fingerprint(self.store.path)
        with self.assertRaises(Invalid) as caught:
            self.send(**kw)
        self.assertIn(words, str(caught.exception))
        self.assertFalse(str(caught.exception).lower().startswith("clark"))
        self.assertEqual(fingerprint(self.store.path), before, "nothing was written")


class Writing(Base):
    def test_one_press_is_one_row_with_its_items_in_the_order_given_once_each(self):
        seq = self.send(ids=[self.b, self.a, self.b, "  " + self.d])
        (row,) = self.store.email_sent_for("ABC")
        self.assertEqual((row["seq"], row["day"], row["mode"], row["by_user"], row["ids"]), (seq, "2026-10-28", "chase", "Sam Lee", sorted({self.a, self.b, self.d})))
        self.assertRegex(row["at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$")

    def test_a_risk_a_decision_and_an_action_are_all_work_items(self):
        self.send(ids=[self.a, self.r, self.d], mode="update_request")
        self.assertEqual(len(self.store.email_sent_for("ABC")[0]["ids"]), 3)

    def test_two_presses_are_two_rows_newest_first(self):
        first = self.send(mode="chase")
        second = self.send(mode="decision", ids=[self.d])
        got = self.store.email_sent_for("ABC")
        self.assertEqual([r["seq"] for r in got], [second, first])
        self.assertEqual(self.store.email_sent_for("ABC", limit=1)[0]["seq"], second)
        self.assertEqual(self.store.email_sent_for("XYZ"), [])

    def test_no_step_and_no_change_log_and_no_undo(self):
        steps = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        log = self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        self.send()
        self.assertEqual((self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0],
                          self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0]), (steps, log))

    def test_the_day_may_be_one_day_ahead_and_not_more(self):
        self.send(day=str(TODAY + timedelta(days=1)))
        self.refuses("is ahead of today", day=str(TODAY + timedelta(days=2)))

    def test_a_chase_stepped_three_times_makes_the_tone_firmer(self):
        for n in range(3):
            self.send(day=f"2026-10-2{n + 7}")
        self.send(mode="update_request")
        counts = de.chase_counts([dict(kind=de.SENT_KIND, ids=r["ids"], date=r["day"], mode=r["mode"]) for r in self.store.email_sent_for("ABC")])
        self.assertEqual(counts[self.a]["n"], 3, "an update request does not count")
        self.assertEqual(de.tone_for([self.a], counts), 2)
        self.assertEqual(counts[self.a]["last"], "2026-10-29")


class InTheHistory(Base):
    def rows(self, kind="all", item=None):
        con = sqlite3.connect(f"file:{self.store.path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return (history.rows_for_item(con, item, kind) if item else history.rows_for_project(con, "ABC", kind))
        finally:
            con.close()

    def test_a_sent_record_is_a_row_in_all_and_in_neither_changes_nor_comments(self):
        self.send(ids=[self.a, self.d], mode="chase", day="2026-10-27")
        mine = [r for r in self.rows() if r["kind"] == "Email sent"]
        (row,) = mine
        self.assertEqual((row["who"], row["how"], row["field"], row["table"]), ("Sam Lee", "in the Draft email", "Email sent", "email_sent"))
        self.assertEqual(row["to"], f"Emailed 27-10-2026 (chasing) about {self.a}, {self.d}")
        self.assertEqual([i["id"] for i in row["items"]], sorted([self.a, self.d]))
        self.assertFalse([r for r in self.rows("changes") if r["kind"] == "Email sent"])
        self.assertFalse([r for r in self.rows("comments") if r["kind"] == "Email sent"])

    def test_it_shows_on_each_item_it_asked_about_and_not_on_another(self):
        self.send(ids=[self.a], mode="update_request")
        self.assertEqual(len([r for r in self.rows(item=self.a) if r["kind"] == "Email sent"]), 1)
        self.assertEqual([r for r in self.rows(item=self.b) if r["kind"] == "Email sent"], [])

    def test_a_restart_keeps_it(self):
        self.send()
        path = self.store.path
        self.store.close()
        again = open_store(path, onedrive_roots=[])
        self.addCleanup(again.close)
        self.assertEqual(len(again.email_sent_for("ABC")), 1)
        self.store = again
        self.assertEqual(len([r for r in self.rows() if r["kind"] == "Email sent"]), 1)


class Refusals(Base):
    def test_each_refusal_writes_nothing_and_says_what_to_do(self):
        self.refuses("who pressed it", who="  ")
        self.refuses("who pressed it", who=None)
        self.refuses("isn't one clark records", mode="reminder")
        self.refuses("Tick at least one item", ids=[])
        self.refuses("Tick at least one item", ids=["  ", ""])
        self.refuses("Tick at least one item", ids="ABC-A-001")
        self.refuses("Tick at least one item", ids=[1, 2])
        self.refuses("At most 50 items", ids=[f"ABC-A-{n:03d}" for n in range(1, 52)])
        self.refuses("not in this project", ids=[self.a, self.other])
        self.refuses("not in this project", ids=["ABC-A-999"])
        self.refuses("not in this project", ids=["ABC-M-001"])
        self.refuses("is not a real date", day="2026-02-30")
        self.refuses("is not a real date", day="20261028")
        self.refuses("is not a real date", day="28-10-2026")
        self.refuses("There is no project", code="QQQ")

    def test_an_archived_project_is_refused(self):
        with self.store.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        self.refuses("archived")

    def test_a_step_that_is_open_is_not_broken_into(self):
        with self.store.step("dashboard", USER):
            with self.assertRaises(Invalid) as caught:
                self.send()
            self.assertIn("middle of a step", str(caught.exception))

    def test_the_email_words_are_in_no_column(self):
        con = sqlite3.connect(self.store.path)
        try:
            names = {r[1] for t in ("email_sent", "email_sent_items") for r in con.execute(f"PRAGMA table_info({t})")}
        finally:
            con.close()
        self.assertEqual(names, {"seq", "project", "at", "day", "mode", "by_user", "item_id"})


class Append(Base):
    def test_neither_table_can_be_updated_or_deleted(self):
        self.send()
        con = sqlite3.connect(self.store.path)
        try:
            for sql in ("UPDATE email_sent SET mode = 'chase' WHERE seq = 1", "DELETE FROM email_sent WHERE seq = 1",
                        "UPDATE email_sent_items SET item_id = 'X' WHERE seq = 1", "DELETE FROM email_sent_items WHERE seq = 1"):
                with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                    con.execute(sql)
            self.assertEqual(con.execute("SELECT count(*) FROM email_sent").fetchone()[0], 1)
        finally:
            con.close()

    def test_neither_table_can_be_replaced_either(self):
        """SQLite's REPLACE removes the old row without running a delete trigger: both spellings must be refused, and the record
        must be exactly as it was."""
        self.send()
        con = sqlite3.connect(self.store.path)
        try:
            before = [con.execute(f"SELECT * FROM {t} ORDER BY 1, 2" if t == "email_sent_items" else f"SELECT * FROM {t}").fetchall()
                      for t in ("email_sent", "email_sent_items")]
            seq, item = before[1][0][0], before[1][0][1]
            for sql in (f"INSERT OR REPLACE INTO email_sent (seq, project, day, mode, by_user) VALUES ({seq}, 'ABC', '2026-01-01', 'chase', 'x')",
                        f"REPLACE INTO email_sent (seq, project, day, mode, by_user) VALUES ({seq}, 'ABC', '2026-01-01', 'chase', 'x')",
                        f"INSERT OR REPLACE INTO email_sent_items (seq, item_id) VALUES ({seq}, '{item}')",
                        f"REPLACE INTO email_sent_items (seq, item_id) VALUES ({seq}, '{item}')"):
                with self.assertRaises(sqlite3.IntegrityError, msg=sql):
                    con.execute(sql)
            after = [con.execute(f"SELECT * FROM {t} ORDER BY 1, 2" if t == "email_sent_items" else f"SELECT * FROM {t}").fetchall()
                     for t in ("email_sent", "email_sent_items")]
            self.assertEqual(after, before)
        finally:
            con.close()

    def test_a_fresh_insert_still_works_and_the_migrated_file_refuses_replace_too(self):
        self.send()
        self.send()
        con = sqlite3.connect(self.store.path)
        try:
            self.assertEqual(con.execute("SELECT count(*) FROM email_sent").fetchone()[0], 2)
            names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'trigger'")}
            self.assertTrue({"email_sent_no_replace", "email_sent_items_no_replace"} <= names)
        finally:
            con.close()


class Migration(unittest.TestCase):
    def test_a_version_2_file_moves_up_keeping_every_row_and_matches_a_new_database(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.action(description="Share the plan")
        path = demo.store.path
        demo.store.close()
        con = sqlite3.connect(path, isolation_level=None)
        for t in ("email_sent_items", "email_sent"):
            con.execute(f"DROP TABLE {t}")
        con.execute("UPDATE meta SET v = '2' WHERE k = 'schema_version'")
        before = {t: con.execute(f'SELECT * FROM "{t}" ORDER BY 1').fetchall() for (t,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall() if t != "meta"}
        con.close()
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        for t, rows in before.items():
            self.assertEqual([tuple(r) for r in s.con.execute(f'SELECT * FROM "{t}" ORDER BY 1')], rows, t)
        self.assertEqual(s.con.execute("SELECT count(*) FROM email_sent").fetchone()[0], 0)
        fresh = DemoStore()
        self.addCleanup(fresh.close)

        def shape(p):
            c = sqlite3.connect(p)
            try:
                return sorted((n, re.sub(r"\s+|\"", "", re.sub(r"--[^\n]*", "", sql))) for n, sql in c.execute(
                    "SELECT name, sql FROM sqlite_master WHERE name LIKE 'email_sent%' AND sql IS NOT NULL"))
            finally:
                c.close()
        self.assertEqual(shape(path), shape(fresh.store.path))
        self.assertTrue(shape(path))

    def at_version(self, level):
        """A demo file put back to `level` (5 or 6): the tables of the later steps dropped, the version written down. Version 5 has
        no app_settings (step 6) and no sent record (step 7); version 6 has app_settings and no sent record."""
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.action(description="Share the plan")
        path = demo.store.path
        demo.store.close()
        con = sqlite3.connect(path, isolation_level=None)
        for t in ("email_sent_items", "email_sent") + (("app_settings",) if level < 6 else ()):
            con.execute(f"DROP TABLE {t}")
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(level),))
        return path, con

    def rows(self, con):
        return {t: [tuple(r) for r in con.execute(f'SELECT * FROM "{t}" ORDER BY 1')] for (t,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall() if t != "meta"}

    def test_a_version_5_file_moves_through_7_by_way_of_the_settings_step_and_keeps_every_row(self):
        path, con = self.at_version(5)
        before = self.rows(con)
        con.close()
        self.assertNotIn("app_settings", before)
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        after = self.rows(s.con)
        self.assertEqual({t: after[t] for t in before}, before)
        self.assertEqual(sorted(set(after) - set(before)), ["app_settings", "email_sent", "email_sent_items"])
        self.assertEqual(s.con.execute("SELECT ask_enabled FROM app_settings").fetchone()[0], 1)
        self.assertEqual(s.con.execute("SELECT count(*) FROM email_sent").fetchone()[0], 0)

    def test_a_version_6_file_with_a_word_row_a_needs_section_and_ask_off_moves_through_7_and_keeps_every_row_route_and_place(self):
        """Step 7 builds two tables and touches nothing else: item_events is not rebuilt, so the route 'word' (step 3) and every place
        stay allowed, the report_sections type CHECK of step 4 keeps 'needs' and 'tracker', and the ask switch (step 6) keeps its value."""
        path, con = self.at_version(6)
        con.execute("INSERT INTO item_events (at, item_id, kind, route, place, actor) VALUES ('x', 'ABC-A-001', 'change', 'word', 'board', 'you')")
        con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-900', 'needs', 'Needs', 900)")
        con.execute("UPDATE app_settings SET ask_enabled = 0")
        sql_of = lambda c, name: c.execute("SELECT sql FROM sqlite_master WHERE name = ?", (name,)).fetchone()[0]
        kept = ("item_events", "report_sections", "app_settings")
        sqls = [sql_of(con, n) for n in kept]
        before = self.rows(con)
        con.close()
        s = open_store(path, onedrive_roots=[])
        self.addCleanup(s.close)
        self.assertEqual(s.con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(store_module.SCHEMA_VERSION))
        self.assertEqual([sql_of(s.con, n) for n in kept], sqls)
        after = self.rows(s.con)
        self.assertEqual({t: after[t] for t in before}, before)
        self.assertEqual(sorted(set(after) - set(before)), ["email_sent", "email_sent_items"])
        self.assertEqual(s.con.execute("SELECT ask_enabled FROM app_settings").fetchone()[0], 0)
        self.assertEqual(s.con.execute("SELECT type FROM report_sections WHERE id = 'ABC-S-900'").fetchone()[0], "needs")
        self.assertEqual(s.con.execute("SELECT count(*) FROM email_sent").fetchone()[0], 0)
        for route in ("dashboard", "assistant", "excel", "undo", "client", "team", "migrate", "word"):
            s.con.execute("INSERT INTO item_events (at, item_id, kind, route, actor) VALUES ('x', 'ABC-A-001', 'change', ?, 'you')", (route,))
        for place in ("peek", "cell", "bulk", "menu", "report", "dashboard", "excel", "board"):
            s.con.execute("INSERT INTO item_events (at, item_id, kind, route, place, actor) VALUES ('x', 'ABC-A-001', 'change', 'word', ?, 'you')", (place,))
        s.con.execute("INSERT INTO report_sections (project, id, type, title, sort_order) VALUES ('ABC', 'ABC-S-901', 'tracker', 'Tracker', 901)")

    def test_the_step_is_number_7_after_the_settings_step(self):
        self.assertGreaterEqual(store_module.SCHEMA_VERSION, 7)                       # later steps follow (#96 is 8)
        self.assertEqual(store_module.MIGRATIONS[4:6], ((6, store_module.migrate_settings), (7, store_module.migrate_email_sent)))
        self.assertEqual([n for n, _ in store_module.MIGRATIONS], list(range(2, store_module.SCHEMA_VERSION + 1)))

    def test_the_frozen_statements_run_on_a_version_6_file_and_match_a_new_database(self):
        path, con = self.at_version(6)
        con.close()
        con = sqlite3.connect(path, isolation_level=None)
        try:
            con.execute("BEGIN")
            store_module.migrate_email_sent(con)
            con.execute("COMMIT")
            fresh = DemoStore()
            self.addCleanup(fresh.close)
            q = "SELECT name, sql FROM sqlite_master WHERE name LIKE 'email_sent%' AND sql IS NOT NULL ORDER BY name"
            clean = lambda rows: [(n, re.sub(r"\s+|\"", "", re.sub(r"--[^\n]*", "", sql))) for n, sql in rows]
            self.assertEqual(clean(con.execute(q)), clean(fresh.store.con.execute(q)))
            self.assertTrue(clean(con.execute(q)))
        finally:
            con.close()

    def test_the_frozen_statements_match_what_schema_sql_creates_today(self):
        mine = sqlite3.connect(":memory:")
        theirs = sqlite3.connect(":memory:")
        try:
            mine.execute("CREATE TABLE projects (code TEXT PRIMARY KEY)")
            for statement in store_module.EMAIL_SENT_DDL:
                mine.execute(statement)
            theirs.execute("CREATE TABLE projects (code TEXT PRIMARY KEY)")
            for statement in store_module._statements(store_module.SCHEMA.read_text(encoding="utf-8")):
                if "email_sent" in statement:
                    theirs.execute(statement)
            q = "SELECT name, sql FROM sqlite_master WHERE name LIKE 'email_sent%' ORDER BY name"
            clean = lambda rows: [(n, re.sub(r"\s+", "", re.sub(r"--[^\n]*", "", sql))) for n, sql in rows]
            self.assertEqual(clean(mine.execute(q)), clean(theirs.execute(q)))
        finally:
            mine.close()
            theirs.close()

class Refusals258(Base):
    """#258: hidden, closed, archived, Sensitive items and a day before 2020 are refused, each writing nothing."""
    def test_hidden_closed_archived_sensitive_and_withdrawn_items_are_refused(self):
        words = "hidden, closed or marked Sensitive"
        mk = self.demo.action
        hidden, closed, cancelled, archived, sens = (mk(description=n) for n in ("h", "c", "x", "a", "s"))
        with self.store.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": hidden})
            st.create("item_labels", {"item_id": sens, "label": "Sensitive"})
            st.update("actions", closed, {"status": "Closed", "closed": "2026-10-20"})
            st.update("actions", cancelled, {"status": "Cancelled"})
            st.archive("actions", archived)
            withdrawn = st.create("decisions", {"project": "ABC", "decision": "Old", "status": "Withdrawn", "source": "demo"})
        for bad in (hidden, closed, cancelled, archived, sens, withdrawn):
            with self.subTest(item=bad):
                self.refuses(words, ids=[self.a, bad])
        self.assertTrue(self.send(ids=[self.a, self.d, self.r]), "open items still record")

    def test_the_words_name_no_field_and_no_sent_value(self):
        sens = self.demo.action(description="s")
        with self.store.step("dashboard", USER) as st:
            st.create("item_labels", {"item_id": sens, "label": "Sensitive"})
        with self.assertRaises(Invalid) as caught:
            self.send(ids=[sens], day="2026-10-27")
        self.assertNotIn(sens, str(caught.exception))
        self.assertNotIn("2026-10-27", str(caught.exception))

    def test_the_three_day_refusals_say_what_to_do_and_that_nothing_was_saved(self):
        # The page sends its own clock's date; the person typed none, so the advice is the computer's clock and a reload.
        for day in ("2026-02-30", str(TODAY - timedelta(days=2)), str(TODAY + timedelta(days=2))):
            with self.subTest(day=day):
                with self.assertRaises(Invalid) as caught:
                    self.send(day=day)
                words = str(caught.exception)
                self.assertTrue(words.endswith("Reload the page and try again. Nothing was saved.")
                                or words.endswith("then reload the page and try again. Nothing was saved."), words)
                for banned in ("calendar", "Check the date", "reply-by", day):
                    self.assertNotIn(banned, words)

    def test_a_local_day_that_differs_from_the_servers_utc_day_is_accepted(self):
        # A page just past local midnight sends the next day while the server's day has not turned; both sides of that are in range.
        utc_day = TODAY
        for local in (utc_day + timedelta(days=1), utc_day - timedelta(days=1)):
            with self.subTest(local=str(local)):
                self.assertNotEqual(local, utc_day)
                self.assertTrue(self.send(day=str(local)))

    def test_the_day_is_bounded_by_the_servers_clock_not_the_pages(self):
        self.refuses("too far in the past", day="2019-12-31")
        self.refuses("too far in the past", day="2020-01-01")
        self.refuses("too far in the past", day=str(TODAY - timedelta(days=2)))
        self.refuses("is ahead of today", day=str(TODAY + timedelta(days=2)))
        for d in (TODAY, TODAY - timedelta(days=1), TODAY + timedelta(days=1)):
            self.assertTrue(self.send(day=str(d)))



if __name__ == "__main__":
    unittest.main()

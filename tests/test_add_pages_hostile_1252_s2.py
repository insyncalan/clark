"""Hostile tests for row 1252 slice 2 (added_pages: step 34, rules, cap, change route, Undo). Fictional data only."""
import json
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import changes, store as sm
from clark.store import open_store, Invalid
from test_store_use_case_done_migration import make_at, schema_of

STEP = sm.ADDED_PAGES_STEP
CAP = "You have 5 added pages. Remove one to add another."


def sec(i="s1", **kw):
    return {"id": i, "type": "text", "title": "T", "body": "<p>x</p>", **kw}


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def new(self, **values):
        v = {"name": "Notes", "starter": "blank"}
        v.update(values)
        return self.change({"project": "ABC", "kind": "added_pages", "op": "new", "values": v})

    def upd(self, ref, **ch):
        return self.change({"project": "ABC", "kind": "added_pages", "op": "update", "id": ref, "changes": ch})

    def rows(self):
        return self.s.read("added_pages", project="ABC")

    def logn(self):
        return self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0]


class Migration(unittest.TestCase):
    def setUp(self):
        self.f = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(shutil.rmtree, self.f, ignore_errors=True)

    def test_step_is_34_and_last_and_schema_version_matches(self):
        self.assertEqual(STEP, 34)
        self.assertEqual(sm.SCHEMA_VERSION, 34)
        self.assertEqual(sm.MIGRATIONS[-1][0], 34)
        self.assertEqual([m[0] for m in sm.MIGRATIONS], sorted({m[0] for m in sm.MIGRATIONS}))

    def test_33_file_with_gantt_switches_keeps_values_and_gets_table_and_index(self):
        path = make_at(self.f, 33)
        con = sqlite3.connect(str(path))
        con.execute("UPDATE projects SET show_gantt_editor = 1, show_gantt_client = 1, gantt_tab_name = 'Plan' WHERE code = 'ABC'")
        con.commit(); con.close()
        s = open_store(path, onedrive_roots=[])
        p = s.read("projects", ref="ABC")
        self.assertEqual((p["show_gantt_editor"], p["show_gantt_client"], p["gantt_tab_name"]), (1, 1, "Plan"))
        self.assertEqual(sm.added_page_count(s.con, "ABC"), 1)       # the switch is counted after the step
        s.close()
        sch = schema_of(path)
        self.assertIn(("index", "added_pages_project"), sch)
        self.assertIn(("table", "added_pages"), sch)

    def test_step_is_idempotent_and_keeps_rows_when_run_again(self):
        path = make_at(self.f, 34)
        con = sqlite3.connect(str(path))
        con.execute("INSERT INTO added_pages(id,project,name,starter) VALUES ('ABC-PG-001','ABC','Keep','blank')")
        con.commit()
        sm.migrate_added_pages(con)
        sm.migrate_added_pages(con)
        self.assertEqual(con.execute("SELECT name FROM added_pages").fetchall(), [("Keep",)])
        con.close()

    def test_33_file_that_already_has_a_table_is_not_broken_or_emptied(self):
        path = make_at(self.f, 33)
        con = sqlite3.connect(str(path))
        con.execute(sm.ADDED_PAGES_TABLE)
        con.execute("INSERT INTO added_pages(id,project,name,starter) VALUES ('ABC-PG-001','ABC','Keep','people')")
        con.commit(); con.close()
        s = open_store(path, onedrive_roots=[]); s.close()
        con = sqlite3.connect(str(path))
        self.assertEqual(con.execute("SELECT name, starter FROM added_pages").fetchall(), [("Keep", "people")])
        self.assertEqual(con.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()[0], "34")
        con.close()

    def test_schema_sql_and_step_statement_are_the_same_text(self):
        norm = lambda t: re.sub(r"\s+", "", re.sub(r"--[^\n]*", "", t))
        sql = (Path(sm.__file__).with_name("schema.sql")).read_text()
        m = re.search(r"CREATE TABLE IF NOT EXISTS added_pages \(.*?\n\);", sql, re.S)
        self.assertEqual(norm(m.group(0).rstrip(";")), norm(sm.ADDED_PAGES_TABLE))

    def test_table_constraints_refuse_bad_rows_even_around_the_store(self):
        path = make_at(self.f, 34)
        con = sqlite3.connect(str(path))
        ins = "INSERT INTO added_pages(id,project,name,starter,sort_order,client,hidden) VALUES (?,?,?,?,?,?,?)"
        good = ["ABC-PG-001", "ABC", "N", "blank", 0, 0, 0]
        for i, bad in enumerate([("id", "ABC-PG-1"), ("id", "abc-PG-001"), ("name", "   "), ("name", "x" * 41), ("starter", "gantt"),
                                 ("sort_order", 1.5), ("sort_order", "a"), ("client", 2), ("hidden", -1)]):
            row = list(good); row["id project name starter sort_order client hidden".split().index(bad[0])] = bad[1]
            with self.subTest(bad=bad):
                with self.assertRaises(sqlite3.IntegrityError):
                    con.execute(ins, row)
        con.rollback()
        con.execute("PRAGMA foreign_keys=ON")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute(ins, ["ZZZ-PG-001", "NOPE", "N", "blank", 0, 0, 0])
        con.close()


class Rules(Base):
    def test_name_edges(self):
        ok = [("x" * 40, "x" * 40), ("  a   b  ", "a b"), ("Plan two", "Plan two"), ("é" * 40, "é" * 40), ("日本語ページ", "日本語ページ")]
        for given, stored in ok:
            with self.subTest(given=given):
                st, b = self.new(name=given)
                self.assertEqual(st, 200, b)
                self.assertEqual(self.s.read("added_pages", ref=b["ref"])["name"], stored)
                self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": b["ref"]})
        n = self.logn()
        for bad in ("", " ", " ", "a\nb", "a\tb", "a\x00b", "​hidden", "‮evil", "x" * 41, " " + "x" * 41, 5, None, ["a"], True):
            with self.subTest(bad=bad):
                st, b = self.new(name=bad)
                self.assertEqual(st, 400, (bad, b))
        self.assertEqual(self.rows(), [])
        self.assertEqual(self.logn(), n)

    def test_sort_order_edges(self):
        for bad in (True, 1.0, "3", [1], {"a": 1}, 2 ** 63, 2 ** 70, -2 ** 64):
            with self.subTest(bad=bad):
                st, b = self.new(sort_order=bad)
                self.assertEqual(st, 400, (bad, b))
        for good in (0, -5, 2 ** 62):
            with self.subTest(good=good):
                st, b = self.new(sort_order=good)
                self.assertEqual(st, 200, b)
                self.assertEqual(self.s.read("added_pages", ref=b["ref"])["sort_order"], good)

    def test_default_place_is_after_the_last_page(self):
        a = self.new()[1]["ref"]; b = self.new()[1]["ref"]; c = self.new()[1]["ref"]
        so = [self.s.read("added_pages", ref=r)["sort_order"] for r in (a, b, c)]
        self.assertTrue(so[0] < so[1] < so[2], so)

    def test_sections_hostile(self):
        bad = ["null", "{}", "\"x\"", "[1]", "[[]]", "[null]", "{", "", json.dumps([sec(), sec()]),
               json.dumps([{**sec(), "extra": 1}]), json.dumps([{"id": "a", "type": "nope", "title": "T"}]),
               json.dumps([{"id": "", "type": "text"}]), json.dumps([{"id": 5, "type": "text"}]), json.dumps([{"type": "text"}]),
               json.dumps([sec(title="x" * 121)]), json.dumps([sec(title=5)]), json.dumps([sec(body=5)]), json.dumps([sec(body=["a"])]),
               json.dumps([sec(beside=True)]), json.dumps([sec(beside=2)]), json.dumps([sec(hidden="1")]), json.dumps([sec(hidden=1.0)]),
               json.dumps([sec(str(i)) for i in range(31)]), "[" * 5000, 5, 1.5, True,
               json.dumps([{"id": "g", "type": "gantt", "title": "G"}]), json.dumps([{"id": "g", "type": "gantttable"}]),
               json.dumps([{"id": "g", "type": "workitems"}])]
        for v in bad:
            with self.subTest(v=str(v)[:40]):
                st, b = self.new(sections=v)
                self.assertEqual(st, 400, (v, b))
        self.assertEqual(self.rows(), [])

    def test_sections_good_edges(self):
        st, b = self.new(sections=json.dumps([sec(str(i)) for i in range(30)]))
        self.assertEqual(st, 200, b)
        st, b = self.new(sections=json.dumps([sec("a", body=None, title="x" * 120, beside=1, hidden=0), {"id": "b", "type": "text"}]))
        self.assertEqual(st, 200, b)
        st, b = self.new(sections=json.dumps([sec("é", title="日本語")]))
        self.assertEqual(json.loads(self.s.read("added_pages", ref=b["ref"])["sections"])[0]["title"], "日本語")
        self.assertIn("日本語", self.s.read("added_pages", ref=b["ref"])["sections"])      # ensure_ascii False kept
        st, b = self.new(sections=[sec("l")])                                                # a list, not text
        self.assertEqual(st, 200, b)
        st, b = self.new()                                                                   # none given
        self.assertEqual(self.s.read("added_pages", ref=b["ref"])["sections"], "[]")

    def test_each_starter(self):
        for s in ("blank", "status", "documents", "people"):
            self.assertEqual(self.new(starter=s)[0], 200, s)
        for s in ("gantt", "Blank", "", None, 1, ["blank"], "blank "):
            with self.subTest(s=s):
                st, b = self.new(starter=s)
                self.assertEqual(st, 400, (s, b))

    def test_cannot_smuggle_id_project_or_unknown_fields(self):
        n = len(self.rows())
        for extra in ({"id": "ABC-PG-099"}, {"project": "XYZ"}, {"updated_at": "x"}, {"bogus": 1}):
            with self.subTest(extra=extra):
                self.assertEqual(self.new(**extra)[0], 400)
        self.assertEqual(len(self.rows()), n)
        for bad in (None, [], "x", 5):
            st, b = self.change({"project": "ABC", "kind": "added_pages", "op": "new", "values": bad})
            self.assertEqual(st, 400, bad)
        st, b = self.change({"project": "ABC", "kind": "added_pages", "op": "new"})
        self.assertEqual(st, 400)

    def test_flags_edges(self):
        for f in ("client", "hidden"):
            for bad in (2, -1, True, 1.0, "1", None and 0):
                if bad is None:
                    continue
                with self.subTest(f=f, bad=bad):
                    self.assertEqual(self.new(**{f: bad})[0], 400)
            st, b = self.new(**{f: 1})
            self.assertEqual(self.s.read("added_pages", ref=b["ref"])[f], 1)


class Cap(Base):
    def project(self, **c):
        return self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": c})

    def test_editing_a_page_at_the_cap_still_works(self):
        refs = [self.new(name=f"P{i}")[1]["ref"] for i in range(5)]
        self.assertEqual(self.upd(refs[2], name="Renamed", hidden=1, client=1)[0], 200)
        self.assertEqual(self.s.read("added_pages", ref=refs[2])["name"], "Renamed")
        self.assertEqual(self.new()[1]["message"], CAP)

    def test_gantt_switch_already_on_set_to_on_again_at_cap_is_not_refused(self):
        self.assertEqual(self.project(show_gantt_editor=1)[0], 200)
        for i in range(4):
            self.assertEqual(self.new(name=f"P{i}")[0], 200)
        self.assertEqual(sm.added_page_count(self.s.con, "ABC"), 5)
        self.assertEqual(self.project(show_gantt_editor=1)[0], 200)   # no change: must not be a 6th
        self.assertEqual(self.project(show_gantt_client=1)[0], 200)   # other fields at cap
        self.assertEqual(self.project(health="Green")[0] in (200, 400), True)

    def test_cap_is_per_project(self):
        for i in range(5):
            self.new(name=f"P{i}")
        projs = [p["code"] for p in self.s.read("projects")]
        other = [c for c in projs if c != "ABC"]
        if not other:
            self.skipTest("demo has one project")
        st, b = self.change({"project": other[0], "kind": "added_pages", "op": "new", "values": {"name": "Z", "starter": "blank"}})
        self.assertEqual(st, 200, b)

    def test_remove_frees_place_and_undo_of_remove_at_cap_does_not_double_count(self):
        refs = [self.new(name=f"P{i}")[1]["ref"] for i in range(5)]
        st, b = self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": refs[0]})
        self.assertEqual(self.new(name="Fill")[0], 200)                 # takes the freed place
        st, back = self.undo({"project": "ABC", "apply_id": b["apply_id"]})   # restoring the removed one would be a 6th
        self.assertLessEqual(len(self.rows()), 5, (st, back))

    def test_undo_of_a_gantt_switch_off_at_cap_cannot_make_a_sixth(self):
        self.project(show_gantt_editor=1)
        st, b = self.project(show_gantt_editor=0)
        for i in range(5):
            self.assertEqual(self.new(name=f"P{i}")[0], 200)
        st, back = self.undo({"project": "ABC", "apply_id": b["apply_id"]})
        total = sm.added_page_count(self.s.con, "ABC")
        self.assertLessEqual(total, 5, (st, back, "count", total))


class Route(Base):
    def test_update_edges(self):
        ref = self.new()[1]["ref"]
        n = self.logn()
        for ch in ({}, {"starter": "people"}, {"name": ""}, {"name": "x" * 41}, {"sort_order": True}, {"client": 3}, {"hidden": "0"},
                   {"sections": "nope"}, {"sections": json.dumps([{"id": "g", "type": "gantt"}])}, {"project": "XYZ"}, {"id": "ABC-PG-050"}):
            with self.subTest(ch=ch):
                self.assertEqual(self.upd(ref, **ch)[0], 400, ch)
        self.assertEqual(self.logn(), n)
        self.assertEqual(self.s.read("added_pages", ref=ref)["name"], "Notes")

    def test_ids_must_be_ours_and_well_formed(self):
        ref = self.new()[1]["ref"]
        for bad in (None, 5, "", "ABC-PG-1", "ABC-PG-0001", "abc-PG-001", "ABC-PG-001 ", "ABC-PG-999", "XYZ-PG-001", ["ABC-PG-001"], "ABC-PG-001\n"):
            for op in ("update", "delete"):
                req = {"project": "ABC", "kind": "added_pages", "op": op, "id": bad}
                if op == "update":
                    req["changes"] = {"name": "Hacked"}
                with self.subTest(bad=bad, op=op):
                    st, b = self.change(req)
                    self.assertEqual(st, 400, (bad, op, b))
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.rows()[0]["name"], "Notes")

    def test_move_and_pick_not_offered(self):
        ref = self.new()[1]["ref"]
        for op in ("move", "pick", "bogus"):
            st, b = self.change({"project": "ABC", "kind": "added_pages", "op": op, "id": ref})
            self.assertEqual(st, 400, op)

    def test_delete_twice_and_undo_twice(self):
        ref = self.new(sections=json.dumps([sec()]))[1]["ref"]
        st, b = self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": ref})
        self.assertEqual(self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": ref})[0], 400)
        self.assertEqual(self.undo({"project": "ABC", "apply_id": b["apply_id"]})[0], 200)
        self.assertEqual(len(self.rows()), 1)
        st2, b2 = self.undo({"project": "ABC", "apply_id": b["apply_id"]})
        self.assertEqual(st2 >= 400, True, b2)
        self.assertEqual(len(self.rows()), 1)

    def test_undo_of_update_restores_old_values_and_of_new_removes(self):
        ref = self.new(name="Old", sort_order=5, client=1)[1]["ref"]
        st, b = self.upd(ref, name="New", sort_order=9, client=0, hidden=1, sections=json.dumps([sec()]))
        self.assertEqual(st, 200, b)
        self.assertEqual(self.undo({"project": "ABC", "apply_id": b["apply_id"]})[0], 200)
        r = self.rows()[0]
        self.assertEqual((r["name"], r["sort_order"], r["client"], r["hidden"], r["sections"]), ("Old", 5, 1, 0, "[]"))

    def test_undo_across_projects_and_archived(self):
        ref = self.new()[1]
        other = [p["code"] for p in self.s.read("projects") if p["code"] != "ABC"]
        if other:
            st, b = self.undo({"project": other[0], "apply_id": ref["apply_id"]})
            self.assertEqual(st >= 400, True, b)
            self.assertEqual(len(self.rows()), 1)

    def test_archived_project_refused(self):
        self.s.con.execute("UPDATE projects SET active = 0, archived = 1 WHERE code = 'ABC'") if "archived" in [c[1] for c in self.s.con.execute("PRAGMA table_info(projects)")] else self.skipTest("no archive column")
        self.s.con.commit()
        st, b = self.new()
        self.assertEqual(st >= 400, True, b)

    def test_ids_counter_is_not_reused_after_remove_and_per_project_prefix(self):
        a = self.new()[1]["ref"]
        self.change({"project": "ABC", "kind": "added_pages", "op": "delete", "id": a})
        b = self.new()[1]["ref"]
        self.assertEqual((a, b), ("ABC-PG-001", "ABC-PG-002"))

    def test_data_for_lists_pages_in_menu_order_and_missing_table_is_empty(self):
        self.new(name="B", sort_order=20); self.new(name="A", sort_order=10); self.new(name="C", sort_order=20)
        self.assertEqual([p["name"] for p in self.s.data_for("ABC")["added_pages"]], ["A", "B", "C"])
        self.s.con.execute("DROP TABLE added_pages"); self.s.con.commit()
        self.assertEqual(self.s.data_for("ABC")["added_pages"], [])

    def test_project_removal_cascades_pages(self):
        self.new()
        fn = [n for n in dir(self.s) if "delete_project" in n or "remove_project" in n or "purge" in n]
        if not fn:
            self.skipTest("no project removal method found")
        getattr(self.s, fn[0])("ABC")
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM added_pages WHERE project='ABC'").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()

"""#126: archive and restore of one row. Nothing of the five kinds is deleted; `archived` is set only by Step.archive and
Step.restore (and the Undo of them)."""
import ast
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC
from clark import store as store_module
from clark.store import Invalid, connect

KINDS = ("milestones", "actions", "raid", "decisions", "use_cases", "documents")


class Archive(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        with self.s.step("dashboard", USER) as st:
            raid = st.create("raid", {"project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01",
                                      "source": "demo"})
            dec = st.create("decisions", {"project": "ABC", "decision": "Go", "date": "2026-10-01", "source": "demo"})
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) "
                           "VALUES ('ABC', 'd1', 'Plan', 'https://example.org/plan', 1)")
        self.action = self.demo.action()
        self.refs = {"milestones": self.demo.milestone, "actions": self.action, "raid": raid, "decisions": dec,
                     "use_cases": self.demo.use_case, "documents": "ABC|d1"}

    def tearDown(self):
        self.demo.close()

    def archive(self, kind, ref=None):
        with self.s.step("dashboard", USER) as st:
            st.archive(kind, ref or self.refs[kind])
        return self.demo.last_step()

    def restore(self, kind, ref=None):
        with self.s.step("dashboard", USER) as st:
            st.restore(kind, ref or self.refs[kind])
        return self.demo.last_step()

    def flag(self, kind, ref=None):
        return self.s.read(kind, ref=ref or self.refs[kind])["archived"]

    def log_of(self, step, kind):
        return [(r["field"], r["old_value"], r["new_value"]) for r in self.s.con.execute(
            "SELECT * FROM change_log WHERE apply_id = ? AND tbl = ? AND field = 'archived' ORDER BY rowid", (step, kind))]

    def test_each_kind_archives_and_restores_in_one_step_each(self):
        for kind in KINDS:
            with self.subTest(kind=kind):
                before = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
                a = self.archive(kind)
                self.assertEqual((self.flag(kind), self.log_of(a, kind)), (1, [("archived", "0", "1")]))
                r = self.restore(kind)
                self.assertEqual((self.flag(kind), self.log_of(r, kind)), (0, [("archived", "1", "0")]))
                self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], before + 2)

    def test_workstreams_have_no_single_archive(self):
        w = self.s.read("workstreams", "ABC")[0]["id"]
        with self.assertRaises(Invalid):
            self.archive("workstreams", w)

    def test_archived_is_refused_by_new_update_and_cancel(self):
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                st.create("actions", {"project": "ABC", "description": "d", "raised": "2026-10-01", "source": "demo",
                                      "archived": 1})
        self.assertIn("Use Archive or Restore", str(e.exception))
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.update("actions", self.action, {"archived": 1})
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                store_module.write_item(st.con, {"table": "actions", "op": "cancel", "id": self.action,
                                                 "changes": {"archived": 1}}, st)
        self.assertEqual(self.flag("actions"), 0)

    def test_an_archived_row_refuses_update_cancel_labels_and_a_new_link(self):
        self.archive("actions")
        for what in ("update", "cancel", "labels"):
            with self.subTest(what=what), self.assertRaises(Invalid) as e:
                with self.s.step("dashboard", USER) as st:
                    if what == "update":
                        st.update("actions", self.action, {"owner": "Sam Example"})
                    elif what == "cancel":
                        st.cancel("actions", self.action)
                    else:
                        st.update("actions", self.action, {"labels": "Sensitive"})
            self.assertIn("archived. Restore it first.", str(e.exception))
        for first, second in ((self.action, self.demo.milestone), (self.demo.milestone, self.action)):
            with self.subTest(link=first), self.assertRaises(Invalid) as e:
                with self.s.step("dashboard", USER) as st:
                    st.create("links", {"from_item": first, "to_item": second, "source": "demo"})
            self.assertIn("Restore it first", str(e.exception))
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.create("item_labels", {"item_id": self.action, "label": "Sensitive"})
        self.assertEqual(self.s.read("actions", ref=self.action)["owner"], "TBC")

    def test_archive_twice_and_restore_of_a_live_row_are_refused_in_plain_words(self):
        with self.assertRaises(Invalid) as e:
            self.restore("actions")
        self.assertIn("is not archived. Nothing was changed. Only an archived record can be restored.", str(e.exception))
        self.archive("actions")
        steps = self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        with self.assertRaises(Invalid) as e:
            self.archive("actions")
        self.assertIn("already archived. Nothing was changed.", str(e.exception))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies").fetchone()[0], steps)

    def test_undo_of_an_archive_and_of_a_restore_and_of_the_undo(self):
        a = self.archive("actions")
        out = self.s.undo(a, USER)
        self.assertEqual((self.flag("actions"), out["skipped"]), (0, []))
        out2 = self.s.undo(out["step_id"], USER)                    # undo of the undo: archived again
        self.assertEqual((self.flag("actions"), out2["skipped"]), (1, []))
        r = self.restore("actions")
        self.s.undo(r, USER)
        self.assertEqual(self.flag("actions"), 1)
        for kind in KINDS:
            with self.subTest(kind=kind):
                if kind != "actions":
                    self.s.undo(self.archive(kind), USER)
                    self.assertEqual(self.flag(kind), 0)

    def test_update_cannot_pass_revert_and_nothing_else_sets_it(self):
        with self.assertRaises(Invalid):
            with self.s.step("dashboard", USER) as st:
                st.update("actions", self.action, {"archived": 1, "revert": True})
        import inspect
        self.assertNotIn("revert", inspect.signature(store_module.Step.update).parameters)
        sets = []                                          # `revert` as a dict key is written only inside revert_group
        for path in sorted((SRC / "clark").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
                for node in ast.walk(fn):
                    if isinstance(node, ast.Dict) and any(isinstance(k, ast.Constant) and k.value == "revert" for k in node.keys):
                        sets.append((path.name, fn.name))
        self.assertEqual(sorted(set(sets)), [("store.py", "revert_group")])

    def test_a_later_change_makes_undo_skip_and_name_the_row(self):
        a = self.archive("actions")
        self.restore("actions")
        out = self.s.undo(a, USER)
        self.assertIsNone(out["step_id"])
        self.assertEqual([x["ref"] for x in out["skipped"]], [self.action])
        self.assertIn("changed since", out["skipped"][0]["why"])
        self.assertEqual(self.flag("actions"), 0)

    def test_restore_runs_the_row_rules_and_archive_checks_only_the_flag(self):
        self.s.con.execute("PRAGMA foreign_keys = OFF")
        self.s.con.execute("UPDATE decisions SET replaces = 'ABC-D-099' WHERE id = ?", (self.refs["decisions"],))   # a legacy row
        self.s.con.execute("PRAGMA foreign_keys = ON")
        self.archive("decisions")                                    # archive still works
        before = list(self.s.con.iterdump())
        with self.assertRaises(Invalid) as e:
            self.restore("decisions")
        self.assertIn("isn't here", str(e.exception))
        self.assertEqual(list(self.s.con.iterdump()), before)
        self.assertEqual(self.flag("decisions"), 1)

    def test_a_workstream_clash_with_an_archived_one_says_so(self):
        w = self.s.read("workstreams", "ABC")[0]
        self.s.con.execute("UPDATE workstreams SET archived = 1 WHERE id = ?", (w["id"],))
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                st.create("workstreams", {"project": "ABC", "name": w["name"], "source": "demo"})
        self.assertIn("which is archived. Restore it, or choose another name.", str(e.exception))

    def test_status_is_untouched(self):
        self.archive("actions")
        self.restore("actions")
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")
        with self.s.step("dashboard", USER) as st:
            st.cancel("actions", self.action)
        self.archive("actions")
        self.restore("actions")
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Cancelled")

    def test_ids_are_not_reused(self):
        self.archive("actions")
        first = self.demo.action()
        self.assertGreater(first, self.action)
        self.s.undo(self.demo.last_step(), USER)                     # the creation is undone (removed): its number stays used
        again = self.demo.action()
        self.assertGreater(again, first)

    def test_delete_row_still_refuses_the_archivable_kinds(self):
        for kind in store_module.ARCHIVE_KINDS + ("workstreams",):
            with self.subTest(kind=kind), self.assertRaises(Invalid):
                with self.s.step("dashboard", USER) as st:
                    store_module.delete_row(st.con, kind, "x", {}, st)

    def test_work_items_are_never_deleted_only_archived(self):
        for kind in KINDS:
            self.archive(kind)
            self.assertIsNotNone(self.s.read(kind, ref=self.refs[kind]), kind)


class ProjectArchive(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.a1 = self.demo.action()
        self.a2 = self.demo.action(description="Second")
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) "
                           "VALUES ('ABC', 'd1', 'Plan', 'https://example.org/plan', 1)")
        self.ws = self.s.read("workstreams", "ABC")[0]["id"]

    def tearDown(self):
        self.demo.close()

    def archive(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
            self.result = st.result
        return self.demo.last_step()

    def restore(self):
        with self.s.step("dashboard", USER) as st:
            st.restore("projects", "ABC")
            self.result = st.result
        return self.demo.last_step()

    def project(self):
        return self.s.read("projects", ref="ABC")

    def archived_children(self):
        return {t: sorted(r["id"] for r in self.s.read(t, "ABC") if r["archived"]) for t in store_module.PROJECT_CHILDREN}

    def test_children_archive_first_then_the_project_in_one_step(self):
        step = self.archive()
        rows = self.s.con.execute("SELECT tbl, item_id FROM change_log WHERE apply_id = ? AND field = 'archived' ORDER BY rowid",
                                  (step,)).fetchall()
        tables = [r["tbl"] for r in rows]
        self.assertEqual(tables[-1], "projects")
        self.assertEqual(tables.count("projects"), 1)
        order = [t for i, t in enumerate(tables) if t not in tables[:i]]
        self.assertEqual(order, [t for t in store_module.PROJECT_CHILDREN if t in tables] + ["projects"])
        p = self.project()
        self.assertEqual((p["archived"], p["active"]), (1, 0))
        self.assertTrue(all(r["archived"] for t in store_module.PROJECT_CHILDREN for r in self.s.read(t, "ABC")))
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM applies WHERE apply_id = ?", (step,)).fetchone()[0], 1)
        self.assertEqual(self.result["counts"]["actions"], 2)

    def test_undo_restores_the_project_first_then_every_child_in_one_step(self):
        step = self.archive()
        out = self.s.undo(step, USER)
        self.assertEqual(out["skipped"], [])
        self.assertEqual((self.project()["archived"], self.project()["active"]), (0, 1))
        self.assertFalse(any(self.archived_children().values()))
        rows = self.s.con.execute("SELECT tbl FROM change_log WHERE apply_id = ? AND field = 'archived' ORDER BY rowid",
                                  (out["step_id"],)).fetchall()
        self.assertEqual(rows[0]["tbl"], "projects")
        self.assertEqual(len({r["apply_id"] for r in self.s.con.execute(
            "SELECT apply_id FROM change_log WHERE via LIKE 'revert:%' AND field = 'archived'")}), 1)

    def test_restore_brings_back_only_what_that_step_archived(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", self.a1)                      # archived earlier, on its own
        self.archive()
        self.assertEqual(self.result["counts"]["actions"], 1)
        self.restore()
        self.assertEqual(self.archived_children()["actions"], [self.a1])
        self.assertEqual(self.archived_children()["documents"], [])
        self.assertEqual(self.project()["archived"], 0)

    def test_active_goes_back_to_what_it_was(self):
        self.archive()
        self.restore()
        self.assertEqual(self.project()["active"], 1)
        self.demo.update("projects", "ABC", {"active": 0})          # closed before the archive: comes back closed
        self.archive()
        self.restore()
        self.assertEqual((self.project()["active"], self.project()["archived"]), (0, 0))

    def test_an_archive_that_fails_on_a_child_leaves_everything_as_it_was(self):
        before = list(self.s.con.iterdump())
        real = store_module._update_row

        def fail_on_actions(con, table, *a, **k):
            if table == "actions":
                raise Invalid("forced")
            return real(con, table, *a, **k)
        with mock.patch.object(store_module, "_update_row", fail_on_actions):
            with self.assertRaises(Invalid):
                self.archive()
        self.assertEqual(list(self.s.con.iterdump()), before)

    def test_a_child_restore_is_refused_while_the_project_is_archived(self):
        self.archive()
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                st.restore("actions", self.a1)
        self.assertIn("archived. Restore it first.", str(e.exception))

    def test_an_archived_project_refuses_a_new_action_and_its_own_edits(self):
        self.archive()
        with self.assertRaises(Invalid) as e:
            self.demo.action()
        self.assertIn("Restore it first", str(e.exception))
        with self.assertRaises(Invalid):
            self.demo.update("projects", "ABC", {"phase": "Build"})
        with self.assertRaises(Invalid):
            self.archive()                                          # already archived

    def test_a_project_with_no_archive_step_in_its_log_restores_alone(self):
        self.s.con.execute("UPDATE actions SET archived = 1 WHERE id = ?", (self.a1,))
        self.s.con.execute("UPDATE projects SET active = 0, archived = 1 WHERE code = 'ABC'")
        self.restore()
        self.assertEqual(self.result["found_step"], False)
        self.assertEqual(self.project()["archived"], 0)
        self.assertEqual(self.archived_children()["actions"], [self.a1])

    def test_a_restore_of_a_live_project_is_refused(self):
        with self.assertRaises(Invalid) as e:
            self.restore()
        self.assertIn("is not archived", str(e.exception))

    def test_undo_of_a_project_restore_archives_the_children_first_and_the_project_last(self):
        self.archive()
        r = self.restore()
        out = self.s.undo(r, USER)
        self.assertEqual(out["skipped"], [])
        self.assertEqual(self.project()["archived"], 1)
        self.assertTrue(all(r["archived"] for t in store_module.PROJECT_CHILDREN for r in self.s.read(t, "ABC")))
        tables = [x["tbl"] for x in self.s.con.execute(
            "SELECT tbl FROM change_log WHERE apply_id = ? AND field = 'archived' ORDER BY rowid", (out["step_id"],))]
        self.assertEqual(tables[-1], "projects")

    def test_two_connections_archiving_the_same_project_end_with_one_step(self):
        other = connect(self.s.path)
        try:
            other_store = store_module.Store(other, self.s.path)
            self.archive()
            with self.assertRaises(Invalid) as e:
                with other_store.step("dashboard", USER) as st:
                    st.archive("projects", "ABC")
            self.assertIn("already archived", str(e.exception))
            n = self.s.con.execute("SELECT count(*) FROM change_log WHERE tbl = 'projects' AND field = 'archived'").fetchone()[0]
            self.assertEqual(n, 1)
        finally:
            other.close()


class NoOtherDelete(unittest.TestCase):
    def test_delete_from_appears_only_in_delete_row_and_revert_group(self):
        found = []
        for path in sorted((SRC / "clark").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
                for node in ast.walk(fn):
                    text = ""
                    if isinstance(node, ast.Constant) and isinstance(node.value, str):
                        text = node.value
                    elif isinstance(node, ast.JoinedStr):
                        text = "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
                    if "DELETE FROM" in text.upper():
                        found.append((path.name, fn.name))
        self.assertEqual(sorted(set(found)), [("store.py", "delete_row"), ("store.py", "revert_group")])



class ReviewFixes(unittest.TestCase):
    """#126 review: a document is not restored inside an archived project; an item is not put on an archived milestone or use case."""

    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.s.con.execute("INSERT INTO documents (project, id, title, url, sort_order) "
                           "VALUES ('ABC', 'd9', 'Plan', 'https://example.org/plan', 1)")

    def tearDown(self):
        self.demo.close()

    def test_a_document_is_not_restored_inside_an_archived_project(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        with self.assertRaises(Invalid) as e:
            with self.s.step("dashboard", USER) as st:
                st.restore("documents", "ABC|d9")
        self.assertEqual(str(e.exception), "Project ABC is archived. Restore it first.")
        self.assertEqual(self.s.read("documents", ref="ABC|d9")["archived"], 1)
        with self.s.step("dashboard", USER) as st:             # restoring the project brings the document back with it
            st.restore("projects", "ABC")
        self.assertEqual(self.s.read("documents", ref="ABC|d9")["archived"], 0)

    def archived(self, kind, ref):
        with self.s.step("dashboard", USER) as st:
            st.archive(kind, ref)

    def test_an_action_is_not_created_or_moved_onto_an_archived_milestone_or_use_case(self):
        self.archived("milestones", self.demo.milestone)
        self.archived("use_cases", self.demo.use_case)
        for field, ref in (("milestone", self.demo.milestone), ("use_case", self.demo.use_case)):
            with self.subTest(field=field):
                with self.assertRaises(Invalid) as e:
                    self.demo.action(**{field: ref})
                self.assertIn("is archived. Restore it first.", str(e.exception))
        with self.s.step("dashboard", USER) as st:
            st.restore("milestones", self.demo.milestone)
        a = self.demo.action()
        self.archived("milestones", self.demo.milestone)
        with self.assertRaises(Invalid):
            self.demo.update("actions", a, {"milestone": self.demo.milestone})
        self.assertIsNone(self.s.read("actions", ref=a)["milestone"])

    def test_an_item_already_on_a_milestone_that_is_archived_can_still_be_edited(self):
        a = self.demo.action(milestone=self.demo.milestone)
        self.archived("milestones", self.demo.milestone)
        self.demo.update("actions", a, {"owner": "Ana"})
        self.assertEqual(self.s.read("actions", ref=a)["owner"], "Ana")



class UndoOfOlderStep(unittest.TestCase):
    """#126 review LOW: an Undo of an older step does not edit an archived row."""

    def test_undoing_an_earlier_edit_leaves_an_archived_action_alone(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        a = demo.action(owner="Ana")
        step = demo.update("actions", a, {"owner": "Bob"})
        with demo.store.step("dashboard", USER) as st:
            st.archive("actions", a)
        result = demo.store.undo(step, USER)
        self.assertEqual(result["reversed"], [])
        self.assertEqual([x["why"] for x in result["skipped"]], [f"{a} is archived. Restore it first."])
        self.assertEqual(demo.store.read("actions", ref=a)["owner"], "Bob")



class BareKeys(unittest.TestCase):
    """#126 review LOW: a bare id for a document (its key is project|id) is "not there", never a ProgrammingError."""

    def test_a_bare_document_id_is_not_found(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.store.con.execute("INSERT INTO documents (project, id, title, url, sort_order) VALUES ('ABC', 'd1', 'Plan', 'https://example.org/p', 1)")
        for bad in ("d1", "ABC|d1|x", ""):
            for op in ("cancel", "archive", "restore"):
                with self.subTest(bad=bad, op=op):
                    with self.assertRaises(Invalid):
                        with demo.store.step("dashboard", USER) as st:
                            getattr(st, op)("documents", bad)
        self.assertEqual(demo.store.read("documents", ref="ABC|d1")["archived"], 0)

if __name__ == "__main__":
    unittest.main()

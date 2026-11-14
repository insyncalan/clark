"""#944 T1: a project's brand (projects.brand), written only through the one writer (changes.py).

Run: python3 dev/run_tests.py test_project_brand_setting
The writer: one step with Undo and a history line; an id that is not generic or installed (checked with the injected brand_ids) is refused
in the one plain sentence with nothing written. The brand is a gate and never published. The migration is in test_store_brand_migration.
Fictional data only.
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from clark import changes, history, page, publish, store as store_module
from test_brand_isolation import install

HOSTILE = ["nope", "", " ", "x" * 61, None, 5, True, ["generic"]]
IDS = lambda: {"generic", "alpha"}


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        patcher = mock.patch.object(changes, "brand_ids", IDS, create=True)      # create: red until T1 adds the seam; test_the_lists_name_it pins that it exists
        patcher.start()
        self.addCleanup(patcher.stop)

    def req(self, **fields):
        return {"project": "ABC", "kind": "projects", "op": "update", "changes": fields}

    def ok(self, request):
        status, body = self.change(request)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def brand(self):
        return self.s.read("projects", ref="ABC")["brand"]

    def counts(self):
        con = self.s.con
        return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log", "item_events")) + (
            con.execute("SELECT group_concat(brand) FROM projects").fetchone()[0],)


class Setting(Base):
    def test_a_change_is_one_step_and_one_undo_puts_generic_back(self):
        before = self.counts()
        body = self.ok(self.req(brand="alpha"))
        self.assertEqual(body["project"]["brand"], "alpha")
        self.assertEqual(self.brand(), "alpha")
        self.assertEqual(self.counts()[0], before[0] + 1, "one step")
        status, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, back)
        self.assertEqual(back["words"], "Put back: the brand.")
        self.assertEqual(back["project"]["brand"], "generic")
        self.assertEqual(self.brand(), "generic")
        self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 409, "an Undo is used once")

    def test_the_history_names_the_brand_field_on_purpose(self):
        self.assertEqual(history.FIELD_NAMES["projects"]["brand"], "Brand")

    def test_the_history_says_who_how_and_when(self):
        body = self.ok({**self.req(brand="alpha"), "place": "menu"})
        rows = [r for r in history.view_for_project(self.s.con, "ABC")["rows"] if r["table"] == "projects" and r["step"] == body["apply_id"]]
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual((row["field"], row["from"], row["to"], row["who"], row["kind"]), ("Brand", "generic", "alpha", USER, "Changed"))
        self.assertEqual(row["how"], history.HOW_TABLE)
        back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})[1]
        undone = [r for r in history.view_for_project(self.s.con, "ABC")["rows"] if r["step"] == back["apply_id"]]
        self.assertEqual([(r["field"], r["from"], r["to"], r["how"]) for r in undone], [("Brand", "alpha", "generic", history.HOW_UNDO)])

    def test_the_lists_name_it(self):
        self.assertTrue(callable(changes.brand_ids), "the seam T2 fills in")
        self.assertIn("brand", changes.CHANGE_KINDS["projects"]["update"])
        self.assertIn("brand", changes.UNDOABLE["projects"])
        self.assertTrue(set(changes.CHANGE_KINDS["projects"]["update"]) <= set(changes.UNDOABLE["projects"]))


class Hostile(Base):
    def test_unknown_empty_long_and_non_string_ids_are_refused_with_nothing_written(self):
        for value in HOSTILE:
            with self.subTest(value=repr(value)):
                before = self.counts()
                status, body = self.change(self.req(brand=value))
                self.assertEqual((status, body["ok"], body["message"]), (400, False, "That isn't a change clark can make."), value)
                self.assertEqual(self.counts(), before)
                self.assertEqual(self.brand(), "generic")

    def test_a_refused_id_does_not_reach_the_store(self):
        with mock.patch.object(store_module.Store, "step", side_effect=AssertionError("a step was opened")):
            for value in HOSTILE:
                with self.subTest(value=repr(value)):
                    status, body = self.change(self.req(brand=value))
                    self.assertEqual((status, body["message"]), (400, "That isn't a change clark can make."))


class Installed(unittest.TestCase):
    """The real brand_ids (no stand-in): generic plus what the brand library holds, read at each call."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="clark-pick-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        patcher = mock.patch.object(page, "BRANDING", self.root / "branding")
        patcher.start()
        self.addCleanup(patcher.stop)

    def send(self, value):
        return self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": {"brand": value}})

    def test_brand_ids_is_generic_alone_then_the_installed_ids(self):
        self.assertEqual(changes.brand_ids(), {"generic"})
        install(self.root, "zebra")
        install(self.root, "quokka")
        self.assertEqual(changes.brand_ids(), {"generic", "zebra", "quokka"})
        self.assertEqual(changes.brand_ids(self.root), {"generic", "zebra", "quokka"})

    def test_the_legacy_single_folder_counts_as_local_brand(self):
        (self.root / "branding").mkdir()
        (self.root / "branding" / "tokens.css").write_text(":root { --brand-navy: #123456; }", encoding="utf-8")
        self.assertIn("local-brand", changes.brand_ids())

    def test_an_installed_brand_is_accepted_and_an_unknown_or_non_string_one_is_refused(self):
        install(self.root, "zebra")
        status, body = self.send("zebra")
        self.assertEqual((status, body["project"]["brand"]), (200, "zebra"), body)
        for bad in ("quokka", 5, None, ["zebra"], True):
            with self.subTest(bad=repr(bad)):
                status, body = self.send(bad)
                self.assertEqual((status, body["message"]), (400, "That isn't a change clark can make."))
        self.assertEqual(self.s.read("projects", ref="ABC")["brand"], "zebra")

    def test_a_removed_brand_is_refused_for_a_new_choice_and_the_output_stays_generic(self):
        folder = install(self.root, "zebra")
        self.assertEqual(self.send("zebra")[0], 200)
        shutil.rmtree(folder)
        self.assertEqual(self.send("zebra")[0], 400)
        from clark import publish_flow
        self.assertEqual(publish_flow.brand_of(self.s, "ABC", self.root), page.NO_BRAND)


class Published(Base):
    def test_it_is_a_gate_and_never_published(self):
        self.ok(self.req(brand="alpha"))
        self.assertNotIn("brand", publish.PUBLISH_FIELDS["projects"])
        self.assertIn("brand", publish.GATES["projects"])
        built = self.s.publish_inputs("ABC", publish.PUBLISH_FIELDS)
        self.assertNotIn("brand", built["data"]["project"])


if __name__ == "__main__":
    unittest.main()

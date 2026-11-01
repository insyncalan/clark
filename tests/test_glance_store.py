"""#45: the writer's side of the At a glance tiles (src/clark/store.py; guarded): data_for and publish_inputs return the
glance_tiles rows, and the tiles are started by the writer (Step.seed_tiles) as history only.

Run: python3 dev/run_tests.py test_glance_store
The data is the fictional store of tests/_demo.py. The route that changes a tile is a later commit (it waits for #68).
"""
import http.client
import json
import threading
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark.store import Invalid
from clark import publish, server as sv, store as store_module


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.addCleanup(self.demo.close)

    def tile(self, tile, code="ABC", **values):
        with self.s.step("dashboard", USER) as st:
            return st.create("glance_tiles", {"project": code, "tile": tile, "sort_order": 0, **values})

    def other_project(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})


class DataForTiles(Base):
    def test_no_rows_is_an_empty_list(self):
        self.assertEqual(self.s.data_for("ABC")["glance_tiles"], [])

    def test_rows_come_back_by_place_then_tile(self):
        self.tile("risks", sort_order=2048, outline="R")
        self.tile("health", sort_order=1024, hidden=1)
        self.tile("overdue", sort_order=2048)
        got = self.s.data_for("ABC")["glance_tiles"]
        self.assertEqual([r["tile"] for r in got], ["health", "overdue", "risks"])
        self.assertEqual(got[0], {"project": "ABC", "tile": "health", "hidden": 1, "outline": "", "sort_order": 1024})
        self.assertEqual(got[2]["outline"], "R")
        self.assertEqual(set(got[0]), {"project", "tile", "hidden", "outline", "sort_order"})

    def test_another_projects_rows_never_appear(self):
        self.other_project()
        self.tile("health", code="XYZ")
        self.assertEqual(self.s.data_for("ABC")["glance_tiles"], [])
        self.assertEqual([r["project"] for r in self.s.data_for("XYZ")["glance_tiles"]], ["XYZ"])

    def test_nothing_else_in_data_for_changed(self):
        got = self.s.data_for("ABC")
        self.assertEqual(sorted(got), sorted(["project", *publish.KINDS, "workstreams", "links", "labels", "report_sections",
                                              "glance_tiles", "report_hidden", "label_rules"]))
        self.assertIsNone(self.s.data_for("NOPE"))

    def test_a_missing_project_still_answers_none(self):
        self.assertIsNone(self.s.data_for("QQQ"))

    def test_the_route_carries_the_key(self):
        self.tile("decisions", hidden=1, sort_order=4096)
        httpd = sv.LocalServer((sv.HOST, 0), data_for=self.s.data_for)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
        self.addCleanup(conn.close)
        conn.request("GET", "/api/data?project=ABC", headers={sv.TOKEN_HEADER: sv.TOKEN})
        r = conn.getresponse()
        body = r.read()
        self.assertEqual(r.status, 200)
        self.assertEqual(json.loads(body)["data"]["glance_tiles"][0]["tile"], "decisions")


class PublishInputsTiles(Base):
    def inputs(self, code="ABC"):
        return publish.read_inputs(self.s, code, "2026-10-28")

    def test_the_key_is_there_and_matches_data_for(self):
        self.assertEqual(self.inputs()["glance_tiles"], [])
        self.tile("risks", sort_order=2048, outline="G")
        self.tile("health", sort_order=1024)
        got = self.inputs()["glance_tiles"]
        self.assertEqual(got, self.s.data_for("ABC")["glance_tiles"])
        self.assertEqual([r["tile"] for r in got], ["health", "risks"])

    def test_another_projects_rows_are_not_read(self):
        self.other_project()
        self.tile("health", code="XYZ")
        self.assertEqual(self.inputs()["glance_tiles"], [])

    def test_it_is_read_in_the_one_read_transaction(self):
        self.tile("health")
        sql = []
        real = store_module.sqlite3.connect

        def spy(*args, **kw):
            con = real(*args, **kw)
            con.set_trace_callback(sql.append)
            return con
        with mock.patch.object(store_module.sqlite3, "connect", spy):
            self.inputs()
        begin = [i for i, q in enumerate(sql) if q.strip().upper() == "BEGIN"]
        commit = [i for i, q in enumerate(sql) if q.strip().upper() == "COMMIT"]
        tiles = [i for i, q in enumerate(sql) if "FROM glance_tiles" in q]
        self.assertEqual((len(begin), len(tiles)), (1, 1))
        self.assertTrue(begin[0] < tiles[0] < commit[-1], "read between BEGIN and COMMIT")

    def test_no_secret_column_is_read_and_select_ignores_the_key(self):
        self.tile("health")
        sql = []
        real = store_module.sqlite3.connect

        def spy(*args, **kw):
            con = real(*args, **kw)
            con.set_trace_callback(sql.append)
            return con
        with mock.patch.object(store_module.sqlite3, "connect", spy):
            inputs = self.inputs()
        query = [q for q in sql if "FROM glance_tiles" in q][0]
        self.assertEqual(query.split("FROM")[0].replace("SELECT", "").replace(" ", "").split(","),
                         ["project", "tile", "hidden", "outline", "sort_order"])
        without = {k: v for k, v in inputs.items() if k != "glance_tiles"}
        self.assertEqual(publish.select(inputs), publish.select(without))


class SeedTiles(Base):
    def seed(self, code="ABC", then=None):
        with self.s.step("dashboard", USER) as st:
            st.seed_tiles(code)
            if then:
                then(st)
        return self.demo.last_step()

    def test_the_four_defaults_match_the_pages_and_the_store_has_its_own_copy(self):
        from clark import glance
        self.assertEqual([t for t, _ in store_module.DEFAULT_TILES], list(glance.TILES))
        self.assertEqual({t for t, h in store_module.DEFAULT_TILES if h}, set(glance.DEFAULT_HIDDEN))
        self.assertNotIn("glance", vars(store_module), "store.py does not import the page's module")

    def test_seeding_gives_four_rows_the_same_as_tile_settings_defaults(self):
        from clark import glance
        self.seed()
        rows = self.s.data_for("ABC")["glance_tiles"]
        self.assertEqual([r["tile"] for r in rows], ["health", "overdue", "risks", "decisions"])
        self.assertEqual([r["hidden"] for r in rows], [0, 0, 0, 1])
        self.assertEqual({r["outline"] for r in rows}, {""})
        self.assertEqual([r["sort_order"] for r in rows], sorted(r["sort_order"] for r in rows))
        seeded, plain = glance.tile_settings(rows), glance.tile_settings([])
        self.assertEqual((seeded["order"], seeded["hidden"]), (plain["order"], plain["hidden"]))
        self.assertEqual({o for o in seeded["outlines"].values()}, {""}, "every outline is automatic")

    def test_a_new_project_has_no_tile_rows_and_both_readers_show_the_four_defaults(self):
        self.other_project()
        self.assertEqual(self.s.data_for("XYZ")["glance_tiles"], [], "the seed is lazy: the first tile change writes the rows")
        from clark import glance
        settings = glance.tile_settings([])
        self.assertEqual((settings["order"], settings["hidden"]), (list(glance.TILES), set(glance.DEFAULT_HIDDEN)))

    def test_a_second_seed_is_refused_and_writes_nothing(self):
        self.seed()
        before = self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0]
        with self.assertRaisesRegex(Invalid, "tiles already"):
            self.seed()
        self.assertEqual(self.s.con.execute("SELECT count(*) FROM change_log").fetchone()[0], before)

    def test_seed_rows_carry_via_seed(self):
        step = self.seed()
        vias = {r["via"] for r in self.s.con.execute("SELECT via FROM change_log WHERE apply_id = ? AND tbl = 'glance_tiles'", (step,))}
        self.assertEqual(vias, {store_module.SEED_VIA})
        self.assertEqual(self.s.step_rows(step)[0]["table"], "glance_tiles")

    def test_undo_of_seed_then_hide_puts_back_only_the_hide(self):
        step = self.seed(then=lambda st: st.update("glance_tiles", "ABC|risks", {"hidden": 1}))
        self.assertEqual(self.s.read("glance_tiles", ref="ABC|risks")["hidden"], 1)
        got = self.s.undo(step, USER)
        self.assertEqual(self.s.read("glance_tiles", ref="ABC|risks")["hidden"], 0)
        self.assertEqual(len(self.s.read("glance_tiles", "ABC")), 4, "the rows stay")
        self.assertEqual(len(got["reversed"]), 1)
        self.assertEqual(got["skipped"], [], "nothing is said about the seed")

    def test_undo_of_a_step_that_only_seeds_puts_nothing_back(self):
        step = self.seed()
        got = self.s.undo(step, USER)
        self.assertEqual((got["step_id"], got["reversed"], got["skipped"]), (None, [], []))
        self.assertEqual(len(self.s.read("glance_tiles", "ABC")), 4)

    def test_no_row_can_be_made_for_a_tile_outside_the_four_or_with_a_bad_place(self):
        for values, words in (({"tile": "milestones"}, "must be one of"), ({"tile": "overdue", "sort_order": 1.5}, "whole number"),
                              ({"tile": "overdue", "sort_order": True}, "whole number")):
            with self.subTest(values=values), self.assertRaisesRegex(Invalid, words):
                self.tile(**values)

    def test_the_seed_widens_nothing_an_undo_may_remove(self):
        self.assertNotIn("glance_tiles", store_module.REVERT_CREATED)
        self.assertEqual(store_module.DELETED_ON_CANCEL, ("links", "item_labels", "labels", "report_sections", "glance_tiles",
                                                           "report_hidden", "source_folders"))

    def test_an_unknown_project_is_refused(self):
        with self.assertRaises(Invalid):
            self.seed("NOPE")


if __name__ == "__main__":
    unittest.main()

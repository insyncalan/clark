"""#45: the At a glance tiles and the project's health through POST /api/change and /api/undo (src/clark/changes.py; guarded).

Run: python3 dev/run_tests.py test_changes_tiles
Each test makes a real store in a temporary folder (fictional data) and calls the same functions the server calls.
"""
import ast
import sqlite3
import unittest

from _demo import USER, DemoStore
from _paths import SRC
from clark import changes, glance, store as store_module


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.path = self.s.path
        self.change = changes.make_change(self.path, [], USER)
        self.undo = changes.make_undo(self.path, [], USER)

    def tile(self, op, tile=None, **more):
        req = {"project": "ABC", "kind": "glance_tiles", "op": op, **more}
        if tile is not None:
            req["id"] = tile
        return req

    def proj(self, **changes_):
        return {"project": "ABC", "kind": "projects", "op": "update", "changes": changes_}

    def ok(self, request):
        status, body = self.change(request)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def snapshot(self):
        con = sqlite3.connect(str(self.path))
        try:
            return (con.execute("SELECT count(*) FROM applies").fetchone()[0], con.execute("SELECT count(*) FROM change_log").fetchone()[0],
                    con.execute("SELECT group_concat(tile || hidden || outline || sort_order) FROM glance_tiles").fetchone()[0],
                    con.execute("SELECT group_concat(health || ifnull(health_reason, '')) FROM projects").fetchone()[0])
        finally:
            con.close()

    def refused(self, request, words, status=400):
        before = self.snapshot()
        got = self.change(request)
        self.assertEqual((got[0], got[1]["ok"], got[1]["message"]), (status, False, words), request)
        self.assertEqual(self.snapshot(), before, "nothing was written")

    def order(self):
        return [r["tile"] for r in sorted(self.s.read("glance_tiles", "ABC"), key=lambda r: r["sort_order"])]

    def back(self, apply_id, project="ABC"):
        return self.undo({"project": project, "apply_id": apply_id})

    def project(self):
        return self.s.read("projects", ref="ABC")


class Kinds(Base):
    def test_the_two_kinds_and_their_fields(self):
        self.assertEqual(changes.CHANGE_KINDS["glance_tiles"], {"update": ("hidden", "outline"), "move": ()})
        self.assertEqual(changes.CHANGE_KINDS["projects"], {"update": ("health", "health_reason", "week_ending"), "archive": (), "restore": ()})   # #126 adds archive and restore
        for kind in ("glance_tiles", "projects"):
            columns = set(store_module.columns(self.s.con, kind))
            for fields in changes.CHANGE_KINDS[kind].values():
                self.assertTrue(set(fields) <= columns, kind)
        for never in ("project", "tile", "sort_order", "code", "name", "phase", "status", "active", "archived", "current_state", "layout"):
            self.assertFalse(any(never in f for k in ("glance_tiles", "projects") for f in changes.CHANGE_KINDS[k].values()), never)

    def test_the_tile_names_agree_with_the_store_and_the_page(self):
        self.assertEqual(changes.TILES, store_module.ALLOWED[("glance_tiles", "tile")])
        self.assertEqual(changes.TILES, glance.TILES)
        self.assertEqual(changes.TILE_WORDS, glance.TILE_TITLES)
        self.assertEqual(changes.HEALTHS, store_module.ALLOWED[("projects", "health")])
        self.assertEqual(set(changes.OUTLINES) - {""}, set(store_module.ALLOWED[("glance_tiles", "outline")]))

    def test_no_delete_and_no_new_for_tiles_or_projects(self):
        for kind in ("glance_tiles", "projects"):
            for op in ("new", "delete"):
                self.refused({"project": "ABC", "kind": kind, "op": op, "id": "health"}, changes.BAD_OP)
        self.refused({"project": "ABC", "kind": "projects", "op": "move", "id": "ABC", "before": None}, changes.BAD_OP)
        self.assertEqual(self.s.read("glance_tiles", "ABC"), [])

    def test_the_source_has_no_sql_and_no_delete(self):
        tree = ast.parse((SRC / "clark" / "changes.py").read_text(encoding="utf-8"))
        for name in ("_do_tile_change", "_do_project_change"):
            fn = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name][0]
            self.assertFalse(any(isinstance(n, ast.Constant) and n.value in ("delete", "cancel") for n in ast.walk(fn)), name)
            self.assertNotIn("DELETE", ast.dump(fn), name)


class Tiles(Base):
    def test_hiding_a_tile_starts_the_four_and_is_one_step_with_one_undo(self):
        body = self.ok(self.tile("update", "risks", changes={"hidden": 1}))
        self.assertEqual(self.order(), ["health", "overdue", "risks", "decisions"])
        self.assertEqual({r["tile"]: r["hidden"] for r in body["tiles"]}, {"health": 0, "overdue": 0, "risks": 1, "decisions": 1})
        self.assertIsNotNone(body["apply_id"])
        status, back = self.back(body["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertEqual(back["words"], "Put back: the tile High risks and issues is shown again.")
        self.assertEqual(len(self.s.read("glance_tiles", "ABC")), 4, "the starting rows stay")
        self.assertEqual({r["tile"]: r["hidden"] for r in back["tiles"]}["risks"], 0)
        self.assertEqual(self.back(body["apply_id"])[0], 409, "twice is refused")

    def test_the_eye_on_decisions_shows_it(self):
        body = self.ok(self.tile("update", "decisions", changes={"hidden": 0}))
        self.assertEqual(self.s.read("glance_tiles", ref="ABC|decisions")["hidden"], 0)
        self.assertEqual(self.back(body["apply_id"])[1]["words"], "Put back: the tile Decisions needed is hidden again.")

    def test_a_second_change_to_a_started_project_is_one_step_with_no_seed(self):
        self.ok(self.tile("update", "risks", changes={"hidden": 1}))
        body = self.ok(self.tile("update", "overdue", changes={"outline": "R"}))
        self.assertEqual({(r["table"], r["key"], r["field"], r["via"]) for r in self.s.step_rows(body["apply_id"])},
                         {("glance_tiles", "ABC|overdue", "outline", "dashboard")}, "one row: no starting rows in this step")

    def test_the_outline_words_say_each_colour(self):
        for code, word in (("R", "Red"), ("A", "Amber"), ("G", "Green"), ("N", "No colour")):
            body = self.ok(self.tile("update", "overdue", changes={"outline": code}))
            self.assertEqual(self.s.read("glance_tiles", ref="ABC|overdue")["outline"], code)
            self.assertEqual(self.back(body["apply_id"])[1]["words"], "Put back: the outline of the tile Overdue actions is Automatic again.")
        self.ok(self.tile("update", "overdue", changes={"outline": "G"}))
        body2 = self.ok(self.tile("update", "overdue", changes={"outline": ""}))
        self.assertEqual(self.back(body2["apply_id"])[1]["words"], "Put back: the outline of the tile Overdue actions is Green again.")

    def test_hiding_twice_makes_no_second_step(self):
        self.ok(self.tile("update", "risks", changes={"hidden": 1}))
        before = self.snapshot()
        body = self.ok(self.tile("update", "risks", changes={"hidden": 1}))
        self.assertIsNone(body["apply_id"])
        self.assertEqual(self.snapshot(), before)

    def test_a_first_change_that_changes_nothing_has_no_undo(self):
        body = self.ok(self.tile("update", "overdue", changes={"hidden": 0}))
        self.assertIsNone(body["apply_id"], "only the starting tiles went in")
        self.assertEqual(len(self.s.read("glance_tiles", "ABC")), 4)

    def test_a_move_renumbers_in_one_step_and_one_undo(self):
        body = self.ok(self.tile("move", "decisions", before="health"))
        self.assertEqual(self.order(), ["decisions", "health", "overdue", "risks"])
        self.assertEqual([r["tile"] for r in body["tiles"]], self.order())
        status, back = self.back(body["apply_id"])
        self.assertEqual((status, back["words"]), (200, "Put back: the place of the tile Decisions needed."))
        self.assertEqual(self.order(), ["health", "overdue", "risks", "decisions"])

    def test_a_move_to_the_end_and_a_move_where_it_already_is(self):
        self.ok(self.tile("move", "health", before=None))
        self.assertEqual(self.order(), ["overdue", "risks", "decisions", "health"])
        before = self.snapshot()
        body = self.ok(self.tile("move", "health", before=None))
        self.assertIsNone(body["apply_id"])
        self.assertEqual(self.snapshot(), before)

    def test_many_moves_renumber_when_no_whole_number_fits(self):
        for _ in range(14):
            self.ok(self.tile("move", "decisions", before="overdue"))
            self.ok(self.tile("move", "decisions", before="health"))
        self.assertEqual(self.order(), ["decisions", "health", "overdue", "risks"])
        self.assertEqual(len({r["sort_order"] for r in self.s.read("glance_tiles", "ABC")}), 4)

    def test_an_undo_of_a_move_after_another_move_leaves_the_later_one_and_says_so(self):
        first = self.ok(self.tile("move", "decisions", before="health"))["apply_id"]
        self.ok(self.tile("move", "decisions", before="risks"))
        status, back = self.back(first)
        self.assertEqual(status, 200)
        self.assertIn("The tile Decisions needed was changed later", back["words"])
        self.assertEqual(self.order().index("decisions"), 2)

    def test_many_phrases_collapse_to_a_count(self):
        body = self.ok(self.tile("move", "decisions", before="health"))
        self.assertEqual(self.back(body["apply_id"])[0], 200)
        words = changes.words([{"ref": f"ABC|{t}", "field": "hidden", "change": "put back", "to": "0"} for t in changes.TILES], [], {})
        self.assertEqual(words, "Put back: 4 changes to the tiles.")

    # refusals: each plain, none writes

    def test_refusals(self):
        bad = [
            (self.tile("update", "nope", changes={"hidden": 1}), changes.NOT_A_TILE),
            (self.tile("update", "Health", changes={"hidden": 1}), changes.NOT_A_TILE),
            (self.tile("update", "ABC|health", changes={"hidden": 1}), changes.NOT_A_TILE),
            (self.tile("update", None, changes={"hidden": 1}), changes.NOT_A_TILE),
            ({**self.tile("update", None, changes={"hidden": 1}), "id": 5}, changes.NOT_A_TILE),
            ({**self.tile("update", None, changes={"hidden": 1}), "id": ["health"]}, changes.NOT_A_TILE),
            (self.tile("update", "health", changes={"hidden": True}), changes.FLAG_WORDS),
            (self.tile("update", "health", changes={"hidden": 2}), changes.FLAG_WORDS),
            (self.tile("update", "health", changes={"hidden": "1"}), changes.FLAG_WORDS),
            (self.tile("update", "health", changes={"hidden": 1.0}), changes.FLAG_WORDS),
            (self.tile("update", "health", changes={"outline": "Red"}), changes.BAD_OUTLINE),
            (self.tile("update", "health", changes={"outline": "r"}), changes.BAD_OUTLINE),
            (self.tile("update", "health", changes={"outline": None}), changes.BAD_OUTLINE),
            (self.tile("update", "health", changes={"outline": ["R"]}), changes.BAD_OUTLINE),
            (self.tile("update", "health", changes={"sort_order": 5}), "The field 'sort_order' can't be set here."),
            (self.tile("update", "health", changes={"tile": "risks"}), "The field 'tile' can't be set here."),
            (self.tile("update", "health", changes={"project": "XYZ"}), "The field 'project' can't be set here."),
            (self.tile("update", "health", changes={"hidden; DROP TABLE x": 1}), "The field 'hidden DROP TABLE x' can't be set here."),
            (self.tile("update", "health", changes={}), "Say what to change."),
            (self.tile("update", "health", changes=[1]), "Send the changes as an object."),
            (self.tile("update", "health"), "Say what to change."),
            (self.tile("update", "health", values={"hidden": 1}), "That change doesn't take 'values'."),
            (self.tile("update", "health", before="risks", changes={"hidden": 1}), "That change doesn't take 'before'."),
            (self.tile("move", "health"), "Say where to move it."),
            (self.tile("move", "health", before="nope"), changes.STALE),
            (self.tile("move", "health", before=3), changes.STALE),
            (self.tile("move", "health", before="health"), "A tile can't be moved before itself."),
            (self.tile("move", "nope", before="health"), changes.NOT_A_TILE),
            (self.tile("move", "health", before="risks", changes={"hidden": 1}), "That change doesn't take 'changes'."),
            (self.tile("move", "health", before="risks", after="x"), "That change doesn't take 'after'."),
            ({"project": "ABC", "kind": "report_hidden", "op": "update", "id": "x", "changes": {}}, changes.BAD_OP),     # #67: report_hidden is a kind now; it takes no update
            ({"project": "ABC", "kind": "glance_tiles ", "op": "update"}, changes.BAD_KIND),
        ]
        for request, words in bad:
            with self.subTest(request=request):
                self.refused(request, words)
        self.assertEqual(self.s.read("glance_tiles", "ABC"), [])

    def test_another_or_a_missing_project_and_an_archived_one(self):
        self.refused({**self.tile("update", "health", changes={"hidden": 1}), "project": "QQQ"}, changes.NO_PROJECT, 404)
        self.refused({**self.tile("update", "health", changes={"hidden": 1}), "project": "abc"}, changes.BAD_PROJECT)
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        self.ok({**self.tile("update", "risks", changes={"hidden": 1}), "project": "XYZ"})
        self.assertEqual(self.s.read("glance_tiles", "ABC"), [], "ABC untouched")
        self.assertEqual(self.s.read("glance_tiles", ref="XYZ|risks")["hidden"], 1)

    def test_the_reply_holds_no_work_item_text(self):
        self.demo.action(description="SECRET-ACTION-TEXT")
        body = self.ok(self.tile("update", "overdue", changes={"outline": "A"}))
        self.assertNotIn("SECRET-ACTION-TEXT", repr(body))
        self.assertEqual(set(body), {"ok", "apply_id", "ref", "tiles"})
        self.assertEqual(set(body["tiles"][0]), set(changes.TILE_SHOWN))


class Health(Base):
    def test_a_health_change_with_a_reason_is_one_step_and_undo_puts_both_back(self):
        week = self.project()["week_ending"]
        body = self.ok(self.proj(health="At risk", health_reason="Test environment is late"))
        self.assertEqual(body["project"], {"health": "At risk", "health_reason": "Test environment is late", "week_ending": week})
        self.assertEqual(set(body), {"ok", "apply_id", "ref", "project"})
        status, back = self.back(body["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertEqual(back["words"], "Put back: the health of the project (On track) and its reason.")
        self.assertEqual(back["project"], {"health": "On track", "health_reason": None, "week_ending": week})
        self.assertEqual((self.project()["health"], self.project()["health_reason"]), ("On track", None))
        self.assertEqual(self.back(body["apply_id"])[0], 409)

    def test_a_health_change_with_no_reason_is_refused_with_the_stores_rule_and_nothing_is_written(self):
        for given in ({"health": "Off track"}, {"health": "Off track", "health_reason": ""}, {"health": "Off track", "health_reason": "  \n "},
                      {"health": "Off track", "health_reason": None}):
            with self.subTest(given=given):
                self.refused(self.proj(**given), changes.HEALTH_NEEDS_REASON)

    def test_a_reason_alone_is_its_own_step(self):
        self.ok(self.proj(health="At risk", health_reason="First"))
        body = self.ok(self.proj(health_reason="Second line\nand a third"))
        self.assertEqual(self.project()["health_reason"], "Second line\nand a third")
        status, back = self.back(body["apply_id"])
        self.assertEqual((status, back["words"]), (200, "Put back: the reason for the project's health."))
        self.assertEqual((self.project()["health"], self.project()["health_reason"]), ("At risk", "First"))

    def test_the_same_health_and_reason_makes_no_step(self):
        self.ok(self.proj(health="At risk", health_reason="Late"))
        before = self.snapshot()
        body = self.ok(self.proj(health="At risk", health_reason="Late"))
        self.assertIsNone(body["apply_id"])
        self.assertEqual(self.snapshot(), before)

    def test_undo_of_a_pick_that_kept_the_reason_as_it_stood_puts_the_health_back(self):
        self.ok(self.proj(health="At risk", health_reason="Same reason"))
        second = self.ok(self.proj(health="Off track", health_reason="Same reason"))
        status, back = self.back(second["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertNotIn("Nothing was put back", back["words"])
        self.assertEqual((self.project()["health"], self.project()["health_reason"]), ("At risk", "Same reason"))

    def test_a_later_change_is_left_and_the_toast_says_so(self):
        first = self.ok(self.proj(health="At risk", health_reason="Late"))["apply_id"]
        self.ok(self.proj(health="Off track", health_reason="Later still"))
        status, back = self.back(first)
        self.assertEqual(status, 200)
        self.assertIn("The project's health was changed later", back["words"])
        self.assertEqual(self.project()["health"], "Off track")

    def test_an_id_and_any_other_project_field_are_refused_in_the_same_words_as_any_unknown_key(self):
        self.refused({**self.proj(health="At risk", health_reason="x"), "id": "ABC"}, "That change doesn't take 'id'.")
        self.refused({**self.proj(health="At risk", health_reason="x"), "id": None}, "That change doesn't take 'id'.")
        self.refused({**self.proj(health="At risk", health_reason="x"), "after": "x"}, "That change doesn't take 'after'.")
        for field in ("name", "phase", "status", "code", "current_state", "layout", "active", "archived", "sponsor", "client_name"):
            self.refused(self.proj(**{field: "x"}), f"The field '{field}' can't be set here.")
        self.refused(self.proj(), "Say what to change.")
        self.refused({"project": "ABC", "kind": "projects", "op": "update"}, "Say what to change.")
        self.refused({"project": "ABC", "kind": "projects", "op": "update", "changes": "At risk"}, "Send the changes as an object.")

    def test_a_real_week_ending_date_is_one_step_and_undo_puts_the_old_date_back(self):
        old = self.project()["week_ending"]
        body = self.ok(self.proj(week_ending="2026-11-06"))
        self.assertEqual(body["project"]["week_ending"], "2026-11-06")
        self.assertEqual(self.project()["week_ending"], "2026-11-06")
        status, back = self.back(body["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertEqual(back["project"]["week_ending"], old)
        self.assertEqual(self.project()["week_ending"], old)
        self.assertEqual(self.back(body["apply_id"])[0], 409)

    def test_a_week_ending_that_is_not_a_real_date_is_refused_and_the_old_date_kept(self):
        old = self.project()["week_ending"]
        for value in ("2026-13-45", "x", 5, None, "2026-02-30", "6-11-2026", ""):
            with self.subTest(value=value):
                self.refused(self.proj(week_ending=value), changes.BAD_WEEK)
                self.assertEqual(self.project()["week_ending"], old)

    def test_week_ending_and_health_change_in_one_step(self):
        old = self.project()["week_ending"]
        body = self.ok(self.proj(health="At risk", health_reason="Late", week_ending="2026-11-13"))
        self.assertEqual(body["project"], {"health": "At risk", "health_reason": "Late", "week_ending": "2026-11-13"})
        status, back = self.back(body["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertEqual((self.project()["health"], self.project()["week_ending"]), ("On track", old))

    def test_a_value_that_is_not_a_health_or_not_text(self):
        for value in ("Green", "on track", "", None, 1, ["At risk"], True):
            with self.subTest(value=value):
                self.refused(self.proj(health=value, health_reason="x"), changes.BAD_HEALTH)
        for value in (5, ["x"], {"a": 1}, True):
            with self.subTest(reason=value):
                self.refused(self.proj(health_reason=value), store_module.REASON_NOT_TEXT)

    def test_a_missing_or_archived_project(self):
        self.refused({**self.proj(health="At risk", health_reason="x"), "project": "QQQ"}, changes.NO_PROJECT, 404)
        con = sqlite3.connect(str(self.path))
        con.execute("UPDATE projects SET active = 0, archived = 1 WHERE code = 'ABC'")
        con.commit()
        con.close()
        self.refused(self.proj(health="At risk", health_reason="x"), changes.PROJECT_NOT_ACTIVE)


class ReasonOnCreate(Base):
    def make(self, code, reason):
        with self.s.step("dashboard", USER) as st:
            return st.create("projects", {"code": code, "name": "New Programme", "health": "On track", "health_reason": reason})

    def test_a_new_projects_reason_is_held_to_the_same_rules(self):
        for bad in ("x\u202e" + "y" * 3000, "y" * 2001, "a\u200bb", "a\x00b", "a\ud800b", 5):
            with self.subTest(reason=repr(bad)[:20]), self.assertRaises(store_module.Invalid):
                self.make("NEW", bad)
        self.assertIsNone(self.s.read("projects", ref="NEW"), "nothing was made")

    def test_a_good_reason_is_kept_and_a_windows_line_break_is_made_plain(self):
        self.make("NEW", "Line one\r\nLine two")
        self.assertEqual(self.s.read("projects", ref="NEW")["health_reason"], "Line one\nLine two")


class ReasonText(Base):
    """Review point: the reason's limits are the store's (`_check_project`), so every writer is held to them; the route
    calls the same function and keeps its refusal as the first line."""

    def refused_in_store(self, value, words):
        before = self.snapshot()
        with self.assertRaises(store_module.Invalid) as got:
            with self.s.step("team", USER) as st:             # a teammate's change, not /api/change
                st.update("projects", "ABC", {"health_reason": value})
        self.assertEqual(str(got.exception), words)
        self.assertEqual(self.snapshot(), before, "nothing was written")

    def test_two_thousand_characters_pass_and_one_more_does_not(self):
        self.ok(self.proj(health_reason="x" * 2000))
        self.assertEqual(len(self.project()["health_reason"]), 2000)
        self.refused(self.proj(health_reason="x" * 2001), store_module.REASON_TOO_LONG)
        self.assertEqual(len(self.project()["health_reason"]), 2000)

    def test_the_store_holds_every_writer_to_it_not_only_the_route(self):
        self.refused_in_store("x" * 2001, store_module.REASON_TOO_LONG)
        self.refused_in_store("a\x00b", store_module.REASON_BAD_CHARS)
        self.refused_in_store(5, store_module.REASON_NOT_TEXT)
        with self.s.step("team", USER) as st:
            st.update("projects", "ABC", {"health": "At risk", "health_reason": "Fine\nover two lines"})
        self.assertEqual(self.project()["health_reason"], "Fine\nover two lines")

    def test_a_windows_line_break_is_made_a_newline_and_counted_after(self):
        self.ok(self.proj(health_reason="one\r\ntwo\r\nthree"))
        self.assertEqual(self.project()["health_reason"], "one\ntwo\nthree")
        with self.s.step("team", USER) as st:
            st.update("projects", "ABC", {"health_reason": "a\r\nb"})
        self.assertEqual(self.project()["health_reason"], "a\nb", "normalised in the store too")
        self.ok(self.proj(health_reason="x" * 999 + "\r\n" + "y" * 1000))          # 2000 once the pair counts as one
        self.refused(self.proj(health_reason="x" * 1000 + "\r\n" + "y" * 1000), store_module.REASON_TOO_LONG)

    def test_other_control_and_invisible_characters_are_refused(self):
        for bad in ("a\rb", "a\x00b", "a\x1bb", "a\x7fb", "a\u200bb", "a\u202eb", "a\u2028b", "a\u2029b", "a\ufeffb",
                    "a\ue000b", "a\ud800b", "a\x85b", "a\u00adb"):
            with self.subTest(bad=repr(bad)):
                self.refused(self.proj(health_reason=bad), store_module.REASON_BAD_CHARS)
                self.refused_in_store(bad, store_module.REASON_BAD_CHARS)

    def test_a_tab_becomes_a_space_instead_of_being_refused(self):
        self.ok(self.proj(health="At risk", health_reason="Cost\tOwner\tLate"))
        self.assertEqual(self.project()["health_reason"], "Cost Owner Late")
        self.assertEqual(store_module.health_reason_text("a\tb"), "a b")

    def test_text_is_kept_as_given_and_never_trimmed_or_quoted_back(self):
        text = "  Caf\u00e9 \U0001F600 late <b>not html</b> & \u201cquoted\u201d  \n\n end "
        body = self.ok(self.proj(health_reason=text))
        self.assertEqual(self.project()["health_reason"], text)
        self.assertEqual(body["project"]["health_reason"], text)
        self.refused(self.proj(health_reason="SECRET-BAD\x00TEXT"), store_module.REASON_BAD_CHARS)
        self.assertNotIn("SECRET", store_module.REASON_BAD_CHARS)

    def test_an_empty_or_none_reason_is_allowed_alone_when_the_health_is_on_track(self):
        self.ok(self.proj(health="At risk", health_reason="Late"))
        self.ok(self.proj(health="On track", health_reason="Back on plan"))
        self.ok(self.proj(health_reason=None))
        self.assertIsNone(self.project()["health_reason"])

    def test_an_empty_reason_is_stored_as_none_not_an_empty_string(self):
        self.ok(self.proj(health="At risk", health_reason="Late"))
        self.ok(self.proj(health="On track", health_reason="Fine"))
        self.ok(self.proj(health_reason=""))
        self.assertIsNone(self.project()["health_reason"])
        self.assertEqual(store_module.health_reason_text(""), None)
        for blank in ("   ", "\n", "\t", "\r\n", " \n\t \r\n "):
            self.assertIsNone(store_module.health_reason_text(blank), repr(blank))
        self.assertEqual(store_module.health_reason_text(" a \n"), " a \n")

    def test_the_reason_cannot_be_cleared_while_the_health_is_not_on_track(self):
        self.ok(self.proj(health="At risk", health_reason="Late"))
        for blank in (None, "", "  \n "):
            with self.subTest(blank=blank):
                self.refused(self.proj(health_reason=blank), changes.HEALTH_NEEDS_REASON)
        self.assertEqual(self.project()["health_reason"], "Late")

    def test_undo_puts_back_an_old_reason_even_one_over_the_limit(self):
        con = sqlite3.connect(str(self.path))                  # an older file's long reason (before this rule)
        con.execute("UPDATE projects SET health_reason = ? WHERE code = 'ABC'", ("z" * 2500,))
        con.commit()
        con.close()
        body = self.ok(self.proj(health="At risk", health_reason="Short"))
        status, back = self.back(body["apply_id"])
        self.assertEqual(status, 200, back)
        self.assertEqual(len(self.project()["health_reason"]), 2500)


class WhatAnUndoMayReverse(Base):
    """Review point: the FIELD is checked, not only the table; one UNDOABLE table for every kind of step from here."""

    def step_by(self, table, key, changes_):
        with self.s.step("dashboard", USER) as st:
            st.update(table, key, changes_)
        return self.demo.last_step()

    def test_undoable_names_every_kind_and_the_fields(self):
        self.assertEqual(set(changes.UNDOABLE), {"report_sections", "actions", "raid", "decisions", "glance_tiles", "projects",
                                                 "milestones", "use_cases", "documents", "workstreams", "report_hidden"})   # #126 adds the archivable records
        self.assertEqual(changes.UNDOABLE["glance_tiles"], ("hidden", "outline", "sort_order"))
        self.assertEqual(changes.UNDOABLE["projects"], ("health", "health_reason", "week_ending", "archived", "active"))
        self.assertTrue(set(changes.UNDOABLE) >= set(changes.CHANGE_KINDS), "every kind the route admits can be undone")

    def test_a_dashboard_step_that_renamed_the_project_is_refused(self):
        step = self.step_by("projects", "ABC", {"name": "Renamed"})
        self.assertEqual(self.back(step), (400, {"ok": False, "message": changes.NO_UNDO, "code": "refused"}))
        self.assertEqual(self.project()["name"], "Renamed")

    def test_a_step_that_changed_health_and_the_phase_together_is_refused(self):
        step = self.step_by("projects", "ABC", {"health": "At risk", "health_reason": "x", "phase": "Build"})
        self.assertEqual(self.back(step)[0], 400)
        self.assertEqual(self.project()["health"], "At risk")

    def test_a_dashboard_step_that_changed_a_tiles_other_data_is_refused_but_its_own_fields_pass(self):
        with self.s.step("dashboard", USER) as st:
            st.seed_tiles("ABC")
        own = self.step_by("glance_tiles", "ABC|risks", {"outline": "A", "sort_order": 5})
        self.assertEqual(self.back(own)[0], 200)

    def test_the_rows_check_by_field_directly(self):
        row = lambda table, key, field, via="dashboard": {"table": table, "key": key, "via": via, "field": field}   # noqa: E731
        ok = lambda *rows: changes._eligible(list(rows), "ABC")                                                      # noqa: E731
        self.assertTrue(ok(row("projects", "ABC", "health"), row("projects", "ABC", "health_reason"), row("projects", "ABC", "updated_at")))
        self.assertFalse(ok(row("projects", "ABC", "health"), row("projects", "ABC", "name")))
        self.assertFalse(ok(row("projects", "ABC", "phase")))
        self.assertFalse(ok(row("projects", "XYZ", "health")), "another project's row")
        self.assertFalse(ok(row("projects", "ABCD", "health")))
        self.assertTrue(ok(row("glance_tiles", "ABC|risks", "hidden")))
        self.assertFalse(ok(row("glance_tiles", "XYZ|risks", "hidden")), "another project's tile")
        self.assertFalse(ok(row("glance_tiles", "ABC|nope", "hidden")))
        self.assertFalse(ok(row("glance_tiles", "ABC|risks", "tile")))
        self.assertTrue(ok(row("glance_tiles", "ABC|risks", "hidden", "seed"), row("glance_tiles", "ABC|risks", "tile", "seed")), "the seed is history")
        self.assertFalse(ok(row("projects", "ABC", "health", "seed"), row("projects", "ABC", "name", "seed")))
        self.assertTrue(ok(row("report_sections", "ABC-S-001", "title"), row("glance_tiles", "ABC|risks", "hidden")), "sections and tiles may share a step")
        self.assertFalse(ok(row("report_sections", "ABC-S-001", "title"), row("glance_tiles", "XYZ|risks", "hidden")), "a section with another project's tile")
        self.assertFalse(ok(row("projects", "ABC", "health", "excel")), "another route")
        self.assertFalse(ok(row("projects", "ABC", "health", "revert:4")))
        self.assertFalse(ok(row("links", "a|b|c", "kind")), "a table outside UNDOABLE")
        self.assertFalse(ok())
        self.assertFalse(ok(row("actions", "ABC-A-001", "status"), row("glance_tiles", "ABC|risks", "hidden")), "work items never mix")

    def test_another_route_step_on_a_tile_or_health_is_still_refused(self):
        step = self.step_by("projects", "ABC", {"health": "At risk", "health_reason": "x"})
        con = sqlite3.connect(str(self.path))
        con.execute("UPDATE change_log SET via = 'excel' WHERE apply_id = ?", (step,))
        con.commit()
        con.close()
        self.assertEqual(self.back(step)[0], 400)

    def test_another_projects_step_is_refused(self):
        body = self.ok(self.proj(health="At risk", health_reason="x"))
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        self.assertEqual(self.undo({"project": "XYZ", "apply_id": body["apply_id"]})[0], 400)
        self.assertEqual(self.project()["health"], "At risk")


if __name__ == "__main__":
    unittest.main()

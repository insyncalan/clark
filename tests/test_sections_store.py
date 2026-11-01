"""#65: the report's own tables in the one writer (src/clark/store.py; guarded): sections with ids, rules, order, delete, undo
and the seed of the eleven default sections; glance_tiles and report_hidden are registered for #45 and #67.

Run: python3 dev/run_tests.py test_sections_store
The data is the fictional store of tests/_demo.py. The route that lets a page change these rows is tested in test_changes.py.
"""
import unicodedata
import unittest

from _demo import USER, DemoStore
from _paths import SRC
from clark import default_sections, order, store as store_module
from clark.store import Invalid

NINE = ("current", "glance", "usecases", "milestones", "text", "raid", "actions", "decisions", "docs")
ELEVEN = (
    ("current", "Current state", 0), ("glance", "At a glance", 0), ("usecases", "Use case summary", 0),
    ("milestones", "Milestones", 0), ("text", "Summary", 0), ("text", "This week", 1), ("text", "Next week", 0),
    ("raid", "Risks and issues", 0), ("actions", "Open actions", 0), ("decisions", "Decisions", 0),
    ("docs", "Supporting documents", 0))


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.addCleanup(self.demo.close)

    def sections(self, code="ABC"):
        return order.in_order(self.s.read("report_sections", code))

    def add(self, title="Plan", code="ABC", **more):
        """A text section at the end, in a step of its own; its id."""
        with self.s.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": code, "type": "text", "title": title,
                                                 "sort_order": order.end_slot(self.sections(code)), **more})

    def last_step(self):
        return self.demo.last_step()

    def change(self, ref, **changes):
        with self.s.step("dashboard", USER) as st:
            st.update("report_sections", ref, changes)
        return self.last_step()


class Seed(Base):
    def test_sections_seed(self):
        rows = self.sections()
        self.assertEqual([(r["type"], r["title"], r["beside"]) for r in rows], list(ELEVEN))
        self.assertEqual([r["id"] for r in rows], [f"ABC-S-{n:03d}" for n in range(1, 12)])
        self.assertEqual([r["sort_order"] for r in rows], [order.GAP * n for n in range(1, 12)])
        self.assertEqual({(r["hidden"], r["body"]) for r in rows}, {(0, "")})
        self.assertEqual({r["project"] for r in rows}, {"ABC"})

    def test_the_seed_is_in_the_projects_own_step_and_one_undo_means_one_thing(self):
        first = self.s.con.execute("SELECT min(apply_id) FROM applies").fetchone()[0]
        tables = {r[0] for r in self.s.con.execute("SELECT DISTINCT tbl FROM change_log WHERE apply_id = ?", (first,))}
        self.assertIn("projects", tables)
        self.assertIn("report_sections", tables)
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme"})
        self.assertEqual(len(self.sections("XYZ")), 11)
        self.assertEqual([r["id"] for r in self.sections("XYZ")][:2], ["XYZ-S-001", "XYZ-S-002"])
        self.assertEqual(len(self.sections("ABC")), 11)

    def test_undoing_a_projects_creation_leaves_the_project_and_its_sections_whole(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme"})
        made = self.last_step()
        before = (self.s.read("projects", ref="XYZ"), self.sections("XYZ"))
        out = self.s.undo(made, USER)
        self.assertIsNone(out["step_id"])                                  # nothing was put back: no step, no half-done work
        self.assertEqual(out["reversed"], [])
        self.assertEqual((self.s.read("projects", ref="XYZ"), self.sections("XYZ")), before)
        self.assertEqual(len(before[1]), 11)
        self.assertTrue(all("can't be removed by an undo" in s["why"] for s in out["skipped"]), out["skipped"])
        self.assertIn("a new project's sections can't be removed by an undo", {s["why"] for s in out["skipped"]})
        ref = self.add("Later", code="XYZ")                               # a section added to it later is a step of its own
        out = self.s.undo(self.last_step(), USER)
        self.assertEqual((out["skipped"], self.s.read("report_sections", ref=ref)), ([], None))
        self.assertEqual(len(self.sections("XYZ")), 11)

    def test_the_default_sections_are_pinned(self):
        self.assertEqual([(s["type"], s["title"], s.get("beside", 0)) for s in default_sections.DEFAULT_SECTIONS], list(ELEVEN))
        self.assertTrue(all(s["type"] in NINE for s in default_sections.DEFAULT_SECTIONS))
        from clark.section_kinds import TYPES as TEMPLATE_TYPES
        self.assertEqual(set(store_module.SECTION_TYPES), set(NINE) | {"needs", "tracker"} | set(TEMPLATE_TYPES))      # the nine of the starting report, and those that carry content (#96: the section templates too)

    def test_data_for_gives_the_sections_in_order_with_their_own_query(self):
        data = self.s.data_for("ABC")
        self.assertEqual([r["title"] for r in data["report_sections"]], [e[1] for e in ELEVEN])
        self.assertEqual(sorted(data["report_sections"][0]), sorted(["id", "type", "title", "body", "beside", "hidden", "sort_order"]))
        self.assertEqual(self.s.data_for("XYZ"), None)

    def test_a_tie_in_sort_order_is_shown_by_id(self):
        a, b = self.add("Tie A"), self.add("Tie B")
        self.change(b, sort_order=self.s.read("report_sections", ref=a)["sort_order"])
        ids = [r["id"] for r in self.s.data_for("ABC")["report_sections"]]
        self.assertEqual(ids.index(a) + 1, ids.index(b))                  # same sort_order: the lower id first
        self.assertEqual(ids, [r["id"] for r in self.sections()])


class Tables(Base):
    def test_the_three_tables_are_known_and_keyed(self):
        for table, key in (("report_sections", ("id",)), ("glance_tiles", ("project", "tile")),
                           ("report_hidden", ("project", "item_id"))):
            with self.subTest(table=table):
                self.assertIn(table, store_module.TABLES)
                self.assertEqual(store_module.KEYS[table], key)
                self.assertIn(table, store_module.REQUIRED_NEW)
                self.assertIn(table, store_module.DELETED_ON_CANCEL)
                self.assertTrue(set(store_module.REQUIRED_NEW[table]) <= set(store_module.columns(self.s.con, table)))
        self.assertEqual(store_module.ID_PREFIX["report_sections"], "-S-")
        self.assertEqual(store_module.REVERT_CREATED.count("report_sections"), 1)
        self.assertNotIn("report_sections", store_module.ITEM_TABLE.values())          # a section is not linkable or labelled
        self.assertIsNone(store_module.item_table("ABC-S-001"))

    def test_section_ids_are_per_project_and_never_reused(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme"})
        one = self.add("One")
        self.assertEqual(one, "ABC-S-012")
        self.assertEqual(self.add("Other project", code="XYZ"), "XYZ-S-012")
        out = self.s.undo(self.demo.last_step(), USER)                  # undo the XYZ add: its row goes
        self.assertEqual(out["skipped"], [])
        self.assertEqual(self.add("Again", code="XYZ"), "XYZ-S-013")    # the number is not freed
        self.assertEqual(self.add("Two"), "ABC-S-013")

    def test_a_new_section_carries_no_id(self):
        with self.assertRaisesRegex(Invalid, "no ID"):
            with self.s.step("dashboard", USER) as st:
                st.create("report_sections", {"project": "ABC", "id": "ABC-S-099", "type": "text", "title": "x", "sort_order": 1})


class Rules(Base):
    def bad(self, words, **values):
        row = {"project": "ABC", "type": "text", "title": "Fine", "sort_order": 99999, **values}
        count = len(self.sections())
        with self.assertRaisesRegex(Invalid, words):
            with self.s.step("dashboard", USER) as st:
                st.create("report_sections", row)
        self.assertEqual(len(self.sections()), count, "nothing was written")

    def test_section_rules_refuse_with_plain_words(self):
        self.bad("missing required", title="")                           # a blank title is a missing one
        self.bad("missing required", title="   ")
        self.bad("missing required", title="\u00a0\t\n")
        with self.assertRaisesRegex(Invalid, "can't be blank"):             # and an update to a blank one says so
            self.change("ABC-S-005", title="  ")
        self.assertEqual(store_module.section_title("  Plan  "), "Plan")
        self.bad("at most 120", title="x" * 121)
        self.bad("invisible", title="Plan\u202eevil")                   # a bidi override
        self.bad("invisible", title="Plan\u200b")                       # a zero-width space
        self.bad("invisible", title="\ufeffPlan")
        self.bad("invisible", title="Two\nlines")
        self.bad("invisible", title="Line\u2028break")
        self.bad("invisible", title="Lone \ud800 surrogate")
        self.bad("invisible", title="\u200b")
        self.bad("must be text", title=["Plan"])
        self.bad("must be text", title={"a": 1})
        self.bad("must be text", title=5)
        self.bad("whole number", sort_order=1.5)
        self.bad("whole number", sort_order="7")
        self.bad("whole number", sort_order=True)
        self.bad("whole number", sort_order=None)
        self.bad("body", type="raid", body="not allowed")
        self.bad("must be one of", type="bogus")
        self.bad("0 or 1", hidden="yes")
        self.bad("0 or 1", beside=2)
        self.bad("0 or 1", hidden=None)
        self.bad("missing required", title=None)
        with self.assertRaisesRegex(Invalid, "missing required"):
            with self.s.step("dashboard", USER) as st:
                st.create("report_sections", {"type": "text", "title": "No project", "sort_order": 1})
        with self.assertRaisesRegex(Invalid, "isn't here"):
            with self.s.step("dashboard", USER) as st:
                st.create("report_sections", {"project": "NOP", "type": "text", "title": "x", "sort_order": 1})

    def test_a_title_that_shows_nothing_is_refused_and_one_that_shows_something_is_not(self):
        blank = ["\u2800", "\u3164", "\uffa0", "\u034f", "\u115f", "\u1160", "\u0301", "\u0903", "\u20dd", "\U0001d159", "\ufffc",   # braille blank, fillers, marks
                 *(chr(c) for c in range(0x180b, 0x180e)), "\u180f", *(chr(c) for c in range(0xfe00, 0xfe10)), "\u2800\u3164\u0301"]
        for title in blank:
            for shape in ("{}", "  {}  ", "{} {} {}", "\u00a0{}\t"):
                with self.subTest(title=f"U+{ord(title[0]):04X}", shape=shape):
                    with self.assertRaisesRegex(Invalid, "can't be blank|invisible|visible letter"):
                        store_module.section_title(shape.format(*[title] * 3))
        self.bad("visible letter", title="\u2800")                         # and through the store's own rules
        for title in ("Risks", "Plan 2", "- 1 -", "\u2764", "Caf\u00e9 \u00dcber", "e\u0301", "\U0001F600", "\u6708\u6b21\u5831\u544a",
                      "\ud55c\uad6d\uc5b4", "\U0001F600 \u2800"):
            with self.subTest(title=title):
                self.assertEqual(store_module.section_title(title), unicodedata.normalize("NFC", title))

    def test_a_title_is_stored_trimmed_and_in_nfc(self):
        ref = self.add("  Cafe\u0301 plan  ")                            # e + combining acute
        self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Caf\u00e9 plan")
        step = self.change(ref, title="  Nai\u0308ve  ")
        self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Na\u00efve")
        self.assertEqual(self.s.undo(step, USER)["skipped"], [])
        self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Caf\u00e9 plan")

    def test_120_characters_fit_and_count_code_points_not_utf16_units(self):
        ref = self.add("\U0001F600" * 120)                              # one code point each (two in JavaScript)
        self.assertEqual(len(self.s.read("report_sections", ref=ref)["title"]), 120)
        self.bad("at most 120", title="\U0001F600" * 121)

    def test_frozen_fields(self):
        ref = self.add()
        for field, value in (("type", "raid"), ("project", "XYZ"), ("id", "ABC-S-099")):
            with self.subTest(field=field):
                with self.assertRaisesRegex(Invalid, "can't be changed"):
                    self.change(ref, **{field: value})
        self.assertEqual(self.s.read("report_sections", ref=ref)["type"], "text")

    def test_only_a_text_section_has_a_body(self):
        raid = self.sections()[7]["id"]
        self.assertEqual(self.s.read("report_sections", ref=raid)["type"], "raid")
        with self.assertRaises(Invalid):
            self.change(raid, body="words")
        self.change(raid, hidden=1)                                     # hiding is for every type
        self.assertEqual(self.s.read("report_sections", ref=raid)["hidden"], 1)
        text = self.add()
        self.change(text, beside=1, body="<p>words</p>")
        self.assertEqual(self.s.read("report_sections", ref=text)["body"], "<p>words</p>")

    def test_every_type_can_sit_beside_another(self):
        seen = set()
        for row in self.sections():
            with self.subTest(type=row["type"]):
                self.change(row["id"], beside=1)
                self.assertEqual(self.s.read("report_sections", ref=row["id"])["beside"], 1)
                seen.add(row["type"])
        self.assertGreater(len(seen), 1)
        self.assertEqual(len(self.sections()), len(ELEVEN))             # nothing else about a section changed

    def test_beside_still_takes_only_0_or_1_on_any_type(self):
        raid = self.sections()[7]["id"]
        with self.assertRaisesRegex(Invalid, "0 or 1"):
            self.change(raid, beside=2)

    def test_a_flag_that_is_a_bool_is_stored_and_logged_as_1_or_0_and_undoes(self):
        ref = self.add()
        step = self.change(ref, hidden=True)                            # the store turns True into 1 (#89)
        self.assertEqual(self.s.read("report_sections", ref=ref)["hidden"], 1)
        row = self.s.con.execute("SELECT old_value, new_value FROM change_log WHERE apply_id = ? AND field = 'hidden'",
                                 (step,)).fetchone()
        self.assertEqual((row[0], row[1]), ("0", "1"))
        self.assertEqual(self.s.undo(step, USER)["skipped"], [])
        self.assertEqual(self.s.read("report_sections", ref=ref)["hidden"], 0)

    def test_at_most_100_sections_a_project(self):
        with self.s.step("dashboard", USER) as st:
            for n in range(89):
                st.create("report_sections", {"project": "ABC", "type": "text", "title": f"S{n}", "sort_order": 100000 + n})
        self.assertEqual(len(self.sections()), 100)
        self.bad("at most 100", title="One too many")
        with self.s.step("dashboard", USER) as st:                      # an update of one of the 100 is not a new section
            st.update("report_sections", "ABC-S-012", {"title": "Renamed"})
        self.assertEqual(self.s.read("report_sections", ref="ABC-S-012")["title"], "Renamed")

    def test_an_undo_that_would_make_101_leaves_the_section_deleted_and_says_so(self):
        gone = self.add("Will go")
        with self.s.step("dashboard", USER) as st:
            st.cancel("report_sections", gone)
        deleted = self.last_step()
        with self.s.step("dashboard", USER) as st:
            for n in range(89):
                st.create("report_sections", {"project": "ABC", "type": "text", "title": f"S{n}", "sort_order": 100000 + n})
        self.assertEqual(len(self.sections()), 100)
        out = self.s.undo(deleted, USER)
        self.assertIsNone(self.s.read("report_sections", ref=gone))
        self.assertEqual([s["why"] for s in out["skipped"]], ["A report can have at most 100 sections."])
        self.assertEqual(len(self.sections()), 100)

    def test_the_id_must_start_with_the_projects_code(self):
        with self.assertRaisesRegex(Invalid, "doesn't belong"):
            store_module._section_rules(self.s.con, "report_sections", {"project": "ABC", "id": "XYZ-S-001", "type": "text",
                                                                        "title": "x", "sort_order": 1}, {"id"})


class TilesAndHidden(Base):
    """Registered now, in one amendment, for #45 and #67: the rows and rules exist; no route can reach them (test_changes)."""

    def tile(self, **values):
        with self.s.step("dashboard", USER) as st:
            return st.create("glance_tiles", {"project": "ABC", "tile": "health", "sort_order": 0, **values})

    def test_tiles(self):
        self.assertEqual(self.tile(), "ABC|health")                     # sort_order 0 is a place
        self.assertEqual(self.tile(tile="risks", outline="R", sort_order=2048), "ABC|risks")
        for words, values in (("must be one of", {"tile": "nope"}), ("must be one of", {"tile": "overdue", "outline": "Z"}),
                              ("whole number", {"tile": "overdue", "sort_order": None}),
                              ("whole number", {"tile": "overdue", "sort_order": "1"}),
                              ("0 or 1", {"tile": "overdue", "hidden": 3}), ("already has", {"tile": "health"})):
            with self.subTest(values=values):
                with self.assertRaisesRegex(Invalid, words):
                    self.tile(**values)
        with self.s.step("dashboard", USER) as st:
            st.update("glance_tiles", "ABC|health", {"hidden": 1})
            st.cancel("glance_tiles", "ABC|risks")
        self.assertEqual(self.s.read("glance_tiles", ref="ABC|health")["hidden"], 1)
        self.assertIsNone(self.s.read("glance_tiles", ref="ABC|risks"))
        with self.assertRaisesRegex(Invalid, "can't be changed"):
            with self.s.step("dashboard", USER) as st:
                st.update("glance_tiles", "ABC|health", {"tile": "risks"})

    def test_hidden_rows(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            self.assertEqual(st.create("report_hidden", {"project": "ABC", "item_id": a}), f"ABC|{a}")
            st.create("report_hidden", {"project": "ABC", "item_id": self.demo.milestone})
            st.create("report_hidden", {"project": "ABC", "item_id": self.demo.use_case})
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme"})
        other = None
        with self.s.step("dashboard", USER) as st:
            other = st.create("actions", {"project": "XYZ", "description": "d", "raised": "2026-10-01", "source": "demo"})
        for item in (other, "ABC-A-099", "ABC-S-001", "not an id", "", None):
            with self.subTest(item=item):
                with self.assertRaises(Invalid):
                    with self.s.step("dashboard", USER) as st:
                        st.create("report_hidden", {"project": "ABC", "item_id": item})
        with self.s.step("dashboard", USER) as st:
            st.cancel("report_hidden", f"ABC|{a}")                       # unhide: the row goes, and an Undo puts it back
        self.assertEqual(self.s.undo(self.last_step(), USER)["skipped"], [])
        self.assertEqual(self.s.read("report_hidden", ref=f"ABC|{a}")["item_id"], a)
        self.assertEqual(self.s.read("report_hidden", "XYZ"), [])


class Move(Base):
    def move(self, ref, before):
        with self.s.step("dashboard", USER) as st:
            for other, place in order.section_slot(self.sections(), ref, before).items():
                st.update("report_sections", other, {"sort_order": place})
        return self.last_step()

    def test_move_changes_only_the_moved_row(self):
        before = {r["id"]: r["sort_order"] for r in self.sections()}
        step = self.move("ABC-S-009", "ABC-S-002")
        rows = self.s.con.execute("SELECT DISTINCT item_id FROM change_log WHERE apply_id = ?", (step,)).fetchall()
        self.assertEqual([r[0] for r in rows], ["ABC-S-009"])
        now = {r["id"]: r["sort_order"] for r in self.sections()}
        self.assertEqual({k for k in now if now[k] != before[k]}, {"ABC-S-009"})
        self.assertEqual([r["id"] for r in self.sections()][:3], ["ABC-S-001", "ABC-S-009", "ABC-S-002"])

    def test_move_renumbers_when_there_is_no_gap(self):
        for n, ref in enumerate(("ABC-S-001", "ABC-S-002", "ABC-S-003", "ABC-S-004")):
            self.change(ref, sort_order=10 + n)                          # four rows one apart
        step = self.move("ABC-S-006", "ABC-S-002")                       # no whole number between 10 and 11
        changed = {r[0] for r in self.s.con.execute("SELECT DISTINCT item_id FROM change_log WHERE apply_id = ?", (step,))}
        self.assertGreater(len(changed), 1)
        self.assertEqual([r["id"] for r in self.sections()][:3], ["ABC-S-001", "ABC-S-006", "ABC-S-002"])
        out = self.s.undo(step, USER)
        self.assertEqual(out["skipped"], [])
        self.assertEqual([r["id"] for r in self.sections()][:3], ["ABC-S-001", "ABC-S-002", "ABC-S-003"])


class Delete(Base):
    def test_only_text_sections_are_deleted(self):
        for row in self.sections():
            with self.subTest(section=row["title"]):
                if row["type"] == "text":
                    continue
                with self.assertRaisesRegex(Invalid, "Only a text, needs or tracker section can be deleted; hide the others"):
                    with self.s.step("dashboard", USER) as st:
                        st.cancel("report_sections", row["id"])
        self.assertEqual(len(self.sections()), 11)
        with self.s.step("dashboard", USER) as st:
            st.cancel("report_sections", "ABC-S-005")                    # Summary is text
        self.assertEqual(len(self.sections()), 10)

    def test_a_work_item_is_still_never_deleted(self):
        a = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.cancel("actions", a)                                      # closes it as Cancelled; the row stays
        self.assertEqual(self.s.read("actions", ref=a)["status"], "Cancelled")
        self.assertNotIn("actions", store_module.DELETED_ON_CANCEL)


class UndoEachKind(Base):
    def back_and_forth(self, step, check_before, check_after):
        """Undo `step`, then Undo of the Undo; `check_before` holds before the step and after the first undo, `check_after`
        after the step and after the undo of the undo."""
        check_after()
        out = self.s.undo(step, USER)
        self.assertEqual(out["skipped"], [])
        check_before()
        again = self.s.undo(out["step_id"], USER)
        self.assertEqual(again["skipped"], [])
        check_after()

    def test_section_undo_puts_back_each_kind(self):
        # add
        ref = self.add("Plan")
        self.back_and_forth(self.last_step(), lambda: self.assertIsNone(self.s.read("report_sections", ref=ref)),
                            lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Plan"))
        # rename
        step = self.change(ref, title="Renamed")
        self.back_and_forth(step, lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Plan"),
                            lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Renamed"))
        # hide
        step = self.change(ref, hidden=1)
        self.back_and_forth(step, lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["hidden"], 0),
                            lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["hidden"], 1))
        # beside
        step = self.change(ref, beside=1)
        self.back_and_forth(step, lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["beside"], 0),
                            lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["beside"], 1))
        # move
        place = self.s.read("report_sections", ref=ref)["sort_order"]
        step = self.change(ref, sort_order=1)
        self.back_and_forth(step, lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["sort_order"], place),
                            lambda: self.assertEqual(self.s.read("report_sections", ref=ref)["sort_order"], 1))
        # delete
        row = dict(self.s.read("report_sections", ref=ref))
        with self.s.step("dashboard", USER) as st:
            st.cancel("report_sections", ref)
        self.back_and_forth(self.last_step(), lambda: self.assertEqual(self.s.read("report_sections", ref=ref), row),
                            lambda: self.assertIsNone(self.s.read("report_sections", ref=ref)))

    def test_section_undo_skips_a_later_change_and_names_it(self):
        ref = self.add("Plan")
        first = self.change(ref, title="Second name")
        later = self.change(ref, title="Third name")
        out = self.s.undo(first, USER)
        self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Third name")
        self.assertEqual([(s["ref"], s["field"], s["by_step"]) for s in out["skipped"]], [(ref, "title", later)])
        self.assertIsNone(out["step_id"])

    def test_an_add_followed_by_a_rename_is_not_undone(self):
        ref = self.add("Plan")
        added = self.last_step()
        later = self.change(ref, title="Renamed")
        out = self.s.undo(added, USER)
        self.assertIsNotNone(self.s.read("report_sections", ref=ref))
        self.assertEqual([s["by_step"] for s in out["skipped"]], [later])

    def test_a_later_step_that_was_only_an_undo_does_not_block_and_is_never_named(self):
        ref = self.add("Plan")
        added = self.last_step()
        renamed = self.change(ref, title="Renamed")
        self.s.undo(renamed, USER)
        undo_step = self.last_step()
        out = self.s.undo(added, USER)                                      # the rename is undone, so only an undo is later
        self.assertEqual((out["skipped"], self.s.read("report_sections", ref=ref)), ([], None))
        self.assertGreater(undo_step, renamed)
        ref = self.add("Plan two")
        added = self.last_step()
        self.change(ref, title="Renamed")
        kept = self.change(ref, title="Renamed again")
        self.s.undo(kept, USER)                                             # back to "Renamed": that rename is still a change
        out = self.s.undo(added, USER)
        self.assertEqual([s["by_step"] for s in out["skipped"]], [kept - 1])
        self.assertIsNotNone(self.s.read("report_sections", ref=ref))

    def test_a_section_made_and_then_changed_or_deleted_in_one_step_goes_back_whole(self):
        with self.s.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Plan", "sort_order": 99999})
            st.update("report_sections", ref, {"title": "Renamed", "hidden": 1})
        step = self.last_step()
        later = self.change(ref, title="A person's later name")                  # a real later step still blocks the undo
        out = self.s.undo(step, USER)
        self.assertEqual(([s["by_step"] for s in out["skipped"]], self.s.read("report_sections", ref=ref)["title"]),
                         ([later], "A person's later name"))
        with self.s.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Plan", "sort_order": 99999})
            st.update("report_sections", ref, {"title": "Renamed", "hidden": 1})
        out = self.s.undo(self.last_step(), USER)
        self.assertEqual((out["skipped"], self.s.read("report_sections", ref=ref)), ([], None))
        with self.s.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "text", "title": "Gone", "sort_order": 99999})
            st.cancel("report_sections", ref)
        out = self.s.undo(self.last_step(), USER)
        self.assertEqual((out["skipped"], self.s.read("report_sections", ref=ref)), ([], None))
        self.assertEqual(self.s.undo(self.last_step(), USER)["skipped"], [])      # and the Undo of that Undo is quiet too

    def test_seed_sections_is_for_a_project_with_none_and_refuses_one_that_has_some(self):
        with self.assertRaisesRegex(Invalid, "has its report sections already"):
            with self.s.step("dashboard", USER) as st:
                st.seed_sections("ABC")
        self.assertEqual(len(self.sections()), 11)

    def test_a_field_changed_twice_in_one_step_goes_back_to_its_first_value(self):
        ref = self.add("Plan")
        with self.s.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"title": "Middle"})
            st.update("report_sections", ref, {"title": "Last"})
        out = self.s.undo(self.last_step(), USER)
        self.assertEqual(out["skipped"], [])
        self.assertEqual(self.s.read("report_sections", ref=ref)["title"], "Plan")


class Source(unittest.TestCase):
    def test_store_py_gains_no_sql_part_for_sections(self):
        """The one-writer test's list of SQL parts is untouched by #65: nothing is built from a name that isn't checked."""
        text = (SRC.parent / "tests" / "test_store_writer.py").read_text(encoding="utf-8")
        self.assertNotIn("report_sections", text)


if __name__ == "__main__":
    unittest.main()

"""#115: the person writers in store.py (add, edit, rename, merge, archive, restore, Undo), guarded.

Run: python3 dev/run_tests.py test_people_store
Every write goes through one step of the one writer, so each is one Undo. Fictional data only.
"""
import unittest

from _demo import USER, DemoStore
from clark.store import Invalid


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.addCleanup(self.demo.close)

    def step(self):
        return self.s.step("dashboard", USER)

    def add(self, name, **kw):
        with self.step() as st:
            return st.add_person(name=name, source="test", **kw)

    def person(self, ref):
        return self.s.con.execute("SELECT * FROM people WHERE id = ?", (ref,)).fetchone()

    def owned(self, person_ref, text):
        a = self.demo.action(owner=text)
        with self.step() as st:
            st.update("actions", a, {"owner_id": person_ref})
        return a

    def undo_last(self):
        self.s.undo(self.demo.last_step(), USER)

    def dump(self):
        return list(self.s.con.iterdump())


class AddAndEdit(Base):
    def test_a_new_person_gets_the_next_id_and_clean_fields(self):
        a = self.add("  Sam   Reed ", email=" Sam@X.example ")
        b = self.add("Jo Park")
        self.assertEqual((a, b), ("P-001", "P-002"))
        row = self.person(a)
        self.assertEqual((row["name"], row["email"], row["needs_details"], row["archived"]), ("Sam Reed", "sam@x.example", 0, 0))

    def test_a_person_added_without_an_email_can_be_flagged_and_an_email_clears_it(self):
        a = self.add("Jo Park", needs_details=1)
        self.assertEqual(self.person(a)["needs_details"], 1)
        with self.step() as st:
            st.edit_person(a, {"email": "jo@x.example"})
        self.assertEqual(self.person(a)["needs_details"], 0)

    def test_the_rules_refuse_in_words_and_write_nothing(self):
        self.add("Sam Reed", email="sam@x.example")
        before = self.dump()
        bad = [{"name": "  "}, {"name": "A", "email": "no at"}, {"name": "A", "email": "SAM@x.example"},
               {"name": "A", "label": "x" * 31}, {"name": "A", "kind": "robot"}, {"name": "A", "id": "P-050"}]
        for fields in bad:
            with self.assertRaises(Invalid, msg=fields):
                with self.step() as st:
                    st.add_person(source="test", **fields)
        self.assertEqual(self.dump(), before)

    def test_a_person_needs_a_source(self):
        with self.assertRaises(Invalid):
            with self.step() as st:
                st.add_person(name="Sam Reed")

    def test_editing_checks_the_email_against_everyone_but_the_person(self):
        a = self.add("Sam Reed", email="sam@x.example")
        b = self.add("Jo Park", email="jo@x.example")
        with self.step() as st:
            st.edit_person(a, {"email": "sam@x.example", "role": "Lead"})        # their own email again is fine
        with self.assertRaises(Invalid) as caught:
            with self.step() as st:
                st.edit_person(b, {"email": "sam@x.example"})
        self.assertIn("Sam Reed", str(caught.exception))

    def test_two_people_may_share_a_name_and_a_number_is_never_reused(self):
        a = self.add("Sam Reed")
        b = self.add("Sam Reed", label="Quay team")
        self.assertEqual((a, b), ("P-001", "P-002"))
        self.undo_last()                                        # the creation of P-002 goes
        self.assertIsNone(self.person("P-002"))
        self.assertEqual(self.add("Jo Park"), "P-003")

    def test_one_step_is_one_undo_and_a_person_is_taken_away_only_by_undoing_their_creation(self):
        a = self.add("Sam Reed")
        self.undo_last()
        self.assertIsNone(self.person(a))


class ArchiveAndRestore(Base):
    def test_archive_hides_and_restore_brings_back_with_the_email(self):
        a = self.add("Sam Reed", email="sam@x.example")
        with self.step() as st:
            st.archive_person(a)
        self.assertEqual(self.person(a)["archived"], 1)
        self.assertEqual([p["id"] for p in self.s.people()], [])
        self.assertEqual(self.s.resolve_owner("Sam Reed")["status"], "archived")
        with self.step() as st:
            st.restore_person(a)
        row = self.person(a)
        self.assertEqual((row["archived"], row["email"]), (0, "sam@x.example"))

    def test_archiving_leaves_the_owner_text_and_link_on_items(self):
        a = self.add("Sam Reed")
        item = self.owned(a, "Sam Reed")
        with self.step() as st:
            st.archive_person(a)
        row = self.s.read("actions", ref=item)
        self.assertEqual((row["owner"], row["owner_id"]), ("Sam Reed", a))

    def test_there_is_no_delete_and_an_archived_person_cannot_be_edited(self):
        a = self.add("Sam Reed")
        with self.step() as st:
            st.archive_person(a)
        with self.assertRaises(Invalid):
            with self.step() as st:
                st.edit_person(a, {"role": "Lead"})
        with self.assertRaises(Invalid):
            with self.step() as st:
                st.cancel("people", a)
        self.assertFalse(hasattr(type(self.s), "delete_person"))

    def test_undo_of_an_archive_restores_the_person(self):
        a = self.add("Sam Reed")
        with self.step() as st:
            st.archive_person(a)
        self.undo_last()
        self.assertEqual(self.person(a)["archived"], 0)


class Rename(Base):
    def test_rename_changes_the_person_and_every_live_item_in_one_step(self):
        a = self.add("Sam Reed")
        live = self.owned(a, "Sam Reed")
        other = self.demo.action(owner="Sam Reed")              # typed, never linked: left alone
        old = self.owned(a, "Sam Reed")
        with self.step() as st:
            st.archive("actions", old)
        with self.step() as st:
            n = st.rename_person(a, "Sam Reid")
        self.assertEqual(n, 1)
        self.assertEqual(self.person(a)["name"], "Sam Reid")
        self.assertEqual(self.s.read("actions", ref=live)["owner"], "Sam Reid")
        self.assertEqual(self.s.read("actions", ref=other)["owner"], "Sam Reed")
        self.assertEqual(self.s.read("actions", ref=old)["owner"], "Sam Reed")      # an archived item keeps the name it had
        self.assertEqual(self.demo.last_step(), self.s.con.execute("SELECT max(apply_id) FROM change_log").fetchone()[0])

    def test_rename_reaches_each_kind_of_owner_column(self):
        a = self.add("Sam Reed")
        ws = self.s.con.execute("SELECT id FROM workstreams").fetchone()[0]
        with self.step() as st:
            st.update("workstreams", ws, {"lead": "Sam Reed", "owner_id": a})
            st.update("milestones", self.demo.milestone, {"owner": "Sam Reed", "owner_id": a})
        with self.step() as st:
            self.assertEqual(st.rename_person(a, "Sam Reid"), 2)
        self.assertEqual(self.s.read("workstreams", ref=ws)["lead"], "Sam Reid")
        self.assertEqual(self.s.read("milestones", ref=self.demo.milestone)["owner"], "Sam Reid")

    def test_undo_of_a_rename_puts_back_the_name_everywhere(self):
        a = self.add("Sam Reed")
        item = self.owned(a, "Sam Reed")
        with self.step() as st:
            st.rename_person(a, "Sam Reid")
        self.undo_last()
        self.assertEqual(self.person(a)["name"], "Sam Reed")
        self.assertEqual(self.s.read("actions", ref=item)["owner"], "Sam Reed")

    def test_a_refused_rename_changes_nothing(self):
        a = self.add("Sam Reed")
        self.owned(a, "Sam Reed")
        before = self.dump()
        with self.assertRaises(Invalid):
            with self.step() as st:
                st.rename_person(a, "  ")
        self.assertEqual(self.dump(), before)


class Merge(Base):
    def test_merge_repoints_items_moves_aliases_and_archives_the_source(self):
        src = self.add("Sam Reed", email="sam@x.example", aliases="Sammy")
        tgt = self.add("Sam Reid", email="reid@x.example")
        item = self.owned(src, "Sam Reed")
        with self.step() as st:
            n = st.merge_people(src, tgt)
        self.assertEqual(n, 1)
        row = self.s.read("actions", ref=item)
        self.assertEqual((row["owner"], row["owner_id"]), ("Sam Reid", tgt))
        t, s = self.person(tgt), self.person(src)
        self.assertEqual(sorted(t["aliases"].split(";")), ["Sam Reed", "Sammy"])
        self.assertEqual(t["email"], "reid@x.example")                     # the target keeps its own email
        self.assertEqual((s["archived"], s["email"]), (1, None))            # the source gives up its email
        self.assertEqual(self.s.resolve_owner("Sammy")["id"], tgt)

    def test_the_target_never_takes_the_sources_email_and_the_source_frees_it(self):
        src = self.add("Sam Reed", email="sam@x.example")
        tgt = self.add("Sam Reid")
        with self.step() as st:
            st.merge_people(src, tgt)
        self.assertIsNone(self.person(tgt)["email"])
        self.assertIsNone(self.person(src)["email"])
        self.add("Li Wen", email="sam@x.example")                           # the address is free to use again

    def test_merge_is_one_undo(self):
        src = self.add("Sam Reed", email="sam@x.example", aliases="Sammy")
        tgt = self.add("Sam Reid")
        item = self.owned(src, "Sam Reed")
        with self.step() as st:
            st.merge_people(src, tgt)
        self.undo_last()
        row = self.s.read("actions", ref=item)
        self.assertEqual((row["owner"], row["owner_id"]), ("Sam Reed", src))
        self.assertEqual((self.person(src)["archived"], self.person(src)["email"]), (0, "sam@x.example"))
        self.assertIsNone(self.person(tgt)["aliases"])

    def test_merge_refuses_the_same_person_and_an_archived_one(self):
        a = self.add("Sam Reed")
        b = self.add("Jo Park")
        with self.assertRaises(Invalid):
            with self.step() as st:
                st.merge_people(a, a)
        with self.step() as st:
            st.archive_person(b)
        with self.assertRaises(Invalid):
            with self.step() as st:
                st.merge_people(a, b)


if __name__ == "__main__":
    unittest.main()

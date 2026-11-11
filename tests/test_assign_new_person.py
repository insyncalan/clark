"""Row 986: Assign to, add a new person from the picker (src/clark/changes.py; guarded). RULING OPTION A: an optional
`new_person` key on the EXISTING owner update (kind actions, raid, milestones: `owner`; decisions: `made_by`). No new route, no
new kind or op. The request is
    {project, kind, op: "update", id, changes: {<owner field>: NAME}, new_person: {"name": NAME, "email": optional}}
and in ONE step with ONE Undo: the person is added to the people list, and the owner text and owner_id are written. Rules pinned
here (to be checked by the lead before the build): new_person.name must equal (after clean) the owner value in changes; nothing
else in `changes` is touched; a name that is blank, TBC, over 120 characters, holds a hidden character, or is already on the list
(any case, any accent, name or alias, live or archived) is refused in words with NOTHING written; a failed add leaves no person.
Run: python3 dev/run_tests.py test_assign_new_person
Pure Python over a real demo store (fictional data). Red until the build: today `new_person` is an unknown key.
"""
import sqlite3
import threading
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import changes, history as history_module, people as people_rules
from clark import store as store_module

KINDS = (("actions", "owner"), ("raid", "owner"), ("decisions", "made_by"), ("milestones", "owner"))


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.a = self.demo.action(owner="Sara Khan")
        self.ms = self.demo.milestone
        with self.s.step("dashboard", USER) as st:
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                        "likelihood": "Medium", "raised": "2026-10-01", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending",
                                             "needed_by": "2030-01-05", "source": "demo"})
        self.ref = {"actions": self.a, "raid": self.r, "decisions": self.d, "milestones": self.ms}

    def req(self, kind, field, name, person="same", **extra):
        body = {"project": "ABC", "kind": kind, "op": "update", "id": self.ref[kind], "changes": {field: name}, "place": "cell"}
        if person == "same":
            person = {"name": name}
        if person is not None:
            body["new_person"] = person
        body.update(extra)
        return body

    def go(self, kind="actions", field="owner", name="Zelda Quince", **kw):
        status, body = self.change(self.req(kind, field, name, **kw))
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log), (SELECT count(*) FROM people), "
                               "(SELECT count(*) FROM item_events)").fetchone()
        finally:
            con.close()

    def refused(self, request, code=None, status=400):
        before = self.counts()
        row = self.s.read(request["kind"], ref=request["id"]) if request["kind"] in self.ref else None
        got, body = self.change(request)
        self.assertEqual((got, body["ok"]), (status, False), body)
        if code:
            self.assertEqual(body.get("code"), code, body)
        self.assertEqual(self.counts(), before, "nothing was written: no step, no person, no history")
        if row is not None:
            self.assertEqual(self.s.read(request["kind"], ref=request["id"]), row)
        for leak in ("new_person", "owner_id", "INSERT", "Traceback"):
            self.assertNotIn(leak, body["message"])
        return body

    def person(self, name):
        rows = [p for p in self.s.people(archived=None) if p["name"] == name]
        return rows[0] if rows else None


class Adding(Base):
    def test_each_kind_adds_the_person_and_assigns_them_in_one_step(self):
        """4 kinds. Fixture: demo store, no one on the people list. Mutation: write the owner but skip the person (or the reverse)."""
        for kind, field in KINDS:
            with self.subTest(kind=kind):
                before = self.counts()
                name = f"Zelda Quince {kind}"
                body = self.go(kind, field, name)
                p = self.person(name)
                self.assertIsNotNone(p, "the person is on the list")
                row = self.s.read(kind, ref=self.ref[kind])
                self.assertEqual((row[field], row["owner_id"]), (name, p["id"]))
                self.assertEqual(self.counts()[0], before[0] + 1, "ONE step")
                self.assertTrue(body["undoable"])
                self.assertEqual(body["ref"], self.ref[kind])

    def test_the_person_is_stored_as_the_people_list_stores_one_added_by_hand(self):
        """Fixture: name with spaces and an email in capitals. Mutation: store the typed spacing, or the email unchanged."""
        self.go(name="  Zelda   Quince ", person={"name": "  Zelda   Quince ", "email": "Zelda.Quince@Example.org"})
        p = self.person("Zelda Quince")
        self.assertEqual((p["email"], p["needs_details"], p["archived"], p["kind"]), ("zelda.quince@example.org", 0, 0, "person"))
        self.go(kind="raid", name="Omar Reid")
        q = self.person("Omar Reid")
        self.assertEqual((q["email"], q["needs_details"]), (None, 1), "no email: marked Needs details, as the list does")

    def test_the_reply_names_the_new_person_so_the_page_can_say_so(self):
        """Mutation: leave the person out of the reply. The reply carries id and name only, never the email."""
        body = self.go(person={"name": "Zelda Quince", "email": "zq@example.org"})
        p = self.person("Zelda Quince")
        self.assertEqual(body["person"], {"id": p["id"], "name": "Zelda Quince"})
        self.assertNotIn("zq@example.org", str(body))

    def test_the_history_has_one_line_for_the_owner_and_the_person_is_in_the_people_history(self):
        """Mutation: a second line for owner_id (row 866 says one), or no line for the person."""
        body = self.go()
        lines = [e for e in history_module.rows_for_item(self.s.con, self.a) if e["step"] == body["apply_id"]]
        self.assertEqual(len(lines), 1, lines)
        self.assertEqual((lines[0]["from"], lines[0]["to"], lines[0]["field"], lines[0]["how"]), ("Sara Khan", "Zelda Quince", "Owner", "In the table"))
        p = self.person("Zelda Quince")
        mine = [e for e in self.s.history(p["id"]) if e["step"] == body["apply_id"]]
        self.assertTrue(mine, "the person's own history shows they were added, by the same step")

    def test_one_undo_takes_back_the_assignment_and_the_person_together(self):
        """Mutation: undo the owner but leave the person (or the reverse). Fixture: action owned by Sara Khan."""
        body = self.go()
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"], undone["skipped"]), (200, True, []), undone)
        row = self.s.read("actions", ref=self.a)
        self.assertEqual((row["owner"], row["owner_id"]), ("Sara Khan", None))
        self.assertIsNone(self.person("Zelda Quince"), "the person made by this step goes with it")
        self.assertEqual(self.s.people(archived=None), [])

    def test_the_undo_of_the_undo_brings_both_back_in_the_store(self):
        """The route refuses an undo of an undo (changes.NO_UNDO); the store's does both, once. Mutation: only one of the two returns."""
        step = self.go()["apply_id"]
        undo_step = self.undo({"project": "ABC", "apply_id": step})[1]["apply_id"]
        self.assertEqual(self.undo({"project": "ABC", "apply_id": undo_step})[0], 400)
        self.s.undo(undo_step, USER)
        p = self.person("Zelda Quince")
        row = self.s.read("actions", ref=self.a)
        self.assertEqual((row["owner"], row["owner_id"]), ("Zelda Quince", p["id"]))
        self.assertEqual(len([x for x in self.s.people(archived=None) if x["name"] == "Zelda Quince"]), 1)

    def test_undo_after_the_item_changed_later_does_not_strand_the_link(self):
        """Fixture: add, then someone else sets the owner. Mutation: the undo removes a person an item still points at."""
        step = self.go()["apply_id"]
        self.demo.update("actions", self.a, {"owner": "Mia Hale"})
        status, _ = self.undo({"project": "ABC", "apply_id": step})
        self.assertIn(status, (200, 409))
        row = self.s.read("actions", ref=self.a)
        self.assertEqual(row["owner"], "Mia Hale")
        ids = {p["id"] for p in self.s.people(archived=None)}
        self.assertTrue(row["owner_id"] is None or row["owner_id"] in ids, "owner_id never points at a person who is gone")

    def test_a_later_plain_owner_update_of_the_same_name_links_the_one_person(self):
        """The existing owner update (no new_person) on the name now on the list links to the one person (row 866). Needs the add first."""
        self.go()
        status, _ = self.change({"project": "ABC", "kind": "raid", "op": "update", "id": self.r, "changes": {"owner": "zelda quince"}, "place": "cell"})
        self.assertEqual(status, 200)
        self.assertEqual(len(self.s.people(archived=None)), 1)
        self.assertEqual(self.s.read("raid", ref=self.r)["owner_id"], self.person("Zelda Quince")["id"])


class Refusals(Base):
    def test_the_key_is_unknown_to_every_other_op(self):
        """new_person is accepted on the owner update only. Mutation: add it to OP_KEYS for all ops. (Green today for the wrong
        reason; stays green once built, and then pins that the key is not widened.)"""
        base = {"project": "ABC", "new_person": {"name": "Zelda Quince"}}
        for req in ({"kind": "actions", "op": "bulk", "ids": [self.a], "changes": {"owner": "Zelda Quince"}},
                    {"kind": "actions", "op": "handover", "ids": [self.a], "to": "Zelda Quince"},
                    {"kind": "report_sections", "op": "new", "values": {"title": "x"}},
                    {"kind": "actions", "op": "archive", "id": self.a}):
            with self.subTest(op=req["op"]):
                before = self.counts()
                status, body = self.change({**base, **req})
                self.assertEqual((status, body["ok"]), (400, False))
                self.assertEqual(self.counts(), before)

    def test_new_person_must_go_with_the_owner_field_and_the_same_name(self):
        """Mutation: add the person named in new_person but assign someone else, or add with no owner change, or with other fields.
        A good request is made first so this is red only for the right reason."""
        self.go(name="Probe Person")
        for label, req in (("other name", self.req("actions", "owner", "Zelda Quince", person={"name": "Omar Reid"})),
                           ("not the owner field", {**self.req("actions", "owner", "Zelda Quince"), "changes": {"priority": "High"}}),
                           ("no changes", {**self.req("actions", "owner", "Zelda Quince"), "changes": {}}),
                           ("owner and more", {**self.req("actions", "owner", "Zelda Quince"), "changes": {"owner": "Zelda Quince", "priority": "Urgent"}}),
                           ("movement place", {**self.req("milestones", "owner", "Zelda Quince"), "place": "movement"})):
            with self.subTest(label):
                self.refused(req)

    def test_hostile_names_are_refused_with_nothing_written(self):
        """Each hostile new_person.name, also sent as the owner value. Mutation: strip silently / truncate / store. Cases: empty,
        whitespace only, no-break and ideographic spaces, 121 characters, newline, NUL, lone surrogate, RTL override, zero width
        space, tab, ESC, DEL. A good add is made first so a red here is not just the unknown key."""
        self.go(name="Probe Person")
        bad = ["", "   ", "  　", "x" * 121, "Ana\nBob", "Ana\x00", "Ana\ud800", "‮Ana", "A​na", "Ana\tBob", "\x1b[31mAna", "Ana\x7f"]
        for kind, field in KINDS:
            for name in bad:
                with self.subTest(kind=kind, name=ascii(name[:12]) + str(len(name))):
                    self.refused(self.req(kind, field, name))

    def test_the_longest_allowed_name_is_taken_and_one_more_is_not(self):
        """120 characters is people_rules.NAME_MAX. Boundary on both sides."""
        ok = "N" * people_rules.NAME_MAX
        self.go(name=ok)
        self.refused(self.req("raid", "owner", ok + "x"))

    def test_spacing_alone_does_not_make_two_names(self):
        """Mutation: compare raw strings. 'Zelda  Quince' in changes and ' Zelda Quince' in new_person is the same name."""
        self.go(name="Zelda  Quince", person={"name": " Zelda Quince"})
        self.assertIsNotNone(self.person("Zelda Quince"))

    def test_markup_is_kept_as_the_words_typed_and_never_as_markup(self):
        """The owner text takes '<b>Ana</b>' as plain text today (test_changes). The person is the same text; nothing is stripped or
        escaped in the store. Mutation: strip tags (the name changes) or store HTML-escaped."""
        name = "<img src=x onerror=alert(1)>Ana & Co"
        self.go(name=name)
        self.assertEqual(self.person(name)["name"], name)
        self.assertEqual(self.s.read("actions", ref=self.a)["owner"], name)

    def test_a_bad_email_is_refused_in_the_lists_words_and_nothing_is_written(self):
        """Mutation: add the person without the email, or keep the owner change. A good add is made first."""
        self.go(name="Probe Person")
        for email in ("not an email", "a@b", "a@@b.co", "a,b@c.co", "x" * 300 + "@b.co", "a@b.co\n", "‮a@b.co"):
            with self.subTest(email=ascii(email[:20])):
                self.refused(self.req("actions", "owner", "Zelda Quince", person={"name": "Zelda Quince", "email": email}))

    def test_an_email_already_on_the_list_is_refused_naming_that_person(self):
        """The list holds one email per person. Mutation: add a second person with the same address."""
        with self.s.step("dashboard", USER) as st:
            st.add_person(name="Omar Reid", email="shared@example.org", source="test")
        body = self.refused(self.req("actions", "owner", "Zelda Quince", person={"name": "Zelda Quince", "email": "SHARED@example.org"}))
        self.assertIn("Omar Reid", body["message"])

    def test_the_shape_of_new_person_is_checked(self):
        """Not an object, no name, extra keys, wrong types: 400 in words, never a 500. Mutation: **person into add_person
        (a request could then set archived, id, source, aliases). A good add is made first."""
        self.go(name="Probe Person")
        for person in ("Zelda Quince", ["Zelda Quince"], 7, True, {}, {"name": None}, {"name": 5}, {"name": ["a"]},
                       {"name": "Zelda Quince", "email": 5}, {"name": "Zelda Quince", "archived": 1},
                       {"name": "Zelda Quince", "id": "P-001"}, {"name": "Zelda Quince", "source": "x"}, {"name": "Zelda Quince", "aliases": "tbc"}):
            with self.subTest(person=repr(person)):
                self.refused(self.req("actions", "owner", "Zelda Quince", person=person))

    def test_a_name_that_is_tbc_is_refused_it_is_the_clear_entry_not_a_person(self):
        """TBC/tbc/' Tbc ' (people.NO_PERSON). Mutation: create a person called TBC. Nothing is written. A good add is made first."""
        self.go(name="Probe Person")
        for name in ("TBC", "tbc", " Tbc ", "TBC "):
            for kind, field in KINDS:
                with self.subTest(kind=kind, name=ascii(name)):
                    self.refused(self.req(kind, field, name))

    def test_a_failed_add_leaves_no_person_behind(self):
        """HOSTILE CASE (the issue's): the person is valid but the item is not changeable. Mutation: create the person before the
        checks and not roll back. Fixture: a missing item, another project's request, an archived item. A good add is made first."""
        self.go(name="Probe Person")
        r = self.req("actions", "owner", "Zelda Quince")
        self.refused({**r, "id": "ABC-A-999"})
        self.refused({**r, "project": "XYZ"}, status=404)
        with self.s.step("dashboard", USER) as st:
            arch = st.create("actions", {"project": "ABC", "description": "Old", "raised": "2026-10-01", "source": "demo"})
            st.archive("actions", arch)
        self.refused({**r, "id": arch})
        self.assertEqual([p["name"] for p in self.s.people(archived=None)], ["Probe Person"])

    def test_a_store_error_after_the_person_was_added_rolls_the_whole_step_back(self):
        """Mutation: the person is committed first. The store's update of the item is made to fail after add_person ran."""
        self.go(name="Probe Person")
        with mock.patch.object(store_module.Step, "update", side_effect=store_module.Invalid("rule")):
            status, body = self.change(self.req("actions", "owner", "Zelda Quince"))
        self.assertEqual((status, body["ok"]), (400, False), body)
        self.assertIsNone(self.person("Zelda Quince"))
        self.assertEqual(self.s.read("actions", ref=self.a)["owner"], "Probe Person")


class Duplicates(Base):
    def person_on_list(self, name, **kw):
        with self.s.step("dashboard", USER) as st:
            return st.add_person(name=name, source="test", **kw)

    def test_a_name_already_on_the_list_is_refused_in_any_case_and_any_accent(self):
        """Matching is people.name_key (NFKC, casefold, squash, confusable skeleton), as the resolver does. The refusal carries the
        existing person (id, name) so the page can offer 'Use this one'. Mutation: compare raw strings; or silently link them."""
        pid = self.person_on_list("José Álvarez")
        for typed in ("José Álvarez", "jose alvarez", "JOSÉ ÁLVAREZ", "Jose  Alvarez", "  josé álvarez ", "Jоse Alvarez"):
            with self.subTest(typed=typed):
                body = self.refused(self.req("actions", "owner", typed), code="person_exists")
                self.assertEqual(body["person"], {"id": pid, "name": "José Álvarez"})
                self.assertIn("Use this one", body["message"])

    def test_an_alias_counts_as_the_same_person(self):
        """Mutation: look at names only."""
        pid = self.person_on_list("Margaret Ho", aliases="Maggie Ho")
        body = self.refused(self.req("raid", "owner", "MAGGIE HO"), code="person_exists")
        self.assertEqual(body["person"]["id"], pid)

    def test_an_archived_person_is_not_duplicated_the_refusal_says_restore(self):
        """people.resolve status 'archived'. Mutation: make a second live person with an archived one's name."""
        pid = self.person_on_list("Omar Reid")
        with self.s.step("dashboard", USER) as st:
            st.archive_person(pid)
        body = self.refused(self.req("actions", "owner", "omar reid"), code="person_archived")
        self.assertEqual(body["person"]["id"], pid)

    def test_two_people_already_with_that_name_are_refused_not_guessed(self):
        """Fixture: two live Sam Reeds (the list allows it). Mutation: link the first."""
        self.person_on_list("Sam Reed")
        self.person_on_list("Sam Reed", label="PMO")
        self.refused(self.req("actions", "owner", "sam reed"), code="person_exists")

    def test_the_second_add_of_a_name_is_refused_like_a_hand_made_person(self):
        """The 'second same name' of the issue: add Zelda, then add Zelda again (other item, other kind)."""
        self.go()
        body = self.refused(self.req("raid", "owner", "ZELDA QUINCE"), code="person_exists")
        self.assertEqual(body["person"]["name"], "Zelda Quince")
        self.assertEqual(len(self.s.people(archived=None)), 1)

    def test_two_creates_of_the_same_name_at_once_make_one_person_and_one_refusal(self):
        """Mutation: check outside the step's lock. 6 threads, 2 items. Exactly one 200, the rest person_exists; one person on the list."""
        results, gate = [], threading.Barrier(6)
        reqs = [self.req("actions", "owner", "Zelda Quince"), self.req("raid", "owner", "zelda quince")] * 3

        def go(r):
            gate.wait(10)
            results.append(self.change(r))
        threads = [threading.Thread(target=go, args=(r,)) for r in reqs]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        self.assertEqual(sorted(s for s, _ in results), [200, 400, 400, 400, 400, 400], results)
        self.assertEqual({b.get("code") for s, b in results if s == 400}, {"person_exists"})
        self.assertEqual(len([p for p in self.s.people(archived=None) if people_rules.name_key(p["name"]) == "zelda quince"]), 1)


class Clearing(Base):
    def test_the_clear_entry_stores_tbc_and_clears_owner_id(self):
        """"TBC (no one yet)" sends owner = "TBC" (the stored value stays TBC; no new key). Pin: owner_id goes to None, no person is
        made, one step, one Undo that puts the person's link back. Mutation: store '' or 'TBC (no one yet)', or leave owner_id.
        The setup needs the add, so this is red until the build."""
        self.go()
        p = self.person("Zelda Quince")
        before = self.counts()
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": self.a, "changes": {"owner": "TBC"}, "place": "cell"})
        self.assertEqual((status, body["ok"]), (200, True), body)
        row = self.s.read("actions", ref=self.a)
        self.assertEqual((row["owner"], row["owner_id"]), ("TBC", None))
        self.assertEqual((self.counts()[0], self.counts()[2]), (before[0] + 1, before[2]), "one step, no person made or lost")
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        row = self.s.read("actions", ref=self.a)
        self.assertEqual((row["owner"], row["owner_id"]), ("Zelda Quince", p["id"]))

    def test_the_words_of_the_clear_entry_are_not_a_name_to_store(self):
        """'TBC (no one yet)' is the page's label; the store holds TBC. Sent as a new person it is refused (code not_a_name), and
        it never resolves to a person. Mutation: store the display words as a name."""
        self.assertEqual(people_rules.resolve("TBC (no one yet)", self.s.people(archived=None))["status"], "none")
        self.refused(self.req("actions", "owner", "TBC (no one yet)"), code="not_a_name")

    def test_a_plain_tbc_update_reads_tbc_in_history(self):
        """Pin of 'check nothing downstream changes': history shows TBC verbatim, never the picker's words."""
        self.demo.update("raid", self.r, {"owner": "Mia Hale"})     # a new risk starts as TBC already, so there is a change to read
        status, body = self.change({"project": "ABC", "kind": "raid", "op": "update", "id": self.r, "changes": {"owner": "TBC"}, "place": "cell"})
        self.assertEqual(status, 200)
        line = [e for e in self.s.history(self.r) if e["step"] == body["apply_id"]]
        self.assertTrue(line and all("no one yet" not in str(e) for e in line))
        self.assertEqual(self.s.read("raid", ref=self.r)["owner"], "TBC")


class Lows(Base):
    def test_any_case_accent_or_space_variant_of_the_clear_entry_is_refused(self):
        """Row 986 follow-up: the clear entry is matched by the people key, not by exact text. Mutation: compare name == CLEAR_ENTRY."""
        for word in ("tbc (No one yet)", "TBC (NO ONE YET)", "Tbc  (no   one yet)", "TBC (no onê yet)", "tbc (no one yet) "):
            for kind, field in KINDS:
                with self.subTest(word=word, kind=kind):
                    self.refused(self.req(kind, field, word))
        self.assertEqual(self.go(name="Zelda Quince")["person"]["name"], "Zelda Quince")

    def _boom(self, exc):
        def add(self_, **fields):
            raise exc
        return mock.patch.object(store_module.Step, "add_person", add)

    def test_a_value_error_from_add_person_is_a_plain_refusal(self):
        """P-999 used up: ValueError out of add_person is a plain Refused, no 500, nothing changed. Mutation: catch only Invalid."""
        with self._boom(ValueError("no more ids")):
            for kind, field in KINDS:
                with self.subTest(kind=kind):
                    body = self.refused(self.req(kind, field, "Zelda Quince"))
                    self.assertEqual(body["message"], changes.NEW_PERSON_BAD)
        self.assertIsNone(self.person("Zelda Quince"))

    def test_an_invalid_from_add_person_is_a_plain_refusal(self):
        """Mutation: catch only ValueError."""
        with self._boom(store_module.Invalid("rule")):
            for kind, field in KINDS:
                with self.subTest(kind=kind):
                    body = self.refused(self.req(kind, field, "Zelda Quince"))
                    self.assertEqual(body["message"], changes.NEW_PERSON_BAD)


if __name__ == "__main__":
    unittest.main()

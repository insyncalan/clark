"""#199: Hand over, a change of owner for work items of all three kinds together, in one step with one Undo (clark.changes, op "handover").

Run: python3 dev/run_tests.py test_changes_hand_over
Pure Python over a real demo store (fictional data): one step and one Undo for actions, risks and decisions together, one history
line per item, items that can't take it left out and named, the confirm above 25, the people list's rule for who can take them,
and hostile requests refused with nothing written. Hand over goes through the same writer as the bulk change (#196).
"""
import json
import re
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC
from clark import changes, server as sv
from clark import store as clark_store

OWNER = "Ada Quillfeather"
NEW = "Zelda Quince"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.actions = [self.demo.action(owner=OWNER) for _ in range(2)]
        with self.s.step("dashboard", USER) as st:
            self.risks = [st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier late", "impact": "Low",
                                             "likelihood": "Low", "raised": "2026-10-01", "owner": OWNER, "source": "demo"})]
            self.decisions = [st.create("decisions", {"project": "ABC", "decision": "Go", "made_by": OWNER,
                                                      "status": "Pending", "source": "demo"})]
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        self.all = self.actions + self.risks + self.decisions

    def send(self, ids, to=NEW, **more):
        return self.change({"project": "ABC", "kind": "actions", "op": "handover", "ids": ids, "to": to, **more})

    def counts(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM applies), (SELECT count(*) FROM change_log), "
                               "(SELECT count(*) FROM item_events)").fetchone()
        finally:
            con.close()

    def who(self, ref):
        table = clark_store.item_table(ref)
        return self.s.read(table, ref=ref)[changes.HAND_OVER_FIELD[table]]

    def refused(self, ids, words, status=400, to=NEW, **more):
        before = self.counts()
        got, body = self.send(ids, to, **more)
        self.assertEqual((got, body["ok"], body["message"]), (status, False, words), body)
        self.assertEqual(self.counts(), before, "nothing was written")
        return body


class HandOver(Base):
    def test_actions_a_risk_and_a_decision_move_in_one_step_with_one_history_line_each(self):
        before = self.counts()[0]
        status, body = self.send(self.all)
        self.assertEqual((status, body["ok"], body["changed"], body["left_out"], body["unchanged"]), (200, True, self.all, [], []), body)
        self.assertEqual((self.counts()[0], body["undoable"], body["words"]), (before + 1, True, "Changed 4 items."))
        for ref in self.all:
            self.assertEqual(self.who(ref), NEW, ref)
            line = [e for e in self.s.history(ref) if e["step"] == body["apply_id"]]
            self.assertEqual(len(line), 1, ref)
            self.assertEqual((line[0]["before"], line[0]["after"], line[0]["place"], line[0]["by_user"]), (OWNER, NEW, "bulk", USER))
        self.assertEqual({i["id"] for i in body["items"]}, set(self.all))

    def test_one_undo_puts_every_owner_back(self):
        _, body = self.send(self.all)
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"], undone["skipped"]), (200, True, []), undone)
        self.assertEqual({self.who(r) for r in self.all}, {OWNER})

    def test_only_the_owner_changes_on_every_kind(self):
        before = {ref: self.s.read(clark_store.item_table(ref), ref=ref) for ref in self.all}
        self.send(self.all)
        for ref, row in before.items():
            with self.subTest(ref=ref):
                table = clark_store.item_table(ref)
                now = self.s.read(table, ref=ref)
                skip = (changes.HAND_OVER_FIELD[table], "updated_at")
                self.assertEqual({k: v for k, v in now.items() if k not in skip}, {k: v for k, v in row.items() if k not in skip})

    def test_items_that_cannot_take_it_are_left_out_and_named(self):
        archived = self.demo.action()
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", archived)
        gone = "ABC-A-900"
        status, body = self.send(self.all + [archived, gone])
        self.assertEqual((status, body["changed"]), (200, self.all), body)
        self.assertEqual(body["left_out"], [{"id": archived, "why": changes.BULK_ARCHIVED}, {"id": gone, "why": changes.BULK_GONE}])
        self.assertIn(f"Left out {archived}: {changes.BULK_ARCHIVED}", body["words"])
        self.assertEqual(self.s.read("actions", ref=archived)["owner"], "TBC")

    def test_nothing_saves_when_none_can_take_it_or_they_have_it_already(self):
        self.refused(["ABC-A-900"], changes.BULK_GONE)
        self.send(self.all)
        before = self.counts()
        status, body = self.send(self.all)
        self.assertEqual((status, body["apply_id"], body["changed"], body["unchanged"], body["words"]), (200, None, [], self.all, changes.BULK_ALREADY))
        self.assertEqual(self.counts(), before)

    def test_a_refusal_in_the_real_step_leaves_every_item_as_it_was(self):
        """#317: the refusal is aimed at one named item (the last one asked for) in the real step, not at the Nth write, and what
        is asserted is the outcome: the answer, the counts and every owner as it was. Items before it were written inside the
        step, so the test only means something if they are rolled back."""
        real_step, real_update = type(self.s).step, clark_store.Step.update
        aim = self.all[-1]
        state = {"real": False, "written": [], "refused": False}

        def step(store, *a, **kw):                                  # mark when the real (not dry) step starts
            state["real"] = not kw.get("dry")
            return real_step(store, *a, **kw)

        def update(st, kind, ref, changes_, **kw):
            if state["real"]:
                if ref == aim:
                    state["refused"] = True
                    raise clark_store.Invalid("owner must be one of nobody")
                state["written"].append(ref)
            return real_update(st, kind, ref, changes_, **kw)
        before = self.counts()
        with mock.patch.object(type(self.s), "step", step), mock.patch.object(clark_store.Step, "update", update):
            status, body = self.send(self.all)
        self.assertTrue(state["refused"], "the refusal came in the real step, on the item aimed at")
        self.assertTrue(set(state["written"]) & set(self.all[:-1]), "other items were written in that step before the refusal")
        self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.STALE), body)
        self.assertEqual(self.counts(), before, "no step, no history line, nothing written")
        self.assertEqual({ref: self.who(ref) for ref in self.all}, {ref: OWNER for ref in self.all})

    def test_an_item_closed_or_decided_between_the_trial_and_the_write_rolls_the_whole_step_back(self):
        for table, ref, sql in (("decisions", self.decisions[0], "UPDATE decisions SET status = 'Made', date = '2026-10-01' WHERE id = ?"),
                                ("actions", self.actions[1], "UPDATE actions SET status = 'Closed' WHERE id = ?")):
            with self.subTest(table=table):
                cls = type(self.s)
                real = cls.step

                def second_connection(store, *a, **kw):
                    if not kw.get("dry"):                           # the trial is over: another connection changes a status
                        con = sqlite3.connect(str(self.s.path))
                        try:
                            con.execute(sql, (ref,))
                            con.commit()
                        finally:
                            con.close()
                    return real(store, *a, **kw)
                before = self.counts()
                with mock.patch.object(cls, "step", second_connection):
                    status, body = self.send(self.all)
                self.assertEqual((status, body["message"]), (400, changes.STALE), body)
                self.assertEqual(self.counts()[:1], before[:1], "no step")
                self.assertEqual({self.who(r) for r in self.all}, {OWNER}, "no owner changed")
                con = sqlite3.connect(str(self.s.path))
                try:
                    con.execute(f"UPDATE {table} SET status = ?, date = NULL WHERE id = ?" if table == "decisions" else
                                f"UPDATE {table} SET status = ? WHERE id = ?", ("Pending" if table == "decisions" else "Open", ref))
                    con.commit()
                finally:
                    con.close()

    def test_closed_items_and_decisions_made_or_withdrawn_are_left_out_and_named(self):
        for status in changes.HAND_OVER_DONE:
            with self.subTest(status=status):
                if status in ("Closed", "Cancelled"):
                    ref = self.demo.action(owner=OWNER)
                    self.demo.update("actions", ref, {"status": status})
                    why = changes.BULK_CLOSED
                else:
                    ref = self.decisions[0]
                    self.demo.update("decisions", ref, {"status": status, **({"date": "2026-10-01"} if status == "Made" else {})})
                    why = changes.BULK_DECIDED
                before = self.counts()
                got, body = self.send([ref])
                self.assertEqual((got, body["code"], body["left_out"]), (400, "none_can", [{"id": ref, "why": why}]), body)
                self.assertEqual(self.counts(), before)
                self.assertEqual(self.who(ref), OWNER, "the owner stays as recorded")
                got, body = self.send([ref] + self.risks)
                self.assertEqual((got, body["changed"], body["left_out"]), (200, self.risks, [{"id": ref, "why": why}]), body)
                self.assertEqual(self.who(ref), OWNER)
                self.undo({"project": "ABC", "apply_id": body["apply_id"]})

    def test_the_closed_list_is_the_pages(self):
        text = (SRC / "clark" / "page" / "src" / "workItems.js").read_text(encoding="utf-8")
        page = re.search(r"const CLOSED = \[([^\]]*)\]", text).group(1)
        self.assertEqual(set(re.findall(r'"([^"]+)"', page)), set(changes.HAND_OVER_DONE))

    def test_hostile_requests_write_nothing(self):
        many = [f"ABC-A-{i % 999 + 1:03d}" for i in range(changes.MAX_BULK + 1)]
        for ids, words in (([], changes.BULK_NOTHING), ("ABC-A-001", changes.BULK_NOTHING), (None, changes.BULK_NOTHING),
                           (many, changes.BULK_TOO_MANY), ([1], changes.ITEM_NOT_MINE), (["ABC-A-001; DROP TABLE actions"], changes.ITEM_NOT_MINE),
                           (["ABC-W-001"], changes.ITEM_NOT_MINE), (["ABC-M-001"], changes.ITEM_NOT_MINE), (["XYZ-A-001"], changes.BULK_PROJECTS),
                           (["ABC-A-١٢٣"], changes.ITEM_NOT_MINE)):
            with self.subTest(ids=str(ids)[:40]):
                self.refused(ids, words)
        for to, words in ((None, changes.ITEM_VALUE_WORDS), ("", changes.ITEM_VALUE_WORDS), ("  ", changes.ITEM_VALUE_WORDS),
                          ("A\nB", changes.ITEM_TEXT_WORDS), ("A​B", changes.ITEM_TEXT_WORDS), ("x" * 201, changes.ITEM_VALUE_WORDS),
                          (3, changes.ITEM_VALUE_WORDS), (["Z"], changes.ITEM_VALUE_WORDS)):
            with self.subTest(to=str(to)[:20]):
                self.refused(self.all, words, to=to)
        self.refused(self.all, changes.BULK_CONFIRM, confirm="yes")
        before = self.counts()
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "handover", "ids": self.all, "to": "Z", "changes": {"status": "Closed"}})
        self.assertEqual((status, body["message"]), (400, "That change doesn't take 'changes'."))
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "handover", "ids": self.all, "to": "Z", "place": "cell"})
        self.assertEqual((status, body["ok"]), (200, True), "a place the page has is taken")
        self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        before = self.counts()
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "handover", "ids": self.all, "to": "Z", "place": "excel"})
        self.assertEqual((status, body["message"]), (400, changes.BAD_PLACE))
        for kind in ("milestones", "use_cases", "report_sections", "projects", "report_hidden", "glance_tiles"):
            with self.subTest(kind=kind):
                status, body = self.change({"project": "ABC", "kind": kind, "op": "handover", "ids": self.all, "to": "Z"})
                self.assertEqual((status, body["message"]), (400, changes.BAD_OP))
        self.assertEqual(self.counts(), before)

    def test_an_archived_project_changes_nothing(self):
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        self.refused(self.all, changes.PROJECT_NOT_ACTIVE)

    def test_the_confirm_counts_the_whole_request_at_25_and_26(self):
        more = self.actions + [self.demo.action(owner=OWNER) for _ in range(23)]
        self.assertEqual(len(more), 25)
        status, body = self.send(more)
        self.assertEqual((status, len(body["changed"])), (200, 25), "25 needs no confirm")
        more.append(self.risks[0])
        body = self.refused(more, "Change 26 items?", status=409, to=OWNER)
        self.assertEqual((body["code"], body["count"]), ("confirm", 26))
        body = self.refused(more + [more[0]], "Change 26 items?", status=409, to=OWNER)     # a duplicate counts once
        status, body = self.send(more, OWNER, confirm=True)
        self.assertEqual((status, len(body["changed"]), body["unchanged"]), (200, 25, self.risks), body)     # the risk had that owner already

    def test_the_largest_request_fits_the_routes_body_limit(self):
        req = {"project": "ABCDEFG", "kind": "actions", "op": "handover", "ids": ["ABCDEFG-A-999"] * changes.MAX_BULK,
               "to": "x" * 200, "confirm": True, "place": "bulk"}
        self.assertLess(len(json.dumps(req).encode()), sv.ROUTE_BODY_LIMITS["/api/change"])

    def test_a_bulk_change_still_takes_one_kind_and_keeps_its_own_checks(self):
        status, body = self.change({"project": "ABC", "kind": "actions", "op": "bulk", "ids": self.all, "changes": {"owner": NEW}})
        self.assertEqual((status, body["message"]), (400, changes.BULK_KINDS))
        self.demo.update("decisions", self.decisions[0], {"status": "Made", "date": "2026-10-01"})
        status, body = self.change({"project": "ABC", "kind": "decisions", "op": "bulk", "ids": self.decisions, "changes": {"made_by": NEW}})
        self.assertEqual((status, body["left_out"]), (400, [{"id": self.decisions[0], "why": changes.BULK_DECIDED}]), body)


class PeopleList(Base):
    """Who can take the items: once the people list has anyone on it, a name on that list (#115's one resolver), written as the
    list has it. With no one on the list yet, any name, as a single owner change takes."""

    def person(self, name, **more):
        with self.s.step("dashboard", USER) as st:
            return st.add_person(name=name, source="People list", **more)

    def test_with_no_one_on_the_list_any_name_is_taken(self):
        self.assertEqual(self.s.people(archived=None), [])
        status, body = self.send(self.all, "Someone New")
        self.assertEqual((status, body["changed"]), (200, self.all), body)
        self.assertEqual({self.who(r) for r in self.all}, {"Someone New"})
        self.assertEqual({self.s.read(clark_store.item_table(r), ref=r)["owner_id"] for r in self.all}, {None}, "free text has no person id")

    def test_a_name_on_the_list_is_written_as_the_list_has_it(self):
        self.person(NEW)
        status, body = self.send(self.all, "  zelda   QUINCE ")
        self.assertEqual((status, body["changed"]), (200, self.all), body)
        self.assertEqual({self.who(r) for r in self.all}, {NEW})

    def test_an_alias_on_the_list_is_the_person(self):
        self.person(NEW, aliases="ZQ")
        status, body = self.send(self.all, "ZQ")
        self.assertEqual((status, {self.who(r) for r in self.all}), (200, {NEW}), body)

    def linked(self, ref):
        """The stored people-table link beside an item's owner text (#115)."""
        return self.s.read(clark_store.item_table(ref), ref=ref)["owner_id"]

    def test_a_hand_over_sets_the_owners_id_on_every_kind_in_the_same_step(self):
        pid = self.person(NEW)
        old = self.person(OWNER)
        with self.s.step("dashboard", USER) as st:                  # the items start linked to the person who has them now
            for ref in self.all:
                st.update(clark_store.item_table(ref), ref, {"owner_id": old})
        status, body = self.send(self.all, "zelda quince")
        self.assertEqual((status, body["changed"]), (200, self.all), body)
        self.assertEqual({self.linked(r) for r in self.all}, {pid}, "the id of the person it names, on an action, a risk and a decision")
        self.assertEqual({self.who(r) for r in self.all}, {NEW})
        con = sqlite3.connect(str(self.s.path))
        try:
            steps = con.execute("SELECT count(DISTINCT apply_id) FROM change_log WHERE field = 'owner_id' AND apply_id = ?",
                                (body["apply_id"],)).fetchone()[0]
        finally:
            con.close()
        self.assertEqual(steps, 1, "the id is written in the hand over's own step")

    def test_one_undo_puts_back_the_owner_and_its_id_together(self):
        old = self.person(OWNER)
        pid = self.person(NEW)
        with self.s.step("dashboard", USER) as st:
            for ref in self.all:
                st.update(clark_store.item_table(ref), ref, {"owner_id": old})
        _, body = self.send(self.all)
        self.assertEqual({self.linked(r) for r in self.all}, {pid})
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        self.assertEqual(len(undone["reversed"]), len(self.all), "one line for each item: the link goes back with its owner")
        self.assertNotIn("owner_id", {e["field"] for e in undone["reversed"]})
        self.assertEqual({self.who(r) for r in self.all}, {OWNER})
        self.assertEqual({self.linked(r) for r in self.all}, {old}, "the old link is back with the old name")

    def test_a_link_changed_alone_is_not_undone_from_here(self):
        """The Undo takes the id only beside its owner text, in the same step of the same item (#199): a step that changes the link
        alone is not the page's to undo."""
        pid = self.person(NEW)
        with self.s.step("dashboard", USER) as st:
            st.update("actions", self.actions[0], {"owner_id": pid})
        con = sqlite3.connect(str(self.s.path))
        try:
            apply_id = con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]
        finally:
            con.close()
        status, body = self.undo({"project": "ABC", "apply_id": apply_id})
        self.assertEqual((status, body["ok"], body["message"]), (400, False, changes.NO_UNDO), body)

    def test_an_undo_after_the_owner_was_edited_by_hand_keeps_the_new_name_and_its_link(self):
        """Ada has it, it goes to Bob, then the owner is typed over as Cara Free. The Undo must not put Ada's link back beside Cara
        Free: the owner and its link go back together or not at all (#199)."""
        ada, bob = self.person(OWNER), self.person(NEW)
        ref = self.actions[0]
        with self.s.step("dashboard", USER) as st:
            st.update("actions", ref, {"owner_id": ada})
        _, body = self.send([ref])
        self.assertEqual((self.who(ref), self.linked(ref)), (NEW, bob))
        status, edited = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": ref, "changes": {"owner": "Cara Free"}})
        self.assertEqual((status, edited["ok"]), (200, True), edited)
        before = self.counts()
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"], undone["message"]), (409, False, changes.HAND_OVER_CHANGED), undone)
        self.assertEqual((self.who(ref), self.linked(ref)), ("Cara Free", None), "the name stays, and no old link is put back beside it")
        self.assertEqual(self.counts(), before, "nothing was written")

    def test_a_hand_over_whose_only_item_was_edited_is_all_skipped_in_an_undo_of_several(self):
        """One item, edited by hand: nothing goes back, and the preview names that item once with the plain reason (#620)."""
        ada, bob = self.person(OWNER), self.person(NEW)
        ref = self.actions[0]
        with self.s.step("dashboard", USER) as st:
            st.update("actions", ref, {"owner_id": ada})
        _, body = self.send([ref])
        self.change({"project": "ABC", "kind": "actions", "op": "update", "id": ref, "changes": {"owner": "Cara Free"}})
        before = self.counts()
        status, undone = self.undo({"project": "ABC", "steps": [body["apply_id"]], "preview": True})
        self.assertEqual(status, 200, undone)
        self.assertEqual([(x["ref"], x["why"]) for x in undone["skipped"]], [(ref, changes.CHANGED_SINCE)], undone)
        self.assertEqual(undone["undo"], [])
        self.assertEqual((self.who(ref), self.linked(ref)), ("Cara Free", None))
        self.assertEqual(self.counts(), before, "a preview writes nothing")

    def three_handed(self):
        """Three actions each linked to Ada, handed to Bob in one step; the owner of the middle one is then typed over as Cara Free."""
        ada, bob = self.person(OWNER), self.person(NEW)
        refs = self.actions + [self.demo.action(owner=OWNER)]
        with self.s.step("dashboard", USER) as st:
            for ref in refs:
                st.update("actions", ref, {"owner_id": ada})
        _, body = self.send(refs)
        self.assertEqual((body["ok"], body["changed"]), (True, refs), body)
        edited = refs[1]
        status, got = self.change({"project": "ABC", "kind": "actions", "op": "update", "id": edited, "changes": {"owner": "Cara Free"}})
        self.assertEqual((status, got["ok"]), (200, True), got)
        return ada, bob, refs, edited, body["apply_id"]

    def test_an_undo_of_a_hand_over_skips_only_the_owner_that_changed_and_undoes_the_rest(self):
        """Three items handed over, one owner then edited by hand: one Undo puts the other two back (owner and link together) and leaves
        the edited one, its text and its link, alone. Nothing is written for it, and the reply says so once (#620)."""
        ada, bob, refs, edited, apply_id = self.three_handed()
        others = [r for r in refs if r != edited]
        status, undone = self.undo({"project": "ABC", "apply_id": apply_id})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        for ref in others:
            self.assertEqual((self.who(ref), self.linked(ref)), (OWNER, ada), "owner and link are both back")
        self.assertEqual((self.who(edited), self.linked(edited)), ("Cara Free", None), "its text and its link are left as they are")
        self.assertEqual(sorted(e["ref"] for e in undone["reversed"]), sorted(others), "one line for each item put back")
        self.assertEqual({e["field"] for e in undone["reversed"]}, {"owner"})
        self.assertEqual([(x["ref"], x["field"], x["why"]) for x in undone["skipped"]], [(edited, "owner", changes.CHANGED_LATER)],
                         "one line for the one item left as it is, the link not named separately")
        self.assertIn("changed later", undone["words"])
        self.assertNotIn(edited, {r["key"] for r in self.s.step_rows(undone["apply_id"])}, "nothing is written for the item that was left")
        self.assertEqual(len([r for r in self.s.step_rows(undone["apply_id"]) if r["field"] == "owner_id"]), 2)

    def test_the_link_of_a_skipped_owner_is_never_put_back_alone(self):
        """The store's own rule, below the page's checks: an owner_id rides with its owner text, so when the text is skipped as
        changed since, the link is skipped with the same reason and the same later step (#620)."""
        ada, bob, refs, edited, apply_id = self.three_handed()
        done = self.s.undo(apply_id, USER)
        skipped = [(x["ref"], x["field"], x["why"]) for x in done["skipped"]]
        self.assertEqual({(r, f) for r, f, _ in skipped}, {(edited, "owner"), (edited, "owner_id")}, done)
        self.assertEqual({w for _, _, w in skipped}, {"has changed since: left as it is"})
        self.assertEqual(len({x["by_step"] for x in done["skipped"]}), 1)
        self.assertIsNotNone(done["skipped"][0]["by_step"])
        self.assertNotIn(edited, {x["ref"] for x in done["reversed"]})
        self.assertEqual(self.linked(edited), None)

    def test_an_undo_of_several_skips_the_edited_item_and_undoes_the_others(self):
        ada, bob, refs, edited, apply_id = self.three_handed()
        others = [r for r in refs if r != edited]
        status, undone = self.undo({"project": "ABC", "steps": [apply_id], "preview": True})
        self.assertEqual(status, 200, undone)
        self.assertEqual(sorted(x["ref"] for x in undone["undo"]), sorted(others), undone)
        self.assertEqual([(x["ref"], x["why"]) for x in undone["skipped"]], [(edited, changes.CHANGED_SINCE)], undone)
        self.assertEqual((self.who(edited), self.linked(edited)), ("Cara Free", None), "a preview changes nothing")
        status, done = self.undo({"project": "ABC", "steps": [apply_id]})
        self.assertEqual(status, 200, done)
        self.assertEqual([(self.who(r), self.linked(r)) for r in others], [(OWNER, ada)] * 2)
        self.assertEqual((self.who(edited), self.linked(edited)), ("Cara Free", None))

    def test_the_activity_tick_stays_for_a_hand_over_with_one_item_left_to_undo(self):
        ada, bob, refs, edited, apply_id = self.three_handed()
        self.assertEqual(changes.undo_refusals(self.s, "ABC", {apply_id}), {}, "two of the three can still go back")

    def test_the_activity_tick_is_withheld_when_every_item_was_edited(self):
        ada, bob = self.person(OWNER), self.person(NEW)
        refs = self.actions
        with self.s.step("dashboard", USER) as st:
            for ref in refs:
                st.update("actions", ref, {"owner_id": ada})
        _, body = self.send(refs)
        for ref in refs:
            self.change({"project": "ABC", "kind": "actions", "op": "update", "id": ref, "changes": {"owner": "Cara Free"}})
        self.assertEqual(changes.undo_refusals(self.s, "ABC", {body["apply_id"]}), {body["apply_id"]: changes.CHANGED_SINCE})

    def test_a_link_only_item_whose_name_was_edited_still_leaves_the_whole_hand_over(self):
        """A link-only item has no owner text row, so the store has no name to judge it by: its step stays whole (fails safe)."""
        ada, bob = self.person(OWNER), self.person(NEW)
        first, second = self.actions
        with self.s.step("dashboard", USER) as st:
            st.update("actions", first, {"owner": NEW})
            st.update("actions", second, {"owner_id": ada})
        _, body = self.send([first, second])
        self.change({"project": "ABC", "kind": "actions", "op": "update", "id": first, "changes": {"owner": "Cara Free"}})
        before = self.counts()
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["message"]), (409, changes.HAND_OVER_CHANGED), undone)
        self.assertEqual(self.counts(), before)
        self.assertEqual(changes.undo_refusals(self.s, "ABC", {body["apply_id"]}), {body["apply_id"]: changes.CHANGED_SINCE})

    def test_a_link_only_hand_over_is_undone_and_only_the_link_goes_back(self):
        """The owner text already reads the person's name, so only the link changes (#199): its Undo is offered and restores the link."""
        bob = self.person(NEW)
        ref = self.actions[0]
        with self.s.step("dashboard", USER) as st:
            st.update("actions", ref, {"owner": NEW})
        _, body = self.send([ref])
        self.assertEqual((body["ok"], body["changed"], self.linked(ref)), (True, [ref], bob), body)
        self.assertEqual([e["field"] for e in self.s.history(ref) if e["step"] == body["apply_id"]], ["owner_id"], "only the link changed")
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        self.assertEqual((self.who(ref), self.linked(ref)), (NEW, None), "the name is as it was; the link is back to none")

    def test_a_link_only_hand_over_is_not_undone_once_the_name_was_edited(self):
        bob = self.person(NEW)
        ref = self.actions[0]
        with self.s.step("dashboard", USER) as st:
            st.update("actions", ref, {"owner": NEW})
        _, body = self.send([ref])
        self.change({"project": "ABC", "kind": "actions", "op": "update", "id": ref, "changes": {"owner": "Cara Free"}})
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, undone["message"]), (409, changes.HAND_OVER_CHANGED), undone)
        self.assertEqual((self.who(ref), self.linked(ref)), ("Cara Free", None))

    def test_free_text_writes_no_id_and_clears_an_old_one(self):
        old = self.person(OWNER)
        with self.s.step("dashboard", USER) as st:
            for ref in self.all:
                st.update(clark_store.item_table(ref), ref, {"owner_id": old})
        with self.s.step("dashboard", USER) as st:                  # no live person left on the list: a free name is taken, as with an empty list
            st.archive_person(old)
        status, body = self.send(self.all, "Someone New")
        self.assertEqual((status, body["changed"]), (200, self.all), body)
        self.assertEqual({self.who(r) for r in self.all}, {"Someone New"})
        self.assertEqual({self.linked(r) for r in self.all}, {None}, "the old person's id does not stay on an item handed to free text")

    def test_a_name_not_on_the_list_is_refused_in_plain_words(self):
        self.person(NEW)
        self.refused(self.all, changes.HAND_OVER_UNKNOWN, to="Zelda Quinse")
        self.assertEqual({self.who(r) for r in self.all}, {OWNER})

    def test_a_name_two_people_share_is_refused(self):
        self.person(NEW, label="Harbour team")
        self.person(NEW, label="Quay team")
        self.refused(self.all, changes.HAND_OVER_MANY)

    def test_an_archived_person_is_refused(self):
        self.person("Someone Else")
        ref = self.person(NEW)
        with self.s.step("dashboard", USER) as st:
            st.archive_person(ref)
        self.refused(self.all, changes.HAND_OVER_ARCHIVED)

    def test_no_one_is_refused(self):
        for to in ("TBC", "tbc"):
            with self.subTest(to=to):
                self.refused(self.all, changes.HAND_OVER_NOBODY, to=to)
        self.person(NEW)
        self.refused(self.all, changes.HAND_OVER_NOBODY, to="TBC")

    def test_the_words_are_plain(self):
        for words in (changes.HAND_OVER_UNKNOWN, changes.HAND_OVER_MANY, changes.HAND_OVER_ARCHIVED, changes.HAND_OVER_NOBODY, changes.BULK_CLOSED):
            self.assertTrue(words.endswith("."), words)
            self.assertNotRegex(words, r"[_{}<>]|\bid\b|owner_id|resolve", words)


class SingleEdit(Base):
    """Row 866: a single owner edit on a work item writes the person link beside the text, so a later rename keeps the edit."""

    def edit(self, ref, who, field="owner"):
        kind = clark_store.item_table(ref)
        got, body = self.change({"project": "ABC", "kind": kind, "op": "update", "id": ref, "changes": {field: who}})
        self.assertEqual(got, 200, body)

    def test_an_edited_owner_survives_a_rename_of_the_old_person(self):
        with self.s.step("dashboard", USER) as st:
            old = st.add_person(name=OWNER, source="People list")
            new = st.add_person(name=NEW, source="People list")
            st.update("actions", self.actions[0], {"owner_id": old})
            st.update("decisions", self.decisions[0], {"owner_id": old})
        self.edit(self.actions[0], NEW)
        self.edit(self.decisions[0], NEW, "made_by")
        self.assertEqual(self.s.read("actions", ref=self.actions[0])["owner_id"], new)
        self.assertEqual(self.s.read("decisions", ref=self.decisions[0])["owner_id"], new)
        with self.s.step("dashboard", USER) as st:
            st.rename_person(old, "Ada Renamed")
        self.assertEqual(self.who(self.actions[0]), NEW)
        self.assertEqual(self.who(self.decisions[0]), NEW)

    def test_free_text_clears_the_link(self):
        with self.s.step("dashboard", USER) as st:
            old = st.add_person(name=OWNER, source="People list")
            st.update("actions", self.actions[0], {"owner_id": old})
        self.edit(self.actions[0], "Someone Unlisted")
        self.assertIsNone(self.s.read("actions", ref=self.actions[0])["owner_id"])
        with self.s.step("dashboard", USER) as st:
            st.rename_person(old, "Ada Renamed")
        self.assertEqual(self.who(self.actions[0]), "Someone Unlisted")


if __name__ == "__main__":
    unittest.main()

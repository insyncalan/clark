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
        real_step, real_update = type(self.s).step, clark_store.Step.update
        state = {"real": False, "writes": 0}

        def step(store, *a, **kw):                                  # mark when the real (not dry) step starts
            state["real"] = not kw.get("dry")
            return real_step(store, *a, **kw)

        def update(st, kind, ref, changes_, **kw):
            if state["real"]:
                state["writes"] += 1
                if state["writes"] == 2:                            # the second write of the real step, whatever came before it
                    raise clark_store.Invalid("owner must be one of nobody")
            return real_update(st, kind, ref, changes_, **kw)
        before = self.counts()
        with mock.patch.object(type(self.s), "step", step), mock.patch.object(clark_store.Step, "update", update):
            status, body = self.send(self.all)
        self.assertEqual(state["writes"], 2, "the refusal came in the real step")
        self.assertEqual((status, body["message"]), (400, changes.STALE), body)
        self.assertEqual(self.counts(), before, "no step, no history line, nothing written")
        self.assertEqual({self.who(r) for r in self.all}, {OWNER})

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

    def test_a_name_on_the_list_is_written_as_the_list_has_it(self):
        self.person(NEW)
        status, body = self.send(self.all, "  zelda   QUINCE ")
        self.assertEqual((status, body["changed"]), (200, self.all), body)
        self.assertEqual({self.who(r) for r in self.all}, {NEW})

    def test_an_alias_on_the_list_is_the_person(self):
        self.person(NEW, aliases="ZQ")
        status, body = self.send(self.all, "ZQ")
        self.assertEqual((status, {self.who(r) for r in self.all}), (200, {NEW}), body)

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


if __name__ == "__main__":
    unittest.main()

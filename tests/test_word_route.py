"""#48 (guarded): the Word routes' logic (src/clark/word_route.py) on a real store, and the server's Word routes through the real
server. Fictional data only. Run: python3 dev/run_tests.py test_word_route

What is asserted, for the import: a check writes nothing; an apply is ONE step by the "word" route with ONE Undo; the history of
each item says "by Word import (<file name>)" under the person's name; items are new, hidden from the client, never changed or
removed; the same content twice makes the items once (and again after an Undo); a bad row names itself and the whole step rolls
back with nothing written; a hostile file, a wrong request and an old plan are refused in plain words; no message has jargon.
"""
import base64
import json
import re
import unittest
from pathlib import Path

from _demo import DemoStore
from _paths import SRC
from clark import history, word_route
from test_docx_read import P, TBL, TR, docx

USER = "Dana Ellis"
TODAY = "2026-10-29"
NAME = "week 43 notes.docx"
JARGON = r"(?i)\bzip\b|\bxml\b|\bentity\b|\bdtd\b|\brelationship|traceback|exception|errno|\bsql\b|\bjson\b|\bschema\b|fingerprint|base64"


def body():
    return (P("Weekly notes", style="Heading1") + P("Next steps", style="Heading1") + P("Chase the supplier")
            + TBL(TR("Action", "Owner", "Due", "Priority"), TR("Draft the brief", "Sam Okafor", "12-11-2026", "High"))
            + P("Risks", style="Heading1") + P("Supplier may slip the delivery")
            + P("Decisions", style="Heading1") + P("Move go-live to December"))


def encoded(data):
    return base64.b64encode(data).decode("ascii")


class Base(unittest.TestCase):
    def setUp(self):
        word_route.PLANS.clear()
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.addCleanup(word_route.PLANS.clear)
        self.store = self.demo.store
        self.now = [1000.0]
        self.seam = word_route.make_word_import(self.store.path, [], USER, today=lambda: TODAY, clock=lambda: self.now[0])

    def post(self, **req):
        status, got = self.seam(req)
        return status, got

    def check(self, data=None, name=NAME, project="ABC"):
        return self.post(op="check", project=project, name=name, data=encoded(docx(body()) if data is None else data))

    def apply(self, plan, accept="all", project="ABC"):
        return self.post(op="apply", project=project, plan=plan, accept=accept)

    def rows(self, table):
        return [r for r in self.store.read(table, "ABC")]

    def counts(self):
        con = self.store.con
        return {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("actions", "raid", "decisions", "applies", "change_log")}

    def state(self):
        return Path(self.store.path).parent / word_route.STATE_FILE


class Check(Base):
    def test_a_check_lists_the_new_items_by_number_and_writes_nothing(self):
        before = self.counts()
        status, got = self.check()
        self.assertEqual(status, 200, got)
        self.assertEqual([(i["n"], i["table"]) for i in got["items"]],
                         [(1, "actions"), (2, "actions"), (3, "raid"), (4, "decisions")])
        self.assertIn("Not shown to the client until you turn it on.", got["items"][0]["text"])
        self.assertEqual(self.counts(), before)
        self.assertFalse(self.state().exists())

    def test_it_reads_the_file_it_is_given_and_names_it_in_the_plan(self):
        status, got = self.check(name="C:\\Users\\dana\\Documents\\week 43 notes.docx")
        self.assertEqual((status, got["file"]), (200, "week 43 notes.docx"))


class Apply(Base):
    def go(self, accept="all"):
        _, plan = self.check()
        return self.apply(plan["plan"], accept)

    def test_accept_all_is_one_step_by_the_word_route_with_one_undo(self):
        status, got = self.go()
        self.assertEqual(status, 200, got)
        self.assertEqual(len(got["added"]), 4)
        step = got["apply_id"]
        rows = self.store.step_rows(step)
        self.assertTrue(rows)
        self.assertEqual({r["via"] for r in rows}, {"word"})
        self.assertEqual(len({r["via"] for r in rows}), 1)
        self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies WHERE apply_id = ?", (step,)).fetchone()[0], 1)
        a, r, d = self.rows("actions"), self.rows("raid"), self.rows("decisions")
        self.assertEqual(sorted(x["description"] for x in a), ["Chase the supplier", "Draft the brief"])
        self.assertEqual([(x["type"], x["description"]) for x in r], [("Risk", "Supplier may slip the delivery")])
        self.assertEqual([x["decision"] for x in d], ["Move go-live to December"])
        for x in a + r + d:
            self.assertEqual(x["client_visible"], 0, "hidden from the client until the person turns it on")
            self.assertTrue(x["source"].startswith("Word import, 29-10-2026, week 43 notes.docx, under"))

    def test_each_items_history_says_how_it_came_in_under_the_persons_name(self):
        _, got = self.go()
        for ref in got["added"]:
            events = history.history(self.store.con, ref)
            self.assertTrue(events, ref)
            for e in events:
                self.assertEqual((e["route"], e["src_ref"], e["by_user"], e["actor"]), ("word", "by Word import (week 43 notes.docx)", USER, "you"))

    def test_undo_takes_back_the_whole_step_and_only_that_step(self):
        before = {t: len(self.rows(t)) for t in ("actions", "raid", "decisions")}
        _, got = self.go()
        status, undone = self.post(op="undo", project="ABC", apply_id=got["apply_id"])
        self.assertEqual(status, 200, undone)
        self.assertEqual({t: len(self.rows(t)) for t in ("actions", "raid", "decisions")}, before)
        self.assertIn("4 item(s)", undone["message"])
        status, again = self.post(op="undo", project="ABC", apply_id=got["apply_id"])
        self.assertEqual((status, again["code"]), (409, "undone"))

    def test_accepting_by_number_adds_only_those(self):
        status, got = self.go([2, 4])
        self.assertEqual(status, 200, got)
        self.assertEqual(len(got["added"]), 2)
        self.assertEqual([x["description"] for x in self.rows("actions")], ["Draft the brief"])
        self.assertEqual(self.rows("raid"), [])
        self.assertEqual(len(self.rows("decisions")), 1)

    def test_a_number_that_is_not_in_the_plan_is_refused_and_nothing_is_written(self):
        before = self.counts()
        status, got = self.go([1, 9])
        self.assertEqual((status, got["message"]), (400, "There is no staged item 9."))
        self.assertEqual(self.counts(), before)

    def test_the_same_file_twice_makes_the_items_once(self):
        self.go()
        after = self.counts()
        status, got = self.check()
        self.assertEqual((status, got["items"], got["already_added"]), (200, [], 4))
        self.assertEqual(self.counts(), after)

    def test_two_imports_of_the_same_file_waiting_together_make_the_items_once(self):
        _, first = self.check()
        _, second = self.check()
        self.assertEqual(self.apply(first["plan"])[0], 200)
        status, got = self.apply(second["plan"])
        self.assertEqual((status, got["code"]), (409, "nothing_to_add"))
        self.assertEqual(len(self.rows("actions")), 2)

    def test_after_an_undo_the_same_content_can_be_added_again(self):
        _, got = self.go()
        self.post(op="undo", project="ABC", apply_id=got["apply_id"])
        status, plan = self.check()
        self.assertEqual(len(plan["items"]), 4)
        self.assertEqual(self.apply(plan["plan"])[0], 200)

    def test_a_plan_is_applied_once(self):
        _, plan = self.check()
        self.assertEqual(self.apply(plan["plan"])[0], 200)
        status, got = self.apply(plan["plan"])
        self.assertEqual((status, got["message"]), (410, word_route.EXPIRED))

    def test_a_plan_expires_and_belongs_to_its_project(self):
        _, plan = self.check()
        self.now[0] += word_route.PLAN_MINUTES * 60 + 1
        self.assertEqual(self.apply(plan["plan"])[1]["message"], word_route.EXPIRED)
        _, plan = self.check()
        self.assertEqual(self.apply(plan["plan"], project="XYZ")[0], 404)
        self.assertEqual(self.apply("nope")[0], 410)

    def test_a_bad_row_names_itself_and_nothing_at_all_is_written(self):
        _, plan = self.check()
        before = self.counts()
        word_route.PLANS[plan["plan"]]["plan"].items[1].values["priority"] = "Whenever"      # the rule the store checks
        status, got = self.apply(plan["plan"])
        self.assertEqual((status, got["code"]), (400, "rolled_back"))
        self.assertIn("Nothing was added", got["message"])
        self.assertIn("new action (table 1, line 1 under", got["message"])
        self.assertEqual(self.counts(), before, "the whole step rolled back")
        self.assertFalse(self.state().exists())
        self.assertIn(plan["plan"], word_route.PLANS, "the person can choose fewer items and try again")
        item = word_route.PLANS[plan["plan"]]["plan"].items[1]
        item.values["priority"] = "High"
        self.assertEqual(self.apply(plan["plan"])[0], 200)

    def test_the_record_holds_fingerprints_and_ids_and_no_text(self):
        self.go()
        text = self.state().read_text(encoding="utf-8")
        for words in ("supplier", "Okafor", "go-live", "brief"):
            self.assertNotIn(words, text)
        got = json.loads(text)
        self.assertEqual(len(got["created"]), 4)
        self.assertTrue(all(set(r) == {"fp", "id", "table"} and re.fullmatch(r"[0-9a-f]{64}", r["fp"]) for r in got["created"]))

    def test_a_record_that_cannot_be_written_is_said_and_the_import_stands(self):
        self.state().mkdir()                                        # a folder where the file should go
        _, got = self.go()
        self.assertEqual(self.counts()["actions"], 2)
        self.assertIn("could not note that", got["message"])

    def test_undo_will_not_reverse_a_step_that_is_not_a_word_import(self):
        step = self.demo.last_step()
        status, got = self.post(op="undo", project="ABC", apply_id=step)
        self.assertEqual((status, got["message"]), (400, word_route.NO_UNDO))
        for bad in (0, -1, "1", 1.5, None, True, 2 ** 70):
            self.assertEqual(self.post(op="undo", project="ABC", apply_id=bad)[1]["message"], word_route.NO_UNDO, bad)

    def test_no_word_step_is_undone_through_another_project_code(self):
        _, got = self.go()
        with self.demo.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "OTH", "name": "Other Programme"})
        self.assertEqual(self.post(op="undo", project="OTH", apply_id=got["apply_id"])[1]["message"], word_route.NO_UNDO)


class Refusals(Base):
    def refused(self, status_wanted=400, **req):
        before = self.counts()
        status, got = self.post(**req)
        self.assertEqual(status, status_wanted, got)
        self.assertFalse(got["ok"])
        self.assertNotRegex(got["message"], JARGON)
        self.assertEqual(self.counts(), before)
        self.assertFalse(word_route.PLANS)
        return got

    def test_a_hostile_file_stages_nothing_and_is_refused_in_plain_words(self):
        for parts, words in (({"word/vbaProject.bin": b"x"}, "has macros"), ({"word/embeddings/a.bin": b"x"}, "file or object inside")):
            got = self.refused(op="check", project="ABC", name=NAME, data=encoded(docx(body(), parts=parts)))
            self.assertIn(words, got["message"])
            self.assertIn(NAME, got["message"])
        got = self.refused(op="check", project="ABC", name=NAME, data=encoded(b"not a word file"))
        self.assertIn("can't be opened as a Word document", got["message"])

    def test_a_file_that_unpacks_too_big_is_refused(self):
        import zipfile
        import io
        big = io.BytesIO()
        with zipfile.ZipFile(big, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", b"0" * (60 * 1024 * 1024))                # about 60 KB packed, 60 MB unpacked
        got = self.refused(op="check", project="ABC", name=NAME, data=encoded(big.getvalue()))
        self.assertIn("MB", got["message"])

    def test_an_oversize_request_is_refused_before_it_is_decoded(self):
        got = self.refused(op="check", project="ABC", name=NAME, data="A" * (word_route.docx_read.MAX_FILE_BYTES * 4 // 3 + 1000))
        self.assertIn("more than clark will open", got["message"])

    def test_requests_that_are_not_what_they_should_be(self):
        for req, words in (({"op": "check", "project": "ABC", "name": NAME}, word_route.NO_FILE),
                           ({"op": "check", "project": "ABC", "name": NAME, "data": "***"}, word_route.BAD_FILE),
                           ({"op": "check", "project": "ABC", "name": "", "data": "AAAA"}, word_route.BAD_NAME),
                           ({"op": "check", "project": "ABC", "name": 7, "data": "AAAA"}, word_route.BAD_NAME),
                           ({"op": "check", "project": "ABC", "name": "x" * 300, "data": "AAAA"}, word_route.BAD_NAME),
                           ({"op": "delete", "project": "ABC"}, word_route.BAD_OP),
                           ({"op": 1, "project": "ABC"}, word_route.BAD_OP),
                           ({"op": "check", "project": "abc", "name": NAME, "data": "AAAA"}, "project code"),
                           ({"project": "ABC"}, word_route.BAD_OP),
                           ({"op": "check", "project": "ABC", "name": NAME, "data": "AAAA", "folder": "/tmp"}, "not allowed: 'folder'"),
                           ({"op": "check", "project": "ABC", "name": NAME, "data": "AAAA", "evil": 1}, "not allowed: 'evil'")):
            with self.subTest(req=req):
                self.assertIn(words, self.refused(**req)["message"])
        self.assertEqual(self.seam([])[1]["message"], word_route.NOT_JSON_OBJECT)
        self.assertEqual(self.refused(404, op="check", project="NOPE", name=NAME, data="AAAA")["code"], "project_not_found")
        _, plan = self.check()
        for accept in (None, [], [0], [-1], ["1"], [True], [1.5], "some", {"all": 1}, list(range(1, 5002))):
            with self.subTest(accept=accept):
                self.assertEqual(self.apply(plan["plan"], accept)[1]["message"], word_route.BAD_ACCEPT)

    def test_nothing_accepted_adds_nothing(self):
        _, plan = self.check()
        self.assertEqual(self.apply(plan["plan"], [])[1]["message"], word_route.BAD_ACCEPT)

    def test_plans_waiting_are_limited(self):
        for n in range(word_route.MAX_PLANS + 3):
            self.now[0] += 1
            self.assertEqual(self.check()[0], 200)
        self.assertEqual(len(word_route.PLANS), word_route.MAX_PLANS)


class WhatTheModuleCanDo(unittest.TestCase):
    """No path that removes, closes or changes an item: read from the source."""
    SRC = (SRC / "clark" / "word_route.py").read_text(encoding="utf-8")

    def test_it_never_changes_cancels_or_deletes_an_item(self):
        for word in (".cancel(", ".update(", "DELETE", "unlink", "os.remove", "rmtree"):
            self.assertNotIn(word, self.SRC.replace("store.undo(step, who)", ""), word)

    def test_it_writes_only_the_one_record_file_and_through_platform(self):
        self.assertEqual(re.findall(r"platform\.write_file\(([^,]+),", self.SRC), ["state_path(store)"])
        self.assertNotRegex(self.SRC, r"open\(|subprocess|socket|urllib")

    def test_its_words_are_plain(self):
        for name in ("NOT_JSON_OBJECT", "BAD_OP", "NO_FILE", "BAD_NAME", "BAD_FILE", "EXPIRED", "BAD_ACCEPT", "NOTHING_ACCEPTED",
                     "NO_UNDO", "UNDONE", "NOT_RECORDED", "ALL_SEEN", "SOME_SEEN"):
            text = getattr(word_route, name)
            self.assertNotRegex(text, JARGON, name)
            self.assertFalse(text.lower().startswith("clark"), name)


if __name__ == "__main__":
    unittest.main()

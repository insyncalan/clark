"""#48 (guarded): the Word routes' logic (src/clark/word_route.py) on a real store, and the server's Word routes through the real
server. Fictional data only. Run: python3 dev/run_tests.py test_word_route

What is asserted, for the import: a check writes nothing; an apply is ONE step by the "word" route with ONE Undo; the history of
each item says "by Word import (<file name>)" under the person's name; items are new, hidden from the client, never changed or
removed; the same content twice makes the items once (and again after an Undo); a bad row names itself and the whole step rolls
back with nothing written; a hostile file, a wrong request and an old plan are refused in plain words; no message has jargon.
"""
import base64
import hashlib
import json
import os
import re
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest import mock

from _demo import DemoStore
from _paths import SRC
from clark import docx_read, history, platform, word_route
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
        text = self.SRC.replace("store.undo(step, who)", "")
        for word in (".cancel(", ".update(", "DELETE", "os.remove", "rmtree"):
            self.assertEqual(text.find(word), -1, word)

    def test_the_only_file_it_removes_is_the_copy_it_has_just_made_that_did_not_match(self):
        self.assertEqual(self.SRC.count(".unlink("), 1)
        body = self.SRC[self.SRC.index("def _take_back"):self.SRC.index("def _do_export")]
        self.assertIn(".unlink(", body)
        calls = re.findall(r"(?<!def )_take_back\((\w+)\)", self.SRC)
        self.assertEqual(calls, ["dest", "target"], "only after a copy it wrote itself failed to read back right")

    def test_it_writes_only_the_one_record_file_and_through_platform(self):
        self.assertEqual(re.findall(r"platform\.write_file\(([^,]+),", self.SRC), ["state_path(store)", "dest"])
        self.assertNotRegex(self.SRC, r"open\(|subprocess|socket|urllib")

    def test_its_words_are_plain(self):
        for name in ("NOT_JSON_OBJECT", "BAD_OP", "NO_FILE", "BAD_NAME", "BAD_FILE", "EXPIRED", "BAD_ACCEPT", "NOTHING_ACCEPTED",
                     "NO_UNDO", "UNDONE", "NOT_RECORDED", "ALL_SEEN", "SOME_SEEN", "CHOOSE_FOLDER", "BAD_FLAG", "BAD_CLASH",
                     "NO_CLIENT_FOLDER", "OVERWRITE_UNCONFIRMED", "NAME_TAKEN", "APPEARED", "FOLDER_GONE", "FOLDER_DATA", "NOT_SAVED",
                     "NOT_AS_MADE", "NOT_AS_MADE_REPLACED", "SAVED", "SAVED_CLIENT", "CLIENT_FAILED", "NOT_RECORDED_FILE", "CANCELLED"):
            text = getattr(word_route, name)
            self.assertNotRegex(text, JARGON, name)
            self.assertFalse(text.lower().startswith("clark"), name)


class Export(unittest.TestCase):
    """POST /api/word-export's logic on a real store with real temporary folders."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-word-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.local, self.client = self.tmp / "Reports", self.tmp / "Client"
        self.local.mkdir()
        self.client.mkdir()
        self.asked = []
        self.seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY, choose_folder=self.choose)
        self.name = "ABC-report-2026-10-29.docx"

    def choose(self, prompt):
        self.asked.append(prompt)
        return str(self.local)

    def post(self, **req):
        req.setdefault("project", "ABC")
        return self.seam(req)

    def save_client_folder(self, folder=None):
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"publish_client": str(folder or self.client)})

    def publications(self):
        return [dict(r) for r in self.store.con.execute("SELECT * FROM publications ORDER BY seq")]

    def files(self, folder):
        return sorted(p.name for p in folder.iterdir())

    def test_a_first_export_asks_for_a_folder_writes_the_file_reads_it_back_and_records_it(self):
        status, got = self.post()
        self.assertEqual((status, got["ok"], got["name"], self.asked), (200, True, self.name, [word_route.CHOOSE_FOLDER]), got)
        data = (self.local / self.name).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), got["sha256"])
        self.assertEqual(self.files(self.local), [self.name], "no temporary file is left")
        read = docx_read.read(data, self.name)
        self.assertIn("Example Programme", json.dumps(read.blocks))
        row, = self.publications()
        self.assertEqual((row["word"], row["file_sha256"], row["local_path"], row["client_path"], row["by_user"], row["project"]),
                         (1, got["sha256"], str(self.local / self.name), None, USER, "ABC"))
        self.assertEqual(self.files(self.client), [])

    def test_the_folder_is_remembered_and_the_dialog_is_not_asked_again(self):
        self.post()
        self.post(on_clash="number")
        self.assertEqual(len(self.asked), 1)

    def test_a_cancelled_folder_dialog_saves_nothing(self):
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY, choose_folder=lambda p: None)
        status, got = seam({"project": "ABC"})
        self.assertEqual((status, got.get("cancelled")), (200, True))
        self.assertEqual((self.files(self.local), self.publications()), ([], []))

    def test_the_dialog_runs_without_the_one_lock_held(self):
        from clark import changes

        def choose(prompt):
            self.assertTrue(changes.LOCK.acquire(blocking=False), "the lock is free while the person chooses")
            changes.LOCK.release()
            return str(self.local)
        word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY, choose_folder=choose)({"project": "ABC"})

    def test_a_taken_name_asks_first_and_writes_nothing_until_answered(self):
        self.post()
        before = (self.files(self.local), len(self.publications()))
        status, got = self.post()
        self.assertEqual((status, got["code"], got["taken"], got["choices"]), (409, "name_taken", {"here": self.name},
                                                                               ["number", "overwrite", "cancel"]))
        self.assertIn(self.name, got["message"])
        self.assertEqual((self.files(self.local), len(self.publications())), before)

    def test_add_a_number_keeps_the_old_file(self):
        self.post()
        old = (self.local / self.name).read_bytes()
        status, got = self.post(on_clash="number")
        self.assertEqual((status, got["name"]), (200, "ABC-report-2026-10-29 (2).docx"))
        self.assertEqual((self.local / self.name).read_bytes(), old)
        self.assertEqual(len(self.publications()), 2)

    def test_replace_needs_the_confirmed_flag_itself(self):
        self.post()
        (self.local / self.name).write_bytes(b"edited by hand")
        for confirmed in (None, False, "true", 1):
            extra = {} if confirmed is None else {"confirmed": confirmed}
            status, got = self.post(on_clash="overwrite", **extra)
            self.assertEqual(status, 400, confirmed)
        self.assertEqual((self.local / self.name).read_bytes(), b"edited by hand")
        status, got = self.post(on_clash="overwrite", confirmed=True)
        self.assertEqual((status, got["name"]), (200, self.name))
        self.assertEqual(hashlib.sha256((self.local / self.name).read_bytes()).hexdigest(), got["sha256"])

    def test_cancel_saves_nothing(self):
        self.post()
        status, got = self.post(on_clash="cancel")
        self.assertEqual((status, got["cancelled"], self.files(self.local), len(self.publications())), (200, True, [self.name], 1))

    def test_a_folder_with_the_name_is_never_replaced(self):
        (self.local / self.name).mkdir()
        self.post()                                                  # remembers nothing: no row yet, so the dialog gives the folder
        status, got = self.post(on_clash="overwrite", confirmed=True)
        self.assertEqual((status, got["code"]), (400, "folder_has_name"))
        self.assertEqual(list((self.local / self.name).iterdir()), [])

    def test_the_client_folder_is_untouched_unless_to_client_is_ticked(self):
        self.save_client_folder()
        self.post()
        self.post(to_client=False, on_clash="number")
        self.assertEqual(self.files(self.client), [])

    def test_to_client_copies_the_same_bytes_and_records_the_copy(self):
        self.save_client_folder()
        status, got = self.post(to_client=True)
        self.assertEqual((status, got["client_name"], got["client_failed"]), (200, self.name, False), got)
        self.assertEqual((self.client / self.name).read_bytes(), (self.local / self.name).read_bytes())
        self.assertEqual(self.files(self.client), [self.name], "no temporary file is left")
        row, = self.publications()
        self.assertEqual((row["word"], row["client_path"], row["file_sha256"]), (1, str(self.client / self.name), got["sha256"]))
        self.assertIn("also copied to the client folder", got["message"])

    def test_to_client_with_no_client_folder_or_a_bad_one_saves_nothing_anywhere(self):
        status, got = self.post(to_client=True)
        self.assertEqual((status, got["message"]), (400, word_route.NO_CLIENT_FOLDER))
        for bad in (self.tmp / "gone", Path(self.store.path).parent, self.local):
            self.save_client_folder(bad)
            status, got = self.post(to_client=True)
            self.assertEqual((status, got["code"]), (400, "client_folder"), bad)
            self.assertTrue(got["message"].endswith("Nothing was saved."))
        self.assertEqual((self.files(self.local), self.publications()), ([], []))

    def test_a_name_taken_in_the_client_folder_asks_and_is_then_numbered_never_replaced(self):
        self.save_client_folder()
        (self.client / self.name).write_bytes(b"the client's own")
        status, got = self.post(to_client=True)
        self.assertEqual((status, got["taken"], got["choices"]), (409, {"client": self.name}, ["number", "cancel"]))
        self.assertEqual(self.files(self.local), [])
        status, got = self.post(to_client=True, on_clash="number")
        self.assertEqual((status, got["client_name"]), (200, "ABC-report-2026-10-29 (2).docx"))
        self.assertEqual((self.client / self.name).read_bytes(), b"the client's own")
        self.post(to_client=True, on_clash="overwrite", confirmed=True)       # replace is for the local file only
        self.assertEqual((self.client / self.name).read_bytes(), b"the client's own")

    def test_a_client_copy_that_does_not_match_is_taken_back_and_the_local_file_stays(self):
        self.save_client_folder()
        real = word_route._verified
        with mock.patch.object(word_route, "_verified", lambda dest, digest: real(dest, digest) if dest.parent == self.local else False):
            status, got = self.post(to_client=True)
        self.assertEqual((status, got["client_failed"], got["client_name"]), (200, True, None))
        self.assertIn("It was not copied to the client folder", got["message"])
        self.assertEqual((self.files(self.local), self.files(self.client)), ([self.name], []))
        self.assertIsNone(self.publications()[0]["client_path"])

    def test_a_local_file_that_does_not_match_is_taken_back_and_nothing_is_recorded(self):
        self.post()                                                 # remember the folder
        for row in self.publications():
            pass
        os.unlink(self.local / self.name)
        self.store.con.execute("DELETE FROM publications")
        with mock.patch.object(word_route, "_verified", lambda dest, digest: False):
            status, got = self.post()
        self.assertEqual((status, got["code"]), (500, "not_as_made"))
        self.assertEqual(self.files(self.local), [])

    def test_a_file_that_cannot_be_written_says_so_in_plain_words_and_records_nothing(self):
        self.post()
        self.store.con.execute("DELETE FROM publications")
        os.unlink(self.local / self.name)
        err = platform.PlatformError("clark couldn't save the file because another program is using it")
        with mock.patch.object(platform, "write_file_unless_exists", side_effect=err):
            status, got = self.post()
        self.assertEqual((status, got["code"]), (503, "not_saved"))
        self.assertIn("Nothing was written.", got["message"])
        self.assertEqual(self.publications(), [])

    def test_a_publication_that_cannot_be_recorded_is_said_and_the_file_stands(self):
        with mock.patch.object(type(self.store), "log_publication", side_effect=word_route.Invalid("busy")):
            status, got = self.post()
        self.assertEqual((status, got["seq"]), (200, None))
        self.assertIn("could not record it", got["message"])
        self.assertTrue((self.local / self.name).is_file())

    def test_a_request_never_names_a_folder_or_a_file(self):
        for key in ("folder", "path", "file", "name", "client_folder", "local_path", "dest"):
            status, got = self.post(**{key: str(self.tmp / "elsewhere")})
            self.assertEqual(status, 400, key)
            self.assertIn("not allowed", got["message"])
        self.assertEqual((self.files(self.local), self.files(self.tmp)), ([], ["Client", "Reports"]))

    def test_other_bad_requests_are_refused_in_plain_words(self):
        for req, words in (({"to_client": "yes"}, word_route.BAD_FLAG), ({"confirmed": 1}, word_route.BAD_FLAG),
                           ({"on_clash": "erase"}, word_route.BAD_CLASH), ({"on_clash": 5}, word_route.BAD_CLASH),
                           ({"project": "abc"}, "project code"), ({"project": None}, "project code")):
            status, got = self.post(**req)
            self.assertEqual(status, 400, req)
            self.assertIn(words, got["message"])
        self.assertEqual(self.post(project="NOPE")[1]["code"], "project_not_found")
        self.assertEqual(self.seam([])[1]["message"], word_route.NOT_JSON_OBJECT)

    def test_a_chosen_folder_inside_clarks_own_data_is_refused(self):
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY,
                                           choose_folder=lambda p: str(Path(self.store.path).parent))
        status, got = seam({"project": "ABC"})
        self.assertEqual((status, got["code"]), (400, "folder_data"))
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY, choose_folder=lambda p: str(self.tmp / "gone"))
        self.assertEqual(seam({"project": "ABC"})[1]["code"], "folder_gone")

    def test_a_long_folder_still_gets_a_name_that_is_safe_on_windows(self):
        deep = self.local
        for part in ("a" * 40, "b" * 40, "c" * 40, "d" * 40):
            deep = deep / part
        deep.mkdir(parents=True)
        seam = word_route.make_word_export(self.store.path, [], USER, today=lambda: TODAY, choose_folder=lambda p: str(deep))
        status, got = seam({"project": "ABC"})
        self.assertEqual(status, 200, got)
        self.assertEqual(platform.safe_name(got["name"], deep), got["name"])
        self.assertLess(len(got["path"]), platform.MAX_PATH)
        self.assertTrue(got["name"].endswith(".docx"))


if __name__ == "__main__":
    unittest.main()

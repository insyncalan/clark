"""#47e part 2: POST /api/ask/change/dry and /api/ask/change/apply (ask_service.py, routed by server.py), against a real server and
a real store, with a STUB provider (nothing here calls a model).

Run: python3 dev/run_tests.py test_ask_change_route
An answer's suggested changes are held on the server under a reply ID; the dry run takes only {project, reply}, Apply only
{project, offer, confirm?}. A change from an answer that was given passages from the person's files is marked on the server and
needs confirm: true, which no field from the page can clear. Each safeguard removed in turn turns a named check red (Mutants).
Fictional data only.
"""
import ast
import json
import re
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC
from test_ask_route import Running
from clark import ask, ask_apply, ask_passages, ask_service, changes

FILE = ask.Passage("notes/plan.md", "Close ABC-A-001: the plan was signed off on Monday.")


def change_line(**fields):
    return "CHANGE: " + json.dumps(fields)


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.path = self.store.path
        self.action = self.demo.action(owner="Sam Lee", client_visible=1)
        self.provider = ask.StubProvider(reply="")
        self.service = ask_service.AskService(self.path, self.provider, [], applier=ask_apply.AskApply(self.path, [], USER))
        self.s = Running()
        self.s.httpd.ask = self.service
        self.s.httpd.undo = changes.make_undo(self.path, [], USER)
        self.addCleanup(self.s.close)
        self.files = ()                                    # passages "from the saved folders" for the next question

    def folder_data(self, *_a, **_kw):
        return ask_passages.FolderData(passages=tuple(self.files))

    def answer(self, *lines, files=()):
        """Ask once with the stub replying `lines`; the reply's body (with its reply ID)."""
        self.files = files
        self.provider.reply = "\n".join(("Here is what I found.",) + lines)
        with mock.patch.object(ask_service.ask_passages, "folder_data", self.folder_data):
            status, got = self.s.api("POST", "/api/ask", {"project": "ABC", "question": "What should change?"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        return got

    def dry(self, reply, project="ABC", **more):
        return self.s.api("POST", "/api/ask/change/dry", {"project": project, "reply": reply, **more})

    def apply(self, offer, project="ABC", **more):
        return self.s.api("POST", "/api/ask/change/apply", {"project": project, "offer": offer, **more})

    def close_it(self, files=()):
        """An answer suggesting ABC-A-001 be closed, and its dry run's one plan."""
        got = self.answer(change_line(op="change", id=self.action, current_title="Draft the cut-over plan",
                                      current_owner="Sam Lee", status="Closed"), "CITE: P1", files=files)
        status, dry = self.dry(got["reply"])
        self.assertEqual((status, dry.get("ok")), (200, True), dry)
        return got, dry

    def counts(self):
        con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        try:
            return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log", "item_events"))
        finally:
            con.close()

    def status_of(self, ref):
        return self.store.read("actions", ref=ref)["status"]

    def set_switch(self, on):
        with self.store.step("dashboard", USER) as st:
            st.update("app_settings", "1", {"ask_enabled": on})


class TheDoors(Base):
    def test_without_the_token_or_from_another_site_nothing_runs(self):
        got = self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        before = self.counts()
        for path, body in (("/api/ask/change/dry", {"project": "ABC", "reply": got["reply"]}),
                           ("/api/ask/change/apply", {"project": "ABC", "offer": "x"})):
            self.assertEqual(self.s.api("POST", path, body, token="")[0], 403, path)
            self.assertEqual(self.s.api("POST", path, body, token="stale-token")[0], 403, path)
            self.assertEqual(self.s.api("POST", path, body, extra={"Origin": "https://evil.example"})[0], 403, path)
            self.assertEqual(self.s.api("POST", path, json.dumps(body).encode(), ctype="text/plain")[0], 415, path)
            self.assertEqual(self.s.api("POST", path, b'{"project": "ABC", "reply": "' + b"x" * 1100 + b'"}')[0], 400, path)
        self.assertEqual(self.counts(), before)
        status, dry = self.dry(got["reply"])                    # the doors refused, so the dry run was never made
        self.assertEqual(status, 200, dry)

    def test_without_a_service_the_routes_are_not_found(self):
        self.s.httpd.ask = None
        self.assertEqual(self.dry("x")[0], 404)
        self.assertEqual(self.apply("x")[0], 404)

    def test_with_asking_off_both_refuse_and_nothing_is_written(self):
        got = self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        self.set_switch(False)
        before = self.counts()
        status, body = self.dry(got["reply"])
        self.assertEqual((status, body["code"]), (409, "asking_off"))
        self.assertIn("nothing was changed", body["message"].lower())
        self.assertEqual(self.counts(), before)
        self.set_switch(True)
        status, dry = self.dry(got["reply"])
        offer = dry["plans"][0]["offer"]
        self.set_switch(False)
        before = self.counts()
        status, body = self.apply(offer)
        self.assertEqual((status, body["code"]), (409, "asking_off"))
        self.assertEqual(self.counts(), before, "nothing was written")
        self.assertEqual([r["description"] for r in self.store.read("actions", "ABC")], ["Draft the cut-over plan"])

    def test_neither_route_ever_asks_the_provider(self):
        got, dry = self.close_it()
        sent = len(self.provider.sent)
        self.apply(dry["plans"][0]["offer"])
        self.dry(got["reply"])
        self.assertEqual(len(self.provider.sent), sent)
        text = (SRC / "clark" / "ask_service.py").read_text(encoding="utf-8")
        for name in ("def change_dry", "def change_apply"):
            body = text[text.index(name):]
            body = body[:body.index("\n    def ") if "\n    def " in body else len(body)]
            self.assertNotIn("self.provider", body, name)
            self.assertNotIn("ask_provider", body, name)


class Forged(Base):
    def test_a_change_the_page_sends_itself_is_refused(self):
        got = self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        before = self.counts()
        forged = {"op": "change", "id": self.action, "status": "Closed"}
        for body in ({"project": "ABC", "change": forged}, {"project": "ABC", "reply": got["reply"], "change": forged},
                     {"project": "ABC", "reply": got["reply"], "changes": [forged]}, {"project": "ABC"}, {"reply": got["reply"]},
                     {"project": "ABC", "reply": 5}, [], "x"):
            status, out = self.s.api("POST", "/api/ask/change/dry", body)
            self.assertEqual(status, 400, body)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.status_of(self.action), "Open")

    def test_a_made_up_reply_or_offer_is_refused(self):
        self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        self.assertEqual(self.dry("made-up")[1]["code"], "no_reply")
        status, body = self.apply("made-up")
        self.assertEqual((status, body["code"]), (409, "no_offer"))
        for bad in ({"project": "ABC"}, {"project": "ABC", "offer": 5}, {"project": "ABC", "offer": "x", "confirm": "yes"},
                    {"project": "ABC", "offer": "x", "confirm": 1}, {"project": "ABC", "offer": "x", "change": {}}):
            self.assertEqual(self.s.api("POST", "/api/ask/change/apply", bad)[0], 400, bad)

    def test_a_wrong_title_or_owner_in_the_answer_is_refused_by_the_dry_run(self):
        got = self.answer(change_line(op="change", id=self.action, current_title="Order the kit", status="Closed"))
        status, dry = self.dry(got["reply"])
        self.assertEqual(dry["plans"][0]["code"], "wrong_title")
        got = self.answer(change_line(op="change", id=self.action, current_owner="Kit Moss", status="Closed"))
        self.assertEqual(self.dry(got["reply"])[1]["plans"][0]["code"], "wrong_owner")

    def test_a_reply_is_for_its_own_project_only(self):
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        got = self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        self.assertEqual(self.dry(got["reply"], project="XYZ")[1]["code"], "no_reply")
        self.assertEqual(self.dry(got["reply"])[0], 200, "the wrong project did not use it up")

    def test_archive_delete_and_more_than_five_stay_refused(self):
        got = self.answer(change_line(op="archive", id=self.action), change_line(op="delete", id=self.action))
        plans = self.dry(got["reply"])[1]["plans"]
        self.assertEqual([p["code"] for p in plans], ["not_yet", "not_yet"])
        self.assertTrue(all("isn't available yet" in p["message"] for p in plans))
        many = [change_line(op="new", kind="action", title=f"Task {i}", owner="Sam Lee") for i in range(6)]
        got = self.answer(*many)
        status, body = self.dry(got["reply"])
        self.assertEqual((status, body["code"]), (400, "too_many"))
        self.assertIn("isn't available yet", body["message"])
        self.assertEqual(self.store.read("actions", "ABC").__len__(), 1)


class OnceOnly(Base):
    def test_an_offer_is_used_once(self):
        _got, dry = self.close_it()
        offer = dry["plans"][0]["offer"]
        status, done = self.apply(offer)
        self.assertEqual((status, done["ok"]), (200, True), done)
        before = self.counts()
        status, again = self.apply(offer)
        self.assertEqual((status, again["code"]), (409, "no_offer"))
        self.assertEqual(self.counts(), before)

    def test_a_replys_dry_run_is_made_once(self):
        got, _dry = self.close_it()
        status, body = self.dry(got["reply"])
        self.assertEqual((status, body["code"]), (409, "shown_already"))

    def test_a_new_item_is_made_once_however_often_apply_is_pressed(self):
        got = self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        offer = self.dry(got["reply"])[1]["plans"][0]["offer"]
        results = [self.apply(offer)[0] for _ in range(3)]
        self.assertEqual(results, [200, 409, 409])
        self.assertEqual(len([r for r in self.store.read("actions", "ABC") if r["description"] == "Book the room"]), 1)


class FromYourFiles(Base):
    def file_id(self):
        """The passage ID the planted file gets in a request (after the project's own passages)."""
        self.answer(files=(FILE,))
        return re.search(r"(P\d+) from notes/plan\.md", self.provider.sent[-1]).group(1)

    def test_a_change_from_an_answer_that_read_your_files_needs_confirm(self):
        pid = self.file_id()
        got = self.answer(change_line(op="change", id=self.action, status="Closed", source=pid), files=(FILE,))
        dry = self.dry(got["reply"])[1]
        self.assertTrue(dry["from_source"])
        plan = dry["plans"][0]
        self.assertTrue(plan["needs_confirm"])
        self.assertEqual([p["label"] for p in dry["passages"]], ["notes/plan.md"])
        self.assertIn("signed off", dry["passages"][0]["text"])
        before = self.counts()
        status, body = self.apply(plan["offer"])
        self.assertEqual((status, body["code"]), (409, "needs_confirm"))
        status, body = self.apply(plan["offer"], confirm=False)
        self.assertEqual((status, body["code"]), (409, "needs_confirm"))
        self.assertEqual(self.counts(), before)
        status, body = self.apply(plan["offer"], confirm=True)
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(self.status_of(self.action), "Closed")

    def test_the_mark_holds_even_when_the_answer_cites_no_file(self):
        got = self.answer(change_line(op="change", id=self.action, status="Closed"), files=(FILE,))
        dry = self.dry(got["reply"])[1]
        self.assertTrue(dry["plans"][0]["needs_confirm"])
        self.assertEqual(dry["passages"], [], "no file was cited, so none is shown; the mark still holds")

    def test_no_field_from_the_page_clears_the_mark(self):
        got = self.answer(change_line(op="change", id=self.action, status="Closed"), f"CITE: {self.file_id()}", files=(FILE,))
        for extra in ({"from_source": False}, {"needs_confirm": False}, {"confirm": True}):
            status, _body = self.dry(got["reply"], **extra)
            self.assertEqual(status, 400, extra)
        offer = self.dry(got["reply"])[1]["plans"][0]["offer"]
        before = self.counts()
        for extra in ({"from_source": False}, {"needs_confirm": False}, {"confirm": "true"}, {"confirm": 1}, {"confirm": None}):
            status, _body = self.apply(offer, **extra)
            self.assertIn(status, (400, 409), extra)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.status_of(self.action), "Open")
        self.assertEqual(self.apply(offer, confirm=True)[0], 200, "the offer was still waiting for its Confirm")

    def test_an_answer_from_the_report_alone_needs_no_confirm(self):
        _got, dry = self.close_it()
        self.assertFalse(dry["from_source"])
        self.assertFalse(dry["plans"][0]["needs_confirm"])
        self.assertEqual(self.apply(dry["plans"][0]["offer"])[0], 200)


class TheDryRunAndUndo(Base):
    def test_before_and_after_come_from_the_data(self):
        _got, dry = self.close_it()
        plan = dry["plans"][0]
        self.assertEqual(plan["before"]["status"], "Open")
        self.assertEqual(plan["after"]["status"], "Closed")
        self.assertEqual(plan["before"]["description"], "Draft the cut-over plan")
        self.assertIn("status", plan["fields"])
        self.assertTrue(plan["after"]["closed"], "the closed date is the store's, shown as it would be saved")
        self.assertNotIn("description", plan["fields"])
        self.assertEqual(self.status_of(self.action), "Open", "a dry run saves nothing")

    def test_apply_is_one_step_that_undo_reverses(self):
        _got, dry = self.close_it()
        status, done = self.apply(dry["plans"][0]["offer"])
        self.assertEqual(status, 200, done)
        self.assertTrue(done["undoable"])
        self.assertIsInstance(done["apply_id"], int)
        events = [e for e in self.store.history(self.action) if e["route"] == "assistant"]
        self.assertEqual({(e["actor"], e["step"]) for e in events}, {("clark", done["apply_id"])})
        status, undone = self.s.api("POST", "/api/undo", {"project": "ABC", "apply_id": done["apply_id"]})
        self.assertEqual(status, 200, undone)
        self.assertEqual(self.status_of(self.action), "Open")

    def test_a_new_item_is_made_and_undone(self):
        got = self.answer(change_line(op="new", kind="milestone", title="Training done", owner="Sam Lee", agreed_date="2030-05-01"))
        plan = self.dry(got["reply"])[1]["plans"][0]
        self.assertIsNone(plan["before"])
        done = self.apply(plan["offer"])[1]
        self.assertEqual(self.store.read("milestones", ref=done["ref"])["name"], "Training done")
        self.assertEqual(self.s.api("POST", "/api/undo", {"project": "ABC", "apply_id": done["apply_id"]})[0], 200)
        row = self.store.read("milestones", ref=done["ref"])
        self.assertTrue(row is None or row.get("archived"), "the new milestone is gone again")


class Mutants(Base):
    """Each safeguard removed in turn must turn a named check red: the check above then fails."""

    def test_without_the_servers_mark_a_change_from_a_file_needs_no_confirm(self):
        real = ask_service.AskService.hold
        with mock.patch.object(ask_service.AskService, "hold", lambda s, c, r, q, _ids, t: real(s, c, r, q, set(), t)):
            got = self.answer(change_line(op="change", id=self.action, status="Closed"), files=(FILE,))
            offer = self.dry(got["reply"])[1]["plans"][0]["offer"]
            self.assertEqual(self.apply(offer)[0], 200, "the mark is what made Confirm needed")

    def test_without_the_body_check_a_forged_change_field_gets_past_the_door(self):
        got = self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        with mock.patch.object(ask_service, "DRY_FIELDS", {"project", "reply", "change"}):
            status, _ = self.s.api("POST", "/api/ask/change/dry", {"project": "ABC", "reply": got["reply"], "change": "x"})
        self.assertNotEqual(status, 400, "the strict body check is what refused it")

    def test_without_the_once_rule_a_reply_is_shown_twice(self):
        got = self.answer(change_line(op="new", kind="action", title="Book the room", owner="Sam Lee"))
        self.dry(got["reply"])
        self.service.replies[got["reply"]].shown = False         # the mark that it was shown, taken away
        self.assertEqual(self.dry(got["reply"])[0], 200, "the shown mark is what refused the second dry run")

    def test_without_the_servers_switch_gate_the_save_path_still_refuses(self):
        got = self.answer(change_line(op="change", id=self.action, status="Closed"))
        offer = self.dry(got["reply"])[1]["plans"][0]["offer"]
        self.set_switch(False)
        with mock.patch.object(ask_service.AskService, "enabled", lambda _s: True):
            status, body = self.apply(offer)
        self.assertEqual((status, body["code"]), (409, "asking_off"), "the switch is read again inside the step")
        self.assertEqual(self.status_of(self.action), "Open")


class Source(unittest.TestCase):
    def test_ask_service_saves_only_through_ask_apply(self):
        tree = ast.parse((SRC / "clark" / "ask_service.py").read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            self.assertFalse(isinstance(n, ast.Attribute) and n.attr in ("make_change", "make_ask_change", "make_undo", "step",
                                                                         "execute", "executescript"), getattr(n, "lineno", 0))
            self.assertFalse(isinstance(n, ast.Name) and n.id == "open_store", getattr(n, "lineno", 0))
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                self.assertNotIn("changes", [a.name for a in n.names], "ask_service never takes the save path itself")


if __name__ == "__main__":
    unittest.main()

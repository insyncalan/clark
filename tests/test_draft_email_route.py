"""#50 item 4: POST /api/draft-email and its seam (draft_email_feed). The route is the server's usual checks plus a hand-over to
the seam; the seam reads one project and asks the builder (draft_email.py) for the ticks and the email. Read only: nothing is
written, sent or drafted. Fictional names. Run: python3 dev/run_tests.py test_draft_email_route"""
import hashlib
import http.client
import json
import re
import sqlite3
import threading
import unittest
from datetime import date
from unittest import mock

import _paths  # noqa: F401
from _paths import SRC
from _demo import DemoStore, USER
from clark import draft_email as de
from clark import draft_email_feed as feed
from clark import publish
from clark import server as sv


class Running:
    """A server on a free port in a thread (the same harness shape as test_server.Running, which is not imported so this file
    stays in the quick tier: it never starts Chrome)."""

    def __init__(self, draft_email=None, draft_email_sent=None):
        self.httpd = sv.LocalServer((sv.HOST, 0), draft_email=draft_email, draft_email_sent=draft_email_sent)
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def ask(self, method, path, headers=None, body=None, host="default"):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            if host == "default":
                host = f"127.0.0.1:{self.port}"
            if host is not None:
                conn.putheader("Host", host)
            for k, v in (headers or {}).items():
                conn.putheader(k, v)
            conn.endheaders(body)
            r = conn.getresponse()
            return r.status, r.msg, r.read()
        finally:
            conn.close()

    def api(self, method, path, body=None, ctype="application/json", token=None, extra=None, host="default"):
        h = {sv.TOKEN_HEADER: sv.TOKEN if token is None else token, **(extra or {})}
        if body is not None:
            h["Content-Type"] = ctype
            h["Content-Length"] = str(len(body))
        return self.ask(method, path, h, body, host=host)

NOW = "2026-10-13 09:00"
OWN = ["example.test"]
INSIDE, OUTSIDE = "sam@example.test", "dana@partner.test"


def action(n, text, due=None, **kw):
    row = {"id": f"ABC-A-{n:03d}", "project": "ABC", "description": text, "owner": "Dana Hart", "priority": "Medium",
           "due_date": due, "status": "Open", "latest_update": None, "client_visible": 1}
    row.update(kw)
    return row


DATA = {"project": {"code": "ABC", "name": "Example Programme"},
        "actions": [action(1, "Share the UAT plan", "2026-10-09", latest_update="Plan in draft"),
                    action(2, "Confirm the test dates", "2026-10-15"),
                    action(3, "Check the vendor margin", "2026-10-20", client_visible=0),
                    action(4, "Closed already", status="Closed"),
                    action(5, "Mark this confidential please", "2026-10-20"),
                    action(6, "Someone else's", owner="Chris Dunn")],
        "raid": [{"id": "ABC-001", "project": "ABC", "type": "Issue", "description": "Test environment may slip",
                  "owner": "Dana Hart", "response_action": None, "due_date": "2026-10-16", "priority": "High", "status": "Open",
                  "client_visible": 1}],
        "decisions": [{"id": "ABC-D-001", "project": "ABC", "decision": "Which use cases go into Phase 2", "made_by": "Dana Hart",
                       "needed_by": "2026-10-15", "status": "Pending", "client_visible": 1},
                      {"id": "ABC-D-002", "project": "ABC", "decision": "Already made", "made_by": "Dana Hart",
                       "needed_by": None, "status": "Made", "client_visible": 1}]}


def profile():
    return {"name": "Sam Lee", "own_domains": OWN}


class Calls:
    def __init__(self, data=DATA):
        self.reads = []
        self.data = data

    def data_for(self, code):
        self.reads.append(code)
        return self.data if code == "ABC" else None


def seam(calls=None, **kw):
    calls = calls or Calls()
    return feed.make(calls.data_for, profile=kw.pop("profile", profile), clock=lambda: NOW, **kw)


def ask(req, **kw):
    return seam(**kw)(req)


class Seam(unittest.TestCase):
    def test_each_mode_builds_and_the_subject_and_signature_come_from_the_settings(self):
        for mode in de.MODES:
            status, body = ask({"project": "ABC", "mode": mode, "email": INSIDE})
            self.assertEqual((status, body["ok"], body["mode"], body["draft"]["mode"]), (200, True, mode, mode))
            self.assertTrue(body["draft"]["subject"].startswith("Example Programme"), body["draft"]["subject"])
            self.assertTrue(body["draft"]["text"].rstrip().endswith("Sam"))
            self.assertTrue(body["draft"]["ready"], body["draft"]["problems"])

    def test_the_answer_says_whether_the_address_is_outside_the_own_domains(self):
        """The AI menu reads this one answer (#72) to offer its email place for an own address only; no address counts as outside."""
        for email, outside in ((INSIDE, False), (OUTSIDE, True), ("", True)):
            _, body = ask({"project": "ABC", "email": email})
            self.assertIs(body["outside"], outside, email)

    def test_the_offered_items_are_the_open_ones_and_a_pending_decision_only(self):
        _, body = ask({"project": "ABC", "email": INSIDE})
        ids = [i["id"] for i in body["items"]]
        self.assertIn("ABC-D-001", ids)
        self.assertIn("ABC-001", ids)
        for gone in ("ABC-A-004", "ABC-D-002", "ABC-A-005"):          # closed, made, and one that says confidential
            self.assertNotIn(gone, ids)

    def test_an_own_address_starts_with_everything_ticked_and_an_outside_one_leaves_internal_items_unticked(self):
        _, inside = ask({"project": "ABC", "email": INSIDE})
        _, outside = ask({"project": "ABC", "email": OUTSIDE})
        self.assertIn("ABC-A-003", inside["picked"])
        self.assertNotIn("ABC-A-003", outside["picked"])
        flagged = {i["id"] for i in outside["items"] if i["internal"]}
        self.assertEqual(flagged, {"ABC-A-003"})
        self.assertFalse(any(i["internal"] for i in inside["items"]))
        self.assertNotIn("ABC-A-003", outside["draft"]["ids"])
        self.assertEqual(outside["draft"]["internal_ids"], [])

    def test_no_address_or_no_own_domains_counts_as_outside(self):
        _, none = ask({"project": "ABC"})
        self.assertNotIn("ABC-A-003", none["picked"])
        _, unset = ask({"project": "ABC", "email": INSIDE}, profile=lambda: feed.SAFE_PROFILE)
        self.assertNotIn("ABC-A-003", unset["picked"])
        self.assertIn(de.NO_SENDER, unset["draft"]["problems"])        # no name yet: the next step is plain, the draft is not ready
        self.assertFalse(unset["draft"]["ready"])

    def test_ticking_an_internal_item_for_an_outside_address_is_noted_and_kept_out_of_nothing_else(self):
        _, body = ask({"project": "ABC", "email": OUTSIDE, "picked": ["ABC-A-001", "ABC-A-003"]})
        self.assertEqual(body["picked"], ["ABC-A-001", "ABC-A-003"])
        self.assertEqual(body["draft"]["internal_ids"], ["ABC-A-003"])

    def test_a_peek_offers_the_one_item_and_picks_the_mode_from_it(self):
        _, late = ask({"project": "ABC", "item": "ABC-A-001", "email": INSIDE})
        self.assertEqual(([i["id"] for i in late["items"]], late["mode"]), (["ABC-A-001"], "chase"))
        _, dec = ask({"project": "ABC", "item": "ABC-D-001", "email": INSIDE})
        self.assertEqual(dec["mode"], "decision")
        _, soon = ask({"project": "ABC", "item": "ABC-A-002", "email": INSIDE})
        self.assertEqual(soon["mode"], "update_request")
        _, set_ = ask({"project": "ABC", "item": "ABC-A-001", "email": INSIDE, "mode": "update_request"})
        self.assertEqual(set_["mode"], "update_request")

    def test_a_closed_item_in_the_project_is_known_but_not_offered(self):
        status, body = ask({"project": "ABC", "item": "ABC-A-004", "email": INSIDE})
        self.assertEqual((status, body["items"], body["draft"]["ready"]), (200, [], False))

    def test_an_owner_offers_their_open_items_and_a_chase_only_the_overdue_ones(self):
        _, mine = ask({"project": "ABC", "owner": "dana hart", "email": INSIDE})
        self.assertNotIn("ABC-A-006", [i["id"] for i in mine["items"]])
        self.assertIn("ABC-A-001", [i["id"] for i in mine["items"]])
        _, chase = ask({"project": "ABC", "owner": "Dana Hart", "mode": "chase", "email": INSIDE})
        self.assertEqual([i["id"] for i in chase["items"]], ["ABC-A-001"])

    def test_options_reach_the_email(self):
        _, body = ask({"project": "ABC", "email": INSIDE, "picked": ["ABC-A-001"], "reply_by": "2026-10-16",
                       "include_update": True, "name": "Dana Hart"})
        text = body["draft"]["text"]
        self.assertIn("Friday 16-10-2026", text)
        self.assertIn("Latest update: Plan in draft", text)
        self.assertTrue(text.startswith("Good morning, Dana,"), text[:40])
        _, dec = ask({"project": "ABC", "mode": "decision", "email": INSIDE, "picked": ["ABC-D-001"], "unblocks": "the Phase 2 plan"})
        self.assertIn("the Phase 2 plan", dec["draft"]["text"])

    def test_text_fields_are_flattened_to_one_line(self):
        _, body = ask({"project": "ABC", "email": INSIDE, "name": "Dana\r\nBcc: x@evil.test", "unblocks": "a b"})
        for field in ("to", "subject"):
            self.assertFalse(re.search("[\r\n  ]", body["draft"][field]), field)
        self.assertNotIn(" ", body["draft"]["text"].split("\n")[2])

    def test_every_bad_input_is_refused_in_plain_words_and_the_store_is_not_read_when_the_shape_is_wrong(self):
        bad = [({"project": "abc"}, "bad_project_code"), ({"project": 5}, "bad_project_code"), ({}, "bad_project_code"),
               ({"project": "ABC", "mode": "send"}, "bad_mode"), ({"project": "ABC", "mode": ["chase"]}, "bad_mode"),
               ({"project": "ABC", "reply_by": "13-10-2026"}, "bad_date"), ({"project": "ABC", "reply_by": "2026-02-30"}, "bad_date"),
               ({"project": "ABC", "reply_by": 5}, "bad_date"),
               ({"project": "ABC", "email": "nobody"}, "bad_address"), ({"project": "ABC", "email": "a@b.c\nBcc: d@e.f"}, "bad_address"),
               ({"project": "ABC", "email": "x" * 300 + "@a.test"}, "bad_text"), ({"project": "ABC", "name": 5}, "bad_text"),
               ({"project": "ABC", "unblocks": "x" * 201}, "bad_text"), ({"project": "ABC", "owner": ["a"]}, "bad_text"),
               ({"project": "ABC", "picked": "ABC-A-001"}, "bad_pick"), ({"project": "ABC", "picked": ["x'; DROP TABLE actions;--"]}, "bad_pick"),
               ({"project": "ABC", "picked": [5]}, "bad_pick"), ({"project": "ABC", "picked": ["ABC-A-001"] * 201}, "bad_pick"),
               ({"project": "ABC", "picked": ["ABC-A-999"]}, "bad_pick"), ({"project": "ABC", "picked": ["XYZ-A-001"]}, "bad_pick"),
               ({"project": "ABC", "include_update": "yes"}, "bad_request"), ({"project": "ABC", "item": 5}, "bad_request"),
               ({"project": "ABC", "item": "../../etc/passwd"}, "bad_request"), ({"project": "ABC", "extra": 1}, "bad_request"),
               ({"project": "ABC", "item": "ABC-A-001", "owner": "Dana Hart"}, "bad_request"), ([], "bad_request"), ("x", "bad_request")]
        for req, code in bad:
            calls = Calls()
            status, body = seam(calls)(req)
            self.assertEqual((status, body["ok"], body["code"]), (400, False, code), req)
            self.assertRegex(body["message"], r"[.?]$")
            self.assertNotRegex(body["message"], r"(?i)sqlite|traceback|select |database|\.py|/")
            self.assertFalse(body["message"].lower().startswith("clark"), body["message"])
            if req not in ({"project": "ABC", "picked": ["ABC-A-999"]}, {"project": "ABC", "picked": ["XYZ-A-001"]}):
                self.assertEqual(calls.reads, [], req)         # a malformed request never reaches the store

    def test_an_unknown_project_or_item_is_404(self):
        status, body = ask({"project": "ZZZ"})
        self.assertEqual((status, body["code"], body["message"]), (404, "project_not_found", sv.MESSAGES["project_not_found"]))
        self.assertEqual(feed.NO_PROJECT, sv.MESSAGES["project_not_found"])
        self.assertEqual(feed.BAD_CODE, sv.MESSAGES["bad_project_code"])
        status, body = ask({"project": "ABC", "item": "ABC-A-999"})
        self.assertEqual((status, body["code"]), (404, "bad_item"))

    def test_an_item_of_another_project_is_not_found(self):
        status, body = ask({"project": "ABC", "item": "XYZ-A-001"})
        self.assertEqual((status, body["code"]), (404, "bad_item"))

    def test_an_odd_address_is_refused(self):
        for bad in ("<x@y.test>", "x@y.test?bcc=q%40z.test", "x@y.test\u202e", "x@y\u200b.test", "a b@y.test", 'x"@y.test', "x@y.test;z@y.test"):
            status, body = seam()({"project": "ABC", "email": bad})
            self.assertEqual((status, body["code"]), (400, "bad_address"), repr(bad))
        self.assertEqual(seam()({"project": "ABC", "email": "dana.o'hart+uat@partner.test"})[0], 200)

    def test_a_look_alike_letter_does_not_hide_a_confidential_item(self):
        data = dict(DATA, actions=[action(7, "Conf\u0456dential figures", "2026-10-20")])       # a Cyrillic "i" in the word
        _, body = seam(Calls(data))({"project": "ABC", "email": INSIDE})
        self.assertNotIn("ABC-A-007", [i["id"] for i in body["items"]])

    def test_nothing_is_written_and_the_answer_holds_no_database_columns(self):
        calls = Calls()
        before = json.dumps(DATA, sort_keys=True)
        _, body = seam(calls)({"project": "ABC", "email": OUTSIDE})
        self.assertEqual(json.dumps(DATA, sort_keys=True), before)
        self.assertEqual(calls.reads, ["ABC"])
        dumped = json.dumps(body)
        for word in ("source", "raised", "client_message", "updated_at", "use_case"):
            self.assertNotIn(word, dumped)

    def test_the_reading_seam_has_no_write_or_mail_calls(self):
        text = (SRC / "clark" / "draft_email_feed.py").read_text(encoding="utf-8")
        reading = text.split('# ---- "I sent it"')[0]                         # the one writer, make_sent, comes after this line
        code = "\n".join(l for l in reading.splitlines() if not l.lstrip().startswith("#"))
        for word in ("open(", "write", "sqlite3", "smtplib", "subprocess", "os.system", "webbrowser", "urllib", "socket", "requests"):
            if word in code.split('"""', 2)[2]:
                self.fail(f"the reading half of draft_email_feed.py holds {word!r}")

    def test_the_sent_seam_writes_only_through_the_one_store_method_and_has_no_mail_calls(self):
        text = (SRC / "clark" / "draft_email_feed.py").read_text(encoding="utf-8")
        sent = text.split('# ---- "I sent it"')[1]
        code = "\n".join(l for l in sent.splitlines() if not l.lstrip().startswith("#"))
        for word in ("open(", "sqlite3", "smtplib", "subprocess", "os.system", "webbrowser", "urllib", "socket", "requests", "execute"):
            if word in code:
                self.fail(f"the sent seam holds {word!r}")
        self.assertEqual(code.count("log_email_sent("), 1)


class OnTheRealStore(unittest.TestCase):
    """The seam against store.data_for and publish's own rules, not a hand-made dict: a row the client's file leaves out must not
    reach a client's email either (Sensitive, in the report's hidden list, archived, another project's), and nothing is written."""
    OUT = "dana@partner.test"

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
        mk = lambda **kw: self.demo.action(owner="Dana Hart", status="Open", client_visible=1, **kw)
        self.plain = mk(description="Share the UAT plan")
        self.sensitive = mk(description="Review the supplier terms")
        self.hidden = mk(description="Prepare the steering pack")
        self.archived = mk(description="Retired task")
        self.internal = self.demo.action(description="Check the vendor margin", owner="Dana Hart", status="Open", client_visible=0)
        with self.store.step("dashboard", USER) as st:
            st.create("actions", {"project": "XYZ", "description": "Other project's work", "owner": "Dana Hart", "raised": "2026-10-01",
                                  "source": "demo", "status": "Open", "client_visible": 1})
            st.create("item_labels", {"item_id": self.sensitive, "label": "Sensitive"})
            st.create("report_hidden", {"project": "ABC", "item_id": self.hidden})
            st.archive("actions", self.archived)
        self.rules = lambda code: feed.rules_from_inputs(publish.read_inputs(self.store, code, "2026-10-12"))
        self.seam = feed.make(self.store.data_for, profile=profile, clock=lambda: NOW, rules_for=self.rules)

    def fingerprint(self):
        con = sqlite3.connect(f"file:{self.store.path}?mode=ro", uri=True)
        try:
            counts = {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()}
        finally:
            con.close()
        return hashlib.sha256(self.store.path.read_bytes()).hexdigest(), counts

    def ask(self, **req):
        status, body = self.seam({"project": "ABC", **req})
        self.assertEqual(status, 200, body)
        return body

    def test_a_client_email_offers_only_what_the_clients_file_would_hold_and_nothing_else_is_ticked(self):
        for email in (self.OUT, ""):
            got = self.ask(email=email)
            offered = {i["id"] for i in got["items"]}
            self.assertIn(self.plain, offered)
            self.assertNotIn(self.hidden, offered, "a row in the report's hidden list is never in an email")
            self.assertNotIn(self.sensitive, offered, "a Sensitive row is not offered to an outside address")
            self.assertNotIn(self.archived, offered)
            self.assertFalse({i for i in offered if i.startswith("XYZ")}, "another project's row")
            self.assertNotIn(self.hidden, got["picked"])
            self.assertNotIn(self.sensitive, got["picked"])
            text = json.dumps(got["draft"])
            for word in ("steering pack", "supplier terms", "Retired task", "Other project"):
                self.assertNotIn(word, text, word)
            self.assertNotIn(self.internal, got["picked"], "a client-visible = 0 row starts unticked for an outside address")

    def test_the_peek_and_the_owners_list_follow_the_same_rules(self):
        for ask in ({"item": self.sensitive}, {"item": self.hidden}):
            status, body = self.seam({"project": "ABC", "email": self.OUT, **ask})
            self.assertTrue(status == 404 or ask["item"] not in body.get("picked", []) and ask["item"] not in {i["id"] for i in body.get("items", [])},
                            (status, body))
        got = self.ask(owner="Dana Hart", email=self.OUT)
        self.assertFalse({self.hidden, self.sensitive} & {i["id"] for i in got["items"]})

    def test_a_sensitive_row_may_go_to_an_own_address_but_a_hidden_one_never_does(self):
        got = self.ask(email=INSIDE)
        offered = {i["id"] for i in got["items"]}
        self.assertIn(self.sensitive, offered)
        self.assertNotIn(self.hidden, offered)

    def test_an_archived_project_is_refused(self):
        with self.store.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        status, body = self.seam({"project": "ABC"})
        self.assertEqual((status, body["code"]), (409, "project_archived"))

    def test_nothing_is_written(self):
        before = self.fingerprint()
        for email in (self.OUT, INSIDE, ""):
            self.ask(email=email)
            self.ask(email=email, owner="Dana Hart")
            self.ask(email=email, item=self.plain)
        self.assertEqual(self.fingerprint(), before)


class Sent(unittest.TestCase):
    """POST /api/draft-email/sent on a real store: one record, never any words of the email, and a refusal writes nothing."""
    DAY = "2026-10-28"

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.a = self.demo.action(description="Share the plan", owner="Dana Hart", status="Open")
        self.b = self.demo.action(description="Book the room", owner="Dana Hart", status="Open")
        self.seam = feed.make_sent(self.store.path, [], by_user="Sam Lee", today=date(2026, 10, 28))
        self.running = Running(draft_email_sent=self.seam)
        self.addCleanup(self.running.close)

    def fingerprint(self):
        con = sqlite3.connect(f"file:{self.store.path}?mode=ro", uri=True)
        try:
            counts = {t: con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0] for (t,) in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()}
        finally:
            con.close()
        return hashlib.sha256(self.store.path.read_bytes()).hexdigest(), counts

    def post(self, body, **kw):
        raw = json.dumps(body).encode() if not isinstance(body, bytes) else body
        status, _, data = self.running.api("POST", "/api/draft-email/sent", raw, **kw)
        return status, json.loads(data)

    def good(self, **over):
        return {"project": "ABC", "ids": [self.a, self.b], "mode": "chase", "day": self.DAY, **over}

    def test_a_good_request_records_one_row_for_the_login_name_not_one_the_request_gave(self):
        status, body = self.post(self.good())
        self.assertEqual((status, body["ok"]), (200, True), body)
        (row,) = self.store.email_sent_for("ABC")
        self.assertEqual((row["seq"], row["by_user"], row["mode"], row["day"], row["ids"]), (body["seq"], "Sam Lee", "chase", self.DAY, sorted([self.a, self.b])))

    def test_the_same_record_while_one_is_being_written_is_refused_not_written_twice(self):
        # #258: an in-flight guard in the seam (the page also disables the button until the reply).
        import threading
        started, release = threading.Event(), threading.Event()
        real = feed._call
        calls = []

        def slow(*a, **k):
            calls.append(1)
            started.set()
            release.wait(5)
            return real(*a, **k)
        results = []
        feed._call = slow
        self.addCleanup(setattr, feed, "_call", real)
        t = threading.Thread(target=lambda: results.append(self.seam(self.good())))
        t.start()
        self.assertTrue(started.wait(5))
        status, body = self.seam(self.good(ids=[self.b, self.a]))          # the same ids in another order
        self.assertEqual((status, body["code"] if "code" in body else body.get("error")), (409, "already_recording"), body)
        self.assertEqual(body["message"], feed.BUSY_SENT)
        self.assertNotIn(self.a, body["message"])
        release.set()
        t.join(5)
        self.assertEqual(results[0][0], 200)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.store.email_sent_for("ABC")), 1)
        self.assertEqual(self.seam(self.good())[0], 200, "once the first is done the guard is released")

    def test_every_refusal_writes_nothing(self):
        before = self.fingerprint()
        bad = [self.good(extra="x"), self.good(text="Hello Dana, please send the plan"), self.good(email="dana@partner.test"),
               self.good(by_user="Someone Else"), {"project": "ABC", "ids": [self.a], "mode": "chase"},
               self.good(project="abc"), self.good(project=5), self.good(mode="reminder"), self.good(mode=None),
               self.good(ids=[]), self.good(ids="ABC-A-001"), self.good(ids=[1]), self.good(ids=["not an id"]),
               self.good(ids=[f"ABC-A-{n:03d}" for n in range(1, 52)]), self.good(ids=[self.a, "ABC-A-999"]),
               self.good(day="2026-02-30"), self.good(day="28-10-2026"), self.good(day=20261028), self.good(day="2026-11-05"),
               self.good(project="XYZ"), [1, 2, 3], "text"]
        for body in bad:
            status, got = self.post(body)
            self.assertIn(status, (400, 404, 409), (body, got))
            self.assertFalse(got["ok"], body)
            self.assertNotRegex(got["message"], r"(?i)traceback|sqlite|\bsql\b|exception")
        self.assertEqual(self.fingerprint(), before)

    def test_the_email_words_never_reach_the_database_file(self):
        self.post(self.good(text="PLANTED-WORDS-xyzzy", email="planted@partner.test"))
        self.post(self.good())
        raw = self.store.path.read_bytes()
        self.assertNotIn(b"PLANTED-WORDS-xyzzy", raw)
        self.assertNotIn(b"planted@partner.test", raw)

    def test_the_token_host_and_origin_and_the_size_limit_come_first(self):
        raw = json.dumps(self.good()).encode()
        h = {"Content-Type": "application/json", "Content-Length": str(len(raw))}
        before = self.fingerprint()
        self.assertEqual(self.running.ask("POST", "/api/draft-email/sent", h, raw)[0], 403)
        self.assertEqual(self.running.api("POST", "/api/draft-email/sent", raw, token="wrong")[0], 403)
        self.assertEqual(self.running.api("POST", "/api/draft-email/sent", raw, host="evil.example")[0], 403)
        self.assertEqual(self.running.api("POST", "/api/draft-email/sent", raw, extra={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.running.api("POST", "/api/draft-email/sent", raw, ctype="text/plain")[0], 415)
        big = json.dumps(self.good(ids=[self.a], pad="x" * 4096)).encode()
        self.assertEqual(self.running.api("POST", "/api/draft-email/sent", big)[0], 400)
        self.assertEqual(self.fingerprint(), before)

    def test_no_seam_is_404(self):
        running = Running()
        self.addCleanup(running.close)
        self.assertEqual(running.api("POST", "/api/draft-email/sent", json.dumps(self.good()).encode())[0], 404)

    def test_three_chases_are_what_the_next_draft_remembers(self):
        reader = feed.make(self.store.data_for, profile=profile, clock=lambda: NOW,
                           chased=lambda code: feed.chase_counts_of(self.store.email_sent_for(code)))
        first = reader({"project": "ABC", "mode": "chase", "picked": [self.a]})[1]["draft"]["text"]
        for day in ("2026-10-20", "2026-10-22", "2026-10-26"):
            self.post(self.good(ids=[self.a], day=day))
        self.post(self.good(ids=[self.a], mode="update_request"))
        after = reader({"project": "ABC", "mode": "chase", "picked": [self.a]})[1]["draft"]["text"]
        self.assertNotEqual(first, after)
        self.assertIn("chased it three times", after.replace("3 times", "three times"))


class Route(unittest.TestCase):
    def setUp(self):
        self.calls = Calls()
        self.running = Running(draft_email=seam(self.calls))
        self.addCleanup(self.running.close)

    def post(self, body, **kw):
        status, _, data = self.running.api("POST", "/api/draft-email", json.dumps(body).encode() if not isinstance(body, bytes) else body, **kw)
        return status, json.loads(data)

    def test_a_good_request_is_answered(self):
        status, body = self.post({"project": "ABC", "mode": "chase", "email": INSIDE})
        self.assertEqual((status, body["ok"], body["draft"]["mode"]), (200, True, "chase"))

    def test_the_token_host_and_origin_come_first(self):
        raw = b'{"project": "ABC"}'
        h = {"Content-Type": "application/json", "Content-Length": str(len(raw))}
        self.assertEqual(self.running.ask("POST", "/api/draft-email", h, raw)[0], 403)               # no token
        self.assertEqual(self.running.api("POST", "/api/draft-email", raw, token="wrong")[0], 403)
        self.assertEqual(self.running.api("POST", "/api/draft-email", raw, host="evil.example")[0], 403)
        self.assertEqual(self.running.api("POST", "/api/draft-email", raw, extra={"Origin": "http://evil.example"})[0], 403)
        self.assertEqual(self.running.api("POST", "/api/draft-email", raw, ctype="text/plain")[0], 415)
        self.assertEqual(self.calls.reads, [])

    def test_bad_json_and_bad_inputs_are_400_and_an_unknown_project_404(self):
        self.assertEqual(self.running.api("POST", "/api/draft-email", b"{nope")[0], 400)
        self.assertEqual(self.post({"project": "abc"})[0], 400)
        self.assertEqual(self.post({"project": "ABC", "picked": ["ABC-A-1'; --"]})[0], 400)
        self.assertEqual(self.post({"project": "ABC", "item": "ABC-A-998"})[0], 404)
        self.assertEqual(self.post({"project": "ZZZ"})[0], 404)
        self.assertEqual(self.post([1, 2])[0], 400)

    def test_the_body_limit_is_16_kib(self):
        limit = sv.ROUTE_BODY_LIMITS["/api/draft-email"]
        self.assertEqual(limit, 16 * 1024)
        over = {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json", "Content-Length": str(limit + 1)}
        status, _, data = self.running.ask("POST", "/api/draft-email", over, b"{}")
        self.assertEqual((status, json.loads(data)["code"]), (400, "too_large"))
        pad = b'{"project": "ABC", "unblocks": "' + b"x" * (limit - 34) + b'"}'
        self.assertEqual(len(pad), limit)
        status, body = self.post(pad)
        self.assertEqual((status, body["code"]), (400, "bad_text"))                  # fits the route; the seam says it is too long
        self.assertEqual(self.running.api("POST", "/api/draft-email", pad + b" ")[0], 400)

    def test_other_methods_are_not_routes(self):
        self.assertEqual(self.running.api("GET", "/api/draft-email")[0], 404)         # after the token
        self.assertEqual(self.running.ask("GET", "/api/draft-email")[0], 403)
        for method in ("PUT", "DELETE", "PATCH"):
            self.assertEqual(self.running.api(method, "/api/draft-email", b"{}")[0], 501, method)        # clark has no handler: its plain 501
        self.assertEqual(self.running.api("POST", "/api/draft-email/", b"{}")[0], 404)

    def test_no_seam_is_404(self):
        running = Running()
        self.addCleanup(running.close)
        status, _, data = running.api("POST", "/api/draft-email", b'{"project": "ABC"}')
        self.assertEqual((status, json.loads(data)["code"]), (404, "not_found"))

    def test_a_fault_in_the_seam_is_the_plain_500(self):
        def broken(req):
            raise RuntimeError("/Users/someone/clark.db is locked")
        running = Running(draft_email=broken)
        self.addCleanup(running.close)
        with self.assertLogs("clark.server", "ERROR"):
            status, _, data = running.api("POST", "/api/draft-email", b"{}")
        self.assertEqual((status, json.loads(data)["message"]), (500, sv.MESSAGES["server_error"]))

    def test_the_route_calls_no_other_part_of_the_server(self):
        handler = mock.Mock()
        handler.server.draft_email = lambda req: (200, {"ok": True, "got": req})
        sv.draft_email_route("draft_email")(handler, {"a": 1})
        handler.send.assert_called_once_with(200, {"ok": True, "got": {"a": 1}})


class EditorShape(unittest.TestCase):
    """The editor's onChange state and the route's request name the same things."""

    def snake(self, name):
        return re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), name)

    def test_the_state_keys_the_editor_changes_are_request_keys(self):
        src = (SRC / "clark" / "page" / "src" / "components" / "DraftEmail.jsx").read_text(encoding="utf-8")
        keys = set(re.findall(r"change\(\{\s*(\w+)\s*:", src))
        self.assertEqual(keys, {"mode", "picked", "replyBy", "unblocks", "includeUpdate"})
        for key in keys:
            self.assertIn(self.snake(key), feed.KEYS, key)

    def test_what_the_editor_reads_back_is_in_the_answer(self):
        _, body = ask({"project": "ABC", "email": INSIDE})
        for key in ("html", "text", "to", "subject", "ids", "internal_ids", "problems"):
            self.assertIn(key, body["draft"], key)
        for item in body["items"]:
            self.assertTrue({"id", "text"} <= set(item))
        self.assertIsInstance(body["picked"], list)


if __name__ == "__main__":
    unittest.main()

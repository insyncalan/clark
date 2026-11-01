"""#97: GET /api/draft?project=<CODE>&item=<ID>, the Draft email of the right-click menu (server.draft_route, draft_read.make_read).

Run: python3 dev/run_tests.py test_draft_route
The route is read only: it is behind authorised(), takes a single project and a single item of a known shape, accepts no body and no
other parameter, answers 404 for a missing project or item, and returns only fields a report may carry (publish.read_inputs). A
sensitive or hidden item and another project's item never come back. All rows are fictional.
"""
import http.client
import json
import sqlite3
import threading
import unittest
from urllib.parse import quote

from _demo import USER, DemoStore
from clark import draft_read, publish, server as sv

SECRET = "Fictional secret supplier margin"


class Profile:
    def __init__(self, name="Sam Example", domains=()):
        self.name, self.domains = name, list(domains)

    def who(self):
        return self.name

    def own_domains(self):
        return self.domains


class Rig(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.a = self.demo.action(owner="Dana Hart", due_date="2026-10-09", latest_update="Plan in draft")
        self.secret = self.demo.action(description=SECRET)
        self.shy = self.demo.action(description="Hidden by the eye")
        self.off = self.demo.action(description="Marked internal", client_visible=0)
        with self.s.step("dashboard", USER) as st:
            self.r = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier slips", "impact": "High",
                                        "likelihood": "Medium", "owner": "Dana Hart", "response_action": "WORKING NOTE ONLY",
                                        "raised": "2026-10-01", "source": "demo"})
            self.d = st.create("decisions", {"project": "ABC", "decision": "Use the new tool", "status": "Pending",
                                             "made_by": "Dana Hart", "needed_by": "2030-01-05", "source": "demo"})
            st.update("actions", self.secret, {"labels": ["Sensitive"]})
            st.create("report_hidden", {"project": "ABC", "item_id": self.shy})
            st.create("projects", {"code": "XYZ", "name": "Other Programme", "health": "On track"})
            self.other = st.create("actions", {"project": "XYZ", "description": "Fictional other-project text", "raised": "2026-10-01",
                                               "source": "demo"})
        self.profile = Profile()
        self.clock = "2026-10-13 09:00"
        read = draft_read.make_read(lambda code: publish.read_inputs(self.s, code), self.profile, lambda: self.clock)
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=self.s.data_for, draft=read)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)

    def get(self, query, token=None, body=None, headers=None, method="GET"):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=10)
        try:
            h = {"Host": f"127.0.0.1:{self.httpd.server_port}", **(headers or {})}
            if token is not False:
                h[sv.TOKEN_HEADER] = token or sv.TOKEN
            if body is not None:
                h["Content-Length"] = str(len(body))
            conn.request(method, "/api/draft" + query, body, h)
            r = conn.getresponse()
            return r.status, json.loads(r.read() or b"null")
        finally:
            conn.close()

    def draft(self, item, **more):
        extra = "".join(f"&{k}={quote(v)}" for k, v in more.items())
        return self.get(f"?project=ABC&item={item}{extra}")


class Answers(Rig):
    def test_an_action_gives_what_the_dialog_needs_and_sends_nothing(self):
        status, got = self.draft(self.a)
        self.assertEqual(status, 200, got)
        self.assertEqual(sorted(got), ["draft", "item", "items", "ok", "project", "reason", "state", "today"])
        self.assertEqual((got["ok"], got["project"], got["item"], got["today"]), (True, "ABC", self.a, "2026-10-13"))
        self.assertEqual(got["items"], [{"id": self.a, "text": "Draft the cut-over plan"}])
        self.assertEqual(got["state"], {"mode": "chase", "picked": [self.a], "replyBy": "", "unblocks": "", "includeUpdate": False})
        d = got["draft"]
        self.assertEqual((d["to"], d["ids"], d["ready"], d["problems"]), ("", [self.a], True, []))
        self.assertIn(self.a, d["subject"])
        self.assertIn("Example Programme", d["subject"])
        self.assertIn("overdue", d["text"])
        self.assertEqual(got["reason"], draft_read.REASON)
        self.assertIn("no People list", got["reason"])

    def test_a_risk_and_a_decision_open_in_their_own_kind(self):
        status, risk = self.draft(self.r)
        self.assertEqual((status, risk["state"]["mode"]), (200, "update_request"))
        self.assertIn("Risk: Supplier slips", risk["draft"]["text"])
        self.assertNotIn("Response:", risk["draft"]["text"])           # a response is a working note: not read, and no line says it is missing
        self.assertNotIn("WORKING NOTE ONLY", json.dumps(risk))
        status, dec = self.draft(self.d)
        self.assertEqual((status, dec["state"]["mode"]), (200, "decision"))

    def test_the_options_change_the_draft_and_are_checked(self):
        status, got = self.draft(self.a, mode="update_request", reply_by="2026-10-20", unblocks="the go-live", include_update="1")
        self.assertEqual(status, 200, got)
        self.assertEqual(got["state"], {"mode": "update_request", "picked": [self.a], "replyBy": "2026-10-20", "unblocks": "the go-live",
                                        "includeUpdate": True})
        self.assertIn("Latest update: Plan in draft", got["draft"]["text"])
        self.assertIn("20-10-2026", got["draft"]["text"])
        status, none = self.draft(self.a, picked="none")
        self.assertEqual((status, none["draft"]["ready"], none["draft"]["problems"]),
                         (200, False, ["No items are ticked. Tick at least one to draft the email."]))
        for bad in ("mode=send", "mode=", "picked=ABC-A-999", "reply_by=tomorrow", "reply_by=2026-13-45", "include_update=yes",
                    "unblocks=" + "x" * 201, "unblocks=a%0Ab"):
            with self.subTest(bad=bad):
                status, got = self.get(f"?project=ABC&item={self.a}&{bad}")
                self.assertEqual((status, got["ok"], got["code"]), (400, False, "bad_draft"), got)
                self.assertTrue(got["message"].endswith(".") and "Traceback" not in got["message"])

    def test_the_sender_signs_and_without_a_name_the_problem_is_said_in_words(self):
        status, got = self.draft(self.a)
        self.assertIn("Sam", got["draft"]["text"])
        self.profile.name = ""
        status, got = self.draft(self.a)
        self.assertEqual((status, got["draft"]["problems"]), (200, [draft_read.draft_email.NO_SENDER]))

    def test_an_item_marked_internal_is_flagged_not_hidden_from_the_person(self):
        status, got = self.draft(self.off)
        self.assertEqual(status, 200)
        self.assertEqual(got["draft"]["internal_ids"], [self.off])


class Safe(Rig):
    def test_a_sensitive_item_and_one_left_off_the_report_give_no_text(self):
        for ref, text in ((self.secret, SECRET), (self.shy, "Hidden by the eye")):
            with self.subTest(ref=ref):
                status, got = self.draft(ref)
                self.assertEqual(status, 200)
                self.assertEqual((got["items"], got["draft"]["ids"], got["draft"]["ready"]), ([], [], False))
                self.assertNotIn(text, json.dumps(got))

    def test_only_the_columns_a_report_may_carry_are_in_the_reply(self):
        text = json.dumps(self.draft(self.r)[1]) + json.dumps(self.draft(self.a)[1])
        for planted in ("WORKING NOTE ONLY", "demo"):                  # the response note and the source
            self.assertNotIn(planted, text.replace("Demo User", ""))
        keys = set(self.draft(self.a)[1]["draft"]["items"][0])
        self.assertTrue(keys <= set(draft_read.draft_email.ITEM_KEYS), keys)

    def test_another_projects_item_is_not_found_by_either_project(self):
        for query in (f"?project=ABC&item={self.other}", f"?project=XYZ&item={self.a}"):
            status, got = self.get(query)
            self.assertEqual((status, got["ok"], got["code"]), (404, False, "item_not_found"), query)
        status, got = self.get(f"?project=XYZ&item={self.other}")
        self.assertEqual(status, 200)

    def test_an_archived_item_a_milestone_and_a_use_case_are_not_found(self):
        gone = self.demo.action(description="To be archived")
        with self.s.step("dashboard", USER) as st:
            st.archive("actions", gone)
        for ref in (gone, "ABC-A-999", self.demo.milestone, self.demo.use_case):
            status, got = self.draft(ref)
            self.assertEqual(status, 404 if ref not in (self.demo.milestone, self.demo.use_case) else 400, (ref, got))

    def test_nothing_is_written(self):
        con = sqlite3.connect(str(self.s.path))
        before = [con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log", "item_events", "report_hidden")]
        for item in (self.a, self.r, self.d, self.secret):
            self.draft(item)
        self.draft(self.a, mode="chase")
        after = [con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log", "item_events", "report_hidden")]
        con.close()
        self.assertEqual(before, after)


class Guarded(Rig):
    def test_the_token_is_needed_and_a_stale_one_says_reload(self):
        self.assertEqual(self.get(f"?project=ABC&item={self.a}", token=False)[0], 403)
        status, got = self.get(f"?project=ABC&item={self.a}", token="old")
        self.assertEqual((status, got.get("stale")), (403, True))

    def test_another_sites_origin_and_host_are_refused(self):
        self.assertEqual(self.get(f"?project=ABC&item={self.a}", headers={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.get(f"?project=ABC&item={self.a}", headers={"Host": "evil.example"})[0], 403)

    def test_a_bad_project_a_bad_item_and_extra_or_repeated_parameters(self):
        cases = ((f"?item={self.a}", "bad_project_code"), (f"?project=abc&item={self.a}", "bad_project_code"),
                 (f"?project=ABC%0A&item={self.a}", "bad_project_code"), (f"?project=ABC&project=XYZ&item={self.a}", "bad_draft"),
                 ("?project=ABC", "bad_item"), ("?project=ABC&item=", "bad_item"), ("?project=ABC&item=ABC-A-1", "bad_item"),
                 ("?project=ABC&item=abc-a-001", "bad_item"), ("?project=ABC&item=ABC-M-001", "bad_item"),
                 ("?project=ABC&item=ABC-A-001%0A", "bad_item"), ("?project=ABC&item=ABC-A-001%27%3B--", "bad_item"),
                 (f"?project=ABC&item={self.a}&item={self.r}", "bad_draft"), (f"?project=ABC&item={self.a}&to=a@b.test", "bad_draft"),
                 (f"?project=ABC&item={self.a}&mode=chase&mode=chase", "bad_draft"), ("", "bad_project_code"))
        for query, code in cases:
            with self.subTest(query=query):
                status, got = self.get(query)
                self.assertEqual((status, got["ok"], got["code"] if "code" in got else None), (400, False, code), got)

    def test_a_missing_project_is_404(self):
        status, got = self.get(f"?project=NOP&item=NOP-A-001")
        self.assertEqual((status, got["code"]), (404, "project_not_found"))

    def test_no_body_is_accepted_and_only_get_exists(self):
        status, got = self.get(f"?project=ABC&item={self.a}", body=b'{"to": "x@y.test"}')
        self.assertEqual((status, got["code"]), (400, "bad_request"))
        for method in ("POST", "PUT", "DELETE"):
            status, _ = self.get(f"?project=ABC&item={self.a}", method=method, body=b"{}", headers={"Content-Type": "application/json"})
            self.assertIn(status, (404, 501), method)

    def test_without_the_seam_the_route_is_not_there(self):
        self.httpd.draft = None
        self.assertEqual(self.get(f"?project=ABC&item={self.a}")[0], 404)

    def test_a_fault_is_a_plain_500_and_names_nothing(self):
        def boom(code, item, opts):
            raise RuntimeError("/secret/path broke")
        self.httpd.draft = boom
        with self.assertLogs("clark.server", "ERROR"):
            status, got = self.get(f"?project=ABC&item={self.a}")
        self.assertEqual((status, got["code"]), (500, "server_error"))
        self.assertNotIn("secret", json.dumps(got))


class Pieces(unittest.TestCase):
    def test_the_route_is_listed_and_the_words_are_plain(self):
        self.assertIn("/api/draft", sv.GET_ROUTES)
        self.assertNotIn("/api/draft", sv.POST_ROUTES)
        for code in ("bad_item", "item_not_found", "bad_draft"):
            self.assertTrue(sv.MESSAGES[code].endswith("."), code)


if __name__ == "__main__":
    unittest.main()

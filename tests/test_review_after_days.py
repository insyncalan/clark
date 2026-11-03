"""#171: a project's own "not reviewed after N days" (projects.review_after_days), written only through the one writer (changes.py).

Run: python3 dev/run_tests.py test_review_after_days
Four things are pinned here. The writer: one step with Undo and a history line, and a value that is not a whole number from 1 to 365 is
refused in the one plain sentence with nothing written. The read: the value reaches the page in the project's own row of /api/data (no
second route). The feed: the freshness each item carries counts from the project's value. The routes: the same session token, loopback
Host and Origin checks as every other route, on a real server. The migration is in test_store_review_days_migration. Fictional data only.
"""
import http.client
import json
import threading
import unittest
from datetime import datetime, timezone
from unittest import mock

from _demo import USER, DemoStore
from clark import changes, history, publish, server as sv, store as store_module

WORDS = "Choose a whole number of days from 1 to 365. Nothing was changed."
HOSTILE = ["14", "abc", "", " ", "1e2", "14.5", "NaN", None, True, False, 14.5, 0.5, 30.0, float("nan"), float("inf"), -1, 0, 366, 400, 10 ** 12,
           10 ** 40, -(10 ** 40), [14], [], {"days": 14}, {}, (14,)]
CLOCK = [datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)]
TODAY = "2026-10-29"


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def req(self, **fields):
        return {"project": "ABC", "kind": "projects", "op": "update", "changes": fields}

    def ok(self, request):
        status, body = self.change(request)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def days(self):
        return self.s.read("projects", ref="ABC")["review_after_days"]

    def counts(self):
        con = self.s.con
        return tuple(con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("applies", "change_log", "item_events")) + (
            con.execute("SELECT group_concat(health || ifnull(health_reason, '') || review_after_days) FROM projects").fetchone()[0],)

    def refused(self, request):
        before = self.counts()
        status, body = self.change(request)
        self.assertEqual((status, body["ok"], body["message"]), (400, False, WORDS), request)
        self.assertEqual(self.counts(), before, f"nothing was written for {request!r}")


class Setting(Base):
    def test_it_starts_at_14_and_the_sentence_is_the_agreed_one(self):
        self.assertEqual(self.days(), 14)
        self.assertEqual(changes.BAD_REVIEW_DAYS, WORDS)

    def test_a_change_is_one_step_and_one_undo_puts_the_old_number_back(self):
        before = self.counts()
        body = self.ok(self.req(review_after_days=30))
        self.assertEqual(body["project"]["review_after_days"], 30)
        self.assertEqual(self.days(), 30)
        self.assertEqual(self.counts()[0], before[0] + 1, "one step")
        status, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, back)
        self.assertEqual(back["words"], "Put back: the days before an item counts as not reviewed.")
        self.assertEqual(back["project"]["review_after_days"], 14)
        self.assertEqual(self.days(), 14)
        self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 409, "an Undo is used once")

    def test_the_end_numbers_are_taken(self):
        for n in (1, 365, 14, 7, 90):
            with self.subTest(n=n):
                self.ok(self.req(review_after_days=n))
                self.assertEqual((self.days(), type(self.days())), (n, int))

    def test_the_same_number_makes_no_step(self):
        before = self.counts()
        body = self.ok(self.req(review_after_days=14))
        self.assertIsNone(body["apply_id"])
        self.assertEqual(self.counts(), before)

    def test_the_history_says_who_how_and_when_the_number_changed(self):
        body = self.ok({**self.req(review_after_days=21), "place": "menu"})
        rows = [r for r in history.view_for_project(self.s.con, "ABC")["rows"] if r["table"] == "projects" and r["step"] == body["apply_id"]]
        self.assertEqual(len(rows), 1, rows)
        row = rows[0]
        self.assertEqual((row["field"], row["from"], row["to"], row["who"], row["kind"]), ("Not reviewed after (days)", "14", "21", USER, "Changed"))
        self.assertRegex(row["when"], r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}$")
        self.assertEqual(row["how"], history.HOW_TABLE)
        back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})[1]
        undone = [r for r in history.view_for_project(self.s.con, "ABC")["rows"] if r["step"] == back["apply_id"]]
        self.assertEqual([(r["field"], r["from"], r["to"], r["how"]) for r in undone], [("Not reviewed after (days)", "21", "14", history.HOW_UNDO)])

    def test_it_goes_in_the_same_step_as_a_health_change_and_one_undo_takes_both_back(self):
        body = self.ok(self.req(health="At risk", health_reason="Late", review_after_days=7))
        self.assertEqual((self.s.read("projects", ref="ABC")["health"], self.days()), ("At risk", 7))
        status, back = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, back)
        self.assertEqual((self.s.read("projects", ref="ABC")["health"], self.days()), ("On track", 14))

    def test_a_bad_number_beside_a_good_health_change_writes_nothing_of_either(self):
        self.refused(self.req(health="At risk", health_reason="Late", review_after_days=0))
        self.assertEqual(self.s.read("projects", ref="ABC")["health"], "On track")

    def test_a_step_that_also_changed_another_project_field_is_not_undone_from_here(self):
        with self.s.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"review_after_days": 9, "phase": "Build"})
        step = self.demo.last_step()
        self.assertEqual(self.undo({"project": "ABC", "apply_id": step})[0], 400)
        self.assertEqual(self.days(), 9)

    def test_the_list_of_what_may_change_and_what_undo_may_put_back_name_it(self):
        self.assertIn("review_after_days", changes.CHANGE_KINDS["projects"]["update"])
        self.assertIn("review_after_days", changes.UNDOABLE["projects"])
        self.assertTrue(set(changes.CHANGE_KINDS["projects"]["update"]) <= set(changes.UNDOABLE["projects"]))


class Hostile(Base):
    def test_every_hostile_value_is_refused_in_the_one_sentence_with_nothing_written(self):
        for value in HOSTILE:
            with self.subTest(value=repr(value)):
                self.refused(self.req(review_after_days=value))
                self.assertEqual(self.days(), 14, "the old number stays")

    def test_the_old_number_stays_when_it_was_not_the_default(self):
        self.ok(self.req(review_after_days=45))
        for value in HOSTILE:
            with self.subTest(value=repr(value)):
                self.refused(self.req(review_after_days=value))
        self.assertEqual(self.days(), 45)

    def test_a_refused_value_does_not_reach_the_store_at_all(self):
        with mock.patch.object(store_module.Store, "step", side_effect=AssertionError("a step was opened")):
            for value in HOSTILE:
                with self.subTest(value=repr(value)):
                    status, body = self.change(self.req(review_after_days=value))
                    self.assertEqual((status, body["message"]), (400, WORDS))

    def test_the_store_refuses_them_too_if_a_caller_goes_round_the_route(self):
        for value in ("14", "abc", 14.5, True, False, -1, 0, 366, [14], {}, 10 ** 40):
            with self.subTest(value=repr(value)):
                before = self.counts()
                with self.assertRaises(store_module.Invalid):
                    with self.s.step("dashboard", USER) as st:
                        st.update("projects", "ABC", {"review_after_days": value})
                self.assertEqual(self.counts(), before)

    def test_the_other_ways_in_are_shut(self):
        # an id, a second field the route does not know, the number sent as the project's own key: all refused, nothing written
        before = self.counts()
        for request in ({**self.req(review_after_days=20), "id": "ABC"}, self.req(review_after_days=20, name="Renamed"),
                        self.req(**{"review_after_days ": 20}), self.req(Review_After_Days=20)):
            with self.subTest(request=request):
                status, body = self.change(request)
                self.assertEqual((status, body["ok"]), (400, False))
                self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("projects", ref="ABC")["name"], "Example Programme")

    def test_other_kinds_cannot_carry_it(self):
        before = self.counts()
        for kind in ("actions", "milestones", "use_cases", "glance_tiles", "report_sections"):
            with self.subTest(kind=kind):
                status, body = self.change({"project": "ABC", "kind": kind, "op": "update", "id": "ABC-A-001", "changes": {"review_after_days": 5}})
                self.assertEqual((status, body["ok"]), (400, False))
        self.assertEqual(self.counts(), before)


class Read(Base):
    def test_the_project_row_the_page_is_given_carries_it(self):
        self.assertEqual(self.s.data_for("ABC")["project"]["review_after_days"], 14)
        self.ok(self.req(review_after_days=30))
        self.assertEqual(self.s.data_for("ABC")["project"]["review_after_days"], 30)

    def test_the_published_file_carries_none_of_it(self):
        self.ok(self.req(review_after_days=33))
        self.assertNotIn("review_after_days", publish.PUBLISH_FIELDS["projects"])
        built = self.s.publish_inputs("ABC", publish.PUBLISH_FIELDS)
        self.assertNotIn("review_after_days", built["data"]["project"])

    def test_the_one_function_that_gives_n_reads_the_row_and_falls_back_to_14(self):
        f = store_module.review_days_for
        self.assertEqual([f({"review_after_days": n}) for n in (1, 14, 365, 30)], [1, 14, 365, 30])
        for odd in (None, {}, {"review_after_days": None}, {"review_after_days": 0}, {"review_after_days": 366}, {"review_after_days": "14"},
                    {"review_after_days": 14.0}, {"review_after_days": True}):
            with self.subTest(row=odd):
                self.assertEqual(f(odd), 14)


class Feed(Base):
    def setUp(self):
        super().setUp()
        for target, value in (("clark.store.clock", lambda: CLOCK[0]), ("clark.store.today", lambda: TODAY)):
            patcher = mock.patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        CLOCK[0] = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)

    def fresh(self, item):
        return {r["id"]: r for r in self.s.data_for("ABC")["actions"]}[item]["freshness"]

    def test_the_feed_counts_from_the_projects_own_number(self):
        CLOCK[0] = datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc)
        item = self.demo.action()                                        # made by a person 10 days before TODAY
        got = self.fresh(item)
        self.assertEqual((got["days"], got["not_reviewed"]), (14, False))
        self.ok(self.req(review_after_days=9))
        got = self.fresh(item)
        self.assertEqual((got["days"], got["not_reviewed"]), (9, True))
        self.ok(self.req(review_after_days=10))
        self.assertEqual(self.fresh(item)["not_reviewed"], False, "exactly N days is not yet flagged")
        self.ok(self.req(review_after_days=365))
        self.assertEqual((self.fresh(item)["days"], self.fresh(item)["not_reviewed"]), (365, False))

    def test_another_project_keeps_its_own_number(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "DEF", "name": "Other Programme"})
        self.ok(self.req(review_after_days=3))
        self.assertEqual(self.s.data_for("DEF")["project"]["review_after_days"], 14)


class Running:
    """The server on a free port in a thread, with the real data, change and undo handlers (the same checks as every route, no Chrome)."""

    def __init__(self, data_for, change, undo):
        self.httpd = sv.LocalServer((sv.HOST, 0), data_for=data_for, change=change, undo=undo)
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def api(self, method, path, body=None, token=None, extra=None, host="default"):
        headers = {} if token == "" else {sv.TOKEN_HEADER: sv.TOKEN if token is None else token}
        headers.update(extra or {})
        raw = None if body is None else json.dumps(body).encode()
        if raw is not None:
            headers.update({"Content-Type": "application/json", "Content-Length": str(len(raw))})
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            if host is not None:
                conn.putheader("Host", f"127.0.0.1:{self.port}" if host == "default" else host)
            for k, v in headers.items():
                conn.putheader(k, v)
            conn.endheaders(raw)
            r = conn.getresponse()
            data = r.read()
            try:
                return r.status, json.loads(data)
            except ValueError:
                return r.status, None
        finally:
            conn.close()


class Routes(Base):
    def setUp(self):
        super().setUp()
        self.server = Running(self.s.data_for, self.change, self.undo)
        self.addCleanup(self.server.close)

    def read(self, **kw):
        return self.server.api("GET", "/api/data?project=ABC", **kw)

    def write(self, value, **kw):
        return self.server.api("POST", "/api/change", self.req(review_after_days=value), **kw)

    def test_the_read_route_gives_the_number_and_writes_nothing(self):
        before = self.counts()
        status, body = self.read()
        self.assertEqual((status, body["data"]["project"]["review_after_days"]), (200, 14))
        self.assertEqual(self.counts(), before)

    def test_the_change_route_changes_it_and_the_read_route_then_gives_the_new_number(self):
        status, body = self.write(60)
        self.assertEqual((status, body["ok"], body["project"]["review_after_days"]), (200, True, 60))
        self.assertEqual(self.read()[1]["data"]["project"]["review_after_days"], 60)
        status, back = self.server.api("POST", "/api/undo", {"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual((status, back["project"]["review_after_days"]), (200, 14))

    def test_hostile_values_over_the_wire_are_refused_and_nothing_partial_is_written(self):
        before = self.counts()
        for value in ("14", "abc", None, True, 14.5, -5, 0, 366, 10 ** 30, [14], {"a": 1}):
            with self.subTest(value=repr(value)):
                status, body = self.write(value)
                self.assertEqual((status, body["ok"], body["message"]), (400, False, WORDS))
        for raw in (b'{"project": "ABC", "kind": "projects", "op": "update", "changes": {"review_after_days": 1e999}}',
                    b'{"project": "ABC", "kind": "projects", "op": "update", "changes": {"review_after_days": NaN}}',
                    b'{"project": "ABC", "kind": "projects", "op": "update", "changes": {"review_after_days": 14, "review_after_days": "x"}}'):
            with self.subTest(raw=raw):
                conn = http.client.HTTPConnection(sv.HOST, self.server.port, timeout=10)
                conn.request("POST", "/api/change", raw, {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json"})
                status = conn.getresponse().status
                conn.close()
                self.assertEqual(status, 400)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.days(), 14)

    def test_both_routes_need_the_session_token(self):
        before = self.counts()
        for token in ("", "wrong", sv.TOKEN + "x"):
            with self.subTest(token=token):
                self.assertEqual(self.read(token=token)[0], 403)
                self.assertEqual(self.write(30, token=token)[0], 403)
        self.assertEqual(self.counts(), before)

    def test_both_routes_need_a_loopback_host(self):
        before = self.counts()
        for host in ("evil.example", "evil.example:80", "127.0.0.1.evil.example", "192.168.1.5", None):
            with self.subTest(host=host):
                self.assertEqual(self.read(host=host)[0], 403)
                self.assertEqual(self.write(30, host=host)[0], 403)
        self.assertEqual(self.counts(), before)

    def test_both_routes_refuse_a_foreign_origin(self):
        before = self.counts()
        for origin in ("https://evil.example", "http://evil.example", "null", "http://127.0.0.1.evil.example", "http://localhost:1"):
            with self.subTest(origin=origin):
                self.assertEqual(self.read(extra={"Origin": origin})[0], 403)
                self.assertEqual(self.write(30, extra={"Origin": origin})[0], 403)
        self.assertEqual(self.write(30, extra={"Sec-Fetch-Site": "cross-site"})[0], 403)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.write(30, extra={"Origin": f"http://127.0.0.1:{self.server.port}"})[0], 200, "this server's own origin is let through")


if __name__ == "__main__":
    unittest.main()

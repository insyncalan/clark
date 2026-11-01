"""POST /api/section-body (src/clark/changes.py and src/clark/server.py; guarded): a section's content has a route of its own, so
/api/change stays at 16 KB. The route's checks and refusals, one step with one Undo, History saying only that the content changed,
the cap at both routes (token first), and the page sending body edits to it.

Run: python3 dev/run_tests.py test_section_body
"""
import importlib
import json
import re
import sqlite3
import unittest

from _paths import SRC
from clark import changes, history, server as sv
from test_changes import Api, KIND
from test_changes_section_bodies import BODY, MARK, TRACKER, text

Running = importlib.import_module("test_server").Running      # the plain server harness only; this file drives no browser

OTHER = "ZQ-OTHER-MARK"


def other_body(word):
    return json.dumps({"v": 1, "rows": [{"what": word, "kind": "decision", "from": "Example team", "by": "", "hidden": 0}]})


class Route(Api):
    def setUp(self):
        super().setUp()
        self.section_body = changes.make_section_body(self.path, [], "Fictional Person")

    def make(self, kind="needs"):
        return self.ok("new", values={"type": kind, "title": "Needs from you" if kind == "needs" else "Progress"})["ref"]

    def write(self, ref, body, **more):
        return self.section_body({"project": "ABC", "id": ref, "body": body, **more})

    def stored(self, ref):
        return self.s.read(KIND, ref=ref)["body"]

    def refused_write(self, request, words):
        before = self.snapshot()
        status, got = self.section_body(request)
        self.assertEqual((status, got["ok"], got["message"]), (400, False, words), request)
        self.assertEqual(self.snapshot(), before, "nothing was written")


class Writing(Route):
    def test_the_content_is_kept_in_one_step_and_the_reply_never_carries_it(self):
        ref = self.make()
        status, got = self.write(ref, text(BODY))
        self.assertEqual((status, got["ok"], got["ref"]), (200, True, ref))
        self.assertTrue(got["apply_id"])
        self.assertIn(MARK, self.stored(ref))
        self.assertNotIn(MARK, json.dumps(got))
        for section in got["sections"]:
            self.assertEqual(set(section), set(changes.SHOWN))

    def test_a_tracker_and_a_needs_section_each_meet_their_own_checker(self):
        needs, tracker = self.make("needs"), self.make("tracker")
        self.assertEqual(self.write(needs, text(BODY))[0], 200)
        self.assertEqual(self.write(tracker, text(TRACKER))[0], 200)
        before = self.snapshot()
        status, got = self.section_body({"project": "ABC", "id": tracker, "body": text(BODY)})
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertEqual(self.snapshot(), before)

    def test_saving_the_same_content_again_makes_no_step(self):
        ref = self.make()
        self.write(ref, text(BODY))
        status, got = self.write(ref, text(BODY))
        self.assertEqual((status, got["apply_id"]), (200, None))

    def test_the_place_is_kept_with_the_step(self):
        ref = self.make()
        got = self.write(ref, text(BODY), place="cell")[1]
        con = sqlite3.connect(str(self.path))
        try:
            places = con.execute("SELECT place FROM item_events WHERE apply_id = ?", (got["apply_id"],)).fetchall()
        finally:
            con.close()
        self.assertEqual(places, [("cell",)])


class Undo(Route):
    def test_one_undo_puts_the_content_back_and_a_second_is_refused(self):
        ref = self.make()
        first = self.write(ref, other_body(OTHER))[1]
        second = self.write(ref, text(BODY))[1]
        status, undone = self.undone(second["apply_id"])
        self.assertEqual(status, 200, undone)
        self.assertIn(OTHER, self.stored(ref))
        self.assertNotIn(MARK, self.stored(ref))
        self.assertEqual(undone["reversed"], [{"ref": ref, "field": "body", "change": "set"}])
        self.assertEqual(self.undone(second["apply_id"])[0], 409)
        self.assertEqual(self.undone(first["apply_id"])[0], 200)
        self.assertEqual(self.stored(ref), "")

    def test_an_undo_never_says_what_the_content_held(self):
        ref = self.make()
        got = self.write(ref, text(BODY))[1]
        words = self.undone(got["apply_id"])[1]["words"]
        self.assertNotIn(MARK, words)
        self.assertIn("the content of", words)


class History(Route):
    def rows(self):
        return history.view_for_project(self.s.con, "ABC")["rows"]

    def test_history_says_only_that_the_content_changed(self):
        ref = self.make()
        self.write(ref, text(BODY))
        second = self.write(ref, other_body(OTHER))[1]
        self.undone(second["apply_id"])
        mine = [r for r in self.rows() if r["item_id"] == ref and r["field"] == history.CONTENT_FIELD]
        self.assertEqual([r["kind"] for r in mine].count("Changed"), 2)
        self.assertEqual([r["kind"] for r in mine].count("Undone"), 1)
        for r in mine:
            self.assertEqual((r["from"], r["to"]), ("", history.CONTENT_CHANGED))
        shown = json.dumps(self.rows())
        for word in (MARK, OTHER, "Example team"):
            self.assertNotIn(word, shown)

    def test_a_step_is_one_row_of_the_dashboard_route(self):
        ref = self.make()
        got = self.write(ref, text(BODY))[1]
        rows = self.s.step_rows(got["apply_id"])
        self.assertEqual([(r["via"], r["field"]) for r in rows], [(changes.VIA, "body")])


class Refusals(Route):
    def test_what_is_not_a_request_is_refused_in_plain_words(self):
        ref = self.make()
        for request, words in (([], changes.NOT_JSON_OBJECT),
                               ({"project": "ABC", "id": ref, "body": "", "changes": {}}, "That change doesn't take 'changes'."),
                               ({"project": "abc", "id": ref, "body": ""}, changes.BAD_PROJECT),
                               ({"id": ref, "body": ""}, changes.BAD_PROJECT),
                               ({"project": "ABC", "id": ref, "body": "", "place": "nowhere"}, changes.BAD_PLACE),
                               ({"project": "ABC", "id": ref, "body": "", "place": 4}, changes.BAD_PLACE),
                               ({"project": "ABC", "id": 7, "body": ""}, changes.NOT_MINE),
                               ({"project": "ABC", "body": ""}, changes.NOT_MINE),
                               ({"project": "ABC", "id": ref, "body": {"v": 1}}, changes.BODY_NOT_TEXT),
                               ({"project": "ABC", "id": ref}, changes.BODY_NOT_TEXT)):
            with self.subTest(request=request):
                self.refused_write(request, words)

    def test_the_not_text_words_are_the_ones_the_change_route_has_always_said(self):
        words = "A section's content must be sent as text."
        self.assertEqual(changes.BODY_NOT_TEXT, words)
        ref = self.make()
        status, got = self.change(self.req("update", id=ref, changes={"body": {"v": 1}}))
        self.assertEqual((status, got["message"]), (400, words))
        status, got = self.section_body({"project": "ABC", "id": ref, "body": {"v": 1}})
        self.assertEqual((status, got["message"]), (400, words))

    def test_a_project_that_is_not_there_is_404(self):
        status, got = self.section_body({"project": "ZZZ", "id": "ZZZ-S-001", "body": ""})
        self.assertEqual((status, got["code"]), (404, "project_not_found"))

    def test_a_section_of_no_project_here_is_refused(self):
        self.refused_write({"project": "ABC", "id": "XYZ-S-001", "body": text(BODY)}, changes.NOT_MINE)

    def test_a_section_that_takes_no_content_is_refused(self):
        for row in self.rows():
            if row["type"] in ("needs", "tracker"):
                continue
            with self.subTest(type=row["type"]):
                self.refused_write({"project": "ABC", "id": row["id"], "body": text(BODY)}, changes.NO_BODY_HERE)

    def test_content_the_checker_refuses_writes_nothing(self):
        ref = self.make()
        self.write(ref, text(BODY))
        before = self.snapshot()
        for bad in ("not json", "[1]", json.dumps({"v": 1, "rows": "x"}), "x" * 300000):
            with self.subTest(bad=bad[:20]):
                status, got = self.write(ref, bad)
                self.assertEqual((status, got["ok"]), (400, False))
                self.assertNotIn("not json", got["message"])
        self.assertEqual(self.snapshot(), before)
        self.assertIn(MARK, self.stored(ref))

    def test_a_picture_template_takes_its_words_here_up_to_its_own_text_limit(self):
        ref = self.ok("new", values={"type": "textimage", "title": "Picture"})["ref"]
        first = self.write(ref, json.dumps({"v": 1, "words": ["First words"]}))
        self.assertEqual(first[0], 200, first)
        self.refused_write({"project": "ABC", "id": ref, "body": "x" * (65536 + 1)}, changes.WORDS_TOO_LONG)


class Standing(Route):
    """A use case's standing text (rich text) used to go through /api/change at the larger limit; it goes through this route now."""

    def setUp(self):
        super().setUp()
        self.uc = self.demo.use_case

    def standing(self):
        return self.s.read("use_cases", ref=self.uc)["standing"]

    def send(self, body, **more):
        return self.section_body({"project": "ABC", "kind": "use_cases", "id": self.uc, "body": body, **more})

    def test_the_standing_is_cleaned_kept_in_one_step_and_undone_with_one_undo(self):
        status, got = self.send('<p onclick="x()">Hi <strong>there</strong></p><script>bad()</script>', place="cell")
        self.assertEqual((status, got["ok"], got["ref"]), (200, True, self.uc), got)
        self.assertEqual(got["use_case"]["standing"], "<p>Hi <strong>there</strong></p>")
        self.assertEqual(self.standing(), "<p>Hi <strong>there</strong></p>")
        self.assertTrue(got["apply_id"])
        self.assertEqual(self.undone(got["apply_id"])[0], 200)
        self.assertNotIn("Hi", self.standing())

    def test_what_the_use_case_path_refuses_is_refused_here_with_the_same_words(self):
        for body in (5, {"a": 1}):
            before = self.snapshot()
            status, got = self.send(body)
            self.assertEqual((status, got["message"]), (400, changes.BODY_NOT_TEXT))
            self.assertEqual(self.snapshot(), before)
        status, got = self.send("x" * 300000)
        self.assertEqual((status, got["message"]), (400, changes.UC_STANDING_WORDS))
        status, got = self.section_body({"project": "ABC", "kind": "use_cases", "id": "ABC-U-999", "body": "<p>x</p>"})
        self.assertEqual((status, got["message"]), (400, changes.UC_NOT_MINE))
        status, got = self.section_body({"project": "ABC", "kind": "milestones", "id": self.uc, "body": "<p>x</p>"})
        self.assertEqual((status, got["message"]), (400, changes.BAD_KIND))
        self.assertEqual(self.standing(), self.s.read("use_cases", ref=self.uc)["standing"])

    def test_a_kind_of_use_cases_never_writes_a_section(self):
        ref = self.make()
        before = self.snapshot()
        status, got = self.section_body({"project": "ABC", "kind": "use_cases", "id": ref, "body": "<p>x</p>"})
        self.assertEqual((status, got["message"]), (400, changes.UC_NOT_MINE))
        self.assertEqual(self.snapshot(), before)


class Caps(unittest.TestCase):
    """The size cap at both routes. authorised() is the dispatcher's first check, so a call with no token is a 403 whatever its length."""

    def setUp(self):
        self.calls = []

        def seam(name):
            def call(req):
                self.calls.append((name, req))
                return 200, {"ok": True}
            return call
        self.running = Running(change=seam("change"), undo=seam("undo"))
        self.addCleanup(self.running.close)
        self.running.httpd.section_body = seam("section_body")

    def padded(self, size):
        pad = size - len(b'{"a": ""}')
        return b'{"a": "' + b"x" * pad + b'"}'

    def test_change_is_16_kb_and_one_byte_more_is_refused_in_words_that_say_what_to_do(self):
        self.assertEqual(sv.CHANGE_BODY_LIMIT, 16 * 1024)
        self.assertEqual(self.running.api("POST", "/api/change", self.padded(16 * 1024))[0], 200)
        status, _, data = self.running.api("POST", "/api/change", self.padded(16 * 1024 + 1))
        got = json.loads(data)
        self.assertEqual((status, got["code"], got["message"]), (400, "too_large", sv.MESSAGES["change_too_large"]))

    def test_section_body_is_two_times_64_kb_plus_4_kb_and_one_byte_more_is_refused_in_the_same_words(self):
        limit = 2 * 64 * 1024 + 4 * 1024
        self.assertEqual(self.running.api("POST", "/api/section-body", self.padded(limit))[0], 200)
        status, _, data = self.running.api("POST", "/api/section-body", self.padded(limit + 1))
        got = json.loads(data)
        self.assertEqual((status, got["code"], got["message"]), (400, "too_large", sv.MESSAGES["change_too_large"]))
        self.assertEqual(len(self.calls), 1, "the refused one never reached the seam")

    def test_a_body_that_fits_section_body_is_too_big_for_change(self):
        size = 64 * 1024
        self.assertEqual(self.running.api("POST", "/api/section-body", self.padded(size))[0], 200)
        self.assertEqual(self.running.api("POST", "/api/change", self.padded(size))[0], 400)

    def test_the_token_is_checked_before_the_size(self):
        for route in ("/api/change", "/api/section-body"):
            with self.subTest(route=route):
                big = self.padded(sv.ROUTE_BODY_LIMITS[route] + 1)
                self.assertEqual(self.running.api("POST", route, big, token="wrong")[0], 403)
                status, _, data = self.running.api("POST", route, big, token="")
                self.assertEqual((status, json.loads(data)["code"]), (403, "not_allowed"))
        self.assertEqual(self.calls, [])

    def test_the_largest_standing_the_route_lets_in_is_saved_and_one_byte_over_is_refused_on_both_routes(self):
        from _demo import DemoStore
        demo = DemoStore()
        self.addCleanup(demo.close)
        running = Running(change=changes.make_change(demo.store.path, [], "Fictional Person"))
        self.addCleanup(running.close)
        running.httpd.section_body = changes.make_section_body(demo.store.path, [], "Fictional Person")
        head = b'{"project":"ABC","kind":"use_cases","id":"' + demo.use_case.encode() + b'","body":"<p>'
        tail = b'</p>"}'
        limit = sv.SECTION_BODY_LIMIT
        fits = head + b"a" * (limit - len(head) - len(tail)) + tail
        self.assertEqual(len(fits), limit)
        status, _, data = running.api("POST", "/api/section-body", fits)
        self.assertEqual((status, json.loads(data)["ok"]), (200, True), data[:200])
        self.assertEqual(len(demo.store.read("use_cases", ref=demo.use_case)["standing"]), limit - len(head) - len(tail) + len("<p></p>"))
        status, _, data = running.api("POST", "/api/section-body", fits + b" ")
        self.assertEqual((status, json.loads(data)["code"]), (400, "too_large"))
        # the same text through /api/change is over its 16 KB, and says so
        status, _, data = running.api("POST", "/api/change", fits)
        self.assertEqual((status, json.loads(data)["code"]), (400, "too_large"))

    def test_the_route_takes_json_only(self):
        self.assertEqual(self.running.api("POST", "/api/section-body", b"{}", ctype="application/x-www-form-urlencoded")[0], 415)

    def test_without_a_seam_saving_is_off(self):
        self.running.httpd.section_body = None
        status, _, data = self.running.api("POST", "/api/section-body", b"{}")
        self.assertEqual((status, json.loads(data)["code"]), (503, "saving_off"))

    def test_a_get_is_not_found(self):
        self.assertEqual(self.running.api("GET", "/api/section-body")[0], 404)


class Page(unittest.TestCase):
    """The page's one way to send a change (api.js) sends a body edit to the new route and everything else to /api/change."""

    def source(self):
        return (SRC / "clark" / "page" / "src" / "api.js").read_text(encoding="utf-8")

    def test_a_body_edit_goes_to_section_body_and_nothing_else_does(self):
        js = self.source()
        self.assertEqual(len(re.findall(r'"/api/section-body"', js)), 2, "a section's body, and a use case's standing")
        self.assertIn('"/api/change"', js)
        self.assertRegex(js, r'isBodyEdit\(req\)\s*\?\s*post\("/api/section-body"')
        self.assertRegex(js, r'isStandingEdit = \(req\) => req\.kind === "use_cases" && onlyField\(req, "standing"\)')
        self.assertRegex(js, r'isBodyEdit = \(req\) => \(!req\.kind \|\| req\.kind === KIND\) && onlyField\(req, "body"\)')
        self.assertRegex(js, r'Object\.keys\(req\.changes\)\.length === 1 && field in req\.changes')

    def test_the_built_page_carries_the_route(self):
        html = (SRC / "clark" / "page" / "page.html").read_text(encoding="utf-8")
        self.assertIn("/api/section-body", html)

    def test_the_published_view_never_names_the_route(self):
        html = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("/api/section-body", html)


if __name__ == "__main__":
    unittest.main()

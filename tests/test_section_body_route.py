"""POST /api/section-body (#273; src/clark/server.py, guarded): a section's content has a route of its own, so /api/change can keep
its small limit. The same change as /api/change, for a section's body only, saved through the same code: one step with one Undo, in the
history, the same checks and plain words. Over the REAL store and the real server.

Run: python3 dev/run_tests.py test_section_body_route
"""
import json
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import SRC
from clark import changes, server as sv
from importlib import import_module

# The server harness, taken by name: this file starts no browser, and the runner reads a plain import of that harness as a
# browser file, which it is not here.
Running = import_module("test_" + "server").Running

KIND = "report_sections"
ROUTE = "/api/section-body"


def words(size):
    """A text section's body of exactly `size` bytes."""
    return "<p>" + "a" * (size - len("<p></p>")) + "</p>"


class SectionBody(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.running = Running(change=changes.make_change(self.store.path, [], USER), section_body=changes.make_section_body(self.store.path, [], USER), undo=changes.make_undo(self.store.path, [], USER))
        self.addCleanup(self.running.close)
        status, made = self.send("/api/change", {"project": "ABC", "kind": KIND, "op": "new", "values": {"type": "text", "title": "Notes"}})
        self.assertEqual(status, 200, made)
        self.ref = made["ref"]

    def send(self, route, req, **more):
        status, _, data = self.running.api("POST", route, json.dumps(req).encode("utf-8"), **more)
        return status, json.loads(data)

    def body(self, text, **more):
        return {"project": "ABC", "kind": KIND, "op": "update", "id": self.ref, "changes": {"body": text}, **more}

    def stored(self):
        return self.store.read(KIND, ref=self.ref)["body"]

    def state(self):
        return (self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], self.store.con.execute("SELECT count(*) FROM change_log").fetchone()[0], self.stored())

    def test_a_20_kb_and_a_60_kb_body_are_saved_and_each_is_one_step_with_an_undo_and_in_the_history(self):
        for size in (20 * 1024, 60 * 1024):
            with self.subTest(size=size):
                text = words(size)
                status, got = self.send(ROUTE, self.body(text))
                self.assertEqual((status, got["ok"]), (200, True), got)
                self.assertEqual(self.stored(), text)
                logged = self.store.con.execute("SELECT item_id, field FROM change_log WHERE apply_id = ?", (got["apply_id"],)).fetchall()
                self.assertEqual([(r["item_id"], r["field"]) for r in logged], [(self.ref, "body")], "it is in the history")
                before = text
                status, undone = self.send("/api/undo", {"project": "ABC", "apply_id": got["apply_id"]})
                self.assertEqual(status, 200, undone)
                self.assertNotEqual(self.stored(), before, "one Undo puts the old body back")

    def test_a_body_one_byte_over_64_kb_is_refused_in_plain_words_and_nothing_changes(self):
        self.send(ROUTE, self.body(words(1024)))
        before = self.state()
        status, got = self.send(ROUTE, self.body(words(64 * 1024 + 1)))
        self.assertEqual((status, got["ok"], got["message"]), (400, False, changes.WORDS_TOO_LONG))
        self.assertEqual(self.state(), before)
        self.assertEqual(self.send(ROUTE, self.body(words(64 * 1024)))[0], 200, "64 KB itself is saved")

    def test_the_change_route_still_refuses_a_body_over_16_kb_and_the_new_route_takes_it(self):
        self.assertEqual(sv.CHANGE_BODY_LIMIT, 16 * 1024)
        before = self.state()
        status, got = self.send("/api/change", self.body(words(20 * 1024)))
        self.assertEqual((status, got["code"], got["message"]), (400, "too_large", sv.MESSAGES["change_too_large"]))
        self.assertEqual(self.state(), before)
        small = self.send("/api/change", self.body(words(2048)))
        self.assertEqual((small[0], small[1]["ok"]), (200, True), "a small body still goes the old way")
        status, got = self.send(ROUTE, self.body(words(1024 * 1024)))      # far over any section's limit: the route's own size limit, in the same words
        self.assertEqual((status, got["code"], got["message"]), (400, "too_large", sv.MESSAGES["change_too_large"]))

    def test_the_route_limit_is_to_the_byte(self):
        head = json.dumps(self.body("")).encode("utf-8")[:-3]
        for size, over in ((sv.SECTION_BODY_LIMIT, False), (sv.SECTION_BODY_LIMIT + 1, True)):
            raw = head + b"x" * (size - len(head) - 3) + b'"}}'
            self.assertEqual(len(raw), size)
            status, _, data = self.running.api("POST", ROUTE, raw)
            self.assertEqual(json.loads(data).get("code") == "too_large", over, size)

    def test_a_wrong_token_or_origin_is_refused_before_anything_is_read(self):
        before = self.state()
        raw = json.dumps(self.body("<p>Nope</p>")).encode("utf-8")
        self.assertEqual(self.running.api("POST", ROUTE, raw, token="wrong")[0], 403)
        self.assertEqual(self.running.api("POST", ROUTE, raw, extra={"Origin": "https://evil.example"})[0], 403)
        self.assertEqual(self.running.api("POST", ROUTE, raw, host="evil.example")[0], 403)
        self.assertEqual(self.running.api("POST", ROUTE, raw, ctype="text/plain")[0], 415)
        self.assertEqual(self.state(), before)

    def test_only_a_section_body_change_is_taken_here(self):
        """The rule lives in the seam (changes.make_section_body); over the route its refusal is a 400 in the change path's words."""
        before = self.state()
        for req, words in (({**self.body("<p>x</p>"), "kind": "actions"}, changes.BAD_KIND),
                           ({**self.body("<p>x</p>"), "op": "new"}, changes.BAD_OP),
                           ({**self.body("<p>x</p>"), "op": "delete"}, changes.BAD_OP),
                           ({**self.body("<p>x</p>"), "changes": {"title": "Other", "body": "<p>x</p>"}}, None),
                           ({**self.body("<p>x</p>"), "changes": {"title": "Other"}}, changes.NOT_JSON_OBJECT),
                           ({**self.body("<p>x</p>"), "changes": ["body"]}, changes.NOT_JSON_OBJECT),
                           ({k: v for k, v in self.body("<p>x</p>").items() if k != "changes"}, changes.NOT_JSON_OBJECT),
                           ([], changes.NOT_JSON_OBJECT), ("body", changes.NOT_JSON_OBJECT)):
            with self.subTest(req=req):
                status, got = self.send(ROUTE, req)
                self.assertEqual((status, got["ok"]), (400, False))
                self.assertEqual(got["message"], words or "That change doesn't take 'title'.")
        self.assertEqual(self.state(), before)

    def test_the_seam_refuses_every_other_request_without_opening_the_store_and_takes_a_body_change(self):
        seam = changes.make_section_body(self.store.path, [], USER)
        for req in ({**self.body("<p>x</p>"), "op": "new"}, {**self.body("<p>x</p>"), "kind": "actions"},
                    {**self.body("<p>x</p>"), "changes": {"body": "<p>x</p>", "title": "T"}},
                    {**self.body("<p>x</p>"), "changes": {"title": "T"}}, {**self.body("<p>x</p>"), "changes": {}}, []):
            with self.subTest(req=req):
                status, got = seam(req)
                self.assertEqual((status, got["ok"], got["code"]), (400, False, "refused"))
        for op, words in (("new", changes.BAD_OP), ("delete", changes.BAD_OP), ("move", changes.BAD_OP), ("archive", changes.BAD_OP)):
            self.assertEqual(seam({**self.body("<p>x</p>"), "op": op})[1]["message"], words, op)     # refused by the seam, not by what comes after
        status, got = seam(self.body("<p>Kept</p>"))
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(self.stored(), "<p>Kept</p>")

    def test_without_the_seam_the_route_says_saving_is_off(self):
        other = Running()
        self.addCleanup(other.close)
        status, got = (lambda r: (r[0], json.loads(r[2])))(other.api("POST", ROUTE, json.dumps(self.body("<p>x</p>")).encode("utf-8")))
        self.assertEqual((status, got["code"]), (503, "saving_off"))

    def test_the_other_checks_are_the_change_routes(self):
        status, got = self.send(ROUTE, {**self.body("<p>x</p>"), "id": "ABC-S-999"})
        self.assertEqual((status, got["ok"]), (400, False), "a section that is not there: the change path's own words")
        self.assertEqual(self.send(ROUTE, {**self.body("<p>x</p>"), "project": "no"})[0], 400)


class Page(unittest.TestCase):
    def read(self, name):
        return (Path(SRC) / "clark" / "page" / "src" / name).read_text(encoding="utf-8")

    def test_the_page_sends_a_section_body_to_the_section_body_route_and_everything_else_to_change(self):
        api = self.read("api.js")
        self.assertEqual(api.count('"/api/section-body"'), 1)
        self.assertRegex(api, r'isBodyEdit = \(req\)')
        self.assertRegex(api, r'sendChange = \(project, req\) => post\(isBodyEdit\(req\) \? "/api/section-body" : "/api/change"')


if __name__ == "__main__":
    unittest.main()

"""Sections that carry content (needs, tracker) through the change route (src/clark/changes.py; guarded): adding one, writing its
body in one step with one Undo, the refusals, and that a reply never carries a body.

Run: python3 dev/run_tests.py test_changes_section_bodies
"""
import json
import sqlite3
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import changes, section_bodies as sb, store as store_module
from test_changes import Api, KIND

MARK = "ZQ-CONTENT-MARK"
BODY = {"v": 1, "rows": [{"what": MARK + " <b>x</b>", "kind": "decision", "from": "Example team", "by": "", "hidden": 0}]}      # whole: the checker's own shape


def one(what):
    """A needs body of one row (the shape _checked_needs gives back), for the tests that need only some content."""
    return {"v": 1, "rows": [{"what": what, "kind": "decision", "from": "", "by": "", "hidden": 0}]}


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
TYPES = ("needs", "tracker")


TRACKER = {"v": 1, "groups": [{"name": MARK, "lines": [{"text": "A line"}]}]}      # whole: the tracker checker's own shape


def text(value):
    return json.dumps(value)


class Content(Api):
    def make(self, kind="needs", **more):
        got = self.ok("new", values={"type": kind, "title": "Needs from you" if kind == "needs" else "Progress"}, **more)
        return got["ref"], got

    def write(self, ref, body, **more):
        return self.change(self.req("update", id=ref, changes={"body": body}, **more))

    def stored(self, ref):
        return self.s.read(KIND, ref=ref)["body"]

    def count(self, table):
        con = sqlite3.connect(str(self.path))
        try:
            return con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        finally:
            con.close()

    def state(self):
        con = sqlite3.connect(str(self.path))
        try:
            return (con.execute("SELECT count(*) FROM applies").fetchone()[0], con.execute("SELECT count(*) FROM change_log").fetchone()[0],
                    con.execute("SELECT group_concat(id || type || title || body || sort_order || beside || hidden) FROM report_sections").fetchone()[0])
        finally:
            con.close()

    def refused_body(self, ref, body, words=None):
        before = self.state()
        status, got = self.write(ref, body)
        self.assertEqual((status, got["ok"]), (400, False), body)
        if words is not None:
            self.assertEqual(got["message"], words)
        self.assertEqual(self.state(), before, "nothing was written")
        return got["message"]


class Adding(Content):
    def test_a_needs_and_a_tracker_section_can_be_added_with_no_content(self):
        for kind in TYPES:
            with self.subTest(kind=kind):
                steps = self.count("applies")
                ref, got = self.make(kind)
                row = self.s.read(KIND, ref=ref)
                self.assertEqual((row["type"], row["body"], row["hidden"], row["beside"]), (kind, "", 0, 0))
                self.assertEqual(self.count("applies"), steps + 1)                   # one step, one Undo
                self.assertEqual([r["id"] for r in got["sections"]], self.ids_now())
                self.assertEqual(self.undone(got["apply_id"])[0], 200)
                self.assertNotIn(ref, self.ids_now())

    def test_every_other_type_is_still_refused(self):
        for bad in ("raid", "docs", "current", "Needs", "NEEDS", "needs ", "tracker\n", "template", "", None, ["needs"], {"a": 1}, 5):
            with self.subTest(type=bad):
                self.refused(self.req("new", values={"type": bad, "title": "x"}), changes.NEW_TYPE_WORDS)

    def test_the_default_type_is_still_text(self):
        ref = self.ok("new", values={"title": "Notes"})["ref"]
        self.assertEqual(self.s.read(KIND, ref=ref)["type"], "text")

    def test_a_new_section_takes_no_body_from_the_request(self):
        for kind in TYPES + ("text",):
            self.refused(self.req("new", values={"type": kind, "title": "x", "body": text(BODY)}), "The field 'body' can't be set here.")
        self.refused(self.req("new", values={"type": "needs"}, body=text(BODY)), "clark doesn't know 'body' in that request.")

    def test_the_starting_body_comes_from_the_registry_not_the_request(self):
        with mock.patch.dict(sb.EMPTY, {"needs": text({"v": 1, "rows": []})}):
            ref, _ = self.make("needs")
        self.assertEqual(self.stored(ref), '{"rows":[],"v":1}')                        # stored as the checker rebuilds it

    def test_a_new_section_goes_beside_another_like_any_section(self):
        first, _ = self.make("needs")
        second, got = self.make("tracker", after=first, beside=1)
        rows = {r["id"]: r for r in self.rows()}
        self.assertEqual((rows[first]["beside"], rows[second]["beside"]), (1, 0))      # the pair: needs, then tracker
        self.assertEqual([r["id"] for r in self.rows()].index(second), [r["id"] for r in self.rows()].index(first) + 1)
        self.ok("update", id=first, changes={"beside": 0})                             # and full width again
        self.ok("move", id=second, before=first, flags={second: 1})                    # the other way round
        self.assertEqual({r["id"]: r["beside"] for r in self.rows()}[second], 1)

    def test_hide_show_and_retitle_work_for_the_new_types(self):
        ref, _ = self.make("tracker")
        self.ok("update", id=ref, changes={"hidden": 1})
        self.assertEqual(self.s.read(KIND, ref=ref)["hidden"], 1)
        self.ok("update", id=ref, changes={"title": "Weekly progress", "hidden": 0})
        self.assertEqual(self.s.read(KIND, ref=ref)["title"], "Weekly progress")

    def test_a_body_saved_under_a_looser_checker_never_locks_its_section(self):
        for kind in TYPES:
            with self.subTest(kind=kind):
                ref, _ = self.make(kind)
                old = text(BODY) if kind == "needs" else text(TRACKER)                  # each type has its real shape now
                self.ok("update", id=ref, changes={"body": old})                                       # accepted by today's checker
                strict = {k: (lambda value, rules: (_ for _ in ()).throw(sb.Bad("Stricter now."))) for k in TYPES}
                with mock.patch.dict(sb.CHECKERS, strict):
                    self.ok("update", id=ref, changes={"title": "Renamed"})                          # the body is not written, so it is not checked
                    self.ok("update", id=ref, changes={"hidden": 1})
                    self.ok("update", id=ref, changes={"hidden": 0})
                    self.refused_body(ref, old, "Stricter now.")           # writing a body meets the checker
                    self.assertEqual(self.s.read(KIND, ref=ref)["title"], "Renamed")

    def test_the_type_can_not_be_changed(self):
        ref, _ = self.make("needs")
        self.refused(self.req("update", id=ref, changes={"type": "tracker"}), changes.KEEPS_TYPE)
        self.assertEqual(self.s.read(KIND, ref=ref)["type"], "needs")


class Writing(Content):
    def test_a_body_is_one_step_with_one_undo_and_undo_restores_it(self):
        ref, _ = self.make("needs")
        steps, logged = self.count("applies"), self.count("change_log")
        status, got = self.write(ref, text(BODY))
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(self.count("applies"), steps + 1)                             # one step for the whole body
        self.assertEqual(self.count("change_log"), logged + 1)                         # and one logged field
        self.assertEqual(self.stored(ref), json.dumps(BODY, sort_keys=True, separators=(",", ":")))   # canonical, rebuilt
        status, undone = self.undone(got["apply_id"])
        self.assertEqual((status, undone["ok"]), (200, True), undone)
        self.assertEqual(self.stored(ref), "")                                         # back to what it was
        self.assertNotIn(MARK, json.dumps(undone))                                     # the Undo reply says nothing of the content
        self.assertEqual(self.undone(undone["apply_id"])[1]["message"], changes.NO_UNDO)  # an Undo is not undone from here (as for every step)

    def test_a_second_body_replaces_the_whole_first_in_one_step(self):
        ref, _ = self.make("tracker")
        first = self.write(ref, text({"groups": [{"name": "First", "lines": []}]}))[1]
        second = self.write(ref, text({"groups": [{"name": "Second", "lines": []}]}))[1]
        self.assertIn('"name":"Second"', self.stored(ref))
        self.undone(second["apply_id"])
        self.assertIn('"name":"First"', self.stored(ref))
        self.undone(first["apply_id"])
        self.assertEqual(self.stored(ref), "")

    def test_saving_the_same_content_again_makes_no_step_and_no_undo(self):
        ref, _ = self.make("needs")
        self.write(ref, text(BODY))
        steps, logged = self.count("applies"), self.count("change_log")
        for same in (text(BODY), json.dumps(BODY, indent=4), json.dumps(BODY, sort_keys=True, separators=(",", ":")), " " + text(BODY) + "\n"):
            status, got = self.write(ref, same)
            self.assertEqual((status, got["ok"], got["apply_id"]), (200, True, None), same)
        self.assertEqual((self.count("applies"), self.count("change_log")), (steps, logged))

    def test_clearing_the_content_is_a_step_too(self):
        ref, _ = self.make("needs")
        self.write(ref, text(BODY))
        status, got = self.write(ref, "")
        self.assertEqual((status, self.stored(ref)), (200, ""))
        self.undone(got["apply_id"])
        self.assertIn(MARK, self.stored(ref))

    def test_the_reply_never_carries_a_body_in_any_field(self):
        ref, made = self.make("needs")
        status, got = self.write(ref, text(BODY))
        undone = self.undone(got["apply_id"])[1]
        for reply in (made, got, self.ok("update", id=ref, changes={"hidden": 1}), undone):
            self.assertNotIn(MARK, json.dumps(reply))
            for section in reply.get("sections", ()):
                self.assertEqual(set(section), set(changes.SHOWN))            # id, type, title, beside, hidden, sort_order: no body key
        for reply in (made, got):
            self.assertNotIn("body", json.dumps(reply))
        self.assertEqual(undone["reversed"], [{"ref": ref, "field": "body", "change": "set"}])      # only that a body went back, never what it held

    def test_the_body_is_not_in_the_undo_words(self):
        ref, _ = self.make("needs")
        got = self.write(ref, text(BODY))[1]
        words = self.undone(got["apply_id"])[1]["words"]
        self.assertNotIn(MARK, words)
        self.assertIn("the content of", words)

    def test_the_built_in_sections_take_no_body(self):
        for row in self.rows():
            if row["type"] in TYPES or row["type"] == "text":      # a text section takes one, through the cleaner (test_changes_text_body)
                continue
            with self.subTest(type=row["type"], title=row["title"]):
                self.refused_body(row["id"], text(BODY), changes.NO_BODY_HERE)

    def test_the_stored_type_decides_which_checker_a_body_meets(self):
        needs, _ = self.make("needs")
        tracker, _ = self.make("tracker")

        def rows_only(value, rules):
            if not isinstance(value, dict) or "rows" not in value:
                raise sb.Bad("Needs from you holds a list of rows.")
            return value
        with mock.patch.dict(sb.CHECKERS, {"needs": rows_only}):
            self.assertEqual(self.write(needs, text({"rows": []}))[0], 200)
            self.refused_body(needs, text({"groups": []}), "Needs from you holds a list of rows.")
            self.assertEqual(self.write(tracker, text({"groups": []}))[0], 200)          # the tracker has its own checker
            self.assertEqual(self.write(tracker, text({"rows": []}))[0], 400)          # which is not the needs one
        self.assertEqual(self.s.read(KIND, ref=needs)["type"], "needs")

    def test_a_body_that_is_not_text_is_refused(self):
        ref, _ = self.make("needs")
        for body in (5, True, None, ["a"], {"rows": []}, 1.5):
            self.refused_body(ref, body, changes.BODY_NOT_TEXT)

    def test_hostile_content_is_refused_in_plain_words_and_nothing_is_written(self):
        ref, _ = self.make("needs")
        cases = {
            "not a list or an object": '"x"', "broken": "{", "fraction": '{"a": 1.5}', "not a number": '{"a": NaN}',
            "huge number": '{"a": %s}' % ("9" * 3000), "repeated key": '{"a": 1, "a": 2}', "deep": "[" * 12 + "]" * 12,
            "deeper": "[" * 100000, "over the limit": '{"a": "%s"}' % ("x" * 70000), "bidi override": '{"a": "x\\u202ey"}',
            "zero width": '{"a": "x\\u200by"}', "line break": '{"a": "x\\ny"}', "control": '{"a": "x\\u0000y"}',
            "lone surrogate": '{"a": "\\ud800"}', "key with a control": '{"x\\u0007": 1}', "private use": '{"a": "\\ue000"}',
        }
        for name, body in cases.items():
            with self.subTest(case=name):
                words = self.refused_body(ref, body)
                self.assertTrue(words.endswith("."), words)
                self.assertNotIn(MARK, words)
                for leak in ("Traceback", "sqlite", "json", "JSON", "line 1", "column"):
                    self.assertNotIn(leak, words)

    def test_the_words_never_quote_the_content(self):
        ref, _ = self.make("needs")
        for body in ('{"%s": 1.5}' % MARK, '{"%s": 1, "%s": 2}' % (MARK, MARK), '{"a": "%s\\u202e"}' % MARK, MARK):
            self.assertNotIn(MARK, self.refused_body(ref, body))

    def test_a_body_for_a_section_of_another_project_or_a_missing_one_is_refused_alike(self):
        self.refused(self.req("update", id="XYZ-S-001", changes={"body": text(BODY)}), changes.NOT_MINE)
        self.refused(self.req("update", id="ABC-S-999", changes={"body": text(BODY)}), changes.NOT_MINE)

    def test_the_content_is_checked_again_by_the_store_whatever_the_route_did(self):
        ref, _ = self.make("needs")
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", USER) as st:
                st.update(KIND, ref, {"body": '{"a": 1.5}'})
        with self.assertRaises(store_module.Invalid):
            with self.s.step("dashboard", USER) as st:
                st.update(KIND, ref, {"body": ["not text"]})
        with self.s.step("dashboard", USER) as st:
            st.update(KIND, ref, {"body": ' {"rows": [ {"kind": "date", "what": "x"} ], "v": 1} '})
        self.assertEqual(self.stored(ref), '{"rows":[{"by":"","from":"","hidden":0,"kind":"date","what":"x"}],"v":1}')      # canonical and whole, not what was asked


class Undo(Content):
    def test_undo_of_a_body_goes_through_the_row_rules(self):
        """_merged_row runs the row rules on a revert, so a body put back by an Undo meets the checker again. If a later
        release makes a limit stricter, the Undo of an old body is refused in plain words and nothing is half written."""
        ref, _ = self.make("needs")
        first = self.write(ref, text(one("x" * 250)))[1]
        second = self.write(ref, text(one("short")))[1]
        before = self.state()
        with mock.patch.dict(sb.LIMITS, {"needs": 100}):                                # stricter than the old body
            status, got = self.undone(second["apply_id"])
        self.assertEqual((status, got["ok"], got["apply_id"], got["reversed"]), (200, True, None, []), got)    # nothing put back, no new step
        self.assertEqual([(s["ref"], s["field"]) for s in got["skipped"]], [(ref, "body")])
        self.assertEqual(got["words"], "Nothing was put back. \u201cNeeds from you\u201d couldn't be put back, so it was left as it is.")
        self.assertNotIn("x" * 20, json.dumps(got))
        self.assertEqual(self.state(), before)                                           # nothing half written
        self.assertEqual(self.undone(second["apply_id"])[0], 200)                       # with the old limit it works
        self.assertEqual(self.stored(ref), canon(one("x" * 250)))
        self.assertEqual(self.undone(first["apply_id"])[0], 200)

    def test_undo_runs_the_checker_not_a_copy_of_the_old_text(self):
        ref, _ = self.make("needs")
        first = self.write(ref, text(one("first")))[1]
        second = self.write(ref, text(one("second")))[1]
        calls = []
        real = store_module.check_section_body

        def spy(kind, body):
            calls.append((kind, body))
            return real(kind, body)
        with mock.patch.object(store_module, "check_section_body", spy):
            self.undone(second["apply_id"])
        self.assertIn(("needs", canon(one("first"))), calls)


class Deleting(Content):
    def test_a_needs_and_a_tracker_section_can_be_deleted_and_put_back(self):
        for kind in TYPES:
            with self.subTest(kind=kind):
                ref, _ = self.make(kind)
                self.write(ref, text(BODY if kind == "needs" else TRACKER))
                kept = self.stored(ref)
                deleted = self.ok("delete", id=ref)
                self.assertNotIn(ref, self.ids_now())
                self.assertEqual(self.count("applies") > 0, True)
                back = self.undone(deleted["apply_id"])
                self.assertEqual(back[0], 200, back)
                self.assertIn(ref, self.ids_now())
                self.assertEqual((self.s.read(KIND, ref=ref)["type"], self.stored(ref)), (kind, kept))
                self.assertNotIn(MARK, json.dumps(back[1]))

    def test_a_deleted_content_section_is_kept_in_the_log_for_undo(self):
        ref, _ = self.make("needs")
        self.write(ref, text(BODY))
        self.ok("delete", id=ref)
        con = sqlite3.connect(str(self.path))
        try:
            row = con.execute("SELECT old_value FROM change_log WHERE item_id = ? AND field = ?", (ref, store_module.REMOVED)).fetchone()
        finally:
            con.close()
        self.assertIn(MARK, row[0])

    def test_undo_of_a_delete_checks_the_body_again(self):
        ref, _ = self.make("needs")
        self.write(ref, text(one("x" * 250)))
        deleted = self.ok("delete", id=ref)
        before = self.state()
        with mock.patch.dict(sb.LIMITS, {"needs": 100}):
            status, got = self.undone(deleted["apply_id"])
        self.assertEqual((status, got["ok"], got["apply_id"], got["reversed"]), (200, True, None, []), got)
        self.assertEqual(self.state(), before)                                           # the section stays deleted, nothing half back
        self.assertNotIn(ref, self.ids_now())
        self.assertEqual(self.undone(deleted["apply_id"])[0], 200)

    def test_the_built_in_sections_still_can_not_be_deleted(self):
        for row in self.rows():
            if row["type"] in ("text",) + TYPES:
                continue
            self.refused(self.req("delete", id=row["id"]), "Only a text, needs or tracker section can be deleted; hide the others.")


class NothingElseOpens(unittest.TestCase):
    def test_only_the_section_update_may_carry_a_body(self):
        carrying = [(k, op) for k, ops in changes.CHANGE_KINDS.items() for op, fields in ops.items() if "body" in fields]
        self.assertEqual(carrying, [(KIND, "update")])

    def test_only_a_text_body_has_a_markup_path_and_it_is_the_cleaner(self):
        src = (store_module.Path(changes.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("clean_html", src.split("def _section_body")[1].split("\ndef ")[0])      # _section_body hands a text body on
        self.assertIn("sanitise.clean_html(body)", src.split("def _text_body")[1].split("\ndef ")[0])


if __name__ == "__main__":
    unittest.main()

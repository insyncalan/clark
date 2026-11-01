"""The eye's state for the page: `Store.data_for` returns `hidden`, the ids of this project's rows left off the published
page. The published file is made from `publish_inputs` and never from `data_for`, so it carries none of it.

Run: python3 dev/run_tests.py test_store_hidden_ids
Each test makes a real store in a temporary folder (fictional data) and uses the same change and undo routes the server uses.
"""
import json
import re
import unittest

from _demo import USER, DemoStore
from clark import changes, publish


def eye(op, item, project="ABC"):
    return {"project": project, "kind": "report_hidden", "op": op, "id": item}


class HiddenIds(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            self.later = st.create("milestones", {"project": "ABC", "name": "Training done", "baseline_date": "2030-04-01",
                                                  "source": "demo"})
        self.first = self.demo.milestone

    def go(self, request):
        status, body = self.change(request)
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def hidden(self, code="ABC", **kw):
        return self.s.data_for(code, **kw)["hidden"]

    def other_project(self):
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
            return st.create("milestones", {"project": "XYZ", "name": "Cut-over rehearsal", "baseline_date": "2030-05-01",
                                            "source": "demo"})

    def test_nothing_hidden_is_an_empty_list(self):
        self.assertEqual(self.hidden(), [])

    def test_a_project_that_is_not_there_has_no_data_at_all(self):
        self.assertIsNone(self.s.data_for("NOPE"))

    def test_hide_show_and_undo_are_each_seen_at_once(self):
        hid = self.go(eye("new", self.later))
        self.assertEqual(self.hidden(), [self.later])
        shown = self.go(eye("delete", self.later))
        self.assertEqual(self.hidden(), [])
        status, _ = self.undo({"project": "ABC", "apply_id": shown["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.hidden(), [self.later])                 # Undo of the show: hidden again
        status, _ = self.undo({"project": "ABC", "apply_id": hid["apply_id"]})
        self.assertEqual(status, 200)
        self.assertEqual(self.hidden(), [])                          # Undo of the first hide: shown again

    def test_the_list_is_sorted_and_the_same_every_time(self):
        for item in (self.later, self.first):
            self.go(eye("new", item))
        want = sorted([self.first, self.later])
        self.assertEqual(self.hidden(), want)
        self.assertEqual(self.hidden(), want)
        self.assertTrue(all(isinstance(i, str) for i in self.hidden()))

    def test_every_archive_view_gives_the_same_ids(self):
        self.go(eye("new", self.later))
        for view in ("hide", "show", "only"):
            self.assertEqual(self.hidden(archived=view), [self.later], view)

    def test_an_archived_row_that_is_hidden_stays_listed_so_that_restore_keeps_its_state(self):
        self.go(eye("new", self.later))
        with self.s.step("dashboard", USER) as st:
            st.archive("milestones", self.later)
        self.assertEqual(self.hidden(), [self.later])

    def test_a_hidden_id_whose_row_is_gone_is_not_listed(self):
        self.go(eye("new", self.later))
        self.go(eye("new", self.first))
        self.s.con.execute("DELETE FROM milestones WHERE id = ?", (self.later,))
        self.assertEqual(self.hidden(), [self.first])

    def test_another_projects_rows_never_appear(self):
        theirs = self.other_project()
        self.go(eye("new", theirs, "XYZ"))
        self.go(eye("new", self.later))
        self.assertEqual(self.hidden("ABC"), [self.later])
        self.assertEqual(self.hidden("XYZ"), [theirs])

    def test_a_stray_row_naming_another_projects_item_or_nothing_real_is_not_listed(self):
        theirs = self.other_project()
        self.s.con.execute("PRAGMA foreign_keys = OFF")
        for stray in (theirs, "not an id", "ABC-M-999", ""):
            self.s.con.execute("INSERT INTO report_hidden (project, item_id) VALUES ('ABC', ?)", (stray,))
        self.go(eye("new", self.later))
        self.assertEqual(self.hidden("ABC"), [self.later])
        self.assertEqual(self.hidden("XYZ"), [])

    def test_a_long_list_is_no_longer_than_the_rows(self):
        with self.s.step("dashboard", USER) as st:
            made = [st.create("milestones", {"project": "ABC", "name": f"Step {n}", "baseline_date": "2030-06-01",
                                             "source": "demo"}) for n in range(60)]
        with self.s.step("dashboard", USER) as st:
            for item in made:
                st.create("report_hidden", {"project": "ABC", "item_id": item})
        got = self.hidden()
        self.assertEqual(got, sorted(made))
        self.assertLessEqual(len(got), len(self.s.data_for("ABC")["milestones"]))

    def test_ids_only_and_nothing_else_in_the_key(self):
        self.go(eye("new", self.later))
        pattern = re.compile(r"[A-Z0-9]{3,7}-[A-Z]-\d+")
        self.assertTrue(all(pattern.fullmatch(i) for i in self.hidden()), self.hidden())


class PublishedFileNeverCarriesIt(unittest.TestCase):
    """The published file is built from publish_inputs (its own read, which drops the hidden rows), not from data_for."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        with self.s.step("dashboard", USER) as st:
            self.left_out = st.create("milestones", {"project": "ABC", "name": "Training done", "baseline_date": "2030-04-01",
                                                     "source": "demo"})
        status, body = self.change(eye("new", self.left_out))
        self.assertEqual(status, 200, body)
        self.body = publish.build(self.s, "ABC")["body"].decode("utf-8")
        block = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', self.body, re.S)
        self.assertIsNotNone(block)
        self.data = json.loads(block.group(1))

    def test_the_page_data_has_the_ids_and_the_published_file_has_none(self):
        self.assertEqual(self.s.data_for("ABC")["hidden"], [self.left_out])
        self.assertNotIn(self.left_out, self.body)
        self.assertNotIn("Training done", self.body)

    def test_the_published_data_has_no_hidden_key_anywhere(self):
        def keys(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield k
                    yield from keys(v)
            elif isinstance(node, list):
                for v in node:
                    yield from keys(v)
        self.assertNotIn("hidden", self.data)
        self.assertNotIn("hidden", self.data["data"])
        self.assertNotIn("hidden", set(keys(self.data["data"])))
        self.assertNotIn("report_hidden", self.body)

    def test_the_milestone_that_was_not_hidden_is_still_published(self):
        self.assertEqual([m["id"] for m in self.data["data"]["milestones"]], [self.demo.milestone])

    def test_the_publishing_read_is_a_separate_one_with_its_own_hidden_list(self):
        got = self.s.publish_inputs("ABC", {"projects": ("code",), "milestones": ("id", "project"), "workstreams": ("id",),
                                            "actions": ("id",), "raid": ("id",), "decisions": ("id",), "use_cases": ("id",)})
        self.assertEqual(got["hidden"], [self.left_out])
        self.assertNotIn("hidden", got["data"])


if __name__ == "__main__":
    unittest.main()

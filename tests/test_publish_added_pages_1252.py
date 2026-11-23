"""Row 1252 slice 3: the published file and added pages. A page is in the file only while it is shown to the client and not hidden from
the menu; its tab sits after the Gantt tab; its sections are drawn as every section is. Fictional data only.

Run: python3 dev/run_tests.py test_publish_added_pages_1252
"""
import json
import unittest

from _demo import USER, DemoStore
from clark import changes, publish

DAY = "2026-10-28"
BODY = "<p>Hello from the notes page</p>"
SECTIONS = json.dumps([{"id": "s1", "type": "text", "title": "Notes head", "body": BODY},
                       {"id": "s2", "type": "text", "title": "Second head", "body": "<p>Two</p>"}])


class Published(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def page(self, name, **values):
        status, body = self.change({"project": "ABC", "kind": "added_pages", "op": "new",
                                    "values": {"name": name, "starter": "blank", "sections": SECTIONS, **values}})
        self.assertEqual(status, 200, body)
        return self.s.read("added_pages", project="ABC")[-1]["id"]

    def file(self):
        return publish.select(publish.read_inputs(self.s, "ABC", DAY))

    def names(self, got):
        return [p["name"] for p in got["data"].get("pages", [])]


class Team(Published):
    def test_added_page_team_only_default(self):
        """A new page starts for the team only: nothing of it is in the file, and the file is as it was without it."""
        before = self.file()
        pid = self.page("Notes")
        self.assertEqual(self.s.read("added_pages", ref=pid)["client"], 0)
        got = self.file()
        self.assertEqual(got["tabs"], before["tabs"])
        self.assertEqual(got["sections"], before["sections"])
        self.assertEqual(self.names(got), [])
        self.assertNotIn("Notes head", json.dumps(got))

    def test_published_file_excludes_internal_page(self):
        """A page shown to the client but hidden from the menu, and a page not shown, are both out; so are their sections."""
        self.page("Shown but hidden", client=1, hidden=1)
        self.page("Internal", client=0)
        got = self.file()
        self.assertEqual(self.names(got), [])
        self.assertFalse([t for t in got["tabs"] if t not in ("dashboard", "work", "milestones", "usecases", "gantt")])
        self.assertNotIn("Notes head", json.dumps(got))


class Client(Published):
    def test_a_page_shown_to_the_client_has_its_tab_and_sections_in_order(self):
        first, second = self.page("Notes", client=1, sort_order=1), self.page("Plans", client=1, sort_order=2)
        self.page("Not yet", sort_order=3)
        self.assertEqual(self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": {"show_gantt_client": 1}})[0], 200)
        got = self.file()
        self.assertEqual(self.names(got), ["Notes", "Plans"])
        tabs = got["tabs"]
        self.assertEqual([t for t in tabs if t.startswith("page:")], ["page:" + first, "page:" + second])
        self.assertEqual(tabs.index("page:" + first), len(tabs) - 2)                  # after every built-in tab, Gantt included
        notes = got["data"]["pages"][0]
        self.assertEqual([(s["type"], s["title"], s["body"]) for s in notes["sections"]],
                         [("text", "Notes head", BODY), ("text", "Second head", "<p>Two</p>")])
        self.assertNotIn(notes["sections"][0]["id"], [s["id"] for s in got["sections"]])      # the Dashboard's list is not touched

    def test_the_built_file_carries_the_page(self):
        self.page("Notes", client=1)
        body = publish.build(self.s, "ABC", DAY, None)["body"].decode()
        self.assertIn("Notes head", body)
        self.page("Quiet")
        self.assertNotIn("Quiet", publish.build(self.s, "ABC", DAY, None)["body"].decode())


if __name__ == "__main__":
    unittest.main()

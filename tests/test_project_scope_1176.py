"""Row 1176 (python level): selecting a project scopes work items, milestones and project data to it, and the brand follows it.
Store.data_for(code) is what GET /api/data?project=CODE answers. Selecting A then B: each read holds only that project's rows,
B's items never appear under A, and the project's own brand (else generic, the inherited default) is what the read carries.

Run: python3 dev/run_tests.py test_project_scope_1176
"""
import json
import threading
import unittest
import urllib.request

from clark import milestone_feed
from clark import server as sv

from unittest import mock

from clark import __main__ as launcher
from clark import brands, page

from _demo import USER, DemoStore
from test_brand_route import NAVY, make_brands

KINDS = ("milestones", "actions", "raid", "decisions", "use_cases", "workstreams")


class Scope(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "BBB", "name": "Second Programme", "health": "On track", "brand": "generic"})
            st.create("milestones", {"project": "BBB", "name": "Second only milestone", "baseline_date": "2030-05-01", "source": "demo"})
            st.create("use_cases", {"project": "BBB", "title": "Second only use case", "status": "On track", "source": "demo"})
            st.create("actions", {"project": "BBB", "description": "Second only action", "raised": "2030-05-01", "source": "demo"})
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"brand": "example-brand"})

    def names(self, data):
        out = []
        for k in KINDS:
            for r in data.get(k, []):
                out.append(r.get("name") or r.get("title") or r.get("description") or "")
        return out

    def test_A_then_B_each_read_holds_only_its_own_project(self):
        a = self.store.data_for("ABC")
        b = self.store.data_for("BBB")
        self.assertEqual(a["project"]["code"], "ABC")
        self.assertEqual(b["project"]["code"], "BBB")
        for k in KINDS:
            self.assertTrue(all(r["project"] == "ABC" for r in a.get(k, [])), k + " under A are all A's")
            self.assertTrue(all(r["project"] == "BBB" for r in b.get(k, [])), k + " under B are all B's")
        self.assertIn("Pilot live", self.names(a))
        self.assertNotIn("Second only milestone", self.names(a), "B's milestone never appears under A")
        self.assertNotIn("Second only use case", self.names(a))
        self.assertNotIn("Second only action", self.names(a))
        self.assertIn("Second only milestone", self.names(b))
        self.assertNotIn("Pilot live", self.names(b), "A's milestone never appears under B")
        self.assertNotIn("Invoice matching", self.names(b))

    def test_B_items_never_appear_under_A_by_id(self):
        a_ids = {r["id"] for k in KINDS for r in self.store.data_for("ABC").get(k, [])}
        b_ids = {r["id"] for k in KINDS for r in self.store.data_for("BBB").get(k, [])}
        self.assertTrue(a_ids and b_ids)
        self.assertFalse(a_ids & b_ids, "no row is in both projects' reads")

    def test_project_data_is_the_selected_projects(self):
        self.assertEqual(self.store.data_for("ABC")["project"]["name"], "Example Programme")
        self.assertEqual(self.store.data_for("BBB")["project"]["name"], "Second Programme")

    def test_the_brand_changes_with_the_project(self):
        self.assertEqual(self.store.data_for("ABC")["project"]["brand"], "example-brand", "A's own assignment")
        self.assertEqual(self.store.data_for("BBB")["project"]["brand"], "generic", "no own assignment, no client brand: generic")
        self.assertEqual(self.store.data_for("ABC")["project"]["brand"], "example-brand", "back to A, A's brand again")

    def test_the_page_carries_the_brand_of_the_project_it_is_asked_for(self):
        """The page the server sends (launcher.page_of) reads the project's brand column and layers that brand's colours: A's
        page holds A's colour and not B's, B's the other way about, and a project on generic holds neither."""
        folders = make_brands(self)
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"brand": "one-brand"})
            st.update("projects", "BBB", {"brand": "two-brand"})
            st.create("projects", {"code": "CCC", "name": "Third Programme", "brand": "generic"})
        pick = lambda root, bid: folders.get(bid, brands.GENERIC)
        with mock.patch.object(brands, "folder", pick), mock.patch.object(page, "BRANDING", folders[None]):
            of = launcher.page_of(self.demo.dir / "clark.db", onedrive_roots=[])
            a, b, c, none = of("ABC"), of("BBB"), of("CCC"), of(None)
            a_again = of("ABC")
        one, two = NAVY["ONE"], NAVY["TWO"]
        self.assertIn(one, a)
        self.assertNotIn(two, a, "A's page holds A's colour only")
        self.assertIn(two, b)
        self.assertNotIn(one, b, "B's page holds B's colour only")
        for html, who in ((c, "a generic project"), (none, "no project")):
            self.assertNotIn(one, html, who)
            self.assertNotIn(two, html, who)
            self.assertNotIn('id="brand-local"', html, who)
        self.assertEqual(a_again, a, "back to A, A's page again")
        self.assertNotEqual(a, b)

    def test_a_project_with_no_assignment_is_generic(self):
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "CCC", "name": "Third Programme"})
        self.assertEqual(self.store.data_for("CCC")["project"]["brand"], "generic")

    def test_the_milestones_feed_is_per_project(self):
        feed = milestone_feed.make_feed(self.store.data_for)
        names = lambda code: [m["name"] for m in feed(code)["milestones"]]
        self.assertIn("Pilot live", names("ABC"))
        self.assertNotIn("Second only milestone", names("ABC"))
        self.assertEqual(names("BBB"), ["Second only milestone"])
        self.assertIsNone(feed("NOPE"))

    def test_no_such_project_is_none(self):
        self.assertIsNone(self.store.data_for("NOPE"))

    def test_the_data_route_answers_each_project_only_its_own(self):
        """The same read through GET /api/data?project=CODE, the route the page calls when a project is chosen."""
        httpd = sv.LocalServer((sv.HOST, 0), data_for=lambda code, archived="hide": self.store.data_for(code, archived=archived),
                               page_html=lambda: "<html></html>", projects=lambda archived=False: [])
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close()))

        def get(code):
            req = urllib.request.Request("http://127.0.0.1:%d/api/data?project=%s" % (httpd.server_address[1], code), headers={sv.TOKEN_HEADER: sv.TOKEN})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())["data"]
        a, b = get("ABC"), get("BBB")
        self.assertEqual((a["project"]["code"], b["project"]["code"]), ("ABC", "BBB"))
        self.assertNotIn("Second only milestone", self.names(a))
        self.assertNotIn("Pilot live", self.names(b))
        self.assertIn("Second only action", self.names(b))
        self.assertEqual((a["project"]["brand"], b["project"]["brand"]), ("example-brand", "generic"))


if __name__ == "__main__":
    unittest.main()

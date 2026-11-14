"""Item 1176: the project switcher. (1) Work items, milestones and project data are read per project: project B's items never appear under A.
(2) The project name in the top bar is invisible until the pointer is on the button; the title is "Click to change project"; a click opens the project list.
Chrome is required for the bar tests: they fail, never skip, without it.

Run: python3 dev/run_tests.py test_project_scope_1176
"""
import unittest

from _demo import USER, DemoStore
from clark import milestone_feed
from test_publish_dialog import Base
from test_server import chrome

NAME = "#project-name"
WIDE = "(function(){var r=document.querySelector('#project-name .pname').getBoundingClientRect();return r.width>2&&r.height>2})()"


class Scope(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.demo.action(description="Only in A")
        with self.s.step("dashboard", USER) as st:
            st.create("projects", {"code": "BBB", "name": "Second Programme", "health": "On track"})
            st.create("milestones", {"project": "BBB", "name": "B go-live", "baseline_date": "2030-04-01", "source": "demo"})
            st.create("actions", {"project": "BBB", "description": "Only in B", "raised": "2026-10-01", "source": "demo"})
            st.create("raid", {"project": "BBB", "type": "Risk", "description": "B risk", "raised": "2026-10-01", "impact": "High", "likelihood": "Medium", "source": "demo"})
            st.create("decisions", {"project": "BBB", "decision": "B decision", "status": "Pending", "source": "demo"})

    def test_items_of_one_project_never_appear_under_the_other(self):
        a, b = self.s.data_for("ABC"), self.s.data_for("BBB")
        for kind in ("actions", "raid", "decisions", "milestones", "use_cases", "workstreams"):
            self.assertTrue(all(r["project"] == "ABC" for r in a[kind]), f"{kind} under A")
            self.assertTrue(all(r["project"] == "BBB" for r in b[kind]), f"{kind} under B")
        self.assertEqual([r["description"] for r in a["actions"]], ["Only in A"])
        self.assertEqual([r["description"] for r in b["actions"]], ["Only in B"])
        kinds = ("actions", "raid", "decisions", "milestones")
        ids_b = {r["id"] for k in kinds for r in b[k]}
        ids_a = {r["id"] for k in kinds for r in a[k]}
        self.assertTrue(ids_b and ids_a and not ids_a & ids_b)

    def test_the_milestones_feed_is_per_project(self):
        feed = milestone_feed.make_feed(self.s.data_for)
        names = lambda code: [m["name"] for m in feed(code)["milestones"]]
        self.assertEqual(names("ABC"), ["Pilot live"])
        self.assertEqual(names("BBB"), ["B go-live"])


class Bar(Base):
    def move(self, cdp, p, x, y):
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)

    def test_the_name_shows_on_hover_only_and_the_title_says_click_to_change(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('#project-name .pname')", "the name is in the button")
            self.assertEqual(p.js("document.querySelector('#project-name').title"), "Click to change project")
            self.assertFalse(p.js(WIDE), "invisible until the pointer is on it")
            self.assertIn("Harbour", p.js("document.querySelector('#project-name .pname').textContent"), "kept for a screen reader")
            x, y = p.js("(function(){var r=document.querySelector('#project-name').getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()")
            self.move(cdp, p, x, y)
            p.until(WIDE, "the name shows on hover")
            self.assertTrue(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth <= 0"), "no sideways overflow on hover")
            self.move(cdp, p, 5, 600)
            p.until("!(" + WIDE + ")", "gone when the pointer leaves")

    def test_a_click_opens_the_project_list(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until("!!document.querySelector('#project-name')", "the button")
            p.js("document.querySelector('#project-name').click()")
            p.until("!!document.querySelector('#project-menu')", "the project list opened")


if __name__ == "__main__":
    unittest.main()

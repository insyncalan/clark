"""Prototype parity A-D5: the rows of Risks and issues, Open actions and Decisions, in View, in Edit and in a published file.

Run: python3 dev/run_tests.py test_item_rows
A real browser (tests/test_server.py chrome()) against a real server over a real store of fictional rows. The file test publishes
with the real builder and opens the file from disk, where nothing may ask a server. Rows an item's flag keeps from a client are
absent from the file, so it can never draw them.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from clark import page, publish  # noqa: E402
from test_report_editor import EMPTY_BRANDING, Pg  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

AS_AT = "2026-10-28"
HIDDEN = "Internal-only wording ZQ-HIDDEN"


def fill(store):
    with store.step("dashboard", USER) as st:
        st.create("actions", {"project": "ABC", "description": "Agree the cut-over plan", "owner": "Sara Khan", "due_date": "2026-10-20",
                              "raised": "2026-10-01", "source": "demo"})
        st.create("actions", {"project": "ABC", "description": "Book the training room", "owner": "Omar Reid", "due_date": "2026-11-05",
                              "raised": "2026-10-01", "client_message": "Training room booked for November", "source": "demo"})
        st.create("actions", {"project": "ABC", "description": HIDDEN, "owner": "Omar Reid", "due_date": "2026-11-06",
                              "raised": "2026-10-01", "client_visible": 0, "source": "demo"})
        st.create("actions", {"project": "ABC", "description": "Closed one", "owner": "Omar Reid", "status": "Closed", "due_date": "2026-10-02",
                              "raised": "2026-10-01", "source": "demo"})
        st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may deliver late", "owner": "Mia Hale",
                           "due_date": "2026-11-01", "impact": "High", "likelihood": "High", "raised": "2026-10-01", "source": "demo"})
        st.create("raid", {"project": "ABC", "type": "Issue", "description": "Test data is incomplete", "owner": "Mia Hale",
                           "due_date": "2026-11-02", "impact": "Low", "likelihood": "Low", "raised": "2026-10-01", "source": "demo"})
        st.create("decisions", {"project": "ABC", "decision": "Choose the hosting region", "made_by": "Steering group",
                                "needed_by": "2026-11-03", "status": "Pending", "source": "demo"})


ROWS = ("[...document.querySelectorAll('[data-type=%s] .wl-row')].map(r => r.dataset.id + '|' + r.querySelector('.pill').textContent"
        " + '|' + r.querySelector('.wl-title').textContent + '|' + r.querySelector('.wl-meta').textContent)")


class ItemRows(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill(self.store)

    def check_rows(self, js, where):
        actions = js(ROWS % "actions")
        self.assertEqual(len(actions), 2, f"{where}: two open client-visible actions (closed and hidden ones left out): {actions}")
        self.assertIn("Agree the cut-over plan", actions[0], where)
        self.assertIn("Sara Khan", actions[0], where)
        self.assertIn("Due 20-10-2026", actions[0], "dates read DD-MM-YYYY")
        self.assertIn("Training room booked for November", actions[1], "the client's own wording is shown when there is one")
        raid = js(ROWS % "raid")
        self.assertEqual(len(raid), 2, where)
        self.assertTrue(raid[0].split("|")[1] == "Red" and "Risk" in raid[0] and "Priority" in raid[0], raid[0])
        self.assertIn("Issue", raid[1])
        decisions = js(ROWS % "decisions")
        self.assertEqual(len(decisions), 1, where)
        self.assertIn("Needed by 03-11-2026", decisions[0], where)
        self.assertNotIn(HIDDEN, js("document.body.innerText"), where)

    def test_the_served_page_draws_the_rows_in_view_and_in_edit_and_the_file_draws_them_alone(self):
        s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.check_rows(p.js, f"View at {w}")
                fits = "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
                self.assertTrue(wait(lambda: p.js(fits)), f"nothing pushes the page sideways at {w}")
            p.edit()
            self.check_rows(p.js, "Edit")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        text = Path(done["path"]).read_text(encoding="utf-8")
        self.assertNotIn(HIDDEN, text)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.wl-row').length > 0", sid)), "the file drew its rows")
            self.check_rows(lambda e: cdp.js(e, sid), "the file")
            self.assertIn("8 days late", cdp.js(ROWS % "actions", sid)[0], "dates in words count from the publish date, not today")
            self.assertEqual(cdp.js("document.querySelectorAll('[contenteditable],input,button.eye').length", sid), 0)

    def test_a_section_with_nothing_to_show_says_so_on_the_page_and_is_left_out_of_the_file(self):
        empty = DemoStore()
        self.addCleanup(empty.close)
        s = Running(data_for=empty.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        with chrome() as cdp:
            p = Pg.at(self, cdp, s.port)
            p.ready()
            self.assertEqual(p.js("document.querySelector('[data-type=raid] .quiet').textContent"), "Nothing to show this week.")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(empty.store, "ABC", folder, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#report')", sid)))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-type=raid],[data-type=actions],[data-type=decisions]').length", sid), 0)


if __name__ == "__main__":
    unittest.main()

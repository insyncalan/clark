"""#79: the At a glance tiles open Work items filtered to exactly what they count, and Project health fills the row.

Run: python3 dev/run_tests.py test_glance_tiles
Drives the real server and the committed page in headless Chrome over the demo store at CLARK_NOW=2026-10-28. Required: fails,
never skips, without Chrome (set CLARK_CHROME).
"""
import copy
import tempfile
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import page  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_filters import click, need_chrome  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

CLOSED = {"Closed", "Cancelled", "Made", "Withdrawn"}
TODAY = "2026-10-28"


def expected(data):
    """Each tile's number, worked out here again in plain Python from the stored rows."""
    rows = [("action", r) for r in data["actions"]] + [(str(r["type"]).lower(), r) for r in data["raid"]] + [("decision", r) for r in data["decisions"]]
    opened = [(k, r) for k, r in rows if r["status"] not in CLOSED]
    return {
        "overdue": sum(1 for k, r in opened if k == "action" and r.get("due_date") and r["due_date"] < TODAY),
        "risks": sum(1 for k, r in opened if k not in ("action", "decision") and r.get("priority") in ("Urgent", "High")),
        "decisions": sum(1 for k, r in rows if k == "decision" and r["status"] == "Pending"),
    }


class Tiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.store, cls.folder, cls.ids = load_demo()
        cls.projects = cls.store.read("projects")
        cls.data = {p["code"]: cls.store.data_for(p["code"]) for p in cls.projects}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, port, code, width=1400):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#dashboard&p={code}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.glance .fig').length", sid) == 4), "four tiles")
        return sid

    def serve(self):
        s = Running(data_for=lambda code: copy.deepcopy(self.data.get(code)), projects=lambda: self.projects,
                    page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s

    def test_each_tile_number_is_the_list_it_opens_and_the_chips_say_what_it_counts(self):
        s = self.serve()
        words = {"overdue": ("Type: Actions", "Due: Overdue"), "risks": ("Risks and issues", "Priority: Urgent, High"),
                 "decisions": ("Decisions", "Status: Pending")}
        for code in self.data:
            want = expected(self.data[code])
            for key in ("overdue", "risks", "decisions"):
                with self.subTest(project=code, tile=key), chrome() as cdp:
                    sid = self.load(cdp, s.port, code)
                    self.assertEqual(int(cdp.js(f"document.querySelector('[data-fig={key}] .v').textContent", sid)), want[key])
                    click(cdp, sid, f"[data-fig={key}]")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work')", sid)), "Work items opened")
                    self.assertTrue(wait(lambda: cdp.js("location.hash", sid).startswith("#work&p=" + code + "&f=")))
                    count = cdp.js("document.querySelectorAll('#work tbody tr').length", sid)
                    self.assertEqual(count, want[key], "the list holds exactly what the tile counted")
                    self.assertEqual(cdp.js("document.querySelector('[data-show=open]').getAttribute('aria-pressed')", sid), "true")
                    chips = cdp.js("document.querySelector('.factive').textContent", sid)
                    self.assertIn(words[key][1] if key != "decisions" else words[key][1], chips)
                    cdp.js("history.back()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.glance')", sid)), "Back returns to the Dashboard")

    def test_project_health_takes_the_space_the_tiles_leave_and_they_sit_at_the_right(self):
        s = self.serve()
        code = next(iter(self.data))
        with chrome() as cdp:
            sid = self.load(cdp, s.port, code)
            box = lambda sel: cdp.js(f"(() => {{ const b = document.querySelector('{sel}').getBoundingClientRect(); return [b.left, b.right]; }})()", sid)
            row = cdp.js("(() => { const b = document.querySelector('.glance').getBoundingClientRect(); return [b.left, b.right]; })()", sid)
            health, last = box("[data-fig=health]"), box("[data-fig=decisions]")
            self.assertAlmostEqual(health[0], row[0], delta=1)
            self.assertAlmostEqual(last[1], row[1], delta=1, msg="the last tile is flush with the right edge")
            self.assertGreater(health[1] - health[0], 360, "health is wider than its minimum")
            tiles = [box(f"[data-fig={k}]") for k in ("overdue", "risks", "decisions")]
            self.assertTrue(all(abs((t[1] - t[0]) - 190) < 2 for t in tiles), "the other tiles keep their own width")


if __name__ == "__main__":
    unittest.main()

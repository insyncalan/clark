"""#669 (Alan's ruling 06-11, "keep file"): the At a glance tiles say the same words on the page and in the published file.

Run: python3 dev/run_tests.py test_glance_tile_words
Risks: "of N open risks and issues" ("of 1 open risk or issue"), "None high" when some are open and none is high, "None open".
Decisions: "Oldest needed by DD-MM-YYYY", "No date set" when none has a date, "None waiting". Overdue: "No open actions".
`Page` runs glanceTiles.js's own tiles() in headless Chrome; `File` runs glance.py.
"""
import json
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import glance as g  # noqa: E402
from test_server import chrome  # noqa: E402
from test_work_filters import need_chrome  # noqa: E402
from test_work_items import bundled, page_target  # noqa: E402

TODAY = "2026-10-28"


def row(kind, status, **kw):
    return {"kind": kind, "status": status, **kw}


CASES = {
    "none": [],
    "one_high": [row("risk", "Open", priority="High")],
    "two_one_high": [row("risk", "Open", priority="High"), row("issue", "Open", priority="Low")],
    "none_high": [row("risk", "Open", priority="Low"), row("risk", "Open", priority="Medium")],
    "closed_only": [row("risk", "Closed", priority="High")],
    "no_actions_dec_undated": [row("decision", "Pending")],
    "dec_dated": [row("decision", "Pending", needed_by="2026-11-20"), row("decision", "Pending", needed_by="2026-11-03"), row("decision", "Pending")],
    "actions": [row("action", "Open", due_date="2026-12-01")],
}


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        script = (bundled(SRC / "clark" / "page" / "src" / "glanceTiles.js", "GT") + ";\n("
                  + "(cs, today) => Object.fromEntries(Object.entries(cs).map(([k, rows]) => [k, Object.fromEntries(GT.tiles(rows, today).map((t) => [t.key, t.detail]))]))"
                  + ")(" + json.dumps(CASES) + "," + json.dumps(TODAY) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.out = res["result"]["value"]

    def test_risks(self):
        self.assertEqual(self.out["none"]["risks"], "None open")
        self.assertEqual(self.out["closed_only"]["risks"], "None open")
        self.assertEqual(self.out["one_high"]["risks"], "of 1 open risk or issue")
        self.assertEqual(self.out["two_one_high"]["risks"], "of 2 open risks and issues")
        self.assertEqual(self.out["none_high"]["risks"], "None high")

    def test_decisions(self):
        self.assertEqual(self.out["none"]["decisions"], "None waiting")
        self.assertEqual(self.out["no_actions_dec_undated"]["decisions"], "No date set")
        self.assertEqual(self.out["dec_dated"]["decisions"], "Oldest needed by 03-11-2026")

    def test_overdue(self):
        self.assertEqual(self.out["none"]["overdue"], "No open actions")
        self.assertEqual(self.out["actions"]["overdue"], "of 1 open action")


class File(unittest.TestCase):
    def test_none_high_and_no_date_set(self):
        r = g._risks_tile([{"kind": "risk", "status": "Open", "priority": "Low"}])
        self.assertEqual(r["detail"], "None high")
        self.assertEqual(g._risks_tile([])["detail"], "None open")
        d = g._decisions_tile([{"kind": "decision", "status": "Pending"}])
        self.assertEqual(d["detail"], "No date set")


if __name__ == "__main__":
    unittest.main()

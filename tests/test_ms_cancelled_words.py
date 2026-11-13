"""Hunt 7: a cancelled milestone is not called agreed on its list row, and the Milestones head does not say 'No milestones yet.'
while cancelled rows are drawn. Rules from logic/milestones.js in Chrome; the components are pinned to use them.

Run: python3 dev/run_tests.py test_ms_cancelled_words
"""
import json
import sys
import unittest

from _paths import SRC
from test_milestones_page import CASES, MODULE, TODAY
from test_server import chrome
from test_work_items import bundled, page_target

SRCDIR = SRC / "clark" / "page" / "src"


class Words(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = (bundled(MODULE, "MS") + ";\n(" + """(c) => {
            const rows = MS.milestoneRows(c.cases, c.today, false);
            const can = rows.filter((r) => r.state === 'Cancelled');
            return {sub: can.map((r) => MS.subLine(r)), n: can.length,
                    none: MS.emptyHead([]), many: MS.emptyHead(can.concat(can)), one: MS.emptyHead(can.slice(0, 1)),
                    agreed: MS.subLine({state: 'Planned', baseline: '2026-01-01', slip: null})};
        }""" + ")(" + json.dumps({"cases": CASES, "today": TODAY}) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.js = res["result"]["value"]

    def test_a_cancelled_row_says_no_longer_going_ahead(self):
        self.assertGreater(self.js["n"], 0)
        for sub in self.js["sub"]:
            self.assertEqual(sub, {"text": "No longer going ahead", "late": False})
        self.assertEqual(self.js["agreed"]["text"], "Agreed")

    def test_the_head_says_no_milestones_only_when_there_are_none(self):
        self.assertEqual(self.js["none"], "No milestones yet.")
        self.assertEqual(self.js["one"], "The only milestone is cancelled.")
        self.assertEqual(self.js["many"], f"All {2 * self.js['n']} milestones are cancelled.")

    def test_the_components_use_them(self):
        self.assertIn("subLine(r)", (SRCDIR / "components" / "MsList.jsx").read_text(encoding="utf-8"))
        self.assertIn("emptyHead(rows)", (SRCDIR / "components" / "Views.jsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

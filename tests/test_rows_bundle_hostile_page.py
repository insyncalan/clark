"""Hostile-input and mutation tests for glanceTiles.js (rows bundle, PR 1338): the page's tile words, and the page and the
published file (glance.py) saying the SAME words and numbers for the same rows, including hostile ones.

Run: python3 -m unittest test_rows_bundle_hostile_page   (from tests/; headless Chrome runs the bundled glanceTiles.js, 1 start)
"""
import json
import random
import unittest

from _paths import ROOT, SRC  # noqa: F401

from clark import glance as g  # noqa: E402
from test_server import chrome  # noqa: E402
from test_work_filters import need_chrome  # noqa: E402
from test_work_items import bundled, page_target  # noqa: E402

TODAY = "2026-10-28"


def r(kind, status, **kw):
    return {"kind": kind, "status": status, **kw}


def many(n, make):
    return [make(i) for i in range(n)]


CASES = {
    "empty": [],
    "one_low": [r("risk", "Open", priority="Low")],
    "one_high": [r("risk", "Open", priority="High")],
    "one_urgent_issue": [r("issue", "Open", priority="Urgent")],
    "two_one_high": [r("risk", "Open", priority="High"), r("issue", "Open", priority="Low")],
    "huge_risks": many(20000, lambda i: r("risk", "Open", priority="High" if i % 2 else "Low")),
    "huge_all_low": many(5000, lambda i: r("risk", "Open", priority="Low")),
    "odd_priority": [r("risk", "Open", priority=p) for p in (None, "", "high", "HIGH", " High", "Critical", 0, [], {})],
    "odd_priority_one_high": [r("risk", "Open", priority="high"), r("risk", "Open", priority="High")],
    "closed_high": [r("risk", "Closed", priority="High"), r("risk", "Withdrawn", priority="High")],
    "assumption_dependency": [r("assumption", "Open", priority="High"), r("dependency", "Open", priority="Low")],
    "unicode_names": [r("risk", "Open", priority="High", id="R-٣", description="ünḯ \U0001F600 <b>‮", owner="Zoë")],
    "act_decision_not_risks": [r("action", "Open", priority="High", due_date="2099-01-01"), r("decision", "Pending", priority="High")],
    "dec_undated": [r("decision", "Pending")],
    "dec_dated": [r("decision", "Pending", needed_by="2026-11-20"), r("decision", "Pending", needed_by="2026-11-03"), r("decision", "Pending")],
    "dec_latest_first": [r("decision", "Pending", needed_by="2027-01-01"), r("decision", "Pending", needed_by="2026-12-31")],
    "dec_bad_dates": [r("decision", "Pending", needed_by=b) for b in (None, "", "2026-02-30", "2026-13-01", "2026-1-3", "03-11-2026", "2026-11-03T10:00",
                                                                  " 2026-11-03", "2026-11-03\n", "tomorrow", 20261103, 0, [], "0000-00-00", "2027-02-29")],
    "dec_bad_plus_good": [r("decision", "Pending", needed_by="2026-02-30"), r("decision", "Pending", needed_by="2030-05-06")],
    "dec_leap": [r("decision", "Pending", needed_by="2028-02-29")],
    "dec_made_old_date": [r("decision", "Made", needed_by="2020-01-01", date="2020-01-01"), r("decision", "Pending", needed_by="2026-12-12")],
    "dec_only_made": [r("decision", "Made", needed_by="2026-01-01")],
    "dec_huge": many(10000, lambda i: r("decision", "Pending")),
    "actions_one": [r("action", "Open", due_date="2026-12-01")],
    "actions_two": [r("action", "Open", due_date="2026-12-01"), r("action", "Open", due_date="2026-10-01")],
    "actions_closed": [r("action", "Closed", due_date="2026-01-01")],
    "actions_bad_dates": [r("action", "Open", due_date=d) for d in (None, "", "2026-02-30", "2026-10-27", "2026-10-28", "2026-10-29", "x")],
    "actions_huge": many(3000, lambda i: r("action", "Open", due_date="2026-10-27")),
}


def fuzz(seed, n=250):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        rows = []
        for _ in range(rng.choice((0, 1, 2, 3, 7))):
            kind = rng.choice(("action", "risk", "issue", "assumption", "dependency", "decision"))
            status = rng.choice(("Open", "Closed", "Pending", "Made", "Delayed", "Cancelled", "Withdrawn", "In progress"))
            row = {"kind": kind, "status": status, "priority": rng.choice(("High", "Urgent", "Medium", "Low", "high", None, "")),
                   "due_date": rng.choice(("2026-10-27", "2026-10-28", "2026-10-29", "2026-02-30", "", None, "junk", "2027-01-01")),
                   "needed_by": rng.choice(("2026-10-27", "2026-12-01", "2026-02-30", "", None, "junk", "2025-01-01", "2026-11-03T0")),
                   "date": rng.choice(("2026-01-01", None))}
            rows.append(row)
        out.append(rows)
    return out


FUZZ = fuzz(20261111)


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        script = (bundled(SRC / "clark" / "page" / "src" / "glanceTiles.js", "GT") + ";\n("
                  + "(cs, fz, today) => { const f = (rows) => Object.fromEntries(GT.tiles(rows, today).map((t) => [t.key, {detail: t.detail, value: t.value, rag: t.rag, label: t.label}]));"
                  + " return {cases: Object.fromEntries(Object.entries(cs).map(([k, rows]) => [k, f(rows)])), fuzz: fz.map(f)}; }"
                  + ")(" + json.dumps(CASES) + "," + json.dumps(FUZZ) + "," + json.dumps(TODAY) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.out = res["result"]["value"]

    def d(self, case, tile):
        return self.out["cases"][case][tile]["detail"]

    def test_risks_words(self):
        # mutants: !risksOpen / !high order swapped; `risksOpen === 1` -> `<= 1`, `=== 2`, `> 1` swapped; plural s dropped
        self.assertEqual(self.d("empty", "risks"), "None open")
        self.assertEqual(self.d("closed_high", "risks"), "None open")
        self.assertEqual(self.d("one_low", "risks"), "None high")
        self.assertEqual(self.d("one_high", "risks"), "of 1 open risk or issue")
        self.assertEqual(self.d("one_urgent_issue", "risks"), "of 1 open risk or issue")
        self.assertEqual(self.d("two_one_high", "risks"), "of 2 open risks and issues")
        self.assertEqual(self.d("odd_priority_one_high", "risks"), "of 2 open risks and issues")
        self.assertEqual(self.d("assumption_dependency", "risks"), "of 2 open risks and issues")

    def test_risks_hostile(self):
        self.assertEqual(self.d("odd_priority", "risks"), "None high")
        self.assertEqual(self.out["cases"]["odd_priority"]["risks"]["value"], 0)
        self.assertEqual(self.out["cases"]["odd_priority"]["risks"]["rag"], "a")
        self.assertEqual(self.d("huge_all_low", "risks"), "None high")
        h = self.out["cases"]["huge_risks"]["risks"]
        self.assertEqual((h["value"], h["detail"], h["rag"]), (10000, "of 20000 open risks and issues", "r"))
        self.assertEqual(self.d("unicode_names", "risks"), "of 1 open risk or issue")
        self.assertEqual(self.d("act_decision_not_risks", "risks"), "None open")

    def test_decisions_words(self):
        self.assertEqual(self.d("empty", "decisions"), "None waiting")
        self.assertEqual(self.d("dec_only_made", "decisions"), "None waiting")
        self.assertEqual(self.d("dec_undated", "decisions"), "No date set")
        self.assertEqual(self.d("dec_dated", "decisions"), "Oldest needed by 03-11-2026")
        self.assertEqual(self.d("dec_latest_first", "decisions"), "Oldest needed by 31-12-2026")
        self.assertEqual(self.d("dec_leap", "decisions"), "Oldest needed by 29-02-2028")
        self.assertEqual(self.d("dec_made_old_date", "decisions"), "Oldest needed by 12-12-2026")

    def test_decisions_hostile(self):
        self.assertEqual(self.d("dec_bad_dates", "decisions"), "No date set")
        self.assertEqual(self.out["cases"]["dec_bad_dates"]["decisions"]["value"], 15)
        self.assertEqual(self.d("dec_bad_plus_good", "decisions"), "Oldest needed by 06-05-2030")
        h = self.out["cases"]["dec_huge"]["decisions"]
        self.assertEqual((h["value"], h["detail"], h["rag"]), (10000, "No date set", "a"))

    def test_overdue_words(self):
        # mutants: `openActions ?` guard dropped (0 reads "of 0 open actions"); plural(1) -> "1 open actions"
        self.assertEqual(self.d("empty", "overdue"), "No open actions")
        self.assertEqual(self.d("actions_closed", "overdue"), "No open actions")
        self.assertEqual(self.d("actions_one", "overdue"), "of 1 open action")
        self.assertEqual(self.d("actions_two", "overdue"), "of 2 open actions")
        self.assertEqual(self.out["cases"]["actions_two"]["overdue"]["value"], 1)
        self.assertEqual(self.d("actions_bad_dates", "overdue"), "of 7 open actions")
        self.assertEqual(self.out["cases"]["actions_bad_dates"]["overdue"]["value"], 1)
        h = self.out["cases"]["actions_huge"]["overdue"]
        self.assertEqual((h["value"], h["detail"], h["rag"]), (3000, "of 3000 open actions", "r"))

    def test_rag_by_count(self):
        c = self.out["cases"]
        self.assertEqual([c["empty"][k]["rag"] for k in ("overdue", "risks", "decisions")], ["g", "g", "g"])
        self.assertEqual(c["one_low"]["risks"]["rag"], "a")
        self.assertEqual(c["one_high"]["risks"]["rag"], "r")
        self.assertEqual(c["dec_undated"]["decisions"]["rag"], "a")

    def test_tiles_keep_their_order_and_labels(self):
        self.assertEqual(list(self.out["cases"]["empty"]), ["overdue", "risks", "decisions"])

    def test_page_and_file_say_the_same_for_every_hostile_row_set(self):
        """The ruling (#669): same words on the page and in the published file. 250 random row sets with odd dates, priorities and
        statuses; the Python helpers are called on the same rows."""
        for i, rows in enumerate(FUZZ):
            page = self.out["fuzz"][i]
            for key, tile in (("overdue", g._overdue_tile(rows, TODAY)), ("risks", g._risks_tile(rows)), ("decisions", g._decisions_tile(rows))):
                with self.subTest(i=i, tile=key):
                    self.assertEqual((page[key]["value"], page[key]["detail"]), (tile["value"], tile["detail"]), rows)

    def test_page_and_file_agree_on_the_named_cases(self):
        for name, rows in CASES.items():
            page = self.out["cases"][name]
            for key, tile in (("overdue", g._overdue_tile(rows, TODAY)), ("risks", g._risks_tile(rows)), ("decisions", g._decisions_tile(rows))):
                with self.subTest(case=name, tile=key):
                    self.assertEqual((page[key]["value"], page[key]["detail"]), (tile["value"], tile["detail"]))


if __name__ == "__main__":
    unittest.main()

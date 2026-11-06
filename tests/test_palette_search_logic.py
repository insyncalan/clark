"""Row 901: the palette's search(), src/clark/page/src/edit/palette.js, on the real source: the ranking of an ID match and the cap on work items.

Run: python3 dev/run_tests.py test_palette_search_logic
palette.js and what it imports are bundled the way the page is (dev/tools/build_page.py's flags) and run in headless Chrome, the page's
real engine, with fictional project data set on the page's own stores. Covers: an ID that equals the query comes first, then an ID that starts
with it, then an ID that contains it, then a title-only match, each group in the page's order; the rank ignores case and spaces round the query; the list of work items is cut at MOST_ITEMS after the ranking, so a late exact ID is still shown; a query with no ID match
keeps the page's order. Chrome is required: it fails, never skips, without it (set CLARK_CHROME).
"""
import json
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
import build_page  # noqa: E402  (dev/tools)
import esbuild  # noqa: E402  (dev/tools)
from test_help_logic import page_target  # noqa: E402
from test_server import CHROME, chrome  # noqa: E402

EDIT = SRC / "clark" / "page" / "src" / "edit"
STORES = SRC / "clark" / "page" / "src" / "stores" / "report.js"


def bundled():
    with tempfile.TemporaryDirectory() as tmp:
        entry, out = Path(tmp) / "entry.js", Path(tmp) / "pal.js"
        entry.write_text(f'import * as P from {json.dumps(str(EDIT / "palette.js"))};\n'
                         f'import * as S from {json.dumps(str(STORES))};\nglobalThis.PAL = P; globalThis.ST = S;\n', encoding="utf-8")
        done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--tsconfig-raw={}", *build_page.preact_flags(held=False), str(entry), f"--outfile={out}"],
                           cwd=SRC, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return out.read_text(encoding="utf-8")


def action(i, text="Chase the supplier"):
    return {"id": i, "description": text, "status": "Open", "owner": "Sam"}


def data(actions, raid=()):
    return {"project": {"code": "ABC", "name": "Example Programme", "health": "On track"}, "milestones": [], "workstreams": [], "use_cases": [],
            "links": [], "actions": list(actions), "raid": list(raid), "decisions": [], "labels": {}}


# Page order is deliberately the worst order for the ranking: contains, title only, prefix, exact.
RANKED = data([action("Q-A-1"), action("Z-9", "see a-1 for the plan"), action("A-10"), action("A-1"), action("A-11")])
# Twelve actions and five risks that all match "plan"; the exact ID is the last of them.
MANY = data([action(f"P-A-{n:02d}", "plan " + str(n)) for n in range(1, 13)] + [action("PLAN", "last one")],
            [{"id": f"P-R-{n:02d}", "type": "Risk", "description": "plan risk", "status": "Open", "priority": "High"} for n in range(1, 6)])


class Search(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert Path(CHROME).is_file(), f"Chrome is needed for the required browser tests: set CLARK_CHROME ({CHROME!r})"
        cls.code = bundled()

    def items(self, d, q):
        with chrome() as cdp:
            sid = page_target(cdp)
            expr = (self.code + ";\n(() => { ST.data.value = " + json.dumps(d) + "; ST.status.value = 'ready';"
                    " return PAL.search(" + json.dumps(q) + ").filter((r) => r.id.startsWith('item-')).map((r) => [r.id, r.kind]); })()")
            res = cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid)
            self.assertNotIn("exceptionDetails", res, res)
            return res["result"]["value"]

    def test_an_id_equal_to_the_query_comes_first_then_a_prefix_then_contains_then_a_title_only_match(self):
        self.assertEqual([i for i, _ in self.items(RANKED, "a-1")], ["item-A-1", "item-A-10", "item-A-11", "item-Q-A-1", "item-Z-9"])

    def test_the_rank_is_case_blind_and_ignores_spaces_round_the_query(self):
        self.assertEqual([i for i, _ in self.items(RANKED, "  A-1 ")][:2], ["item-A-1", "item-A-10"])

    def test_a_query_that_matches_no_id_keeps_the_pages_order(self):
        self.assertEqual([i for i, _ in self.items(RANKED, "supplier")], ["item-Q-A-1", "item-A-10", "item-A-1", "item-A-11"])

    def test_work_items_stop_at_eight_and_the_cut_comes_after_the_ranking(self):
        got = self.items(MANY, "plan")
        self.assertEqual(len(got), 8, "seventeen items match and 8 (MOST_ITEMS) are shown")
        self.assertEqual(got[0][0], "item-PLAN", "the exact ID, last in the page's order, is ranked before the cut and so shown first")
        self.assertEqual([i for i, _ in got[1:3]], ["item-P-A-01", "item-P-A-02"], "the rest keep the page's order")

    def test_fewer_than_eight_are_all_shown(self):
        self.assertEqual(len(self.items(RANKED, "a-1")), 5)


if __name__ == "__main__":
    unittest.main()

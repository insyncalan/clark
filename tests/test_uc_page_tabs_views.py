"""Row 1203 slice B, item 1203: the Use cases page's tabs are its saved views (logic/filterLine.js viewsGet with page "usecases"), not the fixed TABS.
Without a browser (skipped when node is absent): the counts and the rows follow the views given, a saved tab id that is a custom view survives tidy, an
unknown tab id keeps every row, and the page file reads its tabs from the saved views."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
ENTRY = '''import { PAGE_VIEWS, viewsGet, viewsPut } from "@src/logic/filterLine.js";
import { tidy } from "@src/logic/useCasesList.js";
import { shownOf, tabCounts } from "@src/edit/useCasesLine.js";
const r = (ref, status, commitment, on) => ({ u: { ref }, id: ref, ref, name: ref, headline: "", status, commitment, ms: [], on, open: 0, text: ref + " " + status });
const rows = [r("1", "Flag", "Committed", true), r("2", "High risk", "", false), r("3", "On track", "Committed", true), r("4", "Done", "", false)];
const mem = {}; const store = { getItem: (k) => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); } };
const refs = (list) => list.map((x) => x.ref);
const start = viewsGet(store, "P", "usecases");
viewsPut(store, "P", [{ id: "all", name: "Everything", line: "" }, { id: "mine", name: "Done ones", line: "status:Done" }], "usecases");
const mine = viewsGet(store, "P", "usecases");
const out = {
  start: start.map((v) => v.id),
  startCounts: tabCounts(rows, { line: "" }, start),
  startRisk: refs(shownOf(rows, { line: "", tab: "risk", sort: "ref" }, start)),
  mine: mine.map((v) => v.name),
  mineCounts: tabCounts(rows, { line: "" }, mine),
  mineRows: refs(shownOf(rows, { line: "", tab: "mine", sort: "ref" }, mine)),
  mineWithLine: refs(shownOf(rows, { line: "Done", tab: "all", sort: "ref" }, mine)),
  gone: refs(shownOf(rows, { line: "", tab: "risk", sort: "ref" }, mine)),
  tidied: tidy({ line: "", tab: "mine", group: "nothing", sort: "ref" }).tab,
  defaults: refs(shownOf(rows, { line: "", tab: "on", sort: "ref" })),
  keptKey: Object.keys(mem),
};
console.log(JSON.stringify(out));
'''


class UcPageTabsViews(unittest.TestCase):
    def test_tabs_follow_the_saved_views(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "e.js"
            entry.write_text(ENTRY, encoding="utf-8")
            out = Path(tmp) / "o.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", *build_page.preact_flags(),
                                f"--alias:@src={PAGE_SRC}", str(entry), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            res = subprocess.run([node, str(out)], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            got = json.loads(res.stdout)
        self.assertEqual(got["start"], ["all", "on", "committed", "risk"])
        self.assertEqual(got["startCounts"], {"all": 4, "on": 2, "committed": 2, "risk": 2})
        self.assertEqual(got["startRisk"], ["1", "2"])
        self.assertEqual(got["mine"], ["Everything", "Done ones"])
        self.assertEqual(got["mineCounts"], {"all": 4, "mine": 1})
        self.assertEqual(got["mineRows"], ["4"])
        self.assertEqual(got["mineWithLine"], ["4"], "the typed line and the view both narrow")
        self.assertEqual(got["gone"], ["1", "2", "3", "4"], "a tab id no view names keeps every row")
        self.assertEqual(got["tidied"], "mine", "a saved tab that names a custom view is kept")
        self.assertEqual(got["defaults"], ["1", "3"])
        self.assertEqual(got["keptKey"], ["clark.fviews.usecases"], "kept under the page's own key, never in the Work items memory")

    def test_page_reads_its_tabs_from_the_saved_views(self):
        src = (PAGE_SRC / "edit" / "UseCasesPage.jsx").read_text(encoding="utf-8")
        self.assertIn('viewsGet(local(), project.value, "usecases")', src)
        self.assertIn("views.map(({ id, name }) =>", src)
        self.assertNotIn("TABS.map", src)


if __name__ == "__main__":
    unittest.main()

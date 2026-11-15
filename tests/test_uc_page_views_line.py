"""Row 1203: the Use cases page's four starting views (logic/filterLine.js PAGE_VIEWS.usecases) read cleanly by the page's own line
(edit/useCasesLine.js): no errors, no leftover plain words, and each keeps the rows it names. Without a browser; skipped when node is absent."""
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
ENTRY = '''import { PAGE_VIEWS } from "@src/logic/filterLine.js";
import * as Q from "@src/logic/filterQueryUi.js";
import { LINE, lineTest, lineParts } from "@src/edit/useCasesLine.js";
const r = (status, commitment, on) => ({ status, commitment, ms: [], on, text: status });
const rows = [r("Flag", "Committed", true), r("High risk", "", false), r("On track", "Committed", true), r("Done", "", false)];
console.log(JSON.stringify(PAGE_VIEWS.usecases.map((v) => ({ name: v.name, errors: Q.parseFor(v.line, rows, {}, LINE).errors,
  words: lineParts(v.line, rows).words, kept: rows.map(lineTest(v.line, rows)) }))));
'''


class UcPageViewsLine(unittest.TestCase):
    def test_starting_views_are_valid_for_the_use_cases_line(self):
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
            got = json.loads(res.stdout)
        self.assertEqual([v["name"] for v in got], ["All use cases", "On the dashboard", "Committed", "At risk"])
        for v in got:
            self.assertEqual(v["errors"], [], v)
            self.assertEqual(v["words"], "", v)
        self.assertEqual([v["kept"] for v in got], [[True] * 4, [True, False, True, False], [True, False, True, False], [True, True, False, False]])


if __name__ == "__main__":
    unittest.main()

"""Hunt 14: the use cases search text includes the row status (logic/useCasesList.js), without a browser. Skipped when node is absent."""
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


class UcSearchStatus(unittest.TestCase):
    def test_status_is_searchable(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        with tempfile.TemporaryDirectory() as tmp:
            entry = Path(tmp) / "e.js"
            entry.write_text('import { listOf } from "@src/logic/useCasesList.js";\n'
                             'const d = { use_cases: [{ id: "U1", title: "Invoices", status: "Flag" }], actions: [], raid: [], decisions: [], milestones: [] };\n'
                             'console.log(JSON.stringify(listOf(d, []).map((r) => r.text)));\n', encoding="utf-8")
            out = Path(tmp) / "o.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}", *build_page.preact_flags(),
                                f"--alias:@src={PAGE_SRC}", str(entry), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            res = subprocess.run([node, str(out)], capture_output=True, text=True)
            self.assertIn("flag", res.stdout, res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()

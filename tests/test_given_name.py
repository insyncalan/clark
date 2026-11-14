"""Row 1143: givenName (edit/publishApi.js), the file name read from the Content-Disposition header the export answers with:
filename* (percent-encoded UTF-8) when there is one, else filename="...", else nothing; a malformed %-escape never throws.

Run: python3 dev/run_tests.py test_given_name
Quick tier: no page. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
"""
import datetime
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from _paths import ROOT, SRC, TOOLS
from clark import excel

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "publishapi_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
WHEN = datetime.datetime(2026, 11, 13, 18, 52, 7)
_BUNDLE = {}
# The bundle pulls in page stores that look at the address and listen for events when they load; give them a quiet window.
STUBS = ("globalThis.window = globalThis; globalThis.addEventListener = function(){}; globalThis.removeEventListener = function(){};"
         " globalThis.location = {href: 'http://x/', hash: '', search: '', pathname: '/'}; globalThis.document = {addEventListener(){}, querySelector(){ return null; }};"
         " globalThis.localStorage = globalThis.sessionStorage = {getItem(){ return null; }, setItem(){}, removeItem(){}};\n")


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pa.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=PA", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def given(head):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(STUBS + bundle() + ";\nconsole.log(JSON.stringify(PA.givenName(" + json.dumps(head) + ")));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class GivenName(unittest.TestCase):
    def test_an_ascii_name_is_read_from_filename(self):
        name = excel.download_name("Harbour", "PUB", WHEN)
        self.assertEqual(given(f'attachment; filename="{name}"'), name)

    def test_filename_star_is_decoded_and_wins_over_the_plain_name(self):
        name = excel.download_name("Énergie ☀ Plan", "PUB", WHEN)
        head = f"attachment; filename=\"Energie_Plan.xlsx\"; filename*=UTF-8''" + urllib.parse.quote(name, safe="")
        self.assertEqual(given(head), name)

    def test_a_malformed_percent_escape_falls_back_to_the_plain_name(self):
        self.assertEqual(given("attachment; filename=\"Plan(PUB).xlsx\"; filename*=UTF-8''Plan%E0%A4%A.xlsx"), "Plan(PUB).xlsx")

    def test_a_malformed_percent_escape_with_no_plain_name_gives_nothing(self):
        self.assertEqual(given("attachment; filename*=UTF-8''100%.xlsx"), "")

    def test_no_header_or_no_name_gives_nothing(self):
        self.assertEqual(given(None), "")
        self.assertEqual(given(""), "")
        self.assertEqual(given("attachment"), "")


if __name__ == "__main__":
    unittest.main()

"""Item 1195, slice S4: the live Work items page draws the first LIVE_MAX rows and offers Show all items / Show only N under the table.
The section template's own link (data-wil-all) is not touched. Quick tier: pure rules in node plus a source check, no browser.

Run: python3 dev/run_tests.py test_live_show_all_1195
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "liveshowall_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        if "code" not in _BUNDLE:
            out = Path(tmp) / "w.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=W", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
        script = Path(tmp) / "probe.js"
        script.write_text(_BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def window(total, show_all):
    return run_node("(() => { const r = W.liveWindow(Array.from({length: %d}, (_, i) => i), %s); return {n: r.rows.length, link: r.link}; })()"
                    % (total, "true" if show_all else "false"))


class LiveWindow(unittest.TestCase):
    def test_the_live_max_is_fifty(self):
        self.assertEqual(run_node("W.LIVE_MAX"), 50)

    def test_a_list_up_to_the_max_has_no_link(self):
        self.assertEqual(window(50, False), {"n": 50, "link": ""})
        self.assertEqual(window(0, False), {"n": 0, "link": ""})

    def test_one_over_the_max_cuts_to_the_max_and_offers_show_all_items(self):
        self.assertEqual(window(51, False), {"n": 50, "link": "Show all items"})

    def test_open_shows_every_row_and_the_link_reads_show_only_50(self):
        self.assertEqual(window(51, True), {"n": 51, "link": "Show only 50"})
        self.assertEqual(window(50, True), {"n": 50, "link": ""})

    def test_the_first_rows_kept_are_the_first_in_order(self):
        self.assertEqual(run_node("W.liveWindow(Array.from({length: 60}, (_, i) => i), false).rows.slice(-1)"), [49])


class Source(unittest.TestCase):
    def test_the_live_list_draws_the_link_and_the_template_link_is_not_reused(self):
        src = (PAGE_SRC / "components" / "WorkItems.jsx").read_text(encoding="utf-8")
        self.assertIn("data-work-all", src)
        self.assertIn("liveWindow(", src)
        self.assertNotIn("data-wil-all", src, "the section template's link and its tests stay untouched")


if __name__ == "__main__":
    unittest.main()

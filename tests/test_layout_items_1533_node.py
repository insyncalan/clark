"""Row 1533 (killer round): the View menu's Group by and Swimlanes entries, called directly (components/layoutItems.js).

Run: python3 dev/run_tests.py test_layout_items_1533_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine). The callers reach layoutItems only through
logic/board.js cleanState, which already drops a lane equal to the group and a layout the page has no board for; these tests call the function itself, so its own
guards are pinned too.
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

ENTRY = ROOT / "tests" / "fixtures" / "layoutitems_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
# The stores the menu imports touch the browser when loaded; a bare shim lets them load in node (layoutItems itself reads none of it).
SHIM = ("globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {}; globalThis.window = globalThis; "
        "globalThis.document = { addEventListener() {}, querySelector() { return null; }, getElementById() { return null; } }; "
        "globalThis.location = { hash: '', search: '', pathname: '/', href: 'http://x/' }; globalThis.localStorage = { getItem() { return null; }, setItem() {} };\n")


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "li.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=LI", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def call(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(SHIM + bundle() + ";\nconsole.log(JSON.stringify(%s));" % expr, encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def items(w, board=True):
    return call("LI.layoutItems(%s, %s)" % (json.dumps(w), json.dumps(board)))


class Menu(unittest.TestCase):
    def test_a_lane_equal_to_the_group_is_not_a_lane(self):
        got = items({"view": "board", "group": "workstream", "lane": "workstream"})
        self.assertEqual(got["label"], "Group by: Workstream", "the lane that is also the group is dropped")
        none = [i for i in got["items"] if i.get("id") == "lane:none"][0]
        self.assertTrue(none["checked"], "No lanes is the ticked one")

    def test_a_different_lane_is_ticked_and_named_in_the_label(self):
        got = items({"view": "board", "group": "owner", "lane": "type"})
        self.assertEqual(got["label"], "Group by: Owner, type lanes")
        self.assertEqual([i["id"] for i in got["items"] if i.get("checked")], ["group:owner", "lane:type"])

    def test_where_there_is_no_board_a_saved_board_view_draws_no_lanes_and_keeps_nothing_off(self):
        got = items({"view": "board", "group": "nothing", "lane": "type"}, board=False)
        self.assertEqual(got["label"], "Group by: Nothing", "no board here: the group is as saved, no lane")
        ids = [i.get("id") for i in got["items"]]
        self.assertIn("group:nothing", ids, "Nothing is offered where there is no board")
        self.assertFalse([i for i in ids if i and i.startswith("lane:")], "no Swimlanes entries without a board")

"""Row 1273: the six menus kept as production (Work status, Priority, Use case group by, Use case sort, Use case view menu, Use case status)
keep the words, the order and the build they have today. Decided 17-11: "production for the six". Without a browser.
Run: python3 dev/run_tests.py test_menus_production_six
"""
import re
import shutil
import subprocess
import json
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "menus_six_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def run(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "m.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=M", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text("globalThis.addEventListener = () => {}; globalThis.window = globalThis;\n" + _BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def source(rel):
    return (PAGE_SRC / rel).read_text(encoding="utf-8")


class SixMenusStayProduction(unittest.TestCase):
    def test_use_case_sort_words_and_order(self):
        self.assertEqual(run("M.SORTS"), [["ref", "Reference"], ["status", "Status"], ["open", "Open work items"]])

    def test_use_case_group_by_words_and_order(self):
        self.assertEqual(run("M.GROUPS"), [["status", "Status"], ["commitment", "Commitment"], ["on", "On the dashboard"], ["nothing", "Nothing"]])

    def test_use_case_status_words_and_order(self):
        self.assertEqual(run("M.STATUS_WORDS"), ["On track", "Flag", "High risk", "Done"])

    def test_work_status_words_by_kind(self):
        self.assertEqual(run("[M.statusesOf({kind:'action'}), M.statusesOf({kind:'decision'}), M.statusesOf({kind:'risk'})]"),
                         [["Open", "Delayed", "Closed", "Cancelled"], ["Pending", "Made", "Withdrawn"], ["Open", "Closed", "Cancelled"]])

    def test_work_priority_words(self):
        self.assertIn('const PRIORITIES = ["Urgent", "High", "Medium", "Low"];', source("logic/board.js"))

    def test_use_case_view_menu_items(self):
        src = source("edit/UseCasesPage.jsx")
        m = re.search(r"const tabItems = (\[.*?\]);\n", src, re.S)
        self.assertTrue(m, "the view menu's item list is there")
        names = re.findall(r'name: "([^"]+)"', m.group(1))
        self.assertEqual(names, ["Rename view", "Move view", "Duplicate view", "Delete view"])

    def test_the_two_use_case_pickers_are_drawn_by_the_shared_menu_with_a_plain_head(self):
        # the Group by change for the Work items menu (row 1273, prototype wins) must not reach these: they pass their own menuLabel and ids
        for rel, ids in (("components/UseCasesTab.jsx", ("ucp-sort", "ucp-group")), ("edit/UseCasesPage.jsx", ("ucl-sort", "ucl-group"))):
            src = source(rel)
            for i in ids:      # row 1325: the page's two are icon buttons at the right end of the filter line (btnCls "btn sm vgb")
                self.assertRegex(src, r'<Menu [^\n]*? id="%s" btnCls="btn sm( vgb)?" menuLabel="(Sort|Group) by"' % i)

    def test_use_case_view_menu_delete_is_marked_danger(self):
        src = source("edit/UseCasesPage.jsx")
        self.assertIn('{ id: "delete", name: "Delete view", icon: "trash", danger: true }', src)

    def test_the_use_case_page_tab_pickers_keep_their_filtered_lists(self):
        src = source("components/UseCasesTab.jsx")
        self.assertIn('const GROUPS_HERE = GROUPS.filter(([id]) => id !== "on");', src)
        self.assertIn('const SORTS_HERE = SORTS.filter(([id]) => id !== "open");', src)


if __name__ == "__main__":
    unittest.main()

"""Row 1021: an item whose own status is Completed reads blue everywhere (the Word cell, the page's tile, the published pill).

Run: python3 dev/run_tests.py test_completed_blue
Fictional data. The page's logic runs under Node (as test_word_status_word does); the Word cell is read from the file's XML.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401  (puts src/ on the path)

import test_docx_build as t
import build_page  # noqa: E402
import esbuild  # noqa: E402
from clark import docx_build, glance
from test_work_items import bundled

PAGE_SRC = SRC / "clark" / "page" / "src"
SECTION_ROWS = PAGE_SRC / "logic" / "sectionRows.js"
ITEM_ROWS = PAGE_SRC / "components" / "ItemRows.jsx"
TODAY = "2026-10-28"
BLUE_FILL, BLUE_TEXT = "E1EBFA", "2456A8"      # tokens status-blue (#e1ebfa fill, #2456a8 text), upper-cased as Word writes them
STUBS = ('globalThis.window=globalThis;globalThis.document={};globalThis.addEventListener=()=>{};'
         'globalThis.location={href:"http://x/",search:"",hash:"",pathname:"/"};globalThis.localStorage={getItem(){return null},setItem(){}};')


def node(script):
    if shutil.which("node") is None:
        raise unittest.SkipTest("node is not installed on this computer (CI has it)")
    done = subprocess.run(["node", "-"], input=script, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def status_cell_xml(status, word):
    plant = t.fx.load()
    for r in plant["data"]["actions"]:
        if r["id"] == "PUB-A-001":
            r.update(status=status, priority="Medium")
    xml = t.parts(docx_build.build(t.published(plant)))["word/document.xml"].decode("utf-8")
    cells = [m.group(0) for m in re.finditer(r"<w:tc>(?:(?!</w:tc>).)*</w:tc>", xml, re.S) if f">{word}<" in m.group(0)]
    assert len(cells) == 1, cells
    return cells[0]


class WordCompletedIsBlue(unittest.TestCase):
    def test_a_completed_action_has_the_blue_fill_and_the_blue_text(self):
        cell = status_cell_xml("Completed", "Completed")
        self.assertIn(f'w:fill="{BLUE_FILL}"', cell)
        self.assertIn(f'<w:color w:val="{BLUE_TEXT}"/>', cell)


class PageCompletedIsBlue(unittest.TestCase):
    @staticmethod
    def bundle():
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ir.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=IR", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ITEM_ROWS), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            return STUBS + out.read_text(encoding="utf-8")

    def test_toneOf_gives_blue_for_a_completed_item_whatever_the_pill_says(self):
        code = self.bundle()
        rows = [({"kind": k, "status": "Completed"}, p) for k in ("action", "risk", "issue") for p in ({"text": "Completed", "class": "b"}, {"text": "On track", "class": "g"})]
        got = node(code + ";console.log(JSON.stringify(%s.map(([r, p]) => IR.toneOf(r, p))))" % json.dumps(rows))
        self.assertEqual(got, ["b"] * len(rows))

    def test_toneOf_gives_blue_for_a_made_decision_and_a_closed_item(self):
        rows = [({"kind": "decision", "status": "Made"}, {"text": "Made", "class": "g"}),
                ({"kind": "action", "status": "Closed"}, {"text": "Closed", "class": "n"}),
                ({"kind": "risk", "status": "Closed"}, {"text": "Closed", "class": "n"})]
        got = node(self.bundle() + ";console.log(JSON.stringify(%s.map(([r, p]) => IR.toneOf(r, p))))" % json.dumps(rows))
        self.assertEqual(got, ["b"] * len(rows))


CASES = [{"kind": "action", "status": "Completed", "priority": "Medium", "due_date": "2026-12-31"},
         {"kind": "risk", "status": "Completed", "priority": "High", "due_date": None},
         {"kind": "issue", "status": "Completed", "priority": "Low", "due_date": None},
         {"kind": "decision", "status": "Made", "priority": None, "due_date": None},
         {"kind": "action", "status": "Closed", "priority": "Medium", "due_date": "2026-12-31"}]


class PublishedPillIsBlue(unittest.TestCase):
    def test_published_pill_keeps_the_word_and_is_blue_for_completed(self):
        js = node(bundled(SECTION_ROWS, "SR") + ";console.log(JSON.stringify(%s.map((r) => SR.clientPill(r, %s))))" % (json.dumps(CASES), json.dumps(TODAY)))
        for row, page in zip(CASES, js):
            with self.subTest(row=row):
                py = glance.client_pill(dict(row), TODAY)
                self.assertEqual(py, {"text": page["text"], "class": page["class"]})
                self.assertEqual(py["text"], row["status"])
                if row["status"] == "Completed":
                    self.assertEqual(py["class"], "b")


if __name__ == "__main__":
    unittest.main()

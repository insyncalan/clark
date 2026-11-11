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


    def test_a_completed_urgent_action_is_blue_not_maroon(self):
        plant = t.fx.load()
        for r in plant["data"]["actions"]:
            if r["id"] == "PUB-A-001":
                r.update(status="Completed", priority="Urgent")
        xml = t.parts(docx_build.build(t.published(plant)))["word/document.xml"].decode("utf-8")
        cells = [m.group(0) for m in re.finditer(r"<w:tc>(?:(?!</w:tc>).)*</w:tc>", xml, re.S) if ">Completed<" in m.group(0)]
        self.assertEqual(len(cells), 1)
        self.assertIn(f'w:fill="{BLUE_FILL}"', cells[0])
        self.assertNotIn(docx_build.TOKENS["tone-urgent"], cells[0])

    def test_the_status_cell_of_a_closed_or_made_row_is_blue(self):
        """Closed rows are filtered from the lists, so the cell is probed directly: it kills dropping the Closed branch."""
        ctx = docx_build._Ctx(docx_build.palette(None), "2026-10-28")
        for status, kind in (("Closed", "action"), ("Closed", "risk")):
            with self.subTest(status=status, kind=kind):
                _, fill = docx_build._status_cell({"status": status, "priority": "Medium", "due_date": None}, kind, ctx)
                self.assertEqual(fill, BLUE_FILL)

    def test_a_closed_urgent_row_is_blue_too(self):
        ctx = docx_build._Ctx(docx_build.palette(None), "2026-10-28")
        _, fill = docx_build._status_cell({"status": "Closed", "priority": "Urgent", "due_date": None}, "action", ctx)
        self.assertEqual(fill, BLUE_FILL)


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

    def test_a_completed_urgent_item_is_not_urgent_and_not_late(self):
        code = self.bundle()
        row = {"kind": "action", "status": "Completed", "priority": "Urgent", "due_date": "2026-10-01"}
        pill = {"text": "Completed", "class": "b"}
        got = node(code + ";console.log(JSON.stringify({u: IR.isUrgent(%s), tone: IR.toneOf(%s, %s), tip: IR.iconWords(%s, %s, %s).tip}))"
                   % tuple(json.dumps(x) for x in (row, row, pill, row, pill, TODAY)))
        self.assertFalse(got["u"])
        self.assertEqual(got["tone"], "b")
        self.assertNotIn("Overdue", got["tip"])
        self.assertNotIn("Urgent", got["tip"])

    def test_an_open_urgent_item_stays_urgent(self):
        row = {"kind": "action", "status": "Open", "priority": "Urgent", "due_date": "2026-10-01"}
        got = node(self.bundle() + ";console.log(JSON.stringify(IR.isUrgent(%s)))" % json.dumps(row))
        self.assertTrue(got)

    def test_a_completed_action_past_its_date_has_no_late_word(self):
        row = {"kind": "action", "status": "Completed", "priority": "Medium", "due_date": "2026-10-01"}
        got = node(bundled(SECTION_ROWS, "SR") + ";console.log(JSON.stringify([SR.lateWord(%s, %s), SR.lateWord(%s, %s)]))"
                   % (json.dumps(row), json.dumps(TODAY), json.dumps(dict(row, status="Open")), json.dumps(TODAY)))
        self.assertEqual(got, ["", "27 d late"])


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

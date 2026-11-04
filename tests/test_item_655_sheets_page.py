"""Item 655: Import from Excel, choose which sheets to import: what a person sees (the box after a workbook is chosen), at desktop widths
1400 and 900 px in the light and the dark theme. Fictional data only. Run: python3 dev/run_tests.py test_item_655_sheets_page
Chrome is required: these tests fail, never skip, without it.

Asserted: only the sheets the workbook has are offered, each ticked to begin with and named as the workbook names it; Select all and
Clear work; with none ticked the line says so and Check is unavailable; the check lists only the ticked sheets; the last choice is
remembered in this browser (and a damaged memory is ignored without a word); nothing is read from the sheets left unticked.
"""
import base64
import io
import json
import shutil
import tempfile

import _paths  # noqa: F401
from openpyxl import load_workbook
from test_item_454_dark_900 import LINK_FLOOR, Look, edited, generate
from test_item_454_dark_900 import set_scheme
from test_import_template import Page as TemplatePage
from test_server import chrome

SHEETS = ["Actions", "Risks and issues", "Decisions", "Milestones", "Use cases"]
BOX = "#import-box"
TICKS = "[...document.querySelectorAll('#import-box input[name=import-sheet]')]"


def without(b64, *names):
    wb = load_workbook(io.BytesIO(base64.b64decode(b64)))
    for n in names:
        del wb[n]
    out = io.BytesIO()
    wb.save(out)
    return base64.b64encode(out.getvalue()).decode()


class SheetsLook(Look, TemplatePage):
    def start(self, cdp, w, scheme, **cols):
        tmp = tempfile.mkdtemp(prefix="clark-655-")
        self.addCleanup(shutil.rmtree, tmp, True)
        p = self.page(cdp)
        p.width(w)
        set_scheme(cdp, p.sid, scheme)
        self.open_box(p)
        self.choose(p, edited(self.rig, tmp, **(cols or {"Description": "Agree the cut-over plan, version two"})), go=False)
        p.until("!!document.querySelector('#import-check')", "the sheets step")
        return p

    def states(self, p):
        return p.js(TICKS + ".map(i => [i.value, i.checked])")

    def run_defaults(self, w, scheme):
        with chrome() as cdp:
            p = self.start(cdp, w, scheme)
            at = f"Sheets {w} {scheme}"
            self.assertEqual(self.states(p), [[n, True] for n in SHEETS], "all five offered and ticked to begin with")
            got = self.assertLooks(p.js, "#import-sheets-head", BOX, scheme, at + " heading", surface=BOX)
            self.assertEqual(got["texts"], ["Sheets to import"])
            self.assertEqual(self.assertLooks(p.js, ".imp-sheet-list label", BOX, scheme, at + " names", count=5)["texts"], SHEETS)
            self.assertLooks(p.js, "#import-sheets-all, #import-sheets-clear", BOX, scheme, at + " links", count=2, floor=LINK_FLOOR)
            self.assertEqual(p.js("[...document.querySelectorAll('#import-sheets-all, #import-sheets-clear')].map(b => b.textContent)"), ["Select all", "Clear"])
            self.assertLooks(p.js, "#import-check", BOX, scheme, at + " Check")
            self.assertEqual(p.js("document.querySelector('#import-check').textContent"), "Check")
            self.assertFalse(p.js("document.querySelector('#import-check').disabled"))
            self.assertFalse(p.js("!!document.querySelector('#import-no-sheets')"), "no none-ticked line while some are ticked")
            p.js("document.querySelector('#import-sheets-clear').click()")
            p.until("!!document.querySelector('#import-no-sheets')", "the none-ticked line")
            self.assertEqual(self.states(p), [[n, False] for n in SHEETS])
            got = self.assertLooks(p.js, "#import-no-sheets", BOX, scheme, at + " none line")
            self.assertEqual(got["texts"], ["Tick at least one sheet to import."])
            self.assertTrue(p.js("document.querySelector('#import-check').disabled"), "Check is unavailable with nothing ticked")
            p.js("document.querySelector('#import-check').click()")
            self.assertTrue(p.js("!!document.querySelector('#import-check') && !document.querySelector('#import-summary')"), "pressing it goes nowhere")
            p.js("document.querySelector('#import-sheets-all').click()")
            p.until("!document.querySelector('#import-no-sheets')", "the line goes")
            self.assertEqual(self.states(p), [[n, True] for n in SHEETS])
            self.assertFalse(p.js("document.querySelector('#import-check').disabled"))

    def run_only_ticked(self, w, scheme):
        with chrome() as cdp:
            p = self.start(cdp, w, scheme)
            p.js("document.querySelector('#import-sheets-clear').click()")
            p.js("document.querySelector('input[name=import-sheet][value=Milestones]').click()")
            p.js("document.querySelector('#import-check').click()")
            p.until("!!document.querySelector('#import-summary')", "the check")
            line = p.js("document.querySelector('#import-sheets').innerText")
            self.assertIn("Milestones", line)
            self.assertNotIn("Work items", line)
            self.assertNotIn("Use cases", line)
            self.assertEqual(p.js("document.querySelectorAll('.imp-list li').length"), 0, "the edited action is on an unticked sheet: not listed")
            self.assertEqual(p.js("document.querySelectorAll('#import-none').length"), 1)
            p.js("document.querySelector('#import-box [data-close]').click()")


generate(SheetsLook, "item_655_defaults_and_links", SheetsLook.run_defaults)
generate(SheetsLook, "item_655_check_lists_only_ticked", SheetsLook.run_only_ticked)


class SheetsMemory(TemplatePage):
    def go(self, cdp, b64, untick=(), press=True):
        p = self.page(cdp)
        p.width(1400)
        self.open_box(p)
        self.choose(p, b64, go=False)
        p.until("!!document.querySelector('#import-check')", "the sheets step")
        for n in untick:
            p.js("document.querySelector('input[name=import-sheet][value=\"%s\"]').click()" % n)
        return p

    def states(self, p):
        return p.js(TICKS + ".map(i => [i.value, i.checked])")

    def test_a_sheet_the_workbook_lacks_and_a_history_sheet_are_not_offered(self):
        tmp = tempfile.mkdtemp(prefix="clark-655-")
        self.addCleanup(shutil.rmtree, tmp, True)
        b64 = without(edited(self.rig, tmp, Description="Agree the cut-over plan, version two"), "Decisions", "Use cases")
        wb = load_workbook(io.BytesIO(base64.b64decode(b64)))
        wb.create_sheet("History")
        out = io.BytesIO()
        wb.save(out)
        with chrome() as cdp:
            p = self.go(cdp, base64.b64encode(out.getvalue()).decode())
            self.assertEqual(self.states(p), [["Actions", True], ["Risks and issues", True], ["Milestones", True]])
            self.assertNotIn("History", p.js("document.querySelector('#import-box').innerText"))
            self.assertNotIn("Decisions", p.js("document.querySelector('#import-box').innerText"))

    def test_the_choice_is_remembered_when_check_is_pressed_and_not_before(self):
        tmp = tempfile.mkdtemp(prefix="clark-655-")
        self.addCleanup(shutil.rmtree, tmp, True)
        b64 = edited(self.rig, tmp, Description="Agree the cut-over plan, version two")
        with chrome() as cdp:
            p = self.go(cdp, b64, untick=["Use cases"])
            self.assertIsNone(p.js("localStorage.getItem('clark.importSheets')"), "ticking alone keeps nothing")
            p.js("document.querySelector('#import-check').click()")
            p.until("!!document.querySelector('#import-summary')", "the check")
            self.assertEqual(json.loads(p.js("localStorage.getItem('clark.importSheets')"))["Use cases"], False)
            p.js("document.querySelector('#import-box [data-close]').click()")
            p.until("!document.querySelector('#import-box')", "the box closed")
            self.open_box(p)
            self.choose(p, b64, go=False)
            p.until("!!document.querySelector('#import-check')", "the sheets step again")
            self.assertEqual(self.states(p), [[n, n != "Use cases"] for n in SHEETS], "the last choice is back")

    def test_a_remembered_sheet_the_file_lacks_is_not_shown_and_a_new_one_is_ticked(self):
        tmp = tempfile.mkdtemp(prefix="clark-655-")
        self.addCleanup(shutil.rmtree, tmp, True)
        b64 = edited(self.rig, tmp, Description="Agree the cut-over plan, version two")
        with chrome() as cdp:
            p = self.go(cdp, b64)
            p.js("localStorage.setItem('clark.importSheets', JSON.stringify({'Decisions': false, 'Milestones': false}))")
            p.js("document.querySelector('#import-box [data-close]').click()")
            self.open_box(p)
            self.choose(p, without(b64, "Decisions"), go=False)
            p.until("!!document.querySelector('#import-check')", "the sheets step")
            self.assertEqual(self.states(p), [["Actions", True], ["Risks and issues", True], ["Milestones", False], ["Use cases", True]])

    def test_a_damaged_or_refused_memory_means_all_ticked_and_no_word(self):
        tmp = tempfile.mkdtemp(prefix="clark-655-")
        self.addCleanup(shutil.rmtree, tmp, True)
        b64 = edited(self.rig, tmp, Description="Agree the cut-over plan, version two")
        for bad in ("{not json", "[1, 2]", "7", "\"text\"", "null", "{\"Actions\": \"no\"}"):
            with self.subTest(bad=bad), chrome() as cdp:
                p = self.page(cdp)
                p.width(1400)
                p.js("localStorage.setItem('clark.importSheets', %s)" % json.dumps(bad))
                self.open_box(p)
                self.choose(p, b64, go=False)
                p.until("!!document.querySelector('#import-check')", "the sheets step")
                self.assertEqual(self.states(p), [[n, True] for n in SHEETS])
                self.assertEqual(p.js("document.querySelector('#import-problem').textContent"), "")
        with chrome() as cdp:                                          # storage that throws
            p = self.page(cdp)
            p.width(1400)
            p.js("Storage.prototype.getItem = () => { throw new Error('refused'); }; Storage.prototype.setItem = () => { throw new Error('refused'); };")
            self.open_box(p)
            self.choose(p, b64, go=False)
            p.until("!!document.querySelector('#import-check')", "the sheets step")
            self.assertEqual(self.states(p), [[n, True] for n in SHEETS])
            p.js("document.querySelector('#import-check').click()")
            p.until("!!document.querySelector('#import-summary')", "the check goes on without a memory")

    def test_the_published_page_has_no_import_and_no_memory_key(self):
        from pathlib import Path
        view = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for needle in ("importSheets", "import-sheet", "Sheets to import"):
            self.assertNotIn(needle, view, needle)


if __name__ == "__main__":
    import unittest
    unittest.main()

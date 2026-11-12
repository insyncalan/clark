"""Help PR B1: the words for the Excel sheet choice (#671) and the Commitment flag (#673), each pinned against the code.
Reads files only; starts no browser.

Run: python3 dev/run_tests.py test_help_pr_b1
"""
import json
import re
import unittest

from _paths import ROOT

SRC = ROOT / "src" / "clark"
PAGE = SRC / "page" / "src"
RAW = json.loads((PAGE / "help" / "helpContent.json").read_text(encoding="utf-8"))
TASKS = {t["id"]: t for t in RAW["howto"]["tasks"]}
SECS = {s["id"]: s for s in RAW["reference"]["sections"]}
GUIDES = {g["id"]: g for g in RAW["guides"]["guides"]} if isinstance(RAW.get("guides"), dict) else {}


def flat(o):
    if isinstance(o, str):
        return o
    if isinstance(o, list):
        return " ".join(flat(x) for x in o)
    if isinstance(o, dict):
        return " ".join(flat(v) for k, v in o.items() if k not in ("id", "g", "go"))
    return ""


def text(name):
    return (SRC / name).read_text(encoding="utf-8")


class SheetChoice(unittest.TestCase):
    def test_import_step_three(self):
        t = flat(TASKS["import-and-export"])
        self.assertIn("Press **Choose a file** (an Excel .xlsx workbook). The box **What to import** lists the sheets the workbook has, the Gantt sheet after the others, each with its rows. The sheets you ticked last time are ticked again (every sheet, the first time): untick any you do not want, then press **Continue**.", t)
        self.assertNotIn("Excel or CSV", t)
        self.assertIn('accept=".xlsx,', (PAGE / "edit" / "ImportWorkbook.jsx").read_text(encoding="utf-8"))
        cards = (PAGE / "logic" / "dataCard.js").read_text(encoding="utf-8")
        for w in ("What to import", "Continue"):
            self.assertIn(w, cards)

    def test_only_ticked_sheets_are_read(self):
        self.assertIn("Only the sheets you tick in **What to import** are read; the others are not read or changed.", flat(SECS["excel"]))
        self.assertIn("nothing in the file is imported, and the message gives the rule and the row number; untick the Gantt sheet in **What to import** to import the other sheets.", flat(SECS["excel"]))
        self.assertIn("sheets is not None and table not in sheets", text("excel_import.py"))

    def test_guide_row_limits(self):
        body = flat(RAW)
        self.assertIn("shows **more than 2,000 rows**. It is refused whole when you press **Continue**, and the message says so.", body)
        self.assertNotIn("cannot be imported as it is", body)
        self.assertIn("MAX_ROWS = 2000", text("excel_import.py"))
        self.assertIn("SHEET_ROWS_SHOWN = 2000", (PAGE / "logic" / "dataCard.js").read_text(encoding="utf-8"))


class Commitment(unittest.TestCase):
    def test_the_words_and_the_empty_cell(self):
        t = flat(SECS["excel"])
        self.assertIn("The Use cases sheet has a Commitment column that reads Planned 2026, Committed or Planned 2027, spelt exactly like that, or is left empty.", t)
        self.assertIn("An empty Commitment cell on import leaves the flag as it is; it never clears it.", t)
        self.assertIn('COMMITMENTS = ("Planned 2026", "Committed", "Planned 2027")', text("store.py"))
        imp = text("excel_import.py")
        # the word is stripped once, an old Candidate is mapped to Planned 2026, then checked against the list
        self.assertIn("word = str(value).strip()", imp)
        self.assertIn("if word in writer.COMMITMENTS", imp)
        self.assertRegex(imp, r'if f == "commitment" and v is None:\s+continue')
        self.assertIn('("Commitment", "commitment")', text("excel.py"))

    def test_word_note(self):
        self.assertEqual(TASKS["word-in-and-out"]["n"], "The use case table in the Word report has a Commitment column.")
        self.assertIn('["Ref", "Use case", "Status", "Commitment", "Headline", "Work items"]', text("docx_build.py"))

    def test_nothing_about_the_page_or_publishing_the_flag(self):
        for sec in (SECS["excel"], TASKS["word-in-and-out"], TASKS["import-and-export"]):
            for m in re.finditer(r"[^.]*\bCommitment\b[^.]*\.", flat(sec)):
                self.assertNotRegex(m.group(0).lower(), r"dashboard|publish|page")


if __name__ == "__main__":
    unittest.main()

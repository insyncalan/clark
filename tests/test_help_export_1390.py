"""Row 1390 slice 11: the Help words for the Excel export redesign. Reads helpContent.json only; starts no browser.

Run: bash ~/wo/loadgate.sh -p 70 -- python3 dev/run_tests.py test_help_export_1390
"""
import json
import unittest

from _paths import ROOT

RAW = json.loads((ROOT / "src" / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
GUIDE = next(g for g in RAW["guides"] if g["id"] == "send-the-workbook-out")
STEPS = [s["d"] for s in GUIDE["steps"]]
ALL = json.dumps(RAW, ensure_ascii=False)
REFUSAL = "This is a client copy of the report. Import the Excel you exported from the editor."


class ExportHelp(unittest.TestCase):
    def test_the_guide_opens_on_the_report_not_the_cover(self):
        self.assertIn("It opens on the Report sheet", STEPS[4])
        self.assertNotIn("Cover", " ".join(STEPS))
        self.assertIn("Report sheet", GUIDE["result"])
        self.assertNotIn("Cover", GUIDE["result"])

    def test_the_sheets_step_names_documents_history_filters_and_colours(self):
        s = STEPS[5]
        for w in ("Documents, which is read only", "The top row stays in view and has filters", "grey cells are locked",
                  "Priority and Status are coloured as on the page", "A hidden History sheet",
                  "Changes made on the Report, Documents and History sheets are ignored"):
            self.assertIn(w, s)

    def test_the_client_copy_is_explained_in_the_guide_and_on_the_published_page(self):
        self.assertIn("client copy: it leaves out the rows hidden from the client and the columns that say Client visible, and a client copy cannot be imported", STEPS[6])
        self.assertIn("The Excel file is the client copy: it holds only the rows the report shows, has no Client visible or On the dashboard columns, no Internal note and no History sheet, and cannot be imported back.", ALL)

    def test_the_import_words_give_the_refusal_sentence_and_the_old_state_columns(self):
        self.assertIn(REFUSAL, ALL)
        self.assertIn("the old State columns (State chosen and Chosen by you) are ignored without a message", ALL)

    def test_settings_help_says_report_documents_history(self):
        self.assertIn("The **Report** sheet comes first", ALL)
        self.assertIn("**Documents** lists the report’s documents and links", ALL)
        self.assertIn("it is hidden, so right-click a sheet tab and choose Unhide", ALL)
        self.assertNotIn("The **Cover** sheet", ALL)

    def test_no_phone_words_and_no_straight_cover_left_in_the_export_help(self):
        self.assertNotIn("Cover sheet", ALL)
        self.assertNotIn("on the Cover", ALL)


if __name__ == "__main__":
    unittest.main()

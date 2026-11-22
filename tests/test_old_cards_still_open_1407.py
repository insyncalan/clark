"""Row 1407: a new report can no longer add a Risks and issues, Open actions or Decisions card, but a report that already holds those
three cards still opens in the page, still publishes and still exports to Excel.

Run: python3 dev/run_tests.py test_old_cards_still_open_1407
A real store and a real server (the neighbour test_published_cards_plain and test_glance_page set them up), the three old sections
planted the way an older report has them, no mock. All rows are fictional.
"""
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

import test_glance_page as glance
from _publish import PublishedFile
from test_server import chrome

from clark import excel

OLD = {"raid": "Risks and issues", "actions": "Open actions", "decisions": "Decisions"}
SHEETS = ("Actions", "Risks & Issues", "Decisions")


class OldCards(PublishedFile, glance.Setup):
    def setUp(self):
        super().setUp()
        self.demo.plant_builtin_sections()      # the three old cards, as an older report holds them
        have = {r[0]: r[1] for r in self.store.con.execute("SELECT type, title FROM report_sections WHERE project = 'ABC'")}
        for kind, title in OLD.items():
            self.assertEqual(have.get(kind), title, f"the old {kind} card is in the store")

    def test_the_old_cards_open_in_the_page(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.until("document.querySelectorAll('.secs > .sec').length >= 3", "the sections drew")
            text = p.js("document.querySelector('#main').textContent")
            for title in OLD.values():
                self.assertIn(title, text, f"the old card {title} opens")
            self.assertIn("Key person leaves", text, "the risk row is drawn in its old card")
            self.assertIn("Use the shared drive", text, "the decision row is drawn in its old card")
            self.assertIn("Chase the supplier file", text, "the action row is drawn in its old card")

    def test_the_old_cards_are_in_the_published_file(self):
        path = self.publish()
        text = path.read_text(encoding="utf-8")
        for title in OLD.values():
            self.assertIn(title, text)
        with chrome() as cdp:
            p = self.draw(cdp, path)
            body = p.js("document.body.textContent")
            for words in ("Key person leaves", "Use the shared drive", "Chase the supplier file"):
                self.assertIn(words, body, "the published file shows the row of the old card")

    def test_the_old_cards_do_not_stop_the_excel_export(self):
        out = Path(tempfile.mkdtemp(prefix="clark-1407-"))
        self.addCleanup(__import__("shutil").rmtree, out, True)
        path = out / "w.xlsx"
        excel.export_project(self.store, "ABC", path, out / "s.json", on="2030-06-01", exported_by="Sam Example")
        book = load_workbook(path)
        for name in SHEETS:
            self.assertIn(name, book.sheetnames)
        cells = " ".join(str(c.value) for name in SHEETS for row in book[name].iter_rows() for c in row if c.value)
        for words in ("Key person leaves", "Use the shared drive", "Chase the supplier file"):
            self.assertIn(words, cells)


if __name__ == "__main__":
    unittest.main()

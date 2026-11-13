"""Item 454: the Import from Excel words are the prototype's (system/prototype/io.js, views.js), read from the prototype itself so
they cannot drift. No browser needed. Run: python3 dev/run_tests.py test_import_words
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTO = ROOT / "system" / "prototype"
CARD = (ROOT / "src/clark/page/src/logic/dataCard.js").read_text(encoding="utf-8")
BOX = (ROOT / "src/clark/page/src/edit/ImportWorkbook.jsx").read_text(encoding="utf-8")
IO = (PROTO / "io.js").read_text(encoding="utf-8")


def quoted(name):
    return re.search(name + r': "((?:[^"\\]|\\.)*)"', CARD).group(1)


class ImportWords(unittest.TestCase):
    def test_the_first_box_keeps_the_prototypes_rules_about_ids_and_refusals(self):
        # #655: the sentence about which sheets are read is no longer the prototype's (the person chooses); the rest of it still is
        text = re.sub(r"<[^>]+>", "", IO).replace("\n", " ")
        for piece in ("You see the changes before anything is saved. "
                      "If a row breaks a rule, nothing is imported and you are told which rows.",):
            self.assertIn(piece, quoted("pickBody"))
            self.assertIn(piece, text)

    def test_the_data_card_says_what_the_prototype_says(self):
        views = (PROTO / "views.js").read_text(encoding="utf-8")
        self.assertIn(quoted("note"), views)

    def test_the_check_screen_has_the_prototypes_words(self):
        for word in ("Accept all", "Reject all", "Changes to check", "Accept", "Reject"):
            self.assertIn(f'"{word}"', CARD)
            self.assertIn(word, IO)
        self.assertIn("Nothing was imported, because ${k} ${k === 1 ? \"row breaks a rule\" : \"rows break a rule\"}:", CARD)
        self.assertIn("Nothing was imported, because ${k} ${k === 1 ? 'row breaks a rule' : 'rows break a rule'}:", IO)
        self.assertIn("Fix ${k === 1 ? \"it\" : \"them\"} in the workbook and import again. Nothing was changed.", CARD)
        self.assertIn("Fix ${k === 1 ? 'it' : 'them'} in the workbook and import again. Nothing was changed.", IO)

    def test_the_check_screen_has_buttons_not_tick_boxes(self):
        self.assertIn('type="radio"', BOX)
        self.assertNotIn('type="checkbox"', BOX)


class ApprovedWordsArePinned(unittest.TestCase):
    """The owner approved these sentences for item 454 ("yes to all", seven points). Each is pinned here exactly, so a change to one is a
    change to approved wording and fails this test. Words that are the prototype's own are pinned against the prototype above."""

    def test_the_first_box(self):
        self.assertEqual(quoted("pickBody"),
                         "Sheets called Actions, Risks & Issues, Decisions, Milestones and Use cases can be imported. "
                         "You choose which after you pick a file (a History sheet from an export is left alone). "
                         "Every sheet needs an ID column. A row whose ID exists updates it; a row with that column blank adds a new one. You see the changes before anything is saved. "
                         "If a row breaks a rule, nothing is imported and you are told which rows.")
        self.assertNotIn("(or RAID)", CARD)

    def test_the_sheet_choice_words(self):
        self.assertEqual(quoted("sheetsTitle"), "What to import")
        self.assertEqual(quoted("sheetsBody"), "Tick the sheets to import. Anything you leave unticked is not read and not changed.")
        self.assertEqual((quoted("selectAll"), quoted("clear")), ("Select all", "Clear"))
        self.assertEqual(quoted("tickOne"), "Tick at least one sheet.")
        self.assertEqual(quoted("continue"), "Continue")      # the wording the other two-step boxes (Publish, Word) already use
        self.assertIn('`${s.name} (${s.rows > SHEET_ROWS_SHOWN ? "more than 2,000 rows" : `${s.rows} ${s.rows === 1 ? "row" : "rows"}`})`', CARD)

    def test_the_data_card_note_is_only_the_prototypes_sentence(self):
        self.assertEqual(quoted("note"), "The workbook has a sheet each for actions, risks and issues, decisions, milestones and use cases.")

    def test_the_counts_row_and_the_sheet_line(self):
        for piece in ('[c.new || 0, "new"]', '[c.changed || 0, "updated"]', 'r.refused.length) row.push([r.refused.length, "refused"])',
                      'row.push([c.removed, "not in the workbook"])'):
            self.assertIn(piece, CARD)
        self.assertNotIn("unchanged", re.search(r"export function countsRow.*?\n}", CARD, re.S).group(0))
        self.assertIn('`${name}: ${of(tables, "new")} new, ${of(tables, "changed")} updated`', CARD)
        for sheet in ('"Work items"', '"Milestones"', '"Use cases"'):
            self.assertIn(sheet, CARD)
        self.assertIn('.join(" · ")', CARD)

    def test_the_accept_and_reject_words(self):
        self.assertEqual(quoted("changesToCheck"), "Changes to check")
        self.assertEqual((quoted("accept"), quoted("reject")), ("Accept", "Reject"))
        self.assertEqual((quoted("acceptAll"), quoted("rejectAll")), ("Accept all", "Reject all"))
        self.assertEqual(quoted("acceptNote"), "Accept archives it. It is not deleted.")
        self.assertEqual(quoted("newNote"), "gets the next free ID")

    def test_the_unrecorded_workbook_warning_says_accepted_not_ticked(self):
        said = quoted("unrecorded")
        self.assertEqual(said, "There is no record of exporting this workbook from clark, so clark cannot say what you changed in it. "
                               "Check it is the right file; every difference is listed and nothing is accepted that archives a row.")
        self.assertNotIn("ticked", said)

    def test_the_lines_carried_over_say_accept_all(self):
        self.assertIn("It changed in clark after the workbook was made.", BOX)
        self.assertIn("Not imported: {t}", BOX)
        self.assertIn("more, of which {hiddenOn} will be imported", BOX)
        self.assertNotIn("ticks above", BOX)


class SheetRowWords(unittest.TestCase):
    """#655: a sheet's row count in the "What to import" box. Above 2,000 the box says so in words, never a wrong number."""
    def test_sheet_labels_from_the_page_function(self):
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("no node")
        src = Path(__file__).resolve().parents[1] / "src/clark/page/src/logic/dataCard.js"
        with tempfile.TemporaryDirectory() as tmp:
            mod = Path(tmp) / "dataCard.mjs"
            mod.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            probe = Path(tmp) / "probe.mjs"
            probe.write_text('import { sheetWord } from "./dataCard.mjs";\n'
                             'console.log(JSON.stringify([[\'Actions\', 12], [\'Decisions\', 1], [\'Milestones\', 0], [\'Actions\', 2000], [\'Actions\', 2001]]'
                             '.map(([name, rows]) => sheetWord({ name, rows }))));', encoding="utf-8")
            done = subprocess.run([node, str(probe)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), ["Actions (12 rows)", "Decisions (1 row)", "Milestones (0 rows)",
                                                   "Actions (2000 rows)", "Actions (more than 2,000 rows)"])


if __name__ == "__main__":
    unittest.main()

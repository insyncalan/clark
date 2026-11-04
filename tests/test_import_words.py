"""Item 454: the Import from Excel words are the prototype's (system/prototype/io.js, views.js), read from the prototype itself so
they cannot drift. No browser needed. Run: python3 dev/run_tests.py test_import_words
"""
import re
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
    def test_the_first_box_says_what_the_prototype_says(self):
        say = quoted("pickBody")
        self.assertIn(say, re.sub(r"<[^>]+>", "", IO).replace("\n", " "))

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
        # item 655: the one place with tick boxes is the choice of sheets, before the check; the changes themselves stay buttons
        self.assertIn('type="radio"', BOX)
        self.assertEqual(BOX.count('type="checkbox"'), 1)
        self.assertIn('name="import-sheet"', BOX)


class ApprovedWordsArePinned(unittest.TestCase):
    """The owner approved these sentences for item 454 ("yes to all", seven points). Each is pinned here exactly, so a change to one is a
    change to approved wording and fails this test. Words that are the prototype's own are pinned against the prototype above."""

    def test_the_first_box(self):
        self.assertEqual(quoted("pickBody"),
                         "Sheets called Actions, Risks and issues, Decisions, Milestones and Use cases are read (a History sheet from an export is left alone). "
                         "A row whose ID exists updates it; a row without an ID adds a new one. You see the changes before anything is saved. "
                         "If a row breaks a rule, nothing is imported and you are told which rows.")
        self.assertNotIn("(or RAID)", CARD)

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
        self.assertIn("and {items.length - SHOWN} more, taken as Accept all is for the rest: new and changed rows with no problem.", BOX)
        self.assertNotIn("ticks above", BOX)


class SheetChoiceWordsArePinned(unittest.TestCase):
    """Item 655: the words of the choice of sheets, pinned exactly. Each is one the owner signs; a change fails here."""

    def test_the_heading_the_two_links_the_button_and_the_none_line(self):
        self.assertEqual(quoted("sheetsHead"), "Sheets to import")
        self.assertEqual((quoted("selectAll"), quoted("clear")), ("Select all", "Clear"))
        self.assertEqual(quoted("check"), "Check")
        self.assertEqual(quoted("noSheets"), "Tick at least one sheet to import.")

    def test_each_tick_is_the_sheets_own_name_and_no_other_word_is_added(self):
        self.assertIn("{n}</label>", BOX)
        self.assertIn("T.sheetsHead", BOX)
        for key in ("selectAll", "clear", "noSheets", "check"):
            self.assertIn(f"T.{key}", BOX)

    def test_the_sheets_are_the_five_the_first_box_lists_and_a_history_sheet_is_never_offered(self):
        self.assertIn("SHEET_NAMES = IMPORT_COLUMNS.map(([sheet]) => sheet)", CARD)
        self.assertNotIn("History", re.search(r"export const IMPORT_COLUMNS.*?\n\];", CARD, re.S).group(0))

    def test_the_choice_is_kept_in_this_browser_only(self):
        self.assertIn('const MEMORY = "importSheets"', CARD)
        remember = (ROOT / "src/clark/page/src/logic/remember.js").read_text(encoding="utf-8")
        self.assertIn("window.localStorage", remember)
        self.assertNotIn("api.", re.sub(r"//.*", "", CARD.split("const MEMORY")[1].split("export const ticked")[0]))


if __name__ == "__main__":
    unittest.main()

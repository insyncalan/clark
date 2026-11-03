"""clark 0.9's hand checks as tests: the 0.9 features that have merged to main. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v090

Same shape as test_v070 and test_v060.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written before the cut, from origin/main on 04-11-2026, from the board's v0.9 items (19). Merged and visible, in the notes: the
settings chips that stay in view (#440), About you saying what was saved with Undo (#440), the progress section's tiles, bar and
Achieved column (#451), the chase tone control (#452) and the Work items letter badge, grouped cards and eye column (#456), with the
date picker above a message (#456). On main and covered here but not told again in the notes: the Expected chip (#435, in the code since
0.6.0), a use case's next steps (#441, since 0.6.0) and the Help look, Publishing link and Preview address (#459, in the 0.7.0 notes).
Behind the scenes only: #447 (the Help entries still to come are recorded in helpLater.json). Not merged, so WAITING: #287 (PR 537), #436
(PR 504), #437 (PR 262), #439 (PR 458 and PR 527), #442 (no pull request), #444 (PR 461), #448 (PR 534), #450 (PR 503), #454 (PR 501
and PR 498), #457 (PR 383) and #485 (PR 500).
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.9.0, then fail if they are wrong.
The notes' own rules (title, the Beta line, plain words, the data-layout paragraph) are read from the tree now.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.9.0"
SCHEMA_AT_0_8_0 = 11     # the layout on main when this was written (the same as 0.6.0); the notes name a step only if it differs

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#440", "The Settings chips are a bar of their own under the top bar, on the page ground, and never hide a card scrolled into view",
     "test_settings_bar::SettingsBar::test_C_the_bar_stays_under_the_top_bar_on_the_page_ground_and_never_hides_a_card"),
    ("#440", "The chip of the card you are reading is marked as you scroll",
     "test_settings_bar::SettingsBar::test_C_the_marked_chip_follows_the_card_you_are_reading_as_you_scroll"),
    ("#440", "Saving the name or the email says so with Undo, and a second save of the same words says nothing",
     "test_about_you::AboutYou::test_C_saving_the_name_or_the_email_says_so_with_undo_and_a_second_save_of_the_same_words_says_nothing"),
    ("#440", "Undo puts the old value back in the box, the menu and the store",
     "test_about_you::AboutYou::test_C_undo_puts_the_old_value_back_in_the_box_the_menu_and_the_store"),
    ("#451", "The progress section's Overall is three tiles, a labelled bar and a 0% to 100% scale",
     "test_tracker_page::Page::test_view_overall_is_three_tiles_a_labelled_bar_and_a_scale"),
    ("#451", "The Achieved column has a bar, the figure and the red chip",
     "test_tracker_page::Page::test_view_achieved_column_has_a_bar_the_figure_and_the_red_chip"),
    ("#451", "The author's weights note is in Edit and not in View",
     "test_tracker_page::Page::test_the_weights_note_is_in_edit_for_the_author_and_not_in_view"),
    ("#452", "A chase shows the three tones, with clark's own choice picked, and how often it was chased",
     "test_draft_email_editor::Component::test_a_chase_shows_the_three_tones_preselected_to_clarks_choice_and_the_count"),
    ("#452", "Picking a tone asks for a new draft, and changing the kind hands the choice back to clark",
     "test_draft_email_editor::Component::test_picking_a_tone_asks_for_a_new_draft_and_changing_the_kind_hands_the_choice_back"),
    ("#452", "Only a chase has the tone control", "test_draft_email_editor::Component::test_only_a_chase_has_the_tone_control"),
    ("#452", "No tone word reaches the email", "test_draft_email::ToneChoice::test_no_tone_word_reaches_the_email"),
    ("#456", "Work items has a letter badge, no Type column, an eye column and a card for each group, in both modes and themes",
     "test_work_table_parity::Table::test_letter_badge_no_type_column_eye_column_and_a_card_per_group_in_both_modes_and_themes"),
    ("#456", "In Edit the eye turns an item off or on with a message and Undo",
     "test_work_table_parity::Table::test_the_eye_in_edit_turns_an_item_off_and_on_with_a_toast_and_undo"),
    ("#456", "In View the eye is a mark only and a click changes nothing",
     "test_work_table_parity::Table::test_the_eye_in_view_is_a_read_only_mark_and_a_click_changes_nothing"),
    ("#456", "A published file has no eye and no client column",
     "test_work_table_parity::Table::test_a_published_file_has_no_eye_and_no_client_column"),
    ("#435", "The Expected chip in the milestone calendar is whole at 900 px and in Quarter",
     "test_milestones_page::RealBrowser::test_the_expected_chip_is_whole_at_900_px_and_in_quarter"),
    ("#441", "A use case's next steps are every open item in the client's wording, with the owner in a circle",
     "test_glance_page::UseCases::test_next_steps_are_every_open_item_in_the_client_wording_with_the_owner_in_a_circle"),
    ("#459", "Help is a page of cards with a search icon and a key chip",
     "test_help_panel::Panel::test_help_is_a_page_of_cards_with_a_search_icon_and_a_key_chip"),
    ("#459", "With no client folder, To client links to the Publishing card",
     "test_publish_dialog::NoFolder::test_C_set_it_in_settings_publishing_is_a_link_to_the_publishing_card"),
    ("#459", "A preview address opened a second time shows a plain page, not a bare message",
     "test_preview_export_route::Preview::test_a_second_visit_shows_a_plain_page_not_a_bare_message"),
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
    ("#287", "One View menu on the filter line holds Layout, Group by, Swimlanes and saved views", "PR 537",
     "page/src/components/FilterLine.jsx", "export function layoutItems"),
    ("#436", "Milestones: an archived milestone opens read only in the peek, with the eye and one-line rows", "PR 504",
     "page/src/edit/ArchivedPeek.jsx", "export function ArchivedPeek"),
    ("#437", "Publish: the finished line, the warning words and the footer follow the prototype (rows 25, 27 and 29)", "PR 262",
     "page/src/edit/publishLine.js", "export const doneWords"),
    ("#439", "The Week ending box is in View as well as Edit, with the coming Friday as its value", "PR 458",
     "page/src/logic/week.js", "export const shownDay"),
    ("#439", "The project switcher is always a button with open counts, Project settings and a Switched-to message", "PR 527",
     "page/src/edit/ProjectSwitch.jsx", "export const openWords"),
    ("#442", "The remaining rows of Work items Duplicate and editing in View (rows 41 and 43 of the issue)",
     "no pull request yet (issue 442)", "", None),
    ("#444", "Settings Data card and Projects table: Import workbook, Reset the demo data, Add and Edit project", "PR 461",
     "page/src/logic/dataCard.js", "export const DATA"),
    ("#448", "Work items: a rating whatever the status, the live status look and the same status picker in the peek", "PR 534",
     "page/src/edit/itemEdit.js", "export function statusPill(row, today)"),
    ("#450", "Archived items open read only in the peek with one Restore, and the Show archived pill remembers its state", "PR 503",
     "page/src/edit/ArchivedItems.jsx", "export function ArchivedPill"),
    ("#454", "Settings People card: email, organisation, role and Paste from Excel", "PR 501",
     "page/src/edit/People.jsx", "export function People"),
    ("#454", "The Excel import page as the prototype: Check the import, accept or reject each change", "PR 498",
     "page/src/logic/dataCard.js", "export function rejectAll"),
    ("#457", "The peek's Latest update with Draft and a Last updated stamp, and the overdue warning bar", "PR 383",
     "page/src/edit/PeekLatest.jsx", "export function PeekLatest"),
    ("#485", "The use case row on the Dashboard in Edit: the eye, Where it stands, add a next step, link a work item", "PR 500",
     "page/src/logic/ucRow.js", "export function splitStep"),
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#440", "The Settings chip bar reads well as you scroll", "judgement",
     "only a person can say the bar does not jump, the marked chip is clear and no card is hidden under it",
     "Open Settings, scroll down and press a chip, at 1400 and 900 px, light and dark."),
    ("#451", "The Overall tiles and the Achieved bar read as the approved design", "judgement",
     "only a person can compare the tiles, the Planned label and the bar with the approved weekly design",
     "Add a progress section, fill a few lines, and look at the Overall and the Achieved column at 1400 and 900 px, light and dark."),
    ("#452", "The tone control reads well in the Draft email", "judgement",
     "only a person can say the three tones and the line beside them look like the prototype's",
     "Open Draft email on an owner's overdue items, choose Chase, and press each tone at 1400 and 900 px, light and dark."),
    ("#456", "The Work items table reads as the prototype's", "judgement",
     "only a person can compare the letter badge, the group cards and the eye with the prototype",
     "Open Work items in View and in Edit at 1400 and 900 px, light and dark."),
    ("#456", "A date picker low in the table is clickable while a message shows", "live only",
     "the order of the picker and the messages at the bottom left needs a real screen at 900 px",
     "In Edit at 900 px open the Due picker of a low row while a message shows, and press No date."),
]

BANNED_WORDS = ("apply", "applied", "staged", "proposal", "sweep", "tracker", "vault", "extract")


def names_in(path):
    """{class name: {test method names}} in a test file, read without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {c.name: {f.name for f in c.body if isinstance(f, ast.FunctionDef)} for c in tree.body if isinstance(c, ast.ClassDef)}


def version():
    found = re.search(r'__version__\s*=\s*"([^"]+)"', (ROOT / "src" / "clark" / "__init__.py").read_text(encoding="utf-8"))
    return found.group(1) if found else None


def schema_version():
    found = re.search(r"(?m)^SCHEMA_VERSION\s*=\s*(\d+)", (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8"))
    return int(found.group(1)) if found else None


def landed(path, marker):
    """True when the file exists and holds the marker; None for a row with no marker (no pull request yet)."""
    if marker is None:
        return None
    p = ROOT / "src" / "clark" / path
    return p.is_file() and marker in p.read_text(encoding="utf-8")


class Tables(unittest.TestCase):
    def test_every_covering_test_named_here_exists(self):
        out = []
        for item, check, where in COVERED:
            name, cls, test = where.split("::")
            path = TESTS / (name + ".py")
            found = names_in(path) if path.is_file() else {}
            if test not in found.get(cls, ()):
                out.append(f"{item} {check}: {where}")
        self.assertEqual(out, [])

    def test_each_check_is_in_one_list_only_and_each_walk_through_check_says_why_and_what_to_do(self):
        checks = [c for _, c, _ in COVERED] + [c for _, c, *_ in WAITING] + [c for _, c, _, _, _ in WALK_THROUGH]
        self.assertEqual(sorted(c for c in set(checks) if checks.count(c) > 1), [])
        for item, check, kind, why, does in WALK_THROUGH:
            self.assertIn(kind, ("judgement", "live only"), check)
            self.assertTrue(why.strip() and does.strip(), check)

    def test_each_waiting_check_names_its_pull_request_or_says_there_is_none(self):
        for item, check, pr, path, marker in WAITING:
            self.assertRegex(pr, r"^(PR \d+|no pull request yet \(issue \d+\))$", check)
            self.assertEqual(marker is None, pr.startswith("no pull request"), check)

    def test_the_sheet_has_a_row_for_every_waiting_pull_request_and_every_covered_item(self):
        sheet = (ROOT / "dev" / "handchecks" / (VERSION + "-sheet.md")).read_text(encoding="utf-8")
        for item, check, pr, path, marker in WAITING:
            self.assertIn("WAITING " + pr, sheet, check)
            self.assertIn(item, sheet, check)
        for item in {i for i, _, _ in COVERED}:
            self.assertIn(item, sheet, f"{item} has no row on the hand-check sheet")


class Notes(unittest.TestCase):
    """The notes' own rules, read from the tree now (the same for every release): a title that says Beta, the Beta line, plain words,
    no lower-case 'ask clark' in a heading, and the data-layout paragraph only when the layout has changed since the last release."""

    def setUp(self):
        self.text = (ROOT / "dev" / "release-notes" / (VERSION + "-plain.md")).read_text(encoding="utf-8")

    def test_the_title_and_the_beta_line(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("Beta means the whole of clark is Beta until version 1.0.", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_data_layout_paragraph_is_there_only_when_the_layout_changed(self):
        said = "This version includes a change to how clark stores your data" in self.text
        self.assertEqual(said, schema_version() != SCHEMA_AT_0_8_0,
                         "the notes must say a layout step is in exactly when SCHEMA_VERSION in store.py is not %d" % SCHEMA_AT_0_8_0)

    def test_a_date_in_the_notes_is_day_first(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 0.9.1 and later have their own test_vNNN
            self.skipTest(f"the cut commit is not made yet (version is {found}); it sets {VERSION} in src/clark/__init__.py")
        return found

    def test_the_version_is_the_release(self):
        self.assertEqual(self.cut_made(), VERSION)

    def test_the_plain_release_notes_exist_and_name_the_version(self):
        v = self.cut_made()
        notes = ROOT / "dev" / "release-notes" / f"{v}-plain.md"
        self.assertTrue(notes.is_file(), "dev/release-notes/%s-plain.md" % v)
        self.assertIn(v, notes.read_text(encoding="utf-8"))

    def test_the_hand_check_sheet_exists(self):
        v = self.cut_made()
        self.assertTrue((ROOT / "dev" / "handchecks" / f"{v}-sheet.md").is_file())

    def test_a_waiting_row_whose_pull_request_has_landed_has_been_moved_to_covered(self):
        self.cut_made()
        out = [f"{item} {pr}: it is in main now; give it a covering test in COVERED, a line in the notes and a row in the sheet"
               for item, check, pr, path, marker in WAITING if landed(path, marker)]
        self.assertEqual(out, [])


def _skips():
    for i, (item, check, kind, why, does) in enumerate(WALK_THROUGH):
        def t(self, _m=f"needs a person ({kind}): {why}. Do this: {does}"):
            self.skipTest(_m)
        t.__name__ = "test_%s_%d_needs_a_person" % (re.sub(r"\W", "_", item), i)
        t.__doc__ = check
        setattr(Walk, t.__name__, t)
    for i, (item, check, pr, path, marker) in enumerate(WAITING):
        def w(self, _m=f"PENDING = '{pr}': not merged yet; this row runs once it lands and the cut commit is made", _a=(path, marker)):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (re.sub(r"\W", "_", item), i)
        w.__doc__ = check
        setattr(Walk, w.__name__, w)


class Walk(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips()

if __name__ == "__main__":
    unittest.main()

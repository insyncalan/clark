"""clark 0.7's hand checks as tests: the 0.7 features that have merged to main. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v070

Same shape as test_v060.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written before the cut, from origin/main on 03-11-2026. In 0.7.0 so far (merged and visible): the peek's Up and Down (#246) and
slide-out (#450), the calendar's keys (#481), the dashboard's use cases in Edit (#455), New chat in ask clark (#407), Help like the
prototype and the Publish and Preview words (#459), the AI card in Settings (#72), the About you path (#422), saved views that stay
listed (#589), "Not written yet." (#375), the documents link check (#594), the short value after "api key" (#583, #527), a lost
number race (#388), a null character in the logo rule (#493), the right-click menu (#97), hand over (#199) and the Word client copy's
held-back check (#618) and the unknown-kind document (#595). Not merged, so WAITING: #325 (PR 474, a data layout step), #620 (PR 541) and #622 (PR 542).
#220, #171, #160, #269 and #427 are not in this cut: they go to 0.8. Left out on purpose: #196 (in 0.5.0), #198 (in the code since 0.4.0, in no notes) and #270 (in 0.6.0).
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.7.0, then fail if they are wrong.
The notes' own rules (title, the Beta line, plain words, the data-layout paragraph) are read from the tree now.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.7.0"
SCHEMA_AT_0_6_0 = 11

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#246", "With the peek open, Down and Up from Close step to the next and previous item and the keyboard stays",
     "test_peek_arrows::Arrows::test_down_and_up_from_close_step_through_the_list_and_the_focus_stays"),
    ("#246", "The peek does not wrap at the ends and a line only a screen reader hears says so",
     "test_peek_arrows::Arrows::test_the_ends_do_not_wrap_and_the_line_says_so"),
    ("#246", "Esc puts the keyboard on the row of the item the peek was showing",
     "test_peek_arrows::Arrows::test_esc_puts_the_focus_on_the_row_of_the_item_shown"),
    ("#450", "Closing the peek slides a copy out and it goes away",
     "test_peek_exit::PeekExit::test_closing_slides_a_copy_out_and_it_goes_away"),
    ("#450", "With Reduce motion on nothing slides", "test_peek_exit::PeekExit::test_under_reduced_motion_nothing_slides"),
    ("#481", "On a day in the calendar Left, Right, Up and Down move a day or a week and the Tab stop follows",
     "test_milestones_page::RealBrowser::test_left_right_up_and_down_move_a_day_or_a_week_and_the_tab_stop_goes_with_the_focus"),
    ("#481", "Enter on a day with milestones goes to its first milestone, and on an empty day does nothing",
     "test_milestones_page::RealBrowser::test_enter_on_a_day_with_milestones_goes_to_its_first_chip_and_on_an_empty_day_does_nothing"),
    ("#481", "Shift+Tab or Esc on a milestone goes back to its day, and with a peek open Esc closes the peek",
     "test_milestones_page::RealBrowser::test_shift_tab_or_esc_on_a_chip_goes_back_to_its_day_but_with_a_peek_open_esc_closes_the_peek"),
    ("#455", "In Edit a use case row has the status button, the growing Add and the link to add from the project record; View has none",
     "test_uc_dashboard_edit::Edit::test_view_has_none_of_it_and_edit_has_the_button_the_status_buttons_and_the_link"),
    ("#455", "The status menu changes the status in one step with Undo",
     "test_uc_dashboard_edit::Edit::test_the_status_menu_changes_the_status_in_one_step_with_undo"),
    ("#455", "The headline and the name change in place, and a press in them does not open the row",
     "test_uc_dashboard_edit::Edit::test_the_headline_and_the_name_change_in_place_and_a_press_in_them_does_not_open_the_row"),
    ("#455", "Add use case opens the box and adds the use case, hidden from the client until its eye is turned on",
     "test_uc_dashboard_edit::Edit::test_add_use_case_opens_the_box_and_adds_it_hidden_from_the_client"),
    ("#455", "An ID already used is not added", "test_uc_dashboard_edit::Edit::test_an_id_already_used_is_not_added"),
    ("#455", "Add from your project record offers the use cases that are off the dashboard and puts them on",
     "test_uc_dashboard_edit::Edit::test_add_from_your_project_record_offers_the_use_cases_that_are_off_and_puts_them_on"),
    ("#455", "A published file has none of the use case editing",
     "test_uc_dashboard_edit::PublishedFile::test_the_file_has_none_of_edit_for_the_use_cases"),
    ("#455", "A new use case has its ID from clark and starts hidden from the client",
     "test_changes_use_cases::New::test_a_new_use_case_has_its_id_from_clark_its_reference_and_starts_hidden_from_the_client"),
    ("#407", "New chat drops the earlier turns so a stopped chat can start again",
     "test_ask_panel::Panel::test_new_chat_drops_the_earlier_turns_so_a_refused_chat_can_start_again"),
    ("#459", "The top bar has a Help button and Help has a Back button",
     "test_help_panel::Panel::test_the_top_bar_has_a_help_button_and_help_has_a_back_button"),
    ("#459", "Help is a page of cards with a search icon and a key chip",
     "test_help_panel::Panel::test_help_is_a_page_of_cards_with_a_search_icon_and_a_key_chip"),
    ("#459", "A search result marks the word that matched", "test_help_panel::Panel::test_a_result_marks_the_matched_word"),
    ("#459", "With no client folder, To client links to the Publishing card in Settings",
     "test_publish_dialog::NoFolder::test_C_set_it_in_settings_publishing_is_a_link_to_the_publishing_card"),
    ("#459", "A preview address opened a second time shows a plain page, not a bare message",
     "test_preview_export_route::Preview::test_a_second_visit_shows_a_plain_page_not_a_bare_message"),
    ("#72", "Without the AI route the Settings card says AI suggestions come in a later version",
     "test_ai_settings::Line::test_without_the_route_the_line_says_it_comes_in_a_later_version"),
    ("#422", "The History footnote and the Excel cover name Settings, Personal, About you",
     "test_about_you_path::AboutYouPath::test_the_history_footnote_and_the_excel_cover_name_the_real_path"),
    ("#589", "A saved view the filter line cannot read says why in plain words",
     "test_filter_line::SavedViews::test_a_view_the_line_cannot_read_says_why_in_plain_words"),
    ("#589", "A saved view the filter line cannot read stays listed and can be renamed or archived",
     "test_filter_line_page::Line::test_a_saved_view_the_line_cannot_read_stays_listed_says_why_and_can_be_renamed_or_archived"),
    ("#375", "A use case in the list says Not written yet.",
     "test_empty_state_words::EmptyStateWordsTest::test_use_case_summary_row_says_not_written_yet"),
    ("#375", "A use case's page says exactly Not written yet.",
     "test_empty_state_words::EmptyStateWordsTest::test_use_case_detail_read_only_says_exactly_not_written_yet"),
    ("#375", "In Edit an empty use case says how to add text",
     "test_empty_state_words::EmptyStateWordsTest::test_use_case_detail_edit_says_how_to_add_text"),
    ("#594", "Each internal address, now with localdomain, arpa, router and the four documentation ranges, is turned away with the internal message",
     "test_doclinks::InternalAddresses::test_each_internal_address_is_refused_with_the_internal_message"),
    ("#583", "A short mixed value after api key is not sent, on purpose",
     "test_secret_screen::Screen::test_a_short_mixed_value_after_api_key_is_refused_on_purpose"),
    ("#527", "Help names a New project item only if the page builds it",
     "test_help_content::Words::test_help_names_new_project_only_if_the_page_builds_it"),
    ("#388", "A publish that loses the race for a number puts back a link it had replaced",
     "test_publication_numbers::ThroughThePublisher::test_overwrite_with_a_lost_race_puts_back_a_link_it_replaced"),
    ("#493", "A null character in the logo rule is turned away",
     "test_publish_scan_gaps::BrandPictures::test_a_null_byte_in_the_logo_rule_is_refused"),
    ("#400", "A release zip is not built from a tree that is not the tagged commit",
     "test_package::ReleaseFromTagTest::test_untagged_tree_is_refused_and_nothing_is_written"),
    ("#400", "A release zip is not built from a dirty tree",
     "test_package::ReleaseFromTagTest::test_release_with_dirty_is_refused"),
    ("#97", "Right-click a work item opens the menu with every entry",
     "test_row_menu::Menu::test_a_right_click_on_a_row_opens_the_menu_with_every_entry"),
    ("#97", "Draft email to the owner opens with the To line empty unless an address is found by the owner's id",
     "test_row_menu::Rules::test_draft_email_opens_with_the_to_line_empty_and_finds_an_address_by_owner_id_never_the_name"),
    ("#199", "Hand over changes every owner in one step and one Undo puts them back",
     "test_hand_over::Page::test_hand_over_changes_every_owner_in_one_step_and_one_undo"),
    ("#199", "Items that cannot take the hand over are left out and named",
     "test_changes_hand_over::HandOver::test_items_that_cannot_take_it_are_left_out_and_named"),
    ("#595", "A supporting document of an unknown kind is left out of the published file, never published with an empty kind",
     "test_documents_published::Absent::test_an_unknown_document_kind_is_refused_never_published_as_an_empty_kind_and_a_known_kind_is"),
    ("#74", "In Edit the Supporting documents section adds, edits, leaves out and adds back a document, each with its own Undo",
     "test_documents_page::InEdit::test_add_edit_leave_out_and_add_back_each_with_undo"),
    ("#74", "Archive takes a document off the list and the published page in one step with Undo, and Restore brings it back",
     "test_documents_page::Archive::test_archive_undo_and_restore_at_both_widths_light_and_dark"),
    ("#74", "A published file leaves out an archived document",
     "test_documents_page::Archive::test_the_published_file_omits_an_archived_document"),
    ("#286", "The filter line no longer says Press / (that key opens ask clark)",
     "test_filter_line_page::Line::test_the_line_does_not_say_press_slash_in_view_or_edit_because_that_key_opens_ask"),
    ("#481", "One plain Help line names the calendar's keys",
     "test_help_content::CalendarKeysHelp::test_the_calendar_line_names_the_keys_the_page_handles"),
    ("#618", "The Word client copy is refused when it carries text held back from the client",
     "test_word_client_held_back::Cases::test_the_word_client_copy_refuses_it"),
    ("#618", "A refused Word client copy writes nothing in either folder",
     "test_word_client_held_back::Cases::test_the_refusal_writes_nothing_in_either_folder"),
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
    ("#325", "The publications trigger also guards the client copy's path (a data layout step)", "PR 474",
     "store.py", "migrate_publication_trigger_client_path"),
    ("#620", "A hand over's Undo skips only the owner that changed and undoes the rest", "PR 541",
     "changes.py", "def _hand_over_changed(store, step, rows, all_gone=True):"),
    ("#622", "Settings, Backups: an optional 'Copy my backups to' folder (OneDrive allowed)", "PR 542",
     "settings.py", "# ===== Copy my backups to (#622, Settings"),
]
# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#246", "The peek reads well as it steps", "judgement",
     "only a person can say the peek does not jump or flicker and the keyboard never lands on nothing",
     "Open a peek in Work items, step it with Down and Up at 1400 and 900 px, light and dark, and press Esc."),
    ("#455", "The dashboard's use case rows in Edit read as the prototype's", "judgement",
     "only a person can compare the look of the status button, the in-place boxes and the growing plus with the prototype",
     "In Edit open the Dashboard and use each control on a use case row, at 1400 and 900 px, light and dark."),
    ("#459", "Help reads well at both widths", "judgement",
     "only a person can say the cards, the marked word and the key chip are clear and nothing overlaps",
     "Open Help with the ? at the top, search for a word, and look at 1400 and 900 px, light and dark."),
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
    no lower-case 'ask clark' in a heading, and the data-layout paragraph only when the layout has changed since 0.6.0."""

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
        self.assertEqual(said, schema_version() != SCHEMA_AT_0_6_0,
                         "the notes must say a layout step is in exactly when SCHEMA_VERSION in store.py is not %d" % SCHEMA_AT_0_6_0)

    def test_a_date_in_the_notes_is_day_first(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 0.7.1 and later have their own test_vNNN
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

"""clark 0.9's hand checks as tests: the 0.8 features that have merged to main. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v090

Same shape as test_v080.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written after 0.8.0 was published (tag 703a0f06), from origin/main on 04-11-2026: everything merged after the tag, plus the rows 0.8.0 left
waiting. The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.9.0, then fail if wrong.
The notes' own rules (title, the Beta line, plain words, the data-layout paragraph) are read from the tree now.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.9.0"
SCHEMA_AT_0_8_0 = 15     # 0.8.0 reads layout 15; a layout step after it makes the notes say so

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#152", "The Settings Update clark card: Undo update puts the data back as it was and says changes after the update are lost.",
     "test_update_migration::Migrated::test_undo_puts_the_data_back_as_it_was_and_says_changes_after_the_update_are_lost"),
    ("#280", "Once a release key is set, an update file with no signature or a wrong one is refused and nothing is kept.",
     "test_updater::ReviewTest::test_an_unsigned_or_wrongly_signed_update_is_refused_with_nothing_kept"),
    ("#280", "While the release key is the placeholder an update file with no signature is reviewed like any other (the other checks still apply).",
     "test_updater::ReviewTest::test_an_unsigned_update_is_reviewed_while_the_release_key_is_the_placeholder"),
    ("#427", "A copy of the source in a container stops at once with one plain sentence about the missing built page.",
     "test_main::InProcess::test_in_a_container_with_no_built_page_it_stops_at_once_in_one_plain_sentence"),
    ("#427", "A container accepts only loopback and the gateway as local peers; the compose file publishes only on 127.0.0.1.",
     "test_server_container::InAContainer::test_the_gateway_and_loopback_are_local_and_no_other_peer"),
    ("#640", "The filter box's open list floats over the page just under the box and pushes nothing down (row 808 reversed the earlier rule).",
     "test_filter_line_page::Line::test_the_open_list_floats_over_the_page_and_pushes_nothing_down"),
    ("#420", "Open About you before clark has read it, type only a name and leave the box: the email saved before is still there.",
     "test_about_you::AboutYou::test_C_a_save_made_before_the_first_read_has_landed_keeps_the_other_box_saved_value"),
    ("#434", "Risks, issues, actions and decisions rows: a status pill, empty sections, editing in place and the ID button",
     "test_item_rows::EditRows::test_every_part_of_a_row_edits_in_place_and_the_pill_is_the_prototypes"),
    ("#439", "The bar above the page: Week ending is a box in View and in Edit; with no week kept it shows the coming Friday and saves nothing until Enter.",
     "test_report_bar::Bar::test_with_no_week_kept_the_field_shows_the_coming_friday_and_saves_nothing"),
    ("#439", "A typed entry that is not a day keeps the old date and says so.",
     "test_report_bar::Bar::test_a_typed_entry_that_is_not_a_day_keeps_the_old_date_and_says_so"),
    ("#439", "A typed day that is not a Friday keeps the old date and names the Friday (\"Week ending is a Friday. Pick Friday DD-MM-YYYY.\").",
     "test_report_bar::Bar::test_a_typed_day_that_is_not_a_friday_keeps_the_old_date_and_names_the_friday"),
    ("#439", "The project name in the top bar is always a menu: each project with its open-item count (row 1092: Project settings is in Settings, not the menu).",
     "test_project_switch::ProjectSwitch::test_C_the_menu_lists_only_the_projects_with_open_counts"),
    ("#439", "Choosing a project in the menu switches to it and says so.",
     "test_project_switch::ProjectSwitch::test_C_choosing_a_project_changes_the_address_and_says_so"),
    ("#450", "Show archived is a pill in the Work items bar with the archived count; on, the archived items show read only, and the choice is remembered for the project.",
     "test_work_archived_page::Archived::test_the_choice_is_remembered_for_the_project_across_a_reload"),
    ("#450", "An archived item opens read only in the side peek with one Restore; Esc and Close return to its row.",
     "test_work_archived_peek::ArchivedPeek::test_a_row_opens_the_peek_read_only_with_one_restore"),
    ("#450", "Restore puts the item back and leaves the peek open on it, now editable.",
     "test_work_archived_peek::ArchivedPeek::test_restore_puts_it_back_and_leaves_the_peek_open_on_it"),
    ("#444", "Settings › Data: Import workbook checks the workbook first, then imports it in one step, and Undo this import puts it back.",
     "test_settings_data_page::Card::test_import_checks_then_imports_in_one_step_and_undo_puts_it_back"),
    ("#444", "A macro workbook is turned away in words and nothing is stored.",
     "test_excel_route::Check::test_a_macro_workbook_is_refused_in_words_and_nothing_is_stored"),
    ("#444", "Settings has a Projects table with each project and its columns.",
     "test_projects_settings_page::Browser::test_the_table_lists_each_project_with_its_columns_at_1400_and_900_px_in_light_and_dark"),
    ("#449", "Publish warns while a work item the client would see has a placeholder title, and the warning goes when it is renamed or hidden.",
     "test_publish_dialog::Placeholder::test_the_warning_counts_placeholder_items_the_client_would_see_and_goes_when_renamed_or_hidden"),
    ("#449", "The Move to menu works as the page opens, with a toast and Undo, and does not switch to Edit.",
     "test_work_board_page::Moves::test_the_move_to_menu_works_as_the_page_opens_with_a_toast_and_undo"),
    ("#647", "A pasted path to a folder OneDrive syncs is saved like a chosen one.",
     "test_client_folder_paste::APastedFolder::test_a_folder_inside_onedrive_is_saved_as_a_chosen_one"),
    ("#647", "A pasted link can't be used and nothing is saved.",
     "test_client_folder_paste::ALink::test_a_link_is_refused_by_its_form_and_nothing_is_saved"),
    ("#611", "A blank client message is turned away in plain words, not a server error.",
     "test_changes_null_message::NullMessage::test_a_client_message_that_is_not_text_is_refused_and_nothing_is_saved"),
    ("#613", "Settings, About you: typing Jane Doe fills the Alias box with Jane, JD; it is saved beside the name, and a saved or typed Alias is kept when the name changes.",
     "test_alias_suggest::OnThePage::test_C_jane_doe_is_saved_with_jane_jd_and_a_typed_alias_is_kept_when_the_name_changes"),
    ("#343", "A past publication opens read only: a banner with its number and day and Back to now, a tinted frame, nothing to change.",
     "test_past_view::TheBanner::test_the_words_the_date_the_tint_and_back_to_now"),
    ("#343", "A kept file that no longer matches its checksum is refused in plain words and not shown.",
     "test_past_view::TheChecksum::test_a_file_that_no_longer_matches_is_refused_in_plain_words_with_what_to_do"),
    ("#345", "Each published report row has Archive; an archived one is hidden from the list and the pickers; Show archived lists them with Restore.",
     "test_past_reports_card::Card::test_each_row_has_archive_and_the_default_list_hides_the_archived"),
    ("#345", "Archive says \"Publication N archived. Restore it from Show archived.\" and offers no Undo; Restore brings it back.",
     "test_past_reports_card::Card::test_archive_asks_once_says_the_exact_words_with_no_undo_and_reads_the_list_again"),
    ("#345", "Show archived lists the archived publications marked Archived, each with Restore.",
     "test_past_reports_card::Card::test_show_archived_lists_them_marked_with_restore_and_restore_says_its_words"),
    ("#391", "The High risks and issues tile counts the open items of the Risks and issues type rated Urgent or High, by one rule, with the same colour on the page and in the published file.",
     "test_glance_rule::OneRule::test_the_published_file_gives_the_same_colour_as_the_page"),
    ("#613", "Settings, About you: typing a full name shows the suggested Alias below the name (the first name, then the initials).",
     "test_alias_suggest::Suggest::test_a_full_name_suggests_the_first_name_then_the_initials"),
    ("#434", "The risks, issues, actions and decisions rows show a status pill, a heading with a line when empty, edit in place, and an Add line.",
     "test_item_rows::EditRows::test_every_part_of_a_row_edits_in_place_and_the_pill_is_the_prototypes"),
    ("#434", "The Add line adds a row with its client wording, and the count follows.",
     "test_item_rows::EditRows::test_the_add_line_adds_a_row_with_its_wording_and_the_count_follows"),
    ("#434", "The eye takes a row off the page and Add from your project record puts it back.",
     "test_item_rows::EditRows::test_the_eye_takes_a_row_off_and_add_from_your_project_record_puts_it_back"),
    ("#434", "What a client reads has no edit control and nothing internal.",
     "test_item_rows::EditRows::test_what_a_client_reads_has_no_edit_control_and_nothing_internal"),
    ("#614", "The ring beside Publishing\u2026 keeps turning, at a calmer pace, for as long as publishing takes; reduced motion shows a still ring.",
     "test_publish_ring::Ring::test_C_the_ring_still_turns_after_the_old_stop_time_while_publishing"),
    ("#644", "The Use case summary has no export icon in View or in Edit; the Work items workbook export is unchanged.",
     "test_uc_row_parity::Reference::test_the_use_case_summary_has_no_export_icon_in_view_or_edit"),
    ("#612", "In the right-click menu, when the browser does not copy, the select-and-press-copy hint shows only if there is a selection.",
     "test_row_menu::Menu::test_when_the_browser_does_not_copy_the_cmd_c_hint_shows_only_with_a_selection"),
    ("#612", "Duplicate with forged label values is refused and writes nothing.",
     "test_changes_item_eye::Duplicate::test_a_forged_labels_value_on_duplicate_is_refused_and_writes_nothing"),
    ("#48", "Export to Word saves a file and says where.",
     "test_word_screens::Export::test_an_export_saves_a_file_and_says_where"),
    ("#48", "Import from Word shows what it read before anything is added, adds only what is chosen, with one Undo.",
     "test_word_screens::Import::test_it_shows_what_it_read_before_anything_is_added_then_adds_only_what_is_chosen_with_one_undo"),
    ("#48", "Import from Word reads only a Word document, on the server as on the page.",
     "test_word_route::Refusals::test_only_a_docx_is_read_whatever_is_inside"),
    ("#438", "The Also a PDF tick has the prototype's words.",
     "test_pdf_print::Words::test_the_tick_has_the_prototypes_words"),
    ("#438", "A page with the print flag opens the print box once it has drawn.",
     "test_pdf_print::Browser::test_a_page_with_the_flag_opens_the_print_box_once_it_has_drawn_and_a_page_without_it_does_not"),
    ("#449", "Add makes an item, opens it, and Undo removes it.",
     "test_work_add_item::AddMenu::test_each_pick_makes_the_item_opens_it_and_undo_removes_it"),
    ("#449", "A double-click on the grip resets a column's width, with a toast.",
     "test_board_columns::Columns::test_a_double_click_on_the_grip_says_column_width_reset_in_a_toast_in_view_and_in_edit"),
    ("#613", "The Alias box fills in from the name at both widths, light and dark.",
     "test_alias_suggest::OnThePage::test_C_the_box_is_filled_from_the_name_at_both_widths_light_and_dark"),
    ("#613", "Jane Doe is saved with Jane, JD, and a typed Alias is kept when the name changes.",
     "test_alias_suggest::OnThePage::test_C_jane_doe_is_saved_with_jane_jd_and_a_typed_alias_is_kept_when_the_name_changes"),
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
]

BANNED_WORDS = ("apply", "applied", "staged", "proposal", "sweep", "tracker", "vault", "extract", "refused")


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
    no lower-case 'ask clark' in a heading, and the data-layout paragraph only when the layout has changed since 0.8.0."""

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
        if version() != VERSION:        # a cut check: live only at its own version (#709: 1.0.1 has a layout step of its own, and these notes are not its notes)
            self.skipTest(f"the layout moves on after {VERSION} (now {schema_version()}), and a later release says so in its own notes")
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

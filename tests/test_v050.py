"""clark 0.5's hand checks as tests. Each release gets a test_vNNN file, so the walk-through keeps only the judgement and
live-only checks.

Run: python3 dev/run_tests.py test_v050

Same shape as test_v040. Headless and fast: no Chrome is started here. What a person would check in the v0.5 items, and where:
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet; its check is written when it lands (the item is named). Skipped, with the question.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.
The cut checks (version, release notes, hand-check sheet) skip until the cut commit exists, then fail if they are wrong.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.5.0"

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#196", "The bulk bar changes the owner of every selected work item in one step with one Undo",
     "test_bulk_bar::Page::test_the_bar_changes_the_owner_of_every_selected_row_in_one_step_and_one_undo"),
    ("#196", "Close and reopen work from the bulk bar", "test_bulk_bar::Page::test_close_and_reopen_from_the_bar"),
    ("#196", "A status picked on the bar changes only the items that do not have it", "test_bulk_bar::Page::test_a_status_from_the_bar_and_nothing_changed_when_they_have_it"),
    ("#196", "One change to several items is one step with a history line per item and one Undo",
     "test_changes_bulk::Bulk::test_one_change_to_three_actions_is_one_step_with_a_history_line_per_item"),
    ("#196", "Items that cannot take a bulk change are left out and named", "test_bulk_bar::Page::test_left_out_items_are_named"),
    ("#196", "clark asks first when more than 25 items would change", "test_bulk_bar::Page::test_the_question_at_25_and_26"),
    ("#196", "Cancel on the question changes nothing", "test_bulk_bar::Page::test_cancel_on_the_question_changes_nothing"),
    ("#196", "Right-click on a selection or a lone row opens the list of changes",
     "test_bulk_bar::Page::test_the_right_click_menu_on_a_selection_and_on_a_lone_row"),
    ("#196", "Shift+F10 and the Menu key open the same list", "test_bulk_bar::Page::test_shift_f10_and_the_menu_key_open_it_and_mixed_kinds_offer_only_copy_ids"),
    ("#196", "Right-click on a board card opens the list", "test_bulk_bar::Page::test_the_menu_on_a_card"),
    ("#196", "O, S, P, T and C change the owner, status, priority or due date, or close the item or the selection",
     "test_bulk_bar::Page::test_o_s_t_and_c_on_a_row_and_on_a_selection"),
    ("#196", "The letter keys work only when the single-key switch is on",
     "test_single_keys::PageKeys::test_letters_work_when_on_do_nothing_when_off_and_work_again_with_no_reload"),
    ("#196", "Changing one cell of a selected row asks first and then changes that field on every selected row",
     "test_bulk_bar::Page::test_a_cell_of_a_selected_row_changes_every_selected_row_after_saying_so"),
    ("#196", "The bar, the menu and the question fit at both widths in light and dark",
     "test_bulk_bar::Page::test_the_bar_menu_and_question_fit_at_both_widths_in_light_and_dark"),
    ("#195", "Selecting work items by click, Shift and Cmd or Ctrl works in the drawn order", "test_multi_select::Page::test_click_cmd_and_ctrl_click_shift_ranges_in_the_drawn_order"),
    ("#157", "Edit has a Use cases tab beside Milestones", "test_use_cases_list::Tab::test_the_tab_sits_beside_milestones_in_the_editor_and_opens_the_page"),
    ("#157", "Use cases search finds a reference, a name, a headline, the text and a milestone", "test_use_cases_list::Narrowing::test_search_finds_a_reference_a_name_a_headline_the_text_and_a_milestone"),
    ("#157", "The Use cases status filter takes any number of statuses and clears", "test_use_cases_list::Narrowing::test_the_status_choice_takes_any_number_and_clears"),
    ("#157", "The On or Not on the dashboard switch changes the store, syncs with the dashboard and undoes",
     "test_use_cases_list::Eye::test_the_eye_changes_the_store_syncs_with_the_dashboard_and_undoes"),
    ("#157", "Use cases sort by reference, status or open work items", "test_use_cases_list::Narrowing::test_sort_by_reference_status_and_open_work_items"),
    ("#157", "A use case opens on its own page and Esc or the crumb goes back to the list", "test_use_case_detail::Detail::test_esc_and_the_crumb_return_to_the_list"),
    ("#69", "The published Work items tab filters, counts and groups, and each control works", "test_client_page_filters::ClientPageFilters::test_each_control_works"),
    ("#69", "The published page remembers a reader's filter choices in its own key", "test_client_page_filters::ClientPageFilters::test_choices_are_remembered_in_the_pages_own_key"),
    ("#69", "The published page's rows and counts are the same as the model gives for every case", "test_client_page_filters::ModelMatchesPage::test_every_case_gives_the_same_answer"),
    ("#138", "A count is what a click on it would show", "test_client_filters::Counts::test_a_count_is_what_a_click_would_show"),
    ("#138", "In the editor, the counts equal the list after each filter at both widths", "test_work_filters::RealBrowser::test_the_switch_counts_equal_the_list_after_each_filter_at_1400_and_900_px"),
    ("#138", "Nothing matching says so and Clear all brings the rows back", "test_work_filters::RealBrowser::test_nothing_matching_says_so_and_clear_all_brings_the_rows_back"),
    ("#168", "A published Use cases row opens in place with its headline, steps and milestones", "test_publish_usecases::Present::test_the_kept_use_case_with_its_step_and_milestone"),
    ("#168", "The published tabs run Dashboard, Work items, Milestones, Use cases", "test_publish_usecases::Present::test_tab_order"),
    ("#168", "With no use case on the dashboard there is no Use cases tab", "test_publish_usecases::Absent::test_no_tab_when_no_use_case_is_on_the_dashboard"),
    ("#168", "A use case with the eye off, and private notes and history, are not in the published file", "test_publish_usecases::Absent::test_use_case_with_the_eye_off"),
    ("#168", "The published Use cases tab opens and fits at both widths in light and dark", "test_publish_usecases::RealBrowser::test_the_tab_opens_and_fits_at_1400_and_900_light_and_dark"),
    ("#130", "Publishing shows a spinner and then a tick with the same words", "test_publish_dialog::Dialog::test_C_publish_shows_a_spinner_while_it_works_then_a_tick_with_the_same_words"),
    ("#130", "A local publish says locally and leaves the client folder alone", "test_publish_dialog::Dialog::test_C_a_local_publish_says_locally_and_the_client_folder_is_left_alone"),
    ("#277", "An ask clark answer holding the hidden instructions is dropped", "test_ask_canary::Canary::test_a_reply_with_the_canary_is_dropped_and_logged_without_the_text"),
    ("#277", "The hidden instructions spelt in chunks or with hidden characters are still caught", "test_ask_canary::Canary::test_a_reply_that_spells_it_in_chunks_or_with_hidden_characters_is_caught"),
    ("#257", "Passwords and keys in other languages or encoded text are caught", "test_secret_screen::Screen::test_encoded_and_other_language_forms_are_caught"),
    ("#257", "A secret in a file's name is caught", "test_secret_screen::Screen::test_a_secret_in_a_file_name_is_caught"),
    ("#215", "A file with a secret in its name is left out of what ask clark reads", "test_secret_screen::FromFolders::test_a_file_whose_name_holds_a_secret_is_left_out"),
    ("#257", "A question with a secret in it is refused and nothing is sent", "test_secret_refusal_paths::QuestionRoute::test_each_kind_in_the_question_is_refused_and_nothing_is_sent"),
    ("#257", "A selection with a secret in it is refused and nothing is sent", "test_secret_refusal_paths::SelectedText::test_each_kind_in_the_selection_is_refused_and_nothing_is_sent"),
    ("#257", "Ordinary prose about a password is not refused", "test_secret_screen::Screen::test_harmless_prose_about_a_password_is_not_a_secret"),
    ("#215", "The person is told which file was left out and the secret goes nowhere", "test_secret_screen::OnTheRoute::test_the_person_is_told_the_file_and_the_next_step_and_the_secret_goes_nowhere"),
    ("#257", "A clean question after a refusal still reaches the provider", "test_secret_refusal_paths::QuestionRoute::test_a_clean_question_after_a_refusal_still_reaches_the_provider"),
    ("help", "Help describes the section styles in the words Settings shows", "test_help_content::LowWordsRound::test_the_section_style_lines_are_the_ones_settings_shows"),
    ("#119", "The peek shows Raised and Last reviewed and the not-reviewed chip", "test_peek_fresh::PeekFresh::test_a_stale_item_shows_both_dates_and_the_chip_in_every_view"),
    ("#119", "A closed item never shows the not-reviewed chip", "test_peek_fresh::PeekFresh::test_a_closed_item_never_shows_the_chip"),
    ("#158", "An item is flagged after more than 14 days and not at exactly 14", "test_freshness::Rules::test_exactly_n_days_is_not_flagged_and_one_more_is"),
    ("#158", "The Freshness filter selects and counts the right rows", "test_freshness::FilterValue::test_the_filter_selects_and_counts"),
    ("#158", "An import or an ask clark change is not a review", "test_freshness_feed::Feed::test_an_import_or_an_ask_clark_change_is_not_a_review"),
    ("#78", "The peek's priority, date and status icons take their tones", "test_peek_icons::ToneRules::test_priority_urgent_red_high_amber_medium_blue_low_and_none_grey"),
    ("#78", "The date is red when late, amber within a week, blue later and grey with none", "test_peek_icons::ToneRules::test_the_date_is_red_late_amber_within_a_week_blue_later_and_grey_with_none"),
    ("#78", "Every icon is at least 3 to 1 on the peek in light and dark", "test_peek_icons::Contrast::test_every_icon_is_at_least_3_to_1_on_the_peek_and_its_highlight_in_light_and_dark"),
    ("#187", "Every colour in the export table is the look's light value", "test_export_colours::ExportColours::test_every_colour_in_the_export_table_is_the_looks_light_value"),
    ("#187", "The Word file uses the same colour table", "test_export_colours::ExportColours::test_the_word_file_uses_the_same_table"),
    ("#187", "The Word file's font is the look's office font", "test_docx_build::FollowsTheLook::test_the_font_is_the_looks_office_font_in_every_run_style"),
    ("#187", "The Excel header is on the look's brand colour in the look's font", "test_excel_format::Formatting::test_header_is_bold_white_on_the_looks_brand_navy_and_wraps"),
    ("#187", "The drafted email is drawn in the look's light colours", "test_export_colours::FontsAndNothingWrittenByHand::test_the_email_is_drawn_in_the_looks_light_colours"),
    ("#149", "Add a section beside another is one request and the rows are right", "test_templates::Box::test_place_it_beside_the_section_above_is_one_request_and_the_rows_are_right"),
    ("#149", "Beside is greyed out with a reason for a section that already has a partner", "test_templates::Box::test_beside_is_unavailable_with_the_reason_for_a_section_that_has_a_partner"),
    ("#149", "One Undo removes an added section and its pairing", "test_changes::AddBeside::test_one_undo_removes_the_section_and_the_pairing"),
    ("#149", "A section that already has a partner is refused and nothing is written", "test_changes::AddBeside::test_a_section_that_already_has_a_partner_is_refused_and_nothing_is_written"),
    ("#141", "At 900 px the contents rail is a button at the bottom right and the lines are gone", "test_toc_button::TocButton::test_at_900_it_is_a_button_at_the_bottom_right_and_the_lines_are_gone"),
    ("#141", "At 1400 px the rail is the thin rail at the right edge", "test_toc_button::TocButton::test_at_1400_it_is_the_thin_rail_at_the_right_edge_with_no_words"),
    ("#141", "At 900 px only a click or a key opens the list; hover does not", "test_toc_button::TocButton::test_at_900_hover_and_plain_focus_do_not_open_it_but_a_click_does_and_again_shuts_it"),
    ("#141", "At 900 px Esc closes the list and focus returns to the button", "test_toc_button::TocButton::test_at_900_escape_closes_it_and_the_focus_is_back_on_the_button"),
    ("#141", "At 900 px choosing an item goes to the section", "test_toc_button::TocButton::test_at_900_choosing_an_item_goes_to_the_section_and_its_heading_takes_focus"),
    ("#141", "At 900 px a click outside closes the list", "test_toc_button::TocButton::test_at_900_a_click_outside_closes_it"),
    ("#141", "Both built pages carry the On this page button", "test_toc_button_source::Look::test_both_built_pages_carry_it"),
    ("#140", "View draws the saved text of the four text sections and Edit is unchanged", "test_view_text_sections::TheBrowser::test_view_draws_the_text_and_edit_is_unchanged"),
    ("#140", "The published page draws the text sections as before", "test_view_text_sections::TheSource::test_the_published_page_draws_the_same_as_before"),
    ("#130", "The At a glance tiles share the row and Project health takes two shares and the gap", "test_glance_fill::Source::test_tiles_share_the_row_and_health_takes_two_shares_and_the_gap"),
    ("#132", "Four tiles at the least width fit one line at 900 px", "test_glance_fill::Source::test_four_tiles_at_the_least_width_fit_one_line_at_900"),
    ("#132", "In Edit, the label stays clear of the grip and the eye and the hidden tag clear of the text", "test_glance_fill::Source::test_edit_keeps_the_label_line_clear_of_the_grip_and_eye_and_the_hidden_tag_clear_of_the_text"),
    ("#132", "View tiles fill the row at both widths in light and dark", "test_glance_fill::Fill::test_view_tiles_fill_the_row_at_1400_and_900_in_light_and_dark"),
    ("#132", "A lone Project health tile fills the row", "test_glance_fill::Fill::test_a_lone_health_tile_fills_the_row"),
    ("#121", "The Needs from you template is added like the others and one Undo takes it away", "test_needs_page::Page::test_the_template_is_added_like_the_others_and_one_undo_takes_it_away"),
    ("#121", "Add a row to Needs from you is one request, one step and one Undo", "test_needs_page::Page::test_add_a_row_is_one_request_one_step_and_one_undo"),
    ("#121", "Edit, hide, include and remove a Needs row are each one step with one Undo", "test_needs_page::Page::test_edit_hide_include_and_remove_a_row_are_each_one_step_with_one_undo"),
    ("#121", "In View, Needs from you is a table with three headings and nothing to change", "test_needs_page::Page::test_view_is_a_table_with_the_three_words_and_nothing_to_change"),
    ("#121", "A past date says Overdue in words as well as colour", "test_needs_page::Page::test_a_date_that_has_passed_says_the_word_overdue_and_a_date_to_come_does_not"),
    ("#121", "Hidden rows, hidden sections and empty lists are absent in View", "test_needs_page::Page::test_hidden_rows_and_hidden_sections_and_empty_lists_are_absent_in_view"),
    ("#121", "The published file has the Needs table view-only and Overdue as at the publish day", "test_needs_page::Page::test_the_published_file_has_the_table_view_only_and_reads_overdue_as_at_the_day_it_was_published"),
    ("#121", "Needs from you fits and reads at both widths in light and dark", "test_needs_page::Page::test_it_fits_and_reads_at_1400_and_900_in_light_and_dark_in_view_and_in_edit"),
    ("#121", "An empty Needs section is left out of the published file", "test_needs_content::Published::test_no_row_to_show_leaves_the_section_out"),
]

# Not on main (or no test found): (item, check, the question or where it is being built).
WAITING = [
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#69", "A published page lets the client filter the work items", "judgement",
     "only a person can say the filters, chips and remembered choices read right",
     "Publish a demo project (Local only), open the file in Chrome, click Work items, try the filters, close the tab and open the file again; check once at 900 px (sheet line 1)."),
    ("#121", "A report's Needs from you table reads well", "judgement",
     "only a person can say the table reads well and the colours help",
     "In Edit, Add a section, choose Needs from you, add a decision, a piece of information and a past date; check View, Preview and 900 px (sheet line 2)."),
    ("#119", "The peek shows when an item was raised and last reviewed", "judgement",
     "the demo data decides whether a stale item is there to see",
     "In Work items, click a row and read Raised, Last reviewed and the chip; try the Freshness filter (sheet line 3)."),
    ("#78", "The peek's icons carry their colours", "judgement",
     "only a person can say nothing is hard to read in light and dark",
     "Open the peek on items of each priority and date; switch to dark and look again (sheet line 4)."),
    ("#187", "Word, Excel and the drafted email follow the page's look", "live only",
     "needs Word, Excel and Outlook",
     "Open a Word copy, export to Excel and open it, and paste a Draft email into a new Outlook message (sheet line 5)."),
    ("#149", "Adding a section beside another is one step", "judgement",
     "only a person can see the new section sits next to the old one and Undo puts it back",
     "In Edit, Add a section beside an existing one, press Undo once, then try a section that already has a partner (sheet line 6)."),
    ("#141", "At 900 px the contents rail becomes an On this page button", "judgement",
     "feel and position are for the eye, and the published file needs opening by hand",
     "Check the rail at 1400 px, the button at 900 px in the editor and in a published file (sheet line 7)."),
    ("#140", "View draws the text of Current state, Summary, This week and Next week", "judgement",
     "only a person can say the text reads well in plain paragraphs and in dark mode",
     "On the dashboard in View, read the four sections, then Edit, then 900 px and dark (sheet line 8)."),
    ("#130", "Publish shows a spinner and then a tick", "judgement",
     "only a person can see that nothing jumps and Reduce motion is respected",
     "Publish locally from the profile menu, with and without Reduce motion (sheet line 9)."),
    ("#138", "On a published page the rows shown always equal the count", "judgement",
     "a quick look at the real published file with a second filter",
     "Publish a demo project, filter by Overdue, add Owner or Status, then Clear all (sheet line 10)."),
    ("#168", "A published page has a Use cases tab for reading only", "judgement",
     "the tab, its capital letters and its look are for the eye",
     "Set the eye on for some use cases, publish, open the file at 1400 and 900 px in light and dark, then turn them all off and publish again (sheet line 11)."),
    ("#132", "The At a glance tiles fill the row", "judgement",
     "only a person can say the tiles look even and clear",
     "Look at View at 1400 and 900 px, then Edit with a long label and a hidden tile, then a published file, in light and dark (sheet line 12)."),
    ("#257", "Passwords and keys in other forms are refused", "live only",
     "needs ask clark switched on with a real provider and a folder on disk",
     "Ask a question with a made-up password in another language, an ordinary password-policy question, and a question about a folder holding a file with a password in its name (sheet line 13)."),
]


def names_in(path):
    """{class name: {test method names}} in a test file, read without importing it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {c.name: {f.name for f in c.body if isinstance(f, ast.FunctionDef)} for c in tree.body if isinstance(c, ast.ClassDef)}


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
        checks = [c for _, c, _ in COVERED + WAITING] + [c for _, c, _, _, _ in WALK_THROUGH]
        self.assertEqual(sorted(c for c in set(checks) if checks.count(c) > 1), [])
        for item, check, kind, why, does in WALK_THROUGH:
            self.assertIn(kind, ("judgement", "live only"), check)
            self.assertTrue(why.strip() and does.strip(), check)

    def test_each_waiting_check_carries_its_question(self):
        for item, check, question in WAITING:
            self.assertTrue(question.strip(), check)


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        text = (ROOT / "src" / "clark" / "__init__.py").read_text(encoding="utf-8")
        found = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        if not found or not found.group(1).startswith("0.5"):
            self.skipTest(f"the cut commit is not made yet (version is {found.group(1) if found else 'unknown'}); "
                          f"it sets {VERSION} in src/clark/__init__.py")
        return found.group(1)

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


def _skips():
    for i, (item, check, kind, why, does) in enumerate(WALK_THROUGH):
        def t(self, _m=f"needs a person ({kind}): {why}. Do this: {does}"):
            self.skipTest(_m)
        t.__name__ = "test_%s_%d_needs_a_person" % (re.sub(r"\W", "_", item), i)
        t.__doc__ = check
        setattr(Walk, t.__name__, t)
    for i, (item, check, q) in enumerate(WAITING):
        def w(self, _m=f"waiting: {q}"):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (re.sub(r"\W", "_", item), i)
        w.__doc__ = check
        setattr(Walk, w.__name__, w)


class Walk(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips()

if __name__ == "__main__":
    unittest.main()

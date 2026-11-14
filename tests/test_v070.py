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
held-back check (#618) and the unknown-kind document (#595). Not merged, so WAITING: nothing: every row is on main at the cut commit.
#220, #171, #160, #269 and #427 are not in this cut: they go to 0.8.
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
     "test_milestones_calendar_keys::CalendarDayKeys::test_left_right_up_and_down_move_a_day_or_a_week_and_the_tab_stop_goes_with_the_focus"),
    ("#481", "Enter on a day with milestones goes to its first milestone, and on an empty day does nothing",
     "test_milestones_calendar_keys::CalendarDayKeys::test_enter_on_a_day_with_milestones_goes_to_its_first_chip_and_on_an_empty_day_does_nothing"),
    ("#481", "Shift+Tab or Esc on a milestone goes back to its day, and with a peek open Esc closes the peek",
     "test_milestones_calendar_keys::CalendarDayKeys::test_shift_tab_or_esc_on_a_chip_goes_back_to_its_day_but_with_a_peek_open_esc_closes_the_peek"),
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
    ("#459", "The top bar has no Help button and Help has no Back button",
     "test_help_panel::Panel::test_the_top_bar_has_no_help_button_and_help_has_no_back_button"),
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
    ("#589", "A saved view the filter line cannot read stays listed and can be renamed or deleted",
     "test_filter_line_page::Line::test_a_saved_view_the_line_cannot_read_stays_listed_says_why_and_can_be_renamed_or_deleted"),
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
     "test_publish_scan_brand::BrandPictures::test_a_null_byte_in_the_logo_rule_is_refused"),
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
     "test_filter_line_page::Line::test_the_line_does_not_say_press_slash_because_that_key_opens_ask"),
    ("#481", "One plain Help line names the calendar's keys",
     "test_help_content::CalendarKeysHelp::test_the_calendar_line_names_the_keys_the_page_handles"),
    ("#618", "The Word client copy is refused when it carries text held back from the client",
     "test_word_client_held_back::Cases::test_the_word_client_copy_refuses_it"),
    ("#618", "A refused Word client copy writes nothing in either folder",
     "test_word_client_held_back::Cases::test_the_refusal_writes_nothing_in_either_folder"),
    ("#220", "In Edit each of the three text sections shows an editable field, and View shows none.",
     "test_one_editor_gate::PageGate::test_only_the_three_text_sections_have_a_rich_field_and_only_in_edit"),
    ("#220", "A saved body is still there when the field is opened again.",
     "test_one_editor_gate::PageGate::test_a_saved_body_is_still_there_when_the_field_is_opened_again_and_the_focus_comes_back"),
    ("#437", "Open Publish: the line under the title reads \"this will be Publication 1\"; after publishing, \"Publication 2 \u00b7 last published <date>, locally\".",
     "test_publish_dialog::Dialog::test_C_the_dialog_line_says_which_publication_this_will_be_and_when_the_last_one_went"),
    ("#442", "Duplicate an action: the copy opens, carries the same status, owner and dates, and Undo takes it back.",
     "test_row_menu::Menu::test_duplicate_adds_a_copy_in_one_step_opens_it_and_undo_says_so"),
    ("#442", "A copy of a hidden item stays hidden; a shown one stays shown, for actions, risks and decisions.",
     "test_row_menu::Menu::test_a_copy_keeps_the_eye_of_its_original_for_every_kind"),
    ("#639", "Open the downloaded zip: LICENSE and NOTICE.md are in the top folder.",
     "test_package::MacZipTest::test_licence_and_notice_are_in_the_zip"),
    ("#429", "Settings save works before the first profile read answers.",
     "test_about_you::AboutYou::test_C_a_late_read_fills_a_box_that_was_typed_in_saved_and_left_alone"),
    ("#455", "The new use case shows as hidden at both widths and in both themes; turning the eye on shows it.",
     "test_uc_dashboard_edit::Edit::test_a_new_use_case_is_hidden_at_each_width_and_theme_and_turning_its_eye_on_shows_it"),
    ("#174", "Open clark with no name: the Welcome card appears; Save keeps the name and it never returns.",
     "test_welcome::Welcome::test_C_save_keeps_the_name_through_clark_and_it_is_never_asked_again"),
    ("#174", "Not now (or Esc) closes it and it stays closed.",
     "test_welcome::Welcome::test_C_not_now_closes_it_saves_nothing_and_it_stays_closed"),
    ("#485", "Add a next step with Enter; it names the use case and has one Undo.",
     "test_uc_dashboard_edit::Edit::test_a_next_step_is_added_with_enter_names_the_use_case_and_has_one_undo"),
    ("#485", "Link existing work items to a use case from a box, several at once.",
     "test_uc_dashboard_edit::Edit::test_link_an_existing_work_item_opens_a_box_beside_main_and_links_several_in_one_step"),
    ("#485", "Where it stands changes in place with one Undo.",
     "test_uc_dashboard_edit::Edit::test_where_it_stands_is_changed_in_place_in_one_step_with_one_undo"),
    ("#448", "Open a risk's status menu: Status and Rating sections; pick Green and Undo it.",
     "test_inline_edits::Live::test_rating_from_the_status_picker_sets_impact_and_likelihood_with_one_undo"),
    ("#448", "A closed risk is still offered a rating and stays closed.",
     "test_inline_edits::Live::test_a_closed_risk_is_offered_a_rating_and_keeps_its_closed_look"),
    ("#448", "The peek has the same status picker as the table.",
     "test_inline_edits::Live::test_the_peek_has_the_same_status_picker_as_the_table"),
    ("#457", "Open an overdue action in Edit: the bar says how many days overdue and Move to Friday moves the date, with Undo.",
     "test_peek_latest::Browser::test_the_overdue_bar_says_how_late_and_moves_to_friday_with_one_undo"),
    ("#457", "The peek shows Last updated with the date and time.",
     "test_peek_latest::Browser::test_the_last_updated_stamp_is_shown_in_local_time_and_follows_a_change"),
    ("#453", "Open Publish: the PDF tick reads 'Also a PDF'.",
     "test_publish_dialog::Dialog::test_C_pdf_tick_is_there_unticked_and_never_remembered"),
    ("#453", "Right-click a dashboard tile in Edit: the menu is headed 'Outline colour'.",
     "test_glance_page::EditTiles::test_right_click_sets_the_outline_colour_and_undo_puts_it_back"),
    ("#453", "Help names every milestone state.",
     "test_help_content::HelpMatchesThePage::test_every_line_that_lists_milestone_states_lists_fr50s"),
    ("#437", "Tick To client: the warning has both sentences.",
     "test_publish_dialog::Finished::test_C_the_warning_has_both_sentences_at_both_widths_in_light_and_dark"),
    ("#437", "After publishing, the dialog closes by itself and a note says what was done.",
     "test_publish_dialog::Finished::test_C_the_finished_dialog_closes_by_itself_and_a_note_with_no_undo_says_what_was_done"),
    ("#607", "Export a Word report to a client folder where the file already appears: one clear message, no repeat.",
     "test_word_route::Export::test_a_client_copy_failure_says_it_once_and_plainly"),
    ("A-D25", "The menu lists the projects and marks the open one.",
     "test_project_switch::ProjectSwitch::test_C_the_menu_lists_only_the_projects_with_open_counts"),
    ("A-D25", "Choosing a project opens it.",
     "test_project_switch::ProjectSwitch::test_C_choosing_a_project_changes_the_address_and_says_so"),
    ("A-D1", "The band names the project, the week and the client.",
     "test_cover_band::Served::test_the_band_names_the_project_the_week_and_the_client"),
    ("A-D1", "The published file draws the band too.",
     "test_cover_band::InTheFile::test_the_published_file_draws_the_words_in_its_bar_from_its_own_data"),
    ("A-D3", "Every section is a card with one square.",
     "test_section_card_look_page::Cards::test_every_section_is_a_card_with_one_square_in_each_style"),
    ("A-D3", "The published file draws the same cards.",
     "test_section_card_look_page::PublishedCards::test_the_published_file_draws_the_same_cards"),
    ("A-D11", "See all counts every linked item and opens that list.",
     "test_glance_page::UseCases::test_see_all_counts_every_linked_item_and_opens_that_same_list"),
    ("A-D11", "A row opens in place with next steps and See all.",
     "test_glance_page::UseCases::test_a_row_opens_in_place_with_where_it_stands_the_next_steps_and_see_all"),
    ("B-5", "The button counts and the list has Restore.",
     "test_work_archived_filter::ArchivedFilter::test_is_archived_lists_the_archived_items_read_only_and_clearing_brings_back_the_list"),
    ("B-5", "Restore puts the item back and Undo archives it again.",
     "test_work_archived_filter::ArchivedFilter::test_a_row_opens_the_read_only_peek_and_restore_puts_it_back_with_one_undo"),
    ("#620", "Hand over three, edit one owner, Undo: the other two go back and the edited one stays.",
     "test_changes_hand_over::PeopleList::test_an_undo_of_a_hand_over_skips_only_the_owner_that_changed_and_undoes_the_rest"),
    ("#210", "A risk's Priority cell sets impact and likelihood in place.",
     "test_priority_rating_cell::Live::test_a_risks_priority_sets_impact_and_likelihood_in_place_light_and_dark"),
    ("#210", "A pick is one step with one Undo and the priority follows.",
     "test_changes_rating_cell::RatingCell::test_the_cells_pick_is_one_step_with_one_undo_and_the_priority_follows"),
    ("#424", "Duplicate on a client-visible item gives a copy that is client-visible, and a hidden one gives a hidden copy",
     "test_changes_item_eye::Duplicate::test_a_copy_keeps_the_items_eye_whether_or_not_the_request_carries_it"),
    ("#425", "The Add box uses the one shared helper that makes everything behind a dialog inert",
     "test_modal_layers::Source::test_the_add_box_uses_the_shared_helper_and_no_list_of_its_own"),
    ("#425", "With a dialog open every other layer and the toast buttons are inert, and the message area stays live",
     "test_modal_layers::Layers::test_the_draft_email_makes_every_other_layer_inert_and_a_toast_button_unreachable"),
    ("#401", "Help's Work items filter table lists Freshness as the page does",
     "test_help_content::HelpMatchesThePage::test_the_work_items_filters_name_freshness_as_the_page_does"),
    ("#402", "Help names the Use cases link, Esc and the browser Back, and no Back button",
     "test_help_content::HelpMatchesThePage::test_a_use_case_names_the_ways_back_the_page_has"),
    ("#403", "Help says Delete section is for a text section and for Needs from you",
     "test_help_content::HelpMatchesThePage::test_delete_section_is_said_for_both_kinds_that_have_it"),
    ("#440", "The Settings chips are a bar of their own under the top bar, on the page ground, and never hide a card scrolled into view",
     "test_settings_bar::SettingsBar::test_C_the_bar_stays_under_the_top_bar_on_the_page_ground_and_never_hides_a_card"),
    ("#440", "The chip of the card you are reading is marked as you scroll",
     "test_settings_bar::SettingsBar::test_C_the_marked_chip_follows_the_card_you_are_reading_as_you_scroll"),
    ("#440", "Saving the name or the email says so with Undo, and a second save of the same words says nothing",
     "test_about_you::AboutYou::test_C_saving_the_name_or_the_email_says_so_with_undo_and_a_second_save_of_the_same_words_says_nothing"),
    ("#440", "Undo puts the old value back in the box, the menu and the store",
     "test_about_you::AboutYou::test_C_undo_puts_the_old_value_back_in_the_box_the_menu_and_the_store"),
    ("#451", "The progress section's Overall is one tinted tile with two figures, a labelled bar, a 0% to 100% scale, a chip and words (row 930)",
     "test_tracker_page::Page::test_view_overall_is_one_tinted_tile_with_two_figures_a_labelled_bar_a_scale_a_chip_and_words"),
    ("#451", "The Achieved column has a bar, the figure and the red chip",
     "test_tracker_page::Page::test_view_achieved_column_has_a_bar_the_figure_and_the_red_chip"),
    ("#451", "The author's weights note is in Edit and not in View",
     "test_tracker_page::Page::test_the_weights_note_is_in_edit_for_the_author_and_not_in_view"),
    ("#452", "A chase shows the three tones, with clark's own choice picked, and how often it was chased",
     "test_draft_email_editor::Component::test_a_chase_shows_the_three_tones_preselected_to_clarks_choice_and_the_count"),
    ("#452", "Picking a tone asks for a new draft, and changing the kind hands the choice back to clark",
     "test_draft_email_editor::Component::test_picking_a_tone_asks_for_a_new_draft_and_changing_the_kind_hands_the_choice_back"),
    ("#452", "Only a chase has the tone control",
     "test_draft_email_editor::Component::test_only_a_chase_has_the_tone_control"),
    ("#452", "No tone word reaches the email",
     "test_draft_email::ToneChoice::test_no_tone_word_reaches_the_email"),
    ("#456", "Work items has a letter badge, no Type column, an eye column and a card for each group, in both modes and themes",
     "test_work_table_parity::Table::test_letter_badge_no_type_column_eye_column_and_a_card_per_group_in_both_modes_and_themes"),
    ("#456", "In Edit the eye turns an item off or on with a message and Undo",
     "test_work_table_parity::Table::test_the_eye_in_edit_turns_an_item_off_and_on_with_a_toast_and_undo"),
    ("#456", "In View the eye is a mark only and a click changes nothing",
     "test_work_table_parity::Table::test_the_eye_in_view_is_a_read_only_mark_and_a_click_changes_nothing"),
    ("#456", "A published file has no eye and no client column",
     "test_work_table_parity::Table::test_a_published_file_has_no_eye_and_no_client_column"),
    ("#435", "The Expected chip in the milestone calendar is whole at 900 px and in Quarter",
     "test_milestones_calendar::CalendarKeys::test_the_expected_chip_is_whole_at_900_px_and_in_quarter"),
    ("#441", "A use case's next steps are every open item in the client's wording, with the owner in a circle",
     "test_glance_page::UseCases::test_next_steps_are_every_open_item_in_the_client_wording_with_the_owner_in_a_circle"),
    ("#429", "A save that is turned away shows no toast and no Undo",
     "test_about_you::AboutYou::test_C_a_refused_save_shows_no_toast_and_no_undo"),
    ("#325", "The data layout step 12 is in and the version says so",
     "test_publication_numbers::TheTriggerStepTwelve::test_the_step_is_number_12_and_the_version_says_so"),
    ("#325", "A data file at layout 10 or 11 is upgraded, and then refuses a change to a client copy's path",
     "test_publication_numbers::TheTriggerStepTwelve::test_a_file_at_step_10_or_11_with_the_narrow_trigger_is_upgraded_and_refuses_a_client_path_update"),
    ("#325", "The data layout step is safe to repeat",
     "test_publication_numbers::TheTriggerStepTwelve::test_the_step_is_safe_to_repeat"),
    ("#622", "Backups are off the shared copy folder by default and the setting is saved with the others",
     "test_backup_copy::TheSetting::test_off_by_default_and_saved_beside_the_other_settings"),
    ("#622", "Each backup is also copied to the chosen folder as a finished single file under the same name",
     "test_backup_copy::TheCopy::test_each_backup_is_also_a_finished_single_file_under_the_same_name"),
    ("#622", "A missing or unwritable copy folder is a plain warning, and the backup and the save still work",
     "test_backup_copy::WhenItFails::test_a_missing_folder_is_a_plain_warning_and_the_backup_and_the_save_still_succeed"),
    ("#622", "The copy folder may be in OneDrive; the live data folder still may not",
     "test_backup_copy::OneDrive::test_the_copy_folder_may_be_in_onedrive_and_the_live_folder_still_may_not"),
    ("#622", "A copy is restored from the folder onto a clean data folder",
     "test_backup_copy::Restoring::test_a_copy_is_restored_from_the_folder_onto_a_clean_data_folder"),
    ("#436", "An archived milestone opens read only in the peek, with Restore there",
     "test_milestones_archived::Archived::test_the_name_opens_the_milestone_read_only_in_the_peek_with_restore_there"),
    ("#436", "Restore puts the milestone back with one Undo",
     "test_milestones_archived::Archived::test_restore_puts_the_milestone_back_with_one_undo_and_focus_goes_to_the_button"),
    ("#436", "A press on the eye takes a milestone off the dashboard with one Undo",
     "test_milestones_eye::Editor::test_a_press_takes_it_off_the_dashboard_with_one_change_and_one_undo_puts_it_back"),
    ("#436", "A published file has no eye, no mark and not the left-out milestone",
     "test_milestones_eye::Editor::test_the_published_file_has_no_eye_no_mark_and_not_the_left_out_milestone"),
    ("#436", "A milestone row's second line is one line at 1400 px and keeps four columns at 900 px",
     "test_milestones_oneline::Rows::test_the_cells_sit_in_four_columns_at_1400_and_900_px"),
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
]
# (item, check, kind, why, what the person does)
WALK_THROUGH = [
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

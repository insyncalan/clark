"""clark 1.0.3's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.3 row. Each release gets a
test_vNNN file, so the walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v103

Same shape as test_v102.
  COVERED       a merged row a person can see, already covered by a test elsewhere. test_every_covering_test_named_here_exists
                fails if one goes missing. Rows 273, 799 (its Weekly snapshot is gone, row 1065), 802, 827, 872, 874, 889, 895, 905, 907, 917, 918 and 920 have no visible change (NO_VISIBLE_CHANGE).
  WAITING       a row that is not on main yet but has a marker in the source that appears when it lands (item, check, pull request,
                a file under the top folder, the text in it). Skipped, with the pull request. After the cut commit has set the
                version and the marker is there, the row fails until it is moved to COVERED with its test. Empty today: the
                waiting rows live in the status table of the sheet, between its two marker comments.
  WALK_THROUGH  judgement or live only. Skipped: 'needs a person'. Empty today.

The notes hold only merged, user-visible rows; no DRAFT line is allowed anywhere. The status table in the sheet lists every 1.0.3 row
(refresh it with the regeneration helper as rows merge). The cut checks (version, files, layout) skip until the cut commit sets 1.0.3.

The data layout moves from 16 to 17 in 1.0.3 (row 811): the notes carry the Read this first paragraph and the store must say 17.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.3"
SCHEMA = 17              # 1.0.1 moved to layout 16; 1.0.3 moves it to 17 (the Needed from the client flag, row 811)

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#856", 'The project menu starts on the open project and lists only projects.',
     "test_project_switch::ProjectSwitch::test_C_the_menu_starts_on_the_open_project_and_ends_with_the_projects"),
    ("#855", "In Edit, Ctrl or Cmd + J opens ask clark from anywhere and the button's tooltip names it.",
     "test_help_pr_a::TopBar::test_ctrl_or_cmd_j_is_handled_and_the_ask_tooltip_names_it"),
    ("#849", 'The Settings switches say their new state in a message with one Undo.',
     "test_ask_settings::Settings::test_the_switch_says_its_state_in_a_toast_with_one_undo_and_keeps_the_focus"),
    ("#819", "The eye toggles in View and Edit on the lists and the card's eye is a button.",
     "test_work_table_parity::Source::test_the_eye_is_a_button_in_view_and_edit_with_words"),
    ("#789", 'The empty search says the typed words, offers Clear search and a hint.',
     "test_filter_line_page::Line::test_the_empty_state_says_items_not_open_items_on_closed_and_all"),
    ("#859", "A use case's work item row opens its peek beside the page.",
     "test_use_case_detail::Detail::test_a_work_item_row_opens_its_peek_beside_the_page_row_859"),
    ("#860", 'A linked milestone opens its peek and shows its state.',
     "test_use_case_detail::Detail::test_a_linked_milestone_opens_its_peek_and_shows_its_state_row_860"),
    ("#768", "The client workbook's sheets are protected with no password and the export's actions.",
     "test_excel_client_protect::Protect::test_every_sheet_is_protected_with_no_password_and_the_export_actions"),
    ("#768", "The client workbook's dates are left-aligned.",
     "test_excel_client_layout::Layout::test_dates_are_left_aligned_and_a_date_format"),
    ("#806", 'A click on a Work items row or card opens its peek.',
     "test_inline_67::RowClick::test_a_click_on_a_row_opens_its_peek_and_one_in_a_field_or_button_does_not"),
    ("#816", 'Help describes the Settings links as a list at the left.',
     "test_help_pr_a::SettingsChips::test_the_menu_names_and_order_are_the_pages"),
    ("#781", 'Messages are a centred pill at the foot.',
     "test_toast_pill::ToastPill::test_source_has_no_left_edge_and_a_pill_radius"),
    ("#792", 'The Keys group is drawn without a box.',
     "test_about_you::KeysGroupHasNoFrame::test_the_keys_fieldset_uses_the_frameless_group_class"),
    ("#777", 'The use case crumb is in tracked capitals, its link underlined on hover.',
     "test_use_case_detail::Detail::test_the_crumb_is_tracked_capitals_and_its_link_is_not_underlined"),
    ("#780", 'The change card has a quiet look and a small flat Apply.',
     "test_ask_change_page::TheCard::test_the_card_has_a_quiet_look_and_a_small_flat_apply"),
    ("#790", 'The calendar scales are one capsule.',
     "test_milestones_parity::Switcher::test_the_calendar_scales_are_one_capsule_with_the_active_one_filled_and_today_as_tall"),
    ("#791", 'Change status has room before its arrow.',
     "test_use_case_detail::Detail::test_change_status_has_room_between_its_words_and_chevron_and_the_controls_are_as_tall"),
    ("#791", 'The Commitment menu is headed Commitment.',
     "test_use_case_detail::Detail::test_the_commitment_menu_is_headed_commitment"),
    ("#821", 'Quarter view markers have no text and open the peek.',
     "test_milestones_page::RealBrowser::test_a_quarter_chip_is_a_button_with_no_text_and_opens_the_peek"),
    ("#795", 'With asking off the panel keeps its greeting, buttons and box.',
     "test_ask_look::Look::test_off_and_not_set_up_at_both_widths_light_and_dark"),
    ("#794", 'The Answer and You labels are for readers only.',
     "test_ask_panel::Panel::test_the_who_labels_are_for_a_reader_only_and_take_no_room"),
    ("#854", 'The clark logo goes Home (the test checks the Help side; the click is by eye).',
     "test_help_pr_a::TopBar::test_the_help_has_no_logo_bullet_the_logo_has_no_help_line_of_its_own"),
    ("#769", 'The Word tables are wide enough for IDs, dates and words.',
     "test_docx_build::WordTableWidths::test_open_actions_and_risks_columns_are_wide_enough_for_ids_dates_and_words"),
    ("#848", 'The row menu keeps its place.',
     "test_row_menu::Menu::test_a_list_opens_on_hover_stays_while_the_pointer_travels_and_the_menu_does_not_move"),
    ("#822", 'No Show archived while nothing is archived.',
     "test_milestones_archived::ArchivedNone::test_no_button_and_no_empty_box_with_none_archived"),
    ("#786", 'The profile circle shows with no project open.',
     "test_demo_banner::DemoLine::test_the_profile_circle_is_on_the_empty_screen_with_only_the_entries_that_need_no_project"),
    ("#793", 'The last Help contents entry lights at the foot.',
     "test_help_nav_page::Nav::test_the_last_entry_is_marked_at_the_foot_of_each_tab"),
    ("#858", 'The first open of ask clark keeps typed words.',
     "test_ask_panel::Panel::test_row_858_the_box_keeps_its_words_and_the_panel_is_usable_while_it_checks"),
    ("#800", 'No heavy ring on a mouse open.',
     "test_client_menu::Words::test_row_800_the_menu_source_marks_a_mouse_open_and_the_css_drops_the_ring_for_it"),
    ("#837", "The Word copy lists only open actions, risks and issues.",
     "test_docx_build::WordOpenItemsOnly::test_a_closed_or_cancelled_action_or_risk_is_not_listed"),
    ("#837", "The open items are still listed in the Word copy.",
     "test_docx_build::WordOpenItemsOnly::test_open_ones_are_still_listed"),
    ("#767", "The printed Milestones timeline is drawn to the page width and does not scroll.",
     "test_pdf_print::Source::test_the_printed_timeline_is_drawn_to_the_page_and_does_not_scroll"),
    ("#767", "The print leaves off the empty use case lines and their headings.",
     "test_pdf_print::Browser::test_the_print_leaves_off_the_empty_use_case_lines_and_their_headings"),
    ("#771", "The main button of a dialog or form is the aqua pill with dark text.",
     "test_buttons_771_772::Buttons::test_the_main_button_is_the_aqua_gradient_with_readable_dark_text"),
    ("#771", "The main button keeps its focus ring.",
     "test_buttons_771_772::Buttons::test_the_main_button_keeps_its_focus_ring"),
    ("#772", "The search button has an outline and the ask clark text is smaller.",
     "test_buttons_771_772::Buttons::test_the_search_button_has_an_outline_and_the_ask_text_is_smaller"),
    ("#785", "The published footer gives the date once and no View only.",
     "test_publication_footer::TheFooter::test_row_785_the_client_sees_the_date_once_and_no_view_only_at_1400_and_900_light_and_dark"),
    ("#765", "Each project form label is left of its field on one row.",
     "test_project_form_look::Look::test_each_label_is_left_of_its_field_on_one_row_in_two_columns"),
    ("#765", "Every project form field has a visible border.",
     "test_project_form_look::Look::test_every_field_has_a_visible_one_pixel_border_in_light_and_dark"),
    ("#863", "In the project menu the open-items count sits under the name.",
     "test_project_menu_layout::ProjectMenuLayout::test_C_the_count_sits_under_the_name_in_both_themes_and_modes_at_both_widths"),
    ("#766", "The peek's Status, Priority, Owner and Due are four cells.",
     "test_peek_card::CardRule::test_the_card_rules_are_in_the_stylesheet_in_tokens_only"),
    ("#814", "A click outside the peek and Esc close it; clicks that belong to it do not.",
     "test_peek_outside::OutsideBrowser::test_esc_and_a_click_outside_close_it_and_clicks_that_belong_to_it_do_not"),
    ("#728", "Sneak peek changes a milestone's dates and status in words, and Achieved asks first.",
     "test_sneak_milestone_usecase::Milestone::test_achieved_asks_first_and_fills_the_date_the_way_the_store_does"),
    ("#728", "Sneak peek changes a use case's status, headline and commitment in words.",
     "test_sneak_milestone_usecase::UseCase::test_status_headline_and_commitment"),
    ("#797", "Add a section offers the six new templates, described in the same words in the picker and in Help.",
     "test_templates::Logic::test_the_box_and_help_describe_every_template_in_the_same_words"),
    ("#825", "The use case page needs no Edit mode: every control is there.",
     "test_use_case_detail::Detail::test_every_control_is_there_with_no_edit_mode_at_1400_and_900_px_light_and_dark_row_825"),
    ("#825", "Each use case page control saves as one change with one Undo, with no Edit mode.",
     "test_use_case_detail::Detail::test_each_control_saves_as_one_change_with_one_undo_with_no_edit_mode_row_825"),
    ("#757", "The open tab stays in view in the top bar at 900 px.",
     "test_top_bar_tabs::TopBarTabs::test_a_row_narrowed_after_the_scroll_shows_the_open_tab_again_at_900"),
    ("#764", "The top bar's tab row is not cut off at 900 px.",
     "test_top_bar_tabs::TopBarTabs::test_the_tabs_tighten_their_padding_at_900_px_and_never_wrap"),
    ("#775", "The Work items board columns are lifted cards and the full-screen icon is arrows.",
     "test_work_board_page::Cards::test_row_775_columns_are_lifted_cards_and_the_full_screen_icon_are_arrows"),
    ("#776", "The Sneak peek words box is a floating card.",
     "test_peek_arrows::Arrows::test_row_776_the_words_box_is_a_floating_card_in_light_and_dark"),
    ("#776", "The Sneak peek card shows phrase chips, with Not now and Make the change under the lines.",
     "test_peek_arrows::Arrows::test_row_776_the_words_box_has_chips_and_the_button_row_after_a_reading_in_light_and_dark"),
    ("#839", "A date before 1900 in the Excel export is dd-mm-yyyy text, not ####.",
     "test_excel_pre1900::ToCell::test_cell_types_in_the_saved_file"),
    ("#839", "The same date in the client workbook is text, and the Week ending line reads in the same form.",
     "test_excel_pre1900::ClientWorkbook::test_client_sheet_has_text_for_an_old_due_date"),
    ("#787", "The profile menu has a Settings entry after Published reports.",
     "test_profile_menu::ProfileMenu::test_C_settings_is_an_entry_after_published_reports_before_appearance"),
    ("#824", "Work items edit in View at both widths, light and dark.",
     "test_work_no_mode::WorkNoMode::test_work_items_edit_in_view_at_both_widths_in_light_and_dark"),
    ("#824", "On a row Enter opens the peek and the arrows walk the cells.",
     "test_list_keys::Keys::test_enter_opens_the_peek_and_the_arrows_never_open_or_close_it_while_the_peek_keeps_its_arrows"),
    ("#866", "An edited owner survives a rename of the old person.",
     "test_changes_hand_over::SingleEdit::test_an_edited_owner_survives_a_rename_of_the_old_person"),
    ("#866", "The owner edit is undone with its text and link together.",
     "test_changes_hand_over::SingleEdit::test_the_edit_is_undone_and_the_undo_undone_with_text_and_link_together"),
    ("#866", "History shows one Owner line for an edit that changes the link.",
     "test_changes_hand_over::SingleEdit::test_history_shows_one_owner_line_for_an_edit_that_changes_the_link"),
    ("#894", "Two closes before the Back lands step back once.",
     "test_multi_select::Page::test_two_closes_before_the_back_lands_step_back_once"),
    ("#862", 'The page has a Skip to content link as its first Tab stop.',
     "test_top_bar_tabs::SkipLink::test_the_source_has_the_link_first_and_main_can_take_focus"),
    ("#900", 'The command palette lists Pages, Actions, Projects, Commands in that order.',
     "test_palette::Results::test_the_groups_come_in_the_order_pages_actions_projects_commands"),
    ("#801", 'Every sheet of the Excel export is landscape, A4 and one page wide.',
     "test_excel_cover::InTheWorkbook::test_every_sheet_prints_landscape_and_one_page_wide_and_tile_values_are_inset"),
    ("#828", 'All five milestone peek fields are set in one step with one Undo.',
     "test_changes_milestone_fields::Fields::test_all_five_are_set_in_one_step_and_one_undo_puts_them_all_back"),
    ("#826", 'Import from Word is offered without Edit, and Settings has no View | Edit pill.',
     "test_word_screens::Import::test_the_entry_and_the_box_are_there_without_edit_mode"),
    ("#826", 'Settings has no View | Edit pill.',
     "test_word_screens::Import::test_settings_has_the_import_and_no_view_edit_pill"),
    ("#823", 'Add milestone works on the Milestones page without Edit.',
     "test_milestones_inline::Inline::test_view_add_milestone_adds_one"),
    ("#873", 'An imported owner survives a rename of the old person.',
     "test_excel_import_ids::OwnerLink::test_an_imported_owner_edit_survives_a_rename_of_the_old_person"),
    ("#910", 'The Not reviewed tile is gone from At a glance.',
     "test_glance_not_reviewed::NotReviewed::test_there_is_no_not_reviewed_tile_in_view_or_edit_even_with_an_old_browser_flag"),
    ("#667", 'With no stored style the Dashboard is one card.',
     "test_section_card_look_page::DefaultOneCard::test_with_no_stored_choice_the_dashboard_is_flat_full_width_with_a_rule"),
    ("#847", 'Below 1000 px the item and milestone peeks fill the window.',
     "test_peek_narrow::NarrowBrowser::test_the_rule_is_in_the_stylesheet"),
    ("#850", 'The Current state text shows in Edit.',
     "test_item_rows::CurrentStateInEdit::test_the_text_is_drawn_in_view_and_in_edit_in_both_themes_at_both_widths"),
    ("#851", 'Marked items with no client wording are listed under their own text.',
     "test_item_rows::UnwordedRows::test_marked_items_with_no_wording_are_listed_in_view_and_edit_with_n_of_m"),
    ("#773", 'The report bar hint is a chip and a hidden tile is dashed and untinted.',
     "test_dashboard_edit_look::EditLook::test_the_note_is_a_chip_and_a_hidden_tile_is_dashed_and_untinted"),
    ("#774", 'A hover tooltip hides when its menu opens and sits under menus.',
     "test_menu_tooltip::MenuTooltip::test_the_tip_hides_when_the_menu_opens_on_leave_on_esc_and_on_blur_and_sits_under_menus"),
    ("#784", 'The published Work items Item column is wide enough at 900 px.',
     "test_published_item_column::PublishedItemColumn::test_the_item_column_is_wide_enough_and_the_table_fits"),
    ("#869", 'A Settings switch message goes when the page leaves Settings.',
     "test_single_keys::PageKeys::test_the_switch_says_its_state_in_a_toast_with_one_undo_and_keeps_the_focus"),
    ("#811", "The peek of an action, a risk or an issue has a Needed from the client switch; a decision has none.",
     "test_peek_client_action::Page::test_a_risk_has_it_and_a_decision_has_none"),
    ("#811", "The data step to layout 17 keeps every row and starts the flag off.",
     "test_store_client_action_migration::Migrating::test_old_data_opens_keeps_every_row_and_the_flag_is_off"),
    ("#861", "A flagged, open, client-visible item is listed under Needs from you in the published report.",
     "test_publish_client_action::Listed::test_a_flagged_open_visible_item_is_listed_with_the_four_fields"),
    ("#861", "A closed or cancelled flagged item is not listed.",
     "test_publish_client_action::Listed::test_a_closed_or_cancelled_item_is_not_listed"),
    ("#673", "The Milestones Legend button has the information icon.",
     "test_milestones_details::Details::test_the_toggle_is_a_real_button_above_the_list_and_starts_open"),
    ("#815", "The brand check stops a hidden outside address in more cases.",
     "test_publish_brand_cr_ff::Cases::test_an_open_string_ended_by_cr_ff_or_crlf_does_not_hide_a_later_address"),
    ("#893", "Clearing a row's client wording is one step with one Undo.",
     "test_changes_clear_wording::ClearWording::test_a_clear_is_one_step_one_undo_and_the_same_clear_twice_makes_no_step"),
    ("#893", "A blank wording clears it, the row shows its title, and Undo puts the words back.",
     "test_clear_wording_in_place::ClearWordingInPlace::test_a_blank_wording_clears_it_the_row_shows_its_title_and_undo_puts_the_words_back"),
    ("#909", "Esc right after a second pick clears both while the peek is still closing.",
     "test_multi_select::Page::test_esc_right_after_a_second_pick_clears_both_while_the_peek_is_still_closing"),
    ("#877", 'Dialogs and their dim background ease in, and are still when reduced.',
     "test_motion_dialogs_menus::MotionDialogsMenus::test_row_877_dialogs_and_their_dim_background_ease_in_and_are_still_when_reduced"),
    ("#878", 'Menus drop in, and are still when reduced.',
     "test_motion_dialogs_menus::MotionDialogsMenus::test_row_878_menus_drop_in_and_are_still_when_reduced"),
    ("#879", 'The changed peek row flashes and is a still tint when reduced.',
     "test_motion_flash::MotionFlash::test_row_879_the_peek_flashes_and_is_a_still_tint_when_reduced"),
    ("#880", 'Opened group rows glide in, and are still when reduced.',
     "test_motion_group::MotionGroup::test_row_880_opened_rows_glide_in_and_are_still_when_reduced"),
    ("#881", 'Controls fade and cards lift, and snap when reduced.',
     "test_motion_press::MotionPress::test_row_881_controls_fade_and_cards_can_lift_and_snap_when_reduced"),
    ("#882", 'The toast rises in, and is still when reduced.',
     "test_motion_toast::MotionToast::test_row_882_the_toast_rises_in_and_is_still_when_reduced"),
    ("#883", 'The check mark draws, and is whole when reduced.',
     "test_motion_tick::MotionTick::test_row_883_the_check_mark_draws_and_is_whole_when_reduced"),
    ("#884", 'The View | Edit thumb slides and the Edit chrome fades; both are still when reduced.',
     "test_motion_modes::MotionModes::test_row_884_the_thumb_slides_and_the_edit_chrome_fades_and_both_are_still_when_reduced"),
    ("#885", 'The ask clark panel rises and sinks, and is still when reduced.',
     "test_motion_ask::MotionAsk::test_row_885_the_panel_rises_and_sinks_and_is_still_when_reduced"),
    ("#886", 'Placeholder blocks are still (the shimmer of this row was replaced by #934).',
     "test_skeleton_static::SkeletonStatic::test_row_934_the_blocks_are_still_with_motion_allowed_or_reduced"),
    ("#887", 'Board drag feedback lifts and highlights, and is still when reduced.',
     "test_motion_drag_feedback::MotionDragFeedback::test_row_887_cards_lift_and_columns_highlight_and_all_is_still_when_reduced"),
    ("#888", 'The badge ticks, Undo pulses and the eye blinks, and none runs when reduced.',
     "test_motion_micro_delight::MotionMicroDelight::test_row_888_the_badge_ticks_undo_pulses_and_the_eye_blinks_and_none_runs_when_reduced"),
    ("#890", 'Sources are closed by default and list the files the answer used.',
     "test_ask_panel::Panel::test_sources_are_closed_by_default_and_list_the_files_the_answer_used"),
    ("#896", "The Help peek lists the open page's how-to articles.",
     "test_help_peek_real::Real::test_row_896_the_peek_lists_the_how_to_articles_of_the_open_page"),
    ("#899", 'The top bar has no Help button and the ? key toggles Help.',
     "test_help_peek::Peek::test_the_top_bar_has_no_help_button_and_the_key_toggles"),
    ("#901", 'The palette finds the data by words, ID and person.',
     "test_palette::Results::test_search_finds_the_data_by_words_id_and_person"),
    ("#779", 'Help has its search at the top right and no Back button; Esc closes it.',
     "test_help_panel::Panel::test_the_top_bar_has_no_help_button_and_help_has_no_back_button"),
    ("#829", "A work item's title is changed in place in the peek with one Undo.",
     "test_peek_fields::Title::test_the_title_is_changed_in_place_with_enter_and_undone_in_one_step"),
    ("#829", "The client wording is changed in place in the peek with one Undo.",
     "test_peek_fields::Wording::test_the_client_wording_is_changed_in_place_and_undone_in_one_step"),
    ("#829", 'Workstream, Milestone and Use case are chosen in the peek, each with one Undo.',
     "test_peek_fields::Picks::test_workstream_milestone_and_use_case_are_chosen_in_the_peek_each_with_one_undo"),
    ("#829", 'Duplicate in the peek adds a copy, opens it, and one Undo takes it back.',
     "test_peek_fields::Duplicate::test_duplicate_in_the_peek_adds_a_copy_opens_it_and_one_undo_takes_it_back"),
    ("#892", 'Archive in the peek hides the item, closes the peek, and one Undo brings it back.',
     "test_peek_fields::Archive::test_archive_in_the_peek_hides_the_item_closes_the_peek_and_one_undo_brings_it_back"),
    ("#901", 'An item with no owner is not found by the word null or undefined.',
     "test_palette::Results::test_search_finds_the_data_by_words_id_and_person"),
    ("#915", 'History names an Excel import once.',
     "test_history_rows::Rows::test_excel_import_is_named_once_for_what_the_import_stores"),
    ("#783", "Add a section shows the templates as a grid of cards with a picture and width labels, and an X closes it.",
     "test_templates::Box::test_the_templates_are_a_grid_of_cards_with_a_sketch_and_width_chips_and_an_x_closes_it"),
    ("#783", "The chosen template's card shows the focus ring in light and dark.",
     "test_templates::Box::test_the_focus_ring_is_the_brand_blue_in_light_and_dark_and_the_scrim_is_a_token"),
    ("#939", "An update file with no signature file installs while the release key is the placeholder.",
     "test_update_signature::PlaceholderKeyTest::test_an_unsigned_file_installs_through_take_in_with_the_placeholder_key"),
    ("#939", "With a real release key an update with no signature, or a wrong one, is refused.",
     "test_update_signature::PlaceholderKeyTest::test_a_real_release_key_in_force_refuses_unsigned_and_wrongly_signed"),
    ("#939", "An unsigned update is reviewed like any other while the release key is the placeholder.",
     "test_updater::ReviewTest::test_an_unsigned_update_is_reviewed_while_the_release_key_is_the_placeholder"),
    ("#939", "The Choose hint names the update for this computer and has no sentence about a signature file.",
     "test_update_page::Rows::test_row_60_the_choose_hint_names_the_update_for_this_computer_and_never_the_file_type_or_the_source_code"),
    ("#939", "An update with a newer data layout migrates with a copy, and Undo puts the old file back.",
     "test_update_layout_newer::NewerLayoutRelease::test_a_release_with_a_newer_layout_migrates_with_the_copy_and_undo_puts_the_old_file_back_byte_for_byte"),
    ("#947", "Grouped by workstream, the line under an item leaves the workstream out.",
     "test_work_items::Rules::test_the_sub_line_leaves_the_workstream_out_when_grouped_by_workstream"),
    ("#940", "On Work items in Edit at 900 px the Due, Priority and Status cells keep spare width.",
     "test_edit_cells_layout::Cells::test_every_edit_cell_is_one_tidy_box_at_both_widths_in_both_looks"),
    ("#940", "A published report's Item column is wide enough and the table fits at 900 px.",
     "test_published_item_column::PublishedItemColumn::test_the_item_column_is_wide_enough_and_the_table_fits"),
    ("#935", "A board column is a lifted card with a rule under its heading (the closest test; none pins the missing top stripe yet).",
     "test_work_board_page::Cards::test_row_775_columns_are_lifted_cards_and_the_full_screen_icon_are_arrows"),
    ("#805", 'Work items has no intro sentence and no count line.',
     "test_work_items_header::Header::test_row_805_no_intro_sentence_and_no_count_line_and_no_gap_left"),
    ("#807", 'A selected Board card or list row has no check mark but still shows it is selected.',
     "test_work_items_header::Header::test_row_807_a_selected_card_and_a_selected_list_row_have_no_check_mark_but_still_show_it_is_selected"),
    ("#808", 'The filter suggestion list floats over the table and pushes nothing.',
     "test_work_items_header::Header::test_row_808_the_suggestion_list_floats_over_the_table_and_pushes_nothing"),
    ("#808", 'The filter suggestion list floats over the board and pushes nothing.',
     "test_work_items_header::Header::test_row_808_the_suggestion_list_floats_over_the_board_and_pushes_nothing"),
    ("#809", 'The saved views are text tabs on a rule.',
     "test_work_items_header::Header::test_row_809_views_are_text_tabs_on_a_rule_the_same_for_made_and_user_views"),
    ("#812", 'Table and Board are a two-icon switch; Group by stays in the View menu.',
     "test_work_items_header::Header::test_row_812_table_and_board_are_a_two_icon_switch_and_group_by_stays_in_the_view_menu"),
    ("#813", 'There is no Freshness button; the filter still works by typing and by a saved view.',
     "test_work_items_header::Header::test_row_813_no_freshness_pill_and_the_filter_is_still_there_by_typing_and_by_a_saved_view"),
    ("#832", 'Work items has no wrapping card.',
     "test_page_frames::Frames::test_row_832_work_items_has_no_wrapping_card"),
    ("#832", 'Milestones has no wrapping card but the viewer keeps its own.',
     "test_page_frames::Frames::test_row_832_milestones_has_no_wrapping_card_but_the_viewer_keeps_its_own"),
    ("#832", 'Use cases has no wrapping card.',
     "test_page_frames::Frames::test_row_832_use_cases_has_no_wrapping_card"),
    ("#832", 'The Settings head has no card; the cards below keep theirs.',
     "test_page_frames::Frames::test_row_832_the_settings_head_has_no_card_but_the_cards_below_keep_theirs"),
    ("#832", 'A published file keeps its white card.',
     "test_published_frames::PublishedFrames::test_the_published_work_items_page_keeps_its_card"),
    ("#832", 'The rows text has 4.5 to 1 contrast against what is behind it.',
     "test_work_items_header::Header::test_row_832_the_rows_text_has_4_5_to_1_contrast_against_what_is_really_behind_it"),
    ("#902", 'The Appearance choice is a radio group with arrow keys.',
     "test_appearance::Appearance::test_C_appearance_arrow_keys_move_and_pick_row_902"),
    ("#903", 'Help Start here has a hero card and The loop above the jobs.',
     "test_help_panel::Panel::test_three_tabs_and_what_each_shows_today"),
    ("#904", "The palette's active row is outlined and kinds are capitals.",
     "test_palette::Looks::test_the_active_row_has_a_clear_outline_and_the_kind_labels_are_capitals"),
    ("#911", 'Every client workbook sheet prints landscape and one page wide.',
     "test_excel_client_layout::PrintSetup::test_every_sheet_of_the_client_workbook"),
    ("#876", 'A tab change fades and rises in; a redraw or the first draw does not.',
     "test_motion_page_change::MotionPageChange::test_row_876_a_tab_change_fades_and_rises_in_and_a_redraw_or_first_draw_does_not"),
    ("#830", 'The Use cases archived list restores a use case with Undo.',
     "test_use_cases_fields::Live::test_archived_list_restore_and_undo"),
    ("#857", 'The first-run name prompt takes the keyboard.',
     "test_welcome::Welcome::test_C_row_857_the_keyboard_works_at_once_tab_stays_inside_and_esc_closes"),
    ("#820", 'The ask panel title reads ask clark.',
     "test_ask_panel::Panel::test_the_panel_title_reads_ask_clark_and_the_ready_line_is_unchanged"),
    ("#865", 'Undo names a section move and the focus returns to its handle.',
     "test_report_editor::Sections::test_row_865_undo_after_a_move_names_the_move_and_focus_returns_to_the_handle"),
    ("#864", 'The bulk bar stays under the top bar while the list scrolls.',
     "test_bulk_bar::Page::test_the_bar_stays_under_the_top_bar_while_the_list_scrolls"),
    ("#906", 'Every section type deletes and Undo restores it.',
     "test_delete_any_section::RoundTrip::test_every_type_deletes_and_undo_restores_the_row_and_no_data_table_changes"),
    ("#906", "A built-in section can be deleted and Undo puts it back.",
     "test_changes_section_bodies::Deleting::test_the_built_in_sections_can_be_deleted_too_and_undo_puts_each_back"),
    ("#830", "The Use cases page has the archived list and the head buttons with no Edit.",
     "test_use_cases_fields::UseCaseFields::test_page_has_the_pieces"),
    ("#798", 'Published tabs share one eyebrow and Use cases rows show the headline.',
     "test_published_tabs_eyebrow::PublishedTabs::test_one_eyebrow_style_and_the_headline_on_the_use_cases_tab"),
    ("#840", 'Settings labels sit at the left of their controls.',
     "test_settings_rows::Rows::test_C_row_840_the_label_is_at_the_left_and_the_control_is_beside_it_and_not_capped"),
    ("#841", 'The Settings cards are compact.',
     "test_settings_rows::Rows::test_C_row_841_the_cards_are_compact")
]

# Merged rows with no visible change: they have a MERGED line in the status table and need no bullet, hand check or test here.
NO_VISIBLE_CHANGE = {"273", "799", "802", "827", "872", "874", "889", "895", "905", "907", "908", "914", "917", "918", "920", "932", "941"}

# Rows with one part merged and the rest open: the merged part is covered here, the row stays IN REVIEW in the table.
PARTLY_MERGED = {"767", "766", "775", "776", "807"}

# Not on main yet: (item, check, pull request, a file under the top folder and the text that is in it once the pull request has
# landed; marker None means there is no pull request to look for yet).
WAITING = []

# (item, check, kind, why, what the person does)
WALK_THROUGH = []

# "apply" is not banned here: the card's button is called Apply, and the notes must name it.
BANNED_WORDS = ("applied", "staged", "proposal", "sweep", "tracker", "vault", "extract", "refused")

STATUSES = ("MERGED", "IN REVIEW", "WAITING", "DROPPED")
BEGIN, END = "<!-- status table begin -->", "<!-- status table end -->"
ROW = re.compile(r"(?m)^\| (\d+) \| (.+?) \| (MERGED|IN REVIEW|WAITING|DROPPED) \| ([\d, ]*) \|$")
SECTIONS = ("## What is new", "## What is changed", "## What is fixed")


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
    p = ROOT / path
    return p.is_file() and marker.encode("utf-8") in p.read_bytes()


def read_notes():
    return (ROOT / "dev" / "release-notes" / (VERSION + "-plain.md")).read_text(encoding="utf-8")


def read_sheet():
    return (ROOT / "dev" / "handchecks" / (VERSION + "-sheet.md")).read_text(encoding="utf-8")


def table_rows(sheet):
    """[(id, title, status, pr)] in the status table block of the sheet."""
    block = sheet[sheet.index(BEGIN):sheet.index(END)]
    return ROW.findall(block)


def bullets(notes):
    """The bullet lines under What is new, What is changed and What is fixed."""
    out, inside = [], False
    for line in notes.splitlines():
        if line.startswith("## "):
            inside = line in SECTIONS
        elif inside and line.startswith("- "):
            out.append(line)
    return out


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
            self.assertRegex(pr, r"^(PR \d+|no pull request yet \((issue \d+|branch [\w-]+)\))$", check)
            self.assertEqual(marker is None, pr.startswith("no pull request"), check)

    def test_the_sheet_has_a_row_for_every_waiting_pull_request_and_every_covered_item(self):
        sheet = read_sheet()
        for item, check, pr, path, marker in WAITING:
            self.assertIn("WAITING " + pr, sheet, check)
            self.assertIn(item, sheet, check)
        for item in {i for i, _, _ in COVERED}:
            self.assertIn(item, sheet, f"{item} has no row on the hand-check sheet")


class StatusTable(unittest.TestCase):
    """The status table of every 1.0.3 row, between its two markers in the sheet."""

    def test_the_markers_are_there_once_and_in_order(self):
        sheet = read_sheet()
        self.assertEqual(sheet.count(BEGIN), 1)
        self.assertEqual(sheet.count(END), 1)
        self.assertLess(sheet.index(BEGIN), sheet.index(END))

    def test_every_table_line_is_a_well_formed_row_and_each_id_is_there_once(self):
        sheet = read_sheet()
        block = sheet[sheet.index(BEGIN):sheet.index(END)]
        lines = [l for l in block.splitlines() if l.startswith("| ") and not l.startswith("| Id ")]
        rows = table_rows(sheet)
        self.assertTrue(rows, "the status table is empty")
        self.assertEqual(len(lines), len(rows), "a table line is not Id | Title | MERGED/IN REVIEW/WAITING/DROPPED | PR")
        ids = [r[0] for r in rows]
        self.assertEqual(len(ids), len(set(ids)), "an id is in the table twice")

    def test_the_count_line_matches_the_rows(self):
        sheet = read_sheet()
        rows = table_rows(sheet)
        found = re.search(r"(?m)^(\d+) rows: (.+)\.$", sheet[sheet.index(BEGIN):sheet.index(END)])
        self.assertIsNotNone(found, "the count line is missing")
        self.assertEqual(int(found.group(1)), len(rows))
        counts = {s: sum(1 for r in rows if r[2] == s) for s in STATUSES}
        said = ", ".join(f"{counts[s]} {s}" for s in STATUSES if counts[s])
        self.assertEqual(found.group(2), said)

    def test_a_pull_request_cell_holds_numbers_only(self):
        for item, title, status, pr in table_rows(read_sheet()):
            self.assertRegex(pr, r"^(\d+(, \d+)*)?$", item)

    def test_a_merged_row_has_a_hand_check_row_or_is_listed_as_no_visible_change(self):
        sheet = read_sheet()
        covered = {i.lstrip("#") for i, _, _ in COVERED}
        for item, title, status, pr in table_rows(sheet):
            if status != "MERGED":
                continue
            self.assertTrue(item in NO_VISIBLE_CHANGE or item in covered,
                            f"{item} is MERGED: give it a covering test and a hand-check row, or list it in NO_VISIBLE_CHANGE")
            self.assertTrue(pr, f"{item} is MERGED and has no pull request in the table")

    def test_a_no_visible_change_row_is_in_the_table_and_a_covered_row_is_merged(self):
        merged = {r[0] for r in table_rows(read_sheet()) if r[2] == "MERGED"}
        self.assertEqual(sorted(NO_VISIBLE_CHANGE - merged), [], "listed as no visible change but not MERGED in the table")
        for item, check, where in COVERED:
            self.assertIn(item.lstrip("#"), merged | PARTLY_MERGED, f"{item} is covered but not MERGED in the table")

    def test_no_row_in_the_table_is_both_merged_and_still_waiting_in_this_file(self):
        waiting_here = {i.lstrip("#") for i, *_ in WAITING}
        for item, title, status, pr in table_rows(read_sheet()):
            if item in waiting_here:
                self.assertNotEqual(status, "MERGED", f"{item} landed: move it from WAITING to COVERED")


class Notes(unittest.TestCase):
    """The notes' own rules, read from the tree now (the same for every release): a title that says Beta, the Beta line, plain words,
    no lower-case 'ask clark' in a heading, no date in year-first form, no DRAFT marker, and a bullet only for a merged, visible row."""

    def setUp(self):
        self.text = read_notes()

    def test_the_title_the_beta_line_and_the_update_sentence(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("Beta", self.text)
        self.assertIn("This is the 1.0 build. It is still marked Beta: it works and is tested, but expect rough edges and changes between versions.", self.text)
        self.assertIn("Updating from inside clark works from this version on. To move from 1.0.2 to 1.0.3, install by hand", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_notes_carry_the_data_layout_paragraph_and_the_older_clark_sentence(self):
        self.assertIn("This version includes a change to how clark stores your data. Read this first.", self.text)
        self.assertIn("One change to how your data file is stored.", self.text)
        self.assertIn("Each action, risk and issue can now carry a Needed from the client flag.", self.text)
        self.assertIn("A safety copy of your data is made before anything changes.", self.text)
        self.assertIn("An older clark (1.0.2) will not open the new data file", self.text)
        self.assertIn("This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.", self.text)
        self.assertIn("First restore the safety copy", self.text)

    def test_the_known_limits_carry_the_by_hand_install_and_the_demo_limit(self):
        self.assertIn("## Known limits", self.text)
        self.assertIn("Updating from inside clark works from this version on.", self.text)
        self.assertIn("rename the old clark folder first", self.text)
        self.assertIn("Editing a demo project keeps it", self.text)

    def test_a_date_in_the_notes_is_day_first_and_no_one_is_named(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")
        self.assertNotRegex(self.text, r"team-[a-z]+-\d+", "a branch name is in the notes")

    def test_there_is_no_draft_marker_in_the_notes_or_the_sheet(self):
        for text in (self.text, read_sheet()):
            self.assertNotIn("DRAFT", text)

    def test_nobody_says_the_head(self):
        for text in (self.text, read_sheet()):
            self.assertNotRegex(text, r"(?i)\bthe head\b")

    def test_a_bullet_is_only_for_a_merged_visible_row_so_notes_and_sheet_agree(self):
        found = bullets(self.text)
        if not COVERED:
            self.assertEqual(found, [], "a bullet in the notes but no merged, visible row in COVERED")
        else:
            self.assertGreaterEqual(len(found), len({i for i, _, _ in COVERED}), "a covered row has no bullet in the notes")

    def test_the_notes_hold_no_status_table_and_no_row_ids(self):
        self.assertNotIn(BEGIN, self.text)
        self.assertNotRegex(self.text, r"(?m)^\| ")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 1.0.2 and earlier have their own test_vNNN; this file skips them
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

    def test_the_data_layout_is_still_the_one_the_notes_say(self):
        self.cut_made()
        if schema_version() > SCHEMA:
            self.skipTest("the layout has moved on past %d (now %d, a later release's step, row 926): these are 1.0.3's notes" % (SCHEMA, schema_version()))
        self.assertEqual(schema_version(), SCHEMA, "the notes name layout 17")

    def test_a_waiting_row_whose_pull_request_has_landed_has_been_moved_to_covered(self):
        self.cut_made()
        out = [f"{item} {pr}: it is in main now; give it a covering test in COVERED, a line in the notes and a row in the sheet"
               for item, check, pr, path, marker in WAITING if landed(path, marker)]
        self.assertEqual(out, [])

    def test_at_the_cut_no_row_is_left_unmerged_without_being_in_the_notes_as_waiting(self):
        """At the cut every row is MERGED or DROPPED, or still says WAITING / IN REVIEW in the table for the next release."""
        self.cut_made()
        for item, title, status, pr in table_rows(read_sheet()):
            self.assertIn(status, STATUSES, item)


def _skips():
    for i, (item, check, kind, why, does) in enumerate(WALK_THROUGH):
        def t(self, _m=f"needs a person ({kind}): {why}. Do this: {does}"):
            self.skipTest(_m)
        t.__name__ = "test_%s_%d_needs_a_person" % (re.sub(r"\W", "_", item), i)
        t.__doc__ = check
        setattr(Walk, t.__name__, t)
    for i, (item, check, pr, path, marker) in enumerate(WAITING):
        def w(self, _m=f"PENDING = '{pr}': not merged yet; this row runs once it lands and the cut commit is made"):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (re.sub(r"\W", "_", item), i)
        w.__doc__ = check
        setattr(Walk, w.__name__, w)


class Walk(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips()

if __name__ == "__main__":
    unittest.main()

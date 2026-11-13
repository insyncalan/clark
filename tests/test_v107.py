"""clark 1.0.7's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.7 row.

Run: python3 dev/run_tests.py test_v107

Same shape as test_v106. COVERED holds the rows merged so far (the first docs batch); the cut bookkeeping adds the rest from the merged list. WAITING and TEST_ONLY start empty.
The notes' own rules run now against dev/release-notes/1.0.7-plain.md. Everything that reads the hand-check sheet, and the cut
tests, skip until the cut commit sets 1.0.7 in src/clark/__init__.py; from then on both files must exist, every row in the sheet's
status table is MERGED or DROPPED, and no WAIT heading is left in the notes. The data layout is 24 (steps 21 to 24 came with 1.0.7).
"""
import ast
import os
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.7"
SCHEMA = 24              # 1.0.6 ended at layout 20; 1.0.7 took steps 21 to 24

# Filled with the rows merged so far; the cut bookkeeping adds the rest from the merged list.
# (item, the check a person would make by eye, the test that covers it: file::Class::test)
# The cut commit must fill COVERED, NO_VISIBLE_CHANGE and TEST_ONLY from the merged list BEFORE it sets the version to 1.0.7:
# once the version says 1.0.7 every MERGED row must be in one of them (see StatusTable).
COVERED = [
    ('836', 'Settings has a Quit card with one button, Quit clark, that says Stopping clark. You can close this window.',
     'test_quit_card::Card::test_one_click_quits_once_and_says_so'),
    ('999', 'Two projects with different brands each get their own colours in the web page, the Excel and Word files and the PDF; Generic stays plain.',
     'test_brand_isolation::Word::test_each_brand_colours_its_own_word_file_and_not_the_others'),
    ('1023', 'A brand cover picture shows faintly behind every page, and nothing is drawn without one.',
     'test_brand_backdrop::Backdrop::test_every_app_page_has_the_brand_picture_fixed_behind_it'),
    ('1057', 'In a work item peek the words box stays at the bottom while the peek scrolls.',
     'test_peek_sneak_anchor_1057::SneakAnchor::test_the_words_box_stays_at_the_bottom_of_the_peek_while_it_scrolls'),
    ('1059', 'Work items has no type or status buttons; the filter line does their job.',
     'test_no_type_pills::NoTypePills::test_the_app_page_has_no_type_or_status_pills_and_the_line_still_does_their_job'),
    ('1062', 'The ask clark panel no longer carries the billing sentence; the Asking card in Settings does.',
     'test_ask_panel::Panel::test_the_panel_no_longer_carries_the_billing_sentence'),
    ('1063', 'The profile circle menu has Export to Word but no Import from Word.',
     'test_word_screens::Export::test_the_menu_has_export_but_not_import_and_the_tooltip_is_unchanged'),
    ('1064', 'The top bar shows no project name and keeps the logo, with room before the top menu items.',
     'test_header_no_project_name::HeaderNoProjectName::test_the_bar_shows_no_project_name_and_keeps_the_logo'),
    ('1073', '+ New view makes a view at once, named View 1, View 2 and so on.',
     'test_filter_line_page::Line::test_row_1073_a_new_view_takes_the_next_free_view_number_and_the_menu_entry_makes_one_at_once_too'),
    ('1074', 'Each choice in the drop-down lists shows an icon beside the same words.',
     'test_menu_icons::Browser::test_status_and_priority_menus_show_the_icon_and_the_same_words'),
    ('1075', 'A message at the foot of the page goes after 5 seconds with a bar that shrinks, and Ctrl+Z still undoes after it.',
     'test_toast_five_seconds::ToastFiveSeconds::test_the_message_is_still_there_at_4_seconds_and_gone_by_6_and_the_bar_shrinks'),
    ('1076', 'The page opens in an ordinary Chrome window at clark.localhost, and the notes say the saved views start again once.',
     'test_launcher::Launch::test_the_address_is_clark_localhost_with_the_port_for_chrome_and_127_0_0_1_for_the_rest'),
    ('1082', 'Show history under Latest update lists the changes, five in view, and reads Hide history while open.',
     'test_peek_history_1082::Browser::test_five_in_view_the_rest_scroll_and_the_link_toggles'),
    ('1083', 'The Milestones list has a light line and space between milestones at 1400 and 900 px.',
     'test_milestones_spacing::Spacing::test_the_live_page_at_1400_and_900_light_and_dark'),
    ('1089', 'Help has The brand kit guide with what a kit holds, the limits and how to install one.',
     'test_help_guide_brand_kit::TheBrandKitGuide::test_it_says_what_a_kit_holds'),
    ('1106', 'The window that asks what to import opens with the sheets ticked last time ticked.',
     'test_import_remembers_sheets::StartSheets::test_only_the_sheets_ticked_last_time_are_ticked'),
    ('1108', 'The Use case summary shows the first 5 use cases, with Show all and Show the first 5.',
     'test_uc_summary_five::FirstFive::test_with_more_the_first_five_show_and_the_control_expands_and_reduces_while_the_count_stays'),
    ('1092', 'Settings is in the profile circle menu and the project menu lists only projects.',
     'test_profile_menu::ProfileMenu::test_C_the_menu_has_a_separator_before_settings_and_the_appearance_group_below_it'),
    ('1107', 'A use case page links the use case to a milestone with Link a milestone and Unlink takes it away, each with Undo.',
     'test_uc_milestones_change::Change::test_remove_keeps_the_row_and_undo_puts_the_link_back'),
    ('1109', 'When the folder window cannot open, a box to type the folder location appears with Add folder.',
     'test_ask_settings::Settings::test_when_no_window_can_open_a_box_to_type_the_location_appears'),
    ('1110', 'In an opened use case row each next step shows at most two lines and a click opens its peek.',
     'test_next_clamp_1110::NextClamp::test_a_long_step_is_two_lines_with_icon_and_id_beside_it_and_a_click_opens_the_peek'),
    ('1111', 'In a published file a use case opens its own read only page with its work items and milestones.',
     'test_publish_uc_page::TheFilesUseCasePage::test_a_client_opens_the_page_and_sees_it_read_only'),
    ('1112', 'In a published file a tile that counts work items opens the Work items page showing what it counts.',
     'test_glance_page::Published::test_row_1112_a_published_tile_opens_the_files_work_items_with_what_it_counts'),
    ('1114', 'In a published file a milestone row, mark or chip opens a read-only peek.',
     'test_publish_ms_open::PublishedMilestonesOpen::test_a_row_a_mark_and_a_chip_open_the_read_only_peek'),
    ('1021', 'Risks and issues, Open actions and Decisions show one line for each item with a small tinted letter square for the kind and the status colour.',
     'test_item_one_line::OneLineInView::test_one_line_a_tinted_letter_for_the_kind_and_a_colour_for_the_status'),
    ('1025', 'Spacing is one setting, Compact or Comfortable, and Comfortable is looser than Compact.',
     'test_spacing_settings_help::Browser::test_compact_is_what_the_page_had_and_comfortable_is_looser'),
    ('1060', 'In the Excel file a use case Where it stands holds its words in the cell, with no formatting codes.',
     'test_excel_plain_1060::ExcelPlainWords::test_each_rich_field_is_its_words_in_the_cell'),
    ('1061', 'The Commitment choice that said Candidate now says Planned 2026.',
     'test_store_planned_2026_migration::PlannedTwentySix::test_candidate_becomes_planned_2026_and_other_values_stay'),
    ('1065', 'A published file has no Weekly snapshot tab, and an old Weekly snapshot address opens the Dashboard.',
     'test_router::Pure::test_1065_the_retired_client_report_address_falls_back_to_the_dashboard'),
    ('1066', 'A published page shows no Needs from you section that the editor Dashboard does not have.',
     'test_published_matches_editor::Matches::test_a_flagged_item_does_not_add_a_needs_section_the_editor_does_not_have'),
    ('1068', 'A Table section can be added to the Dashboard and draws only the plan table, with one Undo.',
     'test_gantt_table_section::TheChangeRoute::test_a_table_section_is_added_with_one_undo_and_the_undo_takes_it_away'),
    ('1069', 'Settings has a Feedback card with a link in its list.',
     'test_feedback_tab::InSettings::test_settings_draws_the_card_and_a_link_for_it'),
    ('1070', 'Change owner in an item menu has a search box that finds people.',
     'test_row_menu::Menu::test_item_1070_change_owner_has_a_search_box_that_finds_people_on_the_register'),
    ('1071', 'A filter tab can be picked up and dragged left or right and the order is kept.',
     'test_filter_line_page::Line::test_row_1071_a_tab_is_picked_up_and_dragged_left_or_right_and_the_order_is_kept'),
    ('1072', 'Group by is one icon button the size of the List and Board icons.',
     'test_work_items_header::Header::test_row_1072_group_by_is_one_icon_button_the_size_of_table_and_board'),
    ('1077', 'The words box in a peek is headed Ask clark to update for you and there is no Draft chip.',
     'test_peek_ruled_1077::Source::test_the_words_box_is_headed_ask_clark_to_update_for_you'),
    ('1078', 'A milestone peek has the same rows and header line as a work item peek.',
     'test_milestone_peek_1078::Sources::test_the_editor_draws_the_rows_in_the_ruled_order_with_the_name_as_the_title'),
    ('1079', 'On a use case page a milestone can be added, with one Undo.',
     'test_use_case_detail::Detail::test_add_a_milestone_is_one_change_with_one_undo_row_1079'),
    ('1081', 'On a use case page the Work items card shows one line per item with one tinted status chip.',
     'test_use_case_detail::Detail::test_the_work_items_card_is_one_line_per_item_with_one_tinted_chip_row_1081'),
    ('1084', 'The List, Board and Group by icons follow the clear button and the tabs have the whole row.',
     'test_view_icons_filter_line::IconsOnTheLine::test_count_x_import_export_and_three_icons_share_the_line_without_overlap'),
    ('1085', 'The Use cases page has four tabs over a filter line, with counts that follow the line.',
     'test_use_cases_list::Narrowing::test_the_tabs_counts_follow_the_line_and_narrow_the_list'),
    ('1087', 'Published reports has an address of its own and no peek.',
     'test_router::Pure::test_row_1087_the_published_reports_page_has_its_own_address_and_no_peek'),
    ('1088', 'The Brands card takes a brand zip of any file name and the name inside the zip names the brand.',
     'test_brands_zip::Names::test_any_zip_file_name_is_accepted_and_the_manifest_names_the_brand'),
    ('1099', 'Half-width cards fit in View and in Edit, light and dark.',
     'test_half_cards_1099::HalfCards::test_half_width_cards_fit_in_view_and_edit_light_and_dark'),
    ('1100', 'Asking looks for Claude in the npm and nvm places.',
     'test_ask_claude::NpmAndNvmInstalls::test_the_npm_and_nvm_places_are_looked_in'),
    ('1104', 'A column width changes by dragging the right edge of its heading and is kept.',
     'test_col_widths::Widths::test_a_heading_edge_changes_the_width_and_it_is_kept'),
    ('831', 'The Data card in Settings has Export to Word and Import from Word buttons.',
     'test_data_card::DataCard::test_C_word_buttons_open_the_profile_menus_boxes_in_view'),
    ('951', 'The Data card has Excel file layout; it opens a box that says what the exported file holds and sends nothing.',
     'test_data_card::DataCard::test_C_excel_file_layout_opens_a_box_with_the_three_texts_and_sends_nothing'),
    ('658', 'Delete in a row menu and in the peek asks first, removes the item, and Undo at the foot of the page brings it back.',
     'test_row_delete::DeleteItem::test_cancel_does_nothing_delete_removes_the_row_and_undo_brings_it_back'),
    ('1094', 'While ask clark works, one line from a deck of 150 quips shows, and none comes round again until all have been shown.',
     'test_ask_quips::QuipDeck::test_150_quips_none_twice_each_with_an_ellipsis'),
    ('1095', 'New chat, History and Close in the ask clark panel are plain icon buttons, and History keeps the project\'s earlier chats.',
     'test_ask_icons::AskIcons::test_three_plain_icon_buttons_in_order_at_both_widths_and_themes'),
    ('1036', 'Export to Word: the milestone plan picture has the lane names and the dates along its axis.',
     'test_docx_graphics::Labels::test_a_named_lane_has_ink_in_its_own_band_of_the_name_column_and_an_unnamed_one_none'),
    ('1041', 'Press Quit clark while a save or publish runs: the card says clark is finishing it first and then stops.',
     'test_quit_card::Card::test_a_running_save_or_publish_is_said_instead_of_the_idle_line'),
    ('1040', 'Quit clark puts the keyboard focus on its question and gives it back on Cancel or Esc; Help names the key that opens ask clark.',
     'test_quit_card::Card::test_focus_follows_the_question_and_comes_back'),
    ('1030', 'Start clark twice: the message does not tell you to press Ctrl+C in a Terminal window, and clark\'s own check agrees with the launcher.',
     'test_launch_running::Running::test_row_1030_the_words_do_not_send_anyone_to_a_terminal_window'),
    ('1126', 'The backup box and the client folder messages say "data", and two page messages do not say "request".',
     'test_page_words::Words::test_the_page_words_say_data_not_database_and_that_not_request'),
    ('669', 'The At a glance tiles in the editor read the same as in the published file ("None high", "None open", "No date set", "None waiting").',
     'test_glance_tile_words::Page::test_risks'),
    ('1117', 'Under every tile, Edit says the words the published file says.',
     'test_glance_parity::SameWords::test_edit_says_the_words_the_file_says_under_every_tile'),
    ('1118', 'Set the Project health tile colour by hand: Edit and the published file show the same colour.',
     'test_glance_parity::SameWords::test_a_colour_set_by_hand_on_project_health_shows_the_same_in_edit_and_in_the_file'),
    ('936', 'In Edit, the draft email\'s internal note and the rich-text quote have no coloured stripe down one side.',
     'test_card_borders_936_sidetabs::Source::test_edit_css_quiets_the_two_stripes'),
    ('1113', 'The Work items section of a Dashboard takes the same filter line as the Work items page; a name that is gone matches nothing.',
     'test_tpl_workitems::Saved::test_an_owner_or_workstream_or_use_case_that_is_gone_matches_nothing_and_the_filter_stays'),
    ('1005', 'Client wording, picture captions, Movement words and the Own words of a risk use the same editor as other long text.',
     'test_one_editor_gate::MovedFields::test_the_row_and_peek_client_wording_have_no_plain_box_of_their_own'),
    ('1067', 'Work items has no Show archived; is:archived on the filter line lists archived items, read only, and Restore puts one back.',
     'test_work_archived_filter::ArchivedFilter::test_is_archived_lists_the_archived_items_read_only_and_clearing_brings_back_the_list'),
    ('1048', 'Draft email from a row menu fills To with the owner\'s address and name from People.',
     'test_row_menu::Menu::test_row_1048_the_owners_address_and_name_ride_on_the_ask_show_in_the_to_line_and_stay_on_a_changed_option_at_1400_and_900'),
    ('1058', 'On the filter line, choose a key: its values are listed at once.',
     'test_filter_line_page::Line::test_typing_offers_fields_then_values_with_arrows_and_enter_choose'),
    ('1054', 'Archive from a milestone peek: the focus goes to the next row or to Undo; menus and the filter box show a clear ring.',
     'test_milestone_peek_828::Fields::test_after_archive_in_the_peek_focus_goes_to_the_next_row_or_to_undo'),
    ('1093', 'On each page, the suggestions under the ask clark box are that page\'s, and the last question changes them.',
     'test_ask_look::Look::test_row_1093_the_suggestions_follow_the_page_and_the_last_question'),
    ('1096', 'The ask clark question box is one line, the suggestions hide while you type, and Ask is a round up arrow.',
     'test_ask_look::Look::test_the_box_is_one_line_the_suggestions_go_while_typing_and_the_send_is_a_round_arrow'),
    ('1128', 'A cancelled milestone says "No longer going ahead", and the head does not say "No milestones yet." over cancelled rows.',
     'test_ms_cancelled_page::Drawn::test_one_cancelled_milestone'),
    ('1026', 'Close the Gantt Show menu, the Gantt table right-click menu and the / list: each fades out.',
     'test_motion_menu_exit_four::Show::test_row_1026_1_the_gantt_show_menu_fades_out'),
    ('1026', 'The Gantt table right-click menu fades out.',
     'test_motion_menu_exit_four::Context::test_row_1026_2_the_gantt_table_right_click_menu_fades_out'),
    ('1026', 'The / list fades out.',
     'test_motion_menu_exit_four::Slash::test_row_1026_3_the_slash_insert_list_fades_out'),
    ('1027', 'Publish a Gantt whose owner or baseline date is also named in a section: it publishes.',
     'test_gantt_markers_bodies::OwnerAndDates::test_an_owner_that_a_section_body_also_names_publishes'),
    ('1037', 'A long label near the left edge of the Gantt starts inside the chart.',
     'test_gantt_chart::Chart::test_row_1037_a_long_label_near_the_left_edge_never_starts_left_of_the_chart'),
    ('1039', 'With Reduce motion on, the Today button on the Gantt jumps at once.',
     'test_motion_gantt_bars::Bars::test_today_button_jumps_at_once_under_reduced_motion_and_scrolls_smoothly_otherwise_row_1039'),
    ('1038', 'Print a long Gantt on A4: it is scaled to the page and the timeline is not cut at the right edge.',
     'test_gantt_print::Print::test_a_long_plan_is_scaled_to_the_page_and_nothing_is_cut'),
    ('1050', 'With the dark look on, print the Dashboard: it prints light and the look comes back.',
     'test_appearance::PrintLight::test_1050_printing_is_light_in_dark_and_the_look_comes_back'),
    ('1032', 'After Group by, Discard changes does not overlap New view at 1400 wide.',
     'test_work_items_header::Header::test_row_1032_discard_changes_does_not_overlap_new_view_after_group_by'),
    ('1120', 'In the new-person form of the owner picker, Tab moves between its fields and keeps the picker open.',
     'test_assign_new_person_live::NewPerson::test_row_1120_tab_in_the_form_moves_between_its_fields_and_keeps_the_picker'),
    ('1123', 'Drag a column heading on the Work board into the gap between two columns: it goes there.',
     'test_board_columns::Columns::test_dropping_a_heading_in_the_gap_between_columns_puts_it_there_not_at_the_end'),
    ('1034', 'The Dashboard does not scroll sideways at 1400 and 900 wide.',
     'test_row_1034_no_sideways::Dashboard::test_nothing_scrolls_sideways_at_1400_and_900'),
    ('1028', 'Import an Excel workbook with empty rows far down the sheet: it is read and not turned away.',
     'test_excel_empty_row::EmptyRow::test_an_empty_row_at_6000_does_not_refuse_the_workbook'),
    ('1035', 'Export to Word with a project health or use case status that is not plain text: the file builds.',
     'test_docx_build::HostileHealthAndStatus::test_a_health_or_use_case_status_that_is_not_text_builds'),
    ('1116', 'Open a published file with a very long unbroken name: no tab scrolls sideways.',
     'test_view_long_word::LongWord::test_no_tab_of_the_file_scrolls_sideways'),
    ('1119', 'Ask, leave the page while it thinks, come back: the answer is not in the next chat.',
     'test_ask_leave_page::LeavePage::test_an_answer_that_arrives_after_leaving_the_page_is_not_shown_in_the_next_chat'),
    ('1122', 'In Settings, Preview or Restore a backup: the restored message shows and the focus is kept.',
     'test_safety_logic::Card::test_the_restored_message_is_in_view_and_focused_after_the_reload'),
    ('1125', 'Double click Import, and its Undo: it happens once, shows no error and Undo stays.',
     'test_settings_data_page::Card::test_a_double_click_on_import_and_on_undo_applies_once_and_shows_no_error'),
    ('1044', 'At 900 wide the leftmost label of the Milestones strip is not clipped.',
     'test_milestones_dead_css::LeftLabel::test_the_left_most_label_starts_inside_the_strip'),
]

# The first sentence of each bullet, to find it by: {row id: start of its bullet}. Filled with COVERED.
BULLET_STARTS = {
    '836': 'Settings has a Quit card.',
    '999': 'Each project now uses its own brand in everything clark makes',
    '1023': "A brand's cover picture now shows faintly behind every page",
    '1057': "In a work item's peek, the box for your words stays at the bottom while the peek scrolls.",
    '1059': 'The type buttons (All, Actions, Risks and issues, Decisions) and the status buttons (Open, Closed, All) above the list are gone in the app.',
    '1062': 'The Asking card in Settings says where a question goes and which account pays for it.',
    '1063': "Import from Word is no longer in the profile circle's menu.",
    '1064': 'The top bar no longer shows the project name.',
    '1073': '"+ New view" makes a view at once, named View 1, View 2 and so on; you can rename it.',
    '1074': 'Each choice in a drop-down of the peek, the table cells and the milestone peek shows a small icon beside its words',
    '1075': 'A message at the foot of the page goes after 5 seconds',
    '1076': 'Now clark opens as a page in an ordinary Chrome window, at http://clark.localhost:8766/',
    '1082': 'In the peek of an action, "Show history" under Latest update lists the changes to that one field, newest first.',
    '1083': 'In the Milestones list, a light line and a little space separate each milestone from the next.',
    '1089': 'Help has a new guide, "The brand kit guide"',
    '1106': 'The window that asks what to import opens with the sheets you ticked last time',
    '1108': 'The Use case summary shows the first 5 use cases',
    '1092': "Settings is in the profile circle's menu again",
    '1107': "On a use case's page you can link the use case straight to a milestone",
    '1109': 'When the folder window cannot open, Choose folder says so',
    '1110': 'In an opened use case row, each next step shows at most two lines',
    '1111': 'In a published file, a use case opens its own page',
    '1112': 'In a published file, the At a glance tiles that count work items',
    '1114': "In a published file, a milestone's row, mark or chip opens a read-only peek.",
    '1021': 'Risks and issues, Open actions and Decisions show one line',
    '1025': 'Spacing is one setting for the whole app',
    '1060': 'In the Excel file, the Where it stands of a use case',
    '1061': 'The use case Commitment choice that said Candidate',
    '1065': 'A published file no longer has the Weekly snapshot tab.',
    '1066': 'A published page no longer shows a "Needs from you" section',
    '1068': 'A new Dashboard section, Table',
    '1069': 'Settings has a Feedback card:',
    '1070': 'Change owner in an item\'s menu has a search box',
    '1071': 'Filter tabs can be dragged left or right',
    '1072': 'Group by is now one icon button',
    '1077': 'The peek of a work item is flatter',
    '1078': 'The milestone peek has the same format',
    '1079': 'On a use case\'s page you can add and remove milestones',
    '1081': 'On a use case\'s page, the Work items card',
    '1084': 'The List, Board and Group by icons now follow',
    '1085': 'The Use cases page now follows the Work items page',
    '1087': 'Published reports is now a page of its own',
    '1088': 'The Brands card takes a brand zip of any file name',
    '1099': 'Half-width cards (Risks and issues, Open actions) now fit',
    '1100': 'Asking now finds Claude and Codex installed with npm or nvm',
    '1104': 'You can change a column\'s width by dragging',
    '831': 'The Data card in Settings has Export to Word and Import',
    '951': 'The Data card also has "Excel file layout". It opens a b',
    '658': 'A work item or a decision can be deleted from its "..."',
    '1094': 'While ask clark is working, it shows a line from a deck',
    '1095': 'In the ask clark panel, New chat, History and Close are',
    '1036': 'The milestone plan picture in the Word file has the lane',
    '1041': 'When a save or publish is running, the Quit card says cl',
    '1040': 'Quit clark moves the keyboard focus to its question, and',
    '1030': 'When clark is already running, the message no longer tel',
    '1126': 'Words on screen say "data" or "set of data" where they s',
    '669': 'The At a glance tiles in the editor say the same words a',
    '1117': 'Under every tile, Edit says the words the published file',
    '1118': 'A colour set by hand on the Project health tile now show',
    '936': 'In Edit, the draft email\'s internal note and the rich-te',
    '1113': 'The Work items section of a Dashboard takes the same fil',
    '1005': 'The Client wording, picture captions, Movement words and',
    '1067': 'Work items no longer has Show archived. Type is:archived',
    '1048': 'Draft email fills the To line with the owner\'s address a',
    '1058': 'On the filter line, choosing a key shows its values at o',
    '1054': 'After Archive in a milestone\'s peek, the keyboard focus',
    '1093': 'The suggestions under the ask clark box follow the page',
    '1096': 'The ask clark question box is one line high, the suggest',
    '1128': 'A Cancelled milestone says "No longer going ahead", and',
    '1026': 'Three more menus fade out when they close: the',
    '1027': 'A Gantt page whose owner or baseline date is also named',
    '1037': 'A long label near the left edge of the Gantt no longer s',
    '1039': 'The Today button on the Gantt jumps at once when Reduce',
    '1038': 'Printing a long Gantt on A4 scales it to the page, so th',
    '1050': 'Printing is always in the light look, even when the scre',
    '1032': 'Discard changes no longer overlaps New view after Group',
    '1120': 'In the new-person form of the owner picker, Tab moves be',
    '1123': 'A column heading dragged on the Work board into the gap',
    '1034': 'The Dashboard no longer scrolls sideways when the window',
    '1028': 'An Excel workbook with empty rows far down a sheet is no',
    '1035': 'The Word file builds when a project health or a use case',
    '1116': 'A long unbroken name in a published file no longer makes',
    '1119': 'An answer from ask clark that comes back after you leave',
    '1122': 'After Preview or Restore in the Backups card, the restor',
    '1125': 'A double click on Import, or on its Undo, now counts onc',
    '1044': 'The leftmost label of the Milestones strip no longer cli',
}

# Merged rows whose note is another row's bullet or was left out as untrue: covered, but no bullet of their own (1117 repeats 669).
NO_BULLET = {'1117'}
# Bullets for merged work that has no plan row in COVERED: the start of each (1245 in PR 1356; the launcher's synced-folder refusal in PR 1357).
EXTRA_BULLET_STARTS = ('A Completed item no longer reads as late.', 'The launcher now refuses a data folder inside Dropbox', 'In Docker, when the container shares the computer')

# Merged rows with no visible change.
NO_VISIBLE_CHANGE = {'1080', '1029', '1031', '1055'}   # 1055 changed only the old prototype's Help wording
# Merged rows that are tests or internal code only: no bullet, no hand check.
TEST_ONLY = {'1045', '1047'}
# No user note, and no hand check, once merged.
NO_NOTE_WHEN_MERGED = set()

# Rows with one part merged and the rest open: the merged part is covered, the row stays IN REVIEW in the table.
PARTLY_MERGED = set()

# Not on main yet: (item, check, pull request, a file under the top folder and the text that is in it once the pull request has landed).
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


def sheet_if_there():
    """The sheet's text in a list, or an empty list before the cut has written it."""
    path = ROOT / "dev" / "handchecks" / (VERSION + "-sheet.md")
    return [path.read_text(encoding="utf-8")] if path.is_file() else []


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


def bullets_are_final(found_version, env=None):
    """True from the cut on: once the version says 1.0.7 every merged row needs its bullet. V107_FINAL=1 asks for it earlier."""
    return found_version == VERSION or (os.environ.get("V107_FINAL") if env is None else env) == "1"


def bullet_problems(found, covered, final, extra=()):
    """What is wrong with the bullets: never a duplicate or a bullet for no merged row; with final, also a merged row without one."""
    out = []
    covered = set(covered) - NO_BULLET
    for item in sorted(covered):
        n = sum(1 for b in found if b.startswith("- " + BULLET_STARTS[item]))
        if n > 1 or (final and n == 0):
            out.append("%s has %d bullets, wanted %s" % (item, n, "one" if final else "at most one"))
    if covered:
        starts = [BULLET_STARTS[i] for i in covered] + list(extra)
        out += ["a bullet for no merged row: " + b[:40] for b in found if not any(b.startswith("- " + t) for t in starts)]
    if final and not found:
        out.append("the notes hold no bullet")
    return out


WAIT_HEAD = "## WAIT: bullets that go in only when the PR merges (delete this heading when they do)"


def wait_bullets(notes):
    """The bullet lines under the WAIT heading (not counted as notes until the heading is deleted)."""
    if WAIT_HEAD not in notes:
        return []
    return [l for l in notes.split(WAIT_HEAD, 1)[1].splitlines() if l.startswith("- ")]


class Tables(unittest.TestCase):
    """Reads the hand-check sheet, so it skips until the cut."""

    def setUp(self):
        if version() != VERSION:
            self.skipTest(f"the cut commit is not made yet (version is {version()}); it sets {VERSION}")

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
    """The status table of every 1.0.7 row, between its two markers in the sheet. Skips until the cut."""

    def setUp(self):
        if version() != VERSION:
            self.skipTest(f"the cut commit is not made yet (version is {version()}); it sets {VERSION}")

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
            self.assertTrue(item in NO_VISIBLE_CHANGE or item in TEST_ONLY or item in NO_NOTE_WHEN_MERGED or item in covered,
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

    def test_the_title_and_the_beta_line(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("This is the 1.0 build. It is still marked Beta: it works and is tested, but expect rough edges and changes between versions.", self.text)

    def test_the_headings_are_there_in_order(self):
        heads = [l for l in self.text.splitlines() if l.startswith("## ")]
        self.assertEqual(heads[:3], list(SECTIONS))
        self.assertEqual(heads[3], "## Known limits")

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_no_pull_request_number_row_id_or_branch_name_in_what_a_person_reads(self):
        self.assertNotRegex(self.text, r"(?i)\b(PR|pull request|row|issue)s? #?\d+")
        self.assertNotRegex(self.text, r"#\d+")
        self.assertNotRegex(self.text, r"(?i)\bsha[- ]?\d|\b[0-9a-f]{9,}\b")

    def test_a_date_in_the_notes_is_day_first_and_no_one_is_named(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")
        self.assertNotRegex(self.text, r"team-[a-z]+-\d+", "a branch name is in the notes")

    def test_there_is_no_draft_marker_in_the_notes_or_the_sheet(self):
        for text in (self.text, *sheet_if_there()):
            self.assertNotIn("DRAFT", text)

    def test_nobody_says_the_head(self):
        for text in (self.text, *sheet_if_there()):
            self.assertNotRegex(text, r"(?i)\bthe head\b")

    def test_a_bullet_is_only_for_a_merged_visible_row_and_none_waits(self):
        """A merged row may lack its bullet until the cut; from the cut (version 1.0.7, which this class runs at) exactly one for each is demanded."""
        covered = {i.lstrip("#") for i, _, _ in COVERED}
        self.assertEqual(wait_bullets(self.text), [], "no bullet waits at the cut")
        self.assertNotRegex(self.text, r"(?m)^- Issue \d+ ", "no authoring tag is left in a bullet")
        self.assertEqual(bullet_problems(bullets(self.text), covered, bullets_are_final(version()), EXTRA_BULLET_STARTS), [])

    def test_the_notes_hold_no_status_table_and_no_row_ids(self):
        self.assertNotIn(BEGIN, self.text)
        self.assertNotRegex(self.text, r"(?m)^\| ")


class BulletsFinalCheck(unittest.TestCase):
    """Self-test of the cut-time check: a merged row without a bullet fails with V107_FINAL=1 and passes without it."""

    ROWS = {"1", "2"}

    def setUp(self):
        self._saved = dict(BULLET_STARTS)
        BULLET_STARTS.update({"1": "Alpha ", "2": "Beta "})

    def tearDown(self):
        BULLET_STARTS.clear()
        BULLET_STARTS.update(self._saved)

    def test_a_missing_bullet_fails_only_when_final(self):
        found = ["- Alpha one"]
        self.assertEqual(bullet_problems(found, self.ROWS, False), [])
        self.assertTrue(bullet_problems(found, self.ROWS, True))

    def test_every_bullet_there_passes_when_final(self):
        self.assertEqual(bullet_problems(["- Alpha one", "- Beta two"], self.ROWS, True), [])

    def test_a_duplicate_or_stray_bullet_fails_either_way(self):
        self.assertTrue(bullet_problems(["- Alpha one", "- Alpha again"], self.ROWS, False))
        self.assertTrue(bullet_problems(["- Alpha one", "- Gamma"], self.ROWS, False))

    def test_the_check_switches_on_by_itself_at_the_cut(self):
        self.assertTrue(bullets_are_final(VERSION, env=""), "version 1.0.7 demands every bullet, with no env set")
        self.assertFalse(bullets_are_final("1.0.6", env=""), "before the cut a missing bullet is tolerated")
        self.assertTrue(bullets_are_final("1.0.6", env="1"), "V107_FINAL=1 asks for it early")

    def test_dropping_a_bullet_fails_in_the_cut_state(self):
        found = ["- Alpha one"]                      # Beta's bullet dropped
        self.assertTrue(bullet_problems(found, self.ROWS, bullets_are_final(VERSION, env="")))
        self.assertEqual(bullet_problems(found, self.ROWS, bullets_are_final("1.0.6", env="")), [])


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 1.0.3 and earlier have their own test_vNNN; this file skips them
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
        self.assertEqual(schema_version(), SCHEMA, "1.0.7 ends at layout 24")

    def test_a_waiting_row_whose_pull_request_has_landed_has_been_moved_to_covered(self):
        self.cut_made()
        out = [f"{item} {pr}: it is in main now; give it a covering test in COVERED, a line in the notes and a row in the sheet"
               for item, check, pr, path, marker in WAITING if landed(path, marker)]
        self.assertEqual(out, [])

    def test_at_the_cut_every_row_is_merged_or_dropped(self):
        """Fails from the cut until each row has merged (or been dropped and taken out of the notes)."""
        self.cut_made()
        out = [f"{item} is {status}" for item, title, status, pr in table_rows(read_sheet()) if status not in ("MERGED", "DROPPED")]
        self.assertEqual(out, [])

    def test_at_the_cut_the_wait_heading_is_gone(self):
        self.cut_made()
        self.assertNotIn(WAIT_HEAD, read_notes(), "delete the WAIT heading and move its bullets under What is new, changed or fixed")

    def test_at_the_cut_the_notes_and_the_sheet_exist_and_the_placeholder_is_gone(self):
        self.cut_made()
        self.assertNotIn("MANUAL DOWNLOAD LINE", read_notes(), "the placeholder must be gone")


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

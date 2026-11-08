"""clark 1.0.6's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.6 row.

Run: python3 dev/run_tests.py test_v106

Same shape as test_v105. COVERED, WAITING and TEST_ONLY start empty: rows are filled by the cut bookkeeping from the merged list.
The notes' own rules run now against dev/release-notes/1.0.6-plain.md. Everything that reads the hand-check sheet, and the cut
tests, skip until the cut commit sets 1.0.6 in src/clark/__init__.py; from then on both files must exist, every row in the sheet's
status table is MERGED or DROPPED, and no WAIT heading is left in the notes. The data layout stays at 20.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.6"
SCHEMA = 20              # 1.0.5 ended at layout 20 (projects.brand); 1.0.6 stays at 20

# Rows are filled by the cut bookkeeping from the merged list.
# (item, the check a person would make by eye, the test that covers it: file::Class::test)
# The cut commit must fill COVERED, NO_VISIBLE_CHANGE and TEST_ONLY from the merged list BEFORE it sets the version to 1.0.6:
# once the version says 1.0.6 every MERGED row must be in one of them (see StatusTable).
COVERED = [
    ('406', 'The note that part of your report looks like a password or a key reads the same in every place.',
     'test_wording_small_fixes::SecretRefusal::test_the_three_notes_share_one_phrase_and_one_next_step'),
    ('465', "Print tab shows the published file's bytes, not a second build",
     'test_preview_export_route::Preview::test_the_print_tab_shows_the_bytes_that_were_published_even_if_the_project_changes_after'),
    ('471', 'A report line like token: or api_key: with a quoted word is left out when clark reads your folder.',
     'test_secret_screen::Screen::test_a_prefixed_or_suffixed_key_word_with_a_quoted_letters_value_is_refused'),
    ('479', 'Your old data is put back when the update could not move it, and a stuck new clark is stopped and cleared away',
     'test_update_rollback_data::RestoredTest::test_a_failed_start_that_did_not_migrate_but_changed_the_data_is_put_back_byte_for_byte'),
    ('480', 'If a publish fails after a link was replaced, the old link is back.',
     'test_publication_numbers::ThroughThePublisher::test_a_lost_race_in_the_dialog_puts_back_a_link_it_replaced'),
    ('483', 'A bad sent date says to reload the page and that nothing was saved.',
     'test_draft_email::Dates::test_the_sent_record_takes_only_a_stored_day'),
    ('484', 'I sent it: the no-answer line says it may or may not have been recorded',
     'test_email_sent_refusal::Shown::test_no_answer_says_it_may_or_may_not_be_recorded_and_where_to_look'),
    ('503', 'A 25 to 31 character mixed run of letters and digits is left out when clark reads your folder.',
     'test_secret_screen::Screen::test_a_single_unseparated_mixed_run_is_refused_by_design'),
    ('512', 'The Docker starter stops and names the service when the data folder is in OneDrive, Dropbox, iCloud Drive or Google Drive.',
     'test_starter_synced::Decision::test_synced_folders_are_refused_with_the_service_named'),
    ('514', 'Help section headings read each smaller than the page title.',
     'test_size_scale::Scale::test_headings_sit_on_the_heading_sizes'),
    ('515', 'Help says a number is never used again and Undo does not take it back.',
     'test_help_content::PublicationNumberWords::test_help_says_a_publication_number_is_never_reused_and_undo_does_not_take_it_back'),
    ('519', 'A changed section dragged over keeps its glow and shows its drop line.',
     'test_motion::Rules::test_a_drag_over_a_changed_section_keeps_its_glow_and_gets_its_drop_line'),
    ('521', 'The archived milestone peek shows Not set beside Workstream when it is empty.',
     'test_milestones_archived::Archived::test_the_name_opens_the_milestone_read_only_in_the_peek_with_restore_there'),
    ('523', 'Resetting a column width from the keyboard announces Column width reset, as the mouse does.',
     'test_work_board_page::Moves::test_the_move_to_menu_works_as_the_page_opens_with_a_toast_and_undo'),
    ('532', 'A closed risk or issue never rated reads Closed with Not rated beside it on one line, also at 420 px.',
     'test_peek::ClosedUnratedRiskPeek::test_a_closed_unrated_risk_says_not_rated_in_the_published_peek'),
    ('535', 'Clearing the Week ending box shows a line saying the old week ending date was kept.',
     'test_report_bar::Bar::test_a_cleared_field_keeps_the_old_date'),
    ('537', 'An organisation or role over 100 characters is refused with a plain line and nothing changes.',
     'test_people_route::Writers::test_an_organisation_or_role_over_100_characters_is_refused_and_changes_nothing'),
    ('538', 'After a people paste the card says N people added or updated.',
     'test_people_card::PeopleCard::test_paste_from_excel_previews_adds_in_one_step_and_one_undo_takes_it_back'),
    ('539', 'On a use case there is an even gap between Link an existing work item and See all.',
     'test_uc_dashboard_edit::Edit::test_link_button_and_see_all_do_not_run_together'),
    ('544', 'The Claude tile reads Through your Claude subscription, on this computer.',
     'test_ai_connect_page::Card::test_connected_shows_both_tiles_and_the_model'),
    ('549', 'After pressing Draft in Latest update the cursor stays in the box and typing goes into the drafted text.',
     'test_peek_latest::Browser::test_a_real_click_on_draft_with_the_box_open_keeps_the_caret_in_the_editor'),
    ('555', 'The calendar shows the line No milestones in this period at laptop widths.',
     'test_milestones_page::RealBrowser::test_the_empty_period_line_is_seen_at_laptop_widths_not_only_on_a_phone'),
    ('556', 'The PDF check lets through only the footer words Publication, Published and Page.',
     'test_pdf::TheSecondReview::test_extra_words_are_found_and_the_footer_and_headings_are_allowed'),
    ('560', 'A client-visible row with no client wording publishes its title only',
     'test_latest_update_publish::LatestUpdatePublished::test_a_client_message_of_only_invisible_characters_is_no_client_wording'),
    ('571', 'I sent it for an item kept out of emails shows the plain refusal line.',
     'test_email_sent_refusal::KeptOutWording::test_a_keep_quiet_item_is_refused_without_the_word_sensitive'),
    ('573', 'The archived project sentence in the Draft email and the I sent it refusal is the same one.',
     'test_archived_email_sentence::ArchivedEmailSentence::test_one_shared_sentence'),
    ('598', 'A key that starts with sk-, pk- or rk-, in any letter case, is left out when clark reads your folder',
     'test_secret_screen::Screen::test_uppercase_sk_and_pk_rk_keys_are_refused_and_near_misses_pass'),
    ('600', 'The Activity tab and Undo several give the same reason for an undone step',
     'test_activity_refusals::Refusals::test_the_reason_is_the_one_undo_several_gives_for_an_undo_and_a_flagged_step'),
    ('603', 'A Hold that pushes the oldest lines out of the note says so and Undo restores them.',
     'test_changes_milestones::TheHold::test_a_hold_that_drops_lines_says_so_in_its_reply_and_one_undo_restores_the_whole_note'),
    ('619', 'Pasting left-out words inside a row that stays in stops the publish with Nothing was published.',
     'test_word_client_held_back::NoteWithWhitespace::test_each_variant_is_refused_by_the_web_publish_and_the_word_client_copy'),
    ('699', 'Hide a section that fills the screen on the Dashboard, then switch Edit to View: the page does not jump.',
     'test_mode_switch_no_shift::NoShift::test_the_nearest_section_does_not_move'),
    ('721', 'Help no longer names keys the page does not have',
     'test_help_parity::KeyRowsSayWhatTheKeysDo::test_alt_slash_is_not_a_key_the_page_binds'),
    ('807', 'Click a row in a Work items list and see no check mark on it.',
     'test_work_items_header::Header::test_row_807_a_selected_card_and_a_selected_list_row_have_no_check_mark_but_still_show_it_is_selected'),
    ('833', 'Under the filter line the hidden examples row takes no room.',
     'test_work_items_header::Header::test_row_833_the_hidden_examples_row_takes_no_room'),
    ('842', 'At 900 px and wider the links to the Settings cards are a list down the left.',
     'test_settings_head::Head::test_C_the_list_is_at_the_left_at_900_and_wider_and_a_row_of_chips_below_900'),
    ('844', 'Switch between the Work items views and the view you chose stays chosen.',
     'test_work_items_header::Header::test_row_844_a_changed_view_keeps_its_tab_with_a_dot_and_save_view_and_discard_changes_act_on_it'),
    ('845', 'Accepted filters show as chips, each with its own remove button.',
     'test_work_items_header::Header::test_row_845_accepted_filters_are_chips_each_with_its_own_remove_button'),
    ('846', 'Open the value list of a filter field and each value shows its count.',
     'test_work_items_header::Header::test_row_846_each_suggested_value_shows_how_many_items_it_leaves_and_an_unknown_field_lists_the_valid_ones'),
    ('852', 'Settings has a Local folder box with Choose folder that shows the folder in plain words.',
     'test_local_folder::Choosing::test_a_chosen_folder_is_saved_once_with_an_undo'),
    ('867', 'Press Archive on a milestone peek and the milestone is archived with a toast and Undo.',
     'test_milestone_peek_828::Fields::test_archive_in_the_milestone_peek_hides_it_closes_the_peek_and_one_undo_brings_it_back'),
    ('916', "A client wording card with no wording publishes the item's title",
     'test_tpl_raid3::Items::test_a_client_card_with_no_wording_publishes_the_items_title_and_never_other_fields'),
    ('931', 'W.4: Work items: click in the filter box, then press Space -> The list of fields opens only after Space (or Arrow Down), with an icon on each field; Esc closes it.',
     'test_filter_line_page::Line::test_the_list_opens_after_space_or_arrow_down_and_closes_on_a_choice_or_escape_row_931'),
    ('936', 'C.1 (hover a card; Help note: quieter hover tint, thin line round the note) and C.2 (Quote and Link preview: no brand-blue bar)',
     'test_card_borders_936_notes::Notes::test_edit_pages_notes_have_no_side_stripe'),
    ('944', 'B.1: Brands: install a brand zip from the sample folder, replace it, remove it, Undo -> Each step works; Remove asks you to confirm first.',
     'test_brands_install::RemoveAndUndo::test_undo_a_replace_puts_back_the_old_files'),
    ('946', 'Dark contrast and keyboard focus ring sweeps',
     'test_dark_contrast::SectionControlAtRest::test_in_dark_at_900_px_the_icon_reads_at_text_level_contrast'),
    ('950', 'S.1: Settings: open it -> The Profile card is the first card, holding Your name, Alias and Your email.',
     'test_about_you_path::AboutYouPath::test_the_old_path_through_personal_is_written_nowhere_in_src'),
    ('962', 'M.3 Edit: open a picker or menu and close it | It fades out as it closes; with reduced motion on it goes at once.',
     'test_motion_menu_exit_edit::Live::test_row_962_1_a_cell_picker_fades_out'),
    ('976', "Open Settings from the profile circle's menu: Settings is not a tab in the top bar.",
     'test_top_bar_tabs::TopBarTabs::test_the_tab_row_is_usable_on_the_settings_route_at_420_and_360_px'),
    ('977', 'W.1 Work items: right-click a row | The menu has an icon for each choice, evenly spaced; the entry words are not bold. (shared with row 978)',
     'test_row_menu::Menu::test_item_977_the_entry_words_are_plain_not_the_browsers_bold_in_the_menu_and_in_the_list_beside_it'),
    ('978', 'W.1 Work items: right-click a row | The menu has an icon for each choice, evenly spaced; the entry words are not bold.',
     'test_row_menu::Menu::test_row_978_every_entry_has_an_icon_from_the_existing_set_before_its_words_16px_muted_and_taking_the_entry_colour_on_hover'),
    ('979', 'Work items right-click menu jumps around less',
     'test_row_menu::Menu::test_row_979_a_mouse_open_shows_no_ring_on_the_first_entry_even_after_a_key_was_pressed_and_a_key_brings_it_back'),
    ('981', 'D.2 Draft email: with a short email that has a To address, read the button that hands it on | It says "Open in your mail app" and opens the draft. The To field stays empty (a known gap, planned for v1.0.7).',
     'test_draft_email_editor::Component::test_the_mail_button_says_it_opens_your_mail_app'),
    ('983', 'I sent it keeps what the email was about and writes a fuller line in the history',
     'test_sent_note::Note::test_the_sentence_has_the_name_the_day_and_the_subject'),
    ('985', 'A.3 Assign to: type part of a name | The list narrows as you type and the match is easy to see.',
     'test_assign_recent_live::Picker::test_typing_searches_the_register_by_name_alias_email_and_role_and_the_projects_names'),
    ('986', 'A.2 Assign to: type a name that is not in the list (1400 and 900 px) | Two buttons: "Add <the name you typed> as a new person" and "Keep the name only". The first asks for a name and an optional email; Enter saves and assigns in one step, and one Undo takes the person back too. A name already on the list offers "Use this one".',
     'test_assign_new_person_live::NewPerson::test_form_enter_adds_and_assigns_in_one_step_with_one_undo'),
    ('987', 'Help says how Assign to works',
     'test_help_assign_to::AssignToHelp::test_help_says_each_way_to_assign'),
    ('988', 'G.1: Gantt: look at the header row of a project with many lines (1400 and 900 px)',
     'test_gantt_chart::Chart::test_row_988_the_header_row_stays_in_view_with_many_lines'),
    ('989', 'G.2: Gantt: give an item a long label',
     'test_gantt_chart::Chart::test_a_long_bar_label_ellipsises_and_a_short_one_does_not'),
    ('990', 'G.4: Gantt: Print (or print preview)',
     'test_gantt_print::Print::test_the_printed_chart_and_table_have_no_controls_and_fit_the_page_at_a4_both_ways'),
    ('992', 'Tracker words: Escape puts the old words back',
     'test_tracker_page::Page::test_escape_puts_the_old_words_back_even_when_the_field_is_focused_before_any_frame'),
    ('995', 'G.5: Gantt: turn reduced motion on, then off again, and look (1400 and 900 px) (shared with 1000; the 900 px part is this row)',
     'test_gantt_chart::Chart::test_today_flag_is_read_in_full_when_today_is_at_the_start_of_the_plan'),
    ('997', 'R.6: Report: look at the header band with a brand that has a cover picture (shared with 1003)',
     'test_cover_band::Corners::test_the_band_is_rounded_all_round_with_a_shadow_when_the_sections_are_separate'),
    ('1000', 'G.5: Gantt: turn reduced motion on, then off again, and look (1400 and 900 px) (shared with 995)',
     'test_motion_gantt_bars::Bars::test_drawn_under_reduced_motion_then_switched_off_nothing_grows_row_1000'),
    ('1003', 'R.6: Report: look at the header band with a brand that has a cover picture (shared with 997)',
     'test_cover_band::Picture::test_the_brand_picture_fills_the_band'),
    ('1004', 'Use cases: Next steps shows only the linked work item id',
     'test_glance_page::Published::test_published_next_steps_show_only_the_id_link'),
    ('1005', 'P.1 Peek: open a work item and press `/` in the editor | One editor, with the `/` menu, the same in every place you write.',
     'test_one_editor_gate::MovedFields::test_each_moved_field_draws_the_one_editor_and_no_textarea'),
    ('1009', "P.2 Source line names where the item came from; P.3 Activity 'Updated from <file>, <date>, by <name>'",
     'test_source_line::TheLine::test_an_import_line_keeps_its_words_and_adds_by'),
    ('1010', 'U.2 Use cases: look at the eye on a use case row | One button reads "On the dashboard" or "Not on the dashboard", with an eye icon.',
     'test_use_case_detail::Detail::test_the_eye_is_one_button_with_its_words_and_toggles_with_one_undo'),
    ('1012', 'R.1 milestone plan picture; R.2 Health and progress bars as pictures; R.3 Gantt tab as a picture',
     'test_docx_graphics::ProgressAndHealth::test_the_health_segment_of_the_projects_colour_is_filled'),
    ('1013', 'W.5 Work items: look at the Actions cells at rest | They are plain text, not boxed; they are still editable.',
     'test_inline_edits::Live::test_priority_by_click_and_by_keyboard_one_step_with_undo_and_esc_leaves_it'),
    ('1015', 'P.4: Peek: look at the peek bar and a use case page, then type // in the editor -> No star in either place; // opens the words box.',
     'test_peek::PlainLabels::test_there_is_no_sparkle_button_but_the_words_box_stays'),
    ('1016', 'Peek: tighter vertical spacing of the top section',
     'test_peek_spacing_1016::Spacing::test_the_top_section_is_tighter_and_not_cramped'),
    ('1019', 'S.4: Dashboard: scroll halfway down, open another page of the same project, then click back (also use Back) -> returns to the same place, not the top.',
     'test_router::BuiltPage::test_item_1019_the_dashboard_keeps_its_place_across_a_tab_and_back'),
    ('1020', 'Milestones tighter: one label line per milestone, Hide milestone details and Legend on one row',
     'test_milestones_tight::Both::test_the_live_page_at_1400_900_and_420_light_and_dark'),
    ('1022', 'Ids, dates and owners never wrap in the item rows and the RAID cards; only the title is cut',
     'test_row_ids_no_wrap::RowIds::test_the_served_page_in_view_and_in_edit'),
    ('1136', 'H.3: Use cases list, Settings project list, Edit use case row (1400 and 900 px) -> No sideways scroll',
     'test_phone_widths_lists::PhoneLists::test_the_three_lists_do_not_scroll_sideways_at_360_and_420'),
    ('1145', 'M.5: Milestones: Print (or print preview) in light and in dark -> Legend help button is not printed',
     'test_pdf_print::Source::test_the_hover_only_legend_button_is_not_printed'),
    ('1148', 'M.6: Milestones: with reduced motion on, press Earlier, Later and Today -> timeline moves at once, without sliding',
     'test_reduce_motion_sweep_c11::Scroll::test_to_today_asks_reduced'),
    ('1149', 'H.4: People table, edit rows, Settings chips and profile menu (1400 and 900 px) -> No sideways scroll; chips and menu rows are 44 px high',
     'test_phone_tap_c7::PhoneWidth::test_people_table_does_not_run_past_the_window'),
    ('1197', 'Word report: a priority or status saved in an odd form shows Not rated',
     'test_docx_build::HostileValues::test_a_priority_that_is_not_text_is_not_rated_on_a_linked_risk'),
    ('1213', 'The On this page list stays centred and inside the window when Reduce motion is on',
     'test_inline_67::Minimap::test_it_fits_a_short_window_with_reduced_motion_at_1400_and_900'),
]

# The first sentence of each bullet, to find it by: {row id: start of its bullet}. Filled with COVERED.
BULLET_STARTS = {
    '406': 'The note that part of your report looks like a password or a key says the same thing everywhere',
    '465': 'The PDF print tab shows the very file that was just published, not a second copy built afterwards.',
    '471': 'A line such as token: or api_key: followed by a quoted word is now left out when clark reads your folder, like a password.',
    '479': 'If an update could not move your data to the new clark',
    '480': 'If a publish fails after a link was replaced, the link is put back.',
    '483': 'A bad sent date now says: "The day the email was sent must be a real date. Reload the page and try again. Nothing was saved."',
    '484': 'When "I sent it" gets no answer, the line says the press may or may not be saved to the history, and to look in the history before you press I sent it again.',
    '503': 'A long random-looking run of 25 to 31 letters and digits is now left out when clark reads your folder, like a longer one.',
    '512': 'The Docker starter checks the data folder is not in OneDrive, Dropbox, iCloud Drive or Google Drive, then starts.',
    '514': 'Headings in Help now step down in size: the page title is the largest, then the opening heading, then each section heading.',
    '515': 'Help says: "A number is never used again, and **Undo** does not take it back."',
    '519': 'A changed section that you drag over keeps its glow and shows where it will drop.',
    '521': 'An empty Workstream in the archived peek says "Not set".',
    '523': 'Resetting a column width from the keyboard says "Column width reset", as the mouse does.',
    '532': 'A closed risk or issue that was never rated now reads "Closed · Not rated" on one line, also on a phone-width window.',
    '535': 'Clearing the Week ending box says: "Week ending cannot be left empty. The old week ending date was kept."',
    '537': 'An organisation or role longer than 100 characters is not accepted: "the organisation is too long (at most 100 characters). Shorten it and try again. Nothing was changed."',
    '538': 'A done people paste says "N people added or updated".',
    '539': 'On a use case, the gap between "Link an existing work item" and "See all" is even.',
    '544': 'The Claude tile says "Through your Claude subscription, on this computer."',
    '549': 'Pressing Draft in Latest update keeps your cursor in the box, and what you type next goes into the drafted text.',
    '555': 'The calendar\'s "No milestones in this period" line shows at laptop widths.',
    '556': "The publish check on the PDF now lets through only the footer's own words (Publication, Published, Page); every other word must be in the report.",
    '560': 'A row shown to the client but left without client wording now publishes only its title, in the web page and in the Word copy; its Latest update and Description stay out.',
    '571': '"I sent it" for an item kept out of emails says: "One of the ticked items can\'t be recorded: it is hidden, closed or labelled to be kept out of emails. Nothing was saved. Reload the page and tick again."',
    '573': 'The Draft email says the same words for an archived project wherever it shows that sentence.',
    '598': 'A key that starts with sk-, pk- or rk-',
    '600': 'An undone step that belongs to another project reads "This change can\'t be undone from here" on the Activity tab.',
    '603': 'When a Hold pushes the oldest lines out of the note, it says so: "Hold recorded. The oldest lines of the note were removed to fit. Undo."',
    '619': 'If words from a row you left out of the report, from a hidden section, from a left-out document title or from a left-out Gantt line appear inside another row that stays in, publishing stops and says "Nothing was published. The report has something in it that must not go to the client", followed by what was found. The Word copy for the client stops the same way. A left-out text that is exactly the whole of another value still publishes.',
    '699': 'Hiding a section that fills the screen on the Dashboard, then switching from Edit to View, no longer makes the page jump.',
    '721': 'Help no longer names keys the page does not have.',
    '807': 'A row you click in a Work items list no longer shows a check mark.',
    '833': 'The examples row under the filter line no longer makes the area taller.',
    '842': 'At 900 px and wider the links to the Settings cards are a list down the left.',
    '844': 'Switching between the Work items views keeps the view you chose.',
    '845': 'Filters you accept in the filter box now show as chips, each with its own remove button.',
    '846': 'The list of values for a filter field now shows how many items each value leaves.',
    '852': 'Local folder: Publishing in Settings has a Local folder box with Choose folder, saved once.',
    '867': 'Archive is on the milestone peek too, with the same toast and Undo as a work item.',
    '916': 'A client wording card with no wording of its own',
    '931': 'In the filter box, Backspace or Delete beside a half-typed word',
    '936': 'In Edit, the Quote and Link preview no longer have a blue bar down the left side.',
    '944': 'Brands: a new Settings page.',
    '946': 'In dark, buttons, icons and the keyboard focus ring are easier to see.',
    '950': 'Profile is the first card in Settings.',
    '962': 'Pickers and menus fade out when they close',
    '976': 'Settings is no longer a tab in the top bar.',
    '977': 'The words of the right-click menu entries are no longer bold.',
    '978': 'The right-click menu has an icon on each entry.',
    '979': 'In the right-click menu, a list (status, due, owner) opens only when the pointer rests on its entry, so moving across the entries no longer flashes lists open.',
    '981': 'The Draft email button is called',
    '983': 'When you press I sent it, the history now says who was emailed',
    '985': 'The Assign to picker opens on Recent and People.',
    '986': 'If the name you type is not on the list',
    '987': 'Help now explains how Assign to works.',
    '988': 'The Gantt header row stays in view when there are many lines.',
    '989': 'A long label is shortened with "…" instead of running into the next one',
    '990': 'Print gives the Gantt as it is shown on the screen.',
    '992': "In the box for a project's progress words, pressing Escape puts the old words back, also when you click into the box straight away.",
    '995': 'Headings and the Today flag are no longer cut off at 900 px wide.',
    '997': "With separate section cards, the report's top band has rounded corners and the card shadow, so it stands alone like the cards under it.",
    '1000': 'Turning reduced motion off no longer makes every bar grow again.',
    '1003': "When a brand has a cover picture, the report's top band fills with it, faded in from the left edge and clear on the right.",
    '1004': 'Next steps in a Use cases row show only the number of the linked work item.',
    '1005': 'One editor is used everywhere you write:',
    '1009': 'The Details tab of the peek shows a Source line.',
    '1010': 'On a use case, the eye and its words are now one button:',
    '1012': 'A Word report carries the milestone plan',
    '1013': 'Owner, Due, Priority and Status in the Actions table read as plain words;',
    '1015': 'The star ("Change an item with words") is gone from the peek bar',
    '1016': 'The top of the peek is tighter',
    '1019': 'The Dashboard remembers where you were',
    '1020': 'The Milestones timeline is about half as tall: each milestone has one label line, the late text is shortened to "+13 days" and the date stays in the detail list.',
    '1022': 'In the item rows and the RAID cards, ids, dates and owners never wrap; only the title is cut, with an ellipsis.',
    '1136': 'On a phone, the Use cases list, the project buttons in Settings and the Edit use case row fit the window with no sideways scroll.',
    '1145': 'The Legend help button is no longer printed on the Milestones timeline.',
    '1148': 'When your computer asks for less motion, the Earlier, Later and Today buttons on the milestone timeline jump instead of scrolling smoothly, and the contents card, the Legend pop-up and the tab underli',
    '1149': 'At phone width the People table and the edit rows fit the window',
    '1197': 'A priority or status saved in an odd form no longer breaks the Word report',
    '1213': 'The On this page list at the right edge now stays centred and inside the window when Reduce motion is on; before, it could hang off the bottom of a short window.',
}

# Merged rows with no visible change.
NO_VISIBLE_CHANGE = {'517', '520', '522', '528', '547', '550', '561', '567', '577', '587', '919', '943', '960'}
# Merged rows that are tests or internal code only: no bullet, no hand check.
TEST_ONLY = {'233', '315', '468', '470', '497', '518', '543', '576', '578', '599', '924', '1006', '1007', '1008'}
# No user note, and no hand check, once merged.
NO_NOTE_WHEN_MERGED = {'469', '998', '1014'}

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
    """The status table of every 1.0.6 row, between its two markers in the sheet. Skips until the cut."""

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
        found = bullets(self.text)
        covered = {i.lstrip("#") for i, _, _ in COVERED}
        self.assertEqual(wait_bullets(self.text), [], "no bullet waits at the cut")
        self.assertTrue(found, "the notes hold no bullet")
        self.assertNotRegex(self.text, r"(?m)^- Issue \d+ ", "no authoring tag is left in a bullet")
        if covered:         # once the bookkeeping has filled COVERED: one bullet for each covered row
            self.assertEqual(len(found), len(covered), "one bullet for each merged visible row, and no other")
            for item in covered:
                self.assertEqual(sum(1 for b in found if b.startswith("- " + BULLET_STARTS[item])), 1, "%s has one bullet" % item)

    def test_the_notes_hold_no_status_table_and_no_row_ids(self):
        self.assertNotIn(BEGIN, self.text)
        self.assertNotRegex(self.text, r"(?m)^\| ")


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
        self.assertEqual(schema_version(), SCHEMA, "1.0.6 stays at layout 20")

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

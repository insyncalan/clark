# Row 1622 AP2/AP5: marks for the 93 lines of the row body's per-file list

Counts: 52 no-op / 29 requestAnimationFrame / 12 unsure = 93 marks, one per file:line of the body list.
Sources: the row body's per-file list (origin/main 2d33e3a26); current lines read on origin/main 70fc1fbf2. The "body" column is the key (file:line at 2d33e3a26). The "now" column is the same line text found on 70fc1fbf2; "moved/not found" means the text is not in the file now (no guess).
js() awaits since 6762c23b0 (tests/test_server.py:1642-1644, awaitPromise True), so every no-op line waits now. 10 of the rAF lines are two-frame promise lines: no-ops in effect, they wait two frames now.

New since the list, not counted, not checked (found by the same grep on 70fc1fbf2, not in the body list):
- tests/test_rich_focus_guard_1556.py:38 (a two-frame promise line)
- tests/test_js_await_1622.py:4 and :27 (the row's own new test)
- tests/test_server.py:1659 (docstring)
Not checked: multi-line js( calls, other helpers, whether each line runs in a suite.

| body file:line | now | section | verdict |
|---|---|---|---|
| tests/_tpl_notes.py:241 | tests/_tpl_notes.py:241 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_ask_grip_reset_1292.py:88 | tests/test_ask_grip_reset_1292.py:88 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_bell_1046.py:49 | tests/test_bell_1046.py:49 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_bell_1046.py:186 | tests/test_bell_1046.py:186 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_e_key_no_shift.py:82 | tests/test_e_key_no_shift.py:82 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_mode_switch_no_shift.py:57 | tests/test_mode_switch_no_shift.py:57 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_mode_switch_no_shift.py:93 | tests/test_mode_switch_no_shift.py:93 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_mode_switch_no_shift.py:104 | tests/test_mode_switch_no_shift.py:104 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_mode_switch_no_shift.py:113 | tests/test_mode_switch_no_shift.py:113 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_ms_timeline_grip_1267.py:142 | tests/test_ms_timeline_grip_1267.py:142 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_ms_timeline_grip_1267.py:148 | tests/test_ms_timeline_grip_1267.py:148 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_ms_timeline_grip_1267.py:201 | tests/test_ms_timeline_grip_1267.py:201 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 200 ms |
| tests/test_ms_timeline_grip_1267.py:211 | tests/test_ms_timeline_grip_1267.py:211 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 200 ms |
| tests/test_ms_timeline_grip_1267.py:271 | tests/test_ms_timeline_grip_1267.py:271 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 350 ms |
| tests/test_ms_timeline_grip_1267.py:279 | tests/test_ms_timeline_grip_1267.py:279 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 150 ms |
| tests/test_ms_timeline_grip_1267.py:379 | tests/test_ms_timeline_grip_1267.py:379 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_ms_timeline_grip_1267.py:389 | tests/test_ms_timeline_grip_1267.py:389 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_ms_timeline_grip_1267.py:416 | tests/test_ms_timeline_grip_1267.py:416 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_ms_timeline_grip_1267.py:430 | tests/test_ms_timeline_grip_1267.py:430 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_ms_timeline_grip_1267.py:479 | tests/test_ms_timeline_grip_1267.py:479 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_peek.py:582 | tests/test_peek.py:582 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 150 ms |
| tests/test_peek.py:588 | tests/test_peek.py:588 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 200 ms |
| tests/test_peek_arrows.py:99 | tests/test_peek_arrows.py:99 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 150 ms |
| tests/test_peek_arrows.py:111 | tests/test_peek_arrows.py:111 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 150 ms |
| tests/test_peek_arrows.py:152 | tests/test_peek_arrows.py:152 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 100 ms |
| tests/test_peek_arrows.py:164 | tests/test_peek_arrows.py:164 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 100 ms |
| tests/test_peek_arrows.py:176 | tests/test_peek_arrows.py:176 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 100 ms |
| tests/test_peek_arrows.py:196 | tests/test_peek_arrows.py:196 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 150 ms |
| tests/test_peek_arrows.py:249 | tests/test_peek_arrows.py:249 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 100 ms |
| tests/test_peek_arrows.py:265 | tests/test_peek_arrows.py:265 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 100 ms |
| tests/test_peek_arrows.py:271 | tests/test_peek_arrows.py:271 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 100 ms |
| tests/test_plain_line_hostile.py:289 | tests/test_plain_line_hostile.py:moved/not found | no-op | moved/not found: line text is not in the current file, so no verdict (not checked) |
| tests/test_profile_menu_hostile_1281.py:198 | tests/test_profile_menu_hostile_1281.py:198 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_profile_menu_hostile_1281.py:298 | tests/test_profile_menu_hostile_1281.py:298 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_profile_menu_hostile_1281.py:323 | tests/test_profile_menu_hostile_1281.py:323 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_rich_editor_bar_1288.py:101 | tests/test_rich_editor_bar_1288.py:101 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_row_delete.py:137 | tests/test_row_delete.py:137 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_slash_menu_4c_1288.py:132 | tests/test_slash_menu_4c_1288.py:132 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 500 ms |
| tests/test_top_bar_actions.py:64 | tests/test_top_bar_actions.py:64 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_top_bar_actions.py:74 | tests/test_top_bar_actions.py:74 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_top_bar_actions.py:86 | tests/test_top_bar_actions.py:86 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_top_bar_actions.py:92 | tests/test_top_bar_actions.py:92 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 800 ms |
| tests/test_top_bar_tabs.py:186 | tests/test_top_bar_tabs.py:186 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 1500 ms |
| tests/test_tpl_glance_editor_1264_killers.py:230 | tests/test_tpl_glance_editor_1264_killers.py:230 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 700 ms |
| tests/test_tpl_glance_editor_1264_killers.py:249 | tests/test_tpl_glance_editor_1264_killers.py:249 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_tpl_glance_editor_1264_killers_c.py:45 | tests/test_tpl_glance_editor_1264_killers_c.py:45 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_tpl_glance_killers_n1n2_1855.py:44 | tests/test_tpl_glance_killers_n1n2_1855.py:44 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 400 ms |
| tests/test_tpl_glance_killers_n1n2_1855.py:72 | tests/test_tpl_glance_killers_n1n2_1855.py:72 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_tpl_glance_killers_n1n2_1855.py:74 | tests/test_tpl_glance_killers_n1n2_1855.py:74 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_tpl_workitems.py:998 | tests/test_tpl_workitems.py:1001 (moved) | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 700 ms |
| tests/test_view_long_word.py:35 | tests/test_view_long_word.py:35 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 300 ms |
| tests/test_view_picks_1287_writes.py:101 | tests/test_view_picks_1287_writes.py:101 | no-op | no-op before 6762c23b0; waits now (js() awaits, tests/test_server.py:1642-1644); waits 600 ms |
| tests/_rich_page.py:137 | tests/_rich_page.py:137 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 138) |
| tests/test_alias_suggest.py:130 | tests/test_alias_suggest.py:130 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 131) |
| tests/test_e_key_no_shift.py:75 | tests/test_e_key_no_shift.py:75 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_hdr1177_900.py:29 | tests/test_hdr1177_900.py:29 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 30) |
| tests/test_header_no_project_name.py:44 | tests/test_header_no_project_name.py:44 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_header_no_project_name.py:84 | tests/test_header_no_project_name.py:84 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_list_keys.py:104 | tests/test_list_keys.py:104 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 105) |
| tests/test_menu_icons_every_1138.py:243 | tests/test_menu_icons_every_1138.py:244 (moved) | rAF | not a sleep (sets flag or runs a frame ticker, polled at 245) |
| tests/test_milestone_peek_828.py:60 | tests/test_milestone_peek_828.py:60 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 61) |
| tests/test_milestone_peek_828.py:92 | tests/test_milestone_peek_828.py:92 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 93) |
| tests/test_milestones_page_458.py:440 | tests/test_milestones_page_458.py:440 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 441) |
| tests/test_milestones_page_458.py:469 | tests/test_milestones_page_458.py:469 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 470) |
| tests/test_mode_switch_no_shift.py:39 | tests/test_mode_switch_no_shift.py:39 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_mode_switch_no_shift.py:99 | tests/test_mode_switch_no_shift.py:99 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_motion.py:476 | tests/test_motion.py:476 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 477) |
| tests/test_movement_page.py:313 | tests/test_movement_page.py:313 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 314) |
| tests/test_peek_milestone_1184.py:193 | tests/test_peek_milestone_1184.py:193 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 194) |
| tests/test_peek_milestone_1184.py:278 | tests/test_peek_milestone_1184.py:278 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 279) |
| tests/test_peek_milestone_survivors_b_1184.py:78 | tests/test_peek_milestone_survivors_b_1184.py:78 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 79) |
| tests/test_rich_editor.py:269 | tests/test_rich_editor.py:269 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 270) |
| tests/test_rich_font_colour_1364.py:76 | tests/test_rich_font_colour_1364.py:76 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 77) |
| tests/test_router.py:979 | tests/test_router.py:979 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 980) |
| tests/test_settings_key.py:32 | tests/test_settings_key.py:32 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_theme_overscroll_1370.py:128 | tests/test_theme_overscroll_1370.py:128 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 129) |
| tests/test_top_bar_long_names.py:43 | tests/test_top_bar_long_names.py:43 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_top_bar_tabs.py:61 | tests/test_top_bar_tabs.py:61 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_top_bar_tabs.py:178 | tests/test_top_bar_tabs.py:178 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_top_bar_tabs_915.py:48 | tests/test_top_bar_tabs_915.py:48 | rAF | no-op in effect, waits two frames now (two-frame promise) |
| tests/test_tpl_workitems.py:630 | tests/test_tpl_workitems.py:630 | rAF | not a sleep (sets flag or runs a frame ticker, polled at 631) |
| tests/test_about_you.py:507 | tests/test_about_you.py:507 | unsure | patch/stub, not a wait: shortens a page 5000 ms timer to 400 ms |
| tests/test_back_forward.py:382 | tests/test_back_forward.py:382 | unsure | not a sleep (sets flag, polled at 383): starts a 400 ms page timer, until("window.later") follows |
| tests/test_changed_sign_1408.py:69 | tests/test_changed_sign_1408.py:69 | unsure | patch/stub, not a wait: installs a fake clock |
| tests/test_enrichments.py:262 | tests/test_enrichments.py:262 | unsure | patch/stub, not a wait: installs a fake clock, later lines read the recorded timers |
| tests/test_log_wiring.py:640 | tests/test_log_wiring.py:640 | unsure | not a sleep (schedules a page error at 0 ms; wait(...) at 642 polls the log) |
| tests/test_peek_latest.py:349 | tests/test_peek_latest.py:349 | unsure | not a sleep (frame ticker sets window.__lab, polled at 350 with a 10 s limit) |
| tests/test_section_hint_all_types.py:58 | tests/test_section_hint_all_types.py:58 | unsure | patch/stub, not a wait: stretches a 4000 ms page timer to 600000 ms |
| tests/test_settings_head.py:78 | tests/test_settings_head.py:78 | unsure | patch/stub, not a wait: slows requestAnimationFrame by a set delay |
| tests/test_tracker_page.py:394 | tests/test_tracker_page.py:394 | unsure | patch/stub, not a wait: holds requestAnimationFrame and 35/100 ms timer callbacks |
| tests/test_tracker_page.py:404 | tests/test_tracker_page.py:404 | unsure | patch/stub, not a wait: restores the originals and runs the held callbacks |
| tests/test_uc_dashboard_edit.py:371 | tests/test_uc_dashboard_edit.py:371 | unsure | patch/stub, not a wait: stubs requestAnimationFrame to do nothing |
| tests/test_update_page.py:335 | tests/test_update_page.py:335 | unsure | patch/stub, not a wait: makes the stubbed reply arrive after 400 ms; the wait is a later line |

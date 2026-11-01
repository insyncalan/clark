"""clark 0.3's hand checks as tests. Each release gets a test_vNNN file, so the walk-through keeps only the judgement and
live-only checks.

Run: python3 dev/run_tests.py test_v030

Same shape as test_v020. Headless and fast: no Chrome is started here. What a person would check in the v0.3 items, and where:
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
VERSION = "0.3.0"

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#47", "With asking off, nothing is sent anywhere", "test_ask_route::TheSwitchOnTheServer::test_with_asking_off_nothing_is_sent"),
    ("#170", "The asking switch is on by default, is kept and survives a reload",
     "test_ask_settings::Settings::test_the_switch_is_on_by_default_changes_what_the_server_keeps_and_survives_a_reload"),
    ("#212", "A file outside the folders you chose is never read", "test_ask_passages::WhatIsRead::test_a_file_outside_the_saved_folder_is_never_read"),
    ("#213", "An answer can cite a passage from a folder file", "test_ask_passages::OnTheRoute::test_a_reply_can_cite_a_folder_passage"),
    ("#215", "A file holding a secret is left out whole", "test_secret_screen::Screen::test_each_family_is_caught"),
    ("#216", "The Claude command is run with the fixed flags and the question on standard input",
     "test_ask_claude::Arguments::test_the_run_is_started_with_the_isolating_flags_and_the_request_on_standard_input"),
    ("#214", "The ask panel opens with / and closes with Escape", "test_ask_panel::Panel::test_slash_opens_outside_a_field_and_not_in_one"),
    ("#214", "The published file has no ask panel", "test_ask_panel::Words::test_the_published_page_has_no_panel"),
    ("#102", "The ask panel's look, at laptop widths, light and dark",
     "test_ask_look::Look::test_laptop_widths_light_and_dark_empty_and_with_an_answer"),
    ("#102", "The suggestion pills are one row that scrolls sideways", "test_ask_look::Look::test_the_suggestions_are_one_row_that_scrolls_sideways"),
    ("#217", "Each place lists the same AI options in the same order as creaite",
     "test_ai_menu_parity::ListsMatchCreaite::test_each_kept_place_lists_the_same_options_in_the_same_order"),
    ("#72", "Each place's AI menu shape", "test_ai_menu::Places::test_menu_shape_per_place"),
    ("#218", "Nothing changes until the suggestion is accepted", "test_ai_menu::Card::test_nothing_changes_until_accept"),
    ("#218", "Accepting is one editor step and one Undo puts it back",
     "test_ai_menu::Card::test_accept_is_one_editor_step_and_one_undo_puts_it_back"),
    ("#218", "The card shows its working, ready and failed states", "test_ai_card::Card::test_ready"),
    ("#50", "Draft email: a good request is answered", "test_draft_email_route::Route::test_a_good_request_is_answered"),
    ("#50", "Draft email says whether the address is outside your own domains",
     "test_draft_email_route::Seam::test_the_answer_says_whether_the_address_is_outside_the_own_domains"),
    ("#48", "Word import: a check lists new items and writes nothing",
     "test_word_route::Check::test_a_check_lists_the_new_items_by_number_and_writes_nothing"),
    ("#48", "Word import: accepting is one step with one Undo",
     "test_word_route::Apply::test_accept_all_is_one_step_by_the_word_route_with_one_undo"),
    ("#48", "A hostile Word file is refused in plain words",
     "test_word_route::Refusals::test_a_hostile_file_stages_nothing_and_is_refused_in_plain_words"),
    ("#219", "Your own Word template is filled and everything else in it is kept",
     "test_word_template::Fills::test_a_template_is_filled_and_every_other_part_is_the_templates"),
    ("#219", "An unknown {{NAME}} stops the fill", "test_word_template::Stops::test_an_unknown_name_stops_the_fill"),
    ("#68", "Dragging a board card is one step with Undo", "test_work_board_page::Moves::test_dragging_a_card_is_one_step_with_undo"),
    ("#68", "Group by changes the board's columns", "test_work_board_page::GroupBy::test_group_by_menu_and_the_table_groups"),
    ("#68", "The published file has no board", "test_work_board_page::Switch::test_the_published_page_has_no_board"),
    ("#81", "Full screen keeps the headings in view", "test_work_board_page::FullScreen::test_full_screen_icon_scrolls_headings_and_keys"),
    ("#80", "Status changes in place by click and keyboard", "test_inline_edits::Live::test_status_by_click_and_keyboard"),
    ("#77", "Publish is in the profile menu, not in the bar", "test_profile_menu::ProfileMenu::test_C_publish_is_in_the_menu_and_not_in_the_bar"),
    ("#77", "Preview opens a new tab and publishes nothing",
     "test_profile_menu::ProfileMenu::test_C_the_preview_entry_opens_the_page_in_a_new_tab_and_publishes_nothing"),
    ("#77", "Export downloads the workbook named with the code and the day",
     "test_profile_menu::ProfileMenu::test_C_the_export_entry_downloads_the_workbook_named_with_the_code_and_the_day"),
    ("#77", "Preview writes no file and logs no publication",
     "test_preview_export_route::Preview::test_it_logs_no_publication_and_writes_no_file"),
    ("#179", "Dark mode (System, Light, Dark) is in the profile menu",
     "test_appearance::Appearance::test_C_the_menu_has_dark_mode_with_the_same_three_in_the_same_order_below_the_separator"),
    ("#71", "Launching starts clark and opens its window",
     "test_launcher::Launch::test_nothing_there_starts_clark_marked_launched_waits_and_opens_its_window"),
    ("#71", "A second launch only opens a window",
     "test_launcher::AgainstAFakeServer::test_start_then_the_real_check_sees_our_clark_and_a_second_launch_only_opens_a_window"),
    ("#229", "Generated page files merge by rebuilding and equal a fresh build",
     "test_merge_driver::MergeDriverTests::test_with_the_driver_different_sources_merge_and_the_pages_equal_a_fresh_build"),
    ("#238", "Help says PDF files are not read yet, and the panel says how many were skipped",
     "test_ask_passages::OnTheRoute::test_pdf_is_said_to_be_not_supported_yet"),
    ("#98", "The four section styles are shown as picture cards",
     "test_section_style_cards::Cards::test_C_four_cards_each_with_a_drawing_and_one_real_radio_in_a_named_group"),
    ("#78", "The peek shows coloured icons for status, priority and date",
     "test_peek_icons::ToneRules::test_priority_urgent_red_high_amber_medium_blue_low_and_none_grey"),
    ("#239", "History names an undone batch on every row of the batch",
     "test_history_rows::Rows::test_undo_several_is_named_on_every_row_of_the_batch"),
]

# Not on main (or no test found): (item, check, the question or where it is being built).
WAITING = [
    ("#180", "The profile menu shows the signed-in name and email on one line",
     "no test for the name-and-email line on main; is #180 in 0.3, and where is its test?"),
    ("#147", "The Preview and Export follow-up items (#147 items 3 and 4) are all met",
     "#179 and #180 are open as its unmet items; is #147 closed by them?"),
    ("#230", "The board reaches the prototype by v0.7",
     "a planning question for the owner, not a hand check: is 0.2.1 the current release, and is the gap list the plan?"),
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#47", "ask clark answers a real question from the demo data in the real Claude command", "live only",
     "needs a signed-in Claude command on the Mac; headless tests use a stub",
     "Open ask clark on the demo data, ask 'what is overdue?', and read the answer against the Work items page."),
    ("#102", "The ask panel's look (the Wash panel, pills, the working line) is right", "judgement",
     "only a person can say it looks right", "Open ask clark in light and dark and compare it with the design reference."),
    ("#68", "Dragging a card feels right and shows where it will land", "judgement",
     "feel, not a pass or fail", "Drag cards between columns and between lanes on the demo board."),
    ("#71", "The launcher opens clark as a Chrome app from a double-click", "live only",
     "needs a real Chrome and Finder", "Double-click the launcher file; clark opens in its own window; closing it ends clark."),
    ("#48", "Word export opens and reads well in Word", "live only",
     "only Word draws it", "Export a report to Word, open it in Word, and read it as the client would."),
    ("#219", "A report filled into your own Word template looks right in Word", "live only",
     "only Word draws it", "Fill a copy of your own template with {{NAME}} placeholders and open it in Word."),
    ("#50", "The Draft email text pastes into Outlook looking right", "live only",
     "needs Outlook", "Copy a drafted update request and paste it into a new Outlook message."),
    ("#77", "Export opens in Excel and Publish arrives in the client folder", "live only",
     "needs Excel and the synced folder", "Export, open in Excel; Publish To client and check the folder syncs."),
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
        if not found or not found.group(1).startswith("0.3"):
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
        t.__name__ = "test_%s_%d_needs_a_person" % (item.lstrip("#"), i)
        t.__doc__ = check
        setattr(Walk, t.__name__, t)
    for i, (item, check, q) in enumerate(WAITING):
        def w(self, _m=f"waiting: {q}"):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (item.lstrip("#"), i)
        w.__doc__ = check
        setattr(Walk, w.__name__, w)


class Walk(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips()

if __name__ == "__main__":
    unittest.main()

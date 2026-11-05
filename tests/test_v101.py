"""clark 1.0.1's hand checks as tests: the 1.0.1 items that have merged to main after 1.0.0. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v101

Same shape as test_v100.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written after 1.0.0 was published (tag v1.0.0), from origin/main on 05-11-2026: everything merged after the tag, and a WAITING row for
every other v1.0.1 board row that a customer sees.
The cut checks (version, release notes, hand-check sheet, the layout step) skip until the cut commit sets 1.0.1, then fail if wrong.
The notes' own rules (title with (Beta), the Beta line, plain words) are read from the tree now.

The data layout: 1.0.0 reads layout 15. The 1.0.1 notes carry the data-layout paragraph because the use case flag (#709) is a layout
step to 16. SCHEMA_VERSION in store.py stays 15 until the #709 backend merges, so the notes' words are asserted always, but the
agreement with store.py is gated: it skips while the schema is still 15, is checked once it moves, and at the cut it must be 16.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.1"
SCHEMA_AT_1_0_0 = 15     # 1.0.0 reads layout 15; the 1.0.1 use case flag (#709) is the step to 16
SCHEMA_AT_1_0_1 = 16     # what the cut must find in store.py

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#52", "Settings > AI shows a tile for Claude and one for ChatGPT, each Connected or Not connected, and the model list.",
     "test_ai_connect_page::Card::test_connected_shows_both_tiles_and_the_model"),
    ("#54", "Connect and Disconnect on a tile, and the card says what to do when the sign-in is missing.",
     "test_ai_connect_page::Card::test_disconnect_then_connect"),
    ("#54", "A smaller model asks first: Use it anyway or Keep the model I have; keeping changes nothing.",
     "test_ai_connect_page::Card::test_a_smaller_model_asks_first_and_keeping_changes_nothing"),
    ("#446", "The AI card fits and reads at 1400 and 900 px in light and dark.",
     "test_ai_connect_page::Card::test_it_fits_and_reads_at_both_widths_in_light_and_dark"),
    ("#693", "Help shows Connect Claude or ChatGPT, quoting the card's own words.",
     "test_help_shown::Held::test_the_ai_card_help_is_shown_and_quotes_the_card_verbatim"),
    ("#685", "Help calls the Settings section Version and updates, never as the start of a sentence.",
     "test_page_words::Words::test_no_sentence_on_the_page_starts_with_the_product_name"),
    ("#684", "The read-only use case page says No headline yet.",
     "test_empty_state_words::EmptyStateWordsTest::test_use_case_detail_read_only_says_exactly_not_written_yet"),
    ("#562", "A log that is a link is not written through.",
     "test_update_helper::LogHardeningTest::test_a_log_that_is_a_link_is_not_written_through"),
    ("#665", "On the Dashboard View and Edit is a pill at the left of the report bar, not in the top bar.",
     "test_mode_pill::ModePill::test_on_the_dashboard_it_is_in_the_report_bar_at_its_left_and_not_in_the_top_bar"),
    ("#665", "On the other tabs the switch stays in the top bar.",
     "test_mode_pill::ModePill::test_on_the_other_tabs_it_stays_in_the_top_bar"),
    ("#665", "The V and E keys still switch, and no part of the pill overlaps another at four widths in both colours.",
     "test_mode_pill::ModePill::test_no_overlap_at_the_four_widths_in_both_colours"),
    ("#679", "Switching View and Edit keeps the section nearest the top where it was.",
     "test_mode_switch_no_shift::NoShift::test_the_nearest_section_does_not_move"),
    ("#675", "The section dots sit 18 px from the right edge at 1400 px.",
     "test_toc_button_source::Look::test_the_rail_at_1400_is_untouched_by_the_narrow_rules"),
    ("#681", "The top bar tabs stay on one line at 1400, 901, 900 and 800 px.",
     "test_top_bar_tabs::TopBarTabs::check"),
    ("#653", "At 900 px the saved view tab row stays on one line and scrolls inside its own box.",
     "test_filter_line_page::Line::test_the_tab_row_stays_on_one_line_and_scrolls_inside_its_own_box"),
    ("#653", "A tab's options menu closes when the row scrolls or the window resizes.",
     "test_filter_line_page::Line::test_the_open_tabs_menu_closes_when_the_row_scrolls_or_the_window_resizes"),
    ("#682", "With no project open only the cards that work show, and Import and Export workbook say Add a project first.",
     "test_settings_no_project::Browser::test_item_682_only_the_cards_that_work_show_and_import_says_why"),
    ("#701", "Settings with no project reads in light and dark at 900 and 1400 px.",
     "test_settings_no_project::Browser::test_item_701_no_project_settings_in_light_and_dark_at_900_and_1400"),
    ("#683", "The growth check's limit is 6.5, and the helper says so.",
     "test_growth::TheGrowthCheckTellsLinearFromQuadratic::test_the_limit_sits_above_linear_and_below_n_to_the_power_one_and_a_half"),
    ("#695", "The Docker data folder is mounted at /data, outside the read-only share, and clark is told that folder.",
     "test_server_container::Compose::test_no_mount_target_sits_inside_the_read_only_share"),
    ("#696", "A path outside the home folder is shown as it is, and the OneDrive message shows the real path.",
     "test_platform_container::ShownPath::test_the_onedrive_refusal_shows_the_real_path"),
    ("#696", "In Docker the start line says how to stop with docker compose down and mentions no window.",
     "test_platform_container::StartLine::test_the_container_line_gives_the_docker_stop_and_no_window"),
    ("#664", "The top bar has a search icon and an ask clark button, before Help and the avatar.",
     "test_top_bar_actions::TopBarActions::test_the_two_buttons_have_their_words_and_sit_before_help_and_the_avatar"),
    ("#664", "The ask clark button is not there while asking is off.",
     "test_top_bar_actions::TopBarActions::test_the_ask_button_is_not_there_while_asking_is_off"),
    ("#677", "Settings has a chip for each card that is shown.",
     "test_settings_head::Head::test_C_the_title_the_help_line_and_a_chip_for_each_card_that_exists"),
    ("#677", "Appearance is a segmented control (System, Light, Dark), not radio buttons.",
     "test_appearance::Appearance::test_C_appearance_is_a_segmented_control_not_radio_buttons"),
    ("#677", "Single-key shortcuts is a switch with its words and works by keyboard.",
     "test_single_keys::PageKeys::test_the_setting_is_a_switch_with_its_words_and_works_by_keyboard"),
    ("#688", "The line under the Help search count says each result names the guide and the step.",
     "test_help_search_where::Logic::test_the_count_line_and_the_lead_are_the_signed_words"),
    ("#720", "The Help search guide line shows only while a result is a guide.",
     "test_help_search_where::Page::test_the_lead_line_is_in_the_page_only_while_a_result_is_a_guide"),
    ("#694", "The download unzips into one folder called clark, with the program in a hidden folder inside it.",
     "test_package_layout_e2e::DownloadLayout::test_one_folder_called_clark_with_the_program_in_dot_app_and_nothing_of_the_persons"),
    ("#694", "Typed commands in messages read bash clark.command.",
     "test_typed::LauncherScript::test_the_commands_it_forwards_say_bash_clark_command"),
    ("#687", "The Help examples use no full made-up name (hand-over and Sneak peek use first names only).",
     "test_no_real_names::NoRealNames::test_no_tracked_file_names_a_real_client_project_or_person"),
    ("#724", "The ask panel shows no 'asking is off' line until the server has answered.",
     "test_ask_panel::Panel::test_a_slow_server_shows_no_off_line_until_it_answers_that_asking_is_off"),
    ("#672", "Week ending has a calendar button that opens clark's own picker, never the browser's, with only Fridays to choose.",
     "test_report_bar_pick::Pick::test_the_panel_is_named_and_offers_only_friday"),
    ("#672", "A Friday pick is saved like typing it; a day that is not a Friday keeps the old date.",
     "test_report_bar_pick::Pick::test_a_day_that_is_not_a_friday_keeps_the_old_value"),
    ("#672", "Esc closes only the picker.",
     "test_report_bar_pick::Pick::test_esc_closes_only_the_panel_and_keys_work"),
    ("#733", "The project switcher is a bordered box with the chevron at the right.",
     "test_project_switch::ProjectSwitch::test_C_the_switcher_is_a_bordered_box_with_the_chevron_at_the_right"),
    ("#732", "The profile circle in the top bar is filled aqua with a navy mark, in light and dark.",
     "test_top_bar_avatar::Avatar::test_the_profile_circle_is_filled_aqua_with_a_navy_mark_in_light_and_dark"),
    ("#662", "The typed filter highlights field names plain and values as chips.",
     "test_filter_line_page::Line::test_the_text_is_highlighted_field_names_plain_and_values_as_coloured_chips"),
    ("#662", "The match count sits in the box and the x clears to the full view.",
     "test_filter_line_page::Line::test_the_x_shows_whenever_there_is_text_clears_to_the_full_view_and_keeps_the_focus"),
    ("#662", "A token that cannot be used is underlined with its note, and no match shows No work items match with Clear filter.",
     "test_filter_line_page::Line::test_no_match_shows_the_empty_state_with_a_clear_filter_link"),
    ("#662", "Typing offers fields then values.",
     "test_filter_line_page::Line::test_typing_offers_fields_then_values_with_arrows_and_enter_choose"),
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
    ("#655", "Import from Excel lists the workbook's sheets, all ticked, and reads only the ticked ones.",
     "PR 671", "excel_import.py", "sheets=None"),
    ("#710", "The Excel export shows ID: name in the Milestone and Use case cells and has Open work items.",
     "PR 672", "excel.py", '("Open work items", "open_items")'),
    ("#711", "The Excel cover follows option A: title band, INTERNAL tag, tiles, tab order.",
     "PR 672", "excel_palette.py", ""),
    ("#727", "The Excel export locks the cells people should not edit (sheet protection, no password).",
     "no pull request yet (issue 727)", "", None),
    ("#709", "A use case carries a Commitment flag (Candidate, Committed, Planned 2027 or none) in the data, the published report, the Word copy and Excel (layout step 16).",
     "PR 673", "store.py", "SCHEMA_VERSION = 16"),
    ("#709", "In Edit a Commitment menu beside the status sets the flag, and the chip shows on the use case, the Use cases tab and the Dashboard rows.",
     "no pull request yet (issue 709)", "", None),
    ("#713", "The published report has a Report menu with Profile, Export to Excel, Export to PDF, Past reports and Dark mode (Light, Dark, System default).",
     "PR 681", "page/src/components/ClientMenu.jsx", "Report menu"),
    ("#713", "Publishing makes the workbook that goes inside the published file, so Export to Excel and Past reports show there.",
     "PR 687", "excel_client.py", ""),
    ("#716", "The download has a meet clark folder with the overview and the Getting Started PDFs (also #706, #707, #722).",
     "PR 677", "release_files.py", 'EXTRA_TOP = ("meet clark", "intake")'),
    ("#741", "START-HERE no longer carries a version number in its sentence about updating from inside clark.",
     "PR 688", "../../dev/tools/package.py", "Updating from inside clark is switched off,"),
    ("#698", "The README covers both ways to start clark, the check command, where data lives and has pictures (also #708).",
     "PR 682", "../../README.md", "docs/img/clark-mascot.png"),
    ("#712", "The design prototype's Past reports page keeps only the Published reports list (prototype only; PR 674 is merged, no unit test reads the prototype).",
     "PR 674", "../../system/prototype/past.js", "Published reports: a mockup for review"),
    ("#721", "Help describes ask clark and Sneak peek as they behave, with one top-bar button bullet.",
     "PR 685", "page/src/help/helpContent.json", "Sneak peek, with a work item open in Edit"),
    ("#731", "The first start opens with made-up demo projects and a banner 'This is demo data.' with a Remove demo data button.",
     "PR 689", "page/src/logic/demoWords.js", "This is demo data."),
    ("#734", "The toolbar's View and Edit pill is aqua with a pencil on Edit, the week-ending field is rounded and the draft chip is 12 px.",
     "PR 683", "page/src/edit/edit.css", ".rbar .seg .mode .tb-ico"),
    ("#751", "The download carries its own README.md: the repository README without the pictures and without lines that name things outside the download.",
     "no pull request yet (issue 751)", "", None),
    ("#735", "The report cover shows the logo and the wave picture on a distinct dark band.",
     "no pull request yet (issue 735)", "", None),
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
    no lower-case 'ask clark' in a heading, and the data-layout paragraph (the use case flag is a layout step to 16)."""

    def setUp(self):
        self.text = (ROOT / "dev" / "release-notes" / (VERSION + "-plain.md")).read_text(encoding="utf-8")

    def test_the_title_the_beta_line_and_the_update_sentence(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("Beta", self.text)
        self.assertIn("This is the 1.0 build. It is still marked Beta because updating from inside clark is not switched on yet.", self.text)
        self.assertIn("Updating from inside clark is not switched on yet: install a new version by downloading it and replacing the old one.", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_notes_carry_the_data_layout_paragraph_and_the_older_clark_sentence(self):
        """Always asserted, whatever store.py says: the notes are written for the layout step the use case flag (#709) brings."""
        self.assertIn("This version includes a change to how clark stores your data", self.text)
        self.assertIn("a change to how clark stores your data", self.text)
        self.assertIn("from layout %d to %d" % (SCHEMA_AT_1_0_0, SCHEMA_AT_1_0_1), self.text)
        self.assertIn("clark makes a safety copy of your data before it changes anything", self.text)
        self.assertIn("An older clark (1.0.0) refuses the new data file", self.text)
        self.assertIn("This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.", self.text)
        self.assertIn("restore the safety copy", self.text)

    def test_the_layout_words_agree_with_store_py_once_the_layout_step_is_in(self):
        """Gated so it is green before and after the #709 backend merges: while SCHEMA_VERSION is still 15 the step is not in
        main, so there is nothing to compare and the test skips; once it is not 15 it must be exactly the step the notes name."""
        found = schema_version()
        if found == SCHEMA_AT_1_0_0:
            self.skipTest("SCHEMA_VERSION is still %d: the #709 layout step is not on main yet; the notes' words are asserted anyway" % found)
        self.assertEqual(found, SCHEMA_AT_1_0_1, "the notes name layout %d; store.py says %s" % (SCHEMA_AT_1_0_1, found))
        self.assertIn("Step %d:" % found, self.text)

    def test_a_date_in_the_notes_is_day_first(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 1.0.2 and later have their own test_vNNN
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

    def test_the_layout_step_is_in_at_the_cut(self):
        """The notes say a layout step is in, so at the cut SCHEMA_VERSION must be 16: this fails in a 1.0.1 copy while #709's backend is not merged."""
        self.cut_made()
        self.assertEqual(schema_version(), SCHEMA_AT_1_0_1, "the notes carry the layout paragraph: the #709 backend must be in main before the cut")

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

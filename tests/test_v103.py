"""clark 1.0.3's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.3 row. Each release gets a
test_vNNN file, so the walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v103

Same shape as test_v102.
  COVERED       a merged row a person can see, already covered by a test elsewhere. test_every_covering_test_named_here_exists
                fails if one goes missing. Rows 273, 802, 827, 872 and 874 have no visible change (NO_VISIBLE_CHANGE).
  WAITING       a row that is not on main yet but has a marker in the source that appears when it lands (item, check, pull request,
                a file under the top folder, the text in it). Skipped, with the pull request. After the cut commit has set the
                version and the marker is there, the row fails until it is moved to COVERED with its test. Empty today: the
                waiting rows live in the status table of the sheet, between its two marker comments.
  WALK_THROUGH  judgement or live only. Skipped: 'needs a person'. Empty today.

The notes hold only merged, user-visible rows; no DRAFT line is allowed anywhere. The status table in the sheet lists every 1.0.3 row
(refresh it with the regeneration helper as rows merge). The cut checks (version, files, layout) skip until the cut commit sets 1.0.3.

The data layout does not change in 1.0.3 (layout 16 stays): the notes say so and the store must still say 16.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.3"
SCHEMA = 16              # 1.0.1 moved to layout 16; 1.0.3 does not change it

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#856", 'The project menu ends with New project... and starts on the open project.',
     "test_project_switch::ProjectSwitch::test_C_the_menu_starts_on_the_open_project_and_has_New_project_that_opens_the_form"),
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
     "test_help_pr_a::SettingsChips::test_the_chip_names_and_order_are_the_pages"),
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
     "test_top_bar_tabs::TopBarTabs::test_the_tabs_tighten_their_padding_at_1000_px_and_below_and_never_wrap"),
    ("#775", "The Work items board columns are lifted cards and the full-screen icon is arrows.",
     "test_work_board_page::Cards::test_row_775_columns_are_lifted_cards_and_the_full_screen_icon_are_arrows"),
    ("#776", "The Sneak peek words box is a floating card.",
     "test_peek_arrows::Arrows::test_row_776_the_words_box_is_a_floating_card_in_light_and_dark"),
]

# Merged rows with no visible change: they have a MERGED line in the status table and need no bullet, hand check or test here.
NO_VISIBLE_CHANGE = {"273", "802", "827", "872", "874"}

# Rows with one part merged and the rest open: the merged part is covered here, the row stays IN REVIEW in the table.
PARTLY_MERGED = {"767", "766", "775", "776"}

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
        self.assertIn("This is the 1.0 build. It is still marked Beta because updating from inside clark is not switched on yet.", self.text)
        self.assertIn("Updating from inside clark is not switched on yet: install a new version by downloading it and replacing the old one.", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_notes_say_the_data_layout_is_unchanged_and_carry_no_layout_step(self):
        self.assertIn("This version does not change how clark stores your data.", self.text)
        self.assertNotIn("Read this first", self.text)
        self.assertNotIn("Step 17", self.text)

    def test_the_known_limits_carry_the_by_hand_install_and_the_demo_limit(self):
        self.assertIn("## Known limits", self.text)
        self.assertIn("Updating from inside clark is still not switched on.", self.text)
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
        self.assertEqual(schema_version(), SCHEMA, "the notes say the data layout is unchanged")

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

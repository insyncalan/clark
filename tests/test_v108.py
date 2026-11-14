"""clark 1.0.8's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.8 row.

Run: python3 dev/run_tests.py test_v108

Same shape as test_v107. COVERED holds every merged row with something to see; NO_VISIBLE_CHANGE and TEST_ONLY hold the rest; WAITING is empty.
The notes' own rules run against dev/release-notes/1.0.8-plain.md. Everything that reads the hand-check sheet, and the cut
tests, skip until the cut commit sets 1.0.8 in src/clark/__init__.py; from then on both files must exist, every row in the sheet's
status table is MERGED or DROPPED, and no WAIT heading is left in the notes. The data layout is 24 (no step came with 1.0.8).
"""
import ast
import os
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.8"
SCHEMA = 24              # the layout 1.0.7 ended at; 1.0.8 took no step

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ('658', 'In Edit, hover a work item row and press its More actions button. Then open the peek and press More actions. The row menu opens with Delete last in red. In the peek: Duplicate, Archive, then Delete in red.',
     'test_row_delete::DeleteItem::test_the_peek_more_actions_menu_ends_with_delete_in_the_warning_colour_and_asks_the_same_question'),
    ('831', 'In Settings, Data card, press Export to Word, then Esc. Same for Import from Word. Focus is back on the Export to Word button (and on Import from Word).',
     'test_data_card::DataCard::test_C_word_boxes_give_focus_back_to_the_data_button_on_esc_and_close'),
    ('836', 'Open Help. The Quit clark and Docker lines are there and no line runs wider than a readable measure.',
     'test_help_line_length::LineLength::test_help_text_lines_stay_a_readable_measure'),
    ('891', "Ask a question whose answer comes from a PDF in a chosen folder. Then try a scanned or password PDF in the folder. The source reads the file name and 'page N'. For the scanned or password PDF the answer carries a line giving the reason.",
     'test_ask_pdf_passages::InAsk::test_passages_carry_the_page_and_the_name_in_the_folder'),
    ('936', 'Open a published page and Help with a quote, a link preview and a note. No coloured side bar on them. A changed-row amber bar and a picked-row blue bar are still there.',
     'test_card_borders_936::Source::test_the_published_page_has_no_edit_override_and_shell_css_has_the_quiet_note'),
    ('944', 'In Settings, Brands card, with a project open: choose a brand in the project picker. Then remove that brand. The choice saves at once with Undo. After the removal the picker shows Generic with the note.',
     'test_brand_page::Page::test_the_project_picker_lists_generic_and_the_added_brands_and_saves_a_choice_at_once'),
    ('951', 'Settings, Data card: press Excel file layout. The box lists Cover, Gantt and History. The Cover line says it holds the report and that changes made on it are ignored. The Gantt line says one row per line, with Days and Status worked out.',
     'test_data_card::DataCard::test_C_excel_file_layout_opens_a_box_with_the_three_texts_and_sends_nothing'),
    ('993', "Help, Write and format text. The editor bar, the floating bar and the / menu lists name no AI button or AI options. The key line for undo does not mention an AI suggestion. The editor line reads 'Cmd+Enter saves. Esc cancels.'",
     'test_help_content::Words::test_nothing_is_named_that_clark_does_not_have'),
    ('1005', 'Edit: open a picture caption, a Movement who/reason/source field and the Own words of a risk. No / menu, no floating bar and no formatting buttons, only Undo and Redo; Enter saves. Help, editor controls table, has a One-line fields row.',
     'test_one_line_fields_1005::Caption::test_a_caption_is_the_one_line_editor'),
    ('1041', 'Open Help, Settings, Quit. The question, the two buttons Quit clark and Cancel, and the start-again words (double-click clark.command; with Docker, start it the same way as before).',
     'test_help_ui_1332::HelpUi1332::test_quit_help_names_the_question_and_both_buttons'),
    ('1043', 'Open Help at a wide window, then Start here. The return line wraps at a readable width (about 70 characters a line or fewer), and the text on every other Help page does not run across the whole window.',
     'test_help_text_measure_1043::TextMeasure::test_paragraphs_and_list_items_stay_a_readable_measure'),
    ('1097', 'With no model connected, open ask clark and click Open Settings. Settings opens with the Asking card at the top of the view and stays there.',
     'test_ask_panel::Panel::test_row_1097_the_open_settings_link_with_no_model_connected_lands_on_the_asking_card'),
    ('1111', 'Open a published file and a use case page, click a work item that has Client wording and a Latest update. Close the peek and press Esc. Both show as read-only rows. After Esc you land on the Use cases list.',
     'test_peek_latest_wording_1111::PublishedPeek::test_an_action_with_both_shows_both_read_only'),
    ('1114', 'Open a published file. On Milestones press Hide details. Then open the Use cases tab. Hide details is there, open, and works. The Use cases tab has the tabs with counts, Sort by and Group by, and no editing controls.',
     'test_milestones_details::Details::test_a_published_file_has_the_toggle_open_and_remembers_nothing'),
    ('1115', 'Open Settings. Type a word in Search settings. Change Spacing. Change Gantt name. Search settings and Essentials come first; typing narrows the rows. Spacing shows a message with Undo. Gantt name shows a blue dot and a Reset button.',
     'test_settings_essentials_1115::Essentials::test_S3_the_eight_rows_are_there_on_the_shared_row_with_working_controls'),
    ('1133', 'In Work items select a Delayed, a Cancelled and a Closed item (Ctrl-click) and press Reopen in the bulk bar. Then Close a selection holding a Cancelled item. Only the Closed item becomes Open; the Delayed and Cancelled ones stay as they were with a plain reason. The Cancelled item stays Cancelled.',
     'test_changes_bulk::Bulk::test_reopen_with_from_status_leaves_delayed_and_cancelled_alone'),
    ('1135', 'With one demo project, open the bare address. With two or more, open it again after using one. Clear the browser data and open it again. One project opens with no chooser. With several, the last used project opens. After clearing the browser data you see the chooser.',
     'test_open_last_project_1135::Browser::test_one_project_opens_silently'),
    ('1136', 'On Work items in Board view, with the pointer over the board, swipe sideways with two fingers (Mac mouse or trackpad). This needs a person; a test cannot swipe. The browser goes Back or Forward.',
     'test_overscroll_swipe::Swipe::test_no_scroller_stops_the_swipe_on_work_items'),
    ('1137', 'On Work items click in the filter field, light and dark, at 1400 and 900. No purple ring or shadow, only the text cursor. The Table, Board and Group by icons sit in the same places outside the box.',
     'test_filter_line_focus_look::FocusLook::test_focused_field_has_no_ring_shadow_or_darker_border'),
    ('1138', 'In Edit open the dashboard section menu (from the grip) and the profile menu, at 1400 and 900. Every line has an icon beside its words and the words are unchanged.',
     'test_menu_icons_every_1138::Dashboard::test_the_section_menu_gives_each_line_its_icon_and_keeps_its_words'),
    ('1139', 'On Work items hover the badge of an Urgent (maroon) risk and of a light-red risk. The first reads Risk · Urgent, the second Risk · Red; neither says both.',
     'test_icon_words_node::UrgentSaysUrgentOnce::test_an_urgent_risk_that_is_not_overdue_says_urgent_and_not_red'),
    ('1140', 'Open the Work items page and a published file. Titles in the lists and cards look normal weight, not bold.',
     'test_raid_card_title::RaidCardTitle::test_a_card_title_is_normal_weight_not_bold_at_both_widths'),
    ('1141', 'Open a use case page. The Milestones card has one Add a milestone button (no Link a milestone) and a Through work items row has no Remove.',
     'test_uc_milestones_page::Card::test_add_a_milestone_menu_links_it_directly'),
    ('1142', 'Open Work items, Use cases and Gantt. No import or export arrow buttons. Settings > Data still has Import workbook and Export workbook.',
     'test_work_export_button::ExportButton::test_the_editor_has_no_export_or_import_icon'),
    ('1143', 'Export to Excel and look at the downloaded file name. Name, code in brackets with no space before it, date as year.month.day, time with dots.',
     'test_export_download_name::Name::test_the_format_is_name_bracketed_code_then_date_and_time_with_dots'),
    ('1144', 'Open a published report and press the moon button beside the profile circle. Open its menu. The page turns dark (then a sun shows). The menu has no Light, Dark or System rows.',
     'test_client_menu::Menu::test_the_switcher_is_a_named_button_beside_the_badge_and_shows_a_moon_then_a_sun'),
    ('1145', 'Open the Work items page. The first column shows only the tinted letter icon, with no words like Red or Due soon beside it.',
     'test_status_icon_only_1145::IconOnly::test_work_items_status_is_the_icon_alone_and_first'),
    ('1146', 'Open a published report and scroll. One slim bar stays at the top with name, tabs, date and profile circle, and the first card starts just under it.',
     'test_published_one_bar::InTheFile::test_the_bar_is_68_px_and_sticky_at_1400_and_two_rows_at_900'),
    ('1147', 'Open the Dashboard and a published file. In Use case summary the counts are at the left and the coloured bars at the right end of the tile.',
     'test_uc_strip_1147::Bars::test_the_bars_are_at_the_right_of_the_tile_in_view_and_edit'),
    ('1148', 'Open the More actions menu on a use case and on a milestone. Archive then Delete. Delete asks, Undo brings it back, and one with work items says what refers to it.',
     'test_record_delete_1148::Delete::test_a_use_case_row_has_more_actions_archive_then_delete_and_delete_asks_then_undo_brings_it_back'),
    ('1149', 'Open the Use cases page in the editor and in a published file. Each row reads like the dashboard Use case summary row, "UC 1.1" appears once in the box, and Sort by (Reference, Status, Open work items) sits beside Group by.',
     'test_use_cases_list::List::test_a_row_is_laid_out_as_the_dashboard_summary_row_is'),
    ('1150', 'Export a project to Excel and open a work item sheet. Then import the file back. The Milestone drop-down lists names and the Use case drop-down lists "UC 1.5 Title" style text, with no ids. The import shows no change.',
     'test_excel_refs::Export::test_item_cells_show_the_name_and_no_id'),
    ('1152', "Open the Dashboard at 1400 and 900 px. The tile edges line up with the header edges and the tile heading is smaller than before; the published file's headings are unchanged.",
     'test_dash_tiles_header::TileWidth::test_tiles_line_up_with_the_header_and_the_heading_is_19px'),
    ('1154', 'With a brand that has a logo. The Dashboard band shows it at the right at 1400 px; with Generic or a brand with no logo the band is unchanged; the band text stays easy to read.',
     'test_cover_band::Logo::test_the_brand_logo_sits_at_the_right_of_the_band'),
    ('1156', 'Import a workbook whose work item rows name a new milestone and a new use case. Both are listed with Create it and Use an existing one, Import is off until both are answered, then the work item is linked to them.',
     'test_import_questions_page::Questions::test_both_are_listed_with_the_two_choices_and_import_waits_for_each_answer'),
    ('1157', 'Export to Excel and open it. On every sheet each locked column, including Project, has a grey background and the text stays readable.',
     'test_excel_protection::Protected::test_every_locked_column_has_the_grey_fill_on_its_data_rows_and_no_other_does'),
    ('1158', 'Open a work item peek. There is no Needed from the client switch; the Dashboard and a published file show no Needs from you section.',
     'test_peek_client_action::Page::test_no_peek_has_the_switch'),
    ('1159', 'On the Milestones Timeline pick Week, Month and Quarter. The spacing changes, names with no room are hidden, and hovering the mark shows name, date and state.',
     'test_milestones_timeline_zoom_1159::Zoom::test_the_control_has_the_three_choices_and_each_changes_the_spacing'),
    ('1160', 'Export to Excel on the demo data and open the Use cases sheet. The headings run ID, Reference, Use case; then import an older file headed Shown as and see it still imports.',
     'test_excel_format::Formatting::test_header_and_the_id_and_title_columns_are_frozen_on_every_sheet'),
    ('1164', 'Run bash docker/diagnose.command in the unzipped clark folder, then bash docker/start.command on a data folder written by a newer clark (Docker needed). Diagnose lists the folder, both versions, the container and log lines; start stops with a sentence naming the folder and both versions.',
     'test_starter_newer_data::Main::test_newer_data_is_refused_naming_the_folder_both_versions_and_the_way_out'),
    ('1153', 'In Settings, Brands card, with a brand installed and a project open, choose that brand in the project picker. The brand is accepted and the project shows it, where before only Generic could be chosen.',
     'test_project_brand_setting::Installed::test_an_installed_brand_is_accepted_and_an_unknown_or_non_string_one_is_refused'),
]

# The first words of each bullet, to find it by: {row id: start of its bullet}.
BULLET_STARTS = {
    '658': 'Each work item row has a More actions button (show',
    '831': 'Export to Word and Import from Word, opened from t',
    '836': 'Help has new lines for Quit clark, Docker and the ',
    '891': 'When ask clark cannot read a PDF it now says why, ',
    '936': 'Quotes, link previews, Help notes and the draft-em',
    '944': 'The Brands card in Settings has a picker for each ',
    '951': 'The Excel file layout box on the Data card now say',
    '993': 'The Help article on writing and formatting text no',
    '1005': 'One-line wording fields (the Client wording on a r',
    '1041': 'The Quit entry in Help now names the question it a',
    '1043': 'Help lines are narrower and easier to read, includ',
    '1097': 'The Open Settings link in the ask clark box, when ',
    '1111': 'In a published file, the peek of a work item shows',
    '1114': "A published file's Milestones list keeps the Hide ",
    '1115': 'Settings has a Search settings box, an Essentials ',
    '1133': 'Bulk Reopen no longer changes Delayed or Cancelled',
    '1135': 'When there is only one project, clark opens it str',
    '1136': 'The sideways two-finger swipe goes Back and Forwar',
    '1137': 'The filter field no longer gets a purple highlight',
    '1138': 'Every drop-down menu now shows an icon beside each',
    '1139': "A risk's tooltip now says Risk, Urgent or Risk, Re",
    '1140': 'Work item titles in lists and cards are now in nor',
    '1141': "On a use case's page the Milestones card has one b",
    '1142': 'The Import and Export arrow buttons are gone from ',
    '1143': 'The Excel export file is named with the project na',
    '1144': 'The published report has a small moon and sun butt',
    '1145': 'Work item lists show the small tinted letter icon ',
    '1146': 'The published report has one slim bar at the top t',
    '1147': 'In the Use case summary the row of coloured bars s',
    '1148': 'A use case or a milestone can be deleted from its ',
    '1149': 'The Use cases page and the published Use cases tab',
    '1150': 'In the Excel export, a Milestone drop-down cell no',
    '1152': 'On the Dashboard the section tiles are now as wi',
    '1154': 'The report band on the Dashboard shows the brand',
    '1156': 'When a workbook names a milestone or use case th',
    '1157': 'Every locked column of the Excel file now has th',
    '1158': 'The Needed from the client switch and the Needs ',
    '1159': 'The Milestones Timeline has Week, Month and Quar',
    '1160': 'On the Use cases sheet the column headed "Shown ',
    '1164': 'Starting clark with Docker (bash docker/start.co',
    '1153': 'A brand you have installed can now be attached to',
}
assert len(set(BULLET_STARTS.values())) == len(BULLET_STARTS)

# Merged rows whose note is another row's bullet: none.
NO_BULLET = set()
# Bullets for merged work that has no plan row in COVERED: none.
EXTRA_BULLET_STARTS = ()

# Merged rows with no visible change.
NO_VISIBLE_CHANGE = {'669'}   # 669 changed only the owner's prototype, not the build
# Merged rows that are tests or internal code only: no bullet, no hand check.
TEST_ONLY = {'1047', '1093', '1096', '1106', '1107', '1109', '1128', '1132', '1151'}
# No user note, and no hand check, once merged.
NO_NOTE_WHEN_MERGED = set()

# Rows with one part merged and the rest open: none.
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
    """True from the cut on: once the version says 1.0.8 every merged row needs its bullet. V108_FINAL=1 asks for it earlier."""
    return found_version == VERSION or (os.environ.get("V108_FINAL") if env is None else env) == "1"


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
    """The status table of every 1.0.8 row, between its two markers in the sheet. Skips until the cut."""

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
        """A merged row may lack its bullet until the cut; from the cut (version 1.0.8, which this class runs at) exactly one for each is demanded."""
        covered = {i.lstrip("#") for i, _, _ in COVERED}
        self.assertEqual(wait_bullets(self.text), [], "no bullet waits at the cut")
        self.assertNotRegex(self.text, r"(?m)^- Issue \d+ ", "no authoring tag is left in a bullet")
        self.assertEqual(bullet_problems(bullets(self.text), covered, bullets_are_final(version()), EXTRA_BULLET_STARTS), [])

    def test_the_notes_hold_no_status_table_and_no_row_ids(self):
        self.assertNotIn(BEGIN, self.text)
        self.assertNotRegex(self.text, r"(?m)^\| ")


class BulletsFinalCheck(unittest.TestCase):
    """Self-test of the cut-time check: a merged row without a bullet fails with V108_FINAL=1 and passes without it."""

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
        self.assertTrue(bullets_are_final(VERSION, env=""), "version 1.0.8 demands every bullet, with no env set")
        self.assertFalse(bullets_are_final("1.0.7", env=""), "before the cut a missing bullet is tolerated")
        self.assertTrue(bullets_are_final("1.0.7", env="1"), "V108_FINAL=1 asks for it early")

    def test_dropping_a_bullet_fails_in_the_cut_state(self):
        found = ["- Alpha one"]                      # Beta's bullet dropped
        self.assertTrue(bullet_problems(found, self.ROWS, bullets_are_final(VERSION, env="")))
        self.assertEqual(bullet_problems(found, self.ROWS, bullets_are_final("1.0.7", env="")), [])


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
        self.assertEqual(schema_version(), SCHEMA, "1.0.8 ends at layout 24")

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

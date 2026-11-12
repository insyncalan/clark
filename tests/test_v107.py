"""clark 1.0.7's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.7 row.

Run: python3 dev/run_tests.py test_v107

Same shape as test_v106. COVERED holds the rows merged so far (the first docs batch); the cut bookkeeping adds the rest from the merged list. WAITING and TEST_ONLY start empty.
The notes' own rules run now against dev/release-notes/1.0.7-plain.md. Everything that reads the hand-check sheet, and the cut
tests, skip until the cut commit sets 1.0.7 in src/clark/__init__.py; from then on both files must exist, every row in the sheet's
status table is MERGED or DROPPED, and no WAIT heading is left in the notes. The data layout stays at 20.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.7"
SCHEMA = 20              # 1.0.6 ended at layout 20; 1.0.7 stays at 20

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
]

# The first sentence of each bullet, to find it by: {row id: start of its bullet}. Filled with COVERED.
BULLET_STARTS = {
    '836': 'Settings has a Quit card.',
    '999': 'Each project now uses its own brand in everything clark makes',
    '1023': "A brand's cover picture now shows faintly behind every page",
    '1057': "In a work item's peek, the box for your words stays at the bottom while the peek scrolls.",
    '1059': 'The type buttons (All, Actions, Risks and issues, Decisions) and the status buttons (Open, Closed, All) above the list are gone.',
    '1062': 'The Asking card in Settings says where a question goes and which account pays for it.',
    '1063': "Import from Word is no longer in the profile circle's menu.",
    '1064': 'The top bar no longer shows the project name.',
    '1073': '"+ New view" makes a view at once, named View 1, View 2 and so on; you can rename it.',
    '1074': 'Each choice in a drop-down of the peek, the table cells and the milestone peek shows a small icon beside its words',
    '1075': 'A message at the foot of the page goes after 5 seconds',
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
}

# Merged rows with no visible change.
NO_VISIBLE_CHANGE = set()
# Merged rows that are tests or internal code only: no bullet, no hand check.
TEST_ONLY = set()
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
        self.assertEqual(schema_version(), SCHEMA, "1.0.7 stays at layout 20")

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

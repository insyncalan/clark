"""clark 1.0.9's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.9 row.

Run: python3 dev/run_tests.py test_v109

Same shape as test_v108. COVERED holds every merged row with something to see; TEST_ONLY holds the rest.
The notes' own rules run against dev/release-notes/1.0.9-plain.md. Everything that reads the hand-check sheet, and the cut
tests, skip until the cut commit sets 1.0.9 in src/clark/__init__.py; from then on both files must exist, every row in the sheet's
status table is MERGED or DROPPED, and no WAIT heading is left in the notes. The data layout is 24 (no step came with 1.0.9).
"""
import ast
import os
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.9"
SCHEMA = 24              # the layout 1.0.8 ended at; 1.0.9 took no step

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ('665',
     'On a Mac, in View and in Edit, press Cmd+Option+S. It works in both. Then open a work item and press it again. Settings opens the first time; with a record open nothing happens.',
     'test_settings_key::SettingsKey::test_the_chord_opens_settings_at_1400_and_900'),
    ('1113',
     'In Edit open the Work items section of the Dashboard. The Caption box is under the list and each listed row has the client eye; with every eye off the section says it is left out of the published page.',
     'test_wil_eye::Eye::test_a_list_of_only_hidden_items_says_it_is_left_out_of_the_published_page'),
    ('1143',
     'Export to Excel on a project whose name is long enough to be cut. The cut name ends in no dot and no space before the date.',
     'test_export_name_trailing_dot_1143::TrailingDot::test_a_cut_that_ends_on_a_dot_leaves_no_dot_before_the_code'),
    ('1168',
     'In Settings switch Motion on and off. A quiet toast with Undo, and Undo puts it back.',
     'test_settings_save_1115::SaveAtOnce::test_item_1168_the_motion_switch_says_its_new_state_in_a_toast_with_one_undo'),
    ('1169',
     'In Settings press Tab to the Spacing choice, a Gantt box and the Feedback box. Each shows the 2 px house focus ring.',
     'test_settings_focus_ring_1169::SettingsFocusRing::test_each_control_has_the_two_pixel_ring_at_both_widths_in_both_looks'),
    ('1170',
     'In Settings click the search box and press Tab. A Skip to settings button comes next; Enter moves focus to the first card.',
     'test_settings_skip_1170::Skip::test_S_the_skip_link_is_the_next_tab_stop_after_the_search_box_and_reaches_your_name'),
    ('1171',
     'Export to Excel and open the file. No visible metadata sheet; it is hidden and protected. The import reads it as information only.',
     'test_excel_metadata_1171::Sheet::test_very_hidden_protected_with_four_fields_and_row_hashes_only'),
    ('1174',
     'In Edit, on a project holding a stored Needs from you section, use Move up and Move down. The Dashboard draws no Needs section and Move counts only the sections drawn.',
     'test_edit_needs_section_hidden::MoveNextToNeeds::test_move_up_on_the_section_after_needs_passes_the_one_that_shows'),
    ('1175',
     'On the Milestones Timeline hover and Tab to the end marks whose names are hidden. The tip is drawn whole, above the shown names and inside the timeline box.',
     'test_timeline_tip_1175::Tip::test_every_hidden_name_tip_is_above_the_labels_by_focus'),
    ('1176',
     'In Edit, choose project A and then project B from the project name in the header. The work items, milestones and project data follow each choice, and B\'s items never show under A.',
     'test_project_header_switch_1176::HeaderSwitch::test_C_select_A_then_B_then_A_the_page_follows_and_B_items_are_never_under_A'),
    ('1177',
     'In Edit open the Dashboard. One slim header stays at the top when you scroll; its project name says Click to change project and opens the project list, and the View and Edit icons float just under it.',
     'test_project_header_switch_1176::HeaderSwitch::test_C_the_header_name_is_the_one_control_and_says_click_to_change'),
    ('1188',
     'Create a new project and open its Dashboard in Edit. Current state is the first section, a text section with an empty body and a short guiding line.',
     'test_current_state_empty::Data::test_the_store_seeds_an_empty_body_and_the_line_is_kept_once_as_a_constant'),
    ('1193',
     'In a new project open Summary, This week and Next week in Edit. Each is empty with its own guiding line; the published page shows none.',
     'test_current_state_empty::Data::test_item_1193_new_project_seed_gives_all_four_text_sections_an_empty_body'),
    ('1196',
     'Open Work items at 1400 and 900. No More actions button ends a row; the Menu key and right-click open the row menu.',
     'test_row_menu::Menu::test_row_1196_no_more_actions_button_ends_a_row_and_the_menu_keys_still_open_the_menu_at_1400_and_900'),
    ('1200',
     'Open Settings at 1400 and 900, light and dark. Soft side-menu rows, one edge colour, example text in empty boxes, the Backups path as text with a Use button.',
     'test_settings_look_1200::SettingsLook::test_the_look_at_1400_and_900'),
    ('1202',
     'Open a work item peek. It starts below the top bar, 640 px wide, and cannot be dragged wider than the window minus 32 px.',
     'test_peek_width_1202::WidthRule::test_the_most_is_the_window_minus_32'),
]

# The first words of each bullet, to find it by: {row id: start of its bullet}.
BULLET_STARTS = {
    '665': 'Command+Option+S opens Settings',
    '1170': 'A Skip to settings button comes',
    '1169': 'Spacing, the Gantt boxes and the Feedback',
    '1171': 'A full Excel export carries a hidden',
    '1143': 'The Excel export file name no longer',
    '1176': 'Choosing another project from the project name',
    '1177': 'On the Dashboard, the top bar and the banner',
    '1188': 'A new project starts with a blank Current',
    '1193': 'In a new project, Summary, This week',
    '1113': 'The Caption box moves under the list',
    '1202': 'A peek now opens 640 px wide',
    '1175': 'The hover or focus tip of a milestone',
    '1200': 'The Settings page has a new look',
    '1168': 'The Motion switch says',
    '1196': 'The duplicate ... (More actions) button',
    '1174': 'Move, drag and Add after skip',
}
assert len(set(BULLET_STARTS.values())) == len(BULLET_STARTS)

# Merged rows whose note is another row's bullet: none.
NO_BULLET = set()
# Bullets for merged work that has no plan row in COVERED: the version check and the one test line.
EXTRA_BULLET_STARTS = ('A pre-release path (v1.0.8-rc10)', 'Several tests that failed on a Mac')

# Merged rows that are tests or internal code only: no bullet, no hand check.
TEST_ONLY = {'1147', '1151', '1156', '1167', '1172', '1173'}
# No user note, and no hand check, once merged.
NO_NOTE_WHEN_MERGED = set()

# Rows with one part merged and the rest open: none.
PARTLY_MERGED = set()

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
    """True from the cut on: once the version says 1.0.9 every merged row needs its bullet. V109_FINAL=1 asks for it earlier."""
    return found_version == VERSION or (os.environ.get("V109_FINAL") if env is None else env) == "1"


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

    def test_each_check_is_listed_once(self):
        checks = [c for _, c, _ in COVERED]
        self.assertTrue(checks)
        self.assertEqual(sorted(c for c in set(checks) if checks.count(c) > 1), [])

    def test_the_sheet_has_a_row_for_every_covered_item(self):
        sheet = read_sheet()
        for item in {i for i, _, _ in COVERED}:
            self.assertIn(item, sheet, f"{item} has no row on the hand-check sheet")


class StatusTable(unittest.TestCase):
    """The status table of every 1.0.9 row, between its two markers in the sheet. Skips until the cut."""

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

    def test_a_merged_row_has_a_hand_check_row_or_is_listed_as_test_only(self):
        sheet = read_sheet()
        covered = {i.lstrip("#") for i, _, _ in COVERED}
        for item, title, status, pr in table_rows(sheet):
            if status != "MERGED":
                continue
            self.assertTrue(item in TEST_ONLY or item in NO_NOTE_WHEN_MERGED or item in covered,
                            f"{item} is MERGED: give it a covering test and a hand-check row, or list it in TEST_ONLY")
            self.assertTrue(pr, f"{item} is MERGED and has no pull request in the table")

    def test_a_covered_row_is_merged(self):
        merged = {r[0] for r in table_rows(read_sheet()) if r[2] == "MERGED"}
        for item, check, where in COVERED:
            self.assertIn(item.lstrip("#"), merged | PARTLY_MERGED, f"{item} is covered but not MERGED in the table")


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
        """A merged row may lack its bullet until the cut; from the cut (version 1.0.9, which this class runs at) exactly one for each is demanded."""
        covered = {i.lstrip("#") for i, _, _ in COVERED}
        self.assertEqual(wait_bullets(self.text), [], "no bullet waits at the cut")
        self.assertNotRegex(self.text, r"(?m)^- Issue \d+ ", "no authoring tag is left in a bullet")
        self.assertEqual(bullet_problems(bullets(self.text), covered, bullets_are_final(version()), EXTRA_BULLET_STARTS), [])

    def test_the_notes_hold_no_status_table_and_no_row_ids(self):
        self.assertNotIn(BEGIN, self.text)
        self.assertNotRegex(self.text, r"(?m)^\| ")


class BulletsFinalCheck(unittest.TestCase):
    """Self-test of the cut-time check: a merged row without a bullet fails with V109_FINAL=1 and passes without it."""

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
        self.assertTrue(bullets_are_final(VERSION, env=""), "version 1.0.9 demands every bullet, with no env set")
        self.assertFalse(bullets_are_final("1.0.8", env=""), "before the cut a missing bullet is tolerated")
        self.assertTrue(bullets_are_final("1.0.8", env="1"), "V109_FINAL=1 asks for it early")

    def test_dropping_a_bullet_fails_in_the_cut_state(self):
        found = ["- Alpha one"]                      # Beta's bullet dropped
        self.assertTrue(bullet_problems(found, self.ROWS, bullets_are_final(VERSION, env="")))
        self.assertEqual(bullet_problems(found, self.ROWS, bullets_are_final("1.0.8", env="")), [])


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
        self.assertEqual(schema_version(), SCHEMA, "1.0.9 ends at layout 24")

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


if __name__ == "__main__":
    unittest.main()

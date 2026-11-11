"""clark 1.0.5's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.5 row.

Run: python3 dev/run_tests.py test_v105

Same shape as test_v104 (bullets for unmerged rows wait under a WAIT heading). All thirteen 1.0.5 rows are IN REVIEW today (none is merged), so COVERED is empty and every visible row is in WAITING
(no pull request yet). The notes are written ahead of the merges. The cut tests skip until the cut commit sets 1.0.5; from then on a
row that is not MERGED or DROPPED fails, a WAITING row whose marker has landed fails until it moves to COVERED, and the approved
manual download lines must stay in. The data layout moves to 20 (#944 T1, projects.brand).
Rows 836 (PR 942) and 963 (PR 941) are tests or internal code only: in TEST_ONLY, no bullet. PR 943 (NOTICE.md) has no row. Rows are now 13.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.5"
SCHEMA = 22              # 1.0.3 was layout 17; 1.0.4 ended at 19 (row 926); 1.0.5 ended at 20 (#944 T1, projects.brand); 1.0.7 moves it to 21 (row 1061, Planned 2026) and 22 (row 1068, report_sections.type takes gantttable)

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#804", "The View or Edit switch is on the Dashboard and the Gantt page only.",
     "test_filter_line_page::Line::test_the_chosen_filter_and_the_view_edit_toggle_look_different_from_the_others"),
    ("#838", "The Help pages match the program again.",
     "test_help_parity::WhatIsShownIsOnThePage::test_every_label_in_a_shown_entry_is_on_the_page"),
    ("#944", "The data file moves to layout 20.",
     "test_store_brand_migration::Migrating::test_a_layout_19_file_opens_keeps_every_value_and_gets_generic"),
    ("#961", "The zip holds START-HERE.md.",
     "test_package::MacZipTest::test_the_built_zip_carries_the_md_start_file_and_not_the_txt_one"),
    ("#966", "Excel import stops a workbook that is too large to read safely.",
     "test_excel_import_caps::Caps::test_a_sheet_that_says_a1_b2_and_holds_too_many_cells_inside_the_reach_is_refused_before_the_load"),
    ("#968", "A second Esc while a menu is closing is no longer ignored.",
     "test_hand_over::Page::test_esc_during_a_menu_leave_still_leaves_pick_mode"),
    ("#970", "Rows added or removed fade or fold.",
     "test_motion_rows::MotionRows::test_a_deleted_row_fades_in_place_then_leaves_and_an_added_row_rises"),
    ("#971", "The Gantt bars grow in once per page open or data folder change.",
     "test_motion_gantt_bars::Bars::test_bars_grow_once_per_page_open_or_project_not_per_mount"),
    ("#975", "Starting clark while another folder or version runs stops with a plain message.",
     "test_launch_running::Running::test_another_folder_stops_with_the_words_and_changes_nothing"),
    ("#996", "The View | Edit switch focus ring is clear in dark.",
     "test_pill_focus_ring::PillFocusRing::test_the_chosen_half_of_the_pill_has_a_dark_ring_3_to_1_on_its_aqua_at_both_widths_in_both_looks"),
]

# The first sentence of each bullet, to find it by.
BULLET_STARTS = {
    "804": 'The View | Edit switch is shown only on the Dashboard and the Gantt page.',
    "838": 'The Help pages are corrected where they no longer matched the program: the profile circle menu, Publish and Published reports, Import from Excel, the Movement switch on Milestones and the Gantt template.',
    "944": 'The data file moves to layout 20.',
    "961": 'The download holds a start file named START-HERE.md, where 1.0.4 held START-HERE.txt.',
    "966": 'Import from Excel stops a workbook that declares a huge sheet or holds one very large cell, instead of using up the memory of the computer.',
    "968": 'A second Esc pressed while a menu is still fading out now closes the menu in Board, Hand over and Bulk, where it was ignored.',
    "970": 'A row added to a list fades in, and a row taken away fades out.',
    "971": 'The Gantt bars grow in from the left once, when the page opens.',
    "975": 'When clark is already running from another folder or another version, starting this one tells you so, changes nothing and says how to quit the other one (press Ctrl+C in its Terminal window).',
    "996": 'The focus ring on the View | Edit switch can be seen in dark mode.',
}

# Merged rows with no visible change. None merged yet. 
NO_VISIBLE_CHANGE = set()
TEST_ONLY = {"963", "974"}   # 836 step 3 (PR 942): internal code, no new words; 963 (PR 941): tests only. No bullet, no hand check.
# No user note, and no hand check, once merged. 972 is not merged yet, so it cannot sit in NO_VISIBLE_CHANGE (that set must be MERGED).
NO_NOTE_WHEN_MERGED = {"972"}

# Rows with one part merged and the rest open: the merged part is covered here, the row stays IN REVIEW in the table. None in 1.0.5.
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
    """The status table of every 1.0.5 row, between its two markers in the sheet."""

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

    def test_the_title_the_beta_line_and_the_update_sentence(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("This is the 1.0 build. It is still marked Beta: it works and is tested, but expect rough edges and changes between versions.", self.text)
        self.assertIn("Updating from inside clark works from 1.0.4 to this version. To move from 1.0.3 or earlier to 1.0.5, install by hand as described under Known limits.", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_notes_do_not_name_a_newer_clark(self):
        self.assertEqual(self.text.count("This data needs a newer clark. Nothing was changed. Install the latest clark, then try again."), 1, "the layout-20 bullet (#944) quotes the refusal once, as the 1.0.4 notes did")      # 1.0.5 moves the layout, so it now says what an older clark does
        self.assertNotIn("Read this first", self.text)

    def test_the_known_limits_carry_the_by_hand_install_and_the_demo_limit(self):
        self.assertIn("## Known limits", self.text)
        self.assertIn("From 1.0.3 or earlier, install by hand: the update inside those versions does not accept a download that holds START-HERE.md. Quit clark first, then rename the old clark folder. Then unzip the download into a fresh empty folder. A plain unzip over the old folder merges old and new files. Your projects stay where they are.", self.text)
        self.assertIn("Editing a demo project keeps it", self.text)

    def test_the_approved_manual_download_lines_are_present_and_the_placeholder_is_gone(self):
        self.assertIn("- To move to 1.0.5 from 1.0.4, update from inside clark. From 1.0.3 or earlier, install by hand: the update inside those versions does not accept a download that holds START-HERE.md. Quit clark first, then rename the old clark folder. Then unzip the download into a fresh empty folder. A plain unzip over the old folder merges old and new files. Your projects stay where they are.", self.text)
        self.assertIn("- Updating from inside clark works from 1.0.4 to this version. To move from 1.0.3 or earlier to 1.0.5, install by hand as described under Known limits.", self.text)
        self.assertNotIn("MANUAL DOWNLOAD LINE", self.text)
        self.assertNotIn("pending approval", self.text)

    def test_a_date_in_the_notes_is_day_first_and_no_one_is_named(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")
        self.assertNotRegex(self.text, r"team-[a-z]+-\d+", "a branch name is in the notes")

    def test_there_is_no_draft_marker_in_the_notes_or_the_sheet(self):
        for text in (self.text, read_sheet()):
            self.assertNotIn("DRAFT", text)

    def test_nobody_says_the_head(self):
        for text in (self.text, read_sheet()):
            self.assertNotRegex(text, r"(?i)\bthe head\b")

    def test_a_bullet_is_only_for_a_merged_visible_row_and_none_waits(self):
        found = bullets(self.text)
        covered = {i.lstrip("#") for i, _, _ in COVERED}
        self.assertEqual(wait_bullets(self.text), [], "no bullet waits at the cut")
        self.assertEqual(len(found), len(covered), "one bullet for each merged visible row, and no other")
        for item in covered:
            self.assertEqual(sum(1 for b in found if b.startswith("- " + BULLET_STARTS[item])), 1, "%s has one bullet" % item)
        self.assertNotRegex(self.text, r"(?m)^- Issue \d+ ", "no authoring tag is left in a bullet")
        self.assertNotIn("focus-ring pin", self.text)
        self.assertNotIn("checked for Gantt details", self.text)
        self.assertNotIn("and says so", self.text)
        self.assertIn(
            "- Import from Excel stops a workbook that declares a huge sheet or holds one very large cell, instead of using up the memory of the computer.",
            found,
        )

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
        self.assertEqual(schema_version(), SCHEMA, "layout 22: row 1068 let a section be of type gantttable (1.0.5 ended at 20, #944 T1)")

    def test_a_waiting_row_whose_pull_request_has_landed_has_been_moved_to_covered(self):
        self.cut_made()
        out = [f"{item} {pr}: it is in main now; give it a covering test in COVERED, a line in the notes and a row in the sheet"
               for item, check, pr, path, marker in WAITING if landed(path, marker)]
        self.assertEqual(out, [])

    def test_at_the_cut_every_row_is_merged_or_dropped(self):
        """Fails from the cut until each of the thirteen rows has merged (or been dropped and taken out of the notes)."""
        self.cut_made()
        out = [f"{item} is {status}" for item, title, status, pr in table_rows(read_sheet()) if status not in ("MERGED", "DROPPED")]
        self.assertEqual(out, [])

    def test_at_the_cut_the_wait_heading_is_gone(self):
        self.cut_made()
        self.assertNotIn(WAIT_HEAD, read_notes(), "delete the WAIT heading and move its bullets under What is new, changed or fixed")

    def test_at_the_cut_the_manual_download_line_is_approved_wording(self):
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

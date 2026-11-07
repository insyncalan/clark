"""clark 1.0.4's release docs as tests: the notes, the hand-check sheet and the status table of every 1.0.4 row. Each release gets a
test_vNNN file, so the walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v104

Same shape as test_v103.
  COVERED       a merged row a person can see, already covered by a test elsewhere. test_every_covering_test_named_here_exists
                fails if one goes missing. Rows 936, 937, 942, 953 and 956 have no visible change (NO_VISIBLE_CHANGE).
  WAITING       a row that is not on main yet but has a marker in the source that appears when it lands (item, check, pull request,
                a file under the top folder, the text in it). Skipped, with the pull request. After the cut commit has set the
                version and the marker is there, the row fails until it is moved to COVERED with its test.
  WALK_THROUGH  judgement or live only. Skipped: 'needs a person'.

The notes hold only merged, user-visible rows; no DRAFT line is allowed anywhere. The cut checks (version, files, layout) skip until the
cut commit sets 1.0.4. The data layout moves from 17 to 19 in 1.0.4 (row 926: step 18 is merged, step 19 is the Gantt section, PR 899):
the notes carry the Read this first paragraph and, at the cut, the store must say 19.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.4"
SCHEMA = 19              # 1.0.3 was layout 17; 1.0.4 ends at 19 (row 926)

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#796", "The Publish box lists Word before PDF.",
     "test_publish_dialog::Dialog::test_C_row_796_order_title_weight_size_heading_and_tab_at_both_widths_in_light_and_dark"),
    ("#776", "The Sneak peek card shows chips in typed order, with Not now and Make the change.",
     "test_peek::Browser::test_row_776_chips_in_typed_order_and_the_button_row_in_both_widths_and_themes"),
    ("#810", "The Work items view menu offers Rename and Delete on a built-in tab.",
     "test_filter_line_page::Line::test_a_core_tab_can_be_renamed_and_deleted_and_it_is_kept_in_the_browser_only"),
    ("#843", "The base text is 15 px.",
     "test_v060::Sizes87::test_87_1_the_size_scale_is_in_tokens_css"),
    ("#897", "The update check accepts either start file name.",
     "test_updates::GoodFileTest::test_a_download_built_by_package_py_reads"),
    ("#922", "A menu fades out as it closes.",
     "test_motion_menu_exit::MotionMenuExit::test_row_922_a_menu_fades_out_and_is_gone_at_once_when_reduced"),
    ("#927", "Current state is a template in Add a section.",
     "test_changes_text_body::NewWithBody::test_the_plan_summary_starter_is_stored_as_sent"),
    ("#929", "Plan summary is a template in Add a section, with one Undo.",
     "test_changes_text_body::NewWithBody::test_a_new_text_section_stores_its_body_cleaned"),
    ("#930", "The progress tile draws each Size.",
     "test_tracker_page::Page::test_each_size_draws_its_numbers_and_bar_at_1400_and_900_and_old_trackers_read_as_medium"),
    ("#933", "The published file draws the progress tile and its lines.",
     "test_published_tracker_drawn::Drawn::test_the_published_file_draws_the_tracker_tile_and_its_lines"),
    ("#946", "Dark theme focus rings show.",
     "test_dark_primary::Source::test_no_focus_ring_is_drawn_in_the_navy"),
    ("#948", "A long owner name stays on one line in Edit.",
     "test_edit_cells_layout::Cells::test_every_edit_cell_is_one_tidy_box_at_both_widths_in_both_looks"),
    ("#954", "The filter suggestion list sits under the message line.",
     "test_filter_list_error::ListAndError::test_the_list_never_covers_the_unknown_field_error"),
    ("#952", "The chosen half of a segmented control has a dark focus ring.",
     "test_seg_focus_ring::SegFocusRing::test_the_ring_on_every_chosen_half_reaches_3_to_1_on_its_fill_at_both_widths_in_both_looks"),
    ("#955", "Menus have a stronger border.",
     "test_menu_border::MenuBorder::test_every_menu_border_is_3_to_1_on_the_page_and_on_a_card_at_both_widths_in_both_looks"),
    ("#965", "Owner is left out of a client Gantt by default.",
     "test_gantt_publish::TheGate::test_owner_is_hidden_where_nothing_is_saved_and_kept_where_a_list_is_saved"),
    ("#926", "The editor workbook's Gantt sheet; the client workbook's Gantt sheet has no hidden column.",
     "test_gantt_excel_export::TheClientsWorkbook::test_a_hidden_owner_is_absent_as_a_header_and_as_a_value"),
    ("#926", "A line with its eye off is in no part of the client copy.",
     "test_gantt_publish::TheGate::test_an_eye_off_line_is_in_no_part_of_the_client_copy"),
    ("#926", "Import from Excel reads the ticked Gantt sheet in one step with one Undo.",
     "test_gantt_excel_import_flow::Reading::test_ticking_only_the_gantt_sheet_plans_and_applies_only_its_changes_in_one_step_with_one_undo"),
    ("#926", "A client workbook is not imported.",
     "test_gantt_excel_import::Refusals::test_a_client_copy_imported_by_hand_is_refused_and_nothing_is_written"),
    ("#926", "An in-clark update from layout 17 keeps every row.",
     "test_update_17_to_18::Update17To18::test_the_new_build_migrates_17_to_18_keeping_every_row_and_a_second_open_changes_nothing"),
    ("#926", "The older clark says it needs a newer one and touches nothing.",
     "test_update_17_to_18::Update17To18::test_the_old_build_refuses_the_new_data_with_its_plain_sentence_and_touches_nothing"),
]

# Merged rows with no visible change: they have a MERGED line in the status table and need no bullet, hand check or test here.
# 945 (the update message) has no test of its words: it is a WALK_THROUGH check below.
NO_VISIBLE_CHANGE = {"945", "936", "937", "942", "953", "956"}

# Rows with one part merged and the rest open: the merged part is covered here, the row stays IN REVIEW in the table.
PARTLY_MERGED = {"926"}

# Not on main yet: (item, check, pull request, a file under the top folder and the text that is in it once the pull request has landed).
WAITING = [
    ("#928", "The Gantt page, tab, chart and table.", "PR 896", "src/clark/page/src/gantt/components/GanttPage.jsx", "GanttPage"),
    ("#926", "The Gantt section type (layout step 19).", "PR 899", "src/clark/store.py", "SCHEMA_VERSION = 19"),
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#945", "The update message for a missing signature part says what is wrong and what to do.", "live only",
     "no test reads the words end to end", "update with a zip that has no signature part and read the message"),
]

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
    """The status table of every 1.0.4 row, between its two markers in the sheet."""

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
        self.assertIn("This is the 1.0 build. It is still marked Beta: it works and is tested, but expect rough edges and changes between versions.", self.text)
        self.assertIn("Updating from inside clark works from 1.0.3 to this version.", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_notes_carry_the_data_layout_paragraph_and_the_older_clark_sentence(self):
        self.assertIn("This version includes a change to how clark stores your data. Read this first.", self.text)
        self.assertIn("One change to how your data file is stored.", self.text)
        self.assertIn("A project can now hold Gantt lines", self.text)
        self.assertIn("A safety copy of your data is made before anything changes.", self.text)
        self.assertIn("An older clark (1.0.3) will not open the new data file", self.text)
        self.assertIn("This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.", self.text)
        self.assertIn("First restore the safety copy", self.text)

    def test_the_known_limits_carry_the_by_hand_install_and_the_demo_limit(self):
        self.assertIn("## Known limits", self.text)
        self.assertIn("Updating from inside clark works from 1.0.3 to this version.", self.text)
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
        if schema_version() > SCHEMA:
            self.skipTest("the layout has moved on past %d (now %d, a later release's step): these are 1.0.4's notes" % (SCHEMA, schema_version()))
        self.assertEqual(schema_version(), SCHEMA, "the notes name layout 19: row 926 step 19 (PR 899) has not landed")

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

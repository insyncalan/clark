"""clark 0.4's hand checks as tests. Each release gets a test_vNNN file, so the walk-through keeps only the judgement and
live-only checks.

Run: python3 dev/run_tests.py test_v040

Same shape as test_v030. Headless and fast: no Chrome is started here. What a person would check in the v0.4 items, and where:
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
VERSION = "0.4.0"

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#96", "The Add a section box offers only the section types the store takes (all first-slice templates are filled in)", "test_templates::Logic::test_the_first_slice_is_all_there_with_everything_filled_in"),
    ("#96", "A template is placeable only when it is ready", "test_templates::Logic::test_a_stub_type_is_placeable_only_when_ready"),
    ("#96", "A file added to a Documents and links section is copied into Report files, in one step with one Undo",
     "test_section_file_route::Route::test_the_file_is_copied_and_added_in_one_step_and_undo_leaves_the_copy"),
    ("#44a", "The Milestones Calendar opens on Month", "test_calendar_scales::Scale::test_month_is_the_default"),
    ("#45", "The Use cases section lists every use case of the project in order", "test_use_cases_read::WhatItReturns::test_the_project_use_cases_in_order"),
    ("#164", "A use case field changes in one step with one Undo", "test_changes_use_cases::Edit::test_each_field_changes_in_one_step_with_undo"),
    ("#123", "History says who, how, when and from what to what",
     "test_changes_use_cases::Edit::test_history_says_who_how_when_and_from_to_and_the_undo_too"),
    ("#42", "The peek has an Activity tab", "test_peek_activity::BuiltPages::test_the_activity_tab_is_in_the_served_page_only"),
    ("#85b", "The Excel Cover sheet lists the title, the sections and the about block",
     "test_excel_cover::TheLines::test_order_title_then_the_sections_then_the_about_block"),
    ("#85", "The Excel header and the ID and title columns are frozen on every sheet",
     "test_excel_format::Formatting::test_header_and_the_id_and_title_columns_are_frozen_on_every_sheet"),
    ("#85", "Every Excel data sheet is in the look's office font",
     "test_excel_format::Formatting::test_every_data_sheet_is_in_the_looks_office_font_header_body_and_the_empty_rows"),
    ("#85", "An unchanged export imports as no changes",
     "test_excel_roundtrip::Reading::test_an_unchanged_export_imports_as_no_changes_and_nothing_is_ignored"),
    ("#111", "Settings > Safety lists the backups newest first", "test_safety::TheList::test_newest_first_in_words_with_size_status_and_the_number_kept"),
    ("#110", "Logs and diagnostics: a report needs the token", "test_log_wiring::PageErrorRoute::test_the_token_is_checked_and_a_large_body_refused"),
    ("#98", "The brand picture is served from its fixed names", "test_brand_picture::Route::test_each_fixed_name_is_served_with_its_own_type_and_the_security_headers"),
    ("V-E keys", "V and E switch between View and Edit", "test_single_keys::PageKeys::test_letters_work_when_on_do_nothing_when_off_and_work_again_with_no_reload"),
    ("#203", "The Work items cells in Edit are tidy boxes", "test_edit_cells_layout::Cells::test_every_edit_cell_is_one_tidy_box_at_both_widths_in_both_looks"),
    ("Esc", "An inline date closes on one Esc", "test_inline_edits::Live::test_every_inline_date_closes_on_one_esc_a_click_away_or_tab_and_changes_nothing"),
    ("#182", "A bad idle-timer value keeps the default", "test_idle::Environment::test_number_refuses_non_finite_values"),
    ("plain errors", "A broken or odd request gets a plain-words reply", "test_server_error_pages::PlainPages::test_the_wording_is_plain"),
]

# Not on main (or no test found): (item, check, the question or where it is being built).
WAITING = [
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#96", "Dragging a section places it full width or beside another, and feels right", "judgement",
     "feel, not a pass or fail", "In Edit, drag a section between rows and onto the left and right half of another."),
    ("#44a", "The Calendar and Timeline switch reads well, with its icon and word", "judgement",
     "only a person can say it looks right", "Open Milestones, switch between Timeline and Calendar, then try Week, Month and Quarter."),
    ("#85", "The Excel export opens in Excel with the brand font and frozen header rows", "live only",
     "needs Excel", "Export the demo project, open it in Excel, scroll a data sheet and read the Cover sheet."),
    ("#85", "An exported Excel file that is edited, saved again and imported still matches its export", "live only",
     "needs Excel", "Change a cell in Excel, save, import it, and check the changes listed are only yours."),
    ("#96", "Each template can be added, the Figures As of box refuses a bad date, and a file can be added to a Documents and links section",
     "judgement", "only a person can see that each result looks right",
     "In Edit, Add a section: add one of each template; type 31-02-2026 in a Figures As of box and read the words; in a Documents and links section add a file and check it is in the client folder's Report files folder."),
    ("#111", "Settings > Safety previews and restores a backup", "judgement",
     "the owner reads the words and decides they are clear", "Open Settings > Safety, preview a backup and read it; restore only a demo copy."),
    ("#110", "Copy diagnostics gives a report with no client content", "judgement",
     "only a person can read the report for client content", "Settings > Logs and diagnostics: choose Debug, work for a minute, Copy diagnostics, read it."),
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
        if not found or not found.group(1).startswith("0.4"):
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
        t.__name__ = "test_%s_%d_needs_a_person" % (re.sub(r"\W", "_", item), i)
        t.__doc__ = check
        setattr(Walk, t.__name__, t)
    for i, (item, check, q) in enumerate(WAITING):
        def w(self, _m=f"waiting: {q}"):
            self.skipTest(_m)
        w.__name__ = "test_%s_%d_waiting" % (re.sub(r"\W", "_", item), i)
        w.__doc__ = check
        setattr(Walk, w.__name__, w)


class Walk(unittest.TestCase):
    """One skipped test per walk-through or waiting check, so the run lists them by name with the reason."""


_skips()

if __name__ == "__main__":
    unittest.main()

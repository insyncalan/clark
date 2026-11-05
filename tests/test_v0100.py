"""clark 0.10's hand checks as tests: the 0.10 items that have merged to main after 0.9.0. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v0100

Same shape as test_v090.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written after 0.9.0 was published (tag v0.9.0, 9c12a3dd), from origin/main on 05-11-2026: everything merged after the tag.
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.10.0, then fail if wrong.
The notes' own rules (title, the Beta line, plain words, the data-layout paragraph) are read from the tree now.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.10.0"
SCHEMA_AT_0_9_0 = 15     # 0.9.0 reads layout 15; a layout step after it makes the notes say so

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#660", "A text box opens at three lines, grows as you type, keeps one blank row under the last line and has a handle in the bottom right corner (the Ask box).",
     "test_item_660_editors::Ask::test_ask_box"),
    ("#660", "The rich editor and the draft email body have a floor and a handle.",
     "test_item_660_editors::Rich::test_rich_editor_and_draft_email_body_have_a_floor_and_a_handle"),
    ("#660", "The published page has no text box and none of the grow code.",
     "test_item_660_editors::Published::test_the_published_page_has_no_textarea_and_no_useGrow"),
    ("#656", "With no project open Settings opens with Add project and Import workbook (Edit); the other four screens still say No project open.",
     "test_settings_no_project::Browser::test_settings_opens_with_no_project_and_has_add_project_and_import_workbook"),
    ("#656", "Add project with none makes the project and opens it on Work items.",
     "test_settings_no_project::Browser::test_add_project_with_none_makes_it_and_opens_it_on_work_items"),
    ("#386", "After an update the undo takes the data copy made at the layout the update started from, never the newest copy by name; with none it refuses.",
     "test_update_migration::Migrated::test_a_newer_copy_of_another_layout_is_not_taken_for_the_migration_copy"),
    ("#386", "With no copy of the right layout none is recorded and the undo is refused.",
     "test_update_migration::Migrated::test_with_no_copy_of_the_right_layout_none_is_recorded_and_the_undo_is_refused"),
    ("#388", "A publish that replaces a link and cannot put the old report back says so, and never removes a file that is not its own.",
     "test_publication_numbers::ThroughThePublisher::test_put_link_back_reports_a_foreign_file_it_could_not_put_back"),
    ("#388", "When the old copy cannot be cleared the message says so in plain words, not a bare error.",
     "test_publication_numbers::ThroughThePublisher::test_put_link_back_raises_publish_error_when_the_aside_name_cannot_be_removed"),
    ("#663", "A notice that arrives while a box is open is held back with the page behind it, and let go when the box closes.",
     "test_modal_layers::Layers::test_a_toast_that_arrives_while_the_box_is_open_is_inert_and_is_released_on_close"),
    ("#663", "The same in the use case box on the Dashboard.",
     "test_uc_dashboard_edit::Edit::test_a_toast_that_arrives_while_the_box_is_open_is_inert_and_is_released_on_close"),
    ("#680", "The clark name in the top bar is the 24 px heading size.",
     "test_size_scale::Scale::test_headings_sit_on_the_heading_sizes"),
    ("#444", "An imported workbook's links (linked workbooks, hyperlinks, linked images) are never fetched or opened.",
     "test_excel_import_no_fetch::ExternalLinksAreNeverFetched::test_a_check_and_an_apply_never_connect_or_open_a_link_and_import_the_row_as_without_links"),
    ("#534", "The report bar's hooks sit above its early return.",
     "test_report_bar::HookOrder::test_no_hook_comes_after_the_early_return_null"),
    ("#651", "The shared growth check's limit sits above linear and below n to the power 1.5.",
     "test_growth::TheGrowthCheckTellsLinearFromQuadratic::test_the_limit_sits_above_linear_and_below_n_to_the_power_one_and_a_half"),
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
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
    no lower-case 'ask clark' in a heading, and the data-layout paragraph only when the layout has changed since 0.9.0."""

    def setUp(self):
        self.text = (ROOT / "dev" / "release-notes" / (VERSION + "-plain.md")).read_text(encoding="utf-8")

    def test_the_title_and_the_beta_line(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("Beta means the whole of clark is Beta until version 1.0.", self.text)

    def test_no_banned_word_and_no_lower_case_ask_clark_in_a_heading(self):
        for word in BANNED_WORDS:
            self.assertIsNone(re.search(r"(?i)\b%s\b" % word, self.text), word)
        for line in self.text.splitlines():
            if line.startswith("#"):
                self.assertNotIn("ask clark", line)

    def test_the_data_layout_paragraph_is_there_only_when_the_layout_changed(self):
        if version() != VERSION:        # a cut check: live only at its own version (#709: 1.0.1 has a layout step of its own, and these notes are not its notes)
            self.skipTest(f"the layout moves on after {VERSION} (now {schema_version()}), and a later release says so in its own notes")
        said = "This version includes a change to how clark stores your data" in self.text
        self.assertEqual(said, schema_version() != SCHEMA_AT_0_9_0,
                         "the notes must say a layout step is in exactly when SCHEMA_VERSION in store.py is not %d" % SCHEMA_AT_0_9_0)

    def test_a_date_in_the_notes_is_day_first(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 0.10.1 and later have their own test_vNNN
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

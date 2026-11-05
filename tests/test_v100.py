"""clark 1.0's hand checks as tests: the 1.0 items (the Help overhaul) that have merged after 0.11.0. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v100

Same shape as test_v0110.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written after 0.11.0 was published (tag v0.11.0), from the 1.0 release branch on 05-11-2026: everything merged after the tag.
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 1.0.0, then fail if wrong.
The notes' own rules (title with (Beta), plain words, the data-layout paragraph) are read from the tree now.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "1.0.0"
SCHEMA_AT_0_9_0 = 15     # 0.9.0 reads layout 15; a layout step after it makes the notes say so

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#642", "Start here shows the five jobs and the undo link, in the order the owner gave.",
     "test_help_navigation::TheFiveJobs::test_all_five_jobs_and_the_undo_link_are_shown"),
    ("#642", "The contents list and the What next links point at shown places only.",
     "test_help_navigation::WhatNext::test_a_held_place_is_never_a_what_next_link"),
    ("#642", "The nine guides are shipped with five to eight numbered steps, a result line and next links.",
     "test_help_guides::ShippedSource::test_the_nine_guides_are_shipped_and_hold_the_shape"),
    ("#642", "The Hand an item over, Save a view, past-day Dashboard and Back up guides name controls the page has.",
     "test_help_guides_more::TheFourGuides::test_the_controls_the_steps_name_are_the_ones_the_page_has"),
    ("#642", "The Excel and Publish guides name controls the page has.",
     "test_help_guides_excel_publish::TheThreeGuides::test_the_controls_the_steps_name_are_the_ones_the_page_has"),
    ("#642", "The pictures: each is declared, listed, pinned and sits on the step that names its control.",
     "test_help_guide_pictures::TheDeclaredPictures::test_every_listed_shot_is_declared_and_used_once_with_its_words"),
    ("#642", "A search result names the guide, the step and the screen part.",
     "test_help_search_where::Logic::test_a_word_in_a_step_gives_the_guide_the_step_and_its_screen_part"),
    ("#645", "Every screen has its context text and every Settings card has its line.",
     "test_help_guides::ContextText::test_the_settings_text_has_a_line_for_every_settings_card_on_the_page"),
    ("#645", "The ? key opens the Help peek for this page and a second press closes it.",
     "test_help_peek::Peek::test_question_mark_opens_the_peek_for_this_page_and_a_second_closes_it"),
    ("#645", "The Dashboard in Edit has its own peek text.",
     "test_help_peek::Peek::test_the_edit_view_of_the_dashboard_is_its_own_screen"),
    ("#645", "A published file has no peek, no button and no key.",
     "test_help_peek::Published::test_a_published_file_has_no_peek_no_button_and_no_key"),
    ("#652", "The Docker entry is in Help, written for the Terminal.",
     "test_help_content::Shape::test_the_counts"),
    ("#652", "In a container the start line names the port the person opens.",
     "test_main::InProcess::test_in_a_container_the_start_line_names_the_published_port"),
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
    """The notes' own rules, read from the tree now (the same for every release): a title with (Beta), plain words,
    no lower-case 'ask clark' in a heading, and the data-layout paragraph only when the layout has changed since 0.9.0."""

    def setUp(self):
        self.text = (ROOT / "dev" / "release-notes" / (VERSION + "-plain.md")).read_text(encoding="utf-8")

    def test_the_title_is_beta_and_the_beta_line_and_update_sentence_are_there(self):
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

    def test_the_data_layout_paragraph_is_there_only_when_the_layout_changed(self):
        said = "This version includes a change to how clark stores your data" in self.text
        self.assertEqual(said, schema_version() != SCHEMA_AT_0_9_0,
                         "the notes must say a layout step is in exactly when SCHEMA_VERSION in store.py is not %d" % SCHEMA_AT_0_9_0)

    def test_a_date_in_the_notes_is_day_first(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 1.0.1 and later have their own test_vNNN
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

"""clark 0.10's hand checks as tests: the 0.10 features that have merged to main. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v0100

Same shape as test_v070.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

A SKELETON, written before the cut, from origin/main on 04-11-2026. Release 0.10 on the board (written v.0.10) holds 26 items;
5 are merged and 21 are not. Merged: the Supporting documents section in Edit with Archive and Restore (#74) and the About you
toast with Undo (#429), both visible; and three that are behind the scenes only, with no row of their own: #336 (one shared growth
check in the tests), #606 (an AI suggestion request must carry an owner) and #609 (the check_link notes name every refused
ending and range). Not merged, so WAITING: #152 (PR 513), #445 (PR 518), #434 (PR 368), #449 (PR 462), #455 (PR 543), #604 and
#605 (PR 477), #607 (PR 475), #614 (PR 540), #640 (PR 545, a prototype only: the filter line is not built yet) and, with no pull
request yet, #53, #54, #174, #346, #350, #446, #453, #611, #613 and #619. #623 (the Windows spike) is a WALK_THROUGH row: it
needs a real Windows laptop.
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.10.0, then fail if they are wrong.
The notes' own rules (title, the Beta line, plain words, the data-layout paragraph) are read from the tree now.
SCHEMA_AT_0_9_0 is the data layout main reads today (11, the layout of 0.6.0). At the cut, set it to what 0.9.0 shipped.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.10.0"
SCHEMA_AT_0_9_0 = 11

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#429", "Saving the name or the email says so with Undo, and saving the same words again says nothing",
     "test_about_you::AboutYou::test_C_saving_the_name_or_the_email_says_so_with_undo_and_a_second_save_of_the_same_words_says_nothing"),
    ("#429", "Undo puts the old value back in the box, the menu and the store",
     "test_about_you::AboutYou::test_C_undo_puts_the_old_value_back_in_the_box_the_menu_and_the_store"),
    ("#429", "A save that is turned away shows no toast and no Undo",
     "test_about_you::AboutYou::test_C_a_refused_save_shows_no_toast_and_no_undo"),
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
    ("#152", "Settings has a Version and updates card and the update routes, with a data migration step and its undo", "PR 513",
     "updater.py", "class Updater"),
    ("#445", "The Settings Update clark card has labelled rows (Installed, Update, Install from a file, Last update) with hints", "PR 518",
     "page/src/edit/Update.jsx", "upd-rows"),
    ("#434", "Risks, issues, actions and decisions rows: a status pill, empty sections, editing in place and the ID button", "PR 368",
     "page/src/edit/ItemRowsEdit.jsx", "A-D5"),
    ("#449", "Work items: the column width can be changed and reset, with a toast", "PR 462",
     "page/src/logic/board.js", "COL_MIN"),
    ("#455", "A new use case is hidden from the client until its eye is turned on (CLIENT-FACING)", "PR 543",
     "changes.py", "client_visible=0)   # #455"),
    ("#604", "A publish that loses a race puts its link back without a gap between the check and the move", "PR 477",
     "publish.py", "def put_link_back"),
    ("#605", "A link that could not be put back is said plainly in the message", "PR 477",
     "publish.py", "def put_link_back"),
    ("#607", "The Word export and import screens say plainly when a list has expired or a file is too big", "PR 475",
     "word_route.py", "SIZE_TOO_BIG"),
    ("#640", "The filter line: the field list opens on a click, an x clears the line, core view tabs, a menu and + New view on the tabs, "
             "no note under the filter (not built yet: the prototype is PR 545)", "PR 545",
     "page/src/components/FilterLine.jsx", "(#640)"),
    ("#53", "Where clark's AI providers code comes from (a copy from the other product's branch)", "no pull request yet (issue 53)", "", None),
    ("#54", "Settings, AI: Claude and OpenAI sign-in for ask clark", "no pull request yet (issue 54)", "", None),
    ("#174", "The first start asks for your name and details, kept in Settings and used to record who changed what",
     "no pull request yet (issue 174)", "", None),
    ("#446", "Settings, AI card: Connect and Disconnect for Claude, an OpenAI tile that says Later, a model list",
     "no pull request yet (issue 446)", "", None),
    ("#453", "The prototype review of 01-11-2026 (a record of differences; nothing to build as one item)",
     "no pull request yet (issue 453)", "", None),
    ("#611", "A blank client message is turned away in plain words, not a server error", "no pull request yet (issue 611)", "", None),
    ("#613", "Settings: typing a full name suggests an Alias (Jane Doe suggests Jane,JD)", "no pull request yet (issue 613)", "", None),
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
]

BANNED_WORDS = ("apply", "applied", "staged", "proposal", "sweep", "tracker", "vault", "extract")


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
        for item in {i for i, _, _ in COVERED} | {i for i, *_ in WALK_THROUGH}:
            self.assertIn(item, sheet, f"{item} has no row on the hand-check sheet")


class Notes(unittest.TestCase):
    """The notes' own rules, read from the tree now (the same for every release): a title that says Beta, the Beta line, plain words,
    no lower-case 'ask clark' in a heading, and the data-layout paragraph only when the layout has changed since 0.9.0."""

    def setUp(self):
        self.text = (ROOT / "dev" / "release-notes" / (VERSION + "-plain.md")).read_text(encoding="utf-8")

    def test_the_title_and_the_beta_line(self):
        self.assertEqual(self.text.splitlines()[0], f"# clark {VERSION} (Beta), Mac")
        self.assertIn("Beta means the whole of clark is Beta until version 1.0.", self.text)

    def test_the_theme_line_and_the_two_headings(self):
        self.assertEqual(len([ln for ln in self.text.splitlines() if ln.startswith("Theme:")]), 1)
        for heading in ("## What is new", "## What is fixed"):
            self.assertIn(heading, self.text.splitlines())

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

    def test_no_line_of_text_starts_with_clark_in_lower_case(self):
        for line in self.text.splitlines():
            self.assertFalse(re.match(r"^(- )?clark\b", line) and not line.startswith("# clark"), line)


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

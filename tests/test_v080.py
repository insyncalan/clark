"""clark 0.8's hand checks as tests: the 0.8 features that have merged to main. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v080

Same shape as test_v070.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the feature is not on main yet (a pull request is open, or none yet); each row names its pull request and a marker
                in the source that appears when it lands. Skipped, with the pull request. When the cut commit has set the version
                and a marker is there, the row fails until it is moved to COVERED with its test, so a landed change is never
                forgotten at the cut.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

Written before the cut, from origin/main on 04-11-2026. Of the 24 cards the board puts in v0.8 (one more, #228, was dropped), 3 are in the 0.7.0 draft (#407, #400,
#493) and 8 are already in 0.6.0 (#412, #242, #297, #299, #244, #487, #494 and #496, in its notes or its tests), so they are not
told again. In 0.8.0 so far (merged and visible): Duplicate keeps the eye (#424), the Add box makes the page behind it inert (#425)
and three Help lines that now match the page (#401, #402, #403). Merged but not visible: #416, #428, #310, #290, #330, #491, #409 and
#348 (tests, notes and the prototype only). Not merged, so WAITING: 21 cards, each with its pull request or the words 'no pull
request yet'. The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.8.0, then fail if wrong.
The notes' own rules (title, the Beta line, plain words, the data-layout paragraph) are read from the tree now.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.8.0"
SCHEMA_AT_0_7_0 = 12     # main reads layout 11 on 04-11-2026; 0.7.0 is not cut yet, so check this on the 0.7.0 tag

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
]

# Not on main yet: (item, check, pull request, a file under src/clark and the text that is in it once the pull request has landed;
# marker None means there is no pull request to look for yet).
WAITING = [
    ("#280", "An update that migrates and then does not answer in 15 seconds puts the database back too", "PR 544", "update_helper.py", "MARKER_NAME"),
    ("#368", "A web page and its Word copy share one publication number (a data layout step)", "PR 516", "store.py", "migrate_publication_shared_number"),
    ("#344", "A week picker beside Week ending lists the published weeks and opens one", "PR 529", "page/src/edit/WeekPicker.jsx", "export function WeekPicker"),
    ("#349", "The dashboard as at a chosen day, rebuilt from the change history", "PR 526", "as_at.py", "def cutoff"),
    ("#326", "An overwrite of a file over 64 MB is refused in plain words, not put back cut short", "PR 456", "publish.py", "EARLIER_TOO_BIG"),
    ("#460", "The update helper's staging folder is owner only and its copy is hash-checked before it runs", "PR 506", "update_helper.py", "marker[\"helper_sha\"]"),
    ("#461", "The update helper copy is hash-checked before finish and an old signature is pruned", "PR 506", "update_install.py", "os.unlink(e.path + updates.SIGNATURE_SUFFIX)"),
    ("#417", "Three small leftovers of the Word screens", "no pull request yet (issue 417)", "", None),
    ("#432", "Five small leftovers of the Word screens", "no pull request yet (issue 432)", "", None),
    ("#420", "About you saves one box without blanking the other", "no pull request yet (issue 420)", "", None),
    ("#462", "Docker first start: three small leftovers", "no pull request yet (issue 462)", "", None),
    ("#171", "Each project keeps its own not-reviewed-after-days number (a data layout step)", "PR 472", "schema.sql", "review_after_days"),
    ("#427", "Install and first start: the Docker route (clark in a container, opened at 127.0.0.1)", "PR 252", "platform.py", "def container_mode():"),
    ("#160", "Settings has a 'Not reviewed after (days)' setting, and the At a glance row can show an optional Not reviewed tile (needs #171)", "PR 523", "page/src/edit/ReviewDays.jsx", "Settings \u203a Freshness (#160)"),
    ("#269", "The publications row names the PDF file saved with it (a data layout step)", "PR 521",
     "store.py", "def record_pdf_name"),
    ("#454", "Settings, People card: Paste from Excel", "PR 558",
     "page/src/edit/People.jsx", "export function People()"),
    ("#48", "HOLD (the Help wording is the owner's call): Export to Word and Import from Word screens", "PR 475",
     "page/src/edit/Word.jsx", "export function WordLayer"),
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
        for item in {i for i, _, _ in COVERED}:
            self.assertIn(item, sheet, f"{item} has no row on the hand-check sheet")


class Notes(unittest.TestCase):
    """The notes' own rules, read from the tree now (the same for every release): a title that says Beta, the Beta line, plain words,
    no lower-case 'ask clark' in a heading, and the data-layout paragraph only when the layout has changed since 0.7.0."""

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
        said = "This version includes a change to how clark stores your data" in self.text
        self.assertEqual(said, schema_version() != SCHEMA_AT_0_7_0,
                         "the notes must say a layout step is in exactly when SCHEMA_VERSION in store.py is not %d" % SCHEMA_AT_0_7_0)

    def test_a_date_in_the_notes_is_day_first(self):
        self.assertIsNone(re.search(r"\b\d{4}-\d\d-\d\d\b", self.text), "a date in the notes is DD-MM-YYYY")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        found = version()
        if found != VERSION:            # 0.8.1 and later have their own test_vNNN
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

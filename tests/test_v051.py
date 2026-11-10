"""clark 0.5.1's hand checks as tests: the patch for the three things the 0.5.0 walk-through found.

Run: python3 dev/run_tests.py test_v051

Same shape as test_v050. Headless and fast: no Chrome is started here.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  WAITING       the fix is not on main yet; its check is written when it lands (the item is named). Skipped, with the question.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.5.1, then fail if they are wrong.
"""
import ast
import re
import unittest

from _paths import ROOT

TESTS = ROOT / "tests"
VERSION = "0.5.1"

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#492", "A published page keeps its saved filters when the Work items tab is clicked after reopening",
     "test_client_page_filters::ClientPageFilters::test_a_click_on_the_work_items_tab_keeps_the_saved_choices"),
]

# Not on main yet: (item, check, where it is being built). Move each to COVERED, with its test, when it lands.
WAITING = [
    ("#383", "Use cases is written in sentence case in the tab and the heading", "PR 275"),
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#492", "Saved filters on a published page survive a tab click", "judgement",
     "only a person can open the saved file again and see the chips come back",
     "Publish a demo project, filter Work items by Owner and Status, close and reopen the file, click the Work items tab (sheet line 16)."),
    ("#383", "Use cases is in sentence case wherever a person reads it", "judgement",
     "the words sit in many places a person reads, in Edit and in a published file",
     "Read the tab, the heading, the Filter by row and Help in Edit and in a published file at 1400 and 900 px (sheet line 17)."),
    ("#192", "The client report shows nothing meant for the author or the team", "judgement",
     "only a person can judge the snapshot reads as meant for the client",
     "Open the Client report tab with the demo project and read every line at 1400 and 900 px, light and dark (sheet line 18)."),
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
        self.assertEqual(out, [], "a covering test named here is missing")

    def test_each_check_is_in_one_list_only_and_each_walk_through_check_says_why_and_what_to_do(self):
        checks = [c for _, c, _ in COVERED + WAITING] + [c for _, c, _, _, _ in WALK_THROUGH]
        self.assertEqual(sorted(c for c in set(checks) if checks.count(c) > 1), [], "a check is listed twice")
        for item, check, kind, why, does in WALK_THROUGH:
            self.assertIn(kind, ("judgement", "live only"), check)
            self.assertTrue(why.strip() and does.strip(), check)

    def test_each_waiting_check_carries_its_question(self):
        for item, check, question in WAITING:
            self.assertTrue(question.strip(), check)

    def test_each_walk_through_line_is_on_the_sheet(self):
        sheet = (ROOT / "dev" / "handchecks" / f"{VERSION}-sheet.md").read_text(encoding="utf-8")
        for n in (16, 17, 18):
            self.assertRegex(sheet, rf"(?m)^{n}\. \*\*", f"sheet line {n} is missing from dev/handchecks/{VERSION}-sheet.md")


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        text = (ROOT / "src" / "clark" / "__init__.py").read_text(encoding="utf-8")
        found = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        if not found or found.group(1) != VERSION:
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


class Notes(unittest.TestCase):
    """#557, #558: the plain notes name the editor tab and the week-ending date as the code does."""

    def test_the_notes_name_the_editor_tab_and_the_week_ending_date(self):
        text = (ROOT / "dev" / "release-notes" / "0.5.1-plain.md").read_text(encoding="utf-8")
        self.assertNotIn("still called Client report", text)
        self.assertIn("Client Requested Report View", text)
        self.assertIn("Week ending date", text)
        # row 1065: the tab itself is gone, so the code no longer carries its name; the 0.5.1 notes stay as they were written.


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

"""clark 0.6's hand checks as tests: the 0.6 features that have merged to main. Each release gets a test_vNNN file, so the
walk-through keeps only the judgement and live-only checks.

Run: python3 dev/run_tests.py test_v060

Same shape as test_v050.
  COVERED       already covered by a test elsewhere. test_every_covering_test_named_here_exists fails if one goes missing.
  LIVE          Live: the real page in headless Chrome (a browser file, so it fails, never skips, without Chrome). Each test builds its
                own rig and shares nothing with another. Widths 1400 and 900.
  WAITING       the feature is not on main yet; its check is written when it lands. Skipped, with the question.
  WALK_THROUGH  judgement or live only, with the reason and the one line a person follows. Skipped: 'needs a person'.

NOT YET MERGED to origin/main on 02-11-2026 (so WAITING, no test): #124 the PDF option on publishing (with its Tech Debt
#269 and #270), #153 the one filter line for Work items (its Tech Debt #286, #287 and #305), the #130 and #132 UX sweep fixes
beyond the Publish spinner, the tick and Publication N (phone layouts, timeline labels, the 12 px minimum), and #131 the motion
enrichments. Merged and checked here: #120 numbered publications. The calendar (test_calendar_scales, #76) and the filter
line in test_filter_line are 0.4 features and are covered by test_v040, not here.
The cut checks (version, release notes, hand-check sheet) skip until the cut commit sets 0.6.0, then fail if they are wrong.
"""
import ast
import pathlib
import re
import unittest

from _paths import ROOT, SRC

TESTS = ROOT / "tests"
VERSION = "0.6.0"

# (item, the check a person would make by eye, the test that covers it: file::Class::test)
COVERED = [
    ("#120", "Each publish gets the project's next number, 1, 2, 3, and each project has its own count",
     "test_publication_numbers::TheCounter::test_the_numbers_run_1_2_3_for_a_project_and_each_project_has_its_own"),
    ("#120", "A Local-only publish and a Word copy take a number too",
     "test_publication_numbers::TheCounter::test_a_local_only_publish_and_a_word_copy_take_a_number_too"),
    ("#120", "Two publishes at once never take the same number",
     "test_publication_numbers::TheCounter::test_two_connections_publishing_at_once_never_take_one_number"),
    ("#120", "A publication cannot be deleted, changed or replaced",
     "test_publication_numbers::TheCounter::test_a_publication_cannot_be_deleted_changed_or_replaced"),
    ("#120", "Undo never frees a number", "test_publication_numbers::TheCounter::test_undo_never_frees_a_number"),
    ("#120", "A refused publish uses no number", "test_publication_numbers::TheCounter::test_a_refused_publication_uses_no_number"),
    ("#120", "An older file's publications are numbered per project by date, and none is lost",
     "test_publication_numbers::OlderFiles::test_a_version_9_file_is_numbered_per_project_by_date_then_seq_and_keeps_every_row"),
    ("#120", "A publish says its number in the file and in the reply",
     "test_publication_numbers::ThroughThePublisher::test_the_file_says_its_number_and_the_reply_names_it_for_a_local_only_publish"),
    ("#120", "A Preview is not numbered", "test_publication_numbers::ThroughThePublisher::test_a_preview_is_not_numbered_and_takes_no_number"),
    ("#120", "A lost race takes the new file back and puts the earlier one back",
     "test_publication_numbers::ThroughThePublisher::test_publish_publish_returns_the_number_and_takes_its_file_back_on_a_lost_race"),
    ("#120", "Each publish is one History line under All and under no other filter",
     "test_publication_numbers::TheHistoryLine::test_each_publish_is_one_line_in_all_and_in_no_other_filter"),
    ("#120", "A publish through the publisher adds its History line",
     "test_publication_numbers::TheHistoryLine::test_a_publish_through_the_publisher_adds_its_line"),
    ("#120", "The published file's foot reads Publication N and the date, and a Preview has none",
     "test_publication_footer::TheFooter::test_a_published_file_reads_publication_n_and_the_date"),
    ("#120", "A file with no date reads Publication N alone",
     "test_publication_footer::TheFooter::test_a_file_with_no_date_reads_publication_n_alone"),
    ("#120", "A Preview has no footer", "test_publication_footer::TheFooter::test_a_preview_has_no_footer"),
    ("#130", "Publishing shows a spinner and then a tick with the same words, Publication N",
     "test_publish_dialog::Dialog::test_C_publish_shows_a_spinner_while_it_works_then_a_tick_with_the_same_words"),
]

# Live: the real page. Not repeated from COVERED; these are the checks a person would make in the app itself.
LIVE = [
    ("#120", "Two publishes from the dialog read Publication 1 and then Publication 2, and the second file's foot says 2 at both widths",
     "Live::test_two_publishes_say_publication_1_then_2_and_the_second_file_foot_says_2_at_1400_and_900"),
    ("#120", "Help tells a person that each publish, a local one too, gets a number", "Live::test_help_says_each_publish_gets_a_number"),
]

# Not on main yet: (item, check, the question or where it is being built).
WAITING = [
    ("#124", "Publishing offers a PDF option (Local and To client) and the PDF file is named in the publications row", "open; Tech Debt #269 and #270 for the row and the footer number"),
    ("#153", "Work items has one filter line (the '/' key focuses it in View)", "open; Tech Debt #286, #287 and #305"),
    ("#130", "Settings tables stack at phone width, the timeline labels never overlap, text is 12 px or more", "open; phone checks go through the 390 px window but the rule is desktop only, so ask before writing them"),
    ("#131", "The ten mild motion improvements keep a static change marker with reduced motion", "open"),
]

# (item, check, kind, why, what the person does)
WALK_THROUGH = [
    ("#120", "The footer and the Published line read well in the real file", "judgement",
     "only a person can say the footer is clear and the History line reads as meant",
     "Publish a demo project twice (Local only), open both files, read the foot; open History under All and read the two lines."),
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

    def test_each_live_check_names_a_test_in_this_file(self):
        have = names_in(pathlib.Path(__file__)).get("Live", set())
        for item, check, where in LIVE:
            self.assertIn(where.split("::")[1], have, check)

    def test_each_waiting_check_carries_its_question(self):
        for item, check, question in WAITING:
            self.assertTrue(question.strip(), check)


class Cut(unittest.TestCase):
    """Release-cut checks that can be read from the tree. They skip until the cut commit has set the version."""

    def cut_made(self):
        text = (ROOT / "src" / "clark" / "__init__.py").read_text(encoding="utf-8")
        found = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        if not found or found.group(1) != VERSION:            # 0.6.1 and later have their own test_vNNN
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


class Live(unittest.TestCase):
    """The real page in headless Chrome. Each test builds its own rig (the Publish dialog's, over a temporary folder)."""

    def test_two_publishes_say_publication_1_then_2_and_the_second_file_foot_says_2_at_1400_and_900(self):
        from test_page import navigate
        from test_publish import opened
        from test_publish_dialog import Pg
        from test_publish_route import Rig
        from test_server import chrome, wait
        rig = Rig(self)
        with chrome() as cdp:
            sid = navigate(cdp, rig.httpd.server_port, "#dashboard&p=PUB")
            p = Pg(self, cdp, sid)
            p.until("!!document.querySelector('#profile-btn')", "the profile circle is in the top bar")
            for want, name in ((1, "first.html"), (2, "second.html")):
                rig.save_to = rig.local / name
                p.open_publish()
                p.go()
                p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
                self.assertRegex(p.message(), r"^Published \(Publication %d\)\. Saved locally as " % want)
                p.go()
                p.until("!document.querySelector('#publish-dialog[open]')", "the dialog closed")
            for width in (1400, 900):
                sid2 = opened(cdp, (rig.local / "second.html").as_uri(), width)
                self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid2) == "1"))
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#publication-footer').length", sid2) == 1))
                foot = cdp.js("document.querySelector('#publication-footer').textContent", sid2)
                self.assertIn("Publication 2", foot, "at %d px" % width)
                self.assertNotIn("Publication 1", foot)
                self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid2), True, "no sideways scroll at %d px" % width)

    def test_help_says_each_publish_gets_a_number(self):
        text = (SRC / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8")
        self.assertIn("Published (Publication 3)", text)
        self.assertIn("Each publish, a local one too, gets the project\u2019s next number", text)


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

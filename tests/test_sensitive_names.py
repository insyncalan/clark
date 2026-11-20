"""Row 1365 S1: sensitive_names.scan finds people or contract material by NAME only.

Run: python3 dev/run_tests.py test_sensitive_names
"""
import builtins
import os
import re
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import sensitive_names as sn

# The approved list (WO-M7225), stated literally here and not read from the module.
APPROVED = (
    "cv", "cvs", "resume", "resumes", "salary", "payroll", "passport", "passports", "ssn", "disciplinary", "grievance",
    "redundancy", "contract", "contracts", "sow", "nda", "purchase order",
)
PLURALS_ADDED = ("sows", "ndas", "purchase orders")
EXPECTED = (
    "cv", "cvs", "resume", "resumes", "salary", "payroll", "passport", "passports", "ssn", "disciplinary", "grievance",
    "redundancy", "contract", "contracts", "sow", "sows", "nda", "ndas", "purchase order", "purchase orders",
)
EXPECTED_READABLE = (".txt", ".md", ".markdown", ".csv", ".tsv", ".rst", ".docx", ".pdf")


def tree(root, paths):
    for p in paths:
        f = Path(root, p)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x", encoding="utf-8")


class Scan(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = self._t.name
        self.addCleanup(self._t.cleanup)

    def names(self):
        return sorted(r["path_rel"] for r in sn.scan(self.root))

    def test_people_and_contract_folders_named(self):  # test 1
        tree(self.root, ["Candidate CV/a.docx", "Candidate CV/b.pdf", "Contract/c.txt", "Contract/sub/d.md",
                         "Photos/e.jpg"])
        found = {r["name"]: r for r in sn.scan(self.root)}
        self.assertEqual(set(found), {"Candidate CV", "Contract"})
        self.assertEqual(found["Candidate CV"]["words"], ["cv"])
        self.assertEqual(found["Contract"]["words"], ["contract"])

    def test_none_when_no_word(self):
        tree(self.root, ["Photos/a.txt", "Notes/b.md", "readme.md"])
        self.assertEqual(sn.scan(self.root), [])

    def test_big_deep_library_is_not_warned(self):  # test 2
        d = Path(self.root, *[f"level{i}" for i in range(12)])
        d.mkdir(parents=True)
        for i in range(500):
            (d / f"note{i}.txt").write_text("x", encoding="utf-8")
        self.assertEqual(sn.scan(self.root), [])

    def test_opens_nothing_and_sends_nothing(self):  # test 3
        tree(self.root, ["Contract/a.txt", "Passport/b.docx", "top salary.csv"])
        def boom(*a, **k):
            raise AssertionError("scan must not open files or the network")
        with mock.patch.object(builtins, "open", boom), mock.patch.object(os, "open", boom), \
                mock.patch.object(os, "stat", boom), mock.patch.object(socket.socket, "connect", boom), \
                mock.patch("urllib.request.urlopen", boom), mock.patch.object(Path, "read_text", boom), \
                mock.patch.object(Path, "open", boom):
            r = sn.scan(self.root)
        self.assertEqual(len(r), 3)

    def test_name_matching_touches_no_file_system(self):
        calls = []
        def spy(name):
            def f(*a, **k):
                calls.append(name)
                raise AssertionError(name)
            return f
        with mock.patch.object(builtins, "open", spy("open")), mock.patch.object(os, "open", spy("os.open")), \
                mock.patch.object(os, "scandir", spy("os.scandir")), mock.patch.object(os, "stat", spy("os.stat")):
            self.assertEqual(sn.words_in("Candidate CVs"), ["cvs"])
            self.assertEqual(sn.words_in("Photos"), [])
        self.assertEqual(calls, [])

    def test_whole_words_only(self):
        tree(self.root, ["Corporates/a.txt", "shrunk/a.txt", "driver/a.txt", "Standard/a.txt", "Chrome/a.txt"])
        self.assertEqual(sn.scan(self.root), [])

    def test_case_accent_and_separators(self):
        tree(self.root, ["RÉSUMÉ/a.txt", "my_cv_2026/a.txt", "Purchase-Order 7/a.txt", "payroll.xlsx", "pricing.xlsx", "x/NDA.txt"])
        self.assertEqual(self.names(), ["Purchase-Order 7", "RÉSUMÉ", "my_cv_2026", "payroll.xlsx"])

    def test_phrase_needs_both_words(self):
        tree(self.root, ["purchase/a.txt", "order/a.txt"])
        self.assertEqual(sn.scan(self.root), [])

    def test_counts_readable_files_under_match(self):
        tree(self.root, ["Contract/a.txt", "Contract/b.DOCX", "Contract/deep/c.pdf", "Contract/d.xlsx", "Contract/e.jpg"])
        (r,) = sn.scan(self.root)
        self.assertEqual((r["name"], r["readable_files"], r["words"]), ("Contract", 3, ["contract"]))

    def test_top_level_file_listed_by_name(self):
        tree(self.root, ["Payroll 2026.csv", "Other/Payroll.csv"])
        r = sn.scan(self.root)
        self.assertEqual([(x["path_rel"], x["readable_files"]) for x in r], [("Payroll 2026.csv", 1)])

    def test_nested_match_reports_relative_path(self):
        tree(self.root, ["Work/Payroll/a.txt"])
        (r,) = sn.scan(self.root)
        self.assertEqual((r["name"], r["path_rel"]), ("Payroll", os.path.join("Work", "Payroll")))

    def test_links_not_followed(self):
        tree(self.root, ["real/a.txt"])
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        tree(outside.name, ["Contract/a.txt"])
        os.symlink(outside.name, os.path.join(self.root, "link"))
        self.assertEqual(sn.scan(self.root), [])

    def test_link_named_with_a_word_is_not_listed_or_counted(self):
        tree(self.root, ["Contract/a.txt"])
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        tree(outside.name, ["f.txt"])
        os.symlink(outside.name, os.path.join(self.root, "Contract", "more"))
        os.symlink(os.path.join(outside.name, "f.txt"), os.path.join(self.root, "Contract", "g.txt"))
        os.symlink(outside.name, os.path.join(self.root, "Legal"))
        (r,) = sn.scan(self.root)
        self.assertEqual((r["name"], r["readable_files"]), ("Contract", 1))

    def test_unreadable_top_level_file_counts_zero(self):
        tree(self.root, ["payroll.xlsx"])
        self.assertEqual([r["readable_files"] for r in sn.scan(self.root)], [0])

    def test_depth_limit(self):
        tree(self.root, ["a/b/c/Contract/x.txt"])
        with mock.patch.object(sn, "MAX_DEPTH", 2):
            self.assertEqual(sn.scan(self.root), [])
        with mock.patch.object(sn, "MAX_DEPTH", 3):
            self.assertEqual(len(sn.scan(self.root)), 1)

    def test_count_depth_limit(self):
        tree(self.root, ["Contract/a/x.txt", "Contract/y.txt"])
        with mock.patch.object(sn, "MAX_DEPTH", 1):
            (r,) = sn.scan(self.root)
        self.assertEqual(r["readable_files"], 1)

    def test_weak_words_do_not_warn(self):
        tree(self.root, ["Rates/a.txt", "Proposal/a.txt", "Legal/a.txt", "Performance review/a.txt", "Pricing/a.txt", "Agreement/a.txt",
                         "Commercial/a.txt", "HR/a.txt", "Release candidate/a.txt"])
        self.assertEqual(sn.scan(self.root), [])

    def test_ticket_example_and_plurals(self):
        tree(self.root, ["ODC Candidates_CVs/a.docx"])
        (r,) = sn.scan(self.root)
        self.assertEqual((r["name"], r["words"]), ("ODC Candidates_CVs", ["cvs"]))
        for plural in ("Contracts", "Resumes", "Passports", "CVs"):
            self.assertEqual(len(sn.words_in(plural)), 1, plural)

    def test_entry_cap_stops_scan_and_flags_truncated(self):
        tree(self.root, ["A1.txt", "A2.txt", "A3.txt", "Contract/x.txt", "z/Legal/y.txt"])
        with mock.patch.object(sn, "MAX_ENTRIES", 3):
            r = sn.scan(self.root)
        self.assertTrue(r.truncated)
        self.assertEqual(r, [])  # the cap hit before Contract and z were reached

    def test_cap_not_hit_is_not_truncated(self):
        tree(self.root, ["Contract/x.txt", "b.txt"])
        with mock.patch.object(sn, "MAX_ENTRIES", 3):
            r = sn.scan(self.root)
        self.assertFalse(r.truncated)
        self.assertEqual(len(r), 1)

    def test_cap_exactly_met_is_not_truncated(self):
        tree(self.root, ["a.txt", "b.txt"])
        with mock.patch.object(sn, "MAX_ENTRIES", 2):
            self.assertFalse(sn.scan(self.root).truncated)

    def test_count_depth_two_counts_one_level_down(self):
        tree(self.root, ["Contract/a/x.txt", "Contract/a/b/z.txt", "Contract/y.txt"])
        with mock.patch.object(sn, "MAX_DEPTH", 2):
            (r,) = sn.scan(self.root)
        self.assertEqual(r["readable_files"], 2)

    def test_digits_make_one_word(self):
        tree(self.root, ["CV2/a.txt", "2cv/a.txt", "hr5/a.txt"])
        self.assertEqual(sn.scan(self.root), [])

    def test_unreadable_folder_under_match_counts_zero(self):
        tree(self.root, ["Contract/locked/a.txt", "Contract/b.txt"])
        real = os.scandir
        def fake(p):
            if str(p).endswith("locked"):
                raise PermissionError(p)
            return real(p)
        with mock.patch.object(os, "scandir", fake):
            (r,) = sn.scan(self.root)
        self.assertEqual(r["readable_files"], 1)

    def test_unreadable_entry_in_count_is_skipped_and_count_goes_on(self):
        tree(self.root, ["Contract/a.txt", "Contract/b.txt", "Contract/c.txt", "Contract/d.txt"])
        real = sn._is_link
        seen = []
        def flaky(e):
            if e.name.endswith(".txt") and not seen:
                seen.append(e.name)
                raise PermissionError(e.name)
            return real(e)
        with mock.patch.object(sn, "_is_link", flaky):
            (r,) = sn.scan(self.root)
        self.assertEqual(len(seen), 1)
        self.assertEqual(r["readable_files"], 3)

    def test_unreadable_entry_in_walk_is_skipped_and_walk_goes_on(self):
        tree(self.root, ["Contract/a.txt", "Payroll/b.txt", "Passport/c.txt"])
        real = sn._is_link
        n = []
        def flaky(e):
            n.append(e.name)
            if len(n) == 1:
                raise PermissionError(e.name)
            return real(e)
        with mock.patch.object(sn, "_is_link", flaky):
            names = [r["name"] for r in sn.scan(self.root)]
        self.assertEqual(names, ["Passport", "Payroll"])  # the first entry (Contract) was skipped, the others kept

    def test_count_stops_at_the_budget_and_says_truncated(self):
        tree(self.root, ["Contract/a.txt", "Contract/b.txt", "Contract/c.txt", "Contract/d.txt", "Contract/e.txt"])
        with mock.patch.object(sn, "MAX_ENTRIES", 3):
            (r,) = sn.scan(self.root)
            truncated = sn.scan(self.root).truncated
        self.assertEqual(r["readable_files"], 2)  # one name for Contract, two for its files, then the budget is spent
        self.assertTrue(truncated)

    def test_count_within_budget_is_whole_and_not_truncated(self):
        tree(self.root, ["Contract/a.txt", "Contract/b.txt"])
        with mock.patch.object(sn, "MAX_ENTRIES", 3):
            res = sn.scan(self.root)
        self.assertEqual(res[0]["readable_files"], 2)
        self.assertFalse(res.truncated)

    def test_link_loop_is_finished_and_not_counted(self):
        tree(self.root, ["Contract/a.txt"])
        os.symlink(os.path.join(self.root, "Contract"), os.path.join(self.root, "Contract", "again"))
        os.symlink(self.root, os.path.join(self.root, "Contract", "up"))
        res = sn.scan(self.root)
        self.assertEqual([(r["name"], r["readable_files"]) for r in res], [("Contract", 1)])
        self.assertFalse(res.truncated)

    def test_link_out_of_the_folder_is_not_walked_or_counted(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        tree(outside.name, ["Payroll/p.txt", "q.txt", "r.txt"])
        tree(self.root, ["Contract/a.txt"])
        os.symlink(outside.name, os.path.join(self.root, "Contract", "out"))
        os.symlink(os.path.join(outside.name, "Payroll"), os.path.join(self.root, "Payroll"))
        os.symlink(outside.name, os.path.join(self.root, "Elsewhere"))
        res = sn.scan(self.root)
        self.assertEqual([(r["name"], r["readable_files"]) for r in res], [("Contract", 1)])

    def test_junction_and_reparse_point_count_as_links(self):
        class E:
            def __init__(self, junction, attrs):
                self._j, self._a = junction, attrs
            def is_symlink(self):
                return False
            def is_junction(self):
                return self._j
            def stat(self, follow_symlinks=True):
                return mock.Mock(st_file_attributes=self._a)
        self.assertTrue(sn._is_link(E(True, 0)))
        self.assertFalse(sn._is_link(E(False, 0x400)))  # not on this platform: attributes are read on Windows only
        with mock.patch.object(sn.sys, "platform", "win32"):
            self.assertTrue(sn._is_link(E(False, 0x400 | 0x10)))
            self.assertFalse(sn._is_link(E(False, 0x10)))
        self.assertFalse(sn._is_link(E(False, 0)))

    def test_missing_folder_is_empty(self):
        self.assertEqual(sn.scan(os.path.join(self.root, "nope")), [])


class Words(unittest.TestCase):  # test 6
    def test_words_pinned(self):
        self.assertEqual(sn.WORDS, EXPECTED)
        self.assertEqual(len(sn.WORDS), 20)

    def test_final_words_are_the_approved_ones_plus_plurals(self):
        self.assertEqual(len(APPROVED), 17)
        self.assertEqual(sorted(APPROVED + PLURALS_ADDED), sorted(EXPECTED))

    def test_sow_nda_purchase_order_plurals_match(self):
        for name, word in (("NDAs", "ndas"), ("SOWs 2026", "sows"), ("Purchase Orders", "purchase orders"),
                           ("NDA", "nda"), ("SOW", "sow"), ("purchase order 4", "purchase order")):
            self.assertEqual(sn.words_in(name), [word], name)

    def test_readable_types_come_from_the_ask_reader(self):
        from clark import ask_passages
        self.assertEqual(sn.READABLE_TYPES, EXPECTED_READABLE)
        self.assertEqual(sn.READABLE_TYPES, ask_passages.TEXT_TYPES + ask_passages.WORD_TYPES + ask_passages.PDF_TYPES)

    def test_words_live_in_one_module(self):
        src = Path(SRC, "clark")
        for p in src.glob("*.py"):
            if p.name == "sensitive_names.py":
                continue
            text = p.read_text(encoding="utf-8")
            self.assertNotIn('"disciplinary", "grievance"', text, p.name)
            self.assertNotIn('"redundancy"', text, p.name)
            self.assertNotIn('"payroll", "passport"', text, p.name)
            self.assertNotIn("sensitive_names.WORDS =", text, p.name)

    def test_words_are_lower_ascii(self):
        for w in sn.WORDS:
            self.assertRegex(w, r"^[a-z]+( [a-z]+)?$")


class MutationSurvivors(unittest.TestCase):
    """Mutation sweep (non-UI): each test below kills a mutant that the first tests let live."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = self._t.name
        self.addCleanup(self._t.cleanup)

    def test_every_readable_type_is_counted(self):
        for ending in (".txt", ".md", ".markdown", ".csv", ".tsv", ".rst", ".docx", ".pdf"):
            with self.subTest(ending=ending):
                d = Path(self.root, "Contract " + ending.strip("."))
                d.mkdir()
                (d / ("a" + ending)).write_text("x", encoding="utf-8")
                rows = [r for r in sn.scan(self.root) if r["name"] == d.name]
                self.assertEqual(rows[0]["readable_files"], 1, ending)
        d = Path(self.root, "Contract other")
        d.mkdir()
        (d / "a.jpg").write_text("x", encoding="utf-8")
        self.assertEqual([r for r in sn.scan(self.root) if r["name"] == d.name][0]["readable_files"], 0)

    def test_the_limits_are_pinned(self):
        self.assertEqual((sn.MAX_ENTRIES, sn.MAX_DEPTH), (100000, 64))

    def test_a_link_named_with_a_word_is_never_listed(self):
        target = Path(self.root, "plain.txt")
        target.write_text("x", encoding="utf-8")
        try:
            os.symlink(target, Path(self.root, "contract link.txt"))
        except (OSError, NotImplementedError):
            self.skipTest("no links here")
        self.assertEqual(sn.scan(self.root), [])

    def test_rows_come_in_name_order_capitals_first(self):
        tree(self.root, ["salary/a.txt", "Payroll/a.txt", "Contract/a.txt", "cv/a.txt"])
        self.assertEqual([r["name"] for r in sn.scan(self.root)], ["Contract", "Payroll", "cv", "salary"])

    def test_order_does_not_depend_on_the_disk_order(self):
        tree(self.root, ["Payroll/a.txt", "Contract/a.txt", "Passport/a.txt"])
        real = os.scandir
        class Rev:
            def __init__(self, p):
                self.it = real(p)
            def __enter__(self):
                return sorted(self.it.__enter__(), key=lambda e: e.name, reverse=True)
            def __exit__(self, *a):
                return self.it.__exit__(*a)
        with mock.patch.object(os, "scandir", Rev):
            names = [r["name"] for r in sn.scan(self.root)]
        self.assertEqual(names, ["Contract", "Passport", "Payroll"])


    def test_the_budget_stops_the_count_at_the_entry_limit(self):
        # Survivor: _count without "if not budget.take(): break". Six files, room for the folder's own name and three more.
        tree(self.root, [f"Contract/f{i}.txt" for i in range(6)])
        with mock.patch.object(sn, "MAX_ENTRIES", 4):
            res = sn.scan(self.root)
        self.assertEqual([(r["name"], r["readable_files"]) for r in res], [("Contract", 3)])
        self.assertTrue(res.truncated)

    def test_an_unreadable_folder_is_skipped_and_the_scan_goes_on(self):
        # Survivor: re-raise instead of skipping. The matched folder itself cannot be listed, and so cannot a folder inside another.
        tree(self.root, ["Contract/a.txt", "Payroll/b.txt", "Payroll/locked/c.txt", "Payroll/d.txt"])
        real = os.scandir
        def fake(p):
            if str(p).endswith("Contract") or str(p).endswith("locked"):
                raise PermissionError(p)
            return real(p)
        with mock.patch.object(os, "scandir", fake):
            res = sn.scan(self.root)
        self.assertEqual([(r["name"], r["readable_files"]) for r in res], [("Contract", 0), ("Payroll", 2)])

    def test_names_come_out_sorted_whatever_order_the_disk_gives(self):
        # Survivor: sorted() without its key. A scrambled disk order, at the top and one folder down.
        tree(self.root, ["Dept/Salary/a.txt", "Dept/Contract/a.txt", "Dept/NDA.txt", "Payroll/a.txt", "CV.txt",
                         "Passport/a.txt", "Contract/a.txt"])
        real = os.scandir
        class Scrambled:
            def __init__(self, p):
                self.it = real(p)
            def __enter__(self):
                es = sorted(self.it.__enter__(), key=lambda e: e.name)
                return es[1::2] + es[0::2]
            def __exit__(self, *a):
                return self.it.__exit__(*a)
        with mock.patch.object(os, "scandir", Scrambled):
            got = [r["path_rel"] for r in sn.scan(self.root)]
        self.assertEqual(got, ["CV.txt", "Contract", os.path.join("Dept", "Contract"), os.path.join("Dept", "Salary"),
                               "Passport", "Payroll"])


    def test_an_entry_that_cannot_be_checked_is_skipped_in_the_count_and_in_the_walk(self):
        # Survivor: re-raise instead of "except OSError: continue". Subfolder "locked" fails its link check, in the count
        # under Contract and in the walk beside it; the other names are kept.
        tree(self.root, ["Contract/locked/a.txt", "Contract/b.txt", "Contract/c.txt", "locked/Payroll/p.txt", "Passport/q.txt"])
        real = sn._is_link
        def flaky(e):
            if e.name == "locked":
                raise PermissionError(e.name)
            return real(e)
        with mock.patch.object(sn, "_is_link", flaky):
            res = sn.scan(self.root)
        self.assertEqual([(r["name"], r["readable_files"]) for r in res], [("Contract", 2), ("Passport", 1)])


class MutationGaps(unittest.TestCase):
    """Nine survivors of the mutation sweep: each test fails on its mutant of sensitive_names.py."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.root = self._t.name
        self.addCleanup(self._t.cleanup)

    def test_full_width_letters_fold_to_plain(self):  # NFKD -> NFD
        self.assertEqual(sn.words_in("\uff23\uff36.txt"), ["cv"])

    def test_non_ascii_letters_make_their_own_word(self):  # [^\W_]+ -> [a-z0-9]+
        self.assertEqual(sn.words_in("cv\u0436.txt"), [])
        self.assertEqual(sn.words_in("\u0436cv.txt"), [])

    def test_single_letter_word_still_splits_a_phrase(self):  # [^\W_]+ -> [^\W_]{2,}
        self.assertEqual(sn.words_in("purchase a order.txt"), [])

    def test_hits_come_in_list_order(self):  # reversed(words)
        self.assertEqual(sn.words_in("Resume CV Salary"), ["cv", "resume", "salary"])

    def test_count_goes_one_level_per_folder(self):  # depth + 1 -> depth + 2
        tree(self.root, ["Contracts/a/b/x.txt", "Contracts/a/b/c/y.txt"])
        with mock.patch.object(sn, "MAX_DEPTH", 3):
            rows = list(sn.scan(self.root))
        self.assertEqual(rows[0]["readable_files"], 1)

    def test_parent_folder_name_is_not_matched(self):  # words_in(e.name) -> words_in(e.path)
        root = Path(self.root, "Contracts Archive")
        tree(root, ["notes/a.txt", "b.txt"])
        self.assertEqual(list(sn.scan(root)), [])

    def test_all_words_of_a_name_are_listed(self):  # 'words': found[:1], folder and file
        tree(self.root, ["CV Salary/a.txt", "Payroll Passport.txt"])
        rows = {r["name"]: r for r in sn.scan(self.root)}
        self.assertEqual(rows["CV Salary"]["words"], ["cv", "salary"])
        self.assertEqual(rows["Payroll Passport.txt"]["words"], ["payroll", "passport"])

    def test_scan_result_is_not_truncated_by_default(self):  # truncated = True
        self.assertIs(sn.ScanResult().truncated, False)


if __name__ == "__main__":
    unittest.main()

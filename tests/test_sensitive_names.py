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

EXPECTED = (
    "cv", "cvs", "resume", "resumes", "salary", "payroll", "passport", "passports", "ssn", "disciplinary", "grievance",
    "redundancy", "contract", "contracts", "sow", "nda", "purchase order",
)


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
            (d / f"note{i}.txt").write_text("x")
        self.assertEqual(sn.scan(self.root), [])

    def test_opens_nothing_and_sends_nothing(self):  # test 3
        tree(self.root, ["Contract/a.txt", "Passport/b.docx", "top salary.csv"])
        def boom(*a, **k):
            raise AssertionError("scan must not open files or the network")
        with mock.patch.object(builtins, "open", boom), mock.patch.object(socket.socket, "connect", boom), \
                mock.patch("urllib.request.urlopen", boom), mock.patch.object(Path, "read_text", boom), \
                mock.patch.object(Path, "open", boom):
            r = sn.scan(self.root)
        self.assertEqual(len(r), 3)

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

    def test_missing_folder_is_empty(self):
        self.assertEqual(sn.scan(os.path.join(self.root, "nope")), [])


class Words(unittest.TestCase):  # test 6
    def test_words_pinned(self):
        self.assertEqual(sn.WORDS, EXPECTED)

    def test_words_live_in_one_module(self):
        src = Path(SRC, "clark")
        for p in src.glob("*.py"):
            if p.name == "sensitive_names.py":
                continue
            text = p.read_text(encoding="utf-8")
            self.assertNotIn('"disciplinary", "grievance"', text, p.name)
            self.assertNotIn("sensitive_names.WORDS =", text, p.name)

    def test_words_are_lower_ascii(self):
        for w in sn.WORDS:
            self.assertRegex(w, r"^[a-z]+( [a-z]+)?$")


if __name__ == "__main__":
    unittest.main()

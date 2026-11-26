"""The scope script (dev/tools/scope_check.py): every file a change touches is one the ticket names. An extra file is listed
and fails the check; the files of the ticket's named tests count as named.

Run: python3 dev/run_tests.py test_scope_check   (quick tier)
"""
import contextlib
import io
import json
import unittest

from _paths import ROOT  # noqa: F401  (puts dev/tools on the path)
from _pr_fixture import PrFixture, TEST_MOD

import scope_check as sc

TICKET = {"ticket": "9001", "files": ["src/clark/mod.py"], "named_tests": ["test_mod.ModTest.test_double"]}


class NamedTest(unittest.TestCase):
    def test_a_named_test_names_its_file(self):
        self.assertEqual(sc.test_file("test_mod.ModTest.test_double"), "tests/test_mod.py")
        self.assertEqual(sc.test_file("test_mod"), "tests/test_mod.py")
        self.assertEqual(sc.test_file("test_mod.py"), "tests/test_mod.py")
        self.assertEqual(sc.test_file("tests/test_mod.py"), "tests/test_mod.py")

    def test_exact_paths_folders_and_patterns(self):
        named = ["src/clark/mod.py", "docs/", "src/clark/page/*.css"]
        self.assertTrue(sc.is_named("src/clark/mod.py", named))
        self.assertTrue(sc.is_named("docs/help/a.md", named))
        self.assertTrue(sc.is_named("src/clark/page/shell.css", named))
        self.assertFalse(sc.is_named("src/clark/mod.pyc", named))
        self.assertFalse(sc.is_named("src/clark/other.py", named))
        self.assertFalse(sc.is_named("docs.md", named))


class FixtureDiffTest(unittest.TestCase):
    def test_a_change_inside_the_ticket_passes(self):
        with PrFixture() as pr:
            pr.write("src/clark/mod.py", "def double(n):\n    return n + n\n")
            pr.write("tests/test_mod.py", TEST_MOD + "\n# one more line\n")
            pr.commit("in scope")
            r = sc.check(str(pr.dir), pr.base, "HEAD", TICKET)
            self.assertTrue(r["ok"])
            self.assertEqual(r["extra"], [])
            self.assertEqual(r["changed"], ["src/clark/mod.py", "tests/test_mod.py"])

    def test_an_extra_file_is_listed_and_fails(self):
        with PrFixture() as pr:
            pr.write("src/clark/mod.py", "def double(n):\n    return n + n\n")
            pr.write("src/clark/other.py", "X = 1\n")
            pr.commit("one file too many")
            r = sc.check(str(pr.dir), pr.base, "HEAD", TICKET)
            self.assertFalse(r["ok"])
            self.assertEqual(r["extra"], ["src/clark/other.py"])

    def test_a_deleted_file_outside_the_ticket_is_extra(self):
        with PrFixture() as pr:
            pr.remove("src/clark/__init__.py")
            pr.commit("delete a file the ticket does not name")
            self.assertEqual(sc.check(str(pr.dir), pr.base, "HEAD", TICKET)["extra"], ["src/clark/__init__.py"])

    def test_both_names_of_a_moved_file_count(self):
        with PrFixture() as pr:
            pr.git("mv", "src/clark/mod.py", "src/clark/moved.py")
            pr.commit("move")
            self.assertEqual(sc.check(str(pr.dir), pr.base, "HEAD", TICKET)["extra"], ["src/clark/moved.py"])

    def test_a_ticket_that_names_no_file_is_not_a_pass(self):
        with PrFixture() as pr:
            pr.write("src/clark/mod.py", "def double(n):\n    return n + n\n")
            pr.commit("change")
            r = sc.check(str(pr.dir), pr.base, "HEAD", {"ticket": "9001", "files": [], "named_tests": []})
            self.assertFalse(r["ok"])
            self.assertEqual(r["extra"], ["src/clark/mod.py"])


class CommandTest(unittest.TestCase):
    def run_main(self, pr, ticket, base=None):
        pr.write("../ticket.json", "")          # the ticket file lives outside the repository, so it is never part of the change
        path = pr.dir.parent / "ticket.json"
        path.write_text(json.dumps(ticket), encoding="utf-8")
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                code = sc.main(["--repo", str(pr.dir), "--base", base or pr.base, "--ticket", str(path)])
        finally:
            path.unlink()
        return code, out.getvalue()

    def test_exit_0_on_a_change_in_scope(self):
        with PrFixture() as pr:
            pr.write("src/clark/mod.py", "def double(n):\n    return n + n\n")
            pr.commit("in scope")
            code, out = self.run_main(pr, TICKET)
            self.assertEqual(code, 0)
            self.assertIn("Scope: passed (1 changed file, ticket 9001)", out)

    def test_exit_1_and_the_extra_file_printed(self):
        with PrFixture() as pr:
            pr.write("README.md", "hello\n")
            pr.commit("extra")
            code, out = self.run_main(pr, TICKET)
            self.assertEqual(code, 1)
            self.assertIn("not named by the ticket: README.md", out)
            self.assertIn("Scope: FAILED", out)

    def test_exit_2_when_it_cannot_check(self):
        with PrFixture() as pr:
            code, out = self.run_main(pr, TICKET, base="no-such-ref")
            self.assertEqual(code, 2)
            self.assertIn("not checked", out)


if __name__ == "__main__":
    unittest.main()

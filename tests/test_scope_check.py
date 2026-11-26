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

    def test_exit_2_when_it_cannot_check(self):
        with PrFixture() as pr:
            code, out = self.run_main(pr, TICKET, base="no-such-ref")
            self.assertEqual(code, 2)
            self.assertIn("not checked", out)


if __name__ == "__main__":
    unittest.main()

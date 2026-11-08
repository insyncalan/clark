"""#912: the growth tests of the public-copy tool's scrub, moved out of test_publish_public so each file stays short on a hosted runner.

Run: python3 dev/run_tests.py test_publish_public_slow
TheScrubHasALimit is the class that was at the end of tests/test_publish_public.py, with its tests unchanged: a million newlines, a million
'<', 500 long lines and the real Python repros are quick (judged by growth in CPU time) or refused by file number, and never a traceback.
It is about 180 s of the 275 s the old file took. Its helpers (Base, GOOD, clean, has_listed and the fictional names) come from there.
"""
import unittest
from unittest import mock

import _paths  # noqa: F401  (puts dev/tools/ on the path)
import publish_public as pp
from _growth import assert_growth
from test_publish_public import Base, GOOD, OWNER_N, PLAN_REPO, clean, has_listed


class TheScrubHasALimit(Base):
    """Review of fb9b5a0: a million newlines, a million '<', or 500 long lines took the scrub over 40 s and the dry run over 100 s, and
    some Python files raised MemoryError. Each of those is now quick (or refused by file number) and never a traceback."""
    def grows_slowly(self, path, make, n, seconds=4):
        """The scrub and the guard on make(n // 2) and make(2 * n): judged by the growth in CPU time (growth_ratio), not by a wall-clock limit
        (the old quick() asserted `seconds` of wall time, which a loaded runner broke). The alarm is only a hang guard: a regression must
        fail the test, not hang it."""
        import signal

        def too_slow(_signum, _frame):
            raise AssertionError("still reading after %d seconds" % (seconds * 16))
        old = signal.signal(signal.SIGALRM, too_slow)
        signal.alarm(seconds * 16)
        try:
            def work(size):
                data = make(size)
                pp.scrub(path, data)
                pp.guard_kinds(path, data)
            assert_growth(self, work, max(n // 2, 1), self.id().split(".")[-1])
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)

    def test_a_million_newlines_is_refused_by_file_number_without_being_read(self):
        data = b"\n" * 1000000
        self.grows_slowly("docs/x.md", lambda n: b"\n" * n, 500000)
        entry = pp.Entry(7, "100644", "0" * 40, len(data), "docs/x.md")
        self.assertEqual(pp.scrub_limit_findings([entry], [data]), ["file #7: too long to scrub safely (over %d lines or %d KB)"
                                                                      % (pp.MAX_SCRUB_LINES, pp.MAX_SCRUB_BYTES // 1024)])
        self.assertEqual(pp.scrub("docs/x.md", data), data)

    def test_the_line_count_and_the_size_each_make_the_limit(self):
        many = b"a\n" * (pp.MAX_SCRUB_LINES + 1)
        big = b"a" * (pp.MAX_SCRUB_BYTES + 1)
        for name, data in (("lines", many), ("bytes", big)):
            entry = pp.Entry(1, "100644", "0" * 40, len(data), "docs/x.md")
            self.assertEqual(len(pp.scrub_limit_findings([entry], [data])), 1, name)
        fine = b"a\n" * pp.MAX_SCRUB_LINES
        self.assertEqual(pp.scrub_limit_findings([pp.Entry(1, "100644", "0" * 40, len(fine), "docs/x.md")], [fine]), [])
        other = pp.Entry(1, "100644", "0" * 40, len(big), "data.bin")
        self.assertEqual(pp.scrub_limit_findings([other], [big]), [])             # only the files the scrub would read

    def test_a_file_over_the_limit_is_refused_in_a_publish_and_nothing_is_pushed(self):
        self.make_private(dict(GOOD, **{"docs/long.md": "\n" * (pp.MAX_SCRUB_LINES + 5)}))
        for flags in ((), ("--dry-run",)):
            code, out = self.go(*flags)
            self.assertEqual(code, 1, out)
            self.assertRegex(out, r"file #\d+: too long to scrub safely")
            self.assertFalse(has_listed(out))
        self.assertEqual(self.heads(), [])

    # The old check was a wall-clock limit (quick(), seconds=4 for a run of 900000 '<'); a loaded runner took 4.07 s. It is now the growth
    # from n/2 to 2n in CPU time, which is what a regex blow-up changes. ANGLE_OLD_LIMIT is kept as documentation and is no longer asserted.
    ANGLE_OLD_LIMIT = 4

    def test_a_run_of_angle_brackets_is_quick_in_the_scrub_and_the_guard(self):
        def work(n):
            data = b"<" * n
            pp.scrub("docs/x.md", data)
            pp.guard_kinds("docs/x.md", data)
        assert_growth(self, work, 100000, "angle brackets")

    def test_a_run_of_square_brackets_is_quick(self):
        self.grows_slowly("docs/x.md", lambda n: b"[" * n, 450000)

    def test_the_repo_name_and_a_hyphen_over_and_over_is_quick(self):
        self.grows_slowly("docs/x.md", lambda n: (PLAN_REPO.split("-")[0] + "-").encode() * n, 50000)

    def test_many_long_lines_are_quick(self):
        for unit in ("a", " ", "x  ", "the  x", "-_ ", " and ", "[", "<", "[x](", "(", "`", "*"):
            with self.subTest(unit=repr(unit)):
                line = (unit * (1990 // len(unit) + 1))[:1990] + "\n"
                self.grows_slowly("docs/x.md", lambda n, line=line: (line * n).encode(), 50)

    def test_long_runs_of_white_space_are_left_alone_and_a_name_beside_one_is_still_scrubbed(self):
        self.assertEqual(clean("docs/x.md", "a%sb %s here\n" % (" " * 100, OWNER_N)), "a%sb the owner here\n" % (" " * 100))

    def test_real_sized_files_are_scrubbed_as_before(self):
        text = "".join("line %d by %s\n" % (n, OWNER_N) for n in range(5000))
        self.assertNotIn(OWNER_N, clean("docs/x.md", text))

    def test_python_that_runs_out_of_memory_or_depth_is_left_to_the_guard_not_a_crash(self):
        import ast
        for error in (MemoryError, RecursionError):
            with self.subTest(error=error.__name__), mock.patch.object(ast, "parse", side_effect=error):
                self.assertIsNone(pp.python_spans("x = 1  # note\n"))
                data = ("x = 1  # %s\n" % OWNER_N).encode()
                self.assertEqual(pp.scrub("src/a.py", data), data)

    def test_the_real_python_repros_do_not_crash(self):
        for unit, n in (((OWNER_N + " "), 71500), ("-", 500000), ("the  x ", 70000)):
            with self.subTest(unit=unit[:12]):
                self.grows_slowly("src/a.py", lambda k, unit=unit: (unit * k).encode(), n, seconds=8)

    def test_a_statement_too_deep_to_parse_is_left_alone_without_calling_the_parser(self):
        import ast
        deep = ("x = " + "-" * (pp.MAX_LOGICAL_TOKENS + 5) + "1  # " + OWNER_N + "\n")
        with mock.patch.object(ast, "parse", side_effect=AssertionError("parsed")):
            self.assertIsNone(pp.python_spans(deep))
            self.assertEqual(pp.scrub("src/a.py", deep.encode()), deep.encode())
        self.assertTrue(pp._runaway_statement(deep))
        self.assertFalse(pp._runaway_statement("x = [\n" + "1,\n" * 3000 + "]\n"))          # a long list is not deep
        self.assertEqual(clean("src/a.py", "y = (1,\n" + "     2,\n" * 9000 + ")  # " + OWNER_N + "\n").count(OWNER_N), 0)

    def test_a_memory_error_anywhere_in_a_run_is_a_refusal_not_a_traceback(self):
        self.make_private(GOOD)
        with mock.patch.object(pp, "scrub_entries", side_effect=MemoryError):
            code, out = self.go()
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED: a file was too large", out)
        self.assertNotIn("Traceback", out)


if __name__ == "__main__":
    unittest.main()

"""Row 1538 (from row 1368): SQLite FTS5 must be available where the tests and the app run, or the Ask index cannot work.

The image meant is the one in docker/compose.yaml (python:3.12.12-slim-bookworm), the only image on main. Nothing builds it in CI,
so this test runs on whatever Python runs it: in the container it checks that image's SQLite.

Run: python3 dev/run_tests.py test_ask_index_fts5_1368
"""
import re
import sqlite3
import unittest
from pathlib import Path

from _paths import SRC  # noqa: F401

from clark import ask_index

MESSAGE = ("SQLite FTS5 is not available in this image: CREATE VIRTUAL TABLE ... USING fts5 failed. "
           "The Ask index needs FTS5.")


def fts5_problem(connect=sqlite3.connect):
    """None when FTS5 works on an in-memory database, else the exact message."""
    try:
        db = connect(":memory:")
        try:
            db.execute("CREATE VIRTUAL TABLE t USING fts5(text)")
            db.execute("INSERT INTO t(text) VALUES ('hello world')")
            if db.execute("SELECT count(*) FROM t WHERE t MATCH 'hello'").fetchone()[0] != 1:
                return MESSAGE
        finally:
            db.close()
    except sqlite3.Error:
        return MESSAGE
    return None


class Fts5(unittest.TestCase):
    def test_fts5_is_available_in_the_docker_image(self):
        self.assertIsNone(fts5_problem(), MESSAGE)

    def test_the_check_fails_with_the_exact_message_when_fts5_is_missing(self):
        class NoFts5:
            def execute(self, sql, *a):
                if "fts5" in sql:
                    raise sqlite3.OperationalError("no such module: fts5")
                raise AssertionError(sql)

            def close(self):
                pass

        self.assertEqual(fts5_problem(lambda _p: NoFts5()), MESSAGE)

    def test_the_check_fails_when_a_search_finds_nothing(self):
        class Empty:
            def execute(self, sql, *a):
                class R:
                    def fetchone(self):
                        return (0,)
                return R()

            def close(self):
                pass

        self.assertEqual(fts5_problem(lambda _p: Empty()), MESSAGE)

    def test_the_index_itself_uses_fts5_the_way_this_check_does(self):
        self.assertIn("USING fts5", Path(ask_index.__file__).read_text())

    def test_the_image_named_is_the_one_in_compose(self):
        compose = (Path(__file__).resolve().parent.parent / "docker" / "compose.yaml").read_text()
        self.assertRegex(compose, re.compile(r"image: python:3\.12\.\d+-slim-bookworm"))


if __name__ == "__main__":
    unittest.main()

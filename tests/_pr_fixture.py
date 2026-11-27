"""A small git repository that stands in for a pull request, for the pre-CI tests (test_honesty_check, test_scope_check,
test_pre_ci). Nothing here touches the real repository or the network.

    with PrFixture() as pr:                 # a base commit: src/clark/mod.py and tests/test_mod.py
        pr.write("src/clark/mod.py", "...")
        head = pr.commit("change")          # the "pull request" head; pr.base is the commit it started from

`with_tools=True` also copies the real runner and the pre-CI tools in, so dev/tools/pre_ci.py runs inside the fixture exactly
as it runs here (the page build is replaced by a module that has nothing to build).
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from _paths import ROOT

EMAIL = "t@users.noreply.github.com"
MOD = "def double(n):\n    return n * 2\n"
TEST_MOD = '''"""The fixture's test file."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from clark import mod


class ModTest(unittest.TestCase):
    def test_double(self):
        self.assertEqual(mod.double(2), 4)
        self.assertEqual(mod.double(0), 0)

    def test_double_negative(self):
        self.assertEqual(mod.double(-1), -2)


if __name__ == "__main__":
    unittest.main()
'''
PAGE = '''"""Nothing to build in the fixture."""


class PageError(Exception):
    pass


def ensure_built():
    return None
'''
TOOLS = ("dev/run_tests.py", "dev/tools/run_support.py", "dev/tools/ci_scan.py", "dev/tools/publish_public.py",
         "dev/tools/honesty_check.py", "dev/tools/scope_check.py", "dev/tools/pre_ci.py")


class PrFixture:
    def __init__(self, with_tools=False):
        self.with_tools = with_tools
        self.dir = Path(tempfile.mkdtemp(prefix="pr-fixture-"))
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
                        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL=EMAIL, GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL=EMAIL)
        for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(k, None)
        self.git("init", "-q", "-b", "main")
        self.write("src/clark/__init__.py", "")
        self.write("src/clark/mod.py", MOD)
        self.write("tests/test_mod.py", TEST_MOD)
        if with_tools:
            self.write("src/clark/page.py", PAGE)
            self.write("tests/_paths.py", "from pathlib import Path\nROOT = Path(__file__).resolve().parent.parent\n")
            self.write("dev/tools/pre_ci_smoke.txt", "# the fixture's smoke suite\ntest_mod\n")
            self.write(".gitignore", "__pycache__/\ntests/.durations\ntests/.last-failed\ntests/.flaky.jsonl\n")
            for rel in TOOLS:
                (self.dir / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / rel, self.dir / rel)
        self.base = self.commit("base")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)

    def git(self, *args):
        r = subprocess.run(["git", *args], cwd=self.dir, env=self.env, capture_output=True, text=True)
        if r.returncode:
            raise AssertionError("git %s: %s" % (" ".join(args), r.stderr.strip()))
        return r.stdout.strip()

    def write(self, rel, text):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def read(self, rel):
        return (self.dir / rel).read_text(encoding="utf-8")

    def remove(self, rel):
        (self.dir / rel).unlink()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

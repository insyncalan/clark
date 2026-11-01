"""dev/tools/merge_main.sh: merges origin/main, rebuilds the generated pages, stops on real conflicts, never pushes.

Scratch git repos in a temp folder, a tiny fake dev/tools/build_page.py (pages = header + src/a.txt + src/b.txt, with
--check). Standard library only; starts no browser (quick tier).
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

SCRIPT = ROOT / "dev" / "tools" / "merge_main.sh"
ENV = dict(os.environ, GIT_AUTHOR_NAME="T", GIT_AUTHOR_EMAIL="t@example.invalid",
           GIT_COMMITTER_NAME="T", GIT_COMMITTER_EMAIL="t@example.invalid",
           GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
FAKE_BUILD = '''import sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
def want():
    return "header\\n" + (root / "src/a.txt").read_text(encoding="utf-8") + (root / "src/b.txt").read_text(encoding="utf-8")
pages = [root / "src/clark/page/page.html", root / "src/clark/page/page-view.html"]
if "--check" in sys.argv:
    if any(not p.exists() or p.read_text(encoding="utf-8") != want() for p in pages):
        print("out of date")
        sys.exit(1)
    sys.exit(0)
for p in pages:
    p.write_text(want(), encoding="utf-8")
'''


def git(cwd, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, env=ENV, capture_output=True, text=True)
    if check and r.returncode:
        raise AssertionError(f"git {args}: {r.stderr}")
    return r


class MergeMain(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="merge-main-"))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.bare = self.base / "remote.git"
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.bare))
        self.w = self.base / "work"
        git(self.base, "clone", "-q", str(self.bare), str(self.w))
        git(self.w, "checkout", "-q", "-b", "main")
        (self.w / "dev/tools").mkdir(parents=True)
        (self.w / "src/clark/page").mkdir(parents=True)
        (self.w / "dev/tools/build_page.py").write_text(FAKE_BUILD, encoding="utf-8")
        shutil.copy(SCRIPT, self.w / "dev/tools/merge_main.sh")
        self.write("src/a.txt", "a0\n")
        self.write("src/b.txt", "b0\n")
        self.build()
        git(self.w, "add", "-A")
        git(self.w, "commit", "-q", "-m", "base")
        git(self.w, "push", "-q", "origin", "main")
        git(self.w, "checkout", "-q", "-b", "feature")

    def write(self, rel, text):
        (self.w / rel).write_text(text, encoding="utf-8")

    def build(self):
        subprocess.run(["python3", "dev/tools/build_page.py"], cwd=self.w, check=True)

    def commit(self, msg):
        git(self.w, "add", "-A")
        git(self.w, "commit", "-q", "-m", msg)

    def edit_main(self, rel, text, rebuild):
        git(self.w, "checkout", "-q", "main")
        self.write(rel, text)
        if rebuild:
            self.build()
        self.commit("main change")
        git(self.w, "push", "-q", "origin", "main")
        git(self.w, "checkout", "-q", "feature")

    def run_script(self):
        return subprocess.run(["bash", "dev/tools/merge_main.sh"], cwd=self.w, env=ENV, capture_output=True, text=True)

    def remote_main(self):
        return git(self.bare, "rev-parse", "main").stdout.strip()

    def check_ok(self):
        return subprocess.run(["python3", "dev/tools/build_page.py", "--check"], cwd=self.w).returncode == 0

    def test_page_only_conflict_is_rebuilt(self):
        self.write("src/a.txt", "a1\n")
        self.build()
        self.commit("branch change")
        self.edit_main("src/b.txt", "b1\n", True)
        before = self.remote_main()
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.check_ok())
        self.assertEqual((self.w / "src/clark/page/page.html").read_text(encoding="utf-8"), "header\na1\nb1\n")
        self.assertEqual(git(self.w, "log", "-1", "--format=%s").stdout.strip(), "Merge origin/main")
        self.assertEqual(git(self.w, "status", "--porcelain").stdout, "")
        self.assertIn("Not pushed. Run the checks, then push once.", r.stdout)
        self.assertEqual(self.remote_main(), before)

    def test_source_conflict_stops(self):
        self.write("src/a.txt", "branch\n")
        self.commit("branch change")
        self.edit_main("src/a.txt", "main\n", False)
        head = git(self.w, "rev-parse", "HEAD").stdout
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("src/a.txt", r.stdout)
        self.assertIn("git merge --abort", r.stdout)
        self.assertTrue((self.w / ".git/MERGE_HEAD").exists())
        self.assertEqual(git(self.w, "rev-parse", "HEAD").stdout, head)

    def test_clean_merge_with_stale_page_is_rebuilt(self):
        self.write("src/a.txt", "a1\n")
        self.commit("branch change")
        self.edit_main("src/b.txt", "b1\n", False)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.check_ok())
        self.assertEqual(git(self.w, "log", "-1", "--format=%s").stdout.strip(), "Merge origin/main")
        self.assertEqual(len(git(self.w, "log", "-1", "--format=%P").stdout.split()), 2)
        self.assertEqual(git(self.w, "status", "--porcelain").stdout, "")

    def test_refuses_dirty_tree(self):
        self.edit_main("src/b.txt", "b1\n", True)
        self.write("src/a.txt", "dirty\n")
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("not clean", r.stdout)

    def test_refuses_detached_head(self):
        git(self.w, "checkout", "-q", "--detach")
        r = self.run_script()
        self.assertEqual(r.returncode, 1)
        self.assertIn("detached", r.stdout)

    def test_already_up_to_date(self):
        before = git(self.w, "rev-parse", "HEAD").stdout
        r = self.run_script()
        self.assertEqual(r.returncode, 0)
        self.assertIn("Already up to date", r.stdout)
        self.assertEqual(git(self.w, "rev-parse", "HEAD").stdout, before)


if __name__ == "__main__":
    unittest.main()

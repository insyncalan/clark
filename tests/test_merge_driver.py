"""#229: two branches that each change a different JSX source merge with no hand-resolved conflict, and the merged page files
equal a fresh build. Everything happens in a throwaway repository made under the temp folder; no real repository's config is read
or changed."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = "src/clark/page/src/components"
PAGES = ("src/clark/page/page.html", "src/clark/page/page-view.html")
LEFT_OUT = shutil.ignore_patterns(".git", "tests", "docs", "system", "__pycache__", "openpyxl", "et_xmlfile")


def run(cwd, *cmd, check=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(HOME=str(cwd), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        raise AssertionError(f"{' '.join(cmd)} -> {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def add_line(repo, name, line):
    with open(repo / SRC / name, "a", encoding="utf-8", newline="\n") as f:
        f.write(line)


class MergeDriverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="clark-merge-test-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        shutil.copytree(ROOT, self.repo, ignore=LEFT_OUT, symlinks=True)       # the sources, the build and the cached esbuild
        run(self.repo, "git", "init", "-q", "-b", "main")
        run(self.repo, "git", "add", "-A")
        run(self.repo, "git", "add", "-f", "vendor")           # the real repository tracks vendored dist folders that .gitignore's dist/ would skip
        run(self.repo, "git", "commit", "-q", "-m", "base")

    def branch(self, name, source, line):
        run(self.repo, "git", "checkout", "-q", "-b", name, "main")
        add_line(self.repo, source, line)
        run(self.repo, sys.executable, "dev/tools/build_page.py")
        run(self.repo, "git", "commit", "-q", "-am", name)

    def fresh(self):
        run(self.repo, sys.executable, "dev/tools/build_page.py")
        return {p: (self.repo / p).read_bytes() for p in PAGES}

    def two_branches(self):
        self.branch("one", "Icon.jsx", '\nglobalThis.mergeProbeOne = "one";\n')
        self.branch("two", "Menu.jsx", '\nglobalThis.mergeProbeTwo = "two";\n')
        run(self.repo, "git", "checkout", "-q", "one")

    def test_without_the_driver_the_page_files_conflict(self):
        self.two_branches()
        self.assertNotEqual(run(self.repo, "git", "merge", "--no-edit", "two", check=False).returncode, 0)

    def test_with_the_driver_different_sources_merge_and_the_pages_equal_a_fresh_build(self):
        self.two_branches()
        run(self.repo, sys.executable, "dev/tools/install_merge_driver.py")
        run(self.repo, "git", "merge", "--no-edit", "two")
        merged = {p: (self.repo / p).read_bytes() for p in PAGES}
        self.assertEqual(run(self.repo, "git", "status", "--porcelain").stdout, "")
        for p in PAGES:
            self.assertIn(b"mergeProbeOne", merged[p])
            self.assertIn(b"mergeProbeTwo", merged[p])
        self.assertEqual(merged, self.fresh())

    def test_a_conflict_in_a_source_is_still_a_conflict(self):
        self.branch("one", "Icon.jsx", '\nglobalThis.mergeProbe = "one";\n')
        self.branch("two", "Icon.jsx", '\nglobalThis.mergeProbe = "two";\n')
        run(self.repo, "git", "checkout", "-q", "one")
        run(self.repo, sys.executable, "dev/tools/install_merge_driver.py")
        self.assertNotEqual(run(self.repo, "git", "merge", "--no-edit", "two", check=False).returncode, 0)

    def test_the_driver_refuses_another_path_and_the_installer_refuses_outside_a_work_tree(self):
        r = run(self.repo, sys.executable, "dev/tools/merge_page.py", "a", "b", "c", "README.md", check=False)
        self.assertEqual(r.returncode, 2)
        loose = Path(self.tmp.name) / "loose" / "dev" / "tools"
        loose.mkdir(parents=True)
        shutil.copy(ROOT / "dev" / "tools" / "install_merge_driver.py", loose)
        self.assertEqual(run(loose, sys.executable, "install_merge_driver.py", check=False).returncode, 2)
        self.assertFalse((Path(self.tmp.name) / "loose" / ".git").exists())

    def test_the_gitattributes_entry_names_the_driver_for_both_pages(self):
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for p in PAGES:
            self.assertIn(f"{p} merge=clark-page", text)


if __name__ == "__main__":
    unittest.main()

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


def run(cwd, *cmd, check=True, path=None, extra_env=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra_env or {})
    if path is not None:
        env["PATH"] = path
    env.update(PYTHONDONTWRITEBYTECODE="1", HOME=str(cwd), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
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
        self.assert_markers()

    def assert_markers(self):
        """Every failure leaves conflict markers in both page files that git reports as unmerged; never a silently kept side."""
        for p in PAGES:
            text = (self.repo / p).read_text(encoding="utf-8")
            self.assertIn("<<<<<<< ours", text, p)
            self.assertIn("\n=======\n", text, p)
            self.assertIn(">>>>>>> theirs", text, p)

    def installed(self):
        run(self.repo, sys.executable, "dev/tools/install_merge_driver.py")
        return self.repo / ".git" / "clark-merge"

    def test_the_installer_copies_the_driver_outside_the_work_tree_and_records_the_commit(self):
        out = run(self.repo, sys.executable, "dev/tools/install_merge_driver.py")
        folder = self.repo / ".git" / "clark-merge"
        self.assertTrue((folder / "merge_page.py").is_file())
        commit = run(self.repo, "git", "rev-parse", "HEAD").stdout.strip()
        self.assertTrue((folder / "SOURCE-COMMIT").read_text(encoding="utf-8").startswith(commit))
        self.assertIn(str(folder), run(self.repo, "git", "config", "merge.clark-page.driver").stdout)
        self.assertIn("does not update with git pull", out.stdout)
        shown = run(self.repo, sys.executable, str(folder / "merge_page.py"), "--help").stdout
        self.assertIn(commit, shown)

    def test_the_driver_prints_the_installed_commit_to_stderr(self):
        folder = self.installed()
        r = run(self.repo, sys.executable, str(folder / "merge_page.py"), "a", "b", "c", "README.md", check=False)
        self.assertIn(run(self.repo, "git", "rev-parse", "HEAD").stdout.strip(), r.stderr)

    def test_the_installer_refuses_when_the_copy_does_not_run(self):
        broken = Path(self.tmp.name) / "bin"
        broken.mkdir()
        fake = broken / "python3"
        fake.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        fake.chmod(0o755)
        r = run(self.repo, sys.executable, "dev/tools/install_merge_driver.py", check=False, path=f"{broken}{os.pathsep}{os.environ['PATH']}")
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not run", r.stderr)
        self.assertNotEqual(run(self.repo, "git", "config", "--local", "--get", "merge.clark-page.driver", check=False).returncode, 0)

    def test_the_driver_still_works_on_a_branch_without_the_script(self):
        self.two_branches()
        self.installed()
        run(self.repo, "git", "checkout", "-q", "-b", "bare", "one")
        run(self.repo, "git", "rm", "-q", "dev/tools/merge_page.py", "dev/tools/install_merge_driver.py")
        run(self.repo, "git", "commit", "-q", "-m", "bare")
        run(self.repo, "git", "merge", "--no-edit", "two")
        self.assertEqual(run(self.repo, "git", "status", "--porcelain").stdout, "")

    def test_a_missing_script_leaves_markers(self):
        self.two_branches()
        folder = self.installed()
        (folder / "merge_page.py").unlink()
        self.assertNotEqual(run(self.repo, "git", "merge", "--no-edit", "two", check=False).returncode, 0)
        self.assert_markers()

    def test_the_wrappers_markers_have_exactly_the_layout_git_expects(self):
        self.two_branches()
        folder = self.installed()
        (folder / "merge_page.py").unlink()
        run(self.repo, "git", "merge", "--no-edit", "two", check=False)
        for p in PAGES:
            theirs = run(self.repo, "git", "show", f"two:{p}").stdout
            ours = run(self.repo, "git", "show", f"one:{p}").stdout
            text = (self.repo / p).read_text(encoding="utf-8")
            self.assertEqual(text, "<<<<<<< ours (merge driver could not run)\n" + ours.rstrip("\n") + "\n=======\n"
                             + theirs.rstrip("\n") + "\n>>>>>>> theirs\n", p)

    def test_the_python_markers_have_the_same_layout(self):
        r, text = self.drive_directly()
        self.assertEqual(r.returncode, 1)
        lines = text.split("\n")
        self.assertTrue(lines[0].startswith("<<<<<<< ours"), text)
        self.assertEqual(lines[1:], ["OURS PAGE", "=======", "THEIRS PAGE", ">>>>>>> theirs", ""])

    def test_an_unwritable_temp_folder_fails_loudly_and_never_keeps_ours_silently(self):
        self.two_branches()
        folder = self.installed()
        (folder / "merge_page.py").unlink()
        locked = Path(self.tmp.name) / "locked"
        locked.mkdir()
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)
        r = run(self.repo, "git", "merge", "--no-edit", "two", check=False, extra_env={"TMPDIR": str(locked)})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("could not write conflict markers", r.stdout + r.stderr)
        self.assertIn("src/clark/page/page.html", run(self.repo, "git", "diff", "--name-only", "--diff-filter=U").stdout)

    def stamp_and_drive(self, commit):
        folder = self.installed()
        (folder / "SOURCE-COMMIT").write_text(commit + "\n", encoding="utf-8")
        return run(self.repo, sys.executable, str(folder / "merge_page.py"), "a", "b", "c", "README.md", check=False).stderr

    OLDER = "This copy of the merge driver is older than the branch you are on. Run the installer again."

    def test_a_copy_from_a_commit_that_is_not_behind_the_branch_says_so(self):
        self.two_branches()                                  # on "one"
        side = run(self.repo, "git", "rev-parse", "two").stdout.strip()
        self.assertIn(self.OLDER, self.stamp_and_drive(side))

    def test_a_copy_from_an_ancestor_or_the_same_commit_or_an_unknown_one_says_nothing(self):
        self.two_branches()
        base = run(self.repo, "git", "rev-parse", "main").stdout.strip()
        head = run(self.repo, "git", "rev-parse", "HEAD").stdout.strip()
        for stamp in (base, head, head + " (merge_page.py has uncommitted changes)", "0" * 40, "unknown"):
            self.assertNotIn(self.OLDER, self.stamp_and_drive(stamp), stamp)

    def test_a_failed_build_leaves_markers(self):
        self.branch("one", "Icon.jsx", '\nglobalThis.mergeProbeOne = "one";\n')
        self.branch("two", "Menu.jsx", '\nglobalThis.mergeProbeTwo = "two";\n')
        add_line(self.repo, "Menu.jsx", "\nthis is not valid ((( code\n")                 # committed without a rebuild
        run(self.repo, "git", "commit", "-q", "-am", "broken source")
        run(self.repo, "git", "checkout", "-q", "one")
        self.installed()
        self.assertNotEqual(run(self.repo, "git", "merge", "--no-edit", "two", check=False).returncode, 0)
        self.assert_markers()

    def drive_directly(self, **kw):
        folder = self.installed()
        ours, theirs = Path(self.tmp.name) / "ours.html", Path(self.tmp.name) / "theirs.html"
        ours.write_text("OURS PAGE\n", encoding="utf-8")
        theirs.write_text("THEIRS PAGE\n", encoding="utf-8")
        r = run(self.repo, kw.pop("python", sys.executable), str(folder / "merge_page.py"), "base", str(ours), str(theirs), PAGES[0], check=False, **kw)
        return r, ours.read_text(encoding="utf-8")

    def test_unreadable_merge_state_leaves_markers(self):
        r, text = self.drive_directly()                     # no merge in progress: no other side to read
        self.assertEqual(r.returncode, 1)
        self.assertTrue(text.startswith("<<<<<<< ours") and "OURS PAGE" in text and "THEIRS PAGE" in text and "=======" in text and text.rstrip().endswith(">>>>>>> theirs"), text)

    def test_any_unexpected_error_leaves_markers(self):
        r, text = self.drive_directly(path=os.devnull)     # git cannot be found: an exception inside the driver
        self.assertEqual(r.returncode, 1)
        self.assertIn("<<<<<<< ours", text)
        self.assertIn("THEIRS PAGE", text)

    def test_the_driver_refuses_another_path_and_the_installer_refuses_outside_a_work_tree(self):
        r = run(self.repo, sys.executable, "dev/tools/merge_page.py", "a", "b", "c", "README.md", check=False)
        self.assertEqual(r.returncode, 2)
        loose = Path(self.tmp.name) / "loose" / "dev" / "tools"
        loose.mkdir(parents=True)
        shutil.copy(ROOT / "dev" / "tools" / "install_merge_driver.py", loose)
        self.assertEqual(run(loose, sys.executable, "install_merge_driver.py", check=False).returncode, 2)
        self.assertFalse((Path(self.tmp.name) / "loose" / ".git").exists())

    def test_a_branch_that_changes_the_build_code_is_not_run_during_the_merge(self):
        self.branch("one", "Icon.jsx", '\nglobalThis.mergeProbeOne = "one";\n')
        run(self.repo, "git", "checkout", "-q", "-b", "evil", "main")
        probe = Path(self.tmp.name) / "ran-branch-code"
        add_line(self.repo, "Menu.jsx", '\nglobalThis.mergeProbeTwo = "two";\n')
        run(self.repo, sys.executable, "dev/tools/build_page.py")                 # built before the tools change, so the probe never runs here
        tools = self.repo / "dev" / "tools" / "build_page.py"
        tools.write_text(f"open({str(probe)!r}, 'w').close()\n" + tools.read_text(encoding="utf-8"), encoding="utf-8")
        run(self.repo, "git", "commit", "-q", "-am", "evil")
        run(self.repo, "git", "checkout", "-q", "one")
        self.installed()
        r = run(self.repo, "git", "merge", "--no-edit", "evil", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(probe.exists(), "the merged branch's build code ran")
        self.assertIn("will not run code from the branch being merged", r.stderr + r.stdout)
        self.assert_markers()

    def test_a_branch_that_changes_only_page_sources_still_resolves_by_itself(self):
        self.two_branches()
        self.installed()
        self.assertEqual(run(self.repo, "git", "merge", "--no-edit", "two", check=False).returncode, 0)

    def test_unpack_refuses_a_path_that_leaves_the_folder_and_any_link(self):
        import importlib.util
        import io
        import tarfile
        spec = importlib.util.spec_from_file_location("merge_page_under_test", ROOT / "dev" / "tools" / "merge_page.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for kind in ("escape", "symlink", "hardlink"):
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tar:
                m = tarfile.TarInfo({"escape": "../x", "symlink": "link", "hardlink": "hard"}[kind])
                if kind == "escape":
                    m.size = 1
                    tar.addfile(m, io.BytesIO(b"x"))
                else:
                    m.type = tarfile.SYMTYPE if kind == "symlink" else tarfile.LNKTYPE
                    m.linkname = "/etc/passwd" if kind == "symlink" else "target"
                    tar.addfile(m)
            into = Path(self.tmp.name) / ("out-" + kind)
            into.mkdir()
            with self.assertRaises(ValueError):
                mod.unpack(buf.getvalue(), str(into))
            self.assertEqual(list(into.iterdir()), [])
            self.assertFalse((into.parent / "x").exists())
        good = io.BytesIO()
        with tarfile.open(fileobj=good, mode="w") as tar:
            m = tarfile.TarInfo("a/b.txt")
            m.size = 2
            tar.addfile(m, io.BytesIO(b"ok"))
        into = Path(self.tmp.name) / "out-good"
        into.mkdir()
        mod.unpack(good.getvalue(), str(into))
        self.assertEqual((into / "a" / "b.txt").read_bytes(), b"ok")

    def test_uninstall_removes_both_settings_and_the_copy(self):
        folder = self.installed()
        run(self.repo, sys.executable, "dev/tools/install_merge_driver.py", "--uninstall")
        self.assertFalse(folder.exists())
        for key in ("driver", "name"):
            self.assertNotEqual(run(self.repo, "git", "config", "--local", "--get", f"merge.clark-page.{key}", check=False).returncode, 0)
        run(self.repo, sys.executable, "dev/tools/install_merge_driver.py", "--uninstall")      # again: nothing left, still fine

    def test_cherry_pick_rebase_and_squash_never_lose_a_page_silently(self):
        self.two_branches()
        self.installed()
        tip = run(self.repo, "git", "rev-parse", "two").stdout.strip()
        # cherry-pick and rebase: assert what really happens, either a good merged page or a conflict with markers, never ours alone
        for how in (("cherry-pick", tip), ("rebase", "two")):
            run(self.repo, "git", "checkout", "-q", "-B", "work-" + how[0], "one")
            r = run(self.repo, "git", *how, check=False)
            for p in PAGES:
                text = (self.repo / p).read_text(encoding="utf-8")
                if r.returncode == 0:
                    self.assertTrue(b"mergeProbeOne" in text.encode() and b"mergeProbeTwo" in text.encode(), how)
                else:
                    self.assertIn("<<<<<<< ", text, how)
            run(self.repo, "git", how[0], "--abort", check=False)
            run(self.repo, "git", "reset", "-q", "--hard")
        run(self.repo, "git", "checkout", "-q", "-B", "work-squash", "one")
        run(self.repo, "git", "merge", "--squash", "two")
        for p in PAGES:
            text = (self.repo / p).read_text(encoding="utf-8")
            self.assertTrue("mergeProbeOne" in text and "mergeProbeTwo" in text and "<<<<<<<" not in text, p)

    def test_the_gitattributes_entry_names_the_driver_for_both_pages(self):
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for p in PAGES:
            self.assertIn(f"{p} merge=clark-page", text)


if __name__ == "__main__":
    unittest.main()

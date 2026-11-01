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

    def driver_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("merge_page_under_test", ROOT / "dev" / "tools" / "merge_page.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_only_page_data_is_allowed_to_change(self):
        mod = self.driver_module()
        for ok in ("src/clark/page/src/components/Icon.jsx", "src/clark/page/src/help/helpContent.json", "src/clark/page/shell.css",
                   *PAGES):
            self.assertTrue(mod.page_data(ok), ok)
        for bad in ("src/clark/__pycache__/__init__.cpython-39.pyc", "src/clark/page/src/x.py", "src/clark/page/__init__.py",
                    "src/clark/page/src/__pycache__/a.jsx", "src/clark/page/assets/x.css", "src/clark/x.css", "src/Clark/page/shell.css",
                    "src/clark/page/__init__.abi3.so", "src/x.pth", "vendor/fonts/inter/manifest.json", "dev/tools/esbuild.py"):
            self.assertFalse(mod.page_data(bad), bad)

    def test_the_build_code_set_names_every_file_the_build_imports(self):
        """BUILD_CODE must hold every repository file the build imports: a new import from outside it fails here."""
        import ast
        import importlib.util
        import sysconfig
        mod = self.driver_module()
        ours = {"esbuild": "dev/tools/esbuild.py", "clark": "src/clark/__init__.py", "clark.page": "src/clark/page/__init__.py"}
        stdlib = os.path.realpath(sysconfig.get_paths()["stdlib"])
        for name in mod.BUILD_CODE:
            for node in ast.walk(ast.parse((ROOT / name).read_text(encoding="utf-8"))):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                    [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for n in names:
                    if n in ours:
                        self.assertIn(ours[n], mod.BUILD_CODE, n)
                        continue
                    spec = importlib.util.find_spec(n.split(".")[0])
                    origin = getattr(spec, "origin", None) or ""
                    self.assertTrue(origin in ("built-in", "frozen") or os.path.realpath(origin).startswith(stdlib),
                                    f"{name} imports {n}, which is neither the standard library nor in BUILD_CODE")

    def hostile_merge(self, plant, why=None):
        """Branch "evil" changes a page source (so the page conflicts) and plants something; merging it into "one" must refuse:
        markers in both pages, the probe file the planted code would make does not exist, and stderr names the reason."""
        self.branch("one", "Icon.jsx", '\nglobalThis.mergeProbeOne = "one";\n')
        run(self.repo, "git", "checkout", "-q", "-b", "evil", "main")
        add_line(self.repo, "Menu.jsx", '\nglobalThis.mergeProbeTwo = "two";\n')
        run(self.repo, sys.executable, "dev/tools/build_page.py")
        probe = Path(self.tmp.name) / "hostile-code-ran"
        plant(probe)
        run(self.repo, "git", "add", "-A", "-f", "src", "dev/tools")
        run(self.repo, "git", "commit", "-q", "-am", "evil")
        self.assertFalse(probe.exists(), "the test planted code that ran too early")
        run(self.repo, "git", "checkout", "-q", "one")
        self.installed()
        r = run(self.repo, "git", "merge", "--no-edit", "evil", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assert_markers()
        self.assertFalse(probe.exists(), "code from the merged branch ran during the merge")
        self.assertIn("will not run code from the branch being merged" if why is None else why, r.stderr + r.stdout)
        return r

    @staticmethod
    def payload(probe):
        return f"open({str(probe)!r}, 'w').close()\n"

    def prepend(self, rel, probe):
        f = self.repo / rel
        f.write_text(self.payload(probe) + f.read_text(encoding="utf-8"), encoding="utf-8")

    def test_a_force_added_bytecode_file_is_refused(self):
        def plant(probe):
            source = Path(self.tmp.name) / "evil_init.py"
            source.write_text(self.payload(probe), encoding="utf-8")
            # compiled by the python3 the driver runs with, unchecked, so without the fix the import would load it
            run(self.repo, "python3", "-c", "import py_compile, sys, importlib.util as u; py_compile.compile(sys.argv[1], "
                "cfile='src/clark/__pycache__/__init__.' + sys.implementation.cache_tag + '.pyc', "
                "invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)", str(source))
        r = self.hostile_merge(plant)
        self.assertIn("src/clark/__pycache__/__init__.", r.stderr)

    def test_a_compiled_module_under_src_is_refused(self):
        def plant(probe):
            (self.repo / "src" / "clark" / "page" / "__init__.abi3.so").write_bytes(b"\x7fELF not really")
        r = self.hostile_merge(plant)
        self.assertIn("src/clark/page/__init__.abi3.so", r.stderr)

    def test_a_new_python_file_under_src_clark_is_refused(self):
        r = self.hostile_merge(lambda probe: (self.repo / "src" / "clark" / "extra_hook.py").write_text(self.payload(probe), encoding="utf-8"))
        self.assertIn("src/clark/extra_hook.py", r.stderr)

    def test_a_changed_esbuild_py_is_refused(self):
        self.hostile_merge(lambda probe: self.prepend("dev/tools/esbuild.py", probe))

    def test_a_changed_page_package_is_refused(self):
        self.hostile_merge(lambda probe: self.prepend("src/clark/page/__init__.py", probe))

    def test_a_changed_vendored_font_manifest_is_refused(self):
        def plant(probe):
            f = self.repo / "vendor" / "fonts" / "inter" / "manifest.json"
            f.write_text(f.read_text(encoding="utf-8").replace("{", "{\"x\": 1, ", 1), encoding="utf-8")
        self.hostile_merge(plant)

    def test_a_symlink_member_is_refused(self):
        def plant(probe):
            os.symlink(str(probe), str(self.repo / SRC / "Link.jsx"))
        self.hostile_merge(plant, why="something other than a plain file")

    def test_a_link_already_on_both_sides_is_never_unpacked(self):
        os.symlink("clark-icon.svg", str(self.repo / "src" / "clark" / "page" / "assets" / "alias.svg"))
        run(self.repo, "git", "add", "-A")
        run(self.repo, "git", "commit", "-q", "-m", "a link in the base")
        self.two_branches()
        self.installed()
        r = run(self.repo, "git", "merge", "--no-edit", "two", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assert_markers()
        self.assertIn("unsafe entry (src/clark/page/assets/alias.svg)", r.stderr)

    def test_a_write_through_the_cache_path_never_reaches_the_real_cache(self):
        """HEAD's own build (trusted, so it runs) writes into dev/.cache; the write lands in the temporary copy only."""
        tools = self.repo / "dev" / "tools" / "build_page.py"
        tools.write_text(tools.read_text(encoding="utf-8").replace(
            'if __name__ == "__main__":', '(HERE.parent / ".cache" / "esbuild" / "written-by-build").write_text("x")\n\n\nif __name__ == "__main__":'),
            encoding="utf-8")
        run(self.repo, "git", "commit", "-q", "-am", "a build that writes into its cache")
        self.two_branches()
        real = self.repo / "dev" / ".cache" / "esbuild"
        before = {p: p.read_bytes() for p in real.rglob("*") if p.is_file() and p.name != "written-by-build"}
        (real / "written-by-build").unlink()                     # the branch builds above wrote it in the clone itself
        self.installed()
        run(self.repo, "git", "merge", "--no-edit", "two")
        self.assertFalse((real / "written-by-build").exists(), "the merge build wrote into the clone's real dev/.cache")
        self.assertEqual({p: p.read_bytes() for p in real.rglob("*") if p.is_file()}, before)
        self.assertFalse((self.repo / "dev" / ".cache").is_symlink())

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

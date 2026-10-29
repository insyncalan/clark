"""The Mac download that dev/tools/package.py builds (#57, step 3 of docs/handoff/packaging-57.md).

Builds into temporary folders only and downloads nothing. Run: python3 dev/run_tests.py test_package
"""
import contextlib
import functools
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT
import package


def tracked(*paths):
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--", *paths], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


class MacZipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="clark package ")
        cls.zip = package.build("mac", Path(cls.tmp) / "one", dirty=True)
        cls.top = package.top_folder()
        with zipfile.ZipFile(cls.zip) as z:
            cls.infos = {i.filename: i for i in z.infolist()}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def inside(self):
        """The names in the zip, without the top folder."""
        return sorted(n[len(self.top) + 1:] for n in self.infos)

    def test_one_top_folder_named_for_the_version(self):
        self.assertEqual(f"clark-{package.version()}-mac.zip", self.zip.name)
        self.assertEqual({self.top}, {n.split("/")[0] for n in self.infos})
        self.assertRegex(self.top, r"^clark-\d")

    def test_entries_are_exactly_the_file_list(self):
        expected = set()
        for item in package.listed("mac"):
            expected.update(tracked(item) if item.endswith("/") else [item])
        expected = {p for p in expected if not package.LEFT_OUT.search(p)} | {"START-HERE.txt"}
        self.assertEqual(sorted(expected), self.inside())
        self.assertEqual(sorted(self.infos), list(self.infos), "entries are in sorted order")

    def test_nothing_from_outside_the_list(self):
        for name in self.inside():
            with self.subTest(name=name):
                self.assertFalse(name.startswith(("tests/", "docs/", "system/", "comms/", ".git", "dist/")))
                self.assertFalse(name.startswith("dev/") and name != "dev/demo_data.py")
                self.assertFalse(name.startswith(("vendor/preact/", "vendor/tiptap/")), "page build only")
                self.assertNotIn("__pycache__", name)
                self.assertNotIn(".DS_Store", name)
                self.assertFalse(name.endswith((".db", ".log", ".pyc")))

    def test_what_clark_needs_is_there(self):
        names = set(self.inside())
        for needed in ("clark.command", "clark/__main__.py", "src/clark/__main__.py", "src/clark/page/page.html",
                       "src/clark/schema.sql", "vendor/openpyxl/__init__.py", "vendor/et_xmlfile/__init__.py",
                       "vendor/manifest.json", "README.md", "START-HERE.txt"):
            self.assertIn(needed, names)

    def test_demo_file_follows_the_switch(self):
        self.assertEqual(package.INCLUDE_DEMO, "dev/demo_data.py" in self.inside())

    def test_clark_command_keeps_its_run_bit(self):
        for name, info in self.infos.items():
            with self.subTest(name=name):
                self.assertEqual(package.UNIX, info.create_system)
                mode = info.external_attr >> 16
                self.assertTrue(stat.S_ISREG(mode))
                want = 0o755 if name == f"{self.top}/clark.command" else 0o644
                self.assertEqual(want, stat.S_IMODE(mode))

    def test_fixed_times(self):
        self.assertEqual({package.FIXED_TIME}, {i.date_time for i in self.infos.values()})

    def test_two_builds_are_byte_identical(self):
        again = package.build("mac", Path(self.tmp) / "two", dirty=True)
        self.assertEqual(self.zip.read_bytes(), again.read_bytes())

    def test_runs_from_a_folder_with_spaces(self):
        where = Path(self.tmp) / "My Downloads" / "a folder with spaces"
        where.mkdir(parents=True)
        with zipfile.ZipFile(self.zip) as z:
            z.extractall(where)
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        run = subprocess.run([sys.executable, "-m", "clark", "--help"], cwd=str(where / self.top), env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertIn("--data", run.stdout)
        self.assertIn("--demo", run.stdout)

    @unittest.skipUnless(shutil.which("unzip"), "needs the unzip command")
    def test_unzip_keeps_the_run_bit(self):
        where = Path(self.tmp) / "unzipped here"
        where.mkdir()
        subprocess.run(["unzip", "-q", str(self.zip), "-d", str(where)], check=True, timeout=60)
        self.assertTrue(os.access(where / self.top / "clark.command", os.X_OK))
        self.assertFalse(os.access(where / self.top / "README.md", os.X_OK))

    def test_start_here_in_plain_words(self):
        with zipfile.ZipFile(self.zip) as z:
            text = z.read(f"{self.top}/START-HERE.txt").decode("utf-8")
        self.assertEqual(package.start_here("mac"), text)
        self.assertIn("clark.command", text)
        self.assertIn("bash", text, "the fallback when the run bit is lost")
        self.assertNotIn("Clark", text)
        for line in text.splitlines():
            self.assertFalse(line.strip().lower().startswith("clark"), line)
        self.assertEqual(package.INCLUDE_DEMO, "--demo" in text)
        self.assertIn("If your Mac is missing something it needs, clark.command says how to get it.", text)
        self.assertIn("python3 -m clark.doctor", text, "where the checks are run from")
        self.assertNotIn("open Terminal in this folder", text, "the drag-into-Terminal steps are given instead")
        self.assertNotIn("!", text)

    def test_the_default_build_says_it_is_for_the_team_only(self):
        with zipfile.ZipFile(self.zip) as z:
            text = z.read(f"{self.top}/START-HERE.txt").decode("utf-8")
        self.assertEqual("This download is for the team only; it is built from the private copy.", text.splitlines()[0])
        self.assertNotIn(package.TEAM_ONLY, package.start_here("mac", for_client=True))


class CommandTest(unittest.TestCase):
    def run_main(self, *argv):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = package.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_windows_is_not_built_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self.run_main("windows", "--out", tmp)
            self.assertEqual(1, code)
            self.assertIn("Windows download isn't built yet", err)
            self.assertEqual([], os.listdir(tmp))

    def test_refuses_uncommitted_changes_without_dirty(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(package, "uncommitted", return_value=" M README.md"):
            code, out, err = self.run_main("mac", "--out", tmp)
            self.assertEqual(1, code)
            self.assertEqual(err.strip(), "Some of the files that go in the zip have changes that aren't committed: "
                                          "README.md. Commit them first, or add --dirty to build from them as they are.")
            self.assertEqual([], os.listdir(tmp))

    def test_the_changed_files_are_read_from_git_status(self):
        self.assertEqual(package.changed_files(" M README.md\n?? vendor/new.py\nR  old.py -> src/clark/new.py"),
                         ["README.md", "vendor/new.py", "src/clark/new.py"])
        self.assertEqual(package.changed_files(""), [])

    def test_a_missing_file_is_said_plainly(self):
        with mock.patch.object(package, "SHARED", package.SHARED + ("vendor/fictional_missing/",)):
            with self.assertRaises(package.Refused) as said:
                package.files("mac")
        self.assertEqual(str(said.exception), "A file the download needs is missing: vendor/fictional_missing/. Restore it, "
                                              "then build again.")

    def test_builds_into_the_out_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self.run_main("mac", "--out", tmp, "--dirty")
            self.assertEqual(0, code, err)
            self.assertEqual([package.zip_name("mac")], os.listdir(tmp))
            self.assertTrue(out.startswith("Built the Mac download: "), out)
            self.assertIn(package.zip_name("mac"), out)
            self.assertTrue(out.strip().endswith("This download is for the team only; it is built from the private copy."), out)

    def test_the_built_line_shows_no_home_folder(self):
        self.assertEqual(package.shown(package.ROOT / "dist" / "x.zip"), "dist/x.zip")
        self.assertEqual(package.shown(Path.home() / "fictional" / "x.zip"), "~/fictional/x.zip")

    def test_dist_is_ignored_by_git(self):
        run = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "dist/clark-0-mac.zip"])
        self.assertEqual(0, run.returncode)


class ForClientTest(unittest.TestCase):
    """--for-client: only from the scrubbed snapshot, and only when the name guard finds nothing. Temporary folders only."""

    def run_main(self, *argv):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = package.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def out_folder(self):
        tmp = tempfile.mkdtemp(prefix="clark package ")
        self.addCleanup(shutil.rmtree, tmp, True)
        return Path(tmp) / "out"

    def snapshot(self, files, author=None):
        """A small temporary repo that looks like the publish tool's snapshot: no private notes, one neutral commit."""
        pub = package.publish_tool()
        tmp = tempfile.mkdtemp(prefix="clark snapshot ")
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        base = {"README.md": "A fictional public README.\n", "src/clark/__init__.py": '__version__ = "0.0.1"\n',
                "clark.command": "#!/bin/bash\necho start\n"}
        for name, text in {**base, **files}.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        name, email = author or (pub.AUTHOR_NAME, pub.AUTHOR_EMAIL)
        git = ["git", "-C", str(root), "-c", "user.name=" + name, "-c", "user.email=" + email, "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "--no-verify", "-m", "clark v0.0.1 (0000000)"], check=True)
        return root

    def build_small(self, root, out, banned=None):
        with mock.patch.object(package, "SHARED", ("README.md", "src/clark/")), \
                mock.patch.object(package, "SYSTEMS", {"mac": ("clark.command",)}):
            return package.build("mac", out, root=root, for_client=True, banned=banned)

    def private_tree(self):
        """A small temporary repo that looks like a private checkout: it tracks the public README's source and a team
        note, which no snapshot does. Its last commit is by the tool's own author, so the notes alone must refuse it.
        Built here, not read from the folder the tests run in: in the public snapshot that folder is the scrubbed one."""
        return self.snapshot({"docs/public/README.md": "A fictional public README.\n", "dev/HEAD-LOG.md": "A fictional note.\n"})

    def run_main_in(self, root, *argv):
        """main(), with the build reading `root` instead of the checkout the tests run from."""
        with mock.patch.object(package, "build", functools.partial(package.build, root=root)):
            return self.run_main(*argv)

    def test_refuses_from_a_private_tree_and_writes_nothing(self):
        out = self.out_folder()
        code, stdout, err = self.run_main_in(self.private_tree(), "mac", "--for-client", "--out", str(out))
        self.assertEqual(1, code)
        self.assertEqual("", stdout)
        self.assertIn("must be built from the scrubbed public snapshot", err)
        self.assertIn("this folder is the private copy", err)
        self.assertIn("Nothing was written.", err)
        self.assertFalse(out.exists())

    def test_refuses_with_dirty(self):
        out = self.out_folder()
        code, _, err = self.run_main_in(self.snapshot({}), "mac", "--for-client", "--dirty", "--out", str(out))
        self.assertEqual(1, code)
        self.assertIn("--for-client can't be used with --dirty", err)
        self.assertFalse(out.exists())

    def test_refuses_a_tree_whose_last_commit_is_not_the_publish_tool_s(self):
        root = self.snapshot({}, author=("Sam Carter", "sam.carter@example.com"))
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            self.build_small(root, out)
        self.assertIn("its last commit was not made by the publish tool", str(said.exception))
        self.assertFalse(out.exists())

    def test_refuses_naming_the_file_with_a_planted_fictional_name(self):
        from test_no_real_names import FICTIONAL      # the guard's own fictional names, so no real one is written here
        root = self.snapshot({"src/clark/notes.py": "# Prepared for Northwind Traders\nx = 1\n"})
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            self.build_small(root, out, banned=FICTIONAL)
        text = str(said.exception)
        self.assertIn("the name guard found one in: src/clark/notes.py.", text)
        self.assertIn("Nothing was written.", text)
        self.assertNotIn("orthwind", text.lower())
        self.assertNotIn("README.md", text)
        self.assertFalse(out.exists())

    def test_refuses_a_team_name_from_the_publish_tool_s_own_list(self):
        persona = package.publish_tool().PEOPLE_ANY_CASE[1]          # read from the one list, never written here
        root = self.snapshot({"src/clark/views.py": f"# asked for by {persona}\n"})
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            self.build_small(root, out)
        self.assertIn("found one in: src/clark/views.py.", str(said.exception))
        self.assertNotIn(persona.lower(), str(said.exception).lower())
        self.assertFalse(out.exists())

    def test_a_name_in_a_file_s_own_path_is_counted_not_shown(self):
        from test_no_real_names import FICTIONAL
        root = self.snapshot({"src/clark/northwind.py": "x = 1\n"})
        with self.assertRaises(package.Refused) as said:
            self.build_small(root, self.out_folder(), banned=FICTIONAL)
        self.assertIn("1 file(s) whose own name holds one (not shown)", str(said.exception))
        self.assertNotIn("orthwind", str(said.exception).lower())

    def test_builds_from_a_clean_scrubbed_tree(self):
        from test_no_real_names import FICTIONAL
        root = self.snapshot({"src/clark/notes.py": "# fictional sample data only\n"})
        out = self.out_folder()
        target = self.build_small(root, out, banned=FICTIONAL)
        with zipfile.ZipFile(target) as z:
            names = sorted(z.namelist())
            start = z.read("clark-0.0.1/START-HERE.txt").decode("utf-8")
        self.assertEqual(["clark-0.0.1/README.md", "clark-0.0.1/START-HERE.txt", "clark-0.0.1/clark.command",
                          "clark-0.0.1/src/clark/__init__.py", "clark-0.0.1/src/clark/notes.py"], names)
        self.assertNotIn("team only", start)
        self.assertEqual(package.start_here("mac", for_client=True), start)
        self.assertIsNone(package.snapshot_problem(root))


if __name__ == "__main__":
    unittest.main()

"""The Mac download that dev/tools/package.py builds (#57, step 3 of docs/handoff/packaging-57.md).

Builds into temporary folders only and downloads nothing. Run: python3 dev/run_tests.py test_package
"""
import contextlib
import functools
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT
import package
from clark import release_files


def tracked(*paths):
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z", "--", *paths], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


PRODUCT_NAME_START = re.compile(r"^\s*(?:[-*]\s+|\d+[.)]\s+)?clark\b", re.IGNORECASE)     # CLARK_PORT=... is a setting, not the name


def starts_with_product_name(text):
    """The lines of `text` that start with the word clark (after indent and a list marker), in any case."""
    return [line for line in text.splitlines() if PRODUCT_NAME_START.match(line)]


class ProductNameGuardTest(unittest.TestCase):
    def test_guard_trips_on_any_line_that_starts_with_the_name(self):
        """issue 719: not only "clark's own": any START-HERE line starting with the word clark is caught; settings are not."""
        for line in ("clark starts here.", "  Clark is a program.", "- clark.command starts it.", "3. CLARK keeps data.", "clark's own files"):
            self.assertEqual([line], starts_with_product_name(f"fine line\n{line}\nfine"), line)
        for line in ("        CLARK_PORT=8800 docker compose up -d", "Open clark.", "The clark folder"):
            self.assertEqual([], starts_with_product_name(line), line)


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
        """The names in the zip, without the top folder (as placed: program files under .app/)."""
        return sorted(n[len(self.top) + 1:] for n in self.infos)

    def test_one_top_folder_called_clark_and_a_zip_named_for_the_version(self):
        self.assertEqual(f"clark-{package.version()}-mac.zip", self.zip.name)
        self.assertEqual({self.top}, {n.split("/")[0] for n in self.infos})
        self.assertEqual("clark", self.top)

    def test_entries_are_exactly_the_file_list(self):
        expected = set()
        for item in package.listed("mac"):
            expected.update(tracked(item) if item.endswith("/") else [item])
        expected = {p for p in expected if not package.LEFT_OUT.search(p)} | {"START-HERE.md", package.MANIFEST} | set(package.GENERATED_PAGES)     # #495: built, not tracked
        expected = {release_files.place(p) for p in expected}       # issue 694: program files sit under .app/
        self.assertEqual(sorted(expected), self.inside())
        self.assertEqual(sorted(self.infos), list(self.infos), "entries are in sorted order")

    def test_nothing_from_outside_the_list(self):
        for name in (release_files.unplace(n) for n in self.inside()):
            with self.subTest(name=name):
                self.assertFalse(name.startswith(("tests/", "docs/", "system/", "comms/", ".git", "dist/")))
                self.assertFalse(name.startswith("dev/") and name != "dev/demo_data.py")
                self.assertFalse(name.startswith(("vendor/preact/", "vendor/tiptap/")), "page build only")
                self.assertNotIn("__pycache__", name)
                self.assertNotIn(".DS_Store", name)
                self.assertFalse(name.endswith((".db", ".log", ".pyc")))

    def test_what_clark_needs_is_there(self):
        names = set(self.inside())
        for needed in ("clark.command", ".app/clark/__main__.py", ".app/src/clark/__main__.py", ".app/src/clark/page/page.html",
                       ".app/src/clark/schema.sql", ".app/vendor/openpyxl/__init__.py", ".app/vendor/et_xmlfile/__init__.py",
                       ".app/vendor/manifest.json", "README.md", "START-HERE.md",
                       ".app/vendor/pypdf/__init__.py", ".app/vendor/pypdf/LICENSE", ".app/vendor/typing_extensions.py"):
            self.assertIn(needed, names)

    def test_the_zips_readme_is_the_zip_readme_and_not_the_repositorys(self):
        """#751: the README at the top of the zip is docs/zip/README.md, written for the download; the root README.md stays
        for the repository and is not in the zip."""
        with zipfile.ZipFile(self.zip) as z:
            held = z.read(f"{self.top}/README.md")
        self.assertEqual((package.ROOT / release_files.ZIP_README).read_bytes(), held)
        self.assertNotEqual((package.ROOT / "README.md").read_bytes(), held)
        self.assertNotIn(b"docs/zip", held)

    def test_the_zips_readme_has_no_picture_no_repository_and_no_link_out_of_the_zip(self):
        """#751: nothing in the download's README points outside the download: no image, no word 'repository', no file link that
        is missing from the unzipped folder, no path of the source tree."""
        import re
        with zipfile.ZipFile(self.zip) as z, tempfile.TemporaryDirectory() as folder:
            z.extractall(folder)
            base = Path(folder) / self.top
            text = (base / "README.md").read_text(encoding="utf-8")
            self.assertNotRegex(text, r"!\[", "no picture")
            self.assertNotRegex(text, r"<img\b|\.(png|jpe?g|gif|svg)\b", "no picture file")
            self.assertNotIn("repository", text.lower())
            for banned in ("SECURITY.md", "docs/", "dev/run_tests", "dev/tools/", "tests/", "python3 -m clark"):
                self.assertNotIn(banned, text, banned)
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue                                    # a web address or an anchor in the page itself
                self.assertTrue((base / target.split("#")[0]).exists(), f"the link {target} points at nothing in the download")

    def test_the_zip_carries_no_docs_folder_and_no_pictures_of_the_repository_readme(self):
        """#751: the root README's pictures live in docs/img; the zip's README uses none, so the zip holds no docs/ folder at all."""
        names = self.inside()
        self.assertEqual([], [n for n in names if n.startswith(("docs/", ".app/docs/"))])
        self.assertEqual([], [n for n in names if n.lower().endswith((".png", ".jpg", ".jpeg", ".gif")) and not n.startswith((".app/src/", ".app/vendor/"))])

    def test_every_build_refuses_without_the_zip_readme(self):
        """#751: a plain, a --dirty, a release and a client build all refuse when docs/zip/README.md is missing, in the same words;
        none can ship the repository's own README.md by mistake."""
        said = ("A release or a client zip carries docs/zip/README.md as its README.md, and that file is missing. "
                "Nothing was written. Restore it, then build again.")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            (root / "src/clark").mkdir(parents=True)
            (root / "README.md").write_text("A repository README.\n", encoding="utf-8")
            (root / "src/clark/__init__.py").write_text('__version__ = "0.0.1"\n', encoding="utf-8")
            (root / "src/clark/store.py").write_text("SCHEMA_VERSION = 1\n", encoding="utf-8")
            for kind, kwargs in (("plain", {}), ("dirty", {"dirty": True}), ("release", {"release": True}), ("client", {"for_client": True, "dirty": False})):
                with self.subTest(kind=kind), mock.patch.object(package, "SHARED", ("README.md", "src/clark/")), \
                        mock.patch.object(package, "tag_problem", return_value=None), mock.patch.object(package, "snapshot_problem", return_value=None):
                    with self.assertRaises(package.Refused) as caught:
                        package.build("mac", Path(tmp) / "out", root=root, **kwargs)
                    self.assertEqual(said, str(caught.exception))
                    self.assertFalse((Path(tmp) / "out").exists() and any((Path(tmp) / "out").iterdir()))

    def test_licence_and_notice_are_in_the_zip(self):
        """#639: LICENSE and NOTICE.md travel with the code; the list, the zip and the manifest all hold them."""
        import json
        self.assertIn("LICENSE", package.SHARED)
        self.assertIn("NOTICE.md", package.SHARED)
        names = set(self.inside())
        with zipfile.ZipFile(self.zip) as z:
            files = json.loads(z.read(f"{self.top}/{package.MANIFEST}"))["files"]
        for name in (".app/LICENSE", ".app/NOTICE.md"):
            with self.subTest(name=name):
                self.assertIn(name, names)
                self.assertIn(name, files)
                self.assertRegex(files[name]["sha256"], r"^[0-9a-f]{64}$")
                self.assertGreater(files[name]["size"], 0)

    def test_demo_file_follows_the_switch(self):
        self.assertEqual(package.INCLUDE_DEMO, ".app/dev/demo_data.py" in self.inside())

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
        run = subprocess.run([sys.executable, "-m", "clark", "--help"], cwd=str(where / self.top / ".app"), env=env,
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

    def test_the_built_zip_carries_the_md_start_file_and_not_the_txt_one(self):
        """The built zip writes START-HERE.md (1.0.5 on); the 1.0.4 name START-HERE.txt is read by the updater but never written."""
        with zipfile.ZipFile(self.zip) as z:
            names = z.namelist()
            listed = json.loads(z.read(f"{self.top}/{package.MANIFEST}"))["files"]
        self.assertEqual("START-HERE.md", package.START_HERE)
        self.assertIn(f"{self.top}/START-HERE.md", names)
        self.assertNotIn(f"{self.top}/START-HERE.txt", names)
        self.assertIn("START-HERE.md", listed)
        self.assertNotIn("START-HERE.txt", listed)

    def test_the_built_zip_is_accepted_by_the_reader_with_the_md_start_file(self):
        """Both ways: the zip as built (.md) passes the updater's coverage check; the same names with the 1.0.4 .txt do too; both or neither do not."""
        from clark import updates
        from clark.updates import UpdateError
        with zipfile.ZipFile(self.zip) as z:
            rels = [n[len(self.top) + 1:] for n in z.namelist() if n != self.top + "/" and n != f"{self.top}/{package.MANIFEST}"]
        self.assertIn("START-HERE.md", rels)
        updates.check_coverage("mac", rels)
        txt = [("START-HERE.txt" if r == "START-HERE.md" else r) for r in rels]
        updates.check_coverage("mac", txt)
        with self.assertRaises(UpdateError) as both:
            updates.check_coverage("mac", rels + ["START-HERE.txt"])
        self.assertEqual("unsafe", both.exception.key)
        with self.assertRaises(UpdateError) as none:
            updates.check_coverage("mac", [r for r in rels if r != "START-HERE.md"])
        self.assertEqual("incomplete", none.exception.key)

    def test_start_here_in_plain_words(self):
        with zipfile.ZipFile(self.zip) as z:
            text = z.read(f"{self.top}/START-HERE.md").decode("utf-8")
        self.assertEqual(package.start_here("mac"), text)
        self.assertIn("clark.command", text)
        self.assertIn("bash", text, "the fallback when the run bit is lost")
        self.assertNotIn("Clark", text)
        for line in text.splitlines():
            if not line.strip().startswith(("CLARK_DATA_DIR=", "CLARK_PORT=")):     # item 427: a command to type, which sets a variable
                self.assertFalse(line.strip().lower().startswith("clark"), line)
        self.assertEqual(package.INCLUDE_DEMO, "--demo" in text)
        self.assertEqual(package.INCLUDE_DEMO, "   bash clark.command --demo --open\n" in text)
        self.assertIn("If your Mac is missing something it needs, clark.command says how to get it.", text)
        self.assertIn("   bash clark.command --check\n", text, "where the checks are run from (issue 694: the download has no python3 -m clark)")
        self.assertNotIn("python3 -m", text)
        self.assertNotIn("open Terminal in this folder", text, "the drag-into-Terminal steps are given instead")
        self.assertNotIn("!", text)

    def test_start_here_leads_with_docker_in_typed_commands_and_the_zip_holds_what_it_needs(self):
        """item 427: a computer that will not open clark.command uses Docker and Chrome only. The guide says it first, as commands to
        type (never a .command file), and the download holds the compose file it names."""
        text = package.start_here("mac")
        up = "docker compose -f docker/compose.yaml up -d"
        self.assertIn(up, text)
        self.assertIn("docker compose -f docker/compose.yaml down", text)
        self.assertIn("http://localhost:8766", text)
        self.assertLess(text.index(up), text.index("1. Double-click clark.command"), "Docker is said first")
        self.assertIn("Install clark", text)
        self.assertIn("OneDrive", text)
        self.assertIn("A folder inside OneDrive cannot be used by clark.", text)
        self.assertIn("Start Docker from the clark folder.", text)     # item 652: not "refused"
        self.assertNotIn("refused", text.lower())
        self.assertNotIn("clark-docker.command", text)
        # item 615: the second route says what a managed Mac really does (an unsigned download is stopped), and what to do about it.
        self.assertIn("Do not\n   choose Move to Trash: choose Done", text)
        self.assertIn("Privacy & Security", text)
        self.assertIn("Open Anyway", text)
        self.assertIn("administrator's password", text)
        self.assertIn("   bash clark.command", text, "the typed way, which needs no password")
        self.assertNotIn("Control-click", text, "that way stopped working for an unsigned download on current macOS")
        with zipfile.ZipFile(self.zip) as z:
            names = set(z.namelist())
        self.assertIn(f"{self.top}/docker/compose.yaml", names)
        self.assertNotIn(f"{self.top}/docker/Dockerfile", names, "item 427: a stock Python image, no image of clark's own")

    def test_start_here_names_only_the_variables_the_compose_file_reads(self):
        """item 427: a variable START-HERE tells a person to set must be one compose.yaml really reads (a wrong name, such as the
        old CLARK_DATA, does nothing: clark starts on the empty data folder and the person believes their own is in use)."""
        text = package.start_here("mac")
        compose = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        said = set(re.findall(r"\b(CLARK_[A-Z_]+)=", text))
        read = set(re.findall(r"\$\{(CLARK_[A-Z_]+)(?::-|-|\})", compose))
        self.assertEqual(said, {"CLARK_DATA_DIR", "CLARK_PORT"})
        self.assertLessEqual(said, read, f"START-HERE sets {sorted(said - read)}, which compose.yaml does not read")
        self.assertNotIn("CLARK_DATA=", text)

    def test_start_here_says_where_docker_keeps_the_data_and_the_two_ways_never_share_it_at_once(self):
        flat = " ".join(package.start_here("mac").split())
        self.assertIn("These steps are for a Mac.", flat)
        self.assertIn("With Docker, your data is kept in ~/Library/Application Support/clark, the same place clark.command uses, not in this folder, "
                      "so you can swap this folder for a newer download without losing anything.", flat)
        self.assertIn('CLARK_DATA_DIR="/full/path" docker compose -f docker/compose.yaml up -d', flat)
        self.assertNotIn("beside the clark files", flat)
        self.assertIn("Use the clark download, not a copy of the source code: a copy of the source has no built page, and Docker stops with a message saying so.", flat)
        self.assertIn("To see what Docker has said, type this in the same folder:", flat)
        self.assertIn("docker compose -f docker/compose.yaml logs --tail 50", flat)
        warning = ("By default clark.command and Docker use the same data. IMPORTANT: Never open the same data from clark.command "
                   "and from Docker at the same time: stop one before you start the other.")
        self.assertIn(warning, flat)
        lines = package.start_here("mac").splitlines()
        self.assertTrue(any(l.startswith("IMPORTANT: Never open the same data") for l in lines), "the warning starts its own line")
        self.assertLess(flat.index("With Docker, your data"), flat.index(warning))
        self.assertLess(flat.index(warning), flat.index("To use another port"))
        self.assertIn("CLARK_PORT=8800 docker compose -f docker/compose.yaml up -d then open http://localhost:8800 instead.", flat)
        self.assertLess(flat.index("With Docker, your data"), flat.index("Without Docker:"))
        self.assertIn("Without Docker, your data is kept in ~/Library/Application Support/clark", flat)

    def test_start_here_says_what_is_in_the_folder_and_how_to_swap_an_old_clark(self):
        """issue 694: the one-folder download is described, and an update by hand is told as six short numbered steps."""
        text = package.start_here("mac")
        flat = " ".join(text.split())
        self.assertIn("What is in this folder: README.md says what clark is. START-HERE.md is this page. Double-click clark.command to start clark. "
                      "docker is for starting clark with Docker. branding holds your own logo and colours, if you add them. "
                      "The program files are in a hidden folder called .app: you do not need to open it.", flat)
        self.assertLess(flat.index("These steps are for a Mac."), flat.index("What is in this folder:"))
        self.assertIn("If an earlier Docker start kept your data in a data folder inside the clark folder, move that data folder out of the "
                      "clark folder first, or name it with CLARK_DATA_DIR. By default clark.command and Docker use the same data.", flat)
        for block in (text, package.START_HERE_MAC, package.START_HERE_DEMO):
            self.assertEqual(starts_with_product_name(block), [])     # a sentence does not start with the product name
        self.assertLess(flat.index("What is in this folder:"), flat.index("If your Mac will not open"))
        steps = ["If you already have clark:", "1. Close clark.", "2. Rename your old clark folder (for example to clark-old) or move it away, "
                 "so the two folders do not clash.", "3. Unzip this download.", "4. If you added your own logo or colours, copy the "
                 "branding folder (an older clark keeps it in system/branding) from the old clark folder into the new one. An update never changes that folder, but replacing the "
                 "whole clark folder by hand removes it.", "5. If you use Docker and your data is in a data folder inside the old clark "
                 "folder, move that data folder out of it before you delete the old folder, or start Docker with CLARK_DATA_DIR naming it.",
                 '6. Double-click clark.command. Your Mac may ask you to confirm clark.command again: do as in step 2 under "Without Docker" below.',
                 "Your projects are not in the old clark folder: they stay in ~/Library/Application Support/clark. Updating "
                 "from inside clark is switched off, so install this version by hand."]
        line = flat[flat.index("Updating from inside clark"):][:90]
        self.assertNotRegex(line, r"\d+\.\d+", "the updating sentence carries no version number")
        at = -1
        for part in steps:
            found = flat.find(part)
            self.assertGreater(found, at, part)
            at = found
        self.assertLess(flat.index("6. Double-click clark.command."), flat.index("Without Docker:"))

    def test_the_default_build_says_what_is_true_of_the_tree_it_was_built_from(self):
        """This checkout is what is published on the public repository (#463): it tracks no private-only path, so the zip
        is not 'for the team only'. DefaultAudienceTest pins both lines and the tree that holds a private path."""
        with zipfile.ZipFile(self.zip) as z:
            text = z.read(f"{self.top}/START-HERE.md").decode("utf-8")
        self.assertEqual([], package.private_paths(package.ROOT), "no private-only path is tracked on main")
        self.assertEqual(package.PUBLIC_BUILD, text.splitlines()[0])
        self.assertNotIn("team only", text)
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
            self.assertTrue(out.strip().endswith(package.audience(package.ROOT)), out)
            self.assertNotIn("team only", out)

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
        base = {"README.md": "A fictional public README.\n", "docs/zip/README.md": "A fictional download README.\n", "src/clark/__init__.py": '__version__ = "0.0.1"\n', "src/clark/store.py": "SCHEMA_VERSION = 1\n",
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
            start = z.read("clark/START-HERE.md").decode("utf-8")
        self.assertEqual(["clark/.app/src/clark/__init__.py", "clark/.app/src/clark/notes.py", "clark/.app/src/clark/store.py",
                          "clark/README.md", "clark/START-HERE.md", "clark/clark-release.json", "clark/clark.command"], names)
        self.assertNotIn("team only", start)
        self.assertEqual(package.start_here("mac", for_client=True), start)
        self.assertIsNone(package.snapshot_problem(root))


class PlacedLayoutTest(unittest.TestCase):
    """issue 694: the zip holds one folder `clark`, program files in .app, the compose file changed in exactly one line,
    and nothing that belongs to the person. Small temporary repos, plus the real build once."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="clark placed ")
        cls.zip = package.build("mac", Path(cls.tmp) / "one", dirty=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_zip_keeps_its_versioned_name_and_the_folder_does_not(self):
        self.assertEqual("clark", package.top_folder())
        self.assertEqual(f"clark-{package.version()}-mac.zip", package.zip_name("mac"))

    def test_the_manifest_keys_are_the_placed_names_and_the_updater_reads_the_real_zip(self):
        import json
        with zipfile.ZipFile(self.zip) as z:
            members = {n[len("clark/"):] for n in z.namelist()}
            files = json.loads(z.read("clark/" + package.MANIFEST))["files"]
        self.assertEqual(members - {package.MANIFEST}, set(files))
        for name in (".app/src/clark/__init__.py", ".app/clark/launch.py", "README.md", "docker/compose.yaml", "clark.command"):
            self.assertIn(name, files)
        self.assertFalse([n for n in files if n.startswith(("src/", "vendor/", "clark/"))])
        import _signing
        from clark import updates
        _signing.trust_test_key(self)
        _signing.sign_file(self.zip)
        release = updates.read_release(self.zip, "mac", "0.0.0", package.schema_version())
        self.assertEqual(package.version(), release.version)

    def test_nothing_of_the_person_s_is_in_the_zip(self):
        with zipfile.ZipFile(self.zip) as z:
            for name in z.namelist():
                with self.subTest(name=name):
                    self.assertFalse(name.startswith(("clark/system", "clark/data")), name)
                    self.assertFalse(name.startswith(("clark/.app/system", "clark/.app/data")), name)

    def test_the_compose_file_in_the_zip_differs_in_the_one_working_dir_line(self):
        repo = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8").splitlines()
        with zipfile.ZipFile(self.zip) as z:
            made = z.read("clark/docker/compose.yaml").decode("utf-8").splitlines()
        self.assertEqual(len(repo), len(made))
        changed = [(a, b) for a, b in zip(repo, made) if a != b]
        self.assertEqual([("    working_dir: /clark", "    working_dir: /clark/.app")], changed)
        self.assertIn("        source: ..", made, "the bind stays the whole clark folder, so branding is seen")
        self.assertEqual("    working_dir: /clark", next(ln for ln in repo if "working_dir" in ln), "the repo's own file is untouched")

    def test_the_compose_change_is_refused_unless_the_line_is_found_exactly_once(self):
        ok = b"a: 1\n    working_dir: /clark\nb: 2\n"
        self.assertEqual(b"a: 1\n    working_dir: /clark/.app\nb: 2\n", package.compose_for_zip(ok))
        for bad in (b"a: 1\n", b"    working_dir: /clark\n    working_dir: /clark\n", b"    working_dir: /clark/x\n",
                    b"  working_dir: /clark\n"):
            with self.subTest(bad=bad), self.assertRaises(package.Refused):
                package.compose_for_zip(bad)

    def test_a_tracked_path_under_system_or_data_refuses_the_build(self):
        for kept in ("branding/logo.png", "system/branding/logo.png", "data/clark.db", "System/x.txt"):
            with self.subTest(kept=kept):
                root = ForClientTest.snapshot(self, {kept: "mine\n"})
                out = Path(self.tmp) / ("refused " + kept.replace("/", "-"))
                with mock.patch.object(package, "SHARED", ("README.md", "src/clark/", kept.split("/")[0] + "/")), \
                        mock.patch.object(package, "SYSTEMS", {"mac": ("clark.command",)}), \
                        self.assertRaises(package.Refused) as said:
                    package.build("mac", out, root=root, dirty=True)
                self.assertIn(kept, str(said.exception))
                self.assertFalse(out.exists())


class DefaultAudienceTest(unittest.TestCase):
    """The audience line of a default build (not --for-client) follows the tree: a tree that tracks any private-only path
    is for the team only, whatever else is true of it; a tree that tracks none is built from the public repository (#463).
    Small temporary repos only."""
    PUBLIC = "This download holds none of the team's private notes."
    TEAM = "This download is for the team only; it is built from the private copy."

    def tree(self, extra=None):
        root = ForClientTest.snapshot(self, extra or {})
        return root

    def small_build(self, root):
        out = Path(tempfile.mkdtemp(prefix="clark package "))
        self.addCleanup(shutil.rmtree, out, True)
        with mock.patch.object(package, "SHARED", ("README.md", "src/clark/")), \
                mock.patch.object(package, "SYSTEMS", {"mac": ("clark.command",)}):
            target = package.build("mac", out / "o", root=root)
        with zipfile.ZipFile(target) as z:
            return z.read("clark/START-HERE.md").decode("utf-8")

    def built_line(self, root):
        err, out = io.StringIO(), io.StringIO()
        with mock.patch.object(package, "ROOT", root), \
                mock.patch.object(package, "build", functools.partial(package.build, root=root)), \
                mock.patch.object(package, "SHARED", ("README.md", "src/clark/")), \
                mock.patch.object(package, "SYSTEMS", {"mac": ("clark.command",)}), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = package.main(["mac", "--out", str(root / "dist")])
        self.assertEqual(0, code, err.getvalue())
        return out.getvalue().strip()

    def test_the_two_lines_are_pinned(self):
        self.assertEqual(self.PUBLIC, package.PUBLIC_BUILD)
        self.assertEqual(self.TEAM, package.TEAM_ONLY)

    def test_a_tree_with_no_private_path_says_public_in_start_here_and_in_the_built_line(self):
        root = self.tree()
        self.assertEqual([], package.private_paths(root))
        self.assertEqual(self.PUBLIC, package.audience(root))
        start = self.small_build(root)
        self.assertEqual(self.PUBLIC, start.splitlines()[0])
        self.assertNotIn("team only", start)
        self.assertNotIn("private copy", start)
        line = self.built_line(root)
        self.assertTrue(line.endswith(self.PUBLIC), line)
        self.assertNotIn("team only", line)

    def test_the_public_line_one_is_the_ruled_sentence_and_never_says_repository(self):
        """Row 759: the public build's line 1 is exactly this sentence and has no word 'repository'."""
        start = self.small_build(self.tree())
        first = start.splitlines()[0]
        self.assertEqual("This download holds none of the team's private notes.", first)
        self.assertNotIn("repository", first.lower())
        self.assertFalse(first.lower().startswith("clark"))

    def test_a_tree_that_still_tracks_a_private_path_stays_team_only(self):
        for path in ("dev/HEAD-LOG.md", "docs/DECISIONS.md", "docs/TEAM-AND-ROLES.md", "docs/public/README.md"):
            with self.subTest(path=path):
                root = self.tree({path: "A fictional note.\n"})
                self.assertEqual([path], package.private_paths(root))
                self.assertEqual(self.TEAM, package.audience(root))
                start = self.small_build(root)
                self.assertEqual(self.TEAM, start.splitlines()[0])
                self.assertNotIn("built from the public repository", start)
                self.assertEqual("This download is for the team only; it is built from the private copy.", start.splitlines()[0])
                line = self.built_line(root)
                self.assertTrue(line.endswith(self.TEAM), line)

    def test_a_folder_git_cannot_read_is_team_only(self):
        tmp = tempfile.mkdtemp(prefix="clark not a repo ")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.assertIsNone(package.private_paths(tmp))
        self.assertEqual(self.TEAM, package.audience(tmp))

    def test_a_git_that_hangs_is_team_only_and_is_asked_with_a_timeout(self):
        """LOW 3 of the tech-debt list for item 463: git is never waited on for ever. A hang reads as 'git cannot say'."""
        seen = []

        def hang(cmd, **kw):
            seen.append(kw.get("timeout"))
            raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))
        with mock.patch.object(package.subprocess, "run", side_effect=hang):
            self.assertIsNone(package.private_paths(package.ROOT))
            self.assertEqual(self.TEAM, package.audience(package.ROOT))
        self.assertTrue(seen and all(isinstance(t, (int, float)) and t > 0 for t in seen), seen)

    def test_a_client_zip_has_no_audience_line(self):
        self.assertNotIn(self.TEAM, package.start_here("mac", for_client=True))
        self.assertNotIn(self.PUBLIC, package.start_here("mac", for_client=True))


class GitHangTest(unittest.TestCase):
    """Every git call in package.py is given GIT_TIMEOUT. The git on PATH here is a shim that sleeps, so a call with no
    timeout would sit for the whole sleep; each call must come back well before it, and files() must not raise
    TimeoutExpired (it refuses, as Refused, like the other callers)."""
    SLEEP = 20
    LIMIT = 8       # seconds a call may take; GIT_TIMEOUT is patched to 1

    def setUp(self):
        shim = Path(tempfile.mkdtemp(prefix="clark git shim "))
        self.addCleanup(shutil.rmtree, shim, True)
        git = shim / "git"
        git.write_text(f"#!/bin/sh\nexec sleep {self.SLEEP}\n", encoding="utf-8")
        git.chmod(0o755)
        env = mock.patch.dict(os.environ, {"PATH": f"{shim}{os.pathsep}{os.environ.get('PATH', '')}"})
        env.start()
        self.addCleanup(env.stop)
        limit = mock.patch.object(package, "GIT_TIMEOUT", 1)
        limit.start()
        self.addCleanup(limit.stop)

    def prompt(self, call):
        began = time.monotonic()
        try:
            result = call()
        except BaseException as e:
            result = e
        self.assertLess(time.monotonic() - began, self.LIMIT)
        return result

    def test_tracked_is_asked_with_the_limit(self):
        self.assertIsInstance(self.prompt(lambda: package.tracked(ROOT, ["src/clark/"])), subprocess.TimeoutExpired)

    def test_files_refuses_and_does_not_raise_timeout_expired(self):
        got = self.prompt(lambda: package.files("mac", ROOT))
        self.assertIsInstance(got, package.Refused)
        self.assertIn("git did not answer", str(got))

    def test_the_audience_and_the_snapshot_check_read_a_hang_as_team_only(self):
        self.assertEqual(package.TEAM_ONLY, self.prompt(lambda: package.audience(ROOT)))
        self.assertIn("could not list", self.prompt(lambda: package.snapshot_problem(ROOT)))

    def test_the_last_commit_check_alone_comes_back(self):
        with mock.patch.object(package, "private_paths", return_value=[]):
            got = self.prompt(lambda: package.snapshot_problem(ROOT))
        self.assertIn("isn't a public snapshot", got)

    def test_released_on_falls_back_to_today(self):
        import datetime
        self.assertEqual(datetime.date.today().isoformat(), self.prompt(lambda: package.released_on(ROOT)))

    def test_uncommitted_refuses(self):
        got = self.prompt(lambda: package.uncommitted(ROOT, ["README.md"]))
        self.assertIsInstance(got, package.Refused)
        self.assertIn("git did not answer", str(got))

    def test_tag_problem_says_git_could_not(self):
        self.assertIn("did not say which tag", self.prompt(lambda: package.tag_problem(ROOT, "1.2.3")))


class ReleaseFromTagTest(unittest.TestCase):
    """A --release zip is built only from the commit tagged for its version (#400)."""

    def repo(self):
        root = Path(tempfile.mkdtemp(prefix="clark tag "))
        self.addCleanup(shutil.rmtree, root, True)
        (root / "src" / "clark").mkdir(parents=True)
        (root / "src" / "clark" / "__init__.py").write_text('__version__ = "1.2.3"\n', encoding="utf-8")
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-C", str(root)]
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "one"], check=True)
        return root, git

    def test_untagged_tree_is_refused_and_nothing_is_written(self):
        root, _ = self.repo()
        out = root / "out"
        with self.assertRaises(package.Refused) as cm:
            package.build("mac", out, root=root, release=True)
        self.assertIn("not at the tag v1.2.3", str(cm.exception))
        self.assertFalse(out.exists())

    def test_the_wrong_tag_is_refused_and_the_right_one_passes_the_check(self):
        root, git = self.repo()
        subprocess.run(git + ["tag", "v1.2.4"], check=True)
        self.assertIn("v1.2.3", package.tag_problem(root, "1.2.3"))
        subprocess.run(git + ["tag", "v1.2.3"], check=True)
        self.assertIsNone(package.tag_problem(root, "1.2.3"))

    def test_release_with_dirty_is_refused(self):
        root, _ = self.repo()
        with self.assertRaises(package.Refused) as cm:
            package.build("mac", root / "out", root=root, release=True, dirty=True)
        self.assertIn("--dirty", str(cm.exception))

    def test_not_a_git_folder_is_refused(self):
        tmp = Path(tempfile.mkdtemp(prefix="clark not git "))
        self.addCleanup(shutil.rmtree, tmp, True)
        self.assertIn("could not say", package.tag_problem(tmp, "1.2.3"))


STATUS = """Package: bash
Status: install ok installed
Architecture: amd64
Version: 5.2.15-2+b7

Package: oldthing
Status: deinstall ok config-files
Architecture: amd64
Version: 1.0

Package: libssl3
Status: install ok installed
Architecture: amd64
Version: 3.0.17-1~deb12u2
"""
COPYRIGHTS = {"bash": "Files: *\nLicense: GPL-3+\n", "libssl3": "see the Apache License, Version 2.0"}


class ImagePapersTest(unittest.TestCase):
    """Item 637: the generators for THIRD-PARTY-IMAGE.txt and the SBOM (not called by the build)."""

    def test_only_installed_packages_are_read(self):
        self.assertEqual(["bash", "libssl3"], [p["name"] for p in package.image_packages(STATUS)])

    def test_licences_come_from_license_lines_or_known_names(self):
        self.assertEqual(["GPL-2+", "LGPL-2.1+"], package.image_licences("Files: *\nLicense: LGPL-2.1+ and GPL-2+\n"))
        self.assertEqual(["Apache-2.0"], package.image_licences("see the Apache License, Version 2.0"))
        self.assertEqual([], package.image_licences(""))

    def test_lgpl_text_naming_the_gpl_is_not_also_gpl(self):
        text = "GNU Lesser General Public License ... you may also use the GNU General Public License"
        self.assertEqual(["LGPL"], package.image_licences(text))
        self.assertEqual(["GPL"], package.image_licences("GNU General Public License"))

    def test_dual_gpl_and_lgpl_wording_keeps_both(self):
        for text in ("GNU Lesser General Public License, or the GNU General Public License",
                     "under the GNU General Public License or the GNU Lesser General Public License",
                     "either the GNU Lesser General Public License or, at your option, GPL-2",
                     "GNU Lesser General Public License; see /usr/share/common-licenses/GPL-2"):
            self.assertEqual(["GPL", "LGPL"], package.image_licences(text), text)
        boiler = ("This library is free software; you can redistribute it and/or modify it under the terms of the GNU Lesser General Public "
                  "License as published by the Free Software Foundation; either version 2.1 of the License. See /usr/share/common-licenses/LGPL-2.1")
        self.assertEqual(["LGPL"], package.image_licences(boiler))

    def test_purl_percent_encodes_special_characters(self):
        sbom = package.image_sbom([{"name": "g++", "version": "1:12.2@x y/z", "arch": "amd64"}], {}, [{"name": "A_b", "version": "1+local"}])
        self.assertEqual("pkg:deb/debian/g%2B%2B@1:12.2%40x%20y%2Fz?arch=amd64", sbom["components"][0]["purl"])
        self.assertEqual("pkg:pypi/a-b@1%2Blocal", sbom["components"][1]["purl"])

    def test_sbom_is_cyclonedx_with_every_package_and_purl(self):
        sbom = package.image_sbom(package.image_packages(STATUS), COPYRIGHTS, [{"name": "Pip", "version": "24.0"}], "python:3.12-slim")
        self.assertEqual(("CycloneDX", "1.5"), (sbom["bomFormat"], sbom["specVersion"]))
        self.assertEqual(["bash", "libssl3", "Pip"], [c["name"] for c in sbom["components"]])
        self.assertEqual("pkg:deb/debian/bash@5.2.15-2%2Bb7?arch=amd64", sbom["components"][0]["purl"])
        self.assertEqual([{"license": {"name": "GPL-3+"}}], sbom["components"][0]["licenses"])
        self.assertEqual("pkg:pypi/pip@24.0", sbom["components"][-1]["purl"])
        json.dumps(sbom)

    def test_text_names_every_package_with_licences_and_flags_a_missing_copyright_file(self):
        text = package.image_third_party(package.image_packages(STATUS), {"bash": COPYRIGHTS["bash"]}, [], "python:3.12-slim")
        for needle in ("python:3.12-slim", "bash 5.2.15-2+b7: GPL-3+", "libssl3 3.0.17-1~deb12u2: see /usr/share/doc/libssl3/copyright"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


def _files_in_zip(listed_items):
    """The names (as the zip holds them) that a list of items produces from the tracked files."""
    out = []
    for item in listed_items:
        names = tracked(item) if item.endswith("/") else [item]
        out += [release_files.place(n) for n in names]
    return out


class PreviousReleaseAcceptsThisOneTest(unittest.TestCase):
    """Item 1151: an installed older version checks a new zip against ITS OWN list (updates.check_coverage). Tests used to
    check the new list against the new zip only, so 1.0.7 (new vendor/pypdf/) was refused by every 1.0.6 computer."""

    @staticmethod
    def _old_module(tag):
        r = subprocess.run(["git", "-C", str(ROOT), "show", f"{tag}:src/clark/release_files.py"], capture_output=True)
        if r.returncode != 0:
            return None
        import types
        mod = types.ModuleType("old_release_files")
        exec(compile(r.stdout, f"{tag}/release_files.py", "exec"), mod.__dict__)
        return mod

    @staticmethod
    def unsafe_for(old, system="mac"):
        """The names this tree's zip would hold that the older list `old` does not cover (what check_coverage calls unsafe)."""
        return sorted(n for n in _files_in_zip(release_files.listed(system)) if not old.covers(system, n))

    def test_an_older_list_missing_a_path_is_caught(self):
        import types
        old = types.SimpleNamespace(covers=lambda system, rel: not rel.startswith(".app/vendor/pypdf/"))
        found = self.unsafe_for(old)
        self.assertTrue(found and all(n.startswith(".app/vendor/pypdf/") for n in found))

    def test_the_last_release_list_covers_every_file_of_this_tree(self):
        tags = subprocess.run(["git", "-C", str(ROOT), "tag", "--list", "v*", "--sort=-v:refname"], capture_output=True, text=True).stdout.split()
        if not tags:
            shallow = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--is-shallow-repository"], capture_output=True, text=True).stdout.strip()
            if shallow == "true":
                self.skipTest("shallow clone with no release tags (push runs use depth 1; pull request runs fetch all tags)")
            self.fail("no v* release tag in a full clone: fetch tags (git fetch --tags)")
        old = self._old_module(tags[0])
        self.assertIsNotNone(old, tags[0])
        self.assertEqual([], self.unsafe_for(old), f"{tags[0]} would refuse this tree's zip as outside its own list")


if __name__ == "__main__":
    unittest.main()

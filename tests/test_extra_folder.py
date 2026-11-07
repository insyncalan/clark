"""Extra top-level folders in a download (issue 716): package.py --extra-folder, and the updater that reads, plans and swaps them.

The folders are not in git. Every test builds a tiny fake one in a temporary folder. Run: python3 dev/run_tests.py test_extra_folder
"""
import contextlib
import io
import json
import os
import shutil
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

import _signing
import package
from clark import release_files, update_helper as h, update_install as ui, updates
from test_update_helper import Once, snapshot
from test_update_install import Base, STAMP, install, install_release
from test_updates import listed_files, make_zip

MEET = {"README.txt": b"meet notes\n", "templates/one.md": b"# one\n", "templates/two.md": b"# two\n"}
INTAKE = {"form.txt": b"intake form\n"}


def make_folder(base, name, files):
    folder = Path(base) / name
    for rel, data in files.items():
        p = folder / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return folder


def refusal(case, *folders, **kw):
    """The plain sentence of the Refused that build() raises for `folders` (checks nothing was written)."""
    out = Path(case.tmp) / ("out-" + str(len(os.listdir(case.tmp))))
    with case.assertRaises(package.Refused) as said:
        package.build("mac", out, dirty=True, extra_folders=list(folders), **kw)
    case.assertFalse(out.exists(), "a refused build writes nothing")
    case.assertNotIn("\n", str(said.exception))
    return str(said.exception)


class Build(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="clark extra ")
        cls.meet = make_folder(cls.tmp, "meet clark", MEET)
        cls.intake = make_folder(cls.tmp, "intake", INTAKE)
        cls.zip = package.build("mac", Path(cls.tmp) / "one", dirty=True, extra_folders=[cls.meet, cls.intake])
        with zipfile.ZipFile(cls.zip) as z:
            cls.infos = {i.filename: i for i in z.infolist()}
            cls.manifest = json.loads(z.read("clark/" + package.MANIFEST))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_each_folder_is_at_the_top_under_its_own_name(self):
        for rel in MEET:
            self.assertIn(f"clark/meet clark/{rel}", self.infos)
        self.assertIn("clark/intake/form.txt", self.infos)
        self.assertEqual({"clark"}, {n.split("/")[0] for n in self.infos})

    def test_regular_files_mode_0644_and_the_fixed_time(self):
        for name, info in self.infos.items():
            if name.startswith(("clark/meet clark/", "clark/intake/")):
                with self.subTest(name=name):
                    self.assertEqual(0o644, stat.S_IMODE(info.external_attr >> 16))
                    self.assertTrue(stat.S_ISREG(info.external_attr >> 16))
                    self.assertEqual(package.FIXED_TIME, info.date_time)
                    self.assertEqual(3, info.create_system)
        self.assertEqual(sorted(self.infos), list(self.infos), "entries stay sorted")

    def test_the_manifest_lists_every_file_in_the_zip_except_itself(self):
        names = {n[len("clark/"):] for n in self.infos} - {package.MANIFEST}
        self.assertEqual(names, set(self.manifest["files"]))
        row = self.manifest["files"]["meet clark/templates/one.md"]
        self.assertEqual((len(MEET["templates/one.md"]), "644"), (row["size"], row["mode"]))

    def test_entries_lists_them_too(self):
        self.assertIn("clark/intake/form.txt", package.entries("mac", extra_folders=[self.intake]))
        self.assertNotIn("clark/intake/form.txt", package.entries("mac"))

    def test_two_builds_are_byte_identical_whatever_the_order_of_the_flags(self):
        again = package.build("mac", Path(self.tmp) / "two", dirty=True, extra_folders=[self.intake, self.meet])
        self.assertEqual(self.zip.read_bytes(), again.read_bytes())

    def test_without_the_flag_the_zip_has_no_extra_folder(self):
        plain = package.build("mac", Path(self.tmp) / "plain", dirty=True)
        with zipfile.ZipFile(plain) as z:
            self.assertEqual([], [n for n in z.namelist() if n.startswith(("clark/meet clark/", "clark/intake/"))])

    def test_the_flag_may_be_repeated_on_the_command_line(self):
        out = Path(self.tmp) / "cli"
        with contextlib.redirect_stdout(io.StringIO()):
            code = package.main(["mac", "--dirty", "--out", str(out), "--extra-folder", str(self.meet),
                                 "--extra-folder", str(self.intake)])
        self.assertEqual(0, code)
        self.assertEqual(self.zip.read_bytes(), (out / self.zip.name).read_bytes())

    def test_a_refusal_on_the_command_line_is_one_plain_line_and_exit_1(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = package.main(["mac", "--dirty", "--out", str(Path(self.tmp) / "bad"), "--extra-folder",
                                 str(Path(self.tmp) / "nothing here")])
        self.assertEqual(1, code)
        self.assertEqual(1, len(err.getvalue().splitlines()))
        self.assertFalse((Path(self.tmp) / "bad").exists())

    def test_the_built_zip_is_read_by_the_updater_with_the_extra_files_in_the_release(self):
        rels = [r for r in self.manifest["files"] if r != package.MANIFEST]
        updates.check_coverage("mac", rels)


class Refusals(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="clark extra ")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.meet = make_folder(self.tmp, "meet clark", MEET)

    def test_a_missing_path(self):
        self.assertIn("does not exist", refusal(self, Path(self.tmp) / "intake"))

    def test_a_file_is_not_a_folder(self):
        f = Path(self.tmp) / "intake"
        f.write_bytes(b"x")
        self.assertIn("not a folder", refusal(self, f))

    def test_a_link_to_a_folder_is_not_a_folder(self):
        os.symlink(self.meet, Path(self.tmp) / "intake")
        self.assertIn("not a folder", refusal(self, Path(self.tmp) / "intake"))

    def test_a_link_to_a_file_anywhere_inside_is_refused(self):
        os.symlink(self.meet / "README.txt", self.meet / "templates" / "alias")
        self.assertIn("holds a link", refusal(self, self.meet))

    def test_a_link_to_a_folder_inside_is_refused(self):
        os.symlink(self.tmp, self.meet / "loop")
        self.assertIn("holds a link", refusal(self, self.meet))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "needs mkfifo")
    def test_a_pipe_is_not_a_regular_file(self):
        os.mkfifo(self.meet / "pipe")
        self.assertIn("not a regular file", refusal(self, self.meet))

    def test_more_than_5_mb_in_one_folder(self):
        (self.meet / "big.bin").write_bytes(b"x" * package.EXTRA_MAX_BYTES)
        self.assertIn("more than 5 MB", refusal(self, self.meet))

    def test_the_cap_is_for_all_the_folders_together(self):
        intake = make_folder(self.tmp, "intake", {"a.bin": b"x" * (3 * 1024 * 1024)})
        (self.meet / "b.bin").write_bytes(b"x" * (3 * 1024 * 1024))
        self.assertIn("more than 5 MB", refusal(self, self.meet, intake))

    def test_exactly_5_mb_is_allowed(self):
        folder = make_folder(self.tmp, "intake", {"a.bin": b"x" * package.EXTRA_MAX_BYTES})
        self.assertEqual(release_files.EXTRA_TOP[1], os.path.basename(folder))
        self.assertEqual(1, len(package.extra_content([folder])))

    def test_the_same_folder_twice(self):
        self.assertIn("given twice", refusal(self, self.meet, self.meet))
        self.assertIn("given twice", refusal(self, self.meet, str(self.meet) + "/../meet clark"))

    def test_a_name_clark_uses_itself(self):
        for name in ("docker", "system", "data", "System", "README.md", "clark.command", "clark-release.json", "START-HERE.txt", "START-HERE.md", ".app"):
            with self.subTest(name=name):
                folder = make_folder(self.tmp, name, {"a.txt": b"a"})
                self.assertRegex(refusal(self, folder), "uses itself|can't be used")

    def test_a_dot_name_or_an_empty_name(self):
        folder = make_folder(self.tmp, ".hidden", {"a.txt": b"a"})
        self.assertIn("can't be used", refusal(self, folder))
        self.assertIn("can't be used", refusal(self, Path(self.tmp) / "x" / ".."))
        self.assertIn("can't be used", refusal(self, "/"))

    def test_a_name_that_is_not_on_the_list(self):
        folder = make_folder(self.tmp, "stuff", {"a.txt": b"a"})
        self.assertIn("not one a download may carry", refusal(self, folder))

    def test_an_empty_folder(self):
        (Path(self.tmp) / "intake").mkdir()
        self.assertIn("holds no files", refusal(self, Path(self.tmp) / "intake"))

    def test_a_file_name_the_updater_would_refuse(self):
        folder = make_folder(self.tmp, "intake", {"bad:name.txt": b"a"})
        self.assertIn("can't go in a download", refusal(self, folder))

    def test_a_file_name_that_clashes_on_a_mac_disk(self):
        folder = make_folder(self.tmp, "intake", {"Form.txt": b"a", "sub/x.txt": b"b"})
        try:
            (folder / "form.txt").write_bytes(b"c")
            if len(os.listdir(folder)) != 3:
                self.skipTest("this disk folds capitals")
        except OSError:
            self.skipTest("this disk folds capitals")
        self.assertIn("clash", refusal(self, folder))

    def test_a_scratch_file_is_left_out_like_the_rest_of_the_build(self):
        (self.meet / ".DS_Store").write_bytes(b"x")
        self.assertNotIn("meet clark/.DS_Store", package.extra_content([self.meet]))

    def test_a_hidden_file_or_folder_is_refused_and_named(self):
        """A stray .env or .git folder in an extra folder must not be shipped: any name that starts with a dot is refused
        (only .DS_Store is still left out silently); refusal() also checks that nothing was written."""
        for hidden in (".env", ".git/config", ".hidden/notes.txt", "sub/.secret"):
            with self.subTest(hidden=hidden):
                tmp = tempfile.mkdtemp(prefix="clark extra ")
                self.addCleanup(shutil.rmtree, tmp, True)
                folder = make_folder(tmp, "meet clark", MEET)
                target = folder / hidden
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"x")
                case = type("C", (), {"tmp": tmp, "assertRaises": self.assertRaises, "assertFalse": self.assertFalse,
                                      "assertNotIn": self.assertNotIn})()
                message = refusal(case, folder)
                self.assertIn("hidden file or folder", message)
                self.assertIn(hidden.split("/")[0] if hidden.split("/")[0].startswith(".") else hidden, message)
                self.assertIn("Nothing was written", message)

    def test_a_hidden_file_in_a_second_folder_is_refused_too(self):
        intake = make_folder(self.tmp, "intake", {"sample.xlsx": b"x"})
        (intake / ".env").write_bytes(b"x")
        message = refusal(self, self.meet, intake)
        self.assertIn("'intake'", message)
        self.assertIn(".env", message)


class Reader(unittest.TestCase):
    def setUp(self):
        _signing.trust_test_key(self)
        self.tmp = tempfile.mkdtemp(prefix="clark extra read ")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def read(self, path, version="0.3.0"):
        return updates.read_release(path, "mac", version, 2, public_key=_signing.TEST_PUBLIC)

    def test_covers_accepts_only_declared_folders(self):
        self.assertTrue(release_files.covers("mac", "meet clark/a.md"))
        self.assertTrue(release_files.covers("mac", "intake/deep/er/a.md"))
        for rel in ("stray/a.md", "Meet Clark/a.md", "meet clark", "meet clark/", "intake2/a.md", "data/x", "system/branding/a.css",
                    "flat.txt", ".app2/x"):
            with self.subTest(rel=rel):
                self.assertFalse(release_files.covers("mac", rel))

    def test_protected_still_wins(self):
        self.assertFalse(release_files.covers("mac", "system/branding/logo.png"))
        self.assertFalse(release_files.covers("mac", "data/clark.db"))

    def test_a_zip_with_declared_folders_is_read_and_their_files_are_in_the_release(self):
        zip_path = make_zip(self.tmp, version="0.3.1", top_files={"meet clark/a.md": b"a", "intake/b/c.md": b"c"})
        release = self.read(zip_path)
        self.assertIn("meet clark/a.md", release.files)
        self.assertIn("intake/b/c.md", release.files)
        self.assertEqual("644", release.files["intake/b/c.md"]["mode"])

    def test_the_extra_folders_are_optional(self):
        self.assertEqual("0.3.1", self.read(make_zip(self.tmp, version="0.3.1")).version)

    def test_an_undeclared_top_folder_is_still_refused_as_unsafe(self):
        for name in ("stray/a.md", "Intake/a.md", "meet clark2/a.md"):
            with self.subTest(name=name):
                zip_path = make_zip(self.tmp, version="0.3.1", top_files={name: b"a"})
                with self.assertRaises(updates.UpdateError) as said:
                    self.read(zip_path)
                self.assertEqual("unsafe", said.exception.key)

    def test_a_declared_folder_cannot_smuggle_a_protected_name(self):
        zip_path = make_zip(self.tmp, version="0.3.1", top_files={"intake/a.md": b"a"}, extra={"clark/data/x.db": b"x"})
        with self.assertRaises(updates.UpdateError) as said:
            self.read(zip_path)
        self.assertEqual("unsafe", said.exception.key)

    def test_a_link_style_name_in_a_declared_folder_is_refused(self):
        zip_path = make_zip(self.tmp, version="0.3.1", top_files={"intake/../x": b"a"})
        with self.assertRaises(updates.UpdateError) as said:
            self.read(zip_path)
        self.assertEqual("unsafe", said.exception.key)

    def test_a_manifest_that_misses_an_extra_member_is_refused(self):
        zip_path = make_zip(self.tmp, version="0.3.1", extra={"clark/intake/a.md": b"a"})
        with self.assertRaises(updates.UpdateError) as said:
            self.read(zip_path)
        self.assertEqual("incomplete", said.exception.key)

    def test_the_old_reader_refuses_a_download_with_an_extra_folder(self):
        from test_update_old_reader import load_old_reader
        old = load_old_reader()
        zip_path = make_zip(self.tmp, version="1.0.1", top_files={"intake/a.md": b"a"})
        with self.assertRaises(old.UpdateError):
            old.read_release(zip_path, "mac", "1.0.0", 2, public_key=_signing.TEST_PUBLIC)

    def test_an_installed_extra_folder_is_listed_by_walk_app_and_planned(self):
        old = make_zip(self.tmp, version="0.3.0", top_files={"intake/a.md": b"old", "intake/gone.md": b"gone"})
        app = install_release(old, Path(self.tmp) / "clark")
        (app / "intake" / "mine.md").write_bytes(b"mine")
        new = make_zip(self.tmp, version="0.3.1", top_files={"intake/a.md": b"new", "intake/b.md": b"b", "meet clark/m.md": b"m"})
        release = self.read(new)
        files, links = updates.walk_app(app)
        self.assertIn("intake/a.md", files)
        self.assertEqual([], links)
        updates.check_app_folder(app)
        plan = updates.plan(release, app)
        self.assertEqual({"intake/b.md", "meet clark/m.md"}, {r for r in plan.added if "/" in r and not r.startswith(".app")})
        self.assertIn("intake/a.md", plan.replaced)
        self.assertEqual(["intake/gone.md"], plan.removed)
        self.assertIn("intake/mine.md", plan.left)

    def test_a_link_inside_an_extra_folder_stops_an_update_like_any_other(self):
        old = make_zip(self.tmp, version="0.3.0", top_files={"intake/a.md": b"old"})
        app = install_release(old, Path(self.tmp) / "clark")
        os.symlink(app / "README.md", app / "intake" / "alias")
        with self.assertRaises(updates.UpdateError) as said:
            updates.check_app_folder(app)
        self.assertEqual("link", said.exception.key)


class Install(Base):
    """An update over a clark folder that holds extra folders: swapped as whole top entries, never touching system or data."""

    OLD = {"meet clark/a.md": b"old a", "meet clark/gone.md": b"gone", "intake/f.txt": b"old form"}
    NEW = {"meet clark/a.md": b"new a", "meet clark/new.md": b"new", "intake/f.txt": b"new form", "intake/sub/g.txt": b"g"}
    PERSON = {"system/branding/logo.png": b"logo", "data/clark.db": b"data"}

    def setUp(self):
        super().setUp()
        shutil.rmtree(self.app)
        old_zip = make_zip(self.root, version="0.3.0", top_files=self.OLD)
        self.app = install_release(old_zip, self.root / "clark-0.3.0")
        os.unlink(old_zip)
        (self.app / "my notes.txt").write_text("mine\n", encoding="utf-8")
        (self.app / "intake" / "mine.txt").write_bytes(b"my own file in an extra folder")
        for rel, data in self.PERSON.items():
            (self.app / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.app / rel).write_bytes(data)
        os.unlink(self.download)
        self.download = make_zip(self.downloads, version="0.3.1", files=self.new_files, notes="Fixes a typo.\n", top_files=self.NEW)

    def persons(self):
        return {r: (self.app / r).read_bytes() for r in self.PERSON}

    def test_the_marker_swaps_each_extra_folder_as_one_entry_and_never_system_or_data(self):
        release = self.taken()
        backup_dir = ui.back_up(self.app, self.data, self.db, STAMP, "0.3.0", "0.3.1", updates.plan(release, self.app))
        staging = ui.stage(release, self.app, STAMP)
        marker = h.begin(self.data, self.app, staging, STAMP, "0.3.0", "0.3.1", backup_dir=str(backup_dir), **self.begin_kwargs())
        names = [e["name"] for e in json.loads(marker.read_text(encoding="utf-8"))["entries"]]
        self.assertIn("intake", names)
        self.assertIn("meet clark", names)
        self.assertEqual([], [n for n in names if n in ("system", "data")])
        self.assertEqual(h.MANIFEST, names[-1])
        self.assertEqual(".app", names[0])

    def test_an_update_replaces_adds_and_removes_in_the_extra_folders(self):
        keep = self.persons()
        _, code, _ = install(self)
        self.assertEqual(h.OK, code)
        self.assertEqual(b"new a", (self.app / "meet clark/a.md").read_bytes())
        self.assertEqual(b"new", (self.app / "meet clark/new.md").read_bytes())
        self.assertFalse((self.app / "meet clark/gone.md").exists())
        self.assertEqual(b"new form", (self.app / "intake/f.txt").read_bytes())
        self.assertEqual(b"g", (self.app / "intake/sub/g.txt").read_bytes())
        self.assertEqual(0o644, stat.S_IMODE((self.app / "intake/f.txt").stat().st_mode))
        self.assertEqual(b"my own file in an extra folder", (self.app / "intake/mine.txt").read_bytes(), "a person's file there is carried")
        self.assertEqual(keep, self.persons())
        self.assertIn("intake/f.txt", updates.installed_record(self.app)["files"])

    def test_a_download_without_an_extra_folder_removes_the_old_one_it_shipped(self):
        os.unlink(self.download)
        self.download = make_zip(self.downloads, version="0.3.1", files=self.new_files, notes="Fixes a typo.\n")
        _, code, _ = install(self)
        self.assertEqual(h.OK, code)
        self.assertFalse((self.app / "meet clark/a.md").exists())
        self.assertFalse((self.app / "intake/f.txt").exists())
        self.assertEqual(self.PERSON["data/clark.db"], (self.app / "data/clark.db").read_bytes())

    def test_a_fault_at_every_helper_step_puts_the_extra_folders_back(self):
        points = None
        case = type(self)(methodName="run")
        case.setUp()
        try:
            from test_update_install import install_trace
            points = [p for p in install_trace(case) if p not in ("commit", "commit+")]
        finally:
            case.doCleanups()
        self.assertTrue([p for p in points if "intake" in p or "meet clark" in p], "the extra folders are swapped in the trace")
        for point in points:
            with self.subTest(point=point):
                case = type(self)(methodName="run")
                case.setUp()
                try:
                    before = snapshot(case.app)
                    _, code, _ = install(case, fault=Once(point))
                    self.assertEqual(h.ROLLED_BACK, code, point)
                    self.assertEqual(before, snapshot(case.app), point)
                finally:
                    case.doCleanups()

    def test_a_failed_health_check_restores_the_old_extra_folders(self):
        from test_update_helper import FakeSeams
        seams = FakeSeams()
        seams.check_install = lambda app: (_ for _ in ()).throw(h.StepError("damaged", "a module does not import"))
        before = snapshot(self.app)
        _, code, _ = install(self, seams=seams)
        self.assertEqual(h.ROLLED_BACK, code)
        self.assertEqual(before, snapshot(self.app))
        self.assertEqual(b"old a", (self.app / "meet clark/a.md").read_bytes())

    def test_staging_refuses_a_name_in_a_protected_folder_even_inside_an_extra_name(self):
        release = self.taken()
        release.files["system/x"] = release.files["README.md"]
        with self.assertRaises(ui.InstallError):
            ui.stage(release, self.app, STAMP)


if __name__ == "__main__":
    unittest.main()


class StartHereExtra(unittest.TestCase):
    """issue 716: START-HERE says what each extra folder holds, only when that folder is in the zip."""

    def test_the_sentences_appear_only_for_the_folders_given(self):
        none = package.start_here("mac")
        self.assertNotIn("intake holds", none)
        self.assertNotIn("meet clark holds", none)
        both = " ".join(package.start_here("mac", extra=("meet clark", "intake")).split())
        self.assertIn("intake holds a sample workbook with made-up data, in the same layout clark exports. "
                      "meet clark holds an overview and a getting-started guide as PDFs. system/branding holds", both)
        one = " ".join(package.start_here("mac", extra=("intake",)).split())
        self.assertIn("intake holds a sample workbook", one)
        self.assertNotIn("meet clark holds", one)
        self.assertIn("What is in this folder: README.md says what clark is.", both)

    def test_no_line_starts_with_the_product_name_and_the_rest_is_unchanged(self):
        text = package.start_here("mac", extra=("meet clark", "intake"))
        for line in text.splitlines():
            self.assertFalse(line.lstrip().lower().startswith(("clark ", "clark.", "clark's")), line)
        plain = package.start_here("mac")
        self.assertEqual(text.split("What is in this folder:")[0], plain.split("What is in this folder:")[0])
        self.assertEqual(text.split("\n\n", 3)[-1].split("If your Mac will not open")[1], plain.split("If your Mac will not open")[1])

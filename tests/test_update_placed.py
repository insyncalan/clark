"""Updating a clark folder whose program files sit in the hidden .app folder (issue 694): update_helper, update_install, updater.

The person's own top-level folders, system (their branding) and data, must come through every update byte for byte, and no
record, marker or download can make the helper move them. The flat layout (a source checkout, an install from before issue 694)
keeps working: test_update_helper.py still runs it. Run: python3 dev/run_tests.py test_update_placed
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from _paths import ROOT
import clark
from clark import release_files, update_helper as h, update_install as ui, updater, updates
from test_update_helper import FakeSeams, Fixture, Once, STAMP, run_with, snapshot
import test_update_helper as th
from test_update_install import Base, install, install_trace, STAMP as INSTALL_STAMP

PLACED_OLD = {
    "README.md": b"old readme\n",
    "clark.command": b"#!/bin/sh\necho old\n",
    "docker/compose.yaml": b"old compose\n",
    ".app/clark/__init__.py": b"# stand-in\n",
    ".app/src/clark/__init__.py": b'__version__ = "0.3.0"\n',
    ".app/src/clark/mod.py": b"VALUE = 1\n",
    ".app/vendor/lib/a.py": b"A = 1\n",
}
PLACED_NEW = {
    "README.md": b"new readme\n",
    "clark.command": b"#!/bin/sh\necho new\n",
    "docker/compose.yaml": b"new compose\n",
    ".app/clark/__init__.py": b"# stand-in\n",
    ".app/src/clark/__init__.py": b'__version__ = "0.3.1"\n',
    ".app/src/clark/mod.py": b"VALUE = 2\n",
    ".app/src/clark/newmod.py": b"NEW = 1\n",
    ".app/vendor/lib/a.py": b"A = 1\n",
}
PLACED_MINE = {"notes.txt": b"my notes\n", ".app/src/clark/mine.py": b"MINE = 1\n"}
PERSONS = {"system/branding/logo.png": b"old place logo", "branding/logo.png": b"my own logo", "branding/tokens.css": b"my tokens", "data/clark.db": b"docker data"}


def placed_fixture(root):
    """The helper's fixture in the new layout, with the person's system and data folders beside the program files."""
    with mock.patch.object(th, "OLD", PLACED_OLD), mock.patch.object(th, "NEW", PLACED_NEW), \
            mock.patch.object(th, "MINE", PLACED_MINE):
        fx = Fixture(root)
    for rel, data in PERSONS.items():
        th.put(fx.app, rel, data)
    os.symlink(fx.app / "README.md", fx.app / "branding" / "alias")      # a link there must not stop anything
    fx.before = snapshot(fx.app)
    return fx


def persons(app):
    """Everything under system, branding and data, with link targets, so a link that changed shows."""
    out = {}
    for top in ("system", "data", "branding"):
        for folder, dirs, names in os.walk(Path(app) / top):
            for n in names + dirs:
                p = Path(folder, n)
                out[p.relative_to(app).as_posix()] = os.readlink(p) if p.is_symlink() else (None if p.is_dir() else p.read_bytes())
    return out


class Constants(unittest.TestCase):
    def test_the_helper_mirrors_the_lists_it_cannot_import(self):
        self.assertEqual(release_files.HIDDEN, h.HIDDEN)
        self.assertEqual(release_files.PROTECTED, h.PROTECTED)

    def test_the_hidden_folder_is_swapped_first(self):
        self.assertEqual(".app", h.FIRST[0])
        self.assertEqual([".app", "README.md", "docker", "clark.command", h.MANIFEST],
                         h.order_entries({"README.md", "docker", ".app", "clark.command", h.MANIFEST}))

    def test_the_flat_order_is_as_before(self):
        self.assertEqual(["src", "vendor", "README.md", "oldlib", "clark", "clark.command", h.MANIFEST],
                         h.order_entries({"clark", "oldlib", "vendor", "src", "README.md", "clark.command", h.MANIFEST}))

    def test_a_persons_folder_is_never_an_entry(self):
        for name in ("system", "data", "System", "DATA"):
            self.assertEqual([".app"], h.order_entries({".app", name}), name)


class CodeRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark root "))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_the_hidden_folder_when_it_is_there(self):
        (self.tmp / ".app" / "src").mkdir(parents=True)
        self.assertEqual(self.tmp / ".app", h.code_root(self.tmp))
        self.assertEqual(self.tmp / ".app", h.code_root(str(self.tmp)))

    def test_the_folder_itself_in_the_flat_layout(self):
        (self.tmp / "src").mkdir()
        self.assertEqual(self.tmp, h.code_root(self.tmp))

    def test_a_file_or_a_link_named_app_is_not_a_code_root(self):
        (self.tmp / ".app").write_text("x", encoding="utf-8")
        self.assertEqual(self.tmp, h.code_root(self.tmp))
        (self.tmp / ".app").unlink()
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        os.symlink(elsewhere, self.tmp / ".app")
        self.assertEqual(self.tmp, h.code_root(self.tmp))

    def test_the_server_is_started_from_the_code_root(self):
        calls = []
        fake = SimpleNamespace(WINDOWS="win32", MAC="darwin",
                               start_detached=lambda argv, env, log, cwd=None, on=None: calls.append(env["PYTHONPATH"]) or SimpleNamespace(pid=1))
        for layout, hidden in (("placed", True), ("flat", False)):
            app = self.tmp / layout
            (app / (".app" if hidden else "") / "src").mkdir(parents=True)
            h.Seams(platform=fake).start_server(app, self.tmp, 8765, self.tmp / "log")
        self.assertEqual([str(self.tmp / "placed" / ".app" / "src"), str(self.tmp / "flat" / "src")], calls)

    def test_the_health_check_imports_from_the_code_root(self):
        app = self.tmp / "app"
        th.put(app, ".app/src/clark/__init__.py", b"")
        th.put(app, ".app/src/clark/good.py", b"X = 1\n")
        (app / ".app" / "vendor").mkdir()
        h.Seams().check_install(app)
        th.put(app, ".app/src/clark/bad.py", b"import not_a_real_module_here\n")
        with self.assertRaises(h.StepError) as cm:
            h.Seams().check_install(app)
        self.assertEqual("damaged", cm.exception.key)

    def test_the_health_check_finds_nothing_in_a_placed_folder_that_lost_its_code(self):
        app = self.tmp / "app"
        (app / ".app").mkdir(parents=True)
        with self.assertRaises(h.StepError):
            h.Seams().check_install(app)

    def test_first_check_looks_in_the_staged_hidden_folder(self):
        staged = self.tmp / "staged"
        th.put(staged, ".app/src/clark/__init__.py", b"")
        th.put(staged, ".app/src/clark/bad.py", b"raise ImportError('broken')\n")
        (staged / ".app" / "vendor").mkdir()
        with self.assertRaises(ui.InstallError) as said:
            ui.first_check(staged)
        self.assertIn("broken", said.exception.detail)

    def test_first_check_still_reads_a_flat_staging_folder(self):
        staged = self.tmp / "flat"
        th.put(staged, "src/clark/__init__.py", b"")
        th.put(staged, "src/clark/good.py", b"X = 1\n")
        (staged / "vendor").mkdir()
        ui.first_check(staged)


class AppFolder(unittest.TestCase):
    def test_the_clark_folder_is_the_parent_of_the_hidden_folder(self):
        for given, wanted in (("/x/clark/.app/src/clark/__init__.py", "/x/clark"), ("/x/clark/src/clark/__init__.py", "/x/clark")):
            with self.subTest(given=given), mock.patch.object(clark, "__file__", given), \
                    mock.patch.object(Path, "resolve", lambda self, *a, **k: self):
                self.assertEqual(Path(wanted), updater.app_folder())

    def test_this_repository_is_its_own_app_folder(self):
        self.assertEqual(ROOT.resolve(), updater.app_folder())


class HelperHappyPath(unittest.TestCase):
    def test_the_hidden_folder_is_swapped_as_one_entry_and_the_persons_folders_stay(self):
        with tempfile.TemporaryDirectory() as t:
            fx = placed_fixture(t)
            persons_before = persons(fx.app)
            seams = FakeSeams()
            fx.begin()
            m = json.loads(h.marker_path(fx.data).read_text(encoding="utf-8"))
            self.assertEqual([".app", "README.md", "docker", "clark.command", h.MANIFEST], [e["name"] for e in m["entries"]])
            self.assertNotIn("system", json.dumps(m["entries"]))
            self.assertEqual([], [r for r in m["before"] if r.startswith(("system", "data"))])
            code, _ = h.run_update(h.marker_path(fx.data), seams)
            self.assertEqual(h.OK, code)
            self.assertEqual(PLACED_NEW[".app/src/clark/mod.py"], (fx.app / ".app/src/clark/mod.py").read_bytes())
            self.assertEqual(b"MINE = 1\n", (fx.app / ".app/src/clark/mine.py").read_bytes(), "the person's file inside .app is carried")
            self.assertEqual(b"my notes\n", (fx.app / "notes.txt").read_bytes())
            self.assertEqual(persons_before, persons(fx.app))
            self.assertEqual(seams.started, [(str(fx.app), 8765)])

    def test_the_only_swaps_are_the_listed_entries(self):
        with tempfile.TemporaryDirectory() as t:
            fx = placed_fixture(t)
            trace = []
            run_with(fx, trace=trace)
            swaps = [p.split(":")[2] for p in trace if p.startswith("swap:new:") and not p.endswith("+")]
            self.assertEqual([".app", "README.md", "docker", "clark.command", h.MANIFEST], swaps)

    def test_a_fault_at_every_step_puts_everything_back_and_never_touches_system_or_data(self):
        with tempfile.TemporaryDirectory() as t:
            trace = []
            run_with(placed_fixture(t), trace=trace)
        for point in [p for p in trace if p not in ("commit", "commit+")]:
            with self.subTest(point=point), tempfile.TemporaryDirectory() as t:
                fx = placed_fixture(t)
                keep = persons(fx.app)
                code, _ = run_with(fx, fault=Once(point))
                self.assertEqual(h.ROLLED_BACK, code, point)
                self.assertEqual(fx.before, snapshot(fx.app), point)
                self.assertEqual(keep, persons(fx.app), point)

    def test_a_failed_health_check_after_the_swap_puts_the_old_hidden_folder_back(self):
        with tempfile.TemporaryDirectory() as t:
            fx = placed_fixture(t)
            seams = FakeSeams()
            seams.check_install = lambda app: (_ for _ in ()).throw(h.StepError("damaged", "a module does not import"))
            code, _ = run_with(fx, seams=seams)
            self.assertEqual(h.ROLLED_BACK, code)
            self.assertEqual(fx.before, snapshot(fx.app))
            self.assertEqual(PLACED_OLD[".app/src/clark/mod.py"], (fx.app / ".app/src/clark/mod.py").read_bytes())


class HelperRefusals(unittest.TestCase):
    def names_in(self, which, rel):
        """A fixture whose old or new record also names `rel`."""
        fx = placed_fixture(tempfile.mkdtemp(prefix="clark placed "))
        self.addCleanup(shutil.rmtree, fx.root, True)
        path = (fx.app if which == "old" else fx.staging) / h.MANIFEST
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["files"][rel] = dict(doc["files"]["README.md"])
        path.write_text(json.dumps(doc), encoding="utf-8")
        fx.before = snapshot(fx.app)
        return fx

    def test_begin_refuses_a_record_that_names_a_persons_folder(self):
        for which in ("old", "new"):
            for rel in ("branding/logo.png", "system/branding/logo.png", "Branding/x", "data/clark.db", "System/branding/x"):
                for check in (True, False):
                    with self.subTest(which=which, rel=rel, check=check):
                        fx = self.names_in(which, rel)
                        with self.assertRaises(updates.UpdateError) as said:
                            fx.begin(check=check)
                        self.assertEqual("unsafe", said.exception.key)
                        self.assertFalse(h.marker_path(fx.data).exists(), "nothing was written")
                        self.assertEqual(fx.before, snapshot(fx.app))

    def test_a_marker_that_names_system_is_never_acted_on(self):
        for had_old, in_new in ((True, False), (False, False), (True, True)):
            with self.subTest(had_old=had_old, in_new=in_new), tempfile.TemporaryDirectory() as t:
                fx = placed_fixture(t)
                fx.begin()
                marker = h.marker_path(fx.data)
                doc = json.loads(marker.read_text(encoding="utf-8"))
                doc["entries"].insert(0, {"name": "system", "had_old": had_old, "in_new": in_new})
                doc["entries"].append({"name": "Data", "had_old": had_old, "in_new": in_new})
                marker.write_text(json.dumps(doc), encoding="utf-8")
                keep = persons(fx.app)
                code, _ = h.run_update(marker, FakeSeams())
                self.assertEqual(h.OK, code)
                self.assertEqual(keep, persons(fx.app))

    def test_a_marker_that_names_system_is_never_moved_back_either(self):
        with tempfile.TemporaryDirectory() as t:
            fx = placed_fixture(t)
            fx.begin()
            marker = h.marker_path(fx.data)
            doc = json.loads(marker.read_text(encoding="utf-8"))
            doc["entries"].insert(0, {"name": "system", "had_old": False, "in_new": False})     # the rollback would move it to staging
            marker.write_text(json.dumps(doc), encoding="utf-8")
            keep = persons(fx.app)
            code, _ = h.run_update(marker, FakeSeams(), Once("health"))
            self.assertEqual(h.ROLLED_BACK, code)
            self.assertEqual(keep, persons(fx.app))

    def test_stage_refuses_a_name_in_a_persons_folder(self):
        class Case(Base):
            def runTest(self):
                pass
        case = Case()
        case.setUp()
        self.addCleanup(case.doCleanups)
        release = case.taken()
        release.files["branding/logo.png"] = dict(release.files["README.md"])
        with self.assertRaises(ui.InstallError) as said:
            ui.stage(release, case.app, INSTALL_STAMP)
        self.assertIn("unsafe name", said.exception.detail)
        self.assertFalse((case.app / ("%s%s" % (h.STAGING_PREFIX, INSTALL_STAMP))).exists())


class WholeInstall(Base):
    """The server's side and the helper together, over a clark folder that holds the person's system and data."""

    def setUp(self):
        super().setUp()
        for rel, data in PERSONS.items():
            th.put(self.app, rel, data)
        os.symlink(self.app / "README.md", self.app / "branding" / "alias")

    def test_an_update_in_place_leaves_system_branding_byte_identical(self):
        keep = persons(self.app)
        self.assertIn("branding/logo.png", keep)
        _, code, _ = install(self)
        self.assertEqual(h.OK, code)
        self.assertEqual(keep, persons(self.app))
        self.assertTrue((self.app / "branding" / "alias").is_symlink())
        self.assertIn('"0.3.1"', (self.app / ".app/src/clark/__init__.py").read_text(encoding="utf-8"))

    def test_the_new_install_passes_the_real_health_check(self):
        install(self)
        h.Seams().check_install(self.app)

    def test_the_backup_set_holds_neither_system_nor_data(self):
        backup_dir, _, _ = install(self)
        kept = [p.relative_to(backup_dir / "app").as_posix() for p in (backup_dir / "app").rglob("*") if p.is_file()]
        self.assertTrue(kept)
        self.assertEqual([], [k for k in kept if k.startswith(("system", "data"))])

    def test_space_is_counted_without_them(self):
        small = ui.space_needed(self.app, self.db)
        th.put(self.app, "branding/huge.bin", b"x" * 5_000_000)
        self.assertEqual(small, ui.space_needed(self.app, self.db))

    def test_a_link_in_system_does_not_stop_the_check_the_server_makes_first(self):
        updates.check_app_folder(self.app)

    def test_a_fault_at_every_helper_step_leaves_system_and_data_alone(self):
        for point in [p for p in install_trace(self) if p not in ("commit", "commit+")]:
            with self.subTest(point=point):
                case = type(self)(methodName="run")
                case.setUp()
                try:
                    keep = persons(case.app)
                    _, code, _ = install(case, fault=Once(point))
                    self.assertEqual(h.ROLLED_BACK, code, point)
                    self.assertEqual(keep, persons(case.app), point)
                finally:
                    case.doCleanups()


if __name__ == "__main__":
    unittest.main()

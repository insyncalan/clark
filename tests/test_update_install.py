"""The server's side of an update: src/clark/update_install.py.

Takes the file in once, backs up, stages, checks, hands over to the helper (with its platform seams faked), and undoes. Builds
fake downloads, app folders and data folders in temporary places; no network, no Chrome, no real server.
Run: python3 dev/run_tests.py test_update_install
"""
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from _paths import ROOT
from _demo import USER
from clark import settings, store, update_helper as h, update_install as ui, updates
from clark.store import open_store
from test_update_helper import FakeSeams, Once, snapshot
from test_updates import listed_files, make_zip

SYSTEM = "mac"
STAMP = "20261101T120000Z"
UNDO_STAMP = "20261101T130000Z"


def install_release(zip_path, folder):
    """An app folder exactly as a download unzips: every member of `zip_path`'s top folder, with its mode."""
    folder = Path(folder)
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            rel = info.filename.split("/", 1)[1]
            dest = folder / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(z.read(info))
            os.chmod(dest, (info.external_attr >> 16) & 0o777)
    return folder


class Base(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="clark install "))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.downloads = self.root / "Downloads"
        self.downloads.mkdir()
        old_zip = make_zip(self.root, version="0.3.0")
        self.app = install_release(old_zip, self.root / "clark-0.3.0")
        os.unlink(old_zip)
        (self.app / "my notes.txt").write_text("mine\n", encoding="utf-8")
        self.data = self.root / "data"
        self.data.mkdir()
        self.db = self.data / "clark.db"
        s = open_store(self.db, onedrive_roots=[])
        with s.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme", "health": "On track"})
        s.close()
        (self.data / settings.FILE).write_text(json.dumps({"backups_kept": 9}), encoding="utf-8")
        (self.data / "reports").mkdir()
        (self.data / "reports" / "r.docx").write_bytes(b"a published report")
        self.project = self.root / "Projects" / "Example"
        self.project.mkdir(parents=True)
        (self.project / "plan.txt").write_text("a project file\n", encoding="utf-8")
        self.new_files = listed_files("0.3.1")
        self.new_files["src/clark/added.py"] = b"ADDED = 1\n"
        self.download = make_zip(self.downloads, version="0.3.1", files=self.new_files, notes="Fixes a typo.\n")

    def planted(self):
        return {"data": snapshot(self.data / "reports"), "project": snapshot(self.project),
                "mine": (self.app / "my notes.txt").read_bytes(), "settings": (self.data / settings.FILE).read_bytes()}

    def taken(self, source=None):
        path, digest = ui.take_in(source or self.download, self.data, SYSTEM)
        return ui.read_taken(path, digest, SYSTEM, "0.3.0", 2)

    def begin_kwargs(self):
        return dict(installed_schema=2, server_pid=4321, port=8765, mark_header="X-Clark-Mark", mark="mark-1")


class TakeInTest(Base):
    def test_the_file_is_copied_once_into_the_releases_folder_and_the_checksum_is_the_copys(self):
        path, digest = ui.take_in(self.download, self.data, SYSTEM)
        self.assertEqual(self.data / "releases" / "clark-0.3.1-mac.zip", path)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertEqual(self.download.read_bytes(), path.read_bytes())
        self.assertEqual([], [n for n in os.listdir(path.parent) if n.endswith(".part")])
        if os.name != "nt":
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual(0o700, stat.S_IMODE(path.parent.stat().st_mode))

    def test_a_file_swapped_after_it_was_taken_in_changes_nothing_that_is_checked_or_shown(self):
        path, digest = ui.take_in(self.download, self.data, SYSTEM)
        other = self.root / "other"
        other.mkdir()
        evil = make_zip(other, version="0.3.1", notes="Something else.\n")
        shutil.copyfile(evil, self.download)                              # the original is changed after the copy
        release = ui.read_taken(path, digest, SYSTEM, "0.3.0", 2)
        self.assertEqual(digest, release.zip_sha256)
        self.assertEqual("Fixes a typo.\n", release.notes)

    def test_a_copy_changed_after_it_was_taken_in_is_refused(self):
        path, digest = ui.take_in(self.download, self.data, SYSTEM)
        other = self.root / "other"
        other.mkdir()
        shutil.copyfile(make_zip(other, version="0.3.1", notes="Something else.\n"), path)
        with self.assertRaises(updates.UpdateError) as said:
            ui.read_taken(path, digest, SYSTEM, "0.3.0", 2)
        self.assertEqual("damaged", said.exception.key)

    def test_a_link_is_refused_and_nothing_is_kept(self):
        link = self.downloads / "clark-0.4.0-mac.zip"
        os.symlink(self.download, link)
        with self.assertRaises(updates.UpdateError) as said:
            ui.take_in(link, self.data, SYSTEM)
        self.assertEqual("unreadable", said.exception.key)
        self.assertEqual([], os.listdir(self.data / "releases"))

    def test_a_folder_a_wrong_name_and_a_file_too_big_are_refused(self):
        folder = self.downloads / "clark-0.5.0-mac.zip"
        folder.mkdir()
        for source, key, kw in ((folder, "unreadable", {}), (self.downloads / "clark-0.3.1.zip", "source", {}),
                                (self.download, "damaged", {"max_bytes": 10})):
            with self.subTest(source=source.name, key=key):
                with self.assertRaises(updates.UpdateError) as said:
                    ui.take_in(source, self.data, SYSTEM, **kw)
                self.assertEqual(key, said.exception.key)
        self.assertEqual([], [n for n in os.listdir(self.data / "releases")])

    def test_a_browser_copy_name_is_taken_under_its_proper_name_when_chosen(self):
        copy = self.downloads / "clark-0.3.1-mac (1).zip"
        shutil.copyfile(self.download, copy)
        path, _ = ui.take_in(copy, self.data, SYSTEM, chosen=True)
        self.assertEqual("clark-0.3.1-mac.zip", path.name)


class BackUpTest(Base):
    def back_up(self, **kw):
        release = self.taken()
        return ui.back_up(self.app, self.data, self.db, STAMP, "0.3.0", "0.3.1", updates.plan(release, self.app), **kw)

    def test_the_set_holds_the_whole_app_folder_settings_the_database_and_a_record(self):
        folder = self.back_up()
        self.assertEqual(self.data / "updates" / f"{STAMP}-0.3.0-to-0.3.1", folder)
        files, _ = updates.walk_app(self.app)
        for rel in files:
            self.assertEqual((self.app / rel).read_bytes(), (folder / "app" / rel).read_bytes(), rel)
        self.assertEqual((self.data / settings.FILE).read_bytes(), (folder / settings.FILE).read_bytes())
        copy = store.check_copy(folder / "clark.db")
        record = json.loads((folder / "update.json").read_text(encoding="utf-8"))
        self.assertEqual(("update", "0.3.0", "0.3.1", False, None), (record["kind"], record["from"], record["to"], record["undone"],
                                                                     record["db_after"]))
        self.assertEqual(copy["db_id"], record["db_before"]["db_id"])
        self.assertEqual(sorted(files), sorted(record["app_files"]))
        self.assertEqual(hashlib.sha256((self.app / "README.md").read_bytes()).hexdigest(), record["app_files"]["README.md"])
        self.assertEqual(["src/clark/added.py"], record["planned"]["added"])
        self.assertFalse(str(Path.home()) in json.dumps(record) and str(Path.home()) != "/", "the home folder is written ~")

    def test_only_what_rebuilds_the_app_is_in_the_set(self):
        (self.data / "server.log").write_text("log\n", encoding="utf-8")
        (self.data / "ai-key.json").write_text('{"key": "fictional"}\n', encoding="utf-8")
        folder = self.back_up()
        self.assertEqual(sorted(["app", "clark.db", settings.FILE, "update.json"]), sorted(os.listdir(folder)))

    def test_not_enough_room_makes_nothing(self):
        with self.assertRaises(ui.InstallError) as said:
            self.back_up(free=lambda p: 1)
        self.assertEqual("space", said.exception.key)
        self.assertEqual([], os.listdir(self.data / "updates"))

    def test_a_fault_in_each_part_leaves_no_set_and_nothing_else_changed(self):
        before = self.planted()
        app_before = snapshot(self.app)
        for point in ("back_up:app", "back_up:settings", "back_up:database", "back_up:record"):
            with self.subTest(point=point):
                with self.assertRaises(ui.InstallError) as said:
                    self.back_up(fault=Once(point))
                self.assertEqual("backup", said.exception.key)
                self.assertEqual([], os.listdir(self.data / "updates"))
                self.assertEqual(before, self.planted())
                self.assertEqual(app_before, snapshot(self.app))
        self.assertEqual([], ui.sets(self.data))

    def test_a_half_made_set_is_never_counted(self):
        (self.data / "updates").mkdir()
        (self.data / "updates" / f"{STAMP}-0.3.0-to-0.3.1.part").mkdir()
        self.assertEqual([], ui.sets(self.data))
        with self.assertRaises(ui.InstallError):
            self.back_up()


class StageTest(Base):
    def test_every_file_is_staged_with_its_mode_and_the_record_last(self):
        release = self.taken()
        folder = ui.stage(release, self.app, STAMP)
        self.assertEqual(self.app / f".clark-update-{STAMP}", folder)
        for rel, row in release.files.items():
            self.assertEqual(row["sha256"], hashlib.sha256((folder / rel).read_bytes()).hexdigest(), rel)
            self.assertEqual(int(row["mode"], 8), stat.S_IMODE((folder / rel).stat().st_mode), rel)
        record = json.loads((folder / updates.MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual("0.3.1", record["version"])

    def test_a_fault_while_staging_takes_the_folder_away_and_the_app_is_unchanged(self):
        release = self.taken()
        before = snapshot(self.app)
        first = sorted(release.files)[3]
        with self.assertRaises(ui.InstallError) as said:
            ui.stage(release, self.app, STAMP, fault=Once("stage:" + first))
        self.assertEqual("staging", said.exception.key)
        self.assertFalse((self.app / f".clark-update-{STAMP}").exists())
        self.assertEqual(before, snapshot(self.app))

    def test_a_file_that_does_not_match_its_hash_is_not_staged(self):
        release = self.taken()
        release.files["README.md"] = dict(release.files["README.md"], sha256="0" * 64)
        with self.assertRaises(ui.InstallError):
            ui.stage(release, self.app, STAMP)
        self.assertFalse((self.app / f".clark-update-{STAMP}").exists())

    def test_an_unsafe_name_is_never_written(self):
        release = self.taken()
        release.files["../outside.txt"] = release.files["README.md"]
        with self.assertRaises(ui.InstallError) as said:
            ui.stage(release, self.app, STAMP)
        self.assertIn("unsafe name", said.exception.detail, "refused by its name, before anything is read")
        self.assertFalse((self.app.parent / "outside.txt").exists())


class FirstCheckTest(Base):
    def test_the_staged_copy_imports(self):
        ui.first_check(ui.stage(self.taken(), self.app, STAMP))

    def test_a_module_that_does_not_import_is_caught_before_anything_is_swapped(self):
        files = dict(self.new_files)
        files["src/clark/broken.py"] = b"this is not python\n"
        other = self.root / "broken"
        other.mkdir()
        path, digest = ui.take_in(make_zip(other, version="0.3.1", files=files), self.data, SYSTEM)
        folder = ui.stage(ui.read_taken(path, digest, SYSTEM, "0.3.0", 2), self.app, STAMP)
        with self.assertRaises(ui.InstallError) as said:
            ui.first_check(folder)
        self.assertEqual("first_check", said.exception.key)
        self.assertIn("broken", said.exception.detail)


def install(case, seams=None, fault=None):
    """The whole forward path as the server and helper run it: (the backup set, the helper's exit code and result)."""
    release = case.taken()
    backup_dir = ui.back_up(case.app, case.data, case.db, STAMP, "0.3.0", "0.3.1", updates.plan(release, case.app))
    staging = ui.stage(release, case.app, STAMP)
    ui.first_check(staging)
    marker = h.begin(case.data, case.app, staging, STAMP, "0.3.0", "0.3.1", backup_dir=str(backup_dir), **case.begin_kwargs())
    code, result = h.run_update(marker, seams or FakeSeams(), fault)
    if code == h.OK:
        ui.note_installed(backup_dir, case.db)
    return backup_dir, code, result


class InstallTest(Base):
    def test_install_end_to_end_replaces_the_app_and_keeps_everything_else(self):
        before = self.planted()
        backup_dir, code, result = install(self)
        self.assertEqual((h.OK, "installed"), (code, result["status"]))
        self.assertEqual(self.new_files["src/clark/added.py"], (self.app / "src/clark/added.py").read_bytes())
        self.assertIn('"0.3.1"', (self.app / "src/clark/__init__.py").read_text(encoding="utf-8"))
        self.assertEqual(before, self.planted(), "data, reports, a project folder and the person's own file are untouched")
        self.assertEqual("0.3.1", updates.installed_record(self.app)["version"])
        self.assertIsNotNone(ui.read_set(backup_dir)["db_after"])

    def test_a_fault_at_every_helper_step_leaves_the_old_version_and_the_planted_files(self):
        for point in [p for p in install_trace(self) if p not in ("commit", "commit+")]:
            with self.subTest(point=point):
                case = type(self)(methodName="run")
                case.setUp()
                try:
                    app_before, planted = snapshot(case.app), case.planted()
                    _, code, result = install(case, fault=Once(point))
                    self.assertEqual(h.ROLLED_BACK, code, point)
                    self.assertEqual(app_before, snapshot(case.app))
                    self.assertEqual(planted, case.planted())
                    self.assertFalse(h.marker_path(case.data).exists())
                finally:
                    case.doCleanups()


def install_trace(case):
    """The helper's step points of a working install in a fresh copy of `case`'s fixture."""
    trace = []
    other = type(case)(methodName="run")
    other.setUp()
    try:
        release = other.taken()
        backup_dir = ui.back_up(other.app, other.data, other.db, STAMP, "0.3.0", "0.3.1")
        staging = ui.stage(release, other.app, STAMP)
        marker = h.begin(other.data, other.app, staging, STAMP, "0.3.0", "0.3.1", backup_dir=str(backup_dir), **other.begin_kwargs())
        code, _ = h.run_update(marker, FakeSeams(), None, trace)
        assert code == h.OK
    finally:
        other.doCleanups()
    return trace


class HandOverTest(Base):
    def staged(self):
        release = self.taken()
        backup_dir = ui.back_up(self.app, self.data, self.db, STAMP, "0.3.0", "0.3.1")
        return ui.stage(release, self.app, STAMP), backup_dir

    def test_the_helper_is_started_from_the_data_folder_and_the_server_waits_until_it_is_ready(self):
        staging, backup_dir = self.staged()
        started = []

        def start(argv, env, log_path, cwd=None):
            started.append((argv, cwd))
            marker = h.marker_path(self.data)
            doc = json.loads(marker.read_text(encoding="utf-8"))
            doc["phase"] = "ready"
            h.write_json(marker, doc)

        marker = ui.hand_over(self.data, self.app, staging, STAMP, "0.3.0", "0.3.1", backup_dir=backup_dir, start=start,
                              sleep=lambda s: None, **self.begin_kwargs())
        argv, cwd = started[0]
        self.assertEqual(["-I", "-B"], argv[1:3])
        self.assertTrue(argv[3].startswith(str(self.data / "updates" / "helper-")))
        self.assertEqual(["--marker", str(marker)], argv[4:])
        self.assertEqual(str(Path(argv[3]).parent), cwd)
        self.assertNotIn(str(self.app), " ".join(argv), "nothing it runs is in the app folder")

    def test_a_helper_that_never_says_ready_changes_nothing(self):
        staging, backup_dir = self.staged()
        before = snapshot(self.app)
        clock = iter(range(0, 1000)).__next__
        with self.assertRaises(ui.InstallError) as said:
            ui.hand_over(self.data, self.app, staging, STAMP, "0.3.0", "0.3.1", backup_dir=backup_dir,
                         start=lambda *a, **k: None, sleep=lambda s: None, clock=clock, **self.begin_kwargs())
        self.assertEqual("helper", said.exception.key)
        self.assertFalse(h.marker_path(self.data).exists())
        self.assertFalse(staging.exists())
        self.assertEqual(before, snapshot(self.app))

    def test_a_helper_that_cannot_be_started_changes_nothing(self):
        staging, backup_dir = self.staged()

        def start(*a, **k):
            raise OSError("no such program")

        with self.assertRaises(ui.InstallError) as said:
            ui.hand_over(self.data, self.app, staging, STAMP, "0.3.0", "0.3.1", backup_dir=backup_dir, start=start,
                         sleep=lambda s: None, **self.begin_kwargs())
        self.assertEqual("helper", said.exception.key)
        self.assertFalse(h.marker_path(self.data).exists())
        self.assertFalse(staging.exists())


class UndoTest(Base):
    def test_undo_is_full_while_the_data_is_as_the_update_left_it(self):
        install(self)
        self.assertEqual("full", ui.undo_choice(self.data, self.db))

    def test_undo_offers_the_app_and_settings_only_once_the_data_has_changed(self):
        install(self)
        s = open_store(self.db, onedrive_roots=[])
        with s.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": "after the update", "raised": "2026-11-01", "source": "demo"})
        s.close()
        self.assertEqual("app_only", ui.undo_choice(self.data, self.db))

    def test_undo_puts_back_the_old_version_and_settings_and_keeps_the_planted_files(self):
        old_app = snapshot(self.app)
        backup_dir, _, _ = install(self)
        (self.data / settings.FILE).write_text(json.dumps({"backups_kept": 3}), encoding="utf-8")
        planted = self.planted()
        staging = ui.stage_undo(backup_dir, self.app, UNDO_STAMP)
        undo_set = ui.back_up(self.app, self.data, self.db, UNDO_STAMP, "0.3.1", "0.3.0", kind="undo")
        marker = h.begin(self.data, self.app, staging, UNDO_STAMP, "0.3.1", "0.3.0", backup_dir=str(undo_set), **self.begin_kwargs())
        code, result = h.run_update(marker, FakeSeams())
        self.assertEqual((h.OK, "installed"), (code, result["status"]))
        ui.put_back_settings(backup_dir, self.data)
        ui.mark_undone(backup_dir)
        self.assertEqual(old_app, snapshot(self.app))
        self.assertEqual(9, settings.backups_kept(self.data))
        self.assertEqual({k: v for k, v in planted.items() if k != "settings"},
                         {k: v for k, v in self.planted().items() if k != "settings"})
        with self.assertRaises(ui.InstallError) as said:
            ui.undo_choice(self.data, self.db)
        self.assertEqual("undone", said.exception.key)

    def test_a_changed_file_in_the_kept_copy_is_refused(self):
        backup_dir, _, _ = install(self)
        (backup_dir / "app" / "README.md").write_bytes(b"changed afterwards\n")
        with self.assertRaises(ui.InstallError) as said:
            ui.stage_undo(backup_dir, self.app, UNDO_STAMP)
        self.assertEqual("backup_damaged", said.exception.key)
        self.assertFalse((self.app / f".clark-update-{UNDO_STAMP}").exists())

    def test_a_kept_record_that_disagrees_with_the_kept_files_is_refused(self):
        backup_dir, _, _ = install(self)
        record = ui.read_set(backup_dir)
        record["app_files"]["README.md"] = "0" * 64
        h.write_json(backup_dir / "update.json", record)
        with self.assertRaises(ui.InstallError) as said:
            ui.stage_undo(backup_dir, self.app, UNDO_STAMP)
        self.assertEqual("backup_damaged", said.exception.key)

    def test_a_link_in_the_kept_copy_is_refused(self):
        backup_dir, _, _ = install(self)
        kept = backup_dir / "app" / "README.md"
        real = self.root / "elsewhere.md"
        real.write_bytes(kept.read_bytes())
        kept.unlink()
        os.symlink(real, kept)
        with self.assertRaises(ui.InstallError) as said:
            ui.stage_undo(backup_dir, self.app, UNDO_STAMP)
        self.assertEqual("backup_damaged", said.exception.key)

    def test_no_update_to_undo(self):
        with self.assertRaises(ui.InstallError) as said:
            ui.undo_choice(self.data, self.db)
        self.assertEqual("no_update", said.exception.key)


class PruneTest(Base):
    def test_the_last_three_sets_and_releases_are_kept_and_never_the_installed_one(self):
        (self.data / "updates").mkdir()
        for n in range(5):
            folder = self.data / "updates" / f"2026110{n}T120000Z-0.3.{n}-to-0.3.{n + 1}"
            folder.mkdir()
            h.write_json(folder / "update.json", {"kind": "update"})
        (self.data / "updates" / "not-ours").mkdir()
        releases = self.data / "releases"
        releases.mkdir()
        for v in ("0.1.0", "0.2.0", "0.3.0", "0.3.1", "0.10.0"):
            (releases / f"clark-{v}-mac.zip").write_bytes(b"x")
        (releases / "clark-0.0.1-windows.zip").write_bytes(b"x")
        (releases / "mine.zip").write_bytes(b"x")
        gone = ui.prune(self.data, "0.1.0", SYSTEM)
        self.assertEqual(["20261100T120000Z-0.3.0-to-0.3.1", "20261101T120000Z-0.3.1-to-0.3.2", "clark-0.2.0-mac.zip"], gone)
        self.assertEqual(sorted(["clark-0.1.0-mac.zip", "clark-0.3.0-mac.zip", "clark-0.3.1-mac.zip", "clark-0.10.0-mac.zip",
                                 "clark-0.0.1-windows.zip", "mine.zip"]), sorted(os.listdir(releases)))
        self.assertTrue((self.data / "updates" / "not-ours").is_dir())

    def test_nothing_is_taken_away_while_an_update_is_unfinished(self):
        (self.data / "updates").mkdir()
        h.write_json(h.marker_path(self.data), {})
        for n in range(5):
            folder = self.data / "updates" / f"2026110{n}T120000Z-0.3.{n}-to-0.3.{n + 1}"
            folder.mkdir()
            h.write_json(folder / "update.json", {"kind": "update"})
        self.assertEqual([], ui.prune(self.data, "0.3.0", SYSTEM))


class WordsTest(unittest.TestCase):
    BANNED = re.compile(r"\b(zip|manifest|sha|path|vault|tracker|database|stage|staging|apply|refused|invalid)\b", re.I)

    def test_every_sentence_is_plain(self):
        for key, text in ui.MESSAGES.items():
            with self.subTest(key=key):
                self.assertFalse(text.lower().startswith("clark"), text)
                self.assertIsNone(self.BANNED.search(text), text)
                self.assertTrue(text.endswith("."), text)
                self.assertNotIn("/", text)

    def test_every_key_used_has_a_sentence(self):
        source = (ROOT / "src" / "clark" / "update_install.py").read_text(encoding="utf-8")
        for key in set(re.findall(r'InstallError\("([a-z_]+)"', source)):
            self.assertIn(key, ui.MESSAGES)


if __name__ == "__main__":
    unittest.main()

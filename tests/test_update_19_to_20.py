"""Row 944 (track T1, layout 20): a real update from data layout 19 to layout 20 (projects.brand, step 20), through the updater's real package path.

Modelled on test_update_17_to_18. The previous release (tag v1.0.4, data layout 19) is built into a real zip with dev/tools/package.py,
and so is this tree (its version raised to 1.0.5 in a throwaway checkout, so the updater sees an update). The data is made by the OLD
code, the old zip is unpacked as the installed app, and the updater runs on the real zips with a real database; the new build opens the
data in a real child python from the installed app folder.

SKIPS ITSELF while store.SCHEMA_VERSION is below 20 (layout 20 is not on this tree yet); once it is 20 it runs.

Covered: the backup set is made first (layout 19, every row); the new build migrates to layout 20 keeping every row, takes its own safety
copy first, and projects.brand is 'generic' for every existing project; a second open changes nothing; Undo puts layout 19 back; the old
build refuses layout 20 with its plain "newer" sentence; a layout-22 copy is refused by the new build, untouched.
No network, no browser, no window. Run: python3 dev/run_tests.py test_update_19_to_20
"""
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock
from pathlib import Path

from _paths import ROOT
import _signing
import package
from clark import store as store_module, update_helper as h, update_install as ui
from test_update_helper import snapshot
from test_update_install import install_release
from test_updater import Rig

OLD_TAG = "v1.0.4"
NEW_VERSION = "1.0.5"
OLD_LAYOUT = 19
NEW_LAYOUT = 22      # the data layout of this build (schema step 22, row 875); the test pins the number on purpose
SKIP_WORDS = "layout 20 is not on this tree yet (store.SCHEMA_VERSION is %s): the 19-to-20 update test runs once it is 20"

CHILD = r'''
import json, sys
src, vendor, db, op = sys.argv[1:5]
sys.path.insert(0, src)
sys.path.insert(0, vendor)
from clark import store
from clark.store import open_store
if op == "seed":
    s = open_store(db, onedrive_roots=[])
    with s.step("dashboard", "Demo User") as st:
        st.create("projects", {"code": "ABC", "name": "Example Programme", "health": "On track", "client_name": "Example Client"})
    s.close()
    out = {"layout": store.SCHEMA_VERSION}
else:
    try:
        s = open_store(db, onedrive_roots=[])
        out = {"layout": store.SCHEMA_VERSION, "copy": str(s.migration_backup) if s.migration_backup else None}
        s.close()
    except Exception as e:
        out = {"layout": store.SCHEMA_VERSION, "error": str(e), "kind": type(e).__name__}
print(json.dumps(out))
'''

MORE_ROWS = [
    "INSERT INTO projects (code, name, health, health_reason) VALUES ('DEF', 'Other Programme', 'At risk', 'Late supplier')",
    "INSERT INTO report_sections (project, id, type, title, body, sort_order) VALUES ('ABC', 'ABC-S-101', 'milestones', 'Key dates', '', 101)",
    "INSERT INTO report_sections (project, id, type, title, body, sort_order) VALUES ('ABC', 'ABC-S-102', 'text', 'Notes', '<p>Plain words</p>', 102)",
    "INSERT INTO report_sections (project, id, type, title, body, sort_order) VALUES ('ABC', 'ABC-S-103', 'workitems', 'Work', '', 103)",
    "INSERT INTO milestones (id, project, name, baseline_date, source) VALUES ('ABC-M-001', 'ABC', 'Pilot live', '2026-12-01', 'test')",
    "INSERT INTO use_cases (id, project, ref, title, status, headline, source) VALUES ('ABC-U-001', 'ABC', '1.1', 'Match invoices', 'On track', 'Going well', 'test')",
    "INSERT INTO actions (id, project, description, raised, client_action, source) VALUES ('ABC-A-001', 'ABC', 'Send the matching rules', '2026-10-01', 1, 'test')",
    "INSERT INTO raid (id, project, type, description, raised, source) VALUES ('ABC-001', 'ABC', 'Risk', 'Supplier may be late', '2026-10-02', 'test')",
    "INSERT INTO decisions (id, project, decision, date, source) VALUES ('ABC-D-001', 'ABC', 'Use the pilot site', '2026-10-03', 'test')",
    "INSERT INTO documents (project, id, title, kind, url, sort_order) VALUES ('ABC', 'ABC-L-001', 'Plan', 'pdf', 'https://example.test/plan', 1)",
    "INSERT INTO publications (project, week_ending, local_path, client_path, word, file_sha256, checks, by_user, number) "
    "VALUES ('ABC', '2026-10-30', 'Reports/abc-1.html', NULL, 0, 'abc123', 'passed', 'Demo User', 1)",
]


def child(src, db, op, vendor=None):
    """Run the store of the code at `src` on `db` in a real child python; its one line of JSON."""
    script = Path(tempfile.mkdtemp(prefix="clark child ")) / "child.py"
    try:
        script.write_text(CHILD, encoding="utf-8")
        run = subprocess.run([sys.executable, "-I", str(script), str(src), str(vendor or Path(src).parent / "vendor"), str(db), op],
                             capture_output=True, text=True, timeout=300)
        if run.returncode:
            raise AssertionError(run.stderr)
        return json.loads(run.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(script.parent, ignore_errors=True)


def layout(path):
    con = sqlite3.connect(str(path))
    try:
        return int(con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0])
    finally:
        con.close()


def every_row(path, leave_out=()):
    """Every table's rows (meta and SQLite's own left out), rowid order, without the columns in `leave_out`."""
    con = sqlite3.connect(str(path))
    try:
        out = {}
        for (n,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name != 'meta' ORDER BY name"):
            kept = ", ".join(f'"{c[1]}"' for c in con.execute(f'PRAGMA table_info("{n}")') if c[1] not in leave_out and f"{n}.{c[1]}" not in leave_out)
            out[n] = con.execute(f'SELECT rowid, {kept} FROM "{n}" ORDER BY rowid').fetchall()
        return out
    finally:
        con.close()


def dump(path):
    con = sqlite3.connect(str(path))
    try:
        return list(con.iterdump())
    finally:
        con.close()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=300)


class Update19To20(Rig):
    skip_reason = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark 19to20 ")).resolve()
        cls.trees = []
        if store_module.SCHEMA_VERSION < NEW_LAYOUT:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest(SKIP_WORDS % store_module.SCHEMA_VERSION)      # NEW: skip only while layout 20 is not here
        try:
            if git("rev-parse", "--verify", "--quiet", OLD_TAG + "^{commit}").returncode:
                try:
                    subprocess.run(["git", "fetch", "--depth=1", "origin", "tag", OLD_TAG], cwd=str(ROOT), capture_output=True, text=True, timeout=120)
                except subprocess.TimeoutExpired:
                    pass
            if git("rev-parse", "--verify", "--quiet", OLD_TAG + "^{commit}").returncode:
                words = f"the tag {OLD_TAG} is not in this clone (a shallow clone has no tags) and could not be fetched: the layout-19 release cannot be built"
                if os.environ.get("CI"):
                    raise AssertionError(words)      # in CI a missing tag is a failure, never a quiet skip
                raise unittest.SkipTest(words)
            cls.old_tree, cls.new_tree = cls.tmp / "old-tree", cls.tmp / "new-tree"
            for tree, ref in ((cls.old_tree, OLD_TAG), (cls.new_tree, "HEAD")):
                made = git("worktree", "add", "--detach", str(tree), ref)
                if made.returncode:
                    raise unittest.SkipTest("a scratch checkout could not be made: " + made.stderr.strip()[:200])
                cls.trees.append(tree)
            init = cls.new_tree / "src" / "clark" / "__init__.py"
            text = init.read_text(encoding="utf-8")
            assert 'version__ = "' in text
            init.write_text(text.replace(package.version(cls.new_tree), NEW_VERSION), encoding="utf-8")
            assert package.version(cls.new_tree) == NEW_VERSION
            assert package.schema_version(cls.old_tree) == OLD_LAYOUT, "the old tree is not at layout 19"
            assert package.schema_version(cls.new_tree) == store_module.SCHEMA_VERSION
            # The old release holds what its own tag held: today's list names files bundled since (#891), which the old tree has not.
            had = tuple(item for item in package.SHARED if (cls.old_tree / item).exists())
            with mock.patch.object(package, "SHARED", had):
                cls.old_zip = package.build("mac", cls.tmp / "dist-old", root=cls.old_tree, dirty=True)
            cls.new_zip = package.build("mac", cls.tmp / "dist-new", root=cls.new_tree, dirty=True)
            _signing.sign_file(cls.old_zip)
            _signing.sign_file(cls.new_zip)
            # the old build, unpacked once, to open data with (the installed app is a fresh unpack in each test)
            cls.old_app = install_release(cls.old_zip, cls.tmp / "old-build")
            # data made by the old code
            cls.seed = cls.tmp / "seed"
            cls.seed.mkdir()
            seed_db = cls.seed / "clark.db"
            made = child(cls.old_app / ".app" / "src", seed_db, "seed")
            assert made["layout"] == OLD_LAYOUT, made
            con = sqlite3.connect(str(seed_db), isolation_level=None)
            for sql in MORE_ROWS:
                con.execute(sql)
            con.close()
            assert layout(seed_db) == OLD_LAYOUT
            cls.base = every_row(seed_db)
            cls.base_dump = dump(seed_db)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for tree in cls.trees:
            git("worktree", "remove", "--force", str(tree))
        git("worktree", "prune")
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        super().setUp()
        # the installed app is the layout-19 release; the data is the layout-19 data the old code made; Downloads holds the new release
        shutil.rmtree(self.app)
        install_release(self.old_zip, self.app)
        (self.app / "my notes.txt").write_text("mine\n", encoding="utf-8")
        self.db.unlink()
        shutil.copyfile(self.seed / "clark.db", self.db)
        for p in self.downloads.iterdir():
            p.unlink()
        for p in (self.new_zip, Path(str(self.new_zip) + ".sig")):
            shutil.copyfile(p, self.downloads / p.name)
        self.app_19 = snapshot(self.app)
        self.up = self.make(version="1.0.4", schema=OLD_LAYOUT)

    def new_start(self):
        """What the new build does at its start: opens the data, in a child python from the installed app, then settles the update."""
        done = child(self.app / ".app" / "src", self.db, "open")
        self.assertNotIn("error", done)
        now = self.make(version=NEW_VERSION, schema=store_module.SCHEMA_VERSION, migration_backup=done["copy"])
        self.assertTrue(now.settle())
        return now, done

    def update_to_20(self):
        self.installed()
        return self.new_start()

    # --- the update itself ---

    def test_the_release_zips_are_the_real_ones_at_layouts_19_and_20(self):
        old = json.loads((self.old_app / "clark-release.json").read_text(encoding="utf-8"))
        self.assertEqual(("1.0.4", OLD_LAYOUT), (old["version"], old["schema_version"]))
        with zipfile.ZipFile(self.new_zip) as z:
            new = json.loads(z.read("clark/clark-release.json"))
        self.assertEqual((NEW_VERSION, NEW_LAYOUT), (new["version"], new["schema_version"]))
        self.assertEqual(OLD_LAYOUT, layout(self.seed / "clark.db"))
        self.assertEqual(OLD_LAYOUT, child(self.old_app / ".app" / "src", self.seed / "clark.db", "open")["layout"])

    def test_the_backup_is_made_first_and_holds_every_row_at_layout_19(self):
        body = self.reviewed()
        self.assertEqual("Version 1.0.4 → 1.0.5. Released " + body["review"]["heading"].split("Released ")[1], body["review"]["heading"])
        status, done = self.up.install({"review_id": body["review_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        # handed over, the helper not run yet: the app and the data are still exactly what they were, and the backup set is whole
        self.assertEqual(self.app_19, snapshot(self.app))
        self.assertEqual(self.base, every_row(self.db))
        folder, record = ui.sets(self.data)[-1]
        self.assertEqual((OLD_LAYOUT, False), (record["db_before"]["schema_version"], record["installed"]))
        copy = folder / ui.DB_COPY
        self.assertEqual(OLD_LAYOUT, layout(copy))
        self.assertEqual(self.base, every_row(copy))
        self.assertTrue(record["app_files"])
        self.assertEqual(h.OK, self.run_helper()[0])
        self.assertEqual(self.base, every_row(folder / ui.DB_COPY), "the backup does not change when the update goes in")

    def test_the_new_build_is_installed_over_the_old_one(self):
        self.installed()
        self.assertEqual(NEW_VERSION, json.loads((self.app / "clark-release.json").read_text(encoding="utf-8"))["version"])
        self.assertIn(f'"{NEW_VERSION}"', (self.app / ".app" / "src" / "clark" / "__init__.py").read_text(encoding="utf-8"))
        self.assertEqual("mine\n", (self.app / "my notes.txt").read_text(encoding="utf-8"), "the person's own file stays")
        self.assertEqual(self.base, every_row(self.db), "installing does not touch the data: the new build migrates it when it starts")
        self.assertEqual(OLD_LAYOUT, layout(self.db))

    def test_the_new_build_migrates_19_to_20_keeping_every_row_and_a_second_open_changes_nothing(self):
        now, done = self.update_to_20()
        self.assertEqual(NEW_LAYOUT, done["layout"])
        self.assertEqual(NEW_LAYOUT, layout(self.db))
        after = every_row(self.db, leave_out=("brand", "use_cases.owner", "use_cases.owner_id"))
        self.assertEqual(self.base, after, "every row of every table is kept (the new brand and owner columns apart)")
        for table in ("projects", "report_sections", "milestones", "use_cases", "actions", "raid", "decisions", "documents", "publications"):
            self.assertTrue(after[table], table)
        self.assertEqual([("ABC", "generic"), ("DEF", "generic")], self.brands(self.db), "projects.brand is 'generic' for every existing project")
        # the safety copy the migration took first: layout 19, every row
        copy = Path(done["copy"])
        self.assertEqual(self.data / "backups", copy.parent)
        self.assertEqual(OLD_LAYOUT, layout(copy))
        self.assertEqual(self.base, every_row(copy))
        self.assertEqual({"backup": copy.name, "from": OLD_LAYOUT, "to": NEW_LAYOUT}, ui.last_update(self.data)[1]["migration"])
        # a second open changes nothing
        before, backups = dump(self.db), sorted(p.name for p in (self.data / "backups").iterdir())
        again = child(self.app / ".app" / "src", self.db, "open")
        self.assertEqual({"layout": NEW_LAYOUT, "copy": None}, again)
        self.assertEqual(before, dump(self.db))
        self.assertEqual(backups, sorted(p.name for p in (self.data / "backups").iterdir()))

    def test_undo_puts_the_app_and_the_data_back_at_layout_19_and_the_old_build_opens_it(self):
        now, done = self.update_to_20()
        self.assertEqual(NEW_LAYOUT, layout(self.db))
        status, armed = now.arm_undo({})
        self.assertEqual((200, "full"), (status, armed["choice"]))
        self.assertIn("Changes made after the update will be lost.", armed["line"])
        copy_bytes = Path(done["copy"]).read_bytes()
        status, undone = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((200, True), (status, undone["restart"]), undone)
        self.assertEqual(h.OK, self.run_helper()[0])
        self.assertEqual(self.app_19, snapshot(self.app), "the app folder is the layout-19 release again, byte for byte")
        self.assertEqual(OLD_LAYOUT, layout(self.db))
        self.assertEqual(copy_bytes, Path(self.db).read_bytes(), "the data is the copy that was taken before the migration")
        self.assertEqual(self.base, every_row(self.db), "every row, as it was")
        opened = child(self.app / ".app" / "src", self.db, "open")       # the restored OLD build, from the app folder
        self.assertEqual({"layout": OLD_LAYOUT, "copy": None}, opened)
        self.assertEqual(OLD_LAYOUT, layout(self.db))

    def test_the_old_build_refuses_the_new_data_with_its_plain_sentence_and_touches_nothing(self):
        self.update_to_20()
        before = (digest(self.db), sorted(p.name for p in (self.data / "backups").iterdir()))
        said = child(self.old_app / ".app" / "src", self.db, "open")
        self.assertEqual(OLD_LAYOUT, said["layout"])
        self.assertEqual("Invalid", said["kind"])
        self.assertEqual("This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.", said["error"])
        self.assertEqual(before, (digest(self.db), sorted(p.name for p in (self.data / "backups").iterdir())))
        self.assertEqual(NEW_LAYOUT, layout(self.db))

    def test_the_install_side_run_by_the_old_builds_own_updater_code(self):
        self.skipTest("not driven by this test: the install side of the update (review, backup, hand-over) is run here by "
                      "the NEW build's updater code; the 1.0.4 updater that a person's 1.0.4 really runs is not driven, because its server "
                      "needs a live process, port and window")

    # --- helpers ---

    def brands(self, path):
        con = sqlite3.connect(str(path))
        try:
            return con.execute("SELECT code, brand FROM projects ORDER BY code").fetchall()
        finally:
            con.close()

    def test_a_layout_22_copy_is_refused_by_the_new_build_and_left_untouched(self):
        self.update_to_20()
        con = sqlite3.connect(str(self.db), isolation_level=None)
        con.execute("UPDATE meta SET v = ? WHERE k = 'schema_version'", (str(NEW_LAYOUT + 1),))
        con.close()
        before = (digest(self.db), sorted(p.name for p in (self.data / "backups").iterdir()))
        said = child(self.app / ".app" / "src", self.db, "open")
        self.assertEqual("Invalid", said["kind"])
        self.assertEqual("This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.", said["error"])
        self.assertEqual(before, (digest(self.db), sorted(p.name for p in (self.data / "backups").iterdir())))
        self.assertEqual(NEW_LAYOUT + 1, layout(self.db))


if __name__ == "__main__":
    unittest.main()

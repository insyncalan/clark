"""Row 926 (gate G2): a real update from data layout 17 to the layout the new build has now (layout 20: step 20 added the project's brand, step 18 added the Gantt lines, step 19 lets a report hold a Gantt section), through the updater's real package path.

The previous release (tag v1.0.3, data layout 17) is built into a real zip with dev/tools/package.py, and so is this tree (its version
raised by one, in a throwaway checkout, so the updater sees an update; the product files are otherwise this tree's own). The data is
made by the OLD code (the tag's own store), the old zip is unpacked as the installed app, and the updater (review, install, the helper
that swaps the app folder, settle, arm_undo, undo) runs on the real zips with a real database. Only the helper's platform seams are
faked (no process is started, no port is used), as test_updater does. The "new build opens the data" and "old build opens the data"
steps run in a real child python from the installed app folder, so the code that opens the data is the code that is installed.

Covered: the update succeeds; the backup set was made before anything was changed (layout 17, every row); the new build migrates to
layout 19 keeping every row and takes its own safety copy first; a second open changes nothing; Undo puts the app folder and the data
back at layout 17 and the old build opens it; the old build refuses the new data with its plain "newer" sentence and touches nothing.
Not covered (said in the test that skips): the install side run by the OLD build's own updater code (the one in the installed 1.0.3).
No network, no browser, no window. Run: python3 dev/run_tests.py test_update_17_to_18
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
from pathlib import Path

from _paths import ROOT
import _signing
import package
from clark import store as store_module, update_helper as h, update_install as ui
from test_update_helper import snapshot
from test_update_install import install_release
from test_updater import Rig

OLD_TAG = "v1.0.3"
NEW_VERSION = "1.0.4"
NEW_LAYOUT = 20      # the data layout of this build (schema steps 18 to 20); the test pins the number on purpose
GANTT_COLUMNS = ("show_gantt_editor", "show_gantt_client", "gantt_tab_name", "gantt_title", "gantt_hidden_columns", "gantt_default_rows")

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
            kept = ", ".join(f'"{c[1]}"' for c in con.execute(f'PRAGMA table_info("{n}")') if c[1] not in leave_out)
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


class Update17To18(Rig):
    skip_reason = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark 17to18 ")).resolve()
        cls.trees = []
        try:
            if git("rev-parse", "--verify", "--quiet", OLD_TAG + "^{commit}").returncode:
                try:
                    subprocess.run(["git", "fetch", "--depth=1", "origin", "tag", OLD_TAG], cwd=str(ROOT), capture_output=True, text=True, timeout=120)
                except subprocess.TimeoutExpired:
                    pass
            if git("rev-parse", "--verify", "--quiet", OLD_TAG + "^{commit}").returncode:
                words = f"the tag {OLD_TAG} is not in this clone (a shallow clone has no tags) and could not be fetched: the layout-17 release cannot be built"
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
            assert package.schema_version(cls.old_tree) == 17, "the old tree is not at layout 17"
            assert package.schema_version(cls.new_tree) == store_module.SCHEMA_VERSION
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
            assert made["layout"] == 17, made
            con = sqlite3.connect(str(seed_db), isolation_level=None)
            for sql in MORE_ROWS:
                con.execute(sql)
            con.close()
            assert layout(seed_db) == 17
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
        # the installed app is the layout-17 release; the data is the layout-17 data the old code made; Downloads holds the new release
        shutil.rmtree(self.app)
        install_release(self.old_zip, self.app)
        (self.app / "my notes.txt").write_text("mine\n", encoding="utf-8")
        self.db.unlink()
        shutil.copyfile(self.seed / "clark.db", self.db)
        for p in self.downloads.iterdir():
            p.unlink()
        for p in (self.new_zip, Path(str(self.new_zip) + ".sig")):
            shutil.copyfile(p, self.downloads / p.name)
        self.app_17 = snapshot(self.app)
        self.up = self.make(version="1.0.3", schema=17)

    def new_start(self):
        """What the new build does at its start: opens the data, in a child python from the installed app, then settles the update."""
        done = child(self.app / ".app" / "src", self.db, "open")
        self.assertNotIn("error", done)
        now = self.make(version=NEW_VERSION, schema=store_module.SCHEMA_VERSION, migration_backup=done["copy"])
        self.assertTrue(now.settle())
        return now, done

    def update_to_18(self):
        self.installed()
        return self.new_start()

    # --- the update itself ---

    def test_the_release_zips_are_the_real_ones_at_layouts_17_and_19(self):
        old = json.loads((self.old_app / "clark-release.json").read_text(encoding="utf-8"))
        self.assertEqual(("1.0.3", 17), (old["version"], old["schema_version"]))
        with zipfile.ZipFile(self.new_zip) as z:
            new = json.loads(z.read("clark/clark-release.json"))
        self.assertEqual((NEW_VERSION, NEW_LAYOUT), (new["version"], new["schema_version"]))
        self.assertEqual(17, layout(self.seed / "clark.db"))
        self.assertEqual(17, child(self.old_app / ".app" / "src", self.seed / "clark.db", "open")["layout"])

    def test_the_backup_is_made_first_and_holds_every_row_at_layout_17(self):
        body = self.reviewed()
        self.assertEqual("Version 1.0.3 → 1.0.4. Released " + body["review"]["heading"].split("Released ")[1], body["review"]["heading"])
        status, done = self.up.install({"review_id": body["review_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        # handed over, the helper not run yet: the app and the data are still exactly what they were, and the backup set is whole
        self.assertEqual(self.app_17, snapshot(self.app))
        self.assertEqual(self.base, every_row(self.db))
        folder, record = ui.sets(self.data)[-1]
        self.assertEqual((17, False), (record["db_before"]["schema_version"], record["installed"]))
        copy = folder / ui.DB_COPY
        self.assertEqual(17, layout(copy))
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
        self.assertEqual(17, layout(self.db))

    def test_the_new_build_migrates_17_to_18_keeping_every_row_and_a_second_open_changes_nothing(self):
        now, done = self.update_to_18()
        self.assertEqual(NEW_LAYOUT, done["layout"])
        self.assertEqual(NEW_LAYOUT, layout(self.db))
        after = every_row(self.db, leave_out=GANTT_COLUMNS + ("brand",))
        self.assertEqual(self.base, {t: rows for t, rows in after.items() if t != "gantt_lines"}, "every row of every table is kept")
        for table in ("report_sections", "milestones", "use_cases", "actions", "raid", "decisions", "documents", "publications"):
            self.assertTrue(after[table], table)
        self.assertEqual([], after["gantt_lines"], "the new table is there and empty")
        self.assertEqual(self.fresh_defaults(), self.gantt_values(self.db), "every project has the six Gantt columns at their defaults")
        con = sqlite3.connect(str(self.db))
        try:
            self.assertEqual({r[0] for r in con.execute("SELECT brand FROM projects")}, {"generic"}, "every project's brand is generic")
        finally:
            con.close()
        # the safety copy the migration took first: layout 17, every row
        copy = Path(done["copy"])
        self.assertEqual(self.data / "backups", copy.parent)
        self.assertEqual(17, layout(copy))
        self.assertEqual(self.base, every_row(copy))
        self.assertEqual({"backup": copy.name, "from": 17, "to": NEW_LAYOUT}, ui.last_update(self.data)[1]["migration"])
        # a second open changes nothing
        before, backups = dump(self.db), sorted(p.name for p in (self.data / "backups").iterdir())
        again = child(self.app / ".app" / "src", self.db, "open")
        self.assertEqual({"layout": NEW_LAYOUT, "copy": None}, again)
        self.assertEqual(before, dump(self.db))
        self.assertEqual(backups, sorted(p.name for p in (self.data / "backups").iterdir()))

    def test_undo_puts_the_app_and_the_data_back_at_layout_17_and_the_old_build_opens_it(self):
        now, done = self.update_to_18()
        self.assertEqual(NEW_LAYOUT, layout(self.db))
        status, armed = now.arm_undo({})
        self.assertEqual((200, "full"), (status, armed["choice"]))
        self.assertIn("Changes made after the update will be lost.", armed["line"])
        copy_bytes = Path(done["copy"]).read_bytes()
        status, undone = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((200, True), (status, undone["restart"]), undone)
        self.assertEqual(h.OK, self.run_helper()[0])
        self.assertEqual(self.app_17, snapshot(self.app), "the app folder is the layout-17 release again, byte for byte")
        self.assertEqual(17, layout(self.db))
        self.assertEqual(copy_bytes, Path(self.db).read_bytes(), "the data is the copy that was taken before the migration")
        self.assertEqual(self.base, every_row(self.db), "every row, as it was")
        opened = child(self.app / ".app" / "src", self.db, "open")       # the restored OLD build, from the app folder
        self.assertEqual({"layout": 17, "copy": None}, opened)
        self.assertEqual(17, layout(self.db))

    def test_the_old_build_refuses_the_new_data_with_its_plain_sentence_and_touches_nothing(self):
        self.update_to_18()
        before = (digest(self.db), sorted(p.name for p in (self.data / "backups").iterdir()))
        said = child(self.old_app / ".app" / "src", self.db, "open")
        self.assertEqual(17, said["layout"])
        self.assertEqual("Invalid", said["kind"])
        self.assertEqual("This data needs a newer clark. Nothing was changed. Install the latest clark, then try again.", said["error"])
        self.assertEqual(before, (digest(self.db), sorted(p.name for p in (self.data / "backups").iterdir())))
        self.assertEqual(NEW_LAYOUT, layout(self.db))

    def test_the_install_side_run_by_the_old_builds_own_updater_code(self):
        self.skipTest("not reachable without product changes: the install side of the update (review, backup, hand-over) is run here by "
                      "the NEW build's updater code; the 1.0.3 updater that a person's 1.0.3 really runs is not driven, because its server "
                      "needs a live process, port and window")

    # --- helpers ---

    def gantt_values(self, path):
        con = sqlite3.connect(str(path))
        try:
            return con.execute(f"SELECT code, {', '.join(GANTT_COLUMNS)} FROM projects ORDER BY code").fetchall()
        finally:
            con.close()

    def fresh_defaults(self):
        """What a project made by the new build has in the six columns: the defaults. One per project of the seed."""
        fresh = Path(tempfile.mkdtemp(prefix="clark fresh ")) / "clark.db"
        self.addCleanup(shutil.rmtree, fresh.parent, True)
        con = sqlite3.connect(str(self.db))
        codes = [r[0] for r in con.execute("SELECT code FROM projects ORDER BY code")]
        con.close()
        store_module.open_store(fresh, onedrive_roots=[]).close()
        con = sqlite3.connect(str(fresh), isolation_level=None)
        try:
            for code in codes:
                con.execute("INSERT INTO projects (code, name) VALUES (?, 'Fresh')", (code,))
            return con.execute(f"SELECT code, {', '.join(GANTT_COLUMNS)} FROM projects ORDER BY code").fetchall()
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()

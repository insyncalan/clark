"""#111: the backup list, Preview and Restore through a real server on 127.0.0.1 (server.py, safety.py, backup.py), and the
number of backups kept (settings.py). The data is a DemoStore in a temporary folder with fictional data; nothing else is read.

Run: python3 dev/run_tests.py test_safety
No Chrome is started: the page's own logic is tests/test_safety_logic.py.
"""
import errno
import hashlib
import http.client
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _demo import DemoStore
from clark import backup, changes, platform, safety, server as sv, settings, store as cs
from clark.store import open_store
from test_store_migration import make_v1

JARGON = safety.JARGON + ("sql", "token", "json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Rig:
    """A server over a Safety, a demo store (the launcher's own open store) and a backups folder with one backup."""

    def __init__(self, case, wired=True):
        self.case = case
        self.demo = DemoStore()
        case.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.path = self.store.path
        self.folder = self.store.backups_dir
        self.safety = safety.Safety(self.path, [])
        self.httpd = sv.LocalServer((sv.HOST, 0), safety=self.safety if wired else None)
        self.httpd.handle_error = lambda *a: None
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        case.addCleanup(self.stop)
        self.first = self.backup("daily")                   # the copy of today's first step (what the data was)
        self.store.close()                                  # as the launcher does before it serves: nothing holds the database open

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def backup(self, tag="daily"):
        return backup.take(self.store, tag).name

    def edit(self, n=1):
        """n changes made as a request would make them, each on a store of its own; the last step."""
        for _ in range(n):
            s = open_store(self.path, onedrive_roots=[])
            try:
                with s.step("dashboard", "Demo User") as st:
                    st.create("actions", {"project": "ABC", "description": f"Another action {os.urandom(3).hex()}", "raised": "2026-10-01", "source": "demo"})
            finally:
                s.close()
        return self.live()[1]

    def call(self, method, path, body=None, token=None, host=None, ctype="application/json", origin=None, raw=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
            headers = {"Host": host or f"127.0.0.1:{self.httpd.server_port}"}
            if token is not False:
                headers[sv.TOKEN_HEADER] = token or sv.TOKEN
            if origin:
                headers["Origin"] = origin
            if data is not None:
                headers.update({"Content-Type": ctype, "Content-Length": str(len(data))})
            conn.request(method, path, data, headers)
            r = conn.getresponse()
            body_ = r.read()
            return r.status, json.loads(body_) if body_ else None
        finally:
            conn.close()

    def preview(self, name, **kw):
        return self.call("POST", "/api/backups/preview", {"name": name}, **kw)

    def restore(self, name, step, **kw):
        return self.call("POST", "/api/backups/restore", {"name": name, "last_step": step}, **kw)

    def live(self):
        con = sqlite3.connect(str(self.path))
        try:
            return con.execute("SELECT (SELECT count(*) FROM actions), (SELECT max(apply_id) FROM applies)").fetchone()
        finally:
            con.close()

    def files(self):
        return sorted(str(p.relative_to(self.demo.dir)) for p in self.demo.dir.rglob("*") if not p.name.endswith(("-wal", "-shm")))


class Base(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)


class TheList(Base):
    def test_newest_first_in_words_with_size_status_and_the_number_kept(self):
        r = self.rig
        r.edit()
        undo = r.backup("undo")
        status, body = r.call("GET", "/api/backups")
        self.assertEqual(status, 200)
        self.assertEqual([b["name"] for b in body["backups"]][:2], [undo, r.first])
        row = body["backups"][0]
        self.assertEqual((row["kind_label"], row["kind"]), ("Before an undo", "before an undo"))
        self.assertRegex(row["when"], r"^\d\d-\d\d-\d{4} \d\d:\d\d$")
        self.assertRegex(row["size_text"], r"^\d+ KB$")
        self.assertEqual(body["status"], f"Latest backup: {row['when']}. A daily backup is always made.")
        self.assertEqual((body["keep"], body["warning"], body["newest_ok"]), (14, None, True))
        self.assertEqual(body["keep_label"], "How many backups to keep")

    def test_every_kind_has_a_label_in_words(self):
        self.assertEqual(set(safety.KIND_LABELS), set(backup.TAGS))
        for tag, words in backup.KIND_WORDS.items():
            if tag != "restore":                       # KIND_WORDS calls the copy taken before a restore "restored copy"; the page says what it is
                self.assertEqual(safety.KIND_LABELS[tag].lower(), words)
        self.assertEqual(safety.KIND_LABELS["restore"], "Before a restore")

    def test_sizes(self):
        self.assertEqual([safety.size_text(n) for n in (0, 1, 1023, 217088, 1024 ** 2, 1.5 * 1024 ** 2)],
                         ["1 KB", "1 KB", "1 KB", "212 KB", "1.0 MB", "1.5 MB"])

    def test_no_backups_yet(self):
        for p in self.rig.folder.iterdir():
            p.unlink()
        status, body = self.rig.call("GET", "/api/backups")
        self.assertEqual((status, body["backups"]), (200, []))
        self.assertEqual(body["status"], safety.MESSAGES["none_yet"])

    def test_a_damaged_newest_copy_is_said_plainly(self):
        r = self.rig
        bad = r.folder / "clark-20990101T000000Z-undo.db"
        bad.write_bytes(b"not a database at all" * 100)
        os.utime(bad, (4_000_000_000, 4_000_000_000))
        _, body = r.call("GET", "/api/backups")
        self.assertFalse(body["newest_ok"])
        self.assertRegex(body["status"], r"^The latest backup, from \d\d-\d\d-\d{4}, is damaged and can't be used\.$")

    def test_the_folder_is_a_file(self):
        shutil.rmtree(self.rig.folder)
        self.rig.folder.write_text("x", encoding="utf-8")
        status, body = self.rig.call("GET", "/api/backups")
        self.assertEqual((status, body["code"]), (503, "folder"))

    def test_the_daily_warning_is_a_module_value_set_by_a_failed_copy_and_cleared_by_a_good_one(self):
        r = self.rig
        for p in r.folder.iterdir():
            p.unlink()
        self.addCleanup(setattr, backup, "backup_warning", None)
        with mock.patch.object(backup, "take", side_effect=OSError(errno.ENOSPC, "No space left on device")), \
                self.assertLogs("clark.backup", "WARNING"):
            backup.before(r.store, "dashboard")
        self.assertIn("today's backup of your data couldn't be made", backup.backup_warning)
        _, body = r.call("GET", "/api/backups")
        self.assertEqual(body["warning"], backup.backup_warning)
        backup.before(r.store, "dashboard")                      # a good one this time
        self.assertIsNone(backup.backup_warning)
        self.assertIsNone(r.call("GET", "/api/backups")[1]["warning"])

    def test_unwired_the_routes_answer_in_plain_words(self):
        rig = Rig(self, wired=False)
        for method, path in (("GET", "/api/backups"), ("POST", "/api/backups/preview"), ("POST", "/api/backups/restore")):
            status, body = rig.call(method, path, {} if method == "POST" else None)
            self.assertEqual((status, body["code"]), (503, "no_backups"))
            self.assertEqual(body["message"], sv.MESSAGES["no_backups"])


class Preview(Base):
    def test_counts_in_the_copy_and_now_and_nothing_changes(self):
        r = self.rig
        step = r.edit(2)
        before_files, before_live = r.files(), r.live()
        h = sha(r.folder / r.first)
        status, body = r.preview(r.first)
        self.assertEqual(status, 200)
        self.assertEqual(body["copy"], {"projects": 1, "work_items": 0, "milestones": 1})
        self.assertEqual(body["now"], {"projects": 1, "work_items": 2, "milestones": 1})
        self.assertEqual((body["last_step"], body["same_database"], body["older"]), (step, True, False))
        self.assertEqual((r.live(), r.files(), sha(r.folder / r.first)), (before_live, before_files, h))

    def test_it_reads_a_private_temporary_copy_which_is_removed_even_after_a_failure(self):
        r = self.rig
        made = []
        real = tempfile.mkdtemp
        with mock.patch.object(tempfile, "mkdtemp", side_effect=lambda **kw: made.append(real(**kw)) or made[-1]):
            self.assertEqual(r.preview(r.first)[0], 200)
            bad = r.folder / "clark-20990101T000000Z-undo.db"
            bad.write_bytes(b"x" * 5000)
            self.assertEqual(r.preview(bad.name)[1]["code"], "damaged")
        self.assertEqual(len(made), 2)
        self.assertEqual([p for p in made if os.path.exists(p)], [])

    def test_it_never_opens_the_live_file_for_writing(self):
        r = self.rig
        seen = []
        real = sqlite3.connect
        with mock.patch.object(sqlite3, "connect", side_effect=lambda target, *a, **k: seen.append(str(target)) or real(target, *a, **k)):
            r.preview(r.first)
        self.assertEqual([t for t in seen if t == str(r.path)], [])      # the snapshot opens it through a read-only address (a file: URI)

    def test_an_older_copy_says_it_is_brought_up_to_date(self):
        r = self.rig
        name = self.older_copy()
        status, body = r.preview(name)
        self.assertEqual((status, body["older"], body["older_note"]), (200, True, safety.MESSAGES["older"]))

    def older_copy(self):
        scratch = self.rig.demo.dir / "v1"
        scratch.mkdir()
        v1 = make_v1(scratch)
        con = sqlite3.connect(str(v1))
        con.execute("UPDATE meta SET v = ? WHERE k = 'db_id'", (cs.identity(self.rig.path),))
        con.commit()
        con.close()
        name = "clark-20300101T000000Z-undo.db"
        shutil.move(v1, self.rig.folder / name)
        return name

    def test_a_newer_copy_is_refused_at_preview_and_restore(self):
        r = self.rig
        name = "clark-20300101T000000Z-undo.db"
        shutil.copyfile(r.folder / r.first, r.folder / name)
        con = sqlite3.connect(str(r.folder / name))
        con.execute("UPDATE meta SET v = '99' WHERE k = 'schema_version'")
        con.commit()
        con.close()
        step = r.live()[1]
        for status, body in (r.preview(name), r.restore(name, step)):
            self.assertEqual((status, body["code"]), (400, "newer"))
            self.assertEqual(body["message"], f"{name} was made by a newer clark (version 99); update clark to use it.")
        
    def test_a_backup_of_another_database_is_flagged(self):
        r = self.rig
        other = DemoStore()
        self.addCleanup(other.close)
        name = "clark-20300101T000000Z-undo.db"
        shutil.copyfile(backup.take(other.store, "undo"), r.folder / name)
        status, body = r.preview(name)
        self.assertEqual(status, 200)
        self.assertFalse(body["same_database"])


class Names(Base):
    """Attacks on the name: only a whole backup name in the backups folder is ever used."""

    def bad_names(self):
        r = self.rig
        link = r.folder / "clark-20300101T000000Z-undo.db"
        os.symlink(r.path, link)
        hard = r.folder / "clark-20300102T000000Z-undo.db"
        os.link(r.folder / r.first, hard)
        outside = r.demo.dir / "other.db"
        shutil.copyfile(r.folder / r.first, outside)
        (r.folder / "replaced-20300101T000000Z").mkdir()
        shutil.copyfile(r.folder / r.first, r.folder / "replaced-20300101T000000Z" / r.first)
        return [link.name, hard.name, "../clark.db", "../other.db", f"../backups/{r.first}", f"replaced-20300101T000000Z/{r.first}",
                r.first + "\n", r.first[:-3] + "\x00.db", "clark-\u0662\u0660\u0663\u0660\u0660\u0661\u0660\u0661T000000Z-undo.db", "notes.txt",
                "", "/etc/passwd", str(r.path), "clark-20300101T000000Z-undo.db.part", " " + r.first]

    def test_no_forged_name_is_previewed_or_restored(self):
        r = self.rig
        names = self.bad_names()
        step = r.live()[1]
        before = (r.files(), sha(r.path))
        for name in names:
            with self.subTest(name=name):
                for status, body in (r.preview(name), r.restore(name, step)):
                    self.assertEqual(status, 400, body)
                    self.assertIn(body["code"], ("no_backup", "bad_request"))
                    self.assertNotIn("\x00", body["message"])
                self.assertEqual((r.files(), sha(r.path)), before)

    def test_a_name_that_is_not_text_or_is_long(self):
        r = self.rig
        for name in (None, 5, ["a"], {"a": 1}, True, "x" * 5000):
            with self.subTest(name=name):
                self.assertEqual(r.call("POST", "/api/backups/preview", {"name": name})[0], 400)
        self.assertEqual(r.call("POST", "/api/backups/restore", ["a"])[0], 400)
        self.assertEqual(r.call("POST", "/api/backups/restore", {"name": r.first, "last_step": "7"})[0], 400)
        self.assertEqual(r.call("POST", "/api/backups/restore", {"name": r.first, "last_step": True})[0], 400)

    def test_a_missing_name_says_which_in_words(self):
        status, body = self.rig.preview("clark-20300101T000000Z-undo.db")
        self.assertEqual((status, body["message"]), (400, "No backup called clark-20300101T000000Z-undo.db is in the backups folder."))

    def test_a_control_character_never_reaches_the_screen(self):
        body = self.rig.preview("a\x1b[31mb")[1]
        self.assertNotIn("\x1b", body["message"])


class Restoring(Base):
    def test_puts_the_backup_back_keeps_what_there_was_and_the_store_opens(self):
        r = self.rig
        wanted = r.live()
        step = r.edit(3)
        status, body = r.restore(r.first, step)
        self.assertEqual(status, 200, body)
        self.assertRegex(body["message"], r"^Restored the backup from \d\d-\d\d-\d{4}\. Your data from before is kept in case you need it\.$")
        self.assertTrue(body["reload"])
        self.assertEqual(r.live(), wanted)
        kept = [p for p in r.folder.iterdir() if p.name.startswith("replaced-")]
        self.assertEqual(len(kept), 1)
        self.assertTrue(any(p.name.startswith("clark.db") for p in kept[0].iterdir()))
        self.assertTrue([p for p in r.folder.iterdir() if p.name.endswith("-restore.db")])
        open_store(r.path, onedrive_roots=[]).close()
        self.assertEqual(r.call("GET", "/api/backups")[0], 200)      # the server still answers, with no restart
        self.assertEqual(r.preview(r.first)[0], 200)

    def test_data_that_changed_since_preview_is_not_replaced(self):
        r = self.rig
        old = r.live()[1]
        r.edit()
        before = (sha(r.path), r.files())
        status, body = r.restore(r.first, old)
        self.assertEqual((status, body["code"], body["message"]), (409, "changed", "Your data changed after you looked. Look at the backup again."))
        self.assertEqual(r.restore(r.first, None)[1]["code"], "changed")
        self.assertEqual((sha(r.path), r.files()), before)

    def test_it_never_waits_for_a_change_that_is_running(self):
        r = self.rig
        step = r.live()[1]
        before = (sha(r.path), r.files())
        with changes.LOCK:                       # a stand-in step (a change, an undo or an import) holds the one writer lock
            status, body = r.restore(r.first, step)
        self.assertEqual((status, body["code"], body["message"]), (409, "busy", "Something is being saved. Wait a moment and try again."))
        self.assertEqual((sha(r.path), r.files()), before)
        self.assertTrue(changes.LOCK.acquire(blocking=False))      # and the lock was not left held by the refusal
        changes.LOCK.release()

    def test_a_change_waits_for_a_restore_and_sees_the_restored_file(self):
        r = self.rig
        step = r.edit()
        gate = threading.Event()
        real = backup.restore_path

        def slow(*a, **k):
            gate.wait(10)
            return real(*a, **k)
        result = []
        with mock.patch.object(backup, "restore_path", slow):
            t = threading.Thread(target=lambda: result.append(r.restore(r.first, step)))
            t.start()
            for _ in range(200):
                if not changes.LOCK.acquire(blocking=False):
                    break
                changes.LOCK.release()
                threading.Event().wait(0.02)
            free = changes.LOCK.acquire(blocking=False)
            if free:
                changes.LOCK.release()
            self.assertFalse(free)                                       # held for the whole restore
            gate.set()
            t.join(20)
        self.assertEqual(result[0][0], 200)
        self.assertTrue(changes.LOCK.acquire(blocking=False))
        changes.LOCK.release()

    def test_another_program_holding_the_file_stops_it_and_nothing_changes(self):
        r = self.rig
        step = r.live()[1]
        other = sqlite3.connect(str(r.path), timeout=0, isolation_level=None)
        self.addCleanup(other.close)
        other.execute("BEGIN EXCLUSIVE")
        before = r.files()
        status, body = r.restore(r.first, step)
        other.execute("ROLLBACK")
        self.assertEqual((status, body["code"]), (409, "in_use"))
        self.assertEqual(body["message"], "Another window or program has clark's data open. Close it there and try again.")
        self.assertEqual([f for f in r.files() if "replaced" in f], [])
        self.assertTrue(set(before) <= set(r.files()))

    def test_another_databases_copy_is_not_put_back(self):
        r = self.rig
        other = DemoStore()
        self.addCleanup(other.close)
        r.edit()
        with other.store.step("dashboard", "Demo User") as st:
            st.create("projects", {"code": "ZZZ", "name": "Other Programme", "health": "On track"})
        name = "clark-20300101T000000Z-undo.db"
        backup.make(other.store.path, other.dir / "b", [], "undo")
        shutil.copyfile(next((other.dir / "b").iterdir()), r.folder / name)
        before = sha(r.path)
        status, body = r.restore(name, r.live()[1])
        self.assertEqual((status, body["code"]), (400, "other_database"))
        self.assertEqual(body["message"], f"{name} is a backup of a different database, so it wasn't put back.")
        self.assertEqual(sha(r.path), before)

    def test_a_damaged_copy(self):
        r = self.rig
        bad = r.folder / "clark-20990101T000000Z-undo.db"
        bad.write_bytes(b"x" * 9000)
        before = (sha(r.path), r.files())
        status, body = r.restore(bad.name, r.live()[1])
        self.assertEqual((status, body["code"]), (400, "damaged"))
        self.assertEqual(body["message"], f"{bad.name} is damaged, so it can't be used. Choose another backup.")
        self.assertEqual((sha(r.path), r.files()), before)

    def test_a_full_disk_stops_before_anything_is_moved(self):
        r = self.rig
        step = r.edit()
        before = sha(r.path)
        with mock.patch.object(backup, "_write", side_effect=OSError(errno.ENOSPC, "No space left on device")):
            status, body = r.restore(r.first, step)
        self.assertEqual(status, 400)
        self.assertTrue(body["message"].startswith("A backup of your data must be made first, and it couldn't be. Nothing was changed."))
        self.assertIn("the disk is full", body["message"])
        self.assertEqual(sha(r.path), before)
        self.assertEqual([p for p in r.folder.iterdir() if p.name.startswith("replaced-")], [])

    def test_an_older_copy_is_tried_on_a_temporary_copy_then_restored_and_brought_up_to_date(self):
        r = self.rig
        name = Preview.older_copy(self)
        step = r.live()[1]
        status, body = r.restore(name, step)
        self.assertEqual(status, 200, body)
        con = sqlite3.connect(str(r.path))
        try:
            self.assertEqual(con.execute("SELECT v FROM meta WHERE k = 'schema_version'").fetchone()[0], str(cs.SCHEMA_VERSION))
            self.assertEqual(con.execute("SELECT name FROM projects").fetchall(), [("Example Programme",)])
        finally:
            con.close()

    def test_a_failed_trial_changes_nothing_and_leaves_the_store_open(self):
        r = self.rig
        name = Preview.older_copy(self)
        step = r.live()[1]
        before = (sha(r.path), r.files())
        with mock.patch.object(cs, "migrate", side_effect=cs.Invalid(cs.MIGRATE_FAILED)):
            status, body = r.restore(name, step)
        self.assertEqual((status, body["code"], body["message"]), (400, "migrate_failed", cs.MIGRATE_FAILED))
        self.assertEqual((sha(r.path), r.files()), before)

    def test_a_restore_that_stops_part_way_is_finished_by_the_next_start(self):
        r = self.rig
        step = r.edit()
        real = platform.replace_file

        def stop_at_the_end(source, dest, *a, **k):
            if Path(dest).name == "clark.db":
                raise OSError(errno.EIO, "Input/output error")
            return real(source, dest, *a, **k)
        with mock.patch.object(platform, "replace_file", stop_at_the_end):
            status, body = r.restore(r.first, step)
        self.assertEqual((status, body["code"]), (500, "unfinished"))
        self.assertRegex(body["message"], r"^The restore stopped part-way \(.*\)\. Your database is safe in .*replaced-.*\. Start clark again and it will finish putting .* back\.$")
        self.assertFalse(r.path.exists())
        open_store(r.path, onedrive_roots=[]).close()            # the next start finishes it
        self.assertEqual(r.live()[0], 0)

    def test_a_restore_leaves_no_working_files(self):
        r = self.rig
        r.restore(r.first, r.live()[1])
        self.assertFalse([p.name for p in r.demo.dir.iterdir() if p.name.endswith((".restoring", ".restoring.json"))])


class WhoMayCall(Base):
    ROUTES = (("GET", "/api/backups"), ("POST", "/api/backups/preview"), ("POST", "/api/backups/restore"))

    def body(self, method):
        return {"name": self.rig.first, "last_step": 1} if method == "POST" else None

    def test_every_backup_route_is_in_the_tables_and_behind_the_one_check(self):
        self.assertEqual({p for m, p in self.ROUTES if m == "GET"} - set(sv.GET_ROUTES), set())
        self.assertEqual({p for m, p in self.ROUTES if m == "POST"} - set(sv.POST_ROUTES), set())
        before = (sha(self.rig.path), self.rig.files())
        for method, path in self.ROUTES:
            with self.subTest(path=path):
                r = self.rig
                self.assertEqual(r.call(method, path, self.body(method), token=False)[0], 403, "no token")
                self.assertEqual(r.call(method, path, self.body(method), token="wrong")[1]["code"], "stale")
                for origin in ("https://example.org", "http://localhost:1", "http://127.0.0.1.evil.example", "null"):
                    self.assertEqual(r.call(method, path, self.body(method), origin=origin)[0], 403, origin)
                self.assertEqual(r.call(method, path, self.body(method), host="evil.example")[0], 403, "foreign Host")
        self.assertEqual((sha(self.rig.path), self.rig.files()), before)

    def test_text_plain_and_a_large_body_are_refused(self):
        r = self.rig
        for path in ("/api/backups/preview", "/api/backups/restore"):
            self.assertEqual(r.call("POST", path, {"name": r.first}, ctype="text/plain")[0], 415)
            self.assertEqual(r.call("POST", path, raw=b'{"name": "' + b"a" * 2000 + b'"}')[0], 400)
            self.assertEqual(r.call("POST", path, raw=b"{not json")[0], 400)
        
    def test_the_server_module_names_no_store(self):
        text = (Path(sv.__file__)).read_text(encoding="utf-8")
        self.assertNotIn("import store", text)
        route = text.split("def safety_route")[1].split("GET_ROUTES")[0]
        self.assertNotIn("sqlite", route + text.lower().split("import")[0])
        self.assertEqual([w for w in ("clark_store", "backup.", "changes.") if w in route.split('"""')[2]], [])     # the route's code (not its docstring) names none


class WordsAndJargon(Base):
    def test_no_sentence_this_module_says_has_a_technical_word_or_starts_with_the_product_name(self):
        for key, text in safety.MESSAGES.items():
            with self.subTest(key=key):
                low = text.lower()
                self.assertFalse([w for w in JARGON if w in low], text)
                self.assertFalse(text.startswith(("clark", "Clark")), text)
                self.assertNotIn("python3", low)
        for text in (settings.BACKUPS_KEPT_LABEL, settings.BACKUPS_KEPT_HELP, sv.MESSAGES["no_backups"], *safety.KIND_LABELS.values()):
            self.assertFalse([w for w in JARGON if w in text.lower()], text)
            self.assertFalse(text.startswith(("clark", "Clark")), text)

    def test_the_replies_the_attacks_get_have_no_technical_word(self):
        r = self.rig
        replies = [r.preview("../x"), r.preview(r.first + "\n"), r.restore("nope", 1)]
        bad = r.folder / "clark-20990101T000000Z-undo.db"
        bad.write_bytes(b"x" * 3000)
        replies += [r.preview(bad.name), r.restore(bad.name, r.live()[1])]
        for _, body in replies:
            low = body["message"].lower()
            self.assertFalse([w for w in JARGON if w in low], body["message"])
            self.assertNotIn("python3", low)


class NumberKept(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.data = self.demo.dir
        self.folder = self.demo.store.backups_dir
        for p in self.folder.iterdir():
            p.unlink()

    def plant(self, n, tag="daily"):
        source = self.data / "source.db"
        shutil.copyfile(backup.take(self.demo.store, "restore"), source)
        for p in self.folder.iterdir():
            p.unlink()
        for i in range(n):
            p = self.folder / f"clark-2030010{1 + i // 20}T0000{i % 20:02d}Z-{tag}.db"
            shutil.copyfile(source, p)
            os.utime(p, (1_000_000_000 + i, 1_000_000_000 + i))

    def left(self):
        return len([p for p in self.folder.iterdir() if p.name.endswith("-daily.db")])

    def test_the_default_is_14_and_equals_backup_keep(self):
        self.assertEqual((settings.backups_kept(self.data), backup.KEEP, settings.BACKUPS_KEPT_DEFAULT), (14, 14, 14))

    def test_changing_the_setting_changes_what_prune_keeps(self):
        self.plant(18)
        backup.prune(self.folder)
        self.assertEqual(self.left(), 14)                 # no file: the default
        self.plant(18)
        settings.set_backups_kept(self.data, 5)
        backup.prune(self.folder)
        self.assertEqual(self.left(), 5)
        self.plant(18)
        settings.set_backups_kept(self.data, 9)
        backup.prune(self.folder)
        self.assertEqual(self.left(), 9)
        self.plant(18)
        backup.prune(self.folder, 3)                      # an explicit number still wins
        self.assertEqual(self.left(), 3)

    def test_a_new_copy_prunes_by_the_setting_and_the_newest_is_never_removed(self):
        self.plant(6)
        settings.set_backups_kept(self.data, 1)
        newest = backup.take(self.demo.store, "daily")
        self.assertTrue(newest.exists())
        self.assertEqual(self.left(), 1)

    def test_the_list_says_how_many_are_kept(self):
        settings.set_backups_kept(self.data, 21)
        s = safety.Safety(self.demo.store.path, [])
        self.plant(2)
        self.assertEqual(s.listing()[1]["keep"], 21)

    def test_a_bad_value_or_file_is_the_default_and_never_an_error(self):
        path = self.data / "settings.json"
        for text in ('{"backups_kept": 0}', '{"backups_kept": 366}', '{"backups_kept": true}', '{"backups_kept": "7"}',
                     '{"backups_kept": 7.5}', '{"backups_kept": null}', "[1, 2]", "not json", "", '{"backups_kept": -3}',
                     '{"backups_kept": 1e400}', "[" * 100000):
            with self.subTest(text=text[:30]):
                path.write_text(text, encoding="utf-8")
                self.assertEqual(settings.backups_kept(self.data), 14)
        path.write_text('{"backups_kept": 365}', encoding="utf-8")
        self.assertEqual(settings.backups_kept(self.data), 365)
        path.write_text('{"backups_kept": 1}', encoding="utf-8")
        self.assertEqual(settings.backups_kept(self.data), 1)
        path.unlink()
        os.symlink(self.data / "elsewhere.json", path)
        self.assertEqual(settings.backups_kept(self.data), 14)
        self.assertEqual(settings.backups_kept(self.data / "no-such-folder"), 14)

    def test_saving_keeps_the_other_settings_and_refuses_what_is_not_a_number_in_range(self):
        (self.data / "settings.json").write_text('{"other": {"a": 1}}', encoding="utf-8")
        settings.set_backups_kept(self.data, 30)
        self.assertEqual(json.loads((self.data / "settings.json").read_text(encoding="utf-8")), {"other": {"a": 1}, "backups_kept": 30})
        for bad in (0, 366, True, "5", 2.5, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError) as ctx:
                settings.set_backups_kept(self.data, bad)
            self.assertEqual(str(ctx.exception), "Choose a whole number of backups from 1 to 365.")
        self.assertEqual(settings.backups_kept(self.data), 30)


class TheReviewFixes(Base):
    """The code read of #185: plain refusals, working folders in the backups folder, one Preview at a time, settings never lost."""

    def test_no_refusal_the_card_shows_holds_a_file_name_or_a_command(self):
        s = self.rig.safety
        texts = [
            "Something is wrong. Nothing was changed. To put x.db back instead, first delete the file clark.db.restoring.json in /data, then run restore again.",
            "An earlier restore stopped part-way, and clark.db is missing. Nothing was changed. Start clark first: it will finish. Then run restore again if you still want x.db.",
            "x.db is a backup of a different database. To open it anyway, copy it, rename it clark.db, then start clark where FOLDER is the new folder:\n    python3 -m clark --data FOLDER",
            "Some other text that mentions clark.db.restoring somewhere.",
        ]
        for text in texts:
            with self.subTest(text=text[:40]):
                status, body = s.refusal(cs.Invalid(text), "x.db")
                low = body["message"].lower()
                for bad in ("delete the file", "python3", "--data", ".json", ".restoring", "clark.db", "run restore", "restore again"):
                    self.assertNotIn(bad, low)
                self.assertTrue("Nothing was changed" in body["message"] or "wasn't put back" in body["message"])
        self.assertEqual(s.refusal(cs.Invalid(texts[1]))[1]["message"], safety.MESSAGES["unfinished"])

    def test_a_half_done_restore_note_is_met_with_a_plain_sentence_through_the_route(self):
        r = self.rig
        r.path.unlink()
        (r.path.parent / (r.path.name + backup.MARKER)).write_text("{}", encoding="utf-8")
        status, body = r.restore(r.first, None)
        self.assertIn(status, (400, 500))
        for bad in ("delete the file", "run restore", ".json", "clark.db", "python3"):
            self.assertNotIn(bad, body["message"])

    def test_working_folders_are_in_the_backups_folder_never_the_system_temp_folder(self):
        r = self.rig
        made = []
        real = tempfile.mkdtemp
        with mock.patch.object(tempfile, "mkdtemp", side_effect=lambda **kw: made.append(real(**kw)) or made[-1]):
            self.assertEqual(r.preview(r.first)[0], 200)
            self.assertEqual(r.restore(r.first, r.live()[1])[0], 200)
        self.assertEqual(len(made), 2)
        self.assertEqual({Path(p).parent for p in made}, {r.folder})

    def test_stale_working_folders_are_removed_when_clark_starts(self):
        r = self.rig
        stale = [r.folder / "clark-preview-abc", r.folder / "clark-restore-xyz"]
        for d in stale:
            d.mkdir()
            (d / "copy.db").write_bytes(b"x")
        safety.Safety(r.path, [])
        self.assertEqual([d for d in stale if d.exists()], [])
        self.assertTrue((r.folder / r.first).exists())

    def test_a_second_preview_while_one_runs_says_busy_and_waits_for_nothing(self):
        r = self.rig
        self.assertTrue(r.safety._preview_lock.acquire(blocking=False))
        try:
            status, body = r.preview(r.first)
        finally:
            r.safety._preview_lock.release()
        self.assertEqual((status, body["code"]), (409, "busy_preview"))
        self.assertEqual(r.preview(r.first)[0], 200)             # and it is free again afterwards

    def test_saving_never_replaces_a_settings_file_it_cannot_read(self):
        data = Path(tempfile.mkdtemp(prefix="clark-set-"))
        self.addCleanup(shutil.rmtree, data, True)
        for content in ("{not json", "[1, 2]", '{"other": "' + "x" * 70000 + '"}'):
            with self.subTest(size=len(content)):
                (data / "settings.json").write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError) as ctx:
                    settings.set_backups_kept(data, 5)
                self.assertEqual((data / "settings.json").read_text(encoding="utf-8"), content)
                self.assertNotIn("settings.json", str(ctx.exception))
        (data / "settings.json").unlink()
        settings.set_backups_kept(data, 5)                       # no file at all is fine
        self.assertEqual(settings.backups_kept(data), 5)

    def test_keeping_one_still_keeps_the_last_two_copies_made_before_a_restore(self):
        r = self.rig
        source = r.folder / r.first
        names = []
        for i in range(4):
            p = r.folder / f"clark-2030010{i + 1}T000000Z-restore.db"
            shutil.copyfile(source, p)
            os.utime(p, (1_000_000_000 + i, 1_000_000_000 + i))
            names.append(p.name)
        backup.prune(r.folder, 1)
        self.assertEqual([n for n in names if (r.folder / n).exists()], names[-2:])


class TheStaleDocstring(unittest.TestCase):
    def test_restore_path_no_longer_says_an_older_copy_is_refused(self):
        doc = " ".join(backup.restore_path.__doc__.split())
        self.assertNotIn("older-schema copy, or one of another database, is refused", doc)
        self.assertIn("an older-schema copy is put back", doc)


if __name__ == "__main__":
    unittest.main()

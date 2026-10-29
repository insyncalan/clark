"""The update helper (#109, step 6): src/clark/update_helper.py.

Builds a fake app folder, a staged new version and a data folder in a temporary place, and runs the helper with its platform
seams faked. A fault is injected at EVERY step point (before and after each step, including each single rename and each step of
the way back), the helper is killed (SIGKILL, in a real child process) at every step point, and --finish is run to show that the
old version always comes back, byte for byte, and that running it again changes nothing. No network, no Chrome, no real server.
Run: python3 dev/run_tests.py test_update_helper
"""
import ast
import hashlib
import http.server
import json
import os
import re
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import unittest
from pathlib import Path

from _paths import ROOT, SRC
from clark import platform, update_helper as h, updates

STAMP = "20261029T120000Z"
HOME_WORDS = re.compile(r"\b(zip|manifest|sha|vault|tracker)\b", re.I)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(base, rel, data, mode=0o644):
    path = Path(base) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, mode)


OLD = {
    "README.md": b"old readme\n",
    "clark/__init__.py": b"# stand-in\n",
    "src/clark/__init__.py": b'__version__ = "0.3.0"\n',
    "src/clark/mod.py": b"VALUE = 1\n",
    "vendor/lib/a.py": b"A = 1\n",
    "oldlib/x.py": b"X = 1\n",
    "legacy.txt": b"legacy\n",
    "clark.command": b"#!/bin/sh\necho old\n",
}
NEW = {
    "README.md": b"new readme\n",
    "clark/__init__.py": b"# stand-in\n",
    "src/clark/__init__.py": b'__version__ = "0.3.1"\n',
    "src/clark/mod.py": b"VALUE = 2\n",
    "src/clark/newmod.py": b"NEW = 1\n",
    "vendor/lib/a.py": b"A = 1\n",
    "extra.txt": b"extra\n",
    "clark.command": b"#!/bin/sh\necho new\n",
}
EXEC = {"clark.command"}
MINE = {"notes.txt": b"my notes\n", "src/clark/mine.py": b"MINE = 1\n", "oldlib/mine.txt": b"mine\n"}


def manifest(version, files, schema=2):
    return {"product": "clark", "version": version, "system": "mac", "released": "2026-10-29", "notes": "", "schema_version": schema,
            "min_from": "0.0.0", "files": {r: {"sha256": sha(d), "size": len(d), "mode": "755" if r in EXEC else "644"}
                                          for r, d in files.items()}}


class Fixture:
    """An installed 0.3.0 with the person's own files, a staged 0.3.1, and a data folder with a planted file."""

    def __init__(self, root, schema=2):
        self.root = Path(root)
        self.app, self.data = self.root / "clark-0.3.0", self.root / "data"
        for rel, data in OLD.items():
            put(self.app, rel, data, 0o755 if rel in EXEC else 0o644)
        put(self.app, h.MANIFEST, json.dumps(manifest("0.3.0", OLD)).encode())
        for rel, data in MINE.items():
            put(self.app, rel, data)
        self.staging = self.app / (h.STAGING_PREFIX + STAMP)
        for rel, data in NEW.items():
            put(self.staging, rel, data, 0o755 if rel in EXEC else 0o644)     # as the server writes them
        put(self.staging, h.MANIFEST, json.dumps(manifest("0.3.1", NEW, schema)).encode())
        put(self.data, "projects/p1.json", b'{"fictional": true}\n')
        put(self.data, "clark.db", b"database bytes")
        (self.data / h.UPDATES).mkdir()
        (self.app / "emptydir").mkdir()
        self.before = snapshot(self.app)
        self.data_before = snapshot(self.data)

    def begin(self, check=True, **kw):
        return h.begin(self.data, self.app, self.staging, STAMP, "0.3.0", "0.3.1", 2, 4321, 8765, "X-Clark-Mark", "mark-1",
                       backup_dir=str(self.data / "updates" / "backup"), check=check, **kw)


def snapshot(base):
    """Every file (bytes, mode) and folder under base, except clark's own .clark-* and helper-* folders, as a dict that compares."""
    out = {}
    for folder, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith((h.STAGING_PREFIX, h.OLD_PREFIX, h.HELPER_PREFIX))]
        for n in names + dirs:
            p = Path(folder, n)
            rel = p.relative_to(base).as_posix()
            if p.is_dir():
                out[rel + "/"] = None
            elif rel not in (f"updates/{h.LOG_NAME}", f"updates/{h.RESULT_NAME}", f"updates/{h.MARKER_NAME}"):
                out[rel] = (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
    return out


class FakeSeams(h.Seams):
    """No real processes, ports or waiting. Records what the helper asked for."""

    def __init__(self, **kw):
        super().__init__(sleep=lambda s: None, clock=self.tick)
        self.now = 0.0
        self.started, self.stopped = [], []
        self.gone = True
        self.__dict__.update(kw)

    def tick(self):
        self.now += 0.001
        return self.now

    def process_gone(self, pid):
        return self.gone

    def port_free(self, port):
        return self.gone

    def start_server(self, app_dir, data_dir, port, log_path):
        self.started.append((str(app_dir), port))
        return 4242

    def stop_process(self, pid):
        self.stopped.append(pid)

    def server_answers(self, port, header, mark, timeout=2):
        return True

    def check_install(self, app_dir):
        pass


class Once:
    """Raises once at each named point (a stand-in for any failure there)."""

    def __init__(self, *names):
        self.names = set(names)

    def __call__(self, name):
        if name in self.names:
            self.names.discard(name)
            raise RuntimeError("injected fault at " + name)


def run_with(fx, fault=None, seams=None, trace=None, **kw):
    fx.begin()
    return h.run_update(h.marker_path(fx.data), seams or FakeSeams(), fault, trace, **kw)


def points():
    """Every step point of an update that works, in order, from a dry run (names with + are the moments after a step's action)."""
    with tempfile.TemporaryDirectory() as t:
        trace = []
        code, _ = run_with(Fixture(t), trace=trace)
        assert code == h.OK
        return trace


def rollback_points():
    with tempfile.TemporaryDirectory() as t:
        trace = []
        code, _ = run_with(Fixture(t), Once("carry"), trace=trace)
        assert code == h.ROLLED_BACK
        return [p for p in trace if p.startswith("rollback:")]


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s]


class PlainWordsMixin:
    def assertPlain(self, text):
        self.assertTrue(text and text.strip())
        for s in sentences(text):
            self.assertFalse(s.lower().startswith("clark"), s)
        self.assertIsNone(HOME_WORDS.search(text), text)
        self.assertNotIn("Traceback", text)
        self.assertNotIn("{", text)


class HappyPathTest(unittest.TestCase, PlainWordsMixin):
    def test_installs_in_place_keeps_the_old_set_aside_and_keeps_the_persons_files(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams()
            code, result = run_with(fx, seams=seams)
            self.assertEqual((code, result["status"]), (h.OK, "installed"))
            self.assertEqual(result["message"], "Version 0.3.1 is installed. One moment while clark restarts.")
            for rel, data in NEW.items():
                self.assertEqual((fx.app / rel).read_bytes(), data, rel)
            self.assertTrue(os.access(fx.app / "clark.command", os.X_OK))
            self.assertEqual(stat.S_IMODE((fx.app / "src/clark/mod.py").stat().st_mode), 0o644)
            for rel, data in MINE.items():                                   # everything the person added is still there
                self.assertEqual((fx.app / rel).read_bytes(), data, rel)
            self.assertFalse((fx.app / "legacy.txt").exists())
            self.assertFalse((fx.app / "oldlib/x.py").exists())              # shipped before, not now: set aside, not deleted
            old = fx.app / (h.OLD_PREFIX + STAMP)
            self.assertEqual((old / "legacy.txt").read_bytes(), OLD["legacy.txt"])
            self.assertEqual((old / "src/clark/mod.py").read_bytes(), OLD["src/clark/mod.py"])
            self.assertEqual((old / "src/clark/mine.py").read_bytes(), MINE["src/clark/mine.py"])
            self.assertFalse(fx.staging.exists())
            self.assertFalse(h.marker_path(fx.data).exists())
            self.assertEqual(snapshot(fx.data)["projects/p1.json"], fx.data_before["projects/p1.json"])
            self.assertEqual(seams.started, [(str(fx.app), 8765)])
            self.assertEqual(h.read_result(fx.data)["status"], "installed")

    def test_the_marker_is_written_first_and_holds_what_a_restart_needs(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            path = fx.begin()
            m = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual((m["phase"], m["stamp"], m["from"], m["to"], m["server_pid"], m["port"]),
                             ("staged", STAMP, "0.3.0", "0.3.1", 4321, 8765))
            self.assertEqual([e["name"] for e in m["entries"]],
                             ["src", "vendor", "README.md", "extra.txt", "legacy.txt", "oldlib", "clark", "clark.command", h.MANIFEST])
            self.assertEqual(m["before"]["notes.txt"] if "notes.txt" in m["before"] else None, None)   # not an entry: never touched
            self.assertIn("src/clark/mine.py", m["before"])
            self.assertEqual(fx.before, snapshot(fx.app))                    # begin changed nothing in the app folder

    def test_the_stand_in_and_launcher_are_swapped_last_and_the_record_after_them(self):
        names = [p for p in points() if p.startswith("swap:new:") and not p.endswith("+")]
        self.assertEqual([n.split(":")[2] for n in names][-3:], ["clark", "clark.command", h.MANIFEST])
        self.assertEqual(names[0], "swap:new:src")

    def test_cleanup_old_removes_only_clarks_own_folders(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            run_with(fx)
            (fx.app / "my-folder").mkdir()
            put(fx.app, "my-folder/keep.txt", b"keep")
            self.assertEqual(h.cleanup_old(fx.app), [h.OLD_PREFIX + STAMP])
            self.assertTrue((fx.app / "my-folder/keep.txt").exists())
            self.assertTrue((fx.app / "src/clark/mine.py").exists())
            self.assertEqual(h.cleanup_old(fx.app), [])


class BeginRefusalsTest(unittest.TestCase, PlainWordsMixin):
    def refused(self, fx, key):
        with self.assertRaises(updates.UpdateError) as cm:
            fx.begin()
        self.assertEqual(cm.exception.key, key)
        self.assertEqual(cm.exception.message, updates.MESSAGES[key])
        self.assertPlain(cm.exception.message)
        self.assertFalse(h.marker_path(fx.data).exists())                    # nothing was written
        self.assertEqual(fx.before, snapshot(fx.app))

    def test_a_folder_holding_git_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            (fx.app / ".git").mkdir()
            fx.before = snapshot(fx.app)
            self.refused(fx, "git")

    def test_a_link_in_the_app_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            os.symlink(fx.root, fx.app / "src" / "shortcut")
            fx.before = snapshot(fx.app)
            self.refused(fx, "link")

    def test_an_update_that_changes_the_data_layout_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t, schema=3)
            self.refused(fx, "layout")

    def test_a_folder_with_no_record_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            (fx.app / h.MANIFEST).unlink()
            fx.before = snapshot(fx.app)
            self.refused(fx, "norecord")


class FaultEveryStepTest(unittest.TestCase, PlainWordsMixin):
    def test_the_dry_run_has_the_named_steps(self):
        p = points()
        for want in ("ready", "wait_server", "verify_staged", "prepare", "swap:old:src", "swap:old:src+", "swap:new:src",
                     "swap:new:clark.command+", "carry", "verify_installed", "health", "start_new", "start_new+", "commit"):
            self.assertIn(want, p)
        self.assertGreaterEqual(len(p), 40)

    def test_a_fault_at_every_step_point_puts_back_the_old_tree_byte_for_byte(self):
        for point in points():
            with self.subTest(point=point), tempfile.TemporaryDirectory() as t:
                fx = Fixture(t)
                seams = FakeSeams()
                code, result = run_with(fx, Once(point), seams)
                self.assertEqual((code, result["status"]), (h.ROLLED_BACK, "rolled_back"), point)
                self.assertEqual(snapshot(fx.app), fx.before, point)
                self.assertEqual(snapshot(fx.data), fx.data_before, point)
                self.assertFalse(h.marker_path(fx.data).exists())
                self.assertEqual([n for n in os.listdir(fx.app) if n.startswith((h.STAGING_PREFIX, h.OLD_PREFIX, h.HELPER_PREFIX))], [])
                self.assertEqual(len(seams.started), 2 if point in ("start_new+", "commit") else 1, point)   # the old one again (and the new one, if it got that far)
                self.assertPlain(result["message"])
                step = point.rstrip("+")
                log = (h.updates_dir(fx.data) / h.LOG_NAME).read_text(encoding="utf-8")
                self.assertRegex(log, rf" {re.escape(step)} failed ", point)   # one line names the step that failed

    def test_a_server_started_by_a_stopped_update_is_stopped_again(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams()
            run_with(fx, Once("commit"), seams)
            self.assertEqual(seams.stopped, [4242])

    def test_the_new_version_not_answering_puts_the_old_back_with_a_plain_line(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams()
            seams.server_answers = lambda *a, **k: False
            code, result = run_with(fx, None, seams)
            self.assertEqual(code, h.ROLLED_BACK)
            self.assertEqual(snapshot(fx.app), fx.before)
            self.assertIn("The new version didn't start.", result["message"])
            self.assertIn("version 0.3.0 has been restored", result["message"])
            self.assertPlain(result["message"])

    def test_a_failed_health_check_puts_the_old_back(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams()

            def bad(app):
                raise h.StepError("damaged", "a module does not import")
            seams.check_install = bad
            code, result = run_with(fx, None, seams)
            self.assertEqual((code, snapshot(fx.app)), (h.ROLLED_BACK, fx.before))
            self.assertEqual(result["message"], h.MESSAGES["damaged"])

    def test_a_staged_file_that_was_changed_stops_before_anything_is_swapped(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            fx.begin()
            put(fx.staging, "src/clark/mod.py", b"VALUE = 99\n")
            seams = FakeSeams()
            code, result = h.run_update(h.marker_path(fx.data), seams)
            self.assertEqual((code, result["message"]), (h.ROLLED_BACK, h.MESSAGES["damaged"]))
            self.assertEqual(snapshot(fx.app), fx.before)
            self.assertNotIn("swap:old:src", (h.updates_dir(fx.data) / h.LOG_NAME).read_text(encoding="utf-8"))

    def test_a_link_in_the_staged_files_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            fx.begin()
            os.symlink(fx.root, fx.staging / "src" / "clark" / "link")
            code, result = h.run_update(h.marker_path(fx.data), FakeSeams())
            self.assertEqual((code, result["message"]), (h.ROLLED_BACK, h.MESSAGES["unsafe"]))
            self.assertEqual(snapshot(fx.app), fx.before)

    def test_not_enough_room_changes_nothing_and_says_so(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams()
            seams.free_space = lambda path: 10
            code, result = run_with(fx, None, seams)
            self.assertEqual((code, result["message"]), (h.ROLLED_BACK, h.MESSAGES["space"]))
            self.assertEqual(snapshot(fx.app), fx.before)

    def test_the_old_server_not_closing_in_time_changes_nothing_and_restarts_the_old(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams(gone=False)
            seams.now = 0.0
            seams.tick = lambda: setattr(seams, "now", seams.now + 10) or seams.now
            seams.clock = seams.tick
            code, result = run_with(fx, None, seams)
            self.assertEqual((code, result["message"]), (h.ROLLED_BACK, h.MESSAGES["close"]))
            self.assertEqual(snapshot(fx.app), fx.before)
            self.assertEqual(len(seams.started), 1)

    def test_a_file_held_by_another_program_is_retried_then_succeeds(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams()
            fails = {"n": 0}

            def rename(source, dest):
                if Path(dest) == fx.app / "src" and fails["n"] < 4:
                    fails["n"] += 1
                    raise PermissionError(13, "in use")
                os.rename(source, dest)
            seams.rename = rename
            code, result = run_with(fx, None, seams)
            self.assertEqual((code, result["status"], fails["n"]), (h.OK, "installed", 4))

    def test_a_file_that_stays_held_puts_the_old_back_with_the_held_line(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            seams = FakeSeams()

            def rename(source, dest):
                if Path(source) == fx.staging / "clark":
                    raise PermissionError(13, "in use")
                os.rename(source, dest)
            seams.rename = rename
            code, result = run_with(fx, None, seams)
            self.assertEqual((code, result["message"]), (h.ROLLED_BACK, h.MESSAGES["held"]))
            self.assertEqual(snapshot(fx.app), fx.before)

    def test_the_retry_rule_stays_like_the_platform_modules(self):
        self.assertEqual((h.REPLACE_ATTEMPTS, h.REPLACE_FIRST_WAIT, h.LOCKED),
                         (platform.REPLACE_ATTEMPTS, platform.REPLACE_FIRST_WAIT, platform.LOCKED))
        self.assertEqual(h.LOG_LIMIT, platform.LOG_LIMIT)
        waits = []
        seams = FakeSeams()
        seams.sleep = waits.append
        seams.rename = lambda a, b: (_ for _ in ()).throw(PermissionError(13, "x"))
        with self.assertRaises(PermissionError):
            h.rename_with_retry("a", "b", seams)
        self.assertEqual(waits, [0.05, 0.1, 0.2, 0.4])


class FaultInTheWayBackTest(unittest.TestCase, PlainWordsMixin):
    def test_a_fault_in_each_step_of_the_way_back_keeps_the_marker_and_finish_completes_it(self):
        pts = rollback_points()
        self.assertTrue(any(p.startswith("rollback:swap") is False for p in pts))
        self.assertGreaterEqual(len(pts), 12)
        for point in pts:
            with self.subTest(point=point), tempfile.TemporaryDirectory() as t:
                fx = Fixture(t)
                code, result = run_with(fx, Once("carry", point))
                self.assertEqual((code, result["status"]), (h.NOT_RESTORED, "not_restored"), point)
                self.assertTrue(h.marker_path(fx.data).exists())              # kept so the next start tries again
                self.assertPlain(result["message"])
                self.assertIn("Open clark again to finish putting it back.", result["message"])
                self.assertIn("update.log", result["message"])
                code, result = h.finish(fx.data, FakeSeams())
                self.assertEqual((code, result["status"]), (h.ROLLED_BACK, "rolled_back"), point)
                self.assertEqual(snapshot(fx.app), fx.before, point)
                self.assertEqual(snapshot(fx.data), fx.data_before)
                self.assertFalse(h.marker_path(fx.data).exists())


class RollbackIsCheckedTest(unittest.TestCase):
    def test_a_way_back_that_does_not_match_the_old_files_is_not_reported_as_done(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            once = Once("carry")

            def fault(name):
                once(name)
                if name == "rollback:verify":
                    (fx.app / "README.md").write_bytes(b"changed behind its back\n")
            code, result = run_with(fx, fault)
            self.assertEqual((code, result["status"]), (h.NOT_RESTORED, "not_restored"))
            self.assertTrue(h.marker_path(fx.data).exists())


KILL_SCRIPT = textwrap.dedent('''
    import os, signal, sys
    sys.path.insert(0, sys.argv[1])
    from clark import update_helper as h

    class S(h.Seams):
        def process_gone(self, pid): return True
        def port_free(self, port): return True
        def start_server(self, *a): return 4242
        def stop_process(self, pid): pass
        def server_answers(self, *a, **k): return True
        def check_install(self, app): pass

    marker, kill, boom = sys.argv[2], sys.argv[3], sys.argv[4]
    raised = []

    def fault(name):
        if name == boom and not raised:
            raised.append(1)
            raise RuntimeError("injected")
        if name == kill:
            os.kill(os.getpid(), signal.SIGKILL)

    sys.exit(h.run_update(marker, S(), fault)[0])
''')


class KillTest(unittest.TestCase):
    """The helper is killed outright (SIGKILL) at each step point, in a real child process, and --finish is run."""

    def kill_at(self, point, boom="-"):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            script = Path(t) / "kill_helper.py"
            script.write_text(KILL_SCRIPT, encoding="utf-8")
            fx.begin()
            done = subprocess.run([sys.executable, "-I", str(script), str(SRC), str(h.marker_path(fx.data)), point, boom],
                                  capture_output=True, timeout=60)
            self.assertEqual(done.returncode, -signal.SIGKILL, (point, done.stderr[-300:]))
            code, result = h.finish(fx.data, FakeSeams())
            self.assertEqual((code, result["status"]), (h.ROLLED_BACK, "rolled_back"), point)
            tree = snapshot(fx.app)
            self.assertTrue(tree == fx.before, f"half-installed after a kill at {point}")      # old, never half
            self.assertEqual(snapshot(fx.data), fx.data_before, point)
            self.assertFalse(h.marker_path(fx.data).exists())
            self.assertEqual([n for n in os.listdir(fx.app) if n.startswith((h.STAGING_PREFIX, h.OLD_PREFIX, h.HELPER_PREFIX))], [])
            self.assertEqual(h.finish(fx.data, FakeSeams()), (h.OK, None))               # again: nothing more to do
            self.assertEqual(snapshot(fx.app), fx.before)

    def test_killed_at_every_step_point_finish_leaves_the_old_version(self):
        for point in points():
            with self.subTest(point=point):
                self.kill_at(point)

    def test_killed_during_the_way_back_finish_still_leaves_the_old_version(self):
        for point in rollback_points():
            with self.subTest(point=point):
                self.kill_at(point, boom="carry")


class FinishTest(unittest.TestCase, PlainWordsMixin):
    def test_nothing_to_finish_changes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            self.assertEqual(h.finish(fx.data, FakeSeams()), (h.OK, None))
            self.assertEqual(snapshot(fx.app), fx.before)

    def test_finish_after_a_stop_says_so_in_plain_words_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            run_with(fx, Once("health"), None)           # a clean rollback leaves no marker: build a stopped update instead
            fx2 = Fixture(tempfile.mkdtemp(dir=t))
            fx2.begin()
            seams = FakeSeams()
            code, result = h.finish(fx2.data, seams)
            self.assertEqual((code, result["status"]), (h.ROLLED_BACK, "rolled_back"))
            self.assertEqual(result["message"], h.MESSAGES["finished"])
            self.assertPlain(result["message"])
            self.assertEqual(seams.started, [])                               # the launcher starts the server, not --finish
            self.assertEqual(h.finish(fx2.data, seams), (h.OK, None))
            self.assertEqual(h.read_result(fx2.data)["status"], "rolled_back")
            self.assertEqual(snapshot(fx2.app), fx2.before)

    def test_finish_does_not_go_forward_even_when_every_step_had_finished(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            run_with(fx, Once("commit"))
            self.assertEqual(snapshot(fx.app), fx.before)

    def test_finish_stops_while_the_helper_is_still_running(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            path = fx.begin()
            m = json.loads(path.read_text(encoding="utf-8"))
            m["helper_pid"] = 99999
            path.write_text(json.dumps(m), encoding="utf-8")
            seams = FakeSeams(gone=False)
            code, result = h.finish(fx.data, seams)
            self.assertEqual((code, result["message"]), (h.BUSY, h.MESSAGES["busy"]))
            self.assertTrue(path.exists())
            self.assertPlain(result["message"])

    def test_the_command_line(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            said = []
            self.assertEqual(h.main(["--finish", "--data", str(fx.data)], FakeSeams(), said.append), h.OK)
            self.assertEqual(said, [h.MESSAGES["nothing"]])
            fx.begin()
            said.clear()
            self.assertEqual(h.main(["--marker", str(h.marker_path(fx.data))], FakeSeams(), said.append), h.OK)
            self.assertEqual(said, ["Version 0.3.1 is installed. One moment while clark restarts."])


class PersonsFilesTest(unittest.TestCase):
    def test_files_the_person_added_survive_install_and_every_rollback(self):
        for point in ["commit", "carry", "swap:new:clark", "swap:old:oldlib+"]:
            with self.subTest(point=point), tempfile.TemporaryDirectory() as t:
                fx = Fixture(t)
                run_with(fx, Once(point))
                for rel, data in MINE.items():
                    self.assertEqual((fx.app / rel).read_bytes(), data, rel)
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            run_with(fx)
            for rel, data in MINE.items():
                self.assertEqual((fx.app / rel).read_bytes(), data, rel)


class LogTest(unittest.TestCase):
    def test_one_line_per_step_paths_with_a_tilde_and_no_file_contents(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            trace = []
            run_with(fx, trace=trace, home=t)
            lines = (h.updates_dir(fx.data) / h.LOG_NAME).read_text(encoding="utf-8").splitlines()
            self.assertEqual([ln.split()[3] for ln in lines], [n for n in trace if not n.endswith("+")])
            self.assertTrue(all(ln.split()[4] == "ok" and ln.split()[2] == "0.3.0->0.3.1" and ln.split()[1] == STAMP for ln in lines))
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)

            def boom(name):
                if name == "health":
                    raise RuntimeError(f"cannot read {t}/clark-0.3.0/src and then {os.path.expanduser('~')}/x")
            run_with(fx, boom, home=t)
            text = (h.updates_dir(fx.data) / h.LOG_NAME).read_text(encoding="utf-8")
            self.assertNotIn(t, text)
            self.assertIn("~/clark-0.3.0/src", text)
            self.assertNotIn("VALUE", text)

    def test_the_log_is_started_again_past_one_megabyte(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            log = h.updates_dir(fx.data) / h.LOG_NAME
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_bytes(b"x" * (h.LOG_LIMIT + 1))
            run_with(fx)
            self.assertLess(log.stat().st_size, 10000)
            self.assertNotIn("xxxx", log.read_text(encoding="utf-8"))


class PlainWordsTest(unittest.TestCase, PlainWordsMixin):
    def test_every_message_is_plain_and_none_starts_with_the_product_name(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            fx.begin()
            run = h.Run(h.marker_path(fx.data), home=t)
            for key in h.MESSAGES:
                text = run.message(key, why="Try again.")
                self.assertPlain(text)
            for key in ("close", "held", "space", "unsafe", "damaged", "no_start", "generic"):
                self.assertPlain(h.explain(run, key))

    def test_each_failure_message_says_what_to_do_next(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            fx.begin()
            run = h.Run(h.marker_path(fx.data))
            for key in ("close", "held", "space", "unsafe", "damaged", "no_start", "generic", "not_restored", "finished", "busy"):
                text = run.message(key)
                self.assertRegex(text, r"(?i)(try again|open clark again|download it again|wait a minute|from settings)", key)

    def test_the_not_restored_and_close_lines_are_the_notes_words(self):
        self.assertEqual(h.MESSAGES["close"], "The update couldn't start because clark didn't close in time. Nothing was changed. "
                         "Close every clark window, open clark again and try again.")
        self.assertTrue(h.MESSAGES["not_restored"].startswith("The update didn't install, and not everything could be put back yet."))

    def test_the_helper_never_uses_the_updaters_wording_for_a_path(self):
        source = (SRC / "clark" / "update_helper.py").read_text(encoding="utf-8")
        for word in ("sweep", "stage the", "vault"):
            self.assertNotIn(word, "\n".join(re.findall(r'"([^"\n]{20,})"', source)))


class SourceTest(unittest.TestCase):
    def test_standard_library_only_and_unguarded(self):
        source = (SRC / "clark" / "update_helper.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = set()
        for n in top:
            names.update([a.name for a in n.names] if isinstance(n, ast.Import) else [n.module])
        if hasattr(sys, "stdlib_module_names"):
            self.assertTrue({n.split(".")[0] for n in names} <= set(sys.stdlib_module_names), names)
        self.assertFalse([n for n in names if n.split(".")[0] == "clark"], names)
        for node in ast.walk(tree):                                          # the one lazy import is in begin(), the caller's check
            if isinstance(node, ast.ImportFrom) and node.module == "clark":
                self.assertIn("updates", [a.name for a in node.names])
        for guarded in ("server", "store", "changes", "publish", "version"):
            self.assertNotRegex(source, rf"(?m)^\s*(from|import) clark\.?{guarded}\b")
        self.assertNotRegex(source, r"ctypes|os\.system|os\.popen|startfile|shell\s*=")
        self.assertFalse({n.split(".")[0] for n in names} & {"subprocess", "ctypes"}, names)      # it starts nothing itself: platform does
        self.assertNotRegex(source, r"\bunittest\b|os\.environ\.get\(.CLARK_FAIL")      # no fault switch is read in a release

    def test_it_runs_on_its_own_from_another_folder(self):
        with tempfile.TemporaryDirectory() as t:
            copy = Path(t) / "update_helper.py"
            copy.write_bytes((SRC / "clark" / "update_helper.py").read_bytes())
            done = subprocess.run([sys.executable, "-I", str(copy), "--finish", "--data", str(Path(t) / "none")], capture_output=True,
                                  text=True, timeout=30)
            self.assertEqual((done.returncode, done.stdout.strip()), (0, h.MESSAGES["nothing"]))

    def test_platform_py_stays_standard_library_only(self):
        tree = ast.parse((SRC / "clark" / "platform.py").read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for m in mods:
                self.assertNotEqual(m.split(".")[0], "clark", m)
                if hasattr(sys, "stdlib_module_names"):
                    self.assertIn(m.split(".")[0], sys.stdlib_module_names, m)


class HelperCopyTest(unittest.TestCase):
    """begin() copies the helper and platform.py (as clark_platform.py) beside each other; the folder works alone."""

    def test_begin_copies_the_helper_and_platform_and_notes_the_folder(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            path = fx.begin()
            folder = h.updates_dir(fx.data) / ("helper-" + STAMP)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["helper_dir"], str(folder))
            self.assertEqual((folder / "update_helper.py").read_bytes(), (SRC / "clark" / "update_helper.py").read_bytes())
            self.assertEqual((folder / "clark_platform.py").read_bytes(), (SRC / "clark" / "platform.py").read_bytes())
            self.assertFalse((folder / "platform.py").exists())            # that name would hide Python's own platform module

    def test_an_earlier_updates_helper_folder_is_removed(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            put(h.updates_dir(fx.data), "helper-19990101T000000Z/update_helper.py", b"old")
            fx.begin()
            self.assertEqual([p.name for p in h.updates_dir(fx.data).glob("helper-*")], ["helper-" + STAMP])

    def test_finish_works_from_the_copied_folder_alone(self):
        with tempfile.TemporaryDirectory() as t:
            fx = Fixture(t)
            fx.begin()
            folder = h.updates_dir(fx.data) / ("helper-" + STAMP)
            alone = Path(t) / "elsewhere"
            alone.mkdir()
            for f in folder.iterdir():
                (alone / f.name).write_bytes(f.read_bytes())
            self.assertEqual(sorted(p.name for p in alone.iterdir()), ["clark_platform.py", "update_helper.py"])
            done = subprocess.run([sys.executable, "-I", str(alone / "update_helper.py"), "--finish", "--data", str(fx.data)],
                                  capture_output=True, text=True, timeout=60, env={**os.environ, "PYTHONPATH": ""})
            self.assertEqual(done.returncode, h.ROLLED_BACK, done.stdout + done.stderr)
            self.assertEqual(done.stdout.strip(), h.MESSAGES["finished"])
            self.assertFalse(h.marker_path(fx.data).exists())
            self.assertEqual((fx.app / "src/clark/mod.py").read_bytes(), OLD["src/clark/mod.py"])

    def test_the_default_seams_use_the_copy_for_the_server_and_the_health_check(self):
        with tempfile.TemporaryDirectory() as t:
            copy = Path(t) / "one"
            copy.mkdir()
            (copy / "clark_platform.py").write_bytes((SRC / "clark" / "platform.py").read_bytes())
            plat = h.load_platform(copy)
            self.assertIsNot(plat, platform)                                  # a separate load, from the file by its path
            self.assertTrue(callable(plat.start_detached) and callable(plat.run_python_check))
            seams = h.Seams(platform=plat)
            put(t, "app/src/clark/__init__.py", b"")
            (Path(t) / "app/vendor").mkdir()
            seams.check_install(Path(t) / "app")
            put(t, "app/src/clark/bad.py", b"raise ImportError('x')\n")
            with self.assertRaises(h.StepError):
                seams.check_install(Path(t) / "app")

    def test_load_platform_without_a_copy_or_platform_py_fails_plainly(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(OSError):
                h.load_platform(t)


class DefaultSeamsTest(unittest.TestCase):
    def test_is_link_make_executable_free_space(self):
        s = h.Seams()
        with tempfile.TemporaryDirectory() as t:
            put(t, "f", b"x")
            os.symlink(Path(t) / "f", Path(t) / "l")
            self.assertEqual((s.is_link(Path(t) / "l"), s.is_link(Path(t) / "f"), s.is_link(Path(t) / "none")), (True, False, False))
            s.make_executable(Path(t) / "f")
            self.assertTrue(os.access(Path(t) / "f", os.X_OK))
            self.assertGreater(s.free_space(t), 0)
        self.assertTrue(Path(s.helper_python()).exists())

    def test_processes_and_ports(self):
        s = h.Seams()
        self.assertFalse(s.process_gone(os.getpid()))
        self.assertTrue(s.process_gone(None))
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.assertTrue(s.process_gone(child.pid))
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            self.assertFalse(s.port_free(port))
        self.assertTrue(s.port_free(port))

    def test_server_answers_follows_the_launchers_rule(self):
        reply = {"body": b'{"ok": true, "this_data": true}', "status": 200}

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(reply["status"])
                self.end_headers()
                self.wfile.write(reply["body"])

            def log_message(self, *a):
                pass
        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        port, s = server.server_address[1], h.Seams()
        self.assertTrue(s.server_answers(port, "X-Clark-Mark", "m"))
        reply["body"] = b'{"ok": true, "this_data": false}'
        self.assertFalse(s.server_answers(port, "X-Clark-Mark", "m"))
        reply["body"], reply["status"] = b"not json", 200
        self.assertFalse(s.server_answers(port, "X-Clark-Mark", "m"))
        server.shutdown()
        self.assertFalse(s.server_answers(port, "X-Clark-Mark", "m", timeout=0.5))

    def test_the_default_health_check_imports_every_module_in_a_fresh_interpreter(self):
        with tempfile.TemporaryDirectory() as t:
            put(t, "src/clark/__init__.py", b"")
            put(t, "src/clark/good.py", b"X = 1\n")
            (Path(t) / "vendor").mkdir()
            h.Seams().check_install(t)
            put(t, "src/clark/bad.py", b"import not_a_real_module_here\n")
            with self.assertRaises(h.StepError) as cm:
                h.Seams().check_install(t)
            self.assertEqual(cm.exception.key, "damaged")
            self.assertFalse(list(Path(t).rglob("*.pyc")))                   # -B: nothing written


class ReleaseFilesTest(unittest.TestCase):
    def test_the_helper_ships_in_the_downloads_src_folder(self):
        from clark import release_files
        self.assertTrue(release_files.covers("mac", "src/clark/update_helper.py"))
        self.assertTrue((ROOT / "src" / "clark" / "update_helper.py").is_file())


if __name__ == "__main__":
    unittest.main()

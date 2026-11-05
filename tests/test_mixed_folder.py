"""Row 760: clark will not start from a folder whose files are not all from one version.

Run: python3 dev/run_tests.py test_mixed_folder
A download is built in a temporary folder (the program files in .app, the record clark-release.json beside it, written by
package.manifest_bytes from the same bytes). The real launcher is run against it as a subprocess on a free port and a
scratch data folder; every server it starts is stopped by its port. Nothing in the real home folder is touched.
"""
import http.client
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import package  # noqa: E402
from clark import same_version  # noqa: E402

EXACT = ("These clark files are not all from the same version, so clark will not start. "
         "Move the clark folder aside (rename it) and unzip the download again.")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def listening(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def copy_tree(src, dst):
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))


class Download(unittest.TestCase):
    """One fake download per test: tmp/clark/.app/{src,vendor,clark}, tmp/clark/clark.command, tmp/clark/clark-release.json."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-mixed-"))
        self.top = self.tmp / "clark"
        app = self.top / ".app"
        copy_tree(ROOT / "src", app / "src")
        copy_tree(ROOT / "vendor", app / "vendor")
        copy_tree(ROOT / "clark", app / "clark")
        (app / "dev").mkdir()
        shutil.copy(ROOT / "dev" / "demo_data.py", app / "dev" / "demo_data.py")
        shutil.copy(ROOT / "clark.command", self.top / "clark.command")
        self.app = app
        self.data = self.tmp / "data"
        self.write_record()
        self.ports = []
        same_version._ANSWERS.clear()

    def tearDown(self):
        same_version._ANSWERS.clear()
        for port in self.ports:
            subprocess.run("fuser -k %d/tcp" % port, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_record(self):
        content = {}
        for path in sorted(self.top.rglob("*")):
            if path.is_file() and path.name != "clark-release.json":
                content["clark/" + path.relative_to(self.top).as_posix()] = (path.read_bytes(), 0o644)
        (self.top / "clark-release.json").write_bytes(package.manifest_bytes("mac", content, "clark", ROOT))

    def start(self, module="clark", extra=(), demo=False):
        """Run the launcher in the download, as clark.command does: from the top folder, with .app on PYTHONPATH."""
        port = free_port()
        self.ports.append(port)
        env = dict(os.environ, PYTHONPATH=str(self.app), CLARK_CHROME=os.environ.get("CLARK_CHROME", ""))
        env.pop("CLARK_PORT", None)
        cmd = [sys.executable, "-m", module, "--port", str(port)] + ([] if demo else ["--data", str(self.data)]) + list(extra)
        proc = subprocess.Popen(cmd, cwd=str(self.top), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return proc, port

    def refused(self, module="clark"):
        proc, port = self.start(module)
        out, err = proc.communicate(timeout=60)
        self.assertNotEqual(0, proc.returncode, (out, err))
        self.assertIn(EXACT, (out + err))
        self.assertIn(EXACT, err, "the message goes to the terminal's error stream")
        self.assertFalse(listening(port), "no server was started")
        self.assertFalse(self.data.exists(), "nothing was made before the refusal")

    def starts(self):
        proc, port = self.start(extra=("--demo",), demo=True)       # --demo: Linux has no OneDrive finder, so a real data folder can't be opened here
        try:
            for _ in range(150):
                if proc.poll() is not None:
                    break
                if listening(port):
                    return True
                time.sleep(0.2)
            out, err = proc.communicate(timeout=5) if proc.poll() is not None else ("", "")
            self.assertNotIn(EXACT, out + err)
            self.fail("clark did not start: %r %r" % (out, err))
        finally:
            subprocess.run("fuser -k %d/tcp" % port, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.kill()
            proc.communicate()

    def some_file(self):
        return self.app / "src" / "clark" / "idle.py"


class Folder(Download):
    def test_matching_folder_starts(self):
        self.assertFalse(same_version._mixed(self.app))
        self.starts()

    def test_one_older_file_is_refused(self):
        f = self.some_file()
        f.write_bytes(f.read_bytes() + b"# an older file\n")
        self.assertTrue(same_version._mixed(self.app))
        self.refused()

    def test_same_size_different_bytes_is_refused(self):
        f = self.some_file()
        data = f.read_bytes()
        f.write_bytes(bytes([data[0] ^ 1]) + data[1:])
        self.assertTrue(same_version._mixed(self.app))

    def test_missing_file_is_refused(self):
        self.some_file().unlink()
        self.assertTrue(same_version._mixed(self.app))
        self.refused()

    def test_old_launcher_file_is_refused(self):
        (self.top / "clark.command").write_text("#!/bin/bash\n# older\n", encoding="utf-8")
        self.assertTrue(same_version._mixed(self.app))

    def marker(self):
        from clark import update_helper
        path = update_helper.marker_path(self.data)         # the very path the update code writes
        path.parent.mkdir(parents=True)
        path.write_text("{}", encoding="utf-8")
        return path

    def test_mixed_folder_with_an_update_marker_is_left_to_the_recovery(self):
        f = self.some_file()
        f.write_bytes(f.read_bytes() + b"x")
        self.marker()
        argv = ["--data", str(self.data)]
        self.assertTrue(same_version.recovering(argv))
        self.assertTrue(same_version.recovering(["--data=" + str(self.data)]))
        err = io.StringIO()
        self.assertFalse(same_version.refuse(err, self.app, argv=argv))
        self.assertEqual("", err.getvalue())
        proc, port = self.start()                               # the real launcher: the recovery runs (it says its own words), no refusal
        out, err = proc.communicate(timeout=60)
        self.assertNotIn(EXACT, out + err)
        self.assertNotEqual("", out + err)

    def test_mixed_folder_without_the_marker_is_refused(self):
        f = self.some_file()
        f.write_bytes(f.read_bytes() + b"x")
        self.assertFalse(same_version.recovering(["--data", str(self.data)]))
        err = io.StringIO()
        self.assertTrue(same_version.refuse(err, self.app, argv=["--data", str(self.data)]))
        self.assertEqual(EXACT + "\n", err.getvalue())

    def test_the_launcher_checks_after_the_recovery(self):
        from clark import launch
        order = []
        with mock.patch.object(same_version, "refuse", lambda *a, **k: order.append("check") or True):
            launch.launch(0, self.data, lambda text: None, finish=lambda folder, say: order.append("recover") or True)
        self.assertEqual(["recover", "check"], order)

    def test_the_hand_started_server_checks_after_the_recovery(self):
        from clark import __main__ as real
        order = []
        with mock.patch.object(same_version, "refuse", lambda *a, **k: order.append("check") or True), \
                mock.patch.object(real, "finish_unfinished_update", lambda folder, err: order.append("recover") or True):
            code = real.main(["--data", str(self.data), "--port", "1"], out=io.StringIO(), err=io.StringIO(), is_free=lambda port: True)
        self.assertEqual(1, code)
        self.assertEqual(["recover", "check"], order)

    def test_a_src_without_same_version_is_refused_with_the_same_message(self):
        (self.app / "src" / "clark" / "same_version.py").unlink()        # a half-copied unzip: an older src/clark
        for module in ("clark", "clark.launch", "clark.doctor"):
            with self.subTest(module=module):
                proc, port = self.start(module)
                out, err = proc.communicate(timeout=60)
                self.assertEqual(1, proc.returncode, (out, err))
                self.assertEqual(EXACT + "\n", err)
                self.assertNotIn("Traceback", out + err)
                self.assertFalse(listening(port))

    def test_the_stand_ins_say_the_same_words_as_same_version(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("stand_in_main", ROOT / "clark" / "__main__.py")
        stand_in = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stand_in)
        self.assertEqual(same_version.MESSAGE, stand_in.MIXED)

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_clark_command_check_refuses_a_mixed_folder_too(self):
        f = self.some_file()
        f.write_bytes(f.read_bytes() + b"x")
        env = dict(os.environ, CLARK_CHROME=os.environ.get("CLARK_CHROME", ""))
        env.pop("PYTHONPATH", None)
        done = subprocess.run(["bash", str(self.top / "clark.command"), "--check", "--data", str(self.data), "--port", "1"],
                              cwd=str(self.tmp), env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
        self.assertEqual(1, done.returncode, (done.stdout, done.stderr))
        self.assertEqual(EXACT + "\n", done.stderr)
        self.assertNotIn("Ready", done.stdout)

    def command(self, *args):
        env = dict(os.environ, CLARK_CHROME=os.environ.get("CLARK_CHROME", ""))
        env.pop("PYTHONPATH", None)
        return subprocess.run(["bash", str(self.top / "clark.command"), *args, "--data", str(self.data), "--port", "1"],
                              cwd=str(self.tmp), env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_src_vendor_or_clark_beside_app_is_refused_by_clark_command(self):
        for name in ("src", "vendor", "clark"):
            for kind in ("folder", "file"):
                with self.subTest(name=name, kind=kind):
                    path = self.top / name
                    if kind == "folder":
                        path.mkdir()
                    else:
                        path.write_text("x", encoding="utf-8")
                    for args in (("--check",), ()):
                        done = self.command(*args)
                        self.assertEqual(1, done.returncode, (done.stdout, done.stderr))
                        self.assertEqual(EXACT + "\n", done.stderr)
                    shutil.rmtree(path) if kind == "folder" else path.unlink()

    @unittest.skipUnless(shutil.which("bash"), "needs bash")
    def test_a_clean_layout_with_the_persons_folders_beside_app_is_not_refused(self):
        for name in ("system", "data", "meet clark", "intake", "docker"):
            (self.top / name).mkdir(exist_ok=True)
            (self.top / name / "a.txt").write_text("mine", encoding="utf-8")
        (self.top / "START-HERE.txt").write_text("x", encoding="utf-8")
        self.write_record()
        done = self.command("--check")
        self.assertNotIn(EXACT, done.stderr + done.stdout)
        self.assertIn("Checking what clark needs", done.stdout)      # the doctor ran
        self.starts()

    def test_launch_module_refuses_too(self):
        f = self.some_file()
        f.write_bytes(f.read_bytes() + b"x")
        self.refused("clark.launch")

    def test_extra_file_not_in_the_record_is_ignored(self):
        (self.app / "src" / "clark" / "left_over_from_older.py").write_text("x = 1\n", encoding="utf-8")
        (self.top / "my notes.txt").write_text("mine\n", encoding="utf-8")
        self.assertFalse(same_version._mixed(self.app))
        self.starts()

    def test_files_outside_the_program_are_not_checked(self):
        (self.top / "README.md").write_text("changed\n", encoding="utf-8")
        self.assertFalse(same_version._mixed(self.app))

    def test_no_record_starts(self):
        (self.top / "clark-release.json").unlink()
        self.assertFalse(same_version._mixed(self.app))
        self.starts()

    def test_unreadable_record_is_refused(self):
        for text in ("not json", "[]", "{}", '{"files": []}', '{"files": {".app/src/clark/idle.py": 5}}',
                     '{"files": {".app/src/clark/idle.py": {"size": "1", "sha256": "x"}}}',
                     '{"files": {"../outside": {"size": 1, "sha256": "x"}}}', ""):
            (self.top / "clark-release.json").write_text(text, encoding="utf-8")
            self.assertTrue(same_version._mixed(self.app), text)
        (self.top / "clark-release.json").write_bytes(b"\xff\xfe\x00")
        self.assertTrue(same_version._mixed(self.app))
        (self.top / "clark-release.json").write_text('{"files": {}}', encoding="utf-8")
        self.assertFalse(same_version._mixed(self.app), "an empty list lists nothing that differs")

    def test_malformed_record_stops_the_launcher(self):
        (self.top / "clark-release.json").write_text("not json", encoding="utf-8")
        self.refused()

    def test_source_checkout_is_never_checked(self):
        self.assertFalse(same_version._mixed(ROOT))
        self.assertFalse(same_version._mixed(self.tmp))
        checkout = self.tmp / "checkout"                        # not a .app folder: a record beside it is not looked at
        (checkout / "src").mkdir(parents=True)
        (self.tmp / "clark-release.json").write_text("not json", encoding="utf-8")
        self.assertFalse(same_version._mixed(checkout))
        (self.top / "clark-release.json").write_text("not json", encoding="utf-8")
        self.assertTrue(same_version._mixed(self.app), "the same record beside .app does count")

    def test_message_is_exact_and_goes_to_the_given_stream(self):
        f = self.some_file()
        f.write_bytes(f.read_bytes() + b"x")
        err = io.StringIO()
        self.assertTrue(same_version.refuse(err, self.app))
        self.assertEqual(EXACT + "\n", err.getvalue())
        self.assertEqual(EXACT, same_version.MESSAGE)

    def test_check_is_quick(self):
        t = time.perf_counter()
        for _ in range(5):
            same_version._mixed(self.app)
        each = (time.perf_counter() - t) / 5
        print("same_version.mixed: %.0f ms each (%d files)" % (each * 1000, len(json.loads((self.top / 'clark-release.json').read_text(encoding="utf-8"))["files"])))
        self.assertLess(each, 2.0)


if __name__ == "__main__":
    unittest.main()

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

from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import package  # noqa: E402
from clark import same_version  # noqa: E402

EXACT = ("These clark files are not all from the same version, so clark will not start. "
         "Delete the clark folder and unzip the download again.")


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

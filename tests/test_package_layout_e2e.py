"""The download's layout, end to end (issue 694): build the real zip, unzip it with the system's own unzip, and run it.

One folder `clark` with the program files in the hidden `.app`; `bash clark.command --check` runs the doctor from there; the
server starts through clark.command; the person's own branding folder (never in the zip) is found by the page code and
comes through an update byte for byte. Skips cleanly without python3, bash or unzip. Run: python3 dev/run_tests.py test_package_layout_e2e
"""
import hashlib
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile
from pathlib import Path

from _paths import ROOT
import package
from clark import update_helper as h
from test_update_helper import FakeSeams

BASH, UNZIP = shutil.which("bash"), shutil.which("unzip")
PY3 = shutil.which("python3")
MAC = sys.platform == "darwin"
VISIBLE = ["README.md", "START-HERE.md", "clark-release.json", "clark.command", "docker"]
TOKENS = b":root { --e2e-brand-mark: 694; }\n"
STAMP = "20261101T120000Z"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipUnless(BASH and UNZIP and PY3, "needs bash, unzip and python3")
class DownloadLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark layout ")).resolve()
        cls.zip = package.build("mac", cls.tmp / "dist", dirty=True)
        cls.where = cls.tmp / "Downloads and such"
        cls.where.mkdir()
        subprocess.run([UNZIP, "-q", str(cls.zip), "-d", str(cls.where)], check=True, timeout=120)
        cls.clark = cls.where / "clark"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "CLARK_PORT", "CLARK_DATA_DIR")}
        env.update(HOME=str(self.tmp), PYTHONDONTWRITEBYTECODE="1", **extra)
        return env

    def test_one_folder_called_clark_with_the_program_in_dot_app_and_nothing_of_the_persons(self):
        self.assertEqual(["clark"], os.listdir(self.where))
        top = sorted(os.listdir(self.clark))
        self.assertEqual(sorted(VISIBLE + [".app"]), top)
        for gone in ("src", "vendor", "clark", "system", "data", "dev", "LICENSE", "NOTICE.md"):
            self.assertNotIn(gone, top)
        for needed in ("src/clark/__init__.py", "src/clark/page/page.html", "vendor/openpyxl/__init__.py", "clark/__main__.py",
                       "LICENSE", "NOTICE.md"):
            self.assertTrue((self.clark / ".app" / needed).is_file(), needed)
        self.assertTrue(os.access(self.clark / "clark.command", os.X_OK))
        with zipfile.ZipFile(self.zip) as z:
            self.assertEqual([], [n for n in z.namelist() if n.split("/")[1:2] in (["system"], ["data"])
                                  or n.startswith(("clark/.app/system/", "clark/.app/data/"))])
            self.assertEqual({"clark"}, {n.split("/")[0] for n in z.namelist()})

    def test_the_compose_file_is_in_place_and_starts_in_dot_app(self):
        text = (self.clark / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("    working_dir: /clark/.app\n", text)
        self.assertIn("        source: ..\n", text)

    @unittest.skipUnless(MAC, "the checks and the launcher are the Mac's")
    def test_check_runs_the_doctor_from_the_hidden_folder(self):
        data = self.tmp / "check data"
        env = self.env()
        env.pop("PYTHONDONTWRITEBYTECODE", None)        # issue 743: clark.command itself must keep bytecode out, not the caller
        done = subprocess.run([BASH, str(self.clark / "clark.command"), "--check", "--data", str(data), "--port", str(free_port())],
                              cwd=str(self.tmp), env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=120)
        self.assertNotIn("Traceback", done.stdout + done.stderr)
        self.assertIn("Checking what clark needs on this computer...", done.stdout)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        self.assertEqual(0 if "Everything clark needs is ready." in done.stdout else 1, done.returncode, done.stdout)
        self.assertEqual([], [p for p in self.clark.rglob("__pycache__")], "running it wrote no bytecode into the download")

    def test_the_page_code_finds_the_branding_beside_dot_app(self):
        brand = self.clark / "branding"
        self.addCleanup(shutil.rmtree, self.clark / "branding", True)
        brand.mkdir(parents=True)
        (brand / "tokens.css").write_bytes(TOKENS)
        code = ("import sys; sys.path[:0] = [sys.argv[1] + '/.app/src', sys.argv[1] + '/.app/vendor']\n"
                "from clark import page; print(page.BRANDING); print(page.local_tokens_file())\n")
        done = subprocess.run([PY3, "-I", "-c", code, str(self.clark)], cwd=str(self.tmp), capture_output=True, text=True,
                              timeout=60, env=self.env())
        self.assertEqual(0, done.returncode, done.stderr)
        want, tokens = done.stdout.splitlines()
        self.assertEqual(brand.resolve(), Path(want).resolve())
        self.assertEqual((brand / "tokens.css").resolve(), Path(tokens).resolve())

    @unittest.skipUnless(MAC and shutil.which("lsof"), "the launcher is the Mac's; lsof names the server to stop")
    def test_the_server_starts_through_clark_command_and_serves_the_persons_branding(self):
        brand = self.clark / "branding"
        self.addCleanup(shutil.rmtree, self.clark / "branding", True)
        brand.mkdir(parents=True)
        (brand / "tokens.css").write_bytes(TOKENS)
        stub = self.tmp / "browser"
        stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        port, data = free_port(), self.tmp / "server data"
        self.addCleanup(self.stop_server, port)
        done = subprocess.run([BASH, str(self.clark / "clark.command"), "--data", str(data), "--port", str(port)],
                              cwd=str(self.tmp), env=self.env(CLARK_BROWSER=str(stub)), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertIn("Opened clark in its own window.", done.stdout)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=10) as reply:
            self.assertTrue(json.loads(reply.read())["ok"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as reply:
            page = reply.read()
        # Since the per-project brand (row 944, T3) GET / has no project and is the generic look: the person's tokens are layered only
        # for a project whose brand is the local one (test_the_page_code_finds_the_branding_beside_dot_app pins that the tokens are found).
        self.assertNotIn(b"--e2e-brand-mark: 694", page, "the page with no project is the generic look, not the person's brand")
        self.assertTrue((data / "clark.db").is_file())
        self.assertFalse(list((self.clark / ".app").rglob("clark.db")), "no data was written inside the download")

    def stop_server(self, port):
        out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout.split()
        for pid in out:
            try:
                os.kill(int(pid), 15)
            except OSError:
                pass
        end = time.monotonic() + 10
        while time.monotonic() < end and subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                                                        capture_output=True, text=True).stdout.split():
            time.sleep(0.1)

    def test_an_update_in_place_leaves_branding_and_system_branding_byte_identical(self):
        """The real unzipped folder, a staged newer copy of it, and the update helper (its platform seams faked)."""
        app = self.tmp / "updating" / "clark"
        shutil.copytree(self.clark, app)
        brand = app / "branding"
        (brand / "assets").mkdir(parents=True)
        (brand / "tokens.css").write_bytes(TOKENS)
        (brand / "assets" / "cover.png").write_bytes(b"\x89PNG my own cover")
        old_place = app / "system" / "branding"             # the 1.0.5 place stays through an update too
        old_place.mkdir(parents=True)
        (old_place / "tokens.css").write_bytes(TOKENS)
        mine = {p.relative_to(app).as_posix(): p.read_bytes() for q in (brand, old_place) for p in q.rglob("*") if p.is_file()}
        old = json.loads((app / package.MANIFEST).read_text(encoding="utf-8"))
        newer = "9.9.9"
        staging = app / (h.STAGING_PREFIX + STAMP)
        files = {}
        for rel, row in old["files"].items():
            if rel == package.MANIFEST:
                continue
            data = (app / rel).read_bytes()
            if rel == ".app/src/clark/__init__.py":
                data = data.replace(old["version"].encode(), newer.encode())
            dest = staging / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            os.chmod(dest, int(row["mode"], 8))
            files[rel] = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "mode": row["mode"]}
        (staging / package.MANIFEST).write_text(json.dumps({**old, "version": newer, "files": files}), encoding="utf-8")
        data_dir = self.tmp / "updating data"
        (data_dir).mkdir()
        marker = h.begin(data_dir, app, staging, STAMP, old["version"], newer, old["schema_version"], 4321, 8765,
                         "X-Clark-Mark", "mark-1", backup_dir=str(data_dir / "backup"), check=False)
        code, result = h.run_update(marker, FakeSeams(), None)
        self.assertEqual(h.OK, code, result)
        self.assertIn(newer, (app / ".app" / "src" / "clark" / "__init__.py").read_text(encoding="utf-8"))
        self.assertEqual(mine, {p.relative_to(app).as_posix(): p.read_bytes() for q in (brand, old_place) for p in q.rglob("*") if p.is_file()})
        self.assertEqual(sorted(VISIBLE + [".app", "system", "branding"]),
                         sorted(n for n in os.listdir(app) if not n.startswith(".clark-")))


if __name__ == "__main__":
    unittest.main()

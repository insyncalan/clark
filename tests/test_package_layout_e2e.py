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
        self.seed_project_on_local_brand(data)
        done = subprocess.run([BASH, str(self.clark / "clark.command"), "--data", str(data), "--port", str(port)],
                              cwd=str(self.tmp), env=self.env(CLARK_BROWSER=str(stub)), stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertIn("Opened clark in its own window.", done.stdout)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=10) as reply:
            self.assertTrue(json.loads(reply.read())["ok"])
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/?project=BRN", timeout=10) as reply:
            page = reply.read()
        self.assertIn(b"--e2e-brand-mark: 694", page, "the page for a project on the local brand carries the tokens from branding beside .app")
        self.assertTrue((data / "clark.db").is_file())
        self.assertFalse(list((self.clark / ".app").rglob("clark.db")), "no data was written inside the download")

    def seed_project_on_local_brand(self, data):
        """Row 944: the top-level tokens.css is layered only for a project whose row has brand 'local-brand', so the data folder
        starts with one (BRN), made by the download's own store code; the launcher then opens that same folder."""
        code = ("import sys; sys.path[:0] = [sys.argv[1] + '/.app/src', sys.argv[1] + '/.app/vendor']\n"
                "from pathlib import Path\nfrom clark.store import open_store\n"
                "Path(sys.argv[2]).mkdir(parents=True, exist_ok=True)\n"
                "s = open_store(Path(sys.argv[2]) / 'clark.db', onedrive_roots=[])\n"
                "s.con.execute(\"INSERT INTO projects (code, name, brand) VALUES ('BRN', 'Brand check', 'local-brand')\")\n"
                "s.con.commit(); s.close()\n")
        done = subprocess.run([PY3, "-I", "-c", code, str(self.clark), str(data)], cwd=str(self.tmp), capture_output=True,
                              text=True, timeout=60, env=self.env())
        self.assertEqual(0, done.returncode, done.stderr)

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


def make_newer_source(tmp, newer):
    """A real second source tree (git needs it for package.build) whose version is `newer` and which has one more program file."""
    src = tmp / "newer source"
    src.mkdir()
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", "HEAD"], capture_output=True, check=True, timeout=120).stdout
    subprocess.run(["tar", "-x", "-C", str(src)], input=archive, check=True, timeout=120)
    init = src / "src" / "clark" / "__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace(package.version(ROOT), newer, 1), encoding="utf-8")
    (src / "src" / "clark" / "new_in_newer.py").write_text("NEWER = True\n", encoding="utf-8")
    git = ["git", "-C", str(src), "-c", "user.name=t", "-c", "user.email=t@example.com"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "newer"]):
        subprocess.run(git + args, check=True, capture_output=True, timeout=120)
    return src


def tree(base, skip=()):
    """Every file (bytes, mode) and folder under base, minus clark's own working folders, as a dict that compares."""
    out = {}
    for folder, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith((h.STAGING_PREFIX, h.OLD_PREFIX, h.HELPER_PREFIX)) and d not in skip]
        for n in names + dirs:
            p = Path(folder, n)
            rel = p.relative_to(base).as_posix()
            out[rel + "/" if p.is_dir() else rel] = None if p.is_dir() else (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
    return out


@unittest.skipUnless(UNZIP, "needs unzip")
class UpdateFromTheOldDownloadToTheNewZip(unittest.TestCase):
    """SWEEP S4: a 1.0.5 download (real packager), a newer test zip (real packager, a real second source), the update helper
    with its platform seams faked. The person's branding, system/branding and data folders come through byte for byte, and a
    failed update puts the old download back (#280)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark update ")).resolve()
        cls.old_zip = package.build("mac", cls.tmp / "old dist", dirty=True)
        cls.newer = "1.0.6" if package.version(ROOT) != "1.0.6" else "1.0.7"
        cls.new_zip = package.build("mac", cls.tmp / "new dist", root=make_newer_source(cls.tmp, cls.newer), dirty=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="work ", dir=self.tmp))
        subprocess.run([UNZIP, "-q", str(self.old_zip), "-d", str(self.work / "old")], check=True, timeout=120)
        self.app = self.work / "old" / "clark"
        subprocess.run([UNZIP, "-q", str(self.new_zip), "-d", str(self.work / "new")], check=True, timeout=120)
        self.staging = self.app / (h.STAGING_PREFIX + STAMP)
        shutil.copytree(self.work / "new" / "clark", self.staging)
        self.data_dir = self.work / "scratch data"
        (self.data_dir).mkdir()
        (self.data_dir / "clark.db").write_bytes(b"not a real database")
        self.mine = {}
        for rel, body in {"branding/tokens.css": TOKENS, "branding/assets/cover.png": b"\x89PNG my own cover",
                          "system/branding/tokens.css": TOKENS + b"/* old place */\n", "system/notes.txt": b"mine\n",
                          "data/book.xlsx": b"PK my own file\n", "data/deep/er/still.bin": bytes(range(256))}.items():
            path = self.app / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            self.mine[rel] = body
        (self.app / "data" / "empty folder").mkdir()
        self.before = tree(self.app, skip=(self.staging.name,))

    def mine_now(self):
        return {p.relative_to(self.app).as_posix(): p.read_bytes() for top in ("branding", "system", "data")
                for p in (self.app / top).rglob("*") if p.is_file()}

    def begin(self):
        old = json.loads((self.app / package.MANIFEST).read_text(encoding="utf-8"))
        new = json.loads((self.staging / package.MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(self.newer, new["version"])
        self.assertNotEqual(old["version"], new["version"])
        return h.begin(self.data_dir, self.app, self.staging, STAMP, old["version"], new["version"], old["schema_version"],
                       4321, 8765, "X-Clark-Mark", "mark-1", backup_dir=str(self.data_dir / "backup"), check=False)

    def test_the_new_zip_goes_in_and_the_persons_folders_are_byte_identical(self):
        code, result = h.run_update(self.begin(), FakeSeams(), None)
        self.assertEqual(h.OK, code, result)
        self.assertEqual(self.mine, self.mine_now())
        self.assertTrue((self.app / "data" / "empty folder").is_dir())
        self.assertTrue((self.app / ".app" / "src" / "clark" / "new_in_newer.py").is_file())
        self.assertEqual(self.newer, json.loads((self.app / package.MANIFEST).read_text(encoding="utf-8"))["version"])
        for rel, row in json.loads((self.app / package.MANIFEST).read_text(encoding="utf-8"))["files"].items():
            if rel != package.MANIFEST:
                self.assertEqual(row["sha256"], hashlib.sha256((self.app / rel).read_bytes()).hexdigest(), rel)
        self.assertEqual(b"not a real database", (self.data_dir / "clark.db").read_bytes())

    def test_a_failed_update_at_any_step_puts_the_old_download_back_with_the_persons_folders(self):
        trace = []
        code, _ = h.run_update(self.begin(), FakeSeams(), None, trace)       # a dry run names the step points
        self.assertEqual(h.OK, code)
        self.assertGreater(len(trace), 5)
        self.tearDown_and_reset()
        for point in trace:
            with self.subTest(point=point):
                code, result = h.run_update(self.begin(), FakeSeams(), Fail(point))
                self.assertEqual(h.ROLLED_BACK, code, (point, result))
                self.assertEqual(self.before, tree(self.app, skip=(self.staging.name,)), point)
                self.assertEqual(self.mine, self.mine_now(), point)
                self.assertFalse((self.app / ".app" / "src" / "clark" / "new_in_newer.py").exists(), point)
                self.restage()

    def test_the_new_version_not_answering_puts_the_old_download_back(self):
        seams = FakeSeams()
        seams.server_answers = lambda *a, **k: False
        code, result = h.run_update(self.begin(), seams, None)
        self.assertEqual(h.ROLLED_BACK, code, result)
        self.assertEqual(self.before, tree(self.app, skip=(self.staging.name,)))
        self.assertEqual(self.mine, self.mine_now())
        self.assertEqual(b"not a real database", (self.data_dir / "clark.db").read_bytes())

    def test_a_newer_zip_that_ships_into_a_persons_folder_is_refused_and_nothing_is_touched(self):
        from clark import updates
        for top in ("branding", "system", "data", "Branding", "DATA"):
            with self.subTest(top=top):
                path = self.staging / package.MANIFEST
                record = json.loads(path.read_text(encoding="utf-8"))
                record["files"][top + "/tokens.css"] = {"sha256": "0" * 64, "size": 0, "mode": "644"}
                path.write_text(json.dumps(record), encoding="utf-8")
                with self.assertRaises(updates.UpdateError) as cm:
                    self.begin()
                self.assertEqual("unsafe", cm.exception.key)
                self.assertFalse(h.marker_path(self.data_dir).exists())
                self.assertEqual(self.mine, self.mine_now())
                self.tearDown_and_reset()

    def restage(self):
        if not self.staging.exists():
            shutil.copytree(self.work / "new" / "clark", self.staging)
        for stale in (h.updates_dir(self.data_dir) / h.MARKER_NAME,):
            if stale.exists():
                stale.unlink()

    def tearDown_and_reset(self):
        """Put the work folder back as setUp left it, after the dry run that updated it."""
        shutil.rmtree(self.work)
        self.setUp()


class Fail:
    def __init__(self, name):
        self.name = name

    def __call__(self, name):
        if name == self.name:
            raise RuntimeError("injected fault at " + name)


if __name__ == "__main__":
    unittest.main()

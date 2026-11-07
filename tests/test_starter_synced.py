"""Row 512: the Mac-side Docker starter (docker/start.command) refuses a synced data folder BEFORE the container starts.

Run: python3 tests/test_starter_synced.py
The decision is a pure function (clark.starter_check.refusal): no Docker, no network. The script is run with a stub `docker` first on
PATH that only records its arguments, so a test can say whether docker was reached at all. Everything lives in a temporary folder.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clark import starter_check as sc  # noqa: E402

REFUSED = ("/Users/sam/Library/CloudStorage/OneDrive-Fictional Ltd/clark", "/Users/sam/OneDrive/clark", "/Users/sam/onedrive - Fictional Ltd/x/clark",
           "/Users/sam/Dropbox/clark", "/Users/sam/Library/CloudStorage/Dropbox/clark", "/Users/sam/Dropbox (Personal)/clark",
           "/Users/sam/Library/Mobile Documents/com~apple~CloudDocs/clark", "/Users/sam/Library/CloudStorage/GoogleDrive-a@b.test/My Drive/clark",
           "/Users/sam/Google Drive/clark", "/Users/sam/DROPBOX/clark", "/Users/sam/Dropbox-Team/clark", "/Users/sam/Dropbox(Work)/clark",
           "/Users/sam/My Drive/clark", "/Users/sam/Work Files/OneDrive - Fictional Ltd/My Notes/clark")
ALLOWED = ("/Users/sam/Library/Application Support/clark", "/Users/sam/clark-data", "/Users/sam/Documents/not-OneDrive-really/clark",
           "/Users/sam/Documents/dropboxing/clark", "/Users/sam/My Notes/Work Files/clark", "/Users/sam/My Drives/clark")


class Decision(unittest.TestCase):
    def test_synced_folders_are_refused_with_the_service_named(self):
        for path in REFUSED:
            with self.subTest(path):
                text = sc.refusal(path)
                self.assertIsNotNone(text)
                self.assertIn(f"kept in {path} because it is inside ", text)
                self.assertIn("which damages the database", text)

    def test_the_onedrive_words_are_the_existing_ones(self):
        text = sc.refusal("/Users/sam/OneDrive - Fictional Ltd/clark")
        self.assertEqual(text, "Your data can't be kept in /Users/sam/OneDrive - Fictional Ltd/clark because it is inside OneDrive (OneDrive - Fictional Ltd). "
                               "OneDrive copies files while they are being written, which damages the database. Choose a folder on this computer "
                               "that OneDrive doesn't sync.")

    def test_ordinary_folders_are_allowed(self):
        for path in ALLOWED:
            with self.subTest(path):
                self.assertIsNone(sc.refusal(path))

    def test_a_link_into_a_synced_folder_is_followed(self):
        with tempfile.TemporaryDirectory() as t:
            real = Path(t) / "OneDrive - Test" / "clark"
            real.mkdir(parents=True)
            link = Path(t) / "plain"
            link.symlink_to(real)
            self.assertIn("inside OneDrive", sc.refusal(str(link)))
            self.assertIn("inside OneDrive", sc.refusal(str(link / "deeper" / "not-yet-made")))
            elsewhere = Path(t) / "ok"
            elsewhere.mkdir()
            self.assertIsNone(sc.refusal(str(elsewhere)))

    def test_the_default_folder_is_the_compose_files_default(self):
        self.assertEqual(sc.data_folder({"HOME": "/Users/sam"}), "/Users/sam/Library/Application Support/clark")
        self.assertEqual(sc.data_folder({"HOME": "/Users/sam", "CLARK_DATA_DIR": "/x/y"}), "/x/y")
        self.assertEqual(sc.data_folder({"HOME": "/Users/sam", "CLARK_DATA_DIR": ""}), "/Users/sam/Library/Application Support/clark")


class EnvFile(unittest.TestCase):
    """Compose reads docker/.env for CLARK_DATA_DIR when the shell does not set it; the check must see the same folder."""

    def env(self, text):
        t = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, t, True)
        f = Path(t) / ".env"
        f.write_text(text, encoding="utf-8")
        return str(f)

    def test_the_env_file_names_the_folder_when_the_shell_does_not(self):
        f = self.env('# a comment\nOTHER=1\nCLARK_DATA_DIR=/Users/sam/OneDrive/clark\n')
        self.assertEqual(sc.data_folder({"HOME": "/h"}, f), "/Users/sam/OneDrive/clark")
        self.assertEqual(sc.data_folder({"HOME": "/h"}, self.env('CLARK_DATA_DIR="/Users/sam/Dropbox/a b"\n')), "/Users/sam/Dropbox/a b")
        self.assertEqual(sc.data_folder({"HOME": "/h"}, self.env("CLARK_DATA_DIR='/x y'\n")), "/x y")

    def test_the_shell_wins_over_the_env_file_and_a_missing_file_is_nothing(self):
        f = self.env("CLARK_DATA_DIR=/from/file\n")
        self.assertEqual(sc.data_folder({"HOME": "/h", "CLARK_DATA_DIR": "/from/shell"}, f), "/from/shell")
        self.assertEqual(sc.data_folder({"HOME": "/h"}, "/no/such/.env"), "/h/Library/Application Support/clark")
        self.assertEqual(sc.data_folder({"HOME": "/h"}, self.env("CLARK_DATA_DIR=\n")), "/h/Library/Application Support/clark")

    def test_main_refuses_the_folder_the_env_file_names(self):
        import io
        from contextlib import redirect_stderr
        err = io.StringIO()
        with redirect_stderr(err):
            code = sc.main(["--env-file", self.env("CLARK_DATA_DIR=/Users/sam/OneDrive - X/clark\n")], {"HOME": "/h"})
        self.assertEqual(code, 1)
        self.assertIn("inside OneDrive", err.getvalue())


class Script(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = Path(self.tmp) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp) / "docker.log"
        stub = self.bin / "docker"
        stub.write_text('#!/bin/sh\necho "$@" >> "$DOCKER_LOG"\n', encoding="utf-8")
        stub.chmod(0o755)

    def run_script(self, data, *args):
        env = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": self.tmp, "DOCKER_LOG": str(self.log), "CLARK_DATA_DIR": data}
        return subprocess.run(["bash", str(ROOT / "docker" / "start.command"), *args], env=env, capture_output=True, text=True, cwd=self.tmp, timeout=60)

    def test_a_synced_folder_stops_before_docker_is_reached(self):
        r = self.run_script(f"{self.tmp}/OneDrive - Test/clark")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("because it is inside OneDrive", r.stderr)
        self.assertFalse(self.log.exists(), "docker must not be run")

    def test_an_ordinary_folder_runs_compose_up(self):
        r = self.run_script(f"{self.tmp}/data")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").strip(), f"compose -f {ROOT}/docker/compose.yaml up -d")

    def test_extra_words_go_on_to_compose(self):
        self.run_script(f"{self.tmp}/data", "--pull", "always")
        self.assertTrue(self.log.read_text(encoding="utf-8").strip().endswith("up -d --pull always"))

    def test_the_env_file_beside_the_compose_file_is_read(self):
        (Path(self.tmp) / "repo" / "docker").mkdir(parents=True)
        for f in ("src/clark/starter_check.py", "docker/start.command", "docker/compose.yaml"):
            (Path(self.tmp) / "repo" / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / f, Path(self.tmp) / "repo" / f)
        (Path(self.tmp) / "repo" / "docker" / ".env").write_text(f"CLARK_DATA_DIR={self.tmp}/Dropbox/my data\n", encoding="utf-8")
        env = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": self.tmp, "DOCKER_LOG": str(self.log)}
        r = subprocess.run(["bash", str(Path(self.tmp) / "repo" / "docker" / "start.command")], env=env, capture_output=True, text=True, cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("inside Dropbox", r.stderr)
        self.assertFalse(self.log.exists())

    def test_a_space_in_the_folder_to_the_clark_folder_and_data_still_works(self):
        base = Path(self.tmp) / "my clark folder"
        (base / "docker").mkdir(parents=True)
        for f in ("src/clark/starter_check.py", "docker/start.command", "docker/compose.yaml"):
            (base / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / f, base / f)
        r = subprocess.run(["bash", str(base / "docker" / "start.command")], env={"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": self.tmp,
                           "DOCKER_LOG": str(self.log), "CLARK_DATA_DIR": f"{self.tmp}/my data folder"}, capture_output=True, text=True, cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.log.read_text(encoding="utf-8").strip(), f"compose -f {base}/docker/compose.yaml up -d")
        self.log.unlink()
        r = subprocess.run(["bash", str(base / "docker" / "start.command")], env={"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": self.tmp,
                           "DOCKER_LOG": str(self.log), "CLARK_DATA_DIR": f"{self.tmp}/Google Drive/my data"}, capture_output=True, text=True, cwd=self.tmp, timeout=60)
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertFalse(self.log.exists())

    def test_the_compose_file_names_the_starter(self):
        text = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("docker/start.command", text)


if __name__ == "__main__":
    unittest.main()

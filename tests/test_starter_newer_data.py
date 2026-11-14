"""Row 1164: the Docker starter refuses data from a NEWER clark before the container starts, and --diagnose says what it sees.

Run: python3 tests/test_starter_newer_data.py
No Docker, no network, no browser: a stub `docker` first on PATH records its arguments. Everything lives in a temporary folder.
"""
import io
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from clark import starter_check as sc  # noqa: E402


def make_db(folder, version, wal=False):
    Path(folder).mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(Path(folder) / "clark.db")
    if wal:
        con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
    con.execute("INSERT INTO meta VALUES ('schema_version', ?)", (str(version),))
    con.commit()
    return con


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.data = str(Path(self.tmp) / "data")


class Version(Tmp):
    def test_the_version_is_read(self):
        make_db(self.data, 7).close()
        self.assertEqual(sc.folder_data_version(self.data), 7)

    def test_no_folder_and_no_file_are_none(self):
        self.assertIsNone(sc.folder_data_version(self.data))
        Path(self.data).mkdir()
        self.assertIsNone(sc.folder_data_version(self.data))

    def test_an_empty_file_and_a_non_database_are_none(self):
        Path(self.data).mkdir()
        (Path(self.data) / "clark.db").write_bytes(b"")
        self.assertIsNone(sc.folder_data_version(self.data))
        (Path(self.data) / "clark.db").write_text("this is not a database " * 50)
        self.assertIsNone(sc.folder_data_version(self.data))

    def test_a_database_with_no_version_is_none(self):
        Path(self.data).mkdir()
        con = sqlite3.connect(Path(self.data) / "clark.db")
        con.execute("CREATE TABLE meta (k TEXT, v TEXT)")
        con.commit()
        con.close()
        self.assertIsNone(sc.folder_data_version(self.data))

    def test_a_database_held_open_in_wal_mode_is_read(self):
        con = make_db(self.data, 31, wal=True)
        try:
            self.assertEqual(sc.folder_data_version(self.data), 31)
        finally:
            con.close()

    def test_reading_changes_nothing(self):
        make_db(self.data, 5).close()
        before = {p.name: p.read_bytes() for p in Path(self.data).iterdir()}
        sc.folder_data_version(self.data)
        self.assertEqual({p.name: p.read_bytes() for p in Path(self.data).iterdir()}, before)

    def test_the_starters_numbers_match_the_program(self):
        text = (ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8")
        self.assertEqual(sc.SCHEMA_VERSION, int(re.search(r"^SCHEMA_VERSION = (\d+)", text, re.M).group(1)))
        main = (ROOT / "src" / "clark" / "__main__.py").read_text(encoding="utf-8")
        self.assertEqual(sc.DB_NAME, re.search(r'^DB_NAME = "([^"]+)"', main, re.M).group(1))


class Main(Tmp):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = sc.main(list(argv), {"HOME": self.tmp})
        return code, out.getvalue(), err.getvalue()

    def test_newer_data_is_refused_naming_the_folder_both_versions_and_the_way_out(self):
        make_db(self.data, sc.SCHEMA_VERSION + 3).close()
        code, _, err = self.run_main(self.data)
        self.assertEqual(code, 1)
        self.assertIn(self.data, err)
        self.assertIn(f"data version {sc.SCHEMA_VERSION + 3}", err)
        self.assertIn(f"up to version {sc.SCHEMA_VERSION}", err)
        self.assertIn("CLARK_DATA_DIR", err)

    def test_one_version_newer_is_refused(self):
        make_db(self.data, sc.SCHEMA_VERSION + 1).close()
        self.assertEqual(self.run_main(self.data)[0], 1)

    def test_the_same_and_an_older_version_are_allowed(self):
        for v in (sc.SCHEMA_VERSION, sc.SCHEMA_VERSION - 1, 1):
            with self.subTest(v):
                shutil.rmtree(self.data, True)
                make_db(self.data, v).close()
                self.assertEqual(self.run_main(self.data), (0, "", ""))

    def test_a_new_folder_and_a_non_database_are_allowed(self):
        self.assertEqual(self.run_main(self.data)[0], 0)
        Path(self.data).mkdir()
        (Path(self.data) / "clark.db").write_text("junk " * 100)
        self.assertEqual(self.run_main(self.data)[0], 0)

    def test_no_sentence_starts_with_the_product_name_capitalised(self):
        text = sc.newer_data_text("/x/y", 99) + "\n" + "\n".join(sc.diagnose(self.data))
        for sentence in re.split(r"(?<=[.!?])\s+|\n", text):
            self.assertFalse(sentence.startswith("Clark"), sentence)

    def test_the_env_file_folder_is_the_one_checked(self):
        make_db(self.data, sc.SCHEMA_VERSION + 1).close()
        env = Path(self.tmp) / ".env"
        env.write_text(f"CLARK_DATA_DIR={self.data}\n", encoding="utf-8")
        self.assertEqual(self.run_main("--env-file", str(env))[0], 1)

    def test_diagnose_lists_the_folder_its_contents_and_both_versions(self):
        make_db(self.data, sc.SCHEMA_VERSION + 2).close()
        (Path(self.data) / "backups").mkdir()
        code, out, err = self.run_main("--diagnose", self.data)
        self.assertEqual((code, err), (0, ""))
        self.assertIn(f"Data folder: {self.data}", out)
        self.assertIn("backups/", out)
        self.assertIn("clark.db", out)
        self.assertIn(f"Data version in clark.db: {sc.SCHEMA_VERSION + 2}", out)
        self.assertIn(f"reads: up to {sc.SCHEMA_VERSION}", out)
        self.assertIn("newer than this clark", out)

    def test_diagnose_on_a_missing_folder_does_not_fail(self):
        code, out, _ = self.run_main("--diagnose", self.data)
        self.assertEqual(code, 0)
        self.assertIn("missing or cannot be read", out)
        self.assertIn("none (no readable database)", out)


class Script(Tmp):
    def setUp(self):
        super().setUp()
        self.bin = Path(self.tmp) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp) / "docker.log"
        stub = self.bin / "docker"
        stub.write_text('#!/bin/sh\necho "$@" >> "$DOCKER_LOG"\n', encoding="utf-8")
        stub.chmod(0o755)

    def run_script(self, name, *args):
        env = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": self.tmp, "DOCKER_LOG": str(self.log), "CLARK_DATA_DIR": self.data}
        return subprocess.run(["bash", str(ROOT / "docker" / name), *args], env=env, capture_output=True, text=True, cwd=self.tmp, timeout=60)

    def test_newer_data_stops_start_before_docker_is_reached(self):
        make_db(self.data, sc.SCHEMA_VERSION + 1).close()
        r = self.run_script("start.command")
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn("CLARK_DATA_DIR", r.stderr)
        self.assertFalse(self.log.exists(), "docker must not be run")

    def test_current_data_starts_compose(self):
        make_db(self.data, sc.SCHEMA_VERSION).close()
        r = self.run_script("start.command")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("up -d", self.log.read_text(encoding="utf-8"))

    def test_diagnose_command_shows_folder_container_and_logs(self):
        make_db(self.data, sc.SCHEMA_VERSION).close()
        r = self.run_script("diagnose.command")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"Data folder: {self.data}", r.stdout)
        calls = self.log.read_text(encoding="utf-8")
        self.assertIn("ps", calls)
        self.assertIn("logs --tail 20", calls)
        self.assertNotIn("up", calls)


if __name__ == "__main__":
    unittest.main()

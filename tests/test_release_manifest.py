"""clark-release.json, the manifest package.py writes into the download (#109, the writer only).

Builds into a temporary folder only. Run: python3 dev/run_tests.py test_release_manifest
"""
import contextlib
import hashlib
import io
import json
import os
import shutil
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT
import package
import clark.release_files as release_files


def check(zf, top):
    """Re-check a zip against its own manifest; the problems found (empty when whole)."""
    doc = json.loads(zf.read(f"{top}/{package.MANIFEST}"))
    problems = []
    inside = {n[len(top) + 1:] for n in zf.namelist()} - {package.MANIFEST}
    if inside != set(doc["files"]):
        problems.append("list differs")
    for name, row in doc["files"].items():
        data = zf.read(f"{top}/{name}")
        if hashlib.sha256(data).hexdigest() != row["sha256"] or len(data) != row["size"]:
            problems.append(name)
    return problems


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="clark manifest ")
        cls.zip = package.build("mac", Path(cls.tmp) / "one", dirty=True)
        cls.top = package.top_folder()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def doc(self):
        with zipfile.ZipFile(self.zip) as z:
            return json.loads(z.read(f"{self.top}/{package.MANIFEST}"))

    def test_lists_exactly_the_files_in_the_zip_and_not_itself(self):
        with zipfile.ZipFile(self.zip) as z:
            names = {n[len(self.top) + 1:] for n in z.namelist()}
        self.assertIn(package.MANIFEST, names)
        self.assertEqual(names - {package.MANIFEST}, set(self.doc()["files"]))
        self.assertNotIn(package.MANIFEST, self.doc()["files"])

    def test_checksums_sizes_and_modes_are_right(self):
        with zipfile.ZipFile(self.zip) as z:
            for name, row in self.doc()["files"].items():
                with self.subTest(name=name):
                    data = z.read(f"{self.top}/{name}")
                    self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
                    self.assertEqual(len(data), row["size"])
                    self.assertEqual("755" if name in package.RUN_BIT else "644", row["mode"])

    def test_version_and_system_match_the_source(self):
        doc = self.doc()
        init = (ROOT / "src" / "clark" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'__version__ = "{doc["version"]}"', init)
        self.assertEqual(("clark", "mac"), (doc["product"], doc["system"]))
        self.assertRegex(doc["released"], r"^\d{4}-\d{2}-\d{2}$")

    def test_a_changed_byte_is_found_by_a_recheck(self):
        with zipfile.ZipFile(self.zip) as z:
            self.assertEqual([], check(z, self.top))
        bad = Path(self.tmp) / "bad.zip"
        with zipfile.ZipFile(self.zip) as old, zipfile.ZipFile(bad, "w") as new:
            for i in old.infolist():
                data = old.read(i)
                if i.filename == self.top + "/README.md":
                    data = data[:-1] + bytes([data[-1] ^ 1])
                new.writestr(i, data)
        with zipfile.ZipFile(bad) as z:
            self.assertEqual(["README.md"], check(z, self.top))

    def test_two_builds_have_the_same_manifest(self):
        other = package.build("mac", Path(self.tmp) / "two", dirty=True)
        with zipfile.ZipFile(self.zip) as a, zipfile.ZipFile(other) as b:
            key = f"{self.top}/{package.MANIFEST}"
            self.assertEqual(a.read(key), b.read(key))


class WhatTheUpdaterReadsTest(unittest.TestCase):
    """The parts of the record the updater relies on, and the build's refusals."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="clark manifest ")
        cls.zip = package.build("mac", Path(cls.tmp) / "one", dirty=True)
        cls.top = package.top_folder()
        with zipfile.ZipFile(cls.zip) as z:
            cls.infos = {i.filename: i for i in z.infolist()}
            cls.manifest = json.loads(z.read(f"{cls.top}/{package.MANIFEST}"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_header(self):
        m = self.manifest
        self.assertEqual(package.schema_version(), m["schema_version"])
        self.assertEqual("0.0.0", m["min_from"])
        self.assertIn("notes", m)

    def test_each_mode_is_the_one_in_the_zip_and_the_record_has_the_ordinary_mode(self):
        for name, row in self.manifest["files"].items():
            with self.subTest(name=name):
                self.assertEqual(int(row["mode"], 8), stat.S_IMODE(self.infos[f"{self.top}/{name}"].external_attr >> 16))
        self.assertEqual(0o644, stat.S_IMODE(self.infos[f"{self.top}/{package.MANIFEST}"].external_attr >> 16))

    def test_every_listed_name_is_one_the_updater_accepts(self):
        for name in self.manifest["files"]:
            with self.subTest(name=name):
                self.assertTrue(release_files.covers("mac", name))

    def test_the_list_lives_only_in_release_files(self):
        source = (ROOT / "dev" / "tools" / "package.py").read_text(encoding="utf-8")
        self.assertNotIn('"vendor/openpyxl/"', source, "package.py reads the list, it does not hold one")
        self.assertIs(package.SHARED, release_files.SHARED)
        self.assertIs(package.SYSTEMS, release_files.SYSTEMS)

    def test_a_file_outside_the_list_is_not_covered(self):
        for rel in ("tests/x.py", "docs/a.md", "dev/other.py", "clark.cmd", ".git/config", "src/clarkish.py", "../x"):
            with self.subTest(rel=rel):
                self.assertFalse(release_files.covers("mac", rel))

    def test_notes_and_min_from_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = package.build("mac", tmp, dirty=True, notes="Fixes a typo.\n", min_from="0.2.0", released="2026-10-27")
            with zipfile.ZipFile(target) as z:
                m = json.loads(z.read(f"{self.top}/{package.MANIFEST}"))
        self.assertEqual(("Fixes a typo.\n", "0.2.0", "2026-10-27"), (m["notes"], m["min_from"], m["released"]))

    def test_a_bad_min_from_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(package.Refused):
            package.build("mac", tmp, dirty=True, min_from="two")

    def test_a_trailing_newline_in_the_version_or_min_from_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(package, "version", return_value="0.3.0\n"), self.assertRaises(package.Refused):
                package.build("mac", tmp, dirty=True, release=True)
            with self.assertRaises(package.Refused):
                package.build("mac", tmp, dirty=True, min_from="0.2.0\n")
            self.assertEqual([], os.listdir(tmp))

    def test_release_refuses_a_dev_version_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(package, "version", return_value="0.3.0.dev1"), self.assertRaises(package.Refused) as said:
                package.build("mac", tmp, dirty=True, release=True)
            self.assertIn("not a release number", str(said.exception))
            self.assertEqual([], os.listdir(tmp))

    def test_release_flag_and_notes_file_on_the_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()), \
                    mock.patch.object(package, "version", return_value="0.3.0.dev1"):
                self.assertEqual(1, package.main(["mac", "--out", tmp, "--dirty", "--release"]))
            self.assertIn("not a release number", err.getvalue())
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(1, package.main(["mac", "--out", tmp, "--dirty", "--notes", str(Path(tmp) / "missing.txt")]))
            self.assertIn("release notes file can't be read", err.getvalue())


if __name__ == "__main__":
    unittest.main()

"""clark-release.json, the manifest package.py writes into the download (#109, the writer only).

Builds into a temporary folder only. Run: python3 dev/run_tests.py test_release_manifest
"""
import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from _paths import ROOT
import package


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


if __name__ == "__main__":
    unittest.main()

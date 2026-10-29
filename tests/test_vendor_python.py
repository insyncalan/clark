"""#34: the bundled Python libraries (vendor/openpyxl, vendor/et_xmlfile) match vendor/manifest.json, the manifest records
each library's version and licence, the files are creaite v2.6.9's own copies, and openpyxl works from vendor/ alone.

Run: python3 tests/test_vendor_python.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dev" / "tools"))
import vendor_manifest as vm  # noqa: E402

MANIFEST = json.loads((vm.VENDOR / vm.MANIFEST).read_text(encoding="utf-8"))


class VendoredFiles(unittest.TestCase):
    def test_every_file_matches_its_hash_and_nothing_else_is_there(self):
        self.assertEqual(vm.problems(), [])

    def test_each_hash_is_the_file_s_sha256(self):
        for name, h in MANIFEST["files"].items():
            self.assertEqual(hashlib.sha256((vm.VENDOR / name).read_bytes()).hexdigest(), h, name)

    def test_a_changed_missing_or_extra_file_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "vendor"
            shutil.copytree(vm.VENDOR, dest, ignore=shutil.ignore_patterns("__pycache__", *vm.OWN_MANIFESTS))
            self.assertEqual(vm.problems(dest), [])
            (dest / "openpyxl" / "__init__.py").write_text("# changed\n", encoding="utf-8")
            (dest / "et_xmlfile" / "xmlfile.py").unlink()
            (dest / "stray.py").write_text("", encoding="utf-8")
            self.assertEqual(vm.problems(dest), ["missing: et_xmlfile/xmlfile.py", "changed: openpyxl/__init__.py",
                                                 "extra: stray.py"])
            (dest / vm.MANIFEST).write_text("{", encoding="utf-8")
            self.assertEqual(len(vm.problems(dest)), 1)
            self.assertTrue(vm.problems(dest)[0].startswith("unreadable: manifest.json"))

    def test_the_front_end_folders_keep_their_own_manifests(self):
        for folder in vm.OWN_MANIFESTS:
            self.assertTrue(list((vm.VENDOR / folder).rglob("manifest.json")), folder)   # fonts/readex-pro/ has its own, one level down
            self.assertFalse(any(n.startswith(folder + "/") for n in MANIFEST["files"]), folder)

    def test_the_manifest_is_the_pins(self):
        self.assertEqual(MANIFEST, vm.manifest(), "run python3 dev/tools/vendor_manifest.py and commit vendor/")
        self.assertEqual(set(MANIFEST["libraries"]), {"openpyxl", "et_xmlfile"})
        for name, lib in MANIFEST["libraries"].items():
            self.assertEqual(lib["licence"], "MIT", name)
            self.assertEqual(lib["licence_file"], f"licenses/{name}-{lib['version']}-LICENSE.txt")
            self.assertIn(lib["licence_file"], MANIFEST["files"])
            self.assertIn("v2.6.9 (db5adb2)", lib["from"])

    def test_the_versions_are_the_libraries_own(self):
        for name, mod in (("openpyxl", "openpyxl/_constants.py"), ("et_xmlfile", "et_xmlfile/__init__.py")):
            text = (vm.VENDOR / mod).read_text(encoding="utf-8")
            self.assertIn(f'"{MANIFEST["libraries"][name]["version"]}"', text.replace("'", '"'), name)


class Works(unittest.TestCase):
    def test_openpyxl_writes_and_reads_a_workbook_from_vendor_alone(self):
        """In a fresh interpreter with only vendor/ on the path (no site packages), a workbook round-trips."""
        code = (
            "import sys, tempfile, os\n"
            "import openpyxl\n"
            "assert openpyxl.__file__.startswith(sys.argv[1]), openpyxl.__file__\n"
            "wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Work items'\n"
            "ws.append(['ID', 'Title']); ws.append(['DEMO-001', 'Agree the plan'])\n"
            "path = os.path.join(tempfile.mkdtemp(), 'demo.xlsx'); wb.save(path)\n"
            "rows = list(openpyxl.load_workbook(path).active.values)\n"
            "assert rows == [('ID', 'Title'), ('DEMO-001', 'Agree the plan')], rows\n"
            "print(openpyxl.__version__)\n")
        run = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, sys.argv[1]); exec({code!r})",
                              str(vm.VENDOR)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), MANIFEST["libraries"]["openpyxl"]["version"])


if __name__ == "__main__":
    unittest.main()

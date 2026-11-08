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

# #891: library: (the wheel's SHA-256 on PyPI, its licence). pypdf 6.21.4 is the newest release that runs on Python 3.9 (7.0 needs 3.10).
PYPI = {"pypdf": ("33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c", "BSD-3-Clause"),
        "typing_extensions": ("481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8", "PSF-2.0")}
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
            self.assertTrue(list((vm.VENDOR / folder).rglob("manifest.json")), folder)   # fonts/inter/ and fonts/montserrat/ have their own, one level down
            self.assertFalse(any(n.startswith(folder + "/") for n in MANIFEST["files"]), folder)

    def test_the_manifest_is_the_pins(self):
        self.assertEqual(MANIFEST, vm.manifest(), "run python3 dev/tools/vendor_manifest.py and commit vendor/")
        self.assertEqual(set(MANIFEST["libraries"]), {"openpyxl", "et_xmlfile", "ed25519_verify", "pypdf", "typing_extensions"})
        for name, lib in MANIFEST["libraries"].items():
            own = name == "ed25519_verify"       # written for clark from RFC 8032, public domain; openpyxl and et_xmlfile are creaite's copies
            pypi = name in PYPI                  # pypdf and typing_extensions come from PyPI wheels, pinned by the wheel's SHA-256 (#891)
            self.assertEqual(lib["licence"], "CC0-1.0" if own else PYPI[name][1] if pypi else "MIT", name)
            self.assertEqual(lib["licence_file"], f"licenses/{name}-{lib['version']}-LICENSE.txt")
            self.assertIn(lib["licence_file"], MANIFEST["files"])
            self.assertIn("RFC 8032" if own else PYPI[name][0] if pypi else "v2.6.9 (db5adb2)", lib["from"])

    def test_the_versions_are_the_libraries_own(self):
        for name, mod in (("openpyxl", "openpyxl/_constants.py"), ("et_xmlfile", "et_xmlfile/__init__.py")):
            text = (vm.VENDOR / mod).read_text(encoding="utf-8")
            self.assertIn(f'"{MANIFEST["libraries"][name]["version"]}"', text.replace("'", '"'), name)


class Pypdf(unittest.TestCase):
    """#891: pypdf and the one library it needs on Python 3.9 (typing_extensions) are bundled, pinned and licensed."""

    def test_the_wheel_hashes_are_recorded(self):
        for name, (wheel_sha, _lic) in PYPI.items():
            self.assertIn(wheel_sha, MANIFEST["libraries"][name]["from"], name)
        self.assertEqual((MANIFEST["libraries"]["pypdf"]["version"], MANIFEST["libraries"]["typing_extensions"]["version"]),
                         ("6.21.4", "4.16.0"))

    def test_the_versions_are_the_libraries_own(self):
        self.assertIn('__version__ = "6.21.4"', (vm.VENDOR / "pypdf" / "_version.py").read_text(encoding="utf-8"))
        self.assertIn("typing_extensions.py", MANIFEST["files"])
        self.assertFalse(list(vm.VENDOR.glob("*.dist-info")), "only the package files are bundled")

    def test_the_licences_are_shipped_and_say_what_they_are(self):
        pypdf = (vm.VENDOR / MANIFEST["libraries"]["pypdf"]["licence_file"]).read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2006-2008, Mathieu Fenniak", pypdf)
        self.assertIn("Redistributions of source code must retain", pypdf)
        te = (vm.VENDOR / MANIFEST["libraries"]["typing_extensions"]["licence_file"]).read_text(encoding="utf-8")
        self.assertIn("PYTHON SOFTWARE FOUNDATION LICENSE VERSION 2", te)
        sys.path.insert(0, str(REPO / "src"))
        try:
            from clark import release_files
        finally:
            sys.path.pop(0)
        for name in ("vendor/pypdf/", "vendor/typing_extensions.py", "vendor/licenses/", "vendor/manifest.json"):
            self.assertIn(name, release_files.SHARED)

    def test_one_changed_byte_in_pypdf_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "vendor"
            shutil.copytree(vm.VENDOR, dest, ignore=shutil.ignore_patterns("__pycache__", *vm.OWN_MANIFESTS))
            self.assertEqual(vm.problems(dest), [])
            f = dest / "pypdf" / "_reader.py"
            data = bytearray(f.read_bytes())
            data[100] ^= 1
            f.write_bytes(bytes(data))
            self.assertEqual(vm.problems(dest), ["changed: pypdf/_reader.py"])
            (dest / "typing_extensions.py").unlink()
            self.assertIn("missing: typing_extensions.py", vm.problems(dest))

    def test_every_pypdf_module_loads_from_vendor_alone(self):
        """In a fresh interpreter with no site packages, every module in pypdf imports, so nothing else is needed (the three that wrap an optional library, which clark does not use, are allowed to say so)."""
        code = ("import sys, pkgutil, importlib\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "import pypdf\n"
                "assert pypdf.__file__.startswith(sys.argv[1]), pypdf.__file__\n"
                "OPTIONAL = {'pypdf._crypt_providers._cryptography', 'pypdf._crypt_providers._pycryptodome', 'pypdf.generic._image_xobject'}\n"
                "for m in pkgutil.walk_packages(pypdf.__path__, 'pypdf.'):\n"
                "    try: importlib.import_module(m.name)\n"
                "    except ImportError as e:\n"
                "        assert m.name in OPTIONAL, (m.name, e)   # the three that need cryptography, pycryptodome or pillow, which clark does not bundle\n"
                "import typing_extensions; assert typing_extensions.__file__.startswith(sys.argv[1])\n"
                "print(pypdf.__version__)\n")
        run = subprocess.run([sys.executable, "-I", "-S", "-c", code, str(vm.VENDOR)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), MANIFEST["libraries"]["pypdf"]["version"])


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

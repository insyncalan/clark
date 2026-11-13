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
            self.assertTrue(list((vm.VENDOR / folder).rglob("manifest.json")), folder)   # fonts/inter/ and fonts/montserrat/ have their own, one level down
            self.assertFalse(any(n.startswith(folder + "/") for n in MANIFEST["files"]), folder)

    def test_the_manifest_is_the_pins(self):
        self.assertEqual(MANIFEST, vm.manifest(), "run python3 dev/tools/vendor_manifest.py and commit vendor/")
        self.assertEqual(set(MANIFEST["libraries"]), {"openpyxl", "et_xmlfile", "ed25519_verify", "pypdf", "typing_extensions"})
        for name, lib in MANIFEST["libraries"].items():
            if name in THIRD_PARTY_PYPI:
                continue                         # pypdf and typing_extensions: PyPI wheels, checked in PypiWheels below
            own = name == "ed25519_verify"       # written for clark from RFC 8032, public domain; the others are creaite's copies
            self.assertEqual(lib["licence"], "CC0-1.0" if own else "MIT", name)
            self.assertEqual(lib["licence_file"], f"licenses/{name}-{lib['version']}-LICENSE.txt")
            self.assertIn(lib["licence_file"], MANIFEST["files"])
            self.assertIn("RFC 8032" if own else "v2.6.9 (db5adb2)", lib["from"])

    def test_the_versions_are_the_libraries_own(self):
        for name, mod in (("openpyxl", "openpyxl/_constants.py"), ("et_xmlfile", "et_xmlfile/__init__.py")):
            text = (vm.VENDOR / mod).read_text(encoding="utf-8")
            self.assertIn(f'"{MANIFEST["libraries"][name]["version"]}"', text.replace("'", '"'), name)


# #891: copied unchanged from the PyPI wheel (the wheel's SHA-256 is pinned), not from creaite.
THIRD_PARTY_PYPI = {"pypdf": ("6.21.4", "BSD-3-Clause", "pypdf/LICENSE", "pypdf-6.21.4-py3-none-any.whl",
                              "33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c"),
                    "typing_extensions": ("4.16.0", "PSF-2.0", "licenses/typing_extensions-4.16.0-LICENSE.txt",
                                          "typing_extensions-4.16.0-py3-none-any.whl",
                                          "481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8")}


class PypiWheels(unittest.TestCase):
    def test_pypdf_and_its_one_dependency_are_pinned_to_the_wheel_they_came_from(self):
        for name, (version, licence, lic_file, wheel, sha) in THIRD_PARTY_PYPI.items():
            with self.subTest(name):
                lib = MANIFEST["libraries"][name]
                self.assertEqual((lib["version"], lib["licence"], lib["licence_file"]), (version, licence, lic_file))
                self.assertIn(wheel, lib["from"])
                self.assertIn(sha, lib["from"])
                self.assertIn("pypi.org", lib["from"])
                self.assertIn(lib["licence_file"], MANIFEST["files"])

    def test_pypdf_s_folder_says_what_it_is_and_where_it_came_from(self):
        text = (vm.VENDOR / "pypdf" / "VENDORED.md").read_text(encoding="utf-8")
        for needle in ("6.21.4", "pypi.org/project/pypdf/6.21.4", "33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c",
                       "BSD-3-Clause", "typing_extensions", "unchanged"):
            self.assertIn(needle, text)

    def test_the_versions_are_the_libraries_own_and_the_licences_are_the_real_ones(self):
        self.assertIn('__version__ = "6.21.4"', (vm.VENDOR / "pypdf" / "_version.py").read_text(encoding="utf-8"))
        self.assertIn("Redistribution and use in source and binary forms", (vm.VENDOR / "pypdf" / "LICENSE").read_text(encoding="utf-8"))
        self.assertIn("PYTHON SOFTWARE FOUNDATION LICENSE", (vm.VENDOR / "licenses" / "typing_extensions-4.16.0-LICENSE.txt").read_text(encoding="utf-8").upper())

    def test_pypdf_needs_nothing_else_on_python_3_9(self):
        """Its only dependency on 3.9 (typing_extensions) is the vendored single file; the same wheel metadata is recorded."""
        self.assertTrue((vm.VENDOR / "typing_extensions.py").is_file())
        self.assertFalse(list(vm.VENDOR.glob("pypdf/**/*.so")) + list(vm.VENDOR.glob("pypdf/**/*.pyd")), "pure Python only")


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


class NoticeAndPypdf(unittest.TestCase):
    """#891: NOTICE.md lists pypdf and typing_extensions with their licence, and pypdf reads a PDF from vendor/ alone."""
    NOTICE = (REPO / "NOTICE.md").read_text(encoding="utf-8")

    def test_notice_lists_each_new_library_with_version_licence_and_licence_file(self):
        rows = {l.split("|")[1].strip().split(" ")[0]: l for l in self.NOTICE.splitlines() if l.startswith("| ")}
        for name, (version, licence, lic_file, _, _) in THIRD_PARTY_PYPI.items():
            with self.subTest(name):
                self.assertIn(name, rows)
                for needle in (version, licence, "vendor/", lic_file.split("/")[-1]):
                    self.assertIn(needle, rows[name])

    def test_pypdf_licence_is_given_by_reference_and_is_the_bsd_text_in_the_folder(self):
        self.assertIn("licence file vendor/pypdf/LICENSE", self.NOTICE)
        lic = (vm.VENDOR / "pypdf" / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Redistribution and use in source and binary forms", lic)
        self.assertIn("The name of the author may not be used to endorse", lic)

    def test_every_licence_file_named_in_the_manifest_exists_and_is_hashed(self):
        for name, lib in MANIFEST["libraries"].items():
            with self.subTest(name):
                self.assertTrue((vm.VENDOR / lib["licence_file"]).is_file())
                self.assertIn(lib["licence_file"], MANIFEST["files"])

    def test_pypdf_reads_the_text_of_a_pdf_from_vendor_alone(self):
        code = (
            "import sys, io\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from pypdf import PdfReader\n"
            "import pypdf, typing_extensions\n"
            "assert pypdf.__file__.startswith(sys.argv[1]), pypdf.__file__\n"
            "objs = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',\n"
            "  b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',\n"
            "  None, b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']\n"
            "stream = b'BT /F1 12 Tf 20 100 Td (Hello pypdf) Tj ET'\n"
            "objs[3] = b'<< /Length %d >>\\nstream\\n' % len(stream) + stream + b'\\nendstream'\n"
            "out = b'%PDF-1.4\\n'; offs = []\n"
            "for i, o in enumerate(objs, 1):\n"
            "    offs.append(len(out)); out += b'%d 0 obj\\n' % i + o + b'\\nendobj\\n'\n"
            "x = len(out); out += b'xref\\n0 %d\\n0000000000 65535 f \\n' % (len(objs) + 1)\n"
            "for o in offs: out += b'%010d 00000 n \\n' % o\n"
            "out += b'trailer\\n<< /Size %d /Root 1 0 R >>\\nstartxref\\n%d\\n%%%%EOF' % (len(objs) + 1, x)\n"
            "print(PdfReader(io.BytesIO(out)).pages[0].extract_text().strip())\n")
        run = subprocess.run([sys.executable, "-I", "-S", "-c", code, str(vm.VENDOR)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "Hello pypdf")


if __name__ == "__main__":
    unittest.main()

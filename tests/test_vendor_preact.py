"""#34 (creaite BL-256): the vendored Preact and signals (vendor/preact/) match their manifest, and the pins and licences
are recorded. creaite's build tests (each library import maps to a vendored file) come across with the page build in #35.

Run: python3 tests/test_vendor_preact.py
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dev" / "tools"))
import vendor_preact as vp  # noqa: E402

MANIFEST = json.loads(vp.MANIFEST.read_text(encoding="utf-8"))


class VendoredFiles(unittest.TestCase):
    def test_every_file_matches_its_hash_and_nothing_else_is_there(self):
        self.assertEqual(vp.problems(), [])

    def test_a_changed_file_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "preact"
            for name in [*MANIFEST["files"], "manifest.json"]:
                (dest / name).parent.mkdir(parents=True, exist_ok=True)
                (dest / name).write_bytes((vp.VENDOR / name).read_bytes())
            self.assertEqual(vp.problems(dest), [])
            (dest / "preact/dist/preact.module.js").write_text("// changed\n", encoding="utf-8")
            (dest / "stray.js").write_text("", encoding="utf-8")
            self.assertEqual(vp.problems(dest), ["changed: preact/dist/preact.module.js", "extra: stray.js"])

    def test_the_manifest_is_the_pins(self):
        for pkg, (folder, version, tgz, sha, released) in vp.PINS.items():
            m = MANIFEST["packages"][pkg]
            self.assertEqual((m["folder"], m["version"], m["sha256"], m["released"], m["licence"]),
                             (folder, version, sha, released, "MIT"))
            self.assertEqual(m["tarball"], f"https://registry.npmjs.org/{pkg}/-/{tgz}")
            self.assertIn(f"{folder}/LICENSE", MANIFEST["files"])
            self.assertIn("MIT License", (vp.VENDOR / folder / "LICENSE").read_text(encoding="utf-8"))
        self.assertEqual(MANIFEST["modules"], vp.MODULES)

    def test_each_hash_is_the_file_s_sha256(self):
        for name, h in MANIFEST["files"].items():
            self.assertEqual(hashlib.sha256((vp.VENDOR / name).read_bytes()).hexdigest(), h, name)


if __name__ == "__main__":
    unittest.main()

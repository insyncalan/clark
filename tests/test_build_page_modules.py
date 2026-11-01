"""#236: build_page.py takes vendor/preact/manifest.json as data. A module that points outside the vendor folder, at a file the
manifest does not list, at a file whose fingerprint differs, or with a specifier that could reach the esbuild command line
stops the build in plain words and no page is written.

Run: python3 dev/run_tests.py test_build_page_modules
Everything is built in a temporary folder; the "secret" is a made-up file. Runs on Python 3.9 and later.
"""
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401  (puts dev/tools/ on the path)
import build_page as bp

BODY = b"export const x = 1;\n"


def sha(b):
    return hashlib.sha256(b).hexdigest()


class VendorManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.vendor = self.tmp / "vendor" / "preact"
        (self.vendor / "lib").mkdir(parents=True)
        (self.vendor / "lib" / "a.js").write_bytes(BODY)
        self.secret = self.tmp / "secret.js"
        self.secret.write_bytes(b"export const stolen = 1;\n")

    def manifest(self, modules=None, files=None):
        data = {"modules": {"preact": "lib/a.js"} if modules is None else modules,
                "files": {"lib/a.js": sha(BODY)} if files is None else files}
        (self.vendor / "manifest.json").write_text(json.dumps(data), encoding="utf-8")

    def refused(self, **kw):
        self.manifest(**kw)
        with self.assertRaises(bp.VendorManifestError) as ctx:
            bp.vendor_modules(self.vendor)
        message = str(ctx.exception)
        self.assertNotIn(str(self.tmp), message, "the error names the manifest entry, never a resolved path")
        self.assertIn("manifest.json", message)
        return message

    def test_a_normal_manifest_builds(self):
        self.manifest()
        self.assertEqual(bp.vendor_modules(self.vendor), [("preact", os.path.realpath(self.vendor / "lib" / "a.js"))])

    def test_absolute_path(self):
        self.assertIn("absolute", self.refused(modules={"preact": str(self.secret)}, files={str(self.secret): sha(self.secret.read_bytes())}))

    def test_dot_dot(self):
        p = "../../secret.js"
        self.assertIn("'..'", self.refused(modules={"preact": p}, files={p: sha(self.secret.read_bytes())}))

    def test_symlink_out(self):
        os.symlink(self.secret, self.vendor / "lib" / "link.js")
        self.assertIn("link", self.refused(modules={"preact": "lib/link.js"}, files={"lib/link.js": sha(self.secret.read_bytes())}))

    def test_symlinked_folder_out(self):
        os.symlink(self.tmp, self.vendor / "out")
        self.assertIn("link", self.refused(modules={"preact": "out/secret.js"}, files={"out/secret.js": sha(self.secret.read_bytes())}))

    def test_path_not_in_files(self):
        (self.vendor / "lib" / "b.js").write_bytes(BODY)
        self.assertIn("'files' entries", self.refused(modules={"preact": "lib/b.js"}))

    def test_hash_mismatch(self):
        (self.vendor / "lib" / "a.js").write_bytes(BODY + b"// changed\n")
        self.assertIn("sha256", self.refused())

    def test_bad_hash_shape(self):
        self.assertIn("sha256", self.refused(files={"lib/a.js": "nothex"}))

    def test_not_a_regular_file(self):
        (self.vendor / "lib" / "d.js").mkdir()
        self.assertIn("regular", self.refused(modules={"preact": "lib/d.js"}, files={"lib/d.js": sha(b"")}))

    def test_specifier_injection(self):
        for bad in ("pre act", "a=/etc/passwd", "-x", '"preact', "a'b", "preact\n", "Preact", "a;b", "", "a" * 102):
            with self.subTest(spec=bad):
                self.assertIn("specifier", self.refused(modules={bad: "lib/a.js"}))

    def test_a_refused_module_writes_no_page(self):
        self.manifest(modules={"preact": str(self.secret)})
        out, out_view = self.tmp / "page.html", self.tmp / "page-view.html"
        out.write_text("old", encoding="utf-8")
        with mock.patch.object(bp, "VENDOR", self.vendor), mock.patch.object(bp, "OUT", out), \
                mock.patch.object(bp, "OUT_VIEW", out_view), mock.patch("sys.stderr"):
            self.assertEqual(bp.main([]), 1)
        self.assertEqual(out.read_text(encoding="utf-8"), "old")
        self.assertFalse(out_view.exists())

    def test_the_real_manifest_is_accepted(self):
        self.assertEqual(len(bp.vendor_modules()), 5)
        self.assertEqual(bp.main(["--check"]), 0)


if __name__ == "__main__":
    unittest.main()

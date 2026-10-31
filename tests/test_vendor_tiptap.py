"""BL-301 A: the vendored Tiptap editor (vendor/tiptap/) matches its manifest, the manifest records the
pins and a licence for every bundled package, and the committed folder is byte for byte a fresh build of dev/tiptap/.

Run: python3 tests/test_vendor_tiptap.py
The fresh-build test runs only when `python3 dev/tools/tiptap.py fetch` has filled dev/.cache (it never downloads
anything); every other test reads the committed files only, so CI always runs them.
"""
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "dev" / "tools"))
import esbuild  # noqa: E402
import tiptap  # noqa: E402

MANIFEST = json.loads((tiptap.VENDOR / tiptap.MANIFEST).read_text(encoding="utf-8"))


class Committed(unittest.TestCase):
    """What CI can always check: the committed files against their own manifest and the pins."""

    def test_every_file_matches_its_hash_and_nothing_else_is_there(self):
        self.assertEqual(tiptap.manifest_problems(), [])

    def test_each_hash_is_the_file_s_sha256(self):
        for name, h in MANIFEST["files"].items():
            self.assertEqual(hashlib.sha256((tiptap.VENDOR / name).read_bytes()).hexdigest(), h, name)

    def test_a_changed_missing_or_extra_file_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "tiptap"
            shutil.copytree(tiptap.VENDOR, dest)
            self.assertEqual(tiptap.manifest_problems(dest), [])
            (dest / tiptap.MODULE).write_text("// changed\n", encoding="utf-8")
            (dest / "licenses" / "marked-17.0.6-LICENSE.md").unlink()
            (dest / "stray.js").write_text("", encoding="utf-8")
            self.assertEqual(tiptap.manifest_problems(dest), ["missing: licenses/marked-17.0.6-LICENSE.md",
                                                              f"changed: {tiptap.MODULE}", "extra: stray.js"])
            (dest / tiptap.MANIFEST).write_text("{", encoding="utf-8")
            self.assertEqual(tiptap.manifest_problems(dest), [f"unreadable: {tiptap.MANIFEST}"])

    def test_the_manifest_is_the_pins(self):
        self.assertEqual(MANIFEST["tiptap"], tiptap.PINNED)
        self.assertEqual(MANIFEST["build"]["esbuild"], esbuild.PINNED)
        self.assertEqual(MANIFEST["build"]["format"], "esm")
        pins = {name: (version, sha) for name, version, sha in tiptap.PACKAGES}
        for name, m in MANIFEST["packages"].items():
            self.assertEqual((m["version"], m["sha256"]), pins[name], name)
            self.assertEqual(m["tarball"], tiptap.tarball_url(name, m["version"]))

    def test_every_bundled_package_has_its_licence(self):
        """Tiptap, ProseMirror, marked, linkifyjs and the rest: MIT, each with its own licence file beside the bundle."""
        for must in ("@tiptap/core", "@tiptap/markdown", "@tiptap/pm", "prosemirror-model", "prosemirror-view",
                     "prosemirror-tables", "marked", "linkifyjs", "orderedmap", "rope-sequence", "w3c-keyname"):
            self.assertIn(must, MANIFEST["packages"])
        for name, m in MANIFEST["packages"].items():
            self.assertEqual(m["licence"], "MIT", name)
            self.assertTrue(m["licence_files"], name)
            for f in m["licence_files"]:
                self.assertIn(f, MANIFEST["files"])
                self.assertRegex(f, r"^licenses/[a-z0-9.-]+-" + re.escape(m["version"]) + r"-")
                text = (tiptap.VENDOR / f).read_text(encoding="utf-8")
                self.assertIn("MIT", text, f)
        self.assertIn("ProseMirror", (tiptap.VENDOR / "licenses" / "tiptap-pm-3.31.3-THIRD_PARTY_LICENSES.md")
                      .read_text(encoding="utf-8"))

    def test_the_module_is_from_today_s_sources(self):
        """The writer or the editor changed without a rebuild is caught here, without a build (and so on CI)."""
        for path, h in MANIFEST["build"]["sources"].items():
            self.assertEqual(hashlib.sha256((REPO / path).read_bytes()).hexdigest(), h,
                             f"{path} changed: run python3 dev/tools/tiptap.py vendor and commit the folder")
        self.assertEqual(sorted(MANIFEST["build"]["sources"]), sorted(tiptap.SOURCES))

    def test_the_module_exports_the_editor_api(self):
        text = (tiptap.VENDOR / tiptap.MODULE).read_text(encoding="utf-8")
        exports = re.search(r"export\{([^}]*)\};?\s*$", text)
        self.assertTrue(exports, "the module ends with its export list")
        names = {part.split(" as ")[-1].strip() for part in exports.group(1).split(",")}
        self.assertEqual(names, set(MANIFEST["exports"]))
        self.assertEqual(MANIFEST["build"]["bytes"], len(text.encode("utf-8")))
        self.assertNotIn(str(REPO), text)
        self.assertNotIn("/Users/", text)
        self.assertNotIn("sourceMappingURL", text)


class Helpers(unittest.TestCase):
    def test_package_of(self):
        self.assertEqual(tiptap._package_of("dev/.cache/tiptap/3.31.3/node_modules/@tiptap/core/dist/index.js"),
                         "@tiptap/core")
        self.assertEqual(tiptap._package_of("../x/node_modules/marked/lib/marked.esm.js"), "marked")
        self.assertIsNone(tiptap._package_of("dev/tiptap/writer.js"))

    def test_a_package_that_isn_t_pinned_is_refused(self):
        meta = {"inputs": {"dev/tiptap/editor.js": {}, "node_modules/marked/lib/marked.esm.js": {},
                           "node_modules/left-pad/index.js": {}}}
        with self.assertRaises(tiptap.TiptapError):
            tiptap.bundled_packages(meta)
        del meta["inputs"]["node_modules/left-pad/index.js"]
        self.assertEqual(tiptap.bundled_packages(meta), ["marked"])

    def test_compare(self):
        self.assertEqual(tiptap.compare({"a": b"1", "b": b"2"}, {"b": b"3", "c": b"4"}),
                         ["missing: a", "changed: b", "extra: c"])


@unittest.skipUnless(tiptap.is_cached(), "needs the pinned Tiptap and esbuild in dev/.cache (python3 dev/tools/tiptap.py fetch)")
class FreshBuild(unittest.TestCase):
    """The committed folder is exactly what `tiptap.py vendor` builds today: module, licences and manifest."""

    def test_the_committed_folder_is_a_fresh_build(self):
        self.assertEqual(tiptap.fresh_build_problems(), [],
                         "run python3 dev/tools/tiptap.py vendor and commit vendor/tiptap/")

    def test_the_build_is_repeatable(self):
        self.assertEqual(tiptap.vendor_files(), tiptap.vendor_files())


if __name__ == "__main__":
    unittest.main()

"""The Windows download that dev/tools/package.py builds (item 624): the clark folder, docker/ and the runtime image tar,
and nothing that runs by itself on Windows. Builds into temporary folders only. Run: python3 dev/run_tests.py test_package_windows
"""
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from _paths import ROOT
import package
from clark import release_files, updates
from test_package import starts_with_product_name


class WindowsZipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.zip = package.build("windows", cls.tmp.name, dirty=True)
        with zipfile.ZipFile(cls.zip) as z:
            cls.names = z.namelist()
            cls.text = z.read("clark/START-HERE.md").decode("utf-8")
            cls.manifest = json.loads(z.read("clark/clark-release.json"))
            cls.tar = z.read("clark/docker/clark-runtime.tar")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_no_exe_cmd_or_python_folder(self):
        for name in self.names:
            with self.subTest(name=name):
                self.assertIsNone(re.search(r"\.(exe|cmd|bat|dll)\Z", name, re.I))
                self.assertNotIn("python", [part.lower() for part in name.split("/")[:-1]])
                self.assertNotEqual("python.exe", name.rsplit("/", 1)[-1].lower())

    def test_the_guard_refuses_what_a_zip_must_not_hold(self):
        for bad in ("clark/clark.cmd", "clark/x/python.exe", "clark/python/lib.py", "clark/.app/a.EXE"):
            with self.subTest(bad=bad), self.assertRaises(package.Refused):
                package.assert_no_native_windows("windows", {bad: (b"x", 0o644)})
        package.assert_no_native_windows("mac", {"clark/clark.cmd": (b"x", 0o644)})

    def test_what_it_holds(self):
        self.assertIn("clark/docker/compose.yaml", self.names)
        self.assertIn("clark/docker/clark-runtime.tar", self.names)
        self.assertIn("clark/README.md", self.names)
        self.assertNotIn("clark/clark.command", self.names)
        self.assertEqual("windows", self.manifest["system"])
        self.assertIn("docker/clark-runtime.tar", self.manifest["files"])

    def test_the_updaters_coverage_check_passes(self):
        updates.check_coverage("windows", [n.split("/", 1)[1] for n in self.names])

    def test_start_here_types_the_commands(self):
        self.assertIn("docker load -i docker\\clark-runtime.tar", self.text)
        self.assertIn("docker compose -f docker/compose.yaml up -d", self.text)
        self.assertIn("localhost:8766", self.text)
        self.assertEqual([], starts_with_product_name(self.text))
        self.assertNotIn("clark.command", self.text)
        self.assertNotIn("Mac", self.text)

    def test_a_placeholder_tar_is_refused_in_a_release(self):
        self.assertEqual(package.IMAGE_PLACEHOLDER, self.tar)
        with self.assertRaises(package.Refused) as said:
            package.download_content("windows", package.ROOT, release=True, dirty=False)
        self.assertTrue("--image-tar" in str(said.exception) or "tag" in str(said.exception))

    def test_a_given_tar_goes_in_as_it_is(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar = Path(tmp) / "image.tar"
            tar.write_bytes(b"the image bytes")
            content = package.download_content("windows", dirty=True, image_tar=tar)
        self.assertEqual(b"the image bytes", content["clark/docker/clark-runtime.tar"][0])

    def test_the_mac_list_is_not_changed(self):
        self.assertNotIn("docker/clark-runtime.tar", release_files.listed("mac"))
        self.assertEqual(set(), release_files.NOT_BUILT_YET)


if __name__ == "__main__":
    unittest.main()

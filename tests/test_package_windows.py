"""The Windows download that dev/tools/package.py builds (item 624): the clark folder, docker/ and the runtime image tar,
and nothing that runs by itself on Windows. Builds into temporary folders only. Run: python3 dev/run_tests.py test_package_windows
"""
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

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

    def test_the_placeholder_is_what_a_build_without_a_tar_holds(self):
        self.assertEqual(package.IMAGE_PLACEHOLDER, self.tar)

    def test_a_release_without_a_tar_is_refused_for_the_tar(self):
        with mock.patch.object(package, "tag_problem", return_value=None), mock.patch.object(package, "uncommitted", return_value=""), \
                self.assertRaises(package.Refused) as said:
            package.download_content("windows", package.ROOT, release=True)
        self.assertIn("--image-tar", str(said.exception))

    def test_a_native_file_in_an_extra_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "intake"
            folder.mkdir()
            (folder / "run.cmd").write_bytes(b"x")
            with self.assertRaises(package.Refused):
                package.download_content("windows", dirty=True, extra_folders=[str(folder)])

    def test_the_guard_leaves_alone_names_that_only_start_with_python(self):
        for fine in ("clark/docs/python-notes.md", "clark/pythonic.py", "clark/docs/python-style/a.md"):
            with self.subTest(fine=fine):
                package.assert_no_native_windows("windows", {fine: (b"x", 0o644)})
        for bad in ("clark/python3/a.py", "clark/python3.12/a.py", "clark/python"):
            with self.subTest(bad=bad), self.assertRaises(package.Refused):
                package.assert_no_native_windows("windows", {bad: (b"x", 0o644)})

    def test_a_system_with_no_download_is_refused(self):
        with self.assertRaises(package.Refused) as said:
            package.download_content("linux", dirty=True)
        self.assertIn("Choose mac or windows", str(said.exception))

    def test_the_tar_option_reaches_the_build_through_main(self):
        with tempfile.TemporaryDirectory() as tmp:
            tar = Path(tmp) / "image.tar"
            tar.write_bytes(b"the image bytes")
            code = package.main(["windows", "--dirty", "--image-tar", str(tar), "--out", str(Path(tmp) / "out")])
            self.assertEqual(0, code)
            with zipfile.ZipFile(next((Path(tmp) / "out").glob("*.zip"))) as z:
                self.assertEqual(b"the image bytes", z.read("clark/docker/clark-runtime.tar"))

    def test_entries_match_the_zip(self):
        self.assertEqual(sorted(n for n in self.names if n != "clark/clark-release.json"), package.entries("windows"))

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

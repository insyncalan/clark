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
        for bad in ("clark/clark.cmd", "clark/x/python.exe", "clark/python/lib.py", "clark/.app/a.EXE",
                    "clark/run.bat", "clark/x/lib.DLL"):
            with self.subTest(bad=bad), self.assertRaises(package.Refused):
                package.assert_no_native_windows("windows", {bad: (b"x", 0o644)})
        package.assert_no_native_windows("mac", {"clark/clark.cmd": (b"x", 0o644)})

    def test_the_refusal_names_five_of_the_bad_files_and_a_linux_build_is_not_asked(self):
        bad = {f"clark/run{n}.cmd": (b"x", 0o644) for n in range(7)}
        with self.assertRaises(package.Refused) as said:
            package.assert_no_native_windows("windows", bad)
        self.assertEqual(str(said.exception).count("clark/run"), 5)
        package.assert_no_native_windows("linux", bad)

    def test_the_generated_tar_is_not_counted_as_a_changed_file(self):
        def status(root, paths):
            return "".join(f" M {p}\n" for p in paths if p == release_files.IMAGE_TAR)
        with mock.patch.object(package, "uncommitted", status):
            names = package.download_content("windows", package.ROOT)
        self.assertTrue(any(n.endswith(release_files.IMAGE_TAR) for n in names))

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
        self.assertIn("docker compose -f docker/compose.yaml -f docker/compose.windows.yaml up -d", self.text)
        self.assertIn("127.0.0.1:8766", self.text)
        self.assertEqual([], starts_with_product_name(self.text))
        self.assertNotIn("clark.command", self.text)
        self.assertNotIn("Mac", self.text)

    def test_start_here_keeps_the_data_outside_the_clark_folder(self):
        """Item 624: compose.yaml says the data is NOT in the clark folder, so swapping the folder cannot lose it; the Windows text must agree."""
        self.assertIn("a folder called clark-data, beside this folder and not in\nit", self.text)
        self.assertNotIn("CLARK_DATA_DIR", self.text)
        # Item 633, ruled 16-11 (WO-M3672, NEW-WORDS.md): the update sentence matches step 2 of docker/UPDATE-windows.txt.
        flat = " ".join(self.text.split())
        self.assertIn("To update, rename this folder to clark-old, then unzip the newer download into the folder that held it, so clark-data is found again.", flat)
        self.assertIn("so replacing this folder with a newer download cannot lose it.", flat)
        self.assertNotIn("Unzip a newer download beside this folder", flat)
        for inside in ("$PWD", "%CD%", "\\data\""):
            self.assertNotIn(inside, self.text)

    def test_the_placeholder_is_what_a_build_without_a_tar_holds(self):
        self.assertEqual(b"placeholder: the runtime image tar is built in CI and put here with --image-tar (item 624)\n", self.tar)

    def test_a_release_without_a_tar_is_refused_for_the_tar(self):
        with mock.patch.object(package, "tag_problem", return_value=None), mock.patch.object(package, "uncommitted", return_value=""), \
                self.assertRaises(package.Refused) as said:
            package.download_content("windows", package.ROOT, release=True)
        self.assertIn("--image-tar", str(said.exception))

    def test_a_release_with_a_missing_empty_or_placeholder_tar_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.tar"
            empty.write_bytes(b"")
            holder = Path(tmp) / "placeholder.tar"
            holder.write_bytes(package.IMAGE_PLACEHOLDER)
            for name, given in (("empty name", ""), ("empty file", str(empty)), ("missing file", str(Path(tmp) / "none.tar")), ("placeholder bytes", str(holder))):
                with self.subTest(name), mock.patch.object(package, "tag_problem", return_value=None), mock.patch.object(package, "uncommitted", return_value=""), \
                        self.assertRaises(package.Refused) as said:
                    package.download_content("windows", package.ROOT, release=True, image_tar=given)
                self.assertIn("must exist and not be empty", str(said.exception))

    def test_a_build_with_an_empty_tar_file_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.tar"
            empty.write_bytes(b"")
            with self.assertRaises(package.Refused) as said:
                package.download_content("windows", dirty=True, image_tar=str(empty))
            self.assertIn("can't be read or is empty", str(said.exception))

    def test_a_native_file_in_an_extra_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "intake"
            folder.mkdir()
            (folder / "run.cmd").write_bytes(b"x")
            with self.assertRaises(package.Refused) as said:
                package.download_content("windows", dirty=True, extra_folders=[str(folder)])
            self.assertEqual("The Windows download must hold no .exe, .cmd or python folder, and it would hold: "
                             "clark/intake/run.cmd. Nothing was written.", str(said.exception))

    def test_the_guard_leaves_alone_names_that_only_start_with_python(self):
        for fine in ("clark/docs/python-notes.md", "clark/pythonic.py", "clark/docs/python-style/a.md",
                     "clark/run.batx", "clark/lib.dllx", "clark/notes.txt"):
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

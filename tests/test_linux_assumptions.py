"""#100: the tests make no Mac-only assumption. The demo script builds its database on a system whose OneDrive lookup isn't
built (Linux CI), and the browser tests find Chrome the way the workflow does.

Run: python3 dev/run_tests.py test_linux_assumptions
"""
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT

import run_support as support
from clark import platform

_spec = importlib.util.spec_from_file_location("demo_data", str(ROOT / "dev" / "demo_data.py"))
demo_data = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(demo_data)


class DemoDataWithoutOneDrive(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-linux-"))
        self.addCleanup(shutil.rmtree, self.dir, True)

    def test_no_onedrive_lookup_means_no_roots_not_a_failure(self):
        with mock.patch.object(platform, "system", return_value="linux"):
            with self.assertRaises(platform.NotBuiltYet):
                platform.onedrive_roots()                  # what Linux CI used to hit
            self.assertEqual(demo_data.local_onedrive_roots(), [])

    def test_the_script_builds_and_replaces_its_database_on_a_system_without_the_lookup(self):
        out = self.dir / "clark.db"
        with mock.patch.object(platform, "system", return_value="linux"), \
                mock.patch.dict(os.environ, {"CLARK_NOW": "2026-10-28"}):
            self.assertEqual(demo_data.main(["--out", str(out)]), 0)
            first = out.read_bytes()
            self.assertEqual(demo_data.main(["--out", str(out)]), 0, "the second run replaces the first")
        self.assertTrue(first)

    def test_a_folder_inside_a_onedrive_root_is_still_refused_where_the_check_exists(self):
        root = self.dir / "OneDrive-Demo"
        (root / "x").mkdir(parents=True)
        with mock.patch.dict(os.environ, {"CLARK_NOW": "2026-10-28"}):
            with self.assertRaises(platform.PlatformError):
                demo_data.build(root / "x" / "clark.db", demo_data.parse_now("2026-10-28"), onedrive_roots=[root])


class FindingChrome(unittest.TestCase):
    def test_the_order_is_the_workflows(self):
        fake = self._fake_file()
        with mock.patch.dict(os.environ, {"CLARK_CHROME": fake}), \
                mock.patch.object(support.shutil, "which", return_value="/usr/bin/google-chrome"):
            self.assertEqual(support.chrome_path(), fake, "CLARK_CHROME first")
        with mock.patch.dict(os.environ, {"CLARK_CHROME": ""}), \
                mock.patch.object(support.shutil, "which", side_effect=lambda n: "/usr/bin/chromium" if n == "chromium" else None):
            self.assertEqual(support.chrome_path(), "/usr/bin/chromium", "then the PATH names")
        with mock.patch.dict(os.environ, {"CLARK_CHROME": ""}), mock.patch.object(support.shutil, "which", return_value=None), \
                mock.patch.object(support.os.path, "exists", side_effect=lambda p: p == support.MAC_CHROME_PATHS[0]):
            self.assertEqual(support.chrome_path(), support.MAC_CHROME_PATHS[0], "then the Mac app")

    def test_with_no_chrome_anywhere_it_is_none_so_the_browser_tests_fail_and_never_skip(self):
        with mock.patch.dict(os.environ, {"CLARK_CHROME": ""}), mock.patch.object(support.shutil, "which", return_value=None), \
                mock.patch.object(support.os.path, "exists", return_value=False):
            self.assertIsNone(support.chrome_path())

    def test_the_browser_tests_use_that_one_lookup(self):
        for name in ("test_server.py", "test_work_items.py"):
            text = (ROOT / "tests" / name).read_text(encoding="utf-8")
            self.assertNotIn("/Applications/Google Chrome.app", text, f"{name} hard-codes the Mac path")
        server = (ROOT / "tests" / "test_server.py").read_text(encoding="utf-8")
        self.assertIn("chrome_path()", server)
        self.assertNotIn("skip", server.split("class RealBrowser")[1].split("class _Collect")[0].lower().replace("skipped", ""))

    def _fake_file(self):
        d = Path(tempfile.mkdtemp(prefix="clark-fakechrome-"))
        self.addCleanup(shutil.rmtree, d, True)
        f = d / "chrome"
        f.write_text("#!/bin/sh\n", encoding="utf-8")
        return str(f)


if __name__ == "__main__":
    unittest.main()

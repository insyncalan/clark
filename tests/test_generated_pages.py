"""The generated pages are not committed (#495): where they come from. No browser, no bundler run (the build is mocked)."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src/ and dev/tools/ on the path)

import package  # noqa: E402
from clark import page  # noqa: E402


class Ignored(unittest.TestCase):
    def test_git_ignores_and_does_not_track_both_pages(self):
        for name in ("page.html", "page-view.html"):
            rel = f"src/clark/page/{name}"
            self.assertEqual(subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel]).returncode, 0, rel)
            self.assertEqual(subprocess.run(["git", "-C", str(ROOT), "ls-files", rel], capture_output=True, text=True).stdout, "", rel)


class EnsureBuilt(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="pages "))
        self.addCleanup(__import__("shutil").rmtree, self.tmp, True)
        self.pages = (self.tmp / "page.html", self.tmp / "page-view.html")
        patches = [mock.patch.object(page, "PAGE", self.pages[0]), mock.patch.object(page, "VIEW_PAGE", self.pages[1]),
                   mock.patch.object(page, "_checked", False), mock.patch.object(page, "SOURCES", self.tmp / "src")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_a_download_never_calls_the_bundler(self):
        with mock.patch.object(page, "BUILDER", self.tmp / "dev" / "build_page.py"), mock.patch.object(page.subprocess, "run") as run:
            with self.assertRaises(page.PageError):
                page.ensure_built()
            for p in self.pages:
                p.write_text("x", encoding="utf-8")
            page.ensure_built()
            run.assert_not_called()

    def test_a_source_checkout_builds_a_missing_page_once(self):
        builder = self.tmp / "build_page.py"
        builder.write_text("", encoding="utf-8")

        def fake(*a, **k):
            for p in self.pages:
                p.write_text("built", encoding="utf-8")
            return subprocess.CompletedProcess(a, 0, "", "")
        with mock.patch.object(page, "BUILDER", builder), mock.patch.object(page.subprocess, "run", side_effect=fake) as run:
            page.ensure_built()
            page.ensure_built()
            self.assertEqual(run.call_count, 1)

    def test_a_failed_build_is_a_page_error(self):
        builder = self.tmp / "build_page.py"
        builder.write_text("", encoding="utf-8")
        bad = subprocess.CompletedProcess([], 1, "", "esbuild could not be fetched\n")
        with mock.patch.object(page, "BUILDER", builder), mock.patch.object(page.subprocess, "run", return_value=bad):
            with self.assertRaises(page.PageError) as said:
                page.ensure_built()
        self.assertIn("esbuild could not be fetched", str(said.exception))


class Package(unittest.TestCase):
    def test_the_pages_are_in_the_file_list_by_name(self):
        names = package.files("mac")
        for p in package.GENERATED_PAGES:
            self.assertIn(p, names)

    def test_a_missing_page_refuses_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/clark/page/src").mkdir(parents=True)
            with mock.patch.object(package, "SHARED", ("src/clark/",)), mock.patch.object(package, "tracked", return_value=[]):
                with self.assertRaises(package.Refused) as said:
                    package.make_pages(root)
        self.assertIn("has not been built", str(said.exception))

    def test_two_different_builds_refuse_a_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/clark/page/src").mkdir(parents=True)
            (root / "dev/tools").mkdir(parents=True)
            (root / "dev/tools/build_page.py").write_text(
                "import random\nfrom pathlib import Path\nr = Path(__file__).resolve().parents[2] / 'src/clark/page'\n"
                "for n in ('page.html', 'page-view.html'):\n    (r / n).write_text(str(random.random()))\n", encoding="utf-8")
            package.make_pages(root)
            with self.assertRaises(package.Refused) as said:
                package.make_pages(root, twice=True)
        self.assertIn("different bytes", str(said.exception))


if __name__ == "__main__":
    unittest.main()

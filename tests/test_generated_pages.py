"""The generated pages are not committed (#495): where they come from. No browser, no bundler run (the build is mocked)."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401  (puts src/ and dev/tools/ on the path)

import package  # noqa: E402
from clark import page, platform as clark_platform  # noqa: E402


class Ignored(unittest.TestCase):
    def test_git_ignores_and_does_not_track_both_pages(self):
        for name in ("page.html", "page-view.html"):
            rel = f"src/clark/page/{name}"
            self.assertEqual(subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", rel]).returncode, 0, rel)
            self.assertEqual(subprocess.run(["git", "-C", str(ROOT), "ls-files", rel], capture_output=True, text=True).stdout, "", rel)


class CheckWording(unittest.TestCase):
    """build_page --check names a missing page as missing and keeps "out of date" for one that exists and differs."""
    def run_check(self, existing):
        import contextlib
        import io
        import build_page
        tmp = Path(tempfile.mkdtemp(prefix="check "))
        self.addCleanup(__import__("shutil").rmtree, tmp, True)
        outs = (tmp / "page.html", tmp / "page-view.html")
        for f in outs:
            if existing:
                f.write_text("old", encoding="utf-8")
        made = ((outs[0], "new"), (outs[1], "new"))
        out = io.StringIO()
        with mock.patch.object(build_page, "pages", return_value=made), contextlib.redirect_stdout(out):
            code = build_page.main(["--check"])
        return code, out.getvalue()

    def test_a_missing_page_is_called_missing(self):
        code, text = self.run_check(existing=False)
        self.assertEqual(code, 1)
        self.assertIn("src/clark/page/page.html is missing: run python3 dev/tools/build_page.py", text)
        self.assertNotIn("out of date", text)

    def test_a_page_that_differs_is_called_out_of_date(self):
        code, text = self.run_check(existing=True)
        self.assertEqual(code, 1)
        self.assertIn("src/clark/page/page-view.html is out of date: run python3 dev/tools/build_page.py", text)
        self.assertNotIn("is missing", text)


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
        with mock.patch.object(page, "BUILDER", self.tmp / "dev" / "build_page.py"), mock.patch.object(clark_platform.subprocess, "run") as run:
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
        with mock.patch.object(page, "BUILDER", builder), mock.patch.object(clark_platform.subprocess, "run", side_effect=fake) as run:
            page.ensure_built()
            page.ensure_built()
            self.assertEqual(run.call_count, 1)

    def test_threads_together_build_once_and_never_read_half_a_page(self):
        import threading
        import time
        builder = self.tmp / "build_page.py"
        builder.write_text("", encoding="utf-8")

        def fake(*a, **k):
            time.sleep(0.2)
            for p in self.pages:
                tmp = p.with_name(p.name + ".tmp")
                tmp.write_text("built", encoding="utf-8")
                __import__("os").replace(tmp, p)
            return subprocess.CompletedProcess(a, 0, "", "")
        seen, errors = [], []

        def worker():
            try:
                page.ensure_built()
                seen.append([p.read_text(encoding="utf-8") for p in self.pages])
            except Exception as e:      # noqa: BLE001
                errors.append(e)
        with mock.patch.object(page, "BUILDER", builder), mock.patch.object(clark_platform.subprocess, "run", side_effect=fake) as run:
            threads = [threading.Thread(target=worker) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(errors, [])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(seen, [["built", "built"]] * 6)

    def test_a_failed_build_is_a_page_error(self):
        builder = self.tmp / "build_page.py"
        builder.write_text("", encoding="utf-8")
        bad = subprocess.CompletedProcess([], 1, "", "esbuild could not be fetched\n")
        with mock.patch.object(page, "BUILDER", builder), mock.patch.object(clark_platform.subprocess, "run", return_value=bad):
            with self.assertRaises(page.PageError) as said:
                page.ensure_built()
        self.assertIn("esbuild could not be fetched", str(said.exception))


CHILD = """
import subprocess, sys, time
from pathlib import Path
from unittest import mock
sys.path.insert(0, sys.argv[1])
from clark import page, platform as clark_platform
tmp = Path(sys.argv[2])
def fake(*a, **k):
    time.sleep(0.5)
    with open(tmp / "runs", "a") as f:
        f.write("x")
    for n in ("page.html", "page-view.html"):
        t = tmp / (n + ".tmp")
        t.write_text("built")
        __import__("os").replace(t, tmp / n)
    return subprocess.CompletedProcess(a, 0, "", "")
page.PAGE, page.VIEW_PAGE = tmp / "page.html", tmp / "page-view.html"
page.BUILDER, page.CACHE = tmp / "build_page.py", tmp / "cache"
page.STAMP, page.LOCK = page.CACHE / "pages.stamp", page.CACHE / "pages.lock"
page.source_stamp = lambda: "same"
with mock.patch.object(clark_platform.subprocess, "run", side_effect=fake):
    page.ensure_built()
"""


@unittest.skipIf(page.fcntl is None, "no fcntl")
class CrossProcess(unittest.TestCase):
    def test_two_processes_build_once(self):
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            (tmp / "build_page.py").write_text("", encoding="utf-8")
            procs = [subprocess.Popen([sys.executable, "-c", CHILD, str(ROOT / "src"), str(tmp)], stderr=subprocess.PIPE, text=True)
                     for _ in range(2)]
            errs = [p.communicate()[1] for p in procs]
            self.assertEqual([p.returncode for p in procs], [0, 0], errs)
            self.assertEqual((tmp / "runs").read_text(encoding="utf-8"), "x")


class Stamp(unittest.TestCase):
    """The stamp covers every build input, not just the page's own sources."""
    FILES = ("src/clark/page/src/main.jsx", "src/clark/page/shell.css", "src/clark/page/__init__.py", "src/clark/page/assets/a.svg",
             "src/clark/brand/tokens.css", "vendor/preact/p.js", "vendor/tiptap/t.js", "vendor/fonts/inter/f.woff2",
             "dev/tools/build_page.py", "dev/tools/esbuild.py")

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="stamp "))
        self.addCleanup(__import__("shutil").rmtree, self.root, True)
        for f in self.FILES:
            (self.root / f).parent.mkdir(parents=True, exist_ok=True)
            (self.root / f).write_text("one", encoding="utf-8")
        here = self.root / "src/clark/page"
        for p in (mock.patch.object(page, "ROOT", self.root), mock.patch.object(page, "HERE", here),
                  mock.patch.object(page, "SOURCES", here / "src")):
            p.start()
            self.addCleanup(p.stop)

    def test_each_input_changes_the_stamp(self):
        base = page.source_stamp()
        self.assertEqual(page.source_stamp(), base)
        for f in self.FILES:
            path = self.root / f
            path.write_text("two", encoding="utf-8")
            self.assertNotEqual(page.source_stamp(), base, f)
            path.write_text("one", encoding="utf-8")
        self.assertEqual(page.source_stamp(), base)

    def test_a_changed_input_rebuilds_and_an_unchanged_one_does_not(self):
        builder = self.root / "dev/tools/build_page.py"
        pages = (self.root / "p.html", self.root / "v.html")

        def fake(*a, **k):
            for p in pages:
                p.write_text("built", encoding="utf-8")
            return subprocess.CompletedProcess(a, 0, "", "")
        with mock.patch.object(page, "PAGE", pages[0]), mock.patch.object(page, "VIEW_PAGE", pages[1]), \
                mock.patch.object(page, "BUILDER", builder), mock.patch.object(page, "CACHE", self.root / "cache"), \
                mock.patch.object(page, "STAMP", self.root / "cache/pages.stamp"), mock.patch.object(page, "LOCK", self.root / "cache/l"), \
                mock.patch.object(clark_platform.subprocess, "run", side_effect=fake) as run:
            for expect in (1, 1, 2):
                with mock.patch.object(page, "_checked", False):
                    if expect == 2:
                        (self.root / "vendor/tiptap/t.js").write_text("changed", encoding="utf-8")
                    page.ensure_built()
                self.assertEqual(run.call_count, expect)


class Package(unittest.TestCase):
    def test_the_pages_are_in_the_file_list_by_name(self):
        page.ensure_built()          # a fresh checkout has no pages yet
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

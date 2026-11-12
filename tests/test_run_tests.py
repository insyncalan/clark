"""#70: the test runner (dev/run_tests.py, dev/tools/run_support.py), copied from creaite v2.6.11 and adapted. Its shards
cover every test file exactly once, the quick tier is read from the files, --changed and --push choose the files a change
reaches, --max-fail stops starting files, a file that fails under load and passes alone counts and is logged, and --flaky
lists those files.

Run: python3 dev/run_tests.py test_run_tests   (quick tier: starts no Chrome)

Copied from creaite's dev/tests/test_run_tests_shard.py and test_run_support.py (Tiers, FlakeLog), with clark's own cases
for --changed, --push, --max-fail and the re-run alone. The runner runs real (tiny) test files, made in temporary folders.
This file names no browser marker itself (they are joined from parts below), so it stays in the quick tier.
"""
import argparse
import io
import re
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from _paths import ROOT

sys.path.insert(0, str(ROOT / "dev"))
import run_support as support  # noqa: E402
import run_tests  # noqa: E402

BASE = Path(tempfile.mkdtemp(prefix="clark-runner-"))
support.RUN_BASE = BASE                   # the runners made here keep their folders in this test's own
BROWSER = "Google" + " Chrome"            # a marker, joined so this file doesn't carry it
FINDER = "chrome" + "_path"
FINDER_ENV = "CLARK_" + "CHROME"


def everything():
    return sorted(run_tests.TESTS.glob("test_*.py"))


def tearDownModule():
    support.shutil.rmtree(BASE, ignore_errors=True)


def folder(files):
    """A new temporary folder holding `files` ({name: text})."""
    d = Path(tempfile.mkdtemp(prefix="probe-", dir=BASE))
    for name, text in files.items():
        (d / name).parent.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text, encoding="utf-8")
    return d


PASSES = "import unittest\nclass Probe(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
FAILS = "import unittest\nclass Probe(unittest.TestCase):\n    def test_bad(self):\n        self.assertEqual(1, 2)\n"
FLAKY_ONCE = ("import os, unittest\nSEEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'seen')\n"
              "class Probe(unittest.TestCase):\n    def test_once(self):\n        first = not os.path.exists(SEEN)\n"
              "        open(SEEN, 'w', encoding='utf-8').close()\n"
              "        self.assertFalse(first, 'fails the first time only')\n")


# ===== the shards (creaite test_run_tests_shard.py) =====
class ShardCoversEveryFileOnce(unittest.TestCase):
    def check(self, files, n):
        seen = []
        for i in range(1, n + 1):
            seen += [f.name for f in run_tests.shard(files, i, n)]
        self.assertEqual(sorted(seen), sorted(f.name for f in files), f"{n} shards: each file exactly once")
        self.assertEqual(len(seen), len(set(seen)))

    def test_every_file_in_exactly_one_shard_for_1_to_6(self):
        files = everything()
        self.assertGreater(len(files), 5)
        for n in (1, 2, 3, 4, 5, 6):   # 6 = Ubuntu 3.x, 3 = macOS (tests.yml)
            self.check(files, n)

    def test_the_quick_tier_too(self):
        quick = [f for f in everything() if not support.is_chrome(f)]
        self.assertTrue(quick)
        for n in (1, 2, 3, 4):
            self.check(quick, n)

    def test_even_as_files_come_and_go(self):
        files = everything()
        variants = {"one gone": files[1:], "one new": files + [Path("test_zz_new_file.py")],
                    "three new, two gone": files[2:] + [Path(f"test_zz_{i}.py") for i in range(3)]}
        for what, fs in variants.items():
            for n in (1, 2, 3, 4):
                with self.subTest(what=what, n=n):
                    self.check(fs, n)

    def test_more_shards_than_files(self):
        self.check(everything()[:2], 5)

    def test_the_split_is_stable_and_ignores_the_order_given(self):
        files = everything()
        again = run_tests.shard(list(reversed(files)), 2, 3)
        self.assertEqual([f.name for f in run_tests.shard(files, 2, 3)], [f.name for f in again])

    def test_balanced_by_the_times(self):
        files = [Path(f"test_{c}.py") for c in "abcdef"]
        w = {"test_a.py": 100, "test_b.py": 60, "test_c.py": 50, "test_d.py": 50, "test_e.py": 20, "test_f.py": 10}
        totals = [sum(w[f.name] for f in run_tests.shard(files, i, 2, w)) for i in (1, 2)]
        self.assertEqual(sum(totals), 290)
        self.assertLessEqual(abs(totals[0] - totals[1]), 10)

    def test_files_of_no_time_still_spread_out(self):
        files = [Path(f"test_{c}.py") for c in "abcd"]
        w = {f.name: 0 for f in files}
        self.assertEqual([len(run_tests.shard(files, i, 2, w)) for i in (1, 2)], [2, 2])

    def test_without_times_it_is_still_a_split_by_name(self):
        files = [Path(f"test_{c}.py") for c in "abcd"]
        self.assertEqual([f.name for f in run_tests.shard(files, 1, 2, {})], ["test_a.py", "test_c.py"])
        self.assertEqual([f.name for f in run_tests.shard(files, 2, 2, {})], ["test_b.py", "test_d.py"])

    def test_the_committed_times_name_real_files(self):
        names = {f.name for f in everything()}
        listed = set(run_tests.shard_weights())
        self.assertFalse(listed - names, "shard_times.txt names a test file that doesn't exist")
        self.assertTrue(listed, "shard_times.txt is empty")

    def test_every_test_file_has_a_time_and_the_heavy_ones_are_weighted_as_heavy(self):
        """An unlisted file counts as 30 s; test_publish_public.py really takes 6 to 10 minutes on a macOS shard (median 476 s in
        five full macOS runs) and was listed at 80 s, so the shards were uneven. Every file is listed, and the known heavy ones
        weigh what they measured."""
        names = {f.name for f in everything()}
        weights = run_tests.shard_weights()
        self.assertEqual(sorted(names - set(weights)), [], "test files with no time in shard_times.txt")
        for heavy in ("test_publish_public.py", "test_publish_scan_time.py", "test_filter_line_page.py"):
            self.assertGreaterEqual(weights[heavy], 250, heavy)

    def test_the_refreshed_heavy_weights_stay_near_what_was_measured(self):
        """The refresh set these five files to the mean of the old weight and the macOS median x 0.93 (test_publish_public.py's 277.8 is (79.7 + 476) / 2: its median was taken as measured). A weight that drifts far
        either way (too small leaves a shard slow, too large starves the others) is caught, within 10 percent of each."""
        weights = run_tests.shard_weights()
        refreshed = {"test_publish_public.py": 277.8, "test_publish_public_slow.py": 119.7, "test_publish_scan_time.py": 450.4,
                     "test_filter_line_page.py": 270.6, "test_filter_line_page_900.py": 136}
        for name, expected in refreshed.items():
            with self.subTest(name=name):
                self.assertAlmostEqual(weights[name] / expected, 1.0, delta=0.10, msg=name)

    def test_every_listed_time_is_a_positive_number_on_its_own_line(self):
        """A line that does not parse is dropped silently by shard_weights, so a typo would send a heavy file back to 30 s."""
        lines = [ln for ln in (run_tests.SHARD_TIMES.read_text(encoding="utf-8").splitlines()) if ln and not ln.startswith("#")]
        weights = run_tests.shard_weights()
        self.assertEqual(len(lines), len(weights), "a line of shard_times.txt does not read as 'name seconds'")
        self.assertTrue(all(w > 0 for w in weights.values()), "a listed file has no time")


class ShardArgument(unittest.TestCase):
    def test_good_and_bad(self):
        self.assertEqual(run_tests.shard_arg("2/3"), (2, 3))
        for bad in ("0/3", "4/3", "3", "a/b", "1/0", ""):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                run_tests.shard_arg(bad)


class Records(unittest.TestCase):
    """Point the runner's records (.durations, .last-failed, .flaky.jsonl) at a temporary folder."""

    def setUp(self):
        d = Path(tempfile.mkdtemp(prefix="records-", dir=BASE))
        for name, value in (("LAST_FAILED", d / ".last-failed"), ("TIMES", d / ".durations"), ("FLAKY", d / ".flaky.jsonl")):
            patcher = mock.patch.object(run_tests, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)


class FailedFirst(Records):
    def test_failed_files_start_first_and_a_partial_run_keeps_the_rest(self):
        files = [Path(f"test_{c}.py") for c in "abc"]
        run_tests.remember_failed(["test_a.py", "test_b.py", "test_c.py"], ["test_c.py"])
        run_tests.slowest_first(files)
        self.assertEqual(files[0].name, "test_c.py")
        run_tests.remember_failed(["test_a.py"], ["test_a.py"])        # a partial run
        self.assertEqual(run_tests.last_failed(), {"test_a.py", "test_c.py"})
        run_tests.remember_failed(["test_c.py"], [])                   # c passes now
        self.assertEqual(run_tests.last_failed(), {"test_a.py"})


# ===== the tiers (creaite test_run_support.py Tiers) =====
class SelectionErrors(unittest.TestCase):
    """The Full review's LOWs: a name that matches nothing never goes green, and --stress needs --repeat."""

    def run_main(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            try:
                return run_tests.main(list(args)), out.getvalue()
            except SystemExit as e:
                return e.code, out.getvalue()

    def test_a_name_that_matches_nothing_exits_1_even_with_a_shard_or_list(self):
        for extra in ((), ("--shard", "1/2"), ("--shard", "2/2"), ("--quick",), ("--list",), ("--changed",)):
            code, out = self.run_main("test_no_such_file_anywhere", *extra)
            self.assertEqual(code, 1, extra)
            self.assertIn("No test files match.", out)

    def test_an_empty_shard_of_real_files_is_not_an_error(self):
        code, _ = self.run_main("test_layout", "--shard", "2/2", "--list")
        self.assertEqual(code, 0, "more shards than files leaves a shard empty: that is fine")

    def test_stress_without_repeat_is_an_error(self):
        err = io.StringIO()
        with mock.patch.object(sys, "stderr", err):
            code, _ = self.run_main("--stress", "2", "--list")
        self.assertEqual(code, 2)
        self.assertIn("--repeat", err.getvalue())


class Tiers(unittest.TestCase):
    def test_only_the_browser_tests_are_outside_the_quick_tier(self):
        """A file is in the browser tier exactly when it drives Chrome: it is test_server.py (the harness), or it imports the
        harness, or it names Chrome itself. Read here by plain text, so it checks run_support's own reading of the files
        without a list to keep up to date as items add browser tests (#35 added several; this was a list of one)."""
        # The marker words are built from pieces so that this file's own text doesn't make it a browser file.
        marks = ["from test_server import", "import test_server", "chrome" + "_path", "--head" + "less", "CLARK_" + "CHROME"]
        text_says = re.compile("|".join(re.escape(m) for m in marks))
        found = {f.name: support.is_chrome(f) for f in everything()}
        want = {f.name: f.name == "test_server.py" or (f.name != Path(__file__).name
                                                       and bool(text_says.search(f.read_text(encoding="utf-8"))))
                for f in everything()}
        self.assertEqual(found, want)
        self.assertTrue(found["test_server.py"])
        self.assertFalse(found["test_layout.py"])

    def test_this_file_is_quick(self):
        self.assertFalse(support.is_chrome(Path(__file__)))

    def test_read_from_the_files(self):
        d = folder({
            "test_browser.py": f"CHROME = '/Applications/{BROWSER}.app/Contents/MacOS/{BROWSER}'\nDEMO = {{'a': 1}}\n",
            "test_pipe.py": "ARGS = ['--remote-" + "debugging-pipe']\n",
            "browser_kit.py": f"def start():\n    return {FINDER}()\n",
            "test_uses_kit.py": "import browser_kit\n",
            "test_kit_in_a_method.py": "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n"
                                       "        from browser_kit import start\n",
            "test_takes_data.py": "from test_browser import DEMO\n",
            "test_plain.py": "import json\nimport run_support\nimport run_tests\n",
        })
        found = {f.name: support.is_chrome(f) for f in sorted(d.glob("test_*.py"))}
        self.assertEqual(found, {"test_browser.py": True, "test_pipe.py": True, "test_uses_kit.py": True,
                                 "test_kit_in_a_method.py": True, "test_takes_data.py": False, "test_plain.py": False})


class FindingChrome(unittest.TestCase):
    def test_the_variable_comes_first_and_a_missing_one_is_passed_over(self):
        find = getattr(support, FINDER)
        here = folder({"chrome": ""}) / "chrome"
        with mock.patch.dict(os.environ, {FINDER_ENV: str(here)}):
            self.assertEqual(find(), str(here))
        with mock.patch.dict(os.environ, {FINDER_ENV: str(here) + "-missing"}):
            self.assertNotEqual(find(), str(here) + "-missing")


# ===== --changed and --push =====
FAKE_REPO = {
    "src/clark/__init__.py": "",
    "src/clark/report.py": "from . import rows\n",
    "src/clark/rows.py": "import json\n",
    "src/clark/store.py": "import json\n",
    "src/clark/server.py": "from . import store\n",
    "src/clark/milestones.py": "",
    "dev/tools/esbuild.py": "",
    "tests/_paths.py": "",
    "tests/test_report.py": "from clark import report\n",
    "tests/test_server.py": "from clark import server\n",
    "tests/test_no_real_names.py": "import subprocess\nsubprocess.run(['git', 'ls-files'])\n",
    "tests/test_reuse_record.py": "TEXT = open('docs/REUSE-FROM-CREAITE.md').read()\n",
    "tests/test_milestones.py": "from clark.milestones import plan\n",
    "tests/test_layout.py": "from _paths import ROOT\nimport clark\n",
    "tests/test_esbuild_pin.py": "import subprocess\nsubprocess.run(['python3', 'dev/tools/esbuild.py'])\n",
}


class Changed(unittest.TestCase):
    def setUp(self):
        self.repo = folder(FAKE_REPO)
        self.files = sorted((self.repo / "tests").glob("test_*.py"))

    def chosen(self, paths, deep=False):
        files, _ = run_tests.choose(self.files, paths, deep, repo=self.repo)
        return sorted(f.name for f in files)

    def test_a_documents_only_change_runs_the_name_guard_and_the_tests_that_name_the_document(self):
        # test_no_real_names reads every tracked file, documents included; test_reuse_record names the reuse record
        guard = ["test_no_real_names.py"]
        for paths in (["docs/BRD.md"], ["README.md", "dev/HEAD-LOG.md", "docs/handoff/x.md"]):
            with self.subTest(paths):
                self.assertEqual(self.chosen(paths), guard)
        self.assertEqual(self.chosen(["docs/REUSE-FROM-CREAITE.md"]), ["test_no_real_names.py", "test_reuse_record.py"])
        self.assertEqual(self.chosen(["docs/handoff/REUSE-FROM-CREAITE.md"]), ["test_no_real_names.py", "test_reuse_record.py"])
        _, why = run_tests.choose(self.files, ["docs/BRD.md"], repo=self.repo)
        self.assertIn("documents only", why)
        self.assertEqual(self.chosen([]), [])                                  # nothing changed: nothing to run

    def test_any_change_runs_the_name_guard_too(self):
        self.assertEqual(self.chosen(["src/clark/milestones.py"]), ["test_milestones.py", "test_no_real_names.py"])

    def test_a_module_reaches_the_tests_that_name_it(self):
        self.assertEqual(self.chosen(["src/clark/report.py"]), ["test_no_real_names.py", "test_report.py"])
        self.assertEqual(self.chosen(["dev/tools/esbuild.py"]), ["test_esbuild_pin.py", "test_no_real_names.py"])  # "esbuild.py"

    def test_a_changed_test_file_runs_itself(self):
        self.assertEqual(self.chosen(["tests/test_milestones.py"]), ["test_milestones.py", "test_no_real_names.py"])

    def test_a_helper_and_the_package_reach_their_users(self):
        self.assertEqual(self.chosen(["tests/_paths.py"]), ["test_layout.py", "test_no_real_names.py"])
        self.assertEqual(self.chosen(["src/clark/__init__.py"]),
                         ["test_layout.py", "test_milestones.py", "test_no_real_names.py", "test_report.py", "test_server.py"])

    def test_deep_follows_a_module_through_the_modules_that_import_it(self):
        self.assertEqual(self.chosen(["src/clark/rows.py"]), ["test_no_real_names.py"])
        self.assertEqual(self.chosen(["src/clark/rows.py"], deep=True), ["test_no_real_names.py", "test_report.py"])

    def test_these_run_everything(self):
        every = sorted(f.name for f in self.files)
        for p in (".github/workflows/tests.yml", "docs/RULES.md", "dev/run_tests.py", "dev/tools/run_support.py",
                  "dev/tools/shard_times.txt", "vendor/manifest.json", ".claude/settings.json", "VERSION",
                  "system/prototype/app.css"):                           # the last: nothing says which tests read it
            with self.subTest(p):
                self.assertEqual(self.chosen(["docs/BRD.md", p]), every)

    def test_a_changed_guarded_path_selects_every_file(self):
        # #31 and #33 land these; a change to any of them runs everything (as creaite's guarded set does), so a change
        # to src/clark/server.py runs tests/test_server.py and all the rest
        every = sorted(f.name for f in self.files)
        self.assertLessEqual({"src/clark/store.py", "src/clark/schema.sql", "src/clark/history.py",
                              "src/clark/server.py", ".github/workflows/tests.yml", ".github/workflows/"},
                             set(run_tests.GUARDED))
        for p in run_tests.GUARDED:
            with self.subTest(p):
                self.assertEqual(self.chosen([p]), every)
        # #592: the files our rules name, ask*.py by prefix
        for p in ("src/clark/changes.py", "src/clark/word_route.py", "src/clark/section_bodies.py", "src/clark/ai_service.py",
                  "src/clark/doclinks.py", "src/clark/ask_service.py", "src/clark/ask.py", "src/clark/publish.py",
                  "src/clark/secret_screen.py", "src/clark/update.py", "src/clark/updates.py", "src/clark/update_helper.py",
                  "src/clark/publish_flow.py", "src/clark/publish_pdf.py", "src/clark/platform.py",
                  ".github/workflows/release.yml"):
            with self.subTest(p):
                self.assertEqual(self.chosen([p]), every)
        _, why = run_tests.choose(self.files, ["src/clark/server.py"], repo=self.repo)
        self.assertIn("can reach any test", why)

    def test_every_guarded_update_file_has_an_owner_in_codeowners(self):
        # #473 LOW 4: the trust chain, its signing tool and the pin test cannot change without the owner's review
        owners = {ln.split()[0] for ln in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines()
                  if ln.strip() and not ln.startswith("#")}
        for path in run_tests.GUARDED:
            if path.startswith(("vendor/ed25519", "dev/tools/sign_release", "dev/tools/ed25519",
                                "tests/test_update", "clark.command", "src/clark/__main__")):
                with self.subTest(path):
                    self.assertIn("/" + path, owners)

    def test_a_rename_away_from_a_guarded_path_is_seen(self):
        # #593: git diff must list the old name of a rename, so moving store.py away still runs everything
        def git(*a):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *a], cwd=d, check=True,
                           capture_output=True)
        with tempfile.TemporaryDirectory() as d:
            git("init", "-q")
            (Path(d) / "src" / "clark").mkdir(parents=True)
            (Path(d) / "src/clark/store.py").write_text("x = 1\n" * 50, encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "a")
            git("mv", "src/clark/store.py", "src/clark/other.py")
            with mock.patch.object(run_tests, "REPO", Path(d)):
                paths = run_tests.changed_paths("HEAD")
        self.assertIn("src/clark/store.py", paths)

    def test_the_real_repo(self):
        files, why = run_tests.choose(everything(), ["src/clark/milestones.py"])
        self.assertIn("test_milestones.py", [f.name for f in files])
        self.assertNotIn("test_vendor_python.py", [f.name for f in files])
        self.assertIn("clark.milestones", why)


class Push(unittest.TestCase):
    def test_a_documents_change_selects_the_name_guard(self):
        repo = folder(FAKE_REPO)
        files = sorted((repo / "tests").glob("test_*.py"))
        with mock.patch.object(run_tests, "changed_paths", return_value=["docs/REUSE-FROM-CREAITE.md"]), \
                mock.patch.object(run_tests, "REPO", repo):
            got, _ = run_tests.for_push(files, "origin/main")
            self.assertIn("test_no_real_names.py", [f.name for f in got])
            self.assertIn("test_reuse_record.py", [f.name for f in got])
            chosen, _ = run_tests.select(files, "origin/main")
            self.assertEqual(sorted(f.name for f in chosen), ["test_no_real_names.py", "test_reuse_record.py"])

    def test_the_quick_tier_and_the_browser_files_reached(self):
        repo = folder({**FAKE_REPO, "tests/test_report.py": f"from clark import report\nCHROME = '{BROWSER}'\n"})
        files = sorted((repo / "tests").glob("test_*.py"))
        quick = sorted(f.name for f in files if f.name != "test_report.py")
        for paths, want in ((["docs/BRD.md"], quick), (["src/clark/milestones.py"], quick),
                            (["src/clark/report.py"], sorted(quick + ["test_report.py"])),
                            (["src/clark/server.py"], sorted(f.name for f in files)),
                            ([".github/workflows/tests.yml"], sorted(f.name for f in files))):
            with self.subTest(paths), mock.patch.object(run_tests, "changed_paths", return_value=paths), \
                    mock.patch.object(run_tests, "REPO", repo):
                got, _ = run_tests.for_push(files, "origin/main")
                self.assertEqual(sorted(f.name for f in got), want)


# ===== the private temporary folders and their clean-up =====
class TempFolders(unittest.TestCase):
    def test_the_prefix_is_long_and_distinctive(self):
        # the clean-up deletes every folder named <prefix><digits> in the temp folder, so the prefix must be one no other
        # program uses ("cl" once was: it matched any /tmp/cl123)
        self.assertGreaterEqual(len(support.RUN_PREFIX), 12)
        self.assertTrue(support.RUN_PREFIX.startswith("clark"), support.RUN_PREFIX)
        run = support.RunDir()
        try:
            self.assertEqual(run.root.parent, support.RUN_BASE)
            self.assertEqual(run.root.name, f"{support.RUN_PREFIX}{os.getpid()}")
            self.assertEqual(run.for_file().parent, run.root)
        finally:
            run.close()

    def test_the_clean_up_touches_only_the_folders_of_runs_that_are_gone(self):
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait()                                   # its pid is no longer alive
        mine = f"{support.RUN_PREFIX}{gone.pid}"
        others = ["cl" + str(gone.pid), "cl1", "clark-runner-" + str(gone.pid), support.RUN_PREFIX + "abc",
                  support.RUN_PREFIX + "x" + str(gone.pid), "other-" + support.RUN_PREFIX + str(gone.pid)]
        live = f"{support.RUN_PREFIX}{os.getpid()}"
        for name in [mine, live, *others]:
            (support.RUN_BASE / name).mkdir()
        try:
            self.assertEqual([d.name for d in support.stale_folders()], [mine])
            self.assertEqual(support.clean(say=lambda *a: None), 1)
            self.assertFalse((support.RUN_BASE / mine).exists())
            for name in [live, *others]:
                self.assertTrue((support.RUN_BASE / name).is_dir(), name)
        finally:
            for name in [mine, live, *others]:
                support.shutil.rmtree(support.RUN_BASE / name, ignore_errors=True)


# ===== running: --max-fail, the re-run alone, --flaky =====
class Running(Records):
    def run_all(self, d, **kw):
        printed = io.StringIO()
        before = signal.getsignal(signal.SIGTERM)
        try:
            with mock.patch.object(run_tests, "TESTS", d), redirect_stdout(printed):
                code = run_tests.run_all(sorted(d.glob("test_*.py")), **kw)
        finally:
            signal.signal(signal.SIGTERM, before)
        return code, printed.getvalue()

    def test_a_file_that_fails_under_load_and_passes_alone_counts_and_is_logged(self):
        d = folder({"test_probe_ok.py": PASSES, "test_probe_flaky.py": FLAKY_ONCE})
        code, out = self.run_all(d, jobs=2)
        self.assertEqual(code, 0, out)
        self.assertIn("FAIL  test_probe_flaky.py", out)
        self.assertIn("Passed alone after failing under load: test_probe_flaky.py", out)
        self.assertRegex(out.splitlines()[-1], r"^Python \S+: pass, 2 tests in [\d.]+ s$")
        entry = json.loads(run_tests.FLAKY.read_text(encoding="utf-8"))
        self.assertEqual(entry["file"], "test_probe_flaky.py")
        self.assertEqual(entry["failed"], ["test_probe_flaky.Probe.test_once"])
        listed = io.StringIO()
        with redirect_stdout(listed):
            run_tests.flaky_report()
        self.assertIn("test_probe_flaky.py", listed.getvalue())
        self.assertIn("AssertionError: True is not false : fails the first time only", listed.getvalue())

    def test_a_file_that_fails_alone_too_fails_the_run(self):
        d = folder({"test_probe_ok.py": PASSES, "test_probe_bad.py": FAILS})
        code, out = self.run_all(d, jobs=2)
        self.assertEqual(code, 1)
        self.assertIn("FAIL  test_probe_bad.py  (", out)
        self.assertIn("alone)", out)
        self.assertIn("===== test_probe_bad.py =====", out)
        self.assertNotIn("Passed alone", out)
        self.assertRegex(out.splitlines()[-1], r"^Python \S+: FAIL, 2 tests in")
        self.assertFalse(run_tests.FLAKY.exists())

    def test_max_fail_starts_no_more_files(self):
        d = folder({f"test_probe_bad_{i}.py": FAILS for i in range(6)})
        code, out = self.run_all(d, jobs=1, max_fail=1)
        self.assertEqual(code, 1)
        self.assertIn("(--max-fail 1): no further file starts", out)
        self.assertRegex(out, r"\d+ not run \(--max-fail\)")
        self.assertLess(out.count("FAIL  test_probe_bad_"), 6 * 2)

    def test_rerun_max_runs_none_alone_when_too_many_fail(self):
        d = folder({f"test_probe_bad_{i}.py": FAILS for i in range(3)})
        code, out = self.run_all(d, jobs=3, rerun_max=2)
        self.assertEqual(code, 1)
        self.assertIn("more than --rerun-max 2", out)
        self.assertNotIn("alone)", out)

    def test_repeat_reports_each_files_passes(self):
        d = folder({"test_probe_ok.py": PASSES})
        code, out = self.run_all(d, jobs=2, copies=3)
        self.assertEqual(code, 0)
        self.assertIn("3/3  test_probe_ok.py", out)

    def test_the_flaky_list_is_empty_at_first(self):
        listed = io.StringIO()
        with redirect_stdout(listed):
            run_tests.flaky_report()
        self.assertIn("No file has failed under load and passed alone", listed.getvalue())


class FlakeLog(Records):
    """A file that failed under load and passed alone is logged with which tests failed and the end of that output
    (creaite)."""

    def test_the_log_names_the_failed_tests_and_keeps_the_error(self):
        out = ("FAIL: test_a (__main__.BuildsTakeTurns.test_a)\nTraceback (most recent call last):\n"
               "AssertionError: 5 not greater than 20\nERROR: test_b (__main__.Other)\n")
        self.assertEqual(run_tests.failed_tests(out), ["BuildsTakeTurns.test_a", "Other.test_b"])   # 3.11+ and older forms
        run_tests.log_flaky("test_probe.py", 12, out)
        entry = json.loads(run_tests.FLAKY.read_text(encoding="utf-8"))
        self.assertEqual(entry["failed"], ["BuildsTakeTurns.test_a", "Other.test_b"])
        self.assertIn("AssertionError: 5 not greater than 20", entry["tail"])
        printed = io.StringIO()
        with redirect_stdout(printed):
            run_tests.flaky_report()
        self.assertIn("last failed: BuildsTakeTurns.test_a, Other.test_b — AssertionError: 5 not greater than 20",
                      printed.getvalue())


class Choosing(unittest.TestCase):
    def test_names_choose_files_and_a_dotted_name_one_test(self):
        files, ids = run_tests.pick(["vendor"])
        self.assertEqual([f.name for f in files], ["test_vendor_preact.py", "test_vendor_python.py", "test_vendor_tiptap.py"])
        files, ids = run_tests.pick(["test_layout.LayoutTest.test_clark_imports_from_src", "test_vendor_tiptap.py"])
        self.assertEqual([f.name for f in files], ["test_layout.py", "test_vendor_tiptap.py"])
        self.assertEqual(ids, {"test_layout.py": ["test_layout.LayoutTest.test_clark_imports_from_src"]})
        self.assertEqual(run_tests.pick([])[0], everything())

    def test_list_with_a_shard(self):
        printed = io.StringIO()
        with redirect_stdout(printed):
            self.assertEqual(run_tests.main(["--list", "--quick", "--shard", "1/1"]), 0)
        names = [ln.split()[0] for ln in printed.getvalue().splitlines() if ln.startswith("test_")]
        self.assertEqual(names, [f.name for f in everything() if not support.is_chrome(f)])

    def test_the_summary_line_keeps_28s_form(self):
        line = run_tests.summary(True, 97, 1.31)
        self.assertRegex(line, r"^Python \d+\.\d+\.\d+\S*: pass, 97 tests in 1\.3 s$")


class RemoveProfile(unittest.TestCase):
    """remove_profile deletes only a temporary Chrome profile folder; anything else is refused and left alone."""

    def make(self):
        d = Path(tempfile.mkdtemp(prefix=support.PROFILE_PREFIX))
        (d / "Default").mkdir()
        (d / "Default" / "f").write_text("x", encoding="utf-8")
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        return d

    def test_removes_its_own_profile(self):
        d = self.make()
        self.assertTrue(support.remove_profile(d))
        self.assertFalse(d.exists())

    def test_a_missing_profile_is_fine(self):
        d = self.make()
        support.remove_profile(d)
        self.assertTrue(support.remove_profile(d))

    def test_bad_paths_are_refused_and_nothing_is_removed(self):
        keep = Path(tempfile.mkdtemp(prefix="clark-runner-keep-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(keep, ignore_errors=True))
        (keep / "f").write_text("x", encoding="utf-8")
        inside = keep / (support.PROFILE_PREFIX + "x")        # right name, wrong parent
        inside.mkdir()
        bad = [Path("/"), Path.home(), ROOT, ROOT.parent, Path(tempfile.gettempdir()), keep, inside,
               Path(tempfile.gettempdir()) / "other-folder", Path(tempfile.gettempdir()) / (support.PROFILE_PREFIX + "x") / ".."]
        for p in bad:
            with mock.patch.object(support.shutil, "rmtree") as rm:
                with self.assertRaises(ValueError, msg=str(p)):
                    support.remove_profile(p, tries=1, wait=0)
                rm.assert_not_called()
        self.assertTrue((keep / "f").exists())
        self.assertTrue(inside.exists())

    def test_a_link_to_a_real_folder_is_refused(self):
        target = Path(tempfile.mkdtemp(prefix="clark-runner-target-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(target, ignore_errors=True))
        (target / "f").write_text("x", encoding="utf-8")
        link = Path(tempfile.gettempdir()) / (support.PROFILE_PREFIX + "link-" + target.name)
        link.symlink_to(target)
        self.addCleanup(lambda: link.unlink() if link.is_symlink() else None)
        with self.assertRaises(ValueError):
            support.remove_profile(link, tries=1, wait=0)
        self.assertTrue((target / "f").exists())

    def test_retries_then_succeeds(self):
        d = self.make()
        real = support.shutil.rmtree
        calls = []

        def flaky(p, *a, **k):
            calls.append(p)
            if len(calls) < 3:
                raise OSError("Directory not empty")
            return real(p, *a, **k)
        with mock.patch.object(support.shutil, "rmtree", flaky):
            self.assertTrue(support.remove_profile(d, tries=5, wait=0))
        self.assertEqual(len(calls), 3)
        self.assertFalse(d.exists())

    def test_gives_up_after_the_tries_and_says_so(self):
        d = self.make()
        calls = []

        def stuck(p, *a, **k):
            calls.append(p)
            if k.get("ignore_errors"):
                return
            raise OSError("Directory not empty")
        err = io.StringIO()
        with mock.patch.object(support.shutil, "rmtree", stuck), mock.patch("sys.stderr", err):
            self.assertFalse(support.remove_profile(d, tries=4, wait=0))
        self.assertEqual(len(calls), 5)            # 4 tries, then one last forced attempt: bounded
        self.assertIn(str(d), err.getvalue())


class SuiteSlots(unittest.TestCase):
    """A shared box's limit on full runs (support.take_slot). Real locks in a temporary folder; nothing waits long."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.said = []

    def take(self, runs=50, jobs=8, slots=2, **kw):
        return run_tests.support.take_slot(runs, jobs, slots=slots, folder=self.d.name, environ=kw.pop("environ", {}), pause=0.01,
                                           say=lambda text, flush=True: self.said.append(text), **kw)

    def test_a_computer_with_no_limit_is_not_touched(self):
        self.assertEqual(self.take(slots=0), (None, 8))
        self.assertEqual(os.listdir(self.d.name), [])

    def test_the_file_says_the_limit_and_rubbish_is_no_limit(self):
        path = Path(self.d.name) / "slots"
        for text, want in (("2\n", 2), ("x", 0), ("", 0), ("\u00b2", 0)):       # a superscript counts as a digit to isdigit, and int() refuses it
            path.write_text(text, encoding="utf-8")
            self.assertEqual(run_tests.support.box_slots(path), want)
        self.assertEqual(run_tests.support.box_slots(Path(self.d.name) / "none"), 0)

    def test_two_runs_get_slots_and_files_at_once_are_capped(self):
        a, jobs = self.take()
        b, _ = self.take()
        self.addCleanup(os.close, a)
        self.addCleanup(os.close, b)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertEqual(jobs, run_tests.support.BOX_JOBS)

    def test_a_third_waits_says_so_and_starts_anyway_in_the_end(self):
        held = [self.take()[0], self.take()[0]]
        for fd in held:
            self.addCleanup(os.close, fd)
        got, jobs = self.take(max_wait=0.05)
        self.assertIsNone(got, "it runs without a slot rather than never")
        self.assertEqual(jobs, run_tests.support.BOX_JOBS)
        self.assertIn("Nothing is wrong", self.said[0])
        self.assertIn("starting anyway", self.said[-1])

    def test_a_slot_comes_free_when_its_holder_closes(self):
        a = self.take()[0]
        b = self.take()[0]
        self.addCleanup(os.close, b)
        os.close(a)
        c = self.take(max_wait=0.05)[0]
        self.addCleanup(os.close, c)
        self.assertIsNotNone(c)
        self.assertEqual(self.said, [])

    def test_waiters_get_slots_in_the_order_they_arrived(self):
        import threading
        held = [self.take()[0], self.take()[0]]
        order, fds, lock = [], [], threading.Lock()

        def waiter(n):
            fd = self.take(max_wait=20)[0]
            with lock:
                order.append(n)
                fds.append(fd)
            os.close(fd)                                     # frees the slot at once for the next in line
        threads = []

        def places():
            q = Path(self.d.name) / "queue"
            return os.listdir(q) if q.is_dir() else []
        for n in range(4):
            t = threading.Thread(target=waiter, args=(n,))
            t.start()
            threads.append(t)
            deadline = time.time() + 5
            while len(places()) < n + 1 and time.time() < deadline:
                time.sleep(0.005)
            time.sleep(0.01)                                 # arrival times differ by more than a clock tick
        for fd in held:
            os.close(fd)
        for t in threads:
            t.join(30)
        self.assertEqual(order, [0, 1, 2, 3])
        self.assertEqual(places(), [], "every place in the line is given up")

    def test_a_newcomer_does_not_jump_a_waiting_run_when_a_slot_is_free(self):
        q = Path(self.d.name) / "queue"
        q.mkdir()
        import fcntl
        fd = os.open(str(q / "00000000000000000001-1"), os.O_RDWR | os.O_CREAT, 0o666)
        fcntl.flock(fd, fcntl.LOCK_EX)
        self.addCleanup(os.close, fd)
        got, _ = self.take(max_wait=0.05)
        self.assertIsNone(got, "a run is waiting ahead, so the newcomer waits too (and here starts anyway at the end)")
        self.assertIn("starting anyway", self.said[-1])

    def test_a_place_left_by_a_run_that_died_does_not_block_the_line(self):
        q = Path(self.d.name) / "queue"
        q.mkdir()
        old = q / "00000000000000000001-1"
        old.write_text("", encoding="utf-8")
        os.utime(old, (1, 1))
        got, _ = self.take(max_wait=0.5)
        self.addCleanup(os.close, got)
        self.assertIsNotNone(got)
        self.assertFalse(old.exists())

    def test_a_waiters_place_is_locked_while_it_waits(self):
        import fcntl
        q = Path(self.d.name) / "queue"
        name, fd, path = run_tests.support._join(q)
        self.addCleanup(os.close, fd)
        other = os.open(path, os.O_RDWR)
        self.addCleanup(os.close, other)
        with self.assertRaises(OSError, msg="a waiting run's place must be locked, or another run clears it as a dead run's"):
            fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_a_file_in_the_queue_folder_that_is_not_a_ticket_is_left_alone(self):
        q = Path(self.d.name) / "queue"
        q.mkdir()
        stray = q / "notes.txt"
        stray.write_text("not a place in the line", encoding="utf-8")
        os.utime(stray, (1, 1))
        got, _ = self.take(max_wait=0.5)
        self.addCleanup(os.close, got)
        self.assertIsNotNone(got, "a stray file is not a run ahead")
        self.assertTrue(stray.exists(), "only ticket-named places are cleared")

    def test_a_small_run_and_a_run_under_the_wrapper_need_no_slot(self):
        self.assertEqual(self.take(runs=run_tests.support.SMALL_RUN), (None, run_tests.support.BOX_JOBS))
        self.assertEqual(self.take(environ={run_tests.support.SLOT_HELD: "1"}), (None, run_tests.support.BOX_JOBS))
        self.assertEqual(os.listdir(self.d.name), [])

    def test_a_folder_that_cannot_be_made_is_no_limit(self):
        self.assertEqual(run_tests.support.take_slot(50, 8, slots=2, folder="/dev/null/x", environ={})[0], None)


if __name__ == "__main__":
    unittest.main()

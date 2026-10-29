"""#56: the platform layer (src/clark/platform.py), Mac branch, each Windows branch "not built yet".

Run: python3 tests/test_platform.py
Programs are never really started: the dialogs and Finder calls get a fake `run` that records the argument list. The
folders are temporary ones, never the real home folder or OneDrive.
"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from clark import platform as pl  # noqa: E402


class FakeRun:
    """Stands in for subprocess.run: records each argument list and answers with the given result."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.calls, self.result = [], (returncode, stdout, stderr)

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, *self.result)


class TempHome(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)


class Folders(TempHome):
    def test_data_dir_is_application_support(self):
        self.assertEqual(pl.data_dir(self.home, on=pl.MAC), self.home / "Library" / "Application Support" / "clark")
        self.assertFalse(pl.data_dir(self.home, on=pl.MAC).exists(), "data_dir() creates nothing")

    def test_onedrive_roots_are_suggested_from_cloud_storage_and_the_older_app(self):
        self.assertEqual(pl.onedrive_roots(self.home, on=pl.MAC), [])
        cloud = self.home / "Library" / "CloudStorage"
        for name in ("OneDrive-DemoOrg", "OneDrive-Personal", "Dropbox"):
            (cloud / name).mkdir(parents=True)
        (self.home / "OneDrive").mkdir()
        (self.home / "OneDrive-notes.txt").write_text("", encoding="utf-8")       # a file, not a folder
        self.assertEqual(pl.onedrive_roots(self.home, on=pl.MAC),
                         [cloud / "OneDrive-DemoOrg", cloud / "OneDrive-Personal", self.home / "OneDrive"])

    def test_a_data_folder_inside_onedrive_is_refused_with_the_reason(self):
        root = self.home / "Library" / "CloudStorage" / "OneDrive-DemoOrg"
        (root / "clark").mkdir(parents=True)
        for inside in (root, root / "clark", root / "clark" / "not-made-yet"):
            with self.assertRaisesRegex(pl.PlatformError, "inside OneDrive.*damages the database"):
                pl.check_data_dir(inside, roots=[root])
        outside = self.home / "Library" / "Application Support" / "clark"
        self.assertEqual(pl.check_data_dir(outside, roots=[root]), outside)
        self.assertEqual(pl.check_data_dir(self.home / "OneDrive-DemoOrg-old", roots=[root]),
                         self.home / "OneDrive-DemoOrg-old", "a name that only starts like the root is outside it")

    def test_a_link_into_onedrive_is_refused(self):
        root = self.home / "OneDrive"
        (root / "data").mkdir(parents=True)
        (self.home / "looks-local").symlink_to(root / "data")
        with self.assertRaises(pl.PlatformError):
            pl.check_data_dir(self.home / "looks-local", roots=[root])


class OpenAndReveal(TempHome):
    def test_open_and_reveal_use_finder_with_an_argument_list(self):
        f = self.home / "-demo report.html"
        f.write_text("<p>demo</p>", encoding="utf-8")
        run = FakeRun()
        pl.open_file(f, run=run, on=pl.MAC)
        pl.reveal_file(f, run=run, on=pl.MAC)
        self.assertEqual([c[0] for c in run.calls], [["open", str(f)], ["open", "-R", str(f)]])
        self.assertTrue(all("shell" not in c[1] for c in run.calls))

    def test_a_missing_file_or_a_refusal_is_said_plainly(self):
        with self.assertRaisesRegex(pl.PlatformError, "gone.html isn't there"):
            pl.open_file(self.home / "gone.html", run=FakeRun(), on=pl.MAC)
        f = self.home / "demo.xlsx"
        f.write_bytes(b"")
        with self.assertRaisesRegex(pl.PlatformError, "couldn't show demo.xlsx in its folder: no access"):
            pl.reveal_file(f, run=FakeRun(1, stderr="no access"), on=pl.MAC)


class Dialogs(unittest.TestCase):
    def test_the_folder_dialog_passes_text_as_arguments_not_script(self):
        run = FakeRun(stdout="/Users/demo/Reports/\n")
        prompt = 'Choose "Reports" & then quit'
        self.assertEqual(pl.choose_folder(prompt, start="/Users/demo", run=run, on=pl.MAC), Path("/Users/demo/Reports"))
        args = run.calls[0][0]
        self.assertEqual(args[:3], ["osascript", "-e", pl.FOLDER_SCRIPT])
        self.assertEqual(args[3:], [prompt, "/Users/demo"])
        self.assertNotIn(prompt, pl.FOLDER_SCRIPT)

    def test_the_save_dialog_suggests_a_safe_name(self):
        run = FakeRun(stdout="/Users/demo/Weekly report.html\n")
        got = pl.choose_save_file("Save the report", "Weekly: report?.html", run=run, on=pl.MAC)
        self.assertEqual(got, Path("/Users/demo/Weekly report.html"))
        self.assertEqual(run.calls[0][0][3:], ["Save the report", "Weekly- report-.html"])

    def test_cancel_is_none_and_a_failure_is_an_error(self):
        cancelled = FakeRun(1, stderr="execution error: User canceled. (-128)")
        self.assertIsNone(pl.choose_folder("Pick", run=cancelled, on=pl.MAC))
        self.assertIsNone(pl.choose_save_file("Save", "a.html", run=cancelled, on=pl.MAC))
        with self.assertRaisesRegex(pl.PlatformError, "didn't open"):
            pl.choose_folder("Pick", run=FakeRun(1, stderr="syntax error"), on=pl.MAC)

    @unittest.skipUnless(sys.platform == pl.MAC and shutil.which("osascript"), "needs macOS")
    def test_the_scripts_compile(self):
        """Both scripts are valid AppleScript (compiled by osacompile; no dialog is shown)."""
        with tempfile.TemporaryDirectory() as tmp:
            for i, script in enumerate((pl.FOLDER_SCRIPT, pl.SAVE_SCRIPT)):
                done = subprocess.run(["osacompile", "-o", os.path.join(tmp, f"{i}.scpt"), "-e", script],
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)


class WindowsIsNotBuiltYet(unittest.TestCase):
    def test_every_windows_branch_says_so(self):
        calls = (lambda: pl.data_dir(on=pl.WINDOWS), lambda: pl.onedrive_roots(on=pl.WINDOWS),
                 lambda: pl.open_file(__file__, run=FakeRun(), on=pl.WINDOWS),
                 lambda: pl.reveal_file(__file__, run=FakeRun(), on=pl.WINDOWS),
                 lambda: pl.choose_folder("Pick", run=FakeRun(), on=pl.WINDOWS),
                 lambda: pl.choose_save_file("Save", "a.html", run=FakeRun(), on=pl.WINDOWS))
        for call in calls:
            with self.assertRaisesRegex(pl.NotBuiltYet, "on Windows is not built yet"):
                call()

    def test_not_built_yet_is_a_platform_error(self):
        self.assertTrue(issubclass(pl.NotBuiltYet, pl.PlatformError))
        self.assertTrue(issubclass(pl.NotBuiltYet, NotImplementedError))


class FindClaude(unittest.TestCase):
    """#57: the Claude command for ask clark, found with a fake `which`; a .cmd or .bat is refused on every system."""

    def test_found_or_none(self):
        self.assertEqual(pl.find_claude(lambda name: "/opt/fictional/bin/" + name), "/opt/fictional/bin/claude")
        self.assertIsNone(pl.find_claude(lambda name: None))

    def test_a_cmd_or_bat_is_refused(self):
        for found in ("C:/Tools/claude.cmd", "C:/Tools/CLAUDE.BAT"):
            with self.assertRaises(pl.PlatformError) as said:
                pl.find_claude(lambda name, found=found: found)
            self.assertEqual(str(said.exception), "The copy of Claude Code on this computer can't be used safely by ask "
                             "clark. Install Claude Code's own app (claude.exe), then start clark again.")

    def test_an_exe_is_fine(self):
        self.assertEqual(pl.find_claude(lambda name: "C:/Tools/claude.exe"), "C:/Tools/claude.exe")


class NeverReadPlaces(unittest.TestCase):
    """#47b: the places ask clark never reads, moved here from creaite's reach.py because seven name Library/Application Support."""

    def test_the_39_rows_on_the_mac(self):
        rows = pl.never_read_places(on=pl.MAC)
        self.assertEqual(len(rows), 39)
        self.assertEqual(sum(1 for r in rows if r[0] == "home"), 29)
        self.assertEqual(sum(1 for r in rows if r[0] == "abs"), 10)
        self.assertEqual({r[2] for r in rows}, {"secret", "system"})
        self.assertEqual(len({(r[0], r[1]) for r in rows}), 39)
        self.assertTrue(all(r[1].startswith("/") for r in rows if r[0] == "abs"))
        self.assertEqual(len([r for r in rows if "Application Support" in r[1]]), 7)

    def test_windows_is_not_built_yet(self):
        with self.assertRaisesRegex(pl.NotBuiltYet, "on Windows is not built yet"):
            pl.never_read_places(on=pl.WINDOWS)


class SafeName(unittest.TestCase):
    def test_reserved_characters(self):
        self.assertEqual(pl.safe_name('a<b>c:d"e/f\\g|h?i*j.html'), "a-b-c-d-e-f-g-h-i-j.html")
        self.assertEqual(pl.safe_name("tab\there\x01.txt"), "tab-here-.txt")

    def test_device_names(self):
        for name in ("CON", "con", "NUL.html", "COM1", "com9.xlsx", "LPT1", "PRN", "AUX.txt"):
            self.assertEqual(pl.safe_name(name), "_" + name, name)
        for name in ("CONSOLE.html", "COM10", "NULL", "Demo CON.html"):
            self.assertEqual(pl.safe_name(name), name, name)

    def test_a_space_before_the_extension_is_still_a_device_name(self):
        for name in ("CON .txt", "NUL .html", "COM1 .x", "con  .txt", "CON .tar.gz", "CON.tar.gz", "LPT3   .a"):
            self.assertEqual(pl.safe_name(name), "_" + name, name)
        for name in ("CON x.txt", "A CON .txt", "CON1 .txt"):
            self.assertEqual(pl.safe_name(name), name, name)

    def test_the_console_and_superscript_device_names(self):
        for name in ("CONIN$", "conout$", "CONIN$.txt", "CONOUT$ .log",
                     "COM\u00b9", "COM\u00b2.txt", "COM\u00b3 .x", "LPT\u00b9", "lpt\u00b2.html", "LPT\u00b3"):
            self.assertEqual(pl.safe_name(name), "_" + name, name)
        for name in ("CONIN", "CON$", "COM\u2074", "COM\u00b9\u00b2"):
            self.assertEqual(pl.safe_name(name), name, name)

    def test_trailing_dot_or_space(self):
        self.assertEqual(pl.safe_name("report. . "), "report")
        self.assertEqual(pl.safe_name("  report.html  "), "report.html")
        self.assertEqual(pl.safe_name(" . "), "untitled")
        self.assertEqual(pl.safe_name(""), "untitled")

    def test_length_keeps_the_extension(self):
        got = pl.safe_name("x" * 300 + ".html")
        self.assertEqual(len(got), pl.MAX_NAME)
        self.assertTrue(got.endswith("x.html"))
        self.assertEqual(len(pl.safe_name("y" * 300)), pl.MAX_NAME)

    def test_path_length(self):
        folder = "/Users/demo/" + "d" * 200
        got = pl.safe_name("Weekly report for the demo project.html", folder=folder)
        self.assertLessEqual(len(str(Path(folder) / got)), pl.MAX_PATH - 1)
        self.assertTrue(got.endswith(".html"))
        with self.assertRaisesRegex(pl.PlatformError, "folder path is too long"):
            pl.safe_name("a.html", folder="/" + "d" * 250)

    def test_a_safe_name_is_unchanged(self):
        for name in ("Weekly report 28-10-2026.html", "DEMO-A-001.xlsx", "Ünïcode café.docx"):
            self.assertEqual(pl.safe_name(name), name)


class Replace(TempHome):
    def test_write_file_replaces_in_one_step_and_leaves_nothing_else(self):
        dest = self.home / "report.html"
        pl.write_file(dest, "first")
        pl.write_file(dest, "second – UTF-8 ✓")
        self.assertEqual(dest.read_text(encoding="utf-8"), "second – UTF-8 ✓")
        pl.write_file(dest, b"\x00bytes")
        self.assertEqual(dest.read_bytes(), b"\x00bytes")
        self.assertEqual([p.name for p in self.home.iterdir()], ["report.html"])

    def test_two_threads_writing_one_file_at_once_both_succeed(self):
        dest = self.home / "shared.html"
        contents = ["A" * 200000, "B" * 200000]
        start = threading.Barrier(2)
        failures = []

        def write(text):
            try:
                start.wait()
                for _ in range(20):
                    pl.write_file(dest, text)
            except BaseException as e:          # a shared temporary file would fail here
                failures.append(e)

        threads = [threading.Thread(target=write, args=(text,)) for text in contents]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(failures, [])
        self.assertIn(dest.read_text(encoding="utf-8"), contents)
        self.assertEqual([p.name for p in self.home.iterdir()], ["shared.html"])

    def test_each_write_names_its_own_temporary_file(self):
        names = []

        def replace(src, dst):
            names.append(Path(src).name)
            os.replace(src, dst)

        for _ in range(3):
            pl.write_file(self.home / "a.html", "x", replace=replace)
        self.assertEqual(len(set(names)), 3)

    def test_a_brief_lock_is_retried_with_backoff(self):
        tries, waits = [], []

        def replace(src, dst):
            tries.append(dst)
            if len(tries) < 3:
                raise PermissionError(13, "Permission denied")
            os.replace(src, dst)

        dest = self.home / "demo.xlsx"
        pl.write_file(dest, b"ok", sleep=waits.append, replace=replace)
        self.assertEqual(dest.read_bytes(), b"ok")
        self.assertEqual(waits, [pl.REPLACE_FIRST_WAIT, pl.REPLACE_FIRST_WAIT * 2])

    def test_a_file_that_stays_locked_is_named(self):
        """A real refusal: the folder is read-only, so os.replace fails every time."""
        folder = self.home / "locked"
        folder.mkdir()
        dest = folder / "Weekly report.html"
        dest.write_text("old", encoding="utf-8")
        tmp = self.home / "new.part"
        tmp.write_text("new", encoding="utf-8")
        folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(folder.chmod, stat.S_IRWXU)
        waits = []
        with self.assertRaisesRegex(pl.PlatformError, "couldn't save Weekly report.html because another program"):
            pl.replace_file(tmp, dest, sleep=waits.append)
        self.assertEqual(len(waits), pl.REPLACE_ATTEMPTS - 1)
        self.assertEqual(dest.read_text(encoding="utf-8"), "old")

    def test_the_temporary_file_is_removed_when_the_replace_fails(self):
        def refuse(src, dst):
            raise PermissionError(13, "Permission denied")

        with self.assertRaises(pl.PlatformError):
            pl.write_file(self.home / "a.html", "x", sleep=lambda s: None, replace=refuse)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_other_errors_are_not_retried(self):
        waits = []
        with self.assertRaises(FileNotFoundError):
            pl.replace_file(self.home / "nothing", self.home / "a.html", sleep=waits.append)
        self.assertEqual(waits, [])


class Private(TempHome):
    """#86: private folders and files, and moving a file in only if the name is free."""

    def mode(self, path):
        return stat.S_IMODE(os.stat(path).st_mode)

    @unittest.skipIf(os.name == "nt", "mode bits do nothing on Windows, where the profile's permissions apply")
    def test_a_private_folder_is_0700_new_or_already_there(self):
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        new = pl.private_folder(self.home / "a" / "b")
        self.assertEqual(self.mode(new), 0o700)
        (self.home / "c").mkdir()
        os.chmod(self.home / "c", 0o755)
        pl.private_folder(self.home / "c")
        self.assertEqual(self.mode(self.home / "c"), 0o700)

    def test_a_private_folder_is_never_a_link(self):
        (self.home / "elsewhere").mkdir()
        (self.home / "link").symlink_to(self.home / "elsewhere")
        with self.assertRaisesRegex(pl.PlatformError, "is a shortcut, not a real folder\\. Replace it with a real folder, then try again\\.$"):
            pl.private_folder(self.home / "link")

    @unittest.skipIf(os.name == "nt", "mode bits do nothing on Windows, where the profile's permissions apply")
    def test_a_private_file_is_empty_0600_even_at_umask_022_and_is_never_replaced(self):
        old = os.umask(0o022)
        self.addCleanup(os.umask, old)
        f = pl.private_file(self.home / "x.part")
        self.assertEqual((self.mode(f), f.stat().st_size), (0o600, 0))
        with self.assertRaises(FileExistsError):
            pl.private_file(f)

    def test_the_backups_folder_has_its_own_onedrive_wording(self):
        root = self.home / "OneDrive"
        (root / "b").mkdir(parents=True)
        with self.assertRaises(pl.PlatformError) as ctx:
            pl.check_data_dir(root / "b", roots=[root], what="backups")
        text = str(ctx.exception)
        self.assertIn("Backups can't be kept in", text)
        self.assertNotIn("backups can still go to OneDrive", text)


class MoveUnlessExists(TempHome):
    """The shared "put it in place only if the name is still free" (#43 To client, #86 backups)."""

    def staged(self, text="new"):
        src = self.home / ".stage.part"
        src.write_text(text, encoding="utf-8")
        return src

    def test_a_free_name_is_placed_and_the_source_is_gone(self):
        src, dest = self.staged("fresh"), self.home / "Report.html"
        self.assertIs(pl.move_unless_exists(src, dest), True)
        self.assertEqual(dest.read_text(encoding="utf-8"), "fresh")
        self.assertEqual([p.name for p in self.home.iterdir()], ["Report.html"], "no second name left behind")

    def test_a_taken_name_is_never_overwritten(self):
        src, dest = self.staged("new"), self.home / "Report.html"
        dest.write_text("the client's own", encoding="utf-8")
        self.assertIs(pl.move_unless_exists(src, dest), False)
        self.assertEqual(dest.read_text(encoding="utf-8"), "the client's own")
        self.assertTrue(src.exists(), "the caller still has its file to remove")

    def test_a_taken_name_that_is_a_folder_is_not_touched(self):
        src, dest = self.staged(), self.home / "Report.html"
        dest.mkdir()
        self.assertIs(pl.move_unless_exists(src, dest), False)
        self.assertTrue(dest.is_dir())

    def test_a_name_that_appears_between_the_check_and_the_link_is_not_overwritten(self):
        src, dest = self.staged("new"), self.home / "Report.html"
        self.assertFalse(dest.exists(), "the look a caller took: free")

        def late_link(a, b):                    # OneDrive finishes syncing the client's file just before the link
            Path(b).write_text("arrived late", encoding="utf-8")
            os.link(a, b)

        self.assertIs(pl.move_unless_exists(src, dest, link=late_link), False)
        self.assertEqual(dest.read_text(encoding="utf-8"), "arrived late")

    def test_a_disk_with_no_hard_links_gets_a_last_look_then_a_replace(self):
        import errno
        for code in (errno.EPERM, errno.EXDEV, errno.ENOTSUP):
            with self.subTest(errno.errorcode[code]):
                src, dest = self.staged("new"), self.home / f"a{code}.html"

                def no_links(a, b, code=code):
                    raise OSError(code, "no links here")

                self.assertIs(pl.move_unless_exists(src, dest, link=no_links), True)
                self.assertEqual(dest.read_text(encoding="utf-8"), "new")
                self.assertFalse(src.exists())

    def test_the_no_link_path_still_refuses_a_name_that_is_taken(self):
        import errno
        src, dest = self.staged("new"), self.home / "Report.html"
        dest.write_text("older", encoding="utf-8")
        calls = []

        def no_links(a, b):
            raise OSError(errno.EPERM, "no links here")

        self.assertIs(pl.move_unless_exists(src, dest, link=no_links, replace=lambda a, b: calls.append((a, b))), False)
        self.assertEqual((calls, dest.read_text(encoding="utf-8")), ([], "older"))

    def test_any_other_error_is_raised_and_nothing_is_replaced(self):
        import errno
        src, dest = self.staged(), self.home / "Report.html"

        def broken(a, b):
            raise OSError(errno.EIO, "disk error")

        with self.assertRaises(OSError):
            pl.move_unless_exists(src, dest, link=broken, replace=lambda a, b: self.fail("replaced"))
        self.assertFalse(dest.exists())

    def test_write_file_unless_exists_writes_bytes_or_text_and_leaves_no_temporary_file(self):
        self.assertIs(pl.write_file_unless_exists(self.home / "a.html", "ünï ✓"), True)
        self.assertIs(pl.write_file_unless_exists(self.home / "b.html", b"\x00raw"), True)
        self.assertEqual((self.home / "a.html").read_text(encoding="utf-8"), "ünï ✓")
        self.assertEqual((self.home / "b.html").read_bytes(), b"\x00raw")
        self.assertEqual(sorted(p.name for p in self.home.iterdir()), ["a.html", "b.html"])

    def test_write_file_unless_exists_never_replaces_and_cleans_up(self):
        dest = self.home / "a.html"
        dest.write_text("client's", encoding="utf-8")
        self.assertIs(pl.write_file_unless_exists(dest, "ours"), False)
        self.assertEqual(dest.read_text(encoding="utf-8"), "client's")
        self.assertEqual([p.name for p in self.home.iterdir()], ["a.html"], "the temporary file is gone")

    def test_write_file_unless_exists_loses_a_race_without_overwriting(self):
        dest = self.home / "a.html"

        def late_link(a, b):
            Path(b).write_text("arrived late", encoding="utf-8")
            os.link(a, b)

        self.assertIs(pl.write_file_unless_exists(dest, "ours", link=late_link), False)
        self.assertEqual(dest.read_text(encoding="utf-8"), "arrived late")
        self.assertEqual([p.name for p in self.home.iterdir()], ["a.html"])

    def test_write_file_unless_exists_removes_its_temporary_file_when_the_move_fails(self):
        import errno

        def broken(a, b):
            raise OSError(errno.EIO, "disk error")

        with self.assertRaises(OSError):
            pl.write_file_unless_exists(self.home / "a.html", "x", link=broken)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

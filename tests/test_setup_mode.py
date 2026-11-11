"""#836 step 4a: the setup service (src/clark/setup_mode.py). Run: python3 dev/run_tests.py test_setup_mode
Temporary home and folders only. The folder window is always a fake function, never the real one; the real one is only
compared by identity. No server, no port, no store."""
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from _paths import ROOT

from clark import ask_folders, doctor, platform as pl, setup_mode


class Case(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.default = self.home / "Library" / "Application Support" / "clark"
        self.default.parent.mkdir(parents=True)
        self.onedrive = self.home / "OneDrive - Work"
        self.onedrive.mkdir()
        self.good = self.home / "Elsewhere"
        self.good.mkdir()

    def setup(self, answer=None, **over):
        calls = []

        def choose(prompt):
            calls.append(prompt)
            if isinstance(answer, Exception):
                raise answer
            return answer
        kw = dict(home=self.home, on=pl.MAC, choose_folder=choose, onedrive_roots=lambda: [self.onedrive],
                  environ={})
        kw.update(over)
        service = setup_mode.Setup(self.default, **kw)
        service.calls = calls
        return service

    def pointer(self):
        return self.default.parent / setup_mode.POINTER_NAME


class Report(Case):
    def test_the_report_is_the_doctors_lines_as_data(self):
        report = self.setup().report()
        self.assertEqual([r["id"] for r in report["checks"]], [doctor.check_id(c) for c in doctor.CHECKS])
        self.assertTrue(all(set(r) == {"id", "status", "words", "required"} for r in report["checks"]))
        self.assertEqual(report["folder"], "~/Library/Application Support/clark")

    def test_ready_follows_the_doctors_rule(self):
        service = self.setup()
        service.folder = self.onedrive / "clark"
        report = service.report()
        self.assertFalse(report["ready"])
        row = [r for r in report["checks"] if r["id"] == "data_not_in_onedrive"][0]
        self.assertEqual((row["status"], row["required"]), (doctor.FIX, True))

    def test_an_advice_line_alone_does_not_stop_ready(self):
        only = tuple(c for c in doctor.CHECKS if not c.required)
        self.assertTrue(only)
        self.assertTrue(self.setup(checks=only).report()["ready"])

    def test_a_report_makes_nothing(self):
        self.setup().report()
        self.assertFalse(self.default.exists())
        self.assertFalse(self.pointer().exists())


class Choose(Case):
    def test_a_good_folder_is_kept_and_reported(self):
        service = self.setup(str(self.good))
        report = service.choose("Choose")
        self.assertEqual(service.calls, ["Choose"])
        self.assertEqual(report["folder"], "~/Elsewhere")
        self.assertEqual(self.pointer().read_text(encoding="utf-8"), str(self.good) + "\n")
        self.assertEqual(service.folder, self.good)

    def test_the_pointers_own_folder_is_made_when_it_is_missing(self):
        self.default.parent.rmdir()                      # a fresh computer: nothing beside the default folder yet
        service = self.setup(str(self.good))
        report = service.choose("Choose")
        self.assertEqual(report["folder"], "~/Elsewhere")
        self.assertEqual(self.pointer().read_text(encoding="utf-8"), str(self.good) + "\n")
        self.assertEqual(service.folder, self.good)
        self.assertFalse(self.default.exists())         # the data folder itself is still not made here

    def test_a_pointer_that_cannot_be_written_is_a_plain_refusal_not_an_error(self):
        self.default.parent.rmdir()
        self.default.parent.write_text("in the way", encoding="utf-8")       # the pointer's folder can't be made or written
        service = self.setup(str(self.good))
        with self.assertRaises(setup_mode.Refused) as caught:
            service.choose("Choose")
        self.assertEqual(caught.exception.code, "cant_save")
        self.assertEqual(caught.exception.words, ask_folders.MESSAGES["cant_save"])
        self.assertEqual(service.folder, self.default)
        self.assertEqual(list(self.good.iterdir()), [])
        self.assertEqual(self.default.parent.read_text(encoding="utf-8"), "in the way")

    def test_cancel_changes_nothing(self):
        service = self.setup(None)
        self.assertIsNone(service.choose("Choose"))
        self.assertFalse(self.pointer().exists())
        self.assertEqual(service.folder, self.default)

    def test_refused_answers_write_nothing_and_say_the_doctors_words(self):
        link = self.home / "link"
        link.symlink_to(self.good)
        a_file = self.home / "file.txt"
        a_file.write_text("x", encoding="utf-8")
        named = [str(self.home / "missing"), str(a_file), str(link)]           # a real path that isn't a usable folder: named
        unnamed = ["relative/path", "", 5, str(self.good) + "\n/etc", "/" + "a" * 1001, str(self.good) + "\x00"]   # not a path
        for answer in named + unnamed:
            with self.subTest(answer=answer):
                service = self.setup(answer)
                with self.assertRaises(setup_mode.Refused) as caught:
                    service.choose("Choose")
                self.assertEqual(caught.exception.code, "folder_refused")
                words = caught.exception.words
                if answer in named:
                    self.assertIn("can't be saved in ~/" + Path(answer).name, words)
                else:
                    self.assertEqual(words, ask_folders.MESSAGES["not_a_folder"])
                self.assertNotIn("Application Support", words)        # never the folder in use: it was not the one refused
                self.assertNotIn("\n", words)
                self.assertFalse(self.pointer().exists())
                self.assertEqual(service.folder, self.default)

    def test_a_onedrive_folder_is_refused_with_the_platforms_own_words(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        with self.assertRaises(setup_mode.Refused) as caught:
            self.setup(str(inside)).choose("Choose")
        words = caught.exception.words
        self.assertEqual(words, str(self.expect_onedrive(inside)))
        self.assertFalse(self.pointer().exists())

    def expect_onedrive(self, inside):
        try:
            pl.check_data_dir(inside, [self.onedrive])
        except pl.PlatformError as e:
            return e
        self.fail("not refused")

    @unittest.skipIf(not hasattr(os, "geteuid") or os.geteuid() == 0, "root can save anywhere")
    def test_a_folder_that_cannot_be_saved_in_is_refused(self):
        locked = self.home / "locked"
        locked.mkdir()
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)
        with self.assertRaises(setup_mode.Refused) as caught:
            self.setup(str(locked)).choose("Choose")
        self.assertIn("can't be saved in ~/locked", caught.exception.words)
        self.assertFalse(self.pointer().exists())

    def test_a_window_that_cannot_open_lets_the_platform_error_out(self):
        with self.assertRaises(pl.PlatformError):
            self.setup(pl.PlatformError("could not be opened")).choose("Choose")
        self.assertFalse(self.pointer().exists())

    def test_the_lock_is_free_again_after_an_error(self):
        service = self.setup(pl.PlatformError("x"))
        for _ in range(2):
            with self.assertRaises(pl.PlatformError):
                service.choose("Choose")

    def test_a_second_window_while_one_is_open_is_busy(self):
        inside, release = threading.Event(), threading.Event()
        count = []

        def slow(prompt):
            count.append(prompt)
            inside.set()
            release.wait(5)
            return None
        service = self.setup(choose_folder=slow)
        first = threading.Thread(target=service.choose, args=("a",))
        first.start()
        self.assertTrue(inside.wait(5))
        with self.assertRaises(setup_mode.Refused) as caught:
            service.choose("b")
        self.assertEqual(caught.exception.code, "busy")
        self.assertEqual(caught.exception.words, setup_mode.WORDS["busy"])
        self.assertIn("folder window", caught.exception.words)           # a page can show it as it is: it names the window
        self.assertTrue(caught.exception.words.endswith("Nothing was changed."))
        release.set()
        first.join(5)
        self.assertEqual(count, ["a"])

    def test_the_real_chooser_is_the_default_and_is_not_called_here(self):
        service = setup_mode.Setup(self.default, home=self.home, on=pl.MAC)
        self.assertIs(service.choose_folder, pl.choose_folder)

    def test_without_a_fake_nothing_opens_off_a_mac(self):
        service = setup_mode.Setup(self.default, home=self.home, on="linux", onedrive_roots=lambda: [])
        service.choose_folder = lambda prompt: pl.choose_folder(prompt, on="linux")
        with self.assertRaises(pl.NotBuiltYet):
            service.choose("Choose")


class Remembered(Case):
    def test_a_kept_folder_comes_back(self):
        self.setup(str(self.good)).choose("Choose")
        self.assertEqual(self.setup().remembered(), self.good)

    def test_no_file_gives_none(self):
        self.assertIsNone(self.setup().remembered())

    def test_odd_or_refused_values_are_ignored(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        for text in ("", "\n", "relative", str(self.home / "gone"), str(inside), "\x00", "\udcff"):
            with self.subTest(text=text):
                self.pointer().write_bytes(text.encode("utf-8", "surrogateescape"))
                self.assertIsNone(self.setup().remembered())

    def test_a_folder_that_went_away_is_ignored(self):
        gone = self.home / "temp"
        gone.mkdir()
        self.setup(str(gone)).choose("Choose")
        gone.rmdir()
        self.assertIsNone(self.setup().remembered())

    def test_nothing_else_is_written(self):
        before = {p for p in self.home.rglob("*")}
        self.setup(str(self.good)).choose("Choose")
        made = {p for p in self.home.rglob("*")} - before
        self.assertEqual(made, {self.pointer()})


class Source(unittest.TestCase):
    def test_its_borrowed_sentences_are_the_folder_pickers_own_unchanged(self):
        # setup_mode may not import ask_folders (which opens the store), so it carries the sentences; they must stay equal.
        for key in ("cant_save", "not_a_folder"):
            self.assertEqual(setup_mode.WORDS[key], ask_folders.MESSAGES[key], key)

    def test_it_reaches_no_store_and_names_no_system_text(self):
        text = (ROOT / "src" / "clark" / "setup_mode.py").read_text(encoding="utf-8")
        for word in ("import store", "from clark import store", "publish", "movement", "subprocess", "osascript", "~/Library"):
            self.assertNotIn(word, text.replace("publishes", ""), word)


class MutationSweep(Case):
    """Pins found by the mutation sweep of this file (each line names the change that used to pass unnoticed)."""

    def test_the_pointer_file_name_is_the_one_the_design_names(self):
        self.assertEqual(setup_mode.POINTER_NAME, "clark-data-folder")

    def test_path_length_edge_is_1000(self):
        plain = setup_mode._plain_path
        self.assertIsNotNone(plain("/" + "a" * 999))
        self.assertIsNone(plain("/" + "a" * 1000))

    def test_control_characters_edges(self):
        for code in (0, 31, 127):
            with self.subTest(code=code):
                self.assertIsNone(setup_mode._plain_path("/tmp/a" + chr(code) + "b"))
        self.assertIsNotNone(setup_mode._plain_path("/tmp/a b"))            # 32 is a space and is allowed

    def test_the_given_seams_reach_the_doctors_view(self):
        env = {"HOME": "x"}
        service = self.setup(environ=env)
        self.assertIs(service.seen().environ, env)
        self.assertEqual(service.seen().onedrive_roots(), [self.onedrive])
        elsewhere = self.setup(onedrive_roots=lambda: [self.good])           # a root the platform would not find itself
        self.assertEqual(elsewhere.seen().onedrive_roots(), [self.good])

    def test_the_given_checks_are_the_ones_run(self):
        one = (doctor.CHECKS[0],)
        self.assertEqual(len(self.setup(checks=one).report()["checks"]), 1)

    def test_ready_rule_required_unknown_stops_and_advice_fix_does_not(self):
        def unknown(seen):
            return doctor.Line(doctor.NOT_CHECKED, "x")

        def fix(seen):
            return doctor.Line(doctor.FIX, "x")
        unknown.__name__, fix.__name__ = "check_unknown", "check_fix"
        self.assertFalse(self.setup(checks=(doctor.Check("u", True, unknown),)).report()["ready"])
        self.assertTrue(self.setup(checks=(doctor.Check("f", False, fix),)).report()["ready"])
        self.assertFalse(self.setup(checks=(doctor.Check("f", True, fix),)).report()["ready"])

    def test_an_answer_that_is_a_path_object_is_taken(self):
        service = self.setup(self.good)
        self.assertEqual(service.choose("Choose")["folder"], "~/Elsewhere")

    def test_the_kept_folder_is_the_resolved_one(self):
        real = self.home / "real"
        real.mkdir()
        (self.home / "ln").symlink_to(real)
        service = self.setup(str(self.home / "ln" / ".." / "real"))
        service.choose("Choose")
        self.assertEqual(self.pointer().read_text(encoding="utf-8"), str(real) + "\n")
        self.assertEqual(service.folder, real)

    def test_a_refusal_names_the_resolved_folder(self):
        locked = self.home / "locked2"
        locked.mkdir()
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)
        if os.geteuid() == 0:
            self.skipTest("root can save anywhere")
        (self.home / "ln").symlink_to(self.home)
        with self.assertRaises(setup_mode.Refused) as caught:
            self.setup(str(self.home / "ln" / "locked2")).choose("Choose")
        self.assertIn("~/locked2", caught.exception.words)
        self.assertNotIn("/ln/", caught.exception.words)

    def test_a_platform_error_on_the_pointer_is_a_plain_refusal(self):
        from unittest import mock
        service = self.setup(str(self.good))
        with mock.patch.object(pl, "write_file", side_effect=pl.PlatformError("no")):
            with self.assertRaises(setup_mode.Refused) as caught:
                service.choose("Choose")
        self.assertEqual(caught.exception.code, "cant_save")
        self.assertEqual(service.folder, self.default)

    def test_a_folder_with_a_non_ascii_name_comes_back(self):
        odd = self.home / "Caf\u00e9 \u2603"
        odd.mkdir()
        self.setup(str(odd)).choose("Choose")
        self.assertEqual(self.setup().remembered(), odd)


if __name__ == "__main__":
    unittest.main()

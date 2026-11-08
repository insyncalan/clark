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

from clark import doctor, platform as pl, setup_mode


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
        self.assertTrue(all(set(r) == {"id", "status", "words", "required", "page"} for r in report["checks"]))
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
        bad = [str(self.home / "missing"), "relative/path", "", 5, str(a_file), str(link),
               str(self.good) + "\n/etc", "/" + "a" * 1001, str(self.good) + "\x00"]
        for answer in bad:
            with self.subTest(answer=answer):
                service = self.setup(answer)
                with self.assertRaises(setup_mode.Refused) as caught:
                    service.choose("Choose")
                self.assertEqual(caught.exception.code, "folder_refused")
                self.assertIn("can't be saved in", caught.exception.words)
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

    def test_a_onedrive_refusal_has_a_page_line_with_no_settings_step(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        with self.assertRaises(setup_mode.Refused) as caught:
            self.setup(str(inside)).choose("Choose")
        page = caught.exception.page
        self.assertNotEqual(page, caught.exception.words)
        self.assertIn("inside OneDrive", page)
        self.assertIn("Choose a folder on this computer that OneDrive doesn't sync.", page)
        self.assertIn("Backups can still go to OneDrive.", page)

    def test_no_refusal_page_line_sends_the_person_to_terminal_or_settings(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        link = self.home / "link"
        link.symlink_to(self.good)
        a_file = self.home / "file.txt"
        a_file.write_text("x", encoding="utf-8")
        answers = [str(inside), str(self.home / "missing"), "relative/path", "", 5, str(a_file), str(link), str(self.good) + "\x00"]
        for answer in answers:
            with self.subTest(answer=answer):
                with self.assertRaises(setup_mode.Refused) as caught:
                    self.setup(answer).choose("Choose")
                page = caught.exception.page
                self.assertTrue(page)
                for bad in ("Terminal", "Settings", "\u203a", "start clark again", "python3", "xcode"):
                    self.assertNotIn(bad, page)
        status, body = self.setup(str(inside), prompt="Pick").api_folder()
        self.assertEqual(status, 409)
        self.assertNotIn("Settings", body["page"])
        self.assertIn("Settings", body["message"])           # the doctor's own line is kept beside it, unchanged

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


class Api(Case):
    """Slice 2: what the server's setup routes ask of the service. Each answers (status, body), or None when it is not wired."""

    def test_checks_is_the_report(self):
        service = self.setup()
        self.assertEqual(service.api_checks(), (200, service.report()))

    def test_folder_without_a_prompt_is_not_wired(self):
        service = self.setup(str(self.good))
        self.assertIsNone(service.api_folder())
        self.assertEqual(service.calls, [])

    def test_folder_cancel_changes_nothing(self):
        service = self.setup(None, prompt="Pick")
        self.assertEqual(service.api_folder(), (200, {"ok": True, "chosen": False}))
        self.assertEqual(service.calls, ["Pick"])
        self.assertFalse(self.pointer().exists())

    def test_folder_chosen_gives_the_new_report(self):
        service = self.setup(str(self.good), prompt="Pick")
        status, body = service.api_folder()
        self.assertEqual(status, 200)
        self.assertEqual((body["ok"], body["chosen"], body["folder"]), (True, True, "~/Elsewhere"))
        self.assertEqual(set(body), {"ok", "chosen", "ready", "folder", "checks"})
        self.assertTrue(self.pointer().exists())

    def test_folder_refused_carries_the_checks_own_words(self):
        inside = self.onedrive / "clark"
        inside.mkdir()
        status, body = self.setup(str(inside), prompt="Pick").api_folder()
        self.assertEqual((status, body["ok"], body["code"]), (409, False, "folder_refused"))
        self.assertIn("OneDrive", body["message"])
        self.assertFalse(self.pointer().exists())

    def test_folder_window_that_will_not_open_is_dialog_failed(self):
        service = self.setup(pl.PlatformError("The folder window could not be opened. " + pl.TRY_AGAIN), prompt="Pick")
        status, body = service.api_folder()
        self.assertEqual((status, body["code"]), (409, "dialog_failed"))
        self.assertEqual(body["message"], "The folder window could not be opened. " + pl.TRY_AGAIN)

    def test_folder_while_a_window_is_open_is_busy_in_existing_words(self):
        inside, release = threading.Event(), threading.Event()

        def slow(prompt):
            inside.set()
            release.wait(5)
            return None
        service = self.setup(choose_folder=slow, prompt="Pick")
        first = threading.Thread(target=service.api_folder)
        first.start()
        self.assertTrue(inside.wait(5))
        self.assertEqual(service.api_folder(), (409, {"ok": False, "code": "busy", "message": pl.TRY_AGAIN}))
        release.set()
        first.join(5)

    def test_finish_without_a_seam_is_not_wired(self):
        self.assertIsNone(self.setup().api_finish())

    def test_finish_gives_the_helpers_words(self):
        service = self.setup(finish=lambda: (True, ["one", "two"]))
        self.assertEqual(service.api_finish(), (200, {"ok": True, "finished": True, "words": ["one", "two"]}))
        service = self.setup(finish=lambda: (False, ["no"]))
        self.assertEqual(service.api_finish(), (200, {"ok": True, "finished": False, "words": ["no"]}))

    def test_finish_one_at_a_time(self):
        inside, release = threading.Event(), threading.Event()

        def slow():
            inside.set()
            release.wait(5)
            return True, []
        service = self.setup(finish=slow)
        first = threading.Thread(target=service.api_finish)
        first.start()
        self.assertTrue(inside.wait(5))
        self.assertEqual(service.api_finish(), (409, {"ok": False, "code": "busy", "message": pl.TRY_AGAIN}))
        release.set()
        first.join(5)

    def test_done_checks_again_and_refuses_while_a_required_check_fails(self):
        service = self.setup()
        service.folder = self.onedrive / "clark"
        status, body = service.api_done()
        self.assertEqual((status, body["ok"], body["code"], body["ready"]), (409, False, "not_ready", False))
        self.assertEqual(body["checks"], service.report()["checks"])

    def test_done_when_ready_says_restart(self):
        service = self.setup(checks=[])
        self.assertEqual(service.api_done(), (200, {"ok": True, "restart": True}))

    def test_done_trusts_nothing_from_before(self):
        service = self.setup(checks=[])
        self.assertTrue(service.report()["ready"])
        service.checks = [c for c in doctor.CHECKS if c.required]
        service.folder = self.onedrive / "clark"
        self.assertEqual(service.api_done()[0], 409)


class Relaunch(Case):
    """Design item 8: when the page's done is accepted and the server has stopped, main starts the normal clark on the chosen folder."""

    def run_main(self, serve_calls, start_error=None):
        import io
        started = []

        def start(argv, env, log, cwd=None):
            started.append((argv, env, log, cwd))
            if start_error:
                raise start_error
        seen = {}

        def serve(port, out, err, setup):
            setup.checks = []
            seen["service"] = setup
            return serve_calls(setup)
        err = io.StringIO()
        code = setup_mode.main(["--data", str(self.default), "--port", "8801"], out=io.StringIO(), err=err, serve=serve,
                               environ={}, start=start)
        return code, started, err.getvalue()

    def test_an_accepted_done_starts_clark_on_the_chosen_folder_after_the_server_stopped(self):
        import sys
        order = []

        def serve(setup):
            setup.folder = self.good
            order.append(setup.api_done())
            order.append("stopped")
            return 0
        code, started, _ = self.run_main(serve)
        self.assertEqual((code, order[0][1]["restart"]), (0, True))
        (argv, env, log, cwd), = started
        self.assertEqual(argv, [sys.executable, "-m", "clark", "--data", str(self.good), "--port", "8801"])
        self.assertEqual((env["CLARK_LAUNCHED"], env["CLARK_PORT"], log, cwd), ("1", "8801", self.good / "server.log", str(self.good)))

    def test_a_server_that_stopped_without_an_accepted_done_starts_nothing(self):
        self.assertEqual(self.run_main(lambda setup: 0)[:2], (0, []))
        self.assertEqual(self.run_main(lambda setup: 1)[:2], (1, []))

        def not_ready(setup):
            setup.checks = [c for c in doctor.CHECKS if c.required]
            setup.folder = self.onedrive / "clark"
            self.assertEqual(setup.api_done()[0], 409)
            return 0
        self.assertEqual(self.run_main(not_ready)[1], [])

    def test_a_start_that_fails_says_the_systems_words_and_exits_1(self):
        def serve(setup):
            setup.api_done()
            return 0
        code, started, err = self.run_main(serve, start_error=pl.PlatformError("THE WORDS"))
        self.assertEqual((code, len(started), "THE WORDS" in err), (1, 1, True))


class Source(unittest.TestCase):
    def test_it_reaches_no_store_and_names_no_system_text(self):
        text = (ROOT / "src" / "clark" / "setup_mode.py").read_text(encoding="utf-8")
        for word in ("import store", "from clark import store", "publish", "movement", "subprocess", "osascript", "~/Library"):
            self.assertNotIn(word, text.replace("publishes", ""), word)


if __name__ == "__main__":
    unittest.main()

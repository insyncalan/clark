"""#836 step 4c: the launcher's hooks into setup mode (src/clark/launch.py).

Run: python3 dev/run_tests.py test_launcher_setup
Nothing real is started or opened: every system call is a fake (as test_launcher.py). The setup seam is `setup(port, folder,
reason)`: it starts the setup server and opens its window, and answers True when it did. It is off (None) until the setup
entry point and the page exist, so the launcher's old lines are what a person sees today; these tests give it a fake.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC

from clark import __version__, appfiles, launch, platform as pl, same_version, setup_mode
from test_launcher import Fakes, as_the_mac


class FakeSetup:
    def __init__(self, answer=True):
        self.calls, self.answer = [], answer

    def __call__(self, port, folder, reason):
        self.calls.append((port, folder, reason))
        return self.answer


class Hooks(unittest.TestCase):
    def setUp(self):
        as_the_mac(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "clark-data"
        self.folder.mkdir()
        self.setup = FakeSetup()

    def run_launch(self, fakes, **kw):
        base = dict(fakes.kw(), setup=self.setup, data_problem=lambda folder, environ: None)
        base.update(kw)
        return launch.launch(8800, self.folder, **base)

    def test_an_update_that_cannot_be_finished_says_its_line_then_hands_over_to_setup(self):
        f = Fakes([launch.NOTHING])
        code = self.run_launch(f, finish=lambda folder, say: say("UPDATE LINE") and False)
        self.assertEqual((code, self.setup.calls), (0, [(8800, self.folder, "update_stopped")]))
        self.assertEqual((f.said, f.started), (["UPDATE LINE"], []))

    def test_when_setup_does_not_come_up_the_old_exit_and_line_stay(self):
        f = Fakes([launch.NOTHING])
        self.setup.answer = False
        code = self.run_launch(f, finish=lambda folder, say: say("UPDATE LINE") and False)
        self.assertEqual((code, f.said, f.started), (1, ["UPDATE LINE"], []))

    def test_a_folder_of_mixed_versions_says_the_message_then_hands_over_with_the_version_reason(self):
        f = Fakes([launch.NOTHING])
        self.addCleanup(same_version._ANSWERS.clear)
        same_version._ANSWERS[str(None)] = True
        code = self.run_launch(f)
        self.assertEqual((code, self.setup.calls), (0, [(8800, self.folder, "version")]))
        self.assertEqual((f.said, f.started), ([same_version.MESSAGE], []))
        self.setup.answer = False
        self.assertEqual(self.run_launch(Fakes([launch.NOTHING])), 1)

    def test_a_required_data_check_that_fails_says_its_words_then_hands_over(self):
        f = Fakes([launch.NOTHING])
        code = self.run_launch(f, data_problem=lambda folder, environ: "THE CHECK'S WORDS")
        self.assertEqual((code, self.setup.calls), (0, [(8800, self.folder, "data_folder")]))
        self.assertEqual((f.said, f.started, f.asked), (["THE CHECK'S WORDS"], [], []))

    def test_a_clean_check_starts_clark_as_before_and_setup_is_never_called(self):
        f = Fakes([launch.NOTHING, launch.OURS])
        self.assertEqual(self.run_launch(f), 0)
        self.assertEqual((self.setup.calls, len(f.started)), ([], 1))

    def test_the_port_cases_and_the_lock_are_not_setup_cases(self):
        for seen in (launch.OTHER_DATA, launch.NOT_CLARK):
            f = Fakes([seen])
            self.assertEqual(self.run_launch(f), 1)
        f = Fakes([launch.NOTHING], process_exits=True)
        self.assertEqual(self.run_launch(f), 1)                       # clark did not finish starting
        with mock.patch.object(launch, "lock_refusal", return_value="LOCK LINE"):
            f = Fakes([launch.NOTHING])
            self.assertEqual(self.run_launch(f), 1)
            self.assertEqual(f.said, ["LOCK LINE"])
        self.assertEqual(self.setup.calls, [])

    def test_with_no_setup_seam_nothing_new_runs(self):
        asked = []
        f = Fakes([launch.NOTHING, launch.OURS])
        kw = dict(f.kw(), data_problem=lambda *a: asked.append(a))
        self.assertEqual(launch.launch(8800, self.folder, **kw), 0)
        self.assertEqual(asked, [])
        self.assertEqual(launch.launch(8800, self.folder, **dict(Fakes([launch.NOTHING]).kw(), finish=lambda folder, say: False)), 1)


class DataProblem(unittest.TestCase):
    def setUp(self):
        as_the_mac(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_a_folder_that_can_be_saved_in_has_no_problem(self):
        self.assertIsNone(launch.data_problem(self.root, {}))

    def test_a_data_folder_that_is_a_file_gives_the_doctors_own_words(self):
        blocker = self.root / "file"
        blocker.write_text("x", encoding="utf-8")
        words = launch.data_problem(blocker, {})
        self.assertIn("can't be saved in", words)
        self.assertEqual(words.split(" can't")[0].startswith("Your clark data"), True)

    def test_only_the_data_checks_are_asked_not_the_port_or_python(self):
        asked = []
        real = launch.doctor.run_check
        launch.doctor.run_check = lambda check, seen: (asked.append(launch.doctor.check_id(check)), real(check, seen))[1]
        try:
            launch.data_problem(self.root, {})
        finally:
            launch.doctor.run_check = real
        self.assertEqual(asked, ["data_folder", "data_not_in_onedrive"])


class MainHooks(unittest.TestCase):
    def setUp(self):
        as_the_mac(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.said, self.setup = [], FakeSetup()

    def main(self, argv, roots=(), **seams):
        f = Fakes([launch.OURS])
        kw = f.kw()
        for k in ("say", "environ", "free"):
            kw.pop(k)
        kw.update(seams)
        self.fakes = f
        return launch.main(argv, say=self.said.append, environ={}, home=self.home, onedrive_roots=list(roots), **kw)

    def test_a_onedrive_folder_hands_over_to_setup_and_the_folder_is_not_made(self):
        root = self.home / "OneDrive-Fictional"
        root.mkdir()
        want = root / "clark"
        self.assertEqual(self.main(["--data", str(want)], [root], setup=self.setup), 0)
        self.assertEqual(self.setup.calls, [(8766, want, "data_folder")])
        self.assertFalse(want.exists())
        self.assertEqual((self.fakes.started, self.fakes.asked), ([], []))

    def test_if_setup_does_not_come_up_the_old_onedrive_line_is_said(self):
        root = self.home / "OneDrive-Fictional"
        root.mkdir()
        self.setup.answer = False
        self.assertEqual(self.main(["--data", str(root / "clark")], [root], setup=self.setup), 1)
        self.assertIn("is inside OneDrive", self.said[0])

    def test_a_folder_that_cannot_be_made_hands_over_to_setup(self):
        blocker = self.home / "file"
        blocker.write_text("x", encoding="utf-8")
        self.assertEqual(self.main(["--data", str(blocker / "inside")], setup=self.setup), 0)
        self.assertEqual(self.setup.calls, [(8766, blocker / "inside", "data_folder")])

    def test_a_bad_port_is_not_a_setup_case(self):
        self.assertEqual(self.main(["--port", "abc"], setup=self.setup), 2)
        self.assertEqual(self.setup.calls, [])

    def test_no_setup_seam_keeps_the_old_line_and_exit(self):
        blocker = self.home / "file"
        blocker.write_text("x", encoding="utf-8")
        self.assertEqual(self.main(["--data", str(blocker / "inside")]), 1)
        self.assertRegex(self.said[0], r"^The data folder can't be made")


class Pointer(unittest.TestCase):
    """The pointer file (setup_mode.POINTER_NAME, beside the default folder) is read in one place, main."""

    def setUp(self):
        as_the_mac(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.default = self.home / "Library" / "Application Support" / "clark"
        self.pointer = self.default.parent / setup_mode.POINTER_NAME
        self.chosen = self.home / "chosen"
        self.chosen.mkdir()
        self.said = []

    def main(self, argv=(), roots=()):
        f = Fakes([launch.OURS])
        kw = f.kw()
        for k in ("say", "environ", "free"):
            kw.pop(k)
        self.fakes = f
        code = launch.main(list(argv), say=self.said.append, environ={}, home=self.home, onedrive_roots=list(roots), **kw)
        return code, f.asked[0][1]

    def write(self, text):
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        self.pointer.write_text(text, encoding="utf-8")

    def test_no_pointer_file_uses_the_default_folder(self):
        self.assertEqual(self.main(), (0, appfiles.data_mark(self.default)))

    def test_a_good_pointer_is_the_data_folder(self):
        self.write(str(self.chosen) + "\n")
        self.assertEqual(self.main(), (0, appfiles.data_mark(self.chosen.resolve())))
        self.assertFalse(self.default.exists())

    def test_data_on_the_command_line_wins_over_the_pointer(self):
        self.write(str(self.chosen) + "\n")
        other = self.home / "other"
        other.mkdir()
        self.assertEqual(self.main(["--data", str(other)]), (0, appfiles.data_mark(other)))

    def test_a_pointer_that_fails_the_checks_is_ignored_not_trusted(self):
        onedrive = self.home / "OneDrive-Fictional"
        (onedrive / "in").mkdir(parents=True)
        for bad in (str(onedrive / "in"), "relative/path", str(self.home / "missing"), "", "\x00x", "x" * 2000,
                    str(self.home / "file")):
            (self.home / "file").write_text("x", encoding="utf-8")
            self.write(bad + "\n")
            self.assertEqual(self.main(roots=[onedrive]), (0, appfiles.data_mark(self.default)), bad)

    def test_a_pointer_that_is_a_link_is_ignored(self):
        link = self.home / "link"
        link.symlink_to(self.chosen)
        self.write(str(link) + "\n")
        self.assertEqual(self.main(), (0, appfiles.data_mark(self.default)))


class StartSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "refused" / "clark"            # never made
        self.logs = self.root / "Logs" / "clark"
        self.process = type("P", (), {"terminated": False, "poll": lambda s: None,
                                      "terminate": lambda s: setattr(s, "terminated", True)})()

    def go(self, healths=(launch.OURS,), fakes=None, **kw):
        f = fakes or Fakes(list(healths))
        self.f = f
        base = f.kw()
        args = dict(say=f.said.append, environ={"HOME": "/nowhere"}, start=base["start"], health=base["health"], wait=base["wait"],
                    find_chrome=base["find_chrome"], open_window=base["open_window"], open_browser=base["open_browser"],
                    log_dir=lambda: self.logs)
        args.update(kw)
        return launch.start_setup(8800, self.folder, args.pop("reason", "data_folder"), **args)

    def test_it_starts_the_setup_entry_point_beside_the_data_folder_and_opens_the_window(self):
        self.assertTrue(self.go())
        (argv, env, log, cwd), = self.f.started
        self.assertEqual(argv[1:], ["-m", "clark.setup_mode", "--data", str(self.folder), "--port", "8800"])
        self.assertEqual((env["CLARK_LAUNCHED"], env["CLARK_PORT"], env["PYTHONPATH"], env["HOME"]), ("1", "8800", str(SRC), "/nowhere"))
        self.assertEqual(self.f.windows, [("http://127.0.0.1:8800/", "/stub/browser")])
        self.assertEqual(self.f.said, ["Opened clark in its own window."])

    def test_the_log_is_in_the_log_folder_and_the_data_folder_is_not_touched(self):
        self.go()
        (argv, env, log, cwd), = self.f.started
        self.assertEqual((log, cwd), (self.logs / "setup.log", str(SRC)))
        self.assertTrue(self.logs.is_dir())
        self.assertFalse(self.folder.exists())
        self.assertFalse(self.folder.parent.exists())

    def test_setup_is_only_started_for_a_reason_it_can_fix(self):
        for reason in ("update", "version", "anything else"):
            f = Fakes([launch.NOTHING])
            self.assertFalse(self.go(fakes=f, reason=reason), reason)
            self.assertEqual((f.started, f.windows, f.said), ([], [], []), reason)

    def test_it_waits_for_the_mark_of_the_data_folder(self):
        self.go()
        self.assertEqual({m for _, m in self.f.asked}, {appfiles.data_mark(self.folder)})

    def test_a_system_that_refuses_the_start_is_false_with_nothing_said_and_nothing_opened(self):
        f = Fakes([launch.NOTHING], fail_start="no")
        self.assertFalse(self.go(fakes=f))
        self.assertEqual((f.said, f.windows, f.browser), ([], [], []))

    def test_a_setup_that_never_answers_is_false_and_its_process_is_stopped(self):
        f = Fakes([launch.NOTHING])
        f.start = lambda argv, env, log, cwd=None: self.process
        self.assertFalse(self.go(fakes=f, start=f.start))
        self.assertTrue(self.process.terminated)
        self.assertEqual((f.windows, f.said), ([], []))

    def test_a_port_that_answers_as_not_ours_is_false_and_nothing_opens(self):
        for seen in (launch.OTHER_DATA, launch.NOT_CLARK):
            f = Fakes([launch.NOTHING, seen])
            self.assertFalse(self.go(fakes=f))
            self.assertEqual((f.windows, f.said), ([], []))

    def test_a_log_folder_that_cannot_be_found_is_false(self):
        def no_log():
            raise pl.NotBuiltYet("not here")
        self.assertFalse(self.go(log_dir=no_log))
        self.assertEqual(self.f.started, [])

    def test_the_launcher_names_the_setup_process_by_string(self):
        text = (SRC / "clark" / "launch.py").read_text(encoding="utf-8")
        self.assertIn('"clark.setup_mode"', text)
        self.assertNotIn("setup_mode.main", text)


if __name__ == "__main__":
    unittest.main()

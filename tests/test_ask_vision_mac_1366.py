"""#1366 follow-up: the Mac's picture reader (ask_vision_mac). NOT RUN ON A MAC: Vision is never started here. A stand-in takes the
place of the system's script runner and answers like osascript would; what it proves is the plumbing (argument list, temporary file,
limits, failures, the index), not that the Mac recognises text. dev/tools/check_picture_reader_mac.py is the check for a Mac.
Run: python3 dev/run_tests.py test_ask_vision_mac_1366"""
import os
import subprocess
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import Base, ix
from clark import ask_index, ask_picture, ask_vision_mac as vm, platform as pl


class Stub:
    """Stands in for subprocess.run: records the call, looks at the temporary file while it still exists, answers."""

    def __init__(self, out="hello\nworld\n", code=0, error=None):
        self.out, self.code, self.error, self.calls, self.seen = out, code, error, [], []

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        path = argv[-1]
        self.seen.append((path, os.path.exists(path), open(path, "rb").read(), oct(os.stat(path).st_mode & 0o777)))
        if self.error:
            raise self.error
        return subprocess.CompletedProcess(argv, self.code, self.out, "")


class Reader(unittest.TestCase):
    def on_mac(self):
        p = mock.patch.object(pl, "system", return_value=pl.MAC)
        p.start()
        self.addCleanup(p.stop)

    def test_it_runs_osascript_from_an_argument_list_with_the_path_as_the_last_argument(self):
        self.on_mac()
        s = Stub()
        self.assertEqual(vm.read(b"\x89PNG-bytes", run=s), "hello\nworld")
        argv, kw = s.calls[0]
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[:4], ["osascript", "-l", "JavaScript", "-e"])
        self.assertEqual(argv[4], vm.SCRIPT)
        self.assertEqual(len(argv), 6)
        self.assertNotIn(argv[5], vm.SCRIPT)                       # the path is an argument, never put into the script text
        self.assertFalse(kw.get("shell", False))
        self.assertEqual(kw["timeout"], vm.TIMEOUT)
        self.assertIs(kw["stdin"], subprocess.DEVNULL)               # the program never reads this process's input

    def test_the_script_asks_for_accurate_recognition_and_does_nothing_over_a_network(self):
        for word in ("VNRequestTextRecognitionLevelAccurate", "VNRecognizeTextRequest"):
            self.assertIn(word, vm.SCRIPT)
        for word in ("NSURL", "http", "curl", "NSURLSession", "doShellScript"):
            self.assertNotIn(word, vm.SCRIPT)

    def test_the_picture_goes_to_a_private_temporary_file_that_is_deleted_after(self):
        self.on_mac()
        s = Stub()
        vm.read(b"PICBYTES", run=s)
        path, existed, content, mode = s.seen[0]
        self.assertTrue(existed)
        self.assertEqual((content, mode), (b"PICBYTES", "0o600"))
        self.assertFalse(os.path.exists(path))

    def test_the_temporary_file_is_deleted_when_the_reader_fails_or_times_out(self):
        self.on_mac()
        for s in (Stub(code=1), Stub(error=subprocess.TimeoutExpired("osascript", 30)), Stub(error=OSError("no osascript"))):
            with self.assertRaises(ask_picture.PictureUnreadable):
                vm.read(b"PIC", run=s)
            self.assertFalse(os.path.exists(s.seen[0][0]))

    def test_nothing_recognised_is_unreadable(self):
        self.on_mac()
        for out in ("", "\n", "  \n \n"):
            with self.assertRaises(ask_picture.PictureUnreadable):
                vm.read(b"PIC", run=Stub(out=out))

    def test_garbage_bytes_are_unreadable_when_the_system_finds_nothing_or_fails(self):
        self.on_mac()
        for s in (Stub(out=""), Stub(code=1)):
            with self.assertRaises(ask_picture.PictureUnreadable):
                vm.read(os.urandom(300), run=s)

    def test_empty_and_non_bytes_input_never_start_the_program(self):
        self.on_mac()
        s = Stub()
        for bad in (b"", None, "text"):
            with self.assertRaises(ask_picture.PictureUnreadable):
                vm.read(bad, run=s)
        self.assertEqual(s.calls, [])

    def test_a_picture_of_21_mb_is_not_read_and_20_mb_is(self):
        self.on_mac()
        s = Stub()
        with self.assertRaises(ask_picture.PictureUnreadable):
            vm.read(b"\0" * (21 * 1024 * 1024), run=s)
        self.assertEqual(s.calls, [])
        self.assertEqual(vm.read(b"\0" * (20 * 1024 * 1024), run=s), "hello\nworld")

    def test_off_a_mac_nothing_is_started_and_the_reader_is_none(self):
        s = Stub()
        with mock.patch.object(pl, "system", return_value="linux"):
            with self.assertRaises(ask_picture.PictureUnreadable):
                vm.read(b"PIC", run=s)
            self.assertEqual(s.calls, [])
            with mock.patch.object(ask_picture, "_READER", None):
                vm.register()
                self.assertIsNone(ask_picture._READER)
                self.assertIsNone(ask_picture.reader())

    def test_on_a_mac_register_sets_this_reader(self):
        self.on_mac()
        with mock.patch.object(ask_picture, "_READER", None):
            vm.register()
            self.assertIs(ask_picture.reader(), vm.read)

    def test_the_reader_is_registered_when_ask_index_loads_on_a_mac_only(self):
        # ask_index calls register() once at import; here that is repeated for each system
        for system, expect in (("linux", None), ("win32", None), (pl.MAC, vm.read)):
            with mock.patch.object(ask_picture, "_READER", None), mock.patch.object(pl, "system", return_value=system):
                vm.register()
                self.assertIs(ask_picture._READER, expect)

    def test_ask_index_registers_the_reader_when_it_loads_on_a_mac_and_not_elsewhere(self):
        import importlib.util
        for system, expect in (("linux", None), ("win32", None), (pl.MAC, vm.read)):
            spec = importlib.util.spec_from_file_location("ask_index_fresh_1366", ask_index.__file__)
            fresh = importlib.util.module_from_spec(spec)
            with mock.patch.object(ask_picture, "_READER", None), mock.patch.object(pl, "system", return_value=system):
                spec.loader.exec_module(fresh)
                self.assertIs(ask_picture._READER, expect, system)

    def test_every_line_of_the_answer_is_trimmed_and_empty_lines_dropped(self):
        self.on_mac()
        self.assertEqual(vm.read(b"PIC", run=Stub(out="  a  \n b\n\n   \n")), "a\nb")

    def test_run_jxa_refuses_off_a_mac_before_starting_anything(self):
        s = Stub()
        with self.assertRaises(pl.NotBuiltYet):
            pl.run_jxa("x", ["a"], 5, run=s, on="linux")
        self.assertEqual(s.calls, [])


    def test_run_jxa_captures_the_output_with_text_mode_the_given_timeout_and_returns_it(self):
        seen = []

        def fake(argv, **kw):
            seen.append((argv, kw))
            return subprocess.CompletedProcess(argv, 0, "printed\n", "")

        self.assertEqual(pl.run_jxa("x", ["a", 7], 5, run=fake, on="darwin"), "printed\n")
        argv, kw = seen[0]
        self.assertIs(kw["capture_output"], True)               # without it osascript's answer is never read and every picture reads as no text
        self.assertIs(kw["text"], True)
        self.assertIs(kw["check"], False)
        self.assertEqual(kw["timeout"], 5)
        self.assertEqual(argv[-2:], ["a", "7"])

    def test_run_jxa_turns_a_timeout_a_failure_and_a_missing_program_into_a_platform_error(self):
        def late(argv, **kw):
            raise subprocess.TimeoutExpired("osascript", 5)

        def gone(argv, **kw):
            raise OSError("no osascript")

        def failed(argv, **kw):
            return subprocess.CompletedProcess(argv, 1, "", "boom")

        for fake, words in ((late, "did not finish in time"), (gone, "could not be started"), (failed, "failed")):
            with self.subTest(words=words), self.assertRaises(pl.PlatformError) as caught:
                pl.run_jxa("x", [], 5, run=fake, on="darwin")
            self.assertIn(words, str(caught.exception))

    def test_run_jxa_fails_for_a_process_stopped_by_a_signal_whose_return_code_is_negative(self):
        for code in (-9, -15, 2):
            def killed(argv, code=code, **kw):
                return subprocess.CompletedProcess(argv, code, "partial", "")

            with self.subTest(code=code), self.assertRaises(pl.PlatformError) as caught:
                pl.run_jxa("x", [], 5, run=killed, on="darwin")
            self.assertIn("failed", str(caught.exception))


class SweepKillers(unittest.TestCase):
    """Pins found by a mutation sweep of ask_vision_mac and run_jxa: limits, reasons, text decoding and the off-Mac words."""

    def on_mac(self):
        p = mock.patch.object(pl, "system", return_value=pl.MAC)
        p.start()
        self.addCleanup(p.stop)

    def reason(self, raw, stub):
        with self.assertRaises(ask_picture.PictureUnreadable) as caught:
            vm.read(raw, run=stub)
        return str(caught.exception)

    def test_the_time_limit_is_30_seconds_for_the_reader_and_the_default_of_run_jxa(self):
        self.assertEqual(vm.TIMEOUT, 30)
        seen = []

        def fake(argv, **kw):
            seen.append(kw)
            return subprocess.CompletedProcess(argv, 0, "x", "")

        pl.run_jxa("x", [], run=fake, on="darwin")
        self.assertEqual(seen[0]["timeout"], 30)

    def test_run_jxa_decodes_utf8_replacing_bad_bytes_and_a_missing_answer_is_empty(self):
        seen = []

        def fake(argv, **kw):
            seen.append(kw)
            return subprocess.CompletedProcess(argv, 0, None, "")

        self.assertEqual(pl.run_jxa("x", [], 5, run=fake, on="darwin"), "")
        self.assertEqual(seen[0]["encoding"], "utf-8")
        self.assertEqual(seen[0]["errors"], "replace")

    def test_run_jxa_off_a_mac_says_the_system_and_that_it_is_not_built_yet(self):
        with mock.patch.dict(os.environ, {"CLARK_CONTAINER": ""}):
            for on, name in (("win32", "Windows"), ("freebsd", "freebsd"), ("linux", "linux")):
                with self.assertRaises(pl.NotBuiltYet) as caught:
                    pl.run_jxa("x", [], 5, run=Stub(), on=on)
                self.assertEqual(str(caught.exception), f"Reading a picture on {name} is not built yet: clark runs on macOS for now")

    def test_in_a_container_linux_says_the_terminal_words_and_windows_does_not(self):
        with mock.patch.object(pl, "container_mode", return_value=True):
            with self.assertRaises(pl.NotBuiltYet) as linux:
                pl.run_jxa("x", [], 5, run=Stub(), on="linux")
            with self.assertRaises(pl.NotBuiltYet) as windows:
                pl.run_jxa("x", [], 5, run=Stub(), on="win32")
        self.assertEqual(str(linux.exception), pl.needs_mac_words())
        self.assertEqual(str(windows.exception), "Reading a picture on Windows is not built yet: clark runs on macOS for now")
        with mock.patch.object(pl, "container_mode", return_value=False):
            with self.assertRaises(pl.NotBuiltYet) as plain:
                pl.run_jxa("x", [], 5, run=Stub(), on="linux")
        self.assertNotEqual(str(plain.exception), pl.needs_mac_words())

    def test_the_reasons_for_an_unreadable_picture_are_told_apart(self):
        self.on_mac()
        self.assertEqual(self.reason(b"", Stub()), "size")
        self.assertEqual(self.reason(b"\0" * (vm.MAX_BYTES + 1), Stub()), "size")
        self.assertEqual(self.reason(b"PIC", Stub(out="  \n")), "no text")
        self.assertEqual(self.reason(b"PIC", Stub(code=1)), "the reader failed")
        self.assertEqual(self.reason(b"PIC", Stub(error=OSError("none"))), "the reader failed")

    def test_a_program_that_is_not_built_for_this_system_reads_as_the_reader_failed(self):
        self.on_mac()
        with mock.patch.object(pl, "run_jxa", side_effect=pl.NotBuiltYet("not here")):
            self.assertEqual(self.reason(b"PIC", Stub()), "the reader failed")

    def test_a_bytearray_picture_is_read(self):
        self.on_mac()
        self.assertEqual(vm.read(bytearray(b"PICBYTES"), run=Stub()), "hello\nworld")

    def test_the_temporary_file_is_named_clark_picture(self):
        self.on_mac()
        s = Stub()
        vm.read(b"PIC", run=s)
        self.assertTrue(os.path.basename(s.seen[0][0]).startswith("clark-picture-"))


class InTheIndex(Base):
    def reader(self, stub):
        for p in (mock.patch.object(pl, "system", return_value=pl.MAC), mock.patch.object(ask_picture, "_READER", lambda raw: vm.read(raw, run=stub))):
            p.start()
            self.addCleanup(p.stop)

    def counts(self):
        return ix.status(self.data, "P1", [self.box])

    def test_a_picture_read_is_indexed_and_counted(self):
        self.reader(Stub(out="zqvisionword here\nsecond line\n"))
        self.put("a.png", b"\x89PNG....", binary=True)
        self.build()
        self.assertEqual(len(self.found("zqvisionword")), 1)
        c = self.counts()
        self.assertEqual((c["indexed"], c["picture"], c["pictures_read"]), (1, 0, 1))
        self.assertEqual(ask_index.line_for(c), "Indexed 1 of 1 file. 1 picture read on this Mac.")

    def test_a_picture_the_reader_fails_on_is_left_out(self):
        for stub in (Stub(code=1), Stub(out=""), Stub(error=subprocess.TimeoutExpired("osascript", 30))):
            self.reader(stub)
            self.put("a.png", b"\x89PNG....", binary=True)
            self.build()
            c = self.counts()
            self.assertEqual((c["indexed"], c["type"], c["pictures_read"]), (0, 1, 0))


if __name__ == "__main__":
    unittest.main()

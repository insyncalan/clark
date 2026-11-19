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

    def test_run_jxa_refuses_off_a_mac_before_starting_anything(self):
        s = Stub()
        with self.assertRaises(pl.NotBuiltYet):
            pl.run_jxa("x", ["a"], 5, run=s, on="linux")
        self.assertEqual(s.calls, [])


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

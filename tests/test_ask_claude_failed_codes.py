"""The short failure codes of the Claude command checks, with real files in a temp folder: native_reason, find_checked and
ClaudeCommand.command (its failed code, including not_mac_os on a computer that is not a Mac and container in Docker).

Run: python3 dev/run_tests.py test_ask_claude_failed_codes
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ask_claude as ac, platform

MACHO = b"\xcf\xfa\xed\xfe" + b"\0" * 12


class Codes(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="clark-codes-")).resolve()
        self.addCleanup(shutil.rmtree, self.d, True)
        self.d.chmod(0o755)
        self.cmd = self.d / "claude"
        self.roots = (str(self.d),)

    def write(self, data=MACHO, mode=0o755):
        self.cmd.write_bytes(data)
        self.cmd.chmod(mode)

    def test_native_reason_none_for_a_mac_program_we_own(self):
        self.write()
        self.assertIsNone(ac.native_reason(self.cmd, self.roots))

    def test_native_reason_unreadable_when_missing(self):
        self.assertEqual(ac.native_reason(self.cmd, self.roots), "unreadable")

    def test_native_reason_owner_when_writable_by_others(self):
        self.write(mode=0o777)
        self.assertEqual(ac.native_reason(self.cmd, self.roots), "owner")

    def test_native_reason_owner_when_not_runnable(self):
        self.write(mode=0o644)
        self.assertEqual(ac.native_reason(self.cmd, self.roots), "owner")

    def test_native_reason_owner_when_outside_the_roots(self):
        self.write()
        self.assertEqual(ac.native_reason(self.cmd, ("/nowhere/else",)), "owner")

    def test_native_reason_not_mac_for_a_script(self):
        self.write(b"#!/bin/sh\necho hi\n")
        self.assertEqual(ac.native_reason(self.cmd, self.roots), "not_mac")

    def test_find_checked_found_has_no_code(self):
        self.write()
        path, why, code = ac.find_checked((str(self.cmd),), self.roots)
        self.assertEqual((path, why, code), (self.cmd, None, None))

    def test_find_checked_not_found(self):
        path, why, code = ac.find_checked((str(self.d / "none"),), self.roots)
        self.assertEqual((path, why, code), (None, ac.NOT_INSTALLED, "not_found"))

    def test_find_checked_carries_the_native_code(self):
        for data, mode, want in ((b"#!/bin/sh\n", 0o755, "not_mac"), (MACHO, 0o777, "owner")):
            with self.subTest(want=want):
                self.write(data, mode)
                path, why, code = ac.find_checked((str(self.cmd),), self.roots)
                self.assertEqual((path, why, code), (None, ac.NOT_NATIVE, want))

    def test_find_checked_unreadable_for_a_loop_link(self):
        link = self.d / "loop"
        os.symlink(str(link), str(link))
        path, why, code = ac.find_checked((str(link),), self.roots)
        self.assertEqual((path, why, code), (None, ac.NOT_NATIVE, "unreadable"))

    def test_command_failed_codes(self):
        c = ac.ClaudeCommand(places=(str(self.cmd),), roots=self.roots)
        with mock.patch.object(platform, "container_mode", return_value=True):
            self.assertEqual(c.command(), (None, platform.needs_mac_words()))
            self.assertEqual(c.failed, "container")
        with mock.patch.object(platform, "container_mode", return_value=False), mock.patch.object(platform, "system", return_value="linux"):
            self.assertEqual(c.command(), (None, ac.MAC_ONLY))
            self.assertEqual(c.failed, "not_mac_os")
        with mock.patch.object(platform, "container_mode", return_value=False), mock.patch.object(platform, "system", return_value=platform.MAC):
            self.assertEqual(c.command()[0], None)
            self.assertEqual(c.failed, "not_found")
            self.write(b"#!/bin/sh\n")
            c.command()
            self.assertEqual(c.failed, "not_mac")


if __name__ == "__main__":
    unittest.main()

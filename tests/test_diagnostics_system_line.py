"""Row 1298: the System line of the diagnostics report names the macOS version (what the feedback mail now carries), not the Darwin kernel's."""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import diagnostics


def line(system, mac_ver, kernel="23.5.0", **kw):
    with mock.patch.object(diagnostics.stdlib_platform, "mac_ver", return_value=(mac_ver, ("", "", ""), "")), \
            mock.patch.object(diagnostics.stdlib_platform, "release", return_value=kernel):
        return diagnostics.system_line(system, **kw)


class SystemLine(unittest.TestCase):
    def test_darwin_uses_the_macos_version(self):
        self.assertEqual(line("darwin", "14.5"), "macOS 14.5")

    def test_darwin_with_no_macos_version_keeps_the_release_text(self):
        self.assertEqual(line("darwin", ""), "macOS 23.5.0")

    def test_other_systems_are_unchanged(self):
        self.assertEqual(line("linux", "14.5", "6.1.0"), "Linux 6.1.0")
        self.assertEqual(line("win32", "14.5", "10"), "Windows 10")
        self.assertEqual(line("plan9", "14.5", "1"), "Other system 1")

    def test_a_given_release_is_used_as_given(self):
        self.assertEqual(line("darwin", "14.5", release="24.0.0"), "macOS 24.0.0")

    def test_the_report_carries_it(self):
        class L:
            level = staticmethod(lambda: "normal")
            debug_notice = staticmethod(lambda: "")
            errors = staticmethod(lambda: [])
            tail = staticmethod(lambda n: [])
            home = "/h"
            clock = staticmethod(lambda: __import__("datetime").datetime(2026, 1, 1))
        with mock.patch.object(diagnostics.stdlib_platform, "mac_ver", return_value=("14.5", ("", "", ""), "")):
            self.assertIn("System: macOS 14.5\n", diagnostics.build(L(), "1", system="darwin"))


if __name__ == "__main__":
    unittest.main()

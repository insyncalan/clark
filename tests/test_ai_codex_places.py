"""The Codex command's places by machine: Apple silicon and Intel builds, and the other install places (Homebrew, npm global, nvm).
Nothing real is installed: the machine and the files are faked, so this runs on any system.

Run: python3 dev/run_tests.py test_ai_codex_places
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from clark import ai_codex as c, ask_claude, platform


class PlacesByMachine(unittest.TestCase):
    def test_apple_silicon_has_the_arm_build_and_no_intel_one(self):
        places = c.places_for("arm64")
        self.assertTrue(any("codex-darwin-arm64/vendor/aarch64-apple-darwin" in p for p in places))
        self.assertFalse(any("x86_64" in p for p in places))

    def test_an_intel_mac_has_the_x86_64_build_and_no_arm_one(self):
        places = c.places_for("x86_64")
        self.assertTrue(any("codex-darwin-x64/vendor/x86_64-apple-darwin" in p for p in places))
        self.assertFalse(any("aarch64" in p for p in places))

    def test_the_other_install_places_are_covered(self):
        places = c.places_for("x86_64")
        for want in ("/usr/local/lib/", "~/.npm-global/lib/", "~/.nvm/versions/node/*/lib/", "/usr/local/bin/codex"):
            self.assertTrue(any(want in p for p in places), want)

    def test_another_machine_has_only_the_links(self):
        self.assertEqual(c.places_for("riscv"), c.BINS)

    def test_the_command_takes_its_places_from_the_machine(self):
        with mock.patch.object(platform, "machine", return_value="x86_64"):
            self.assertEqual(c.CodexCommand(env={}).places, c.places_for("x86_64"))
        with mock.patch.object(platform, "machine", return_value="arm64"):
            self.assertEqual(c.CodexCommand(env={}).places, c.places_for("arm64"))

    def test_places_are_absolute_once_the_home_is_expanded(self):
        for machine in ("arm64", "x86_64"):
            self.assertTrue(all(os.path.isabs(os.path.expanduser(p)) for p in c.places_for(machine)))


class NotFound(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-codex-places-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        patch = mock.patch.object(platform, "system", return_value=platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)

    def test_the_codex_words_are_used_for_each_case(self):
        provider = c.CodexCommand(places=(str(self.d / "none"),), env={}, walled=False)
        provider.not_found_words = {"missing": "W-MISSING", "elsewhere": "W-ELSEWHERE"}
        with mock.patch.object(ask_claude.shutil, "which", return_value="/x/codex"):
            self.assertEqual(provider.command(), (None, "W-ELSEWHERE"))
        with mock.patch.object(ask_claude.shutil, "which", return_value=None):
            self.assertEqual(provider.command(), (None, "W-MISSING"))

    def test_it_looks_for_codex_not_claude(self):
        seen = []
        with mock.patch.object(ask_claude.shutil, "which", side_effect=lambda n: seen.append(n)):
            c.CodexCommand(places=(str(self.d / "none"),), env={}, walled=False).command()
        self.assertEqual(seen, ["codex"])

    def test_the_codex_command_uses_the_codex_table_not_the_claude_one(self):
        self.assertIs(c.CodexCommand.not_found_words, c.NOT_FOUND_WORDS)
        self.assertIsNot(c.NOT_FOUND_WORDS, ask_claude.NOT_FOUND_WORDS)

    def test_missing_says_the_old_sentence_and_elsewhere_the_new_one(self):
        self.assertEqual(c.NOT_FOUND_WORDS, {"missing": c.NOT_INSTALLED, "elsewhere": c.NOT_ELSEWHERE})
        self.assertEqual(c.NOT_ELSEWHERE, "Codex works in Terminal, but clark can't use it from where it is installed. "
                         "Install it again with ChatGPT's own installer, then ask again.")
        provider = c.CodexCommand(places=(str(self.d / "none"),), env={}, walled=False)
        with mock.patch.object(ask_claude.shutil, "which", return_value="/x/codex"):
            self.assertEqual(provider.command(), (None, c.NOT_ELSEWHERE))
            self.assertEqual(provider.status(), {"connected": False, "why": c.NOT_ELSEWHERE})
        with mock.patch.object(ask_claude.shutil, "which", return_value=None):
            self.assertEqual(provider.command(), (None, c.NOT_INSTALLED))
            self.assertEqual(provider.status(), {"connected": False, "why": c.NOT_INSTALLED})


if __name__ == "__main__":
    unittest.main()

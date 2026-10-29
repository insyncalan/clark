"""#29: a real client brand stays on this laptop (RULES.md; BRD FR-110 and NFR-1).

Run: python3 dev/run_tests.py test_brand

Test A: git tracks nothing under system/branding/, and .gitignore keeps system/branding/ and comms/ out. (Names are
guarded by tests/test_no_real_names.py, creaite's rule, which needs no local file and never skips.)
"""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

BRANDING = "system/branding"
GIT = shutil.which("git")


def git(repo, *args):
    """The output of a git command in `repo` (raises if git fails)."""
    return subprocess.run([GIT, "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def tracked_branding(repo):
    """Every path git tracks (or has staged) under system/branding/ in `repo`."""
    return git(repo, "ls-files", "--", BRANDING).split()


class NothingTrackedUnderBranding(unittest.TestCase):
    """Test A."""

    def test_git_tracks_nothing_under_system_branding(self):
        self.assertEqual(tracked_branding(ROOT), [], "remove these from git (git rm --cached); they stay on the laptop")

    def test_gitignore_keeps_branding_and_comms_out(self):
        for path in ("system/branding/logo.png", "system/branding/brand.css", "comms/notes.md"):
            done = subprocess.run([GIT, "-C", str(ROOT), "check-ignore", "-q", "--no-index", path])
            self.assertEqual(done.returncode, 0, f"{path} is not ignored")

    def test_a_staged_file_is_caught(self):
        """Proved in a temporary copy: a file forced past .gitignore into system/branding/ is found."""
        with tempfile.TemporaryDirectory() as tmp:
            git(tmp, "init", "-q")
            shutil.copy(ROOT / ".gitignore", Path(tmp) / ".gitignore")
            (Path(tmp) / BRANDING).mkdir(parents=True)
            (Path(tmp) / BRANDING / "logo.svg").write_text("<svg/>", encoding="utf-8")
            git(tmp, "add", ".")
            self.assertEqual(tracked_branding(tmp), [], ".gitignore stops a plain add")
            git(tmp, "add", "-f", f"{BRANDING}/logo.svg")
            self.assertEqual(tracked_branding(tmp), [f"{BRANDING}/logo.svg"])


if __name__ == "__main__":
    unittest.main()

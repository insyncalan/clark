"""The repository holds no merge-conflict markers and no stray backup files (a sed -i without a suffix argument leaves a
file ending in -E; a failed patch leaves .orig or .rej). #36's review found both; the row-counting tests missed them.

Run: python3 dev/run_tests.py test_repo_hygiene
"""
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

STRAY = re.compile(r"(\.(orig|rej|bak|swp|tmp)|~|-E)$")
# git writes both the opening and the closing marker, so those two are enough; a bare ======= line is a Markdown heading rule
MARKER = re.compile(r"^(<<<<<<< |>>>>>>> )", re.M)
SKIP = re.compile(r"(^|/)(vendor|node_modules)/|\.(png|jpe?g|gif|ico|icns|pdf|xlsx|docx|pptx|zip|gz|woff2?|ttf|otf|db|sqlite)$", re.I)


def tracked(repo):
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def problems(repo):
    """Places a stray file or a conflict marker is found, by place in git ls-files (never the path)."""
    found = []
    for i, path in enumerate(tracked(repo), 1):
        if STRAY.search(path):
            found.append(f"tracked file #{i} is a stray backup or patch file")
        if SKIP.search(path):
            continue
        try:
            data = (Path(repo) / path).read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            continue
        if b"\0" in data:
            continue
        text = data.decode("utf-8", "ignore")
        for m in MARKER.finditer(text):
            found.append(f"tracked file #{i} line {text.count(chr(10), 0, m.start()) + 1}: a conflict marker")
    return found


class RepoHygiene(unittest.TestCase):
    def test_no_conflict_markers_or_stray_files_are_tracked(self):
        self.assertEqual(problems(ROOT), [], "find a file with: git ls-files | sed -n '<n>p'")

    def test_the_check_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "-C", tmp, "init", "-q"], check=True)
            (root / "ok.md").write_text("A heading\n=========\nfine\n", encoding="utf-8")
            (root / "bad.md").write_text("a\n<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> branch\n", encoding="utf-8")
            (root / "notes.md-E").write_text("x", encoding="utf-8")
            (root / "x.py.orig").write_text("x", encoding="utf-8")
            (root / "vendor").mkdir()
            (root / "vendor" / "lib.txt").write_text("<<<<<<< vendored\n", encoding="utf-8")
            subprocess.run(["git", "-C", tmp, "add", "-f", "."], check=True)
            got = problems(root)
        text = " ".join(got)
        self.assertEqual(text.count("conflict marker"), 2, got)       # bad.md's opening and closing markers, nothing else
        self.assertEqual(text.count("stray backup"), 2, got)         # the -E and .orig files
        self.assertNotIn("tracked file #3", text.replace("tracked file #3 is", ""), "vendor/ and the heading are not flagged")


if __name__ == "__main__":
    unittest.main()

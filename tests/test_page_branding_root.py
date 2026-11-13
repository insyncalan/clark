"""Where the person's branding folder is, in a source checkout and in a download (issue 694).

A download keeps its program files in the hidden .app folder; branding stays beside it, at the top of the clark folder.
Run: python3 dev/run_tests.py test_page_branding_root
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT
from clark import page


class BrandingFolder(unittest.TestCase):
    def test_a_download_looks_beside_the_hidden_folder(self):
        self.assertEqual(Path("/x/clark/branding"), page.branding_folder(Path("/x/clark/.app")))

    def test_a_source_checkout_looks_in_its_own_folder(self):
        self.assertEqual(Path("/x/clark-repo/branding"), page.branding_folder(Path("/x/clark-repo")))

    def test_only_a_folder_named_exactly_app_with_a_dot_counts(self):
        for name in ("app", ".App", ".app2", "x.app"):
            self.assertEqual(Path("/x") / name / "branding", page.branding_folder(Path("/x") / name), name)

    def test_a_folder_named_app_lower_down_is_not_the_root(self):
        self.assertEqual(Path("/x/.app/y/branding"), page.branding_folder(Path("/x/.app/y")))

    def test_this_checkout_is_unchanged(self):
        self.assertEqual(page.ROOT / "branding", page.BRANDING)
        self.assertNotEqual(".app", page.ROOT.name)

    def test_the_module_run_from_a_hidden_folder_finds_the_clark_folders_branding(self):
        """The real module file, copied to <clark>/.app/src/clark/page/, reads <clark>/branding."""
        with tempfile.TemporaryDirectory(prefix="clark download ") as t:
            top = Path(t) / "clark"
            target = top / ".app" / "src" / "clark" / "page"
            target.parent.mkdir(parents=True)
            shutil.copytree(ROOT / "src" / "clark", target.parent, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "page.html", "page-view.html", "src"))
            shutil.copytree(ROOT / "vendor", top / ".app" / "vendor", ignore=shutil.ignore_patterns("__pycache__"))
            code = "import clark.page as p; print(p.BRANDING)"
            env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(top / ".app" / "src"), str(top / ".app" / "vendor")]),
                   "PYTHONDONTWRITEBYTECODE": "1"}
            out = subprocess.run([sys.executable, "-B", "-c", code], env=env, cwd=t, capture_output=True, text=True)
            self.assertEqual(0, out.returncode, out.stderr[-400:])
            self.assertEqual(str((top / "branding").resolve()), str(Path(out.stdout.strip()).resolve()))


if __name__ == "__main__":
    unittest.main()

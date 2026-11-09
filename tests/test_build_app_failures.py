"""Row 836 v5: pin what build_app.sh's failure paths DO (exit code, nothing half-built left behind, scratch source removed).
Same fakes as test_build_app: no real osacompile, nothing compiled, no dialog."""
import unittest

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from test_build_app import SCRIPT, fake


class BuildAppFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.out = self.tmp / "out"
        fake(self.bin, "osacompile", 'mkdir -p "$2" && cp "$3" "$2/source.applescript"')
        fake(self.bin, "uname", "echo Darwin")

    def run_script(self, *args):
        env = dict(os.environ, PATH=f"{self.bin}:/usr/bin:/bin", TMPDIR=str(self.tmp))
        return subprocess.run(["/bin/bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def leftovers(self):
        return sorted(p.name for p in self.tmp.iterdir() if p.name.startswith("clark-applet."))

    def test_a_refusal_leaves_no_folder_and_no_scratch_source(self):
        for args in (["--nope"], ["--test-port", "1;2", "--test-data", "/x"], ["--test-data", '/a"b']):
            with self.subTest(args=args):
                r = self.run_script(*args, str(self.out))
                self.assertEqual(r.returncode, 1)
                self.assertFalse(self.out.exists())
                self.assertEqual(self.leftovers(), [])

    # KNOWN GAP (row 836 v5): build_app.sh does not remove a partial clark.app when osacompile fails. Fix the script, then drop this mark.
    @unittest.expectedFailure
    def test_a_failing_osacompile_leaves_no_half_built_app(self):
        # osacompile that dies after starting to write the app
        fake(self.bin, "osacompile", 'mkdir -p "$2" && echo half > "$2/partial" && exit 3')
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Built", r.stdout)
        self.assertFalse((self.out / "clark.app").exists(), "a half-built clark.app was left behind")

    def test_a_failing_osacompile_removes_the_scratch_source(self):
        fake(self.bin, "osacompile", "exit 3")
        self.run_script(str(self.out))
        self.assertEqual(self.leftovers(), [])

    def test_an_existing_app_is_untouched_and_scratch_is_not_made(self):
        (self.out / "clark.app").mkdir(parents=True)
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(list((self.out / "clark.app").iterdir()), [])


if __name__ == "__main__":
    unittest.main()

"""Row 836 v6: pin what build_app.sh's failure paths DO (exit code, nothing half-built left behind, scratch source removed).
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
        # fake mktemp: logs every call, then runs the real one, so a test can tell whether the script ever asked for scratch space
        self.mklog = self.tmp / "mktemp.log"
        fake(self.bin, "mktemp", f'echo "$@" >> "{self.mklog}"; exec /usr/bin/mktemp "$@"')

    def run_script(self, *args, extra_path=""):
        path = f"{self.bin}:{extra_path}/usr/bin:/bin"
        if not (self.bin / "osacompile").exists():
            # a real /usr/bin/osacompile may exist (a Mac): hide it behind a tools dir holding only what the script needs
            tools = self.tmp / "tools"
            tools.mkdir(exist_ok=True)
            for name in ("mkdir", "rm", "cat", "dirname"):
                found = shutil.which(name, path="/usr/bin:/bin")
                if found and not (tools / name).exists():
                    (tools / name).symlink_to(found)
            path = f"{self.bin}:{tools}"
        env = dict(os.environ, PATH=path, TMPDIR=str(self.tmp))
        return subprocess.run(["/bin/bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def leftovers(self):
        # clark-applet. is the scratch source; clark-app. is the default output folder made when no folder is named
        return sorted(p.name for p in self.tmp.iterdir() if p.name.startswith(("clark-applet.", "clark-app.")))

    def scratch_requests(self):
        text = self.mklog.read_text(encoding="utf-8") if self.mklog.exists() else ""
        return [l for l in text.splitlines() if "clark-applet." in l]

    def test_a_refusal_leaves_no_folder_and_no_scratch_source(self):
        # leftovers() alone cannot fail here (the script makes the scratch source after every refusal and removes it on exit),
        # so the fake mktemp log is what shows the scratch source was never even asked for.
        for args in (["--nope"], ["--test-port", "1;2", "--test-data", "/x"], ["--test-data", '/a"b']):
            with self.subTest(args=args):
                r = self.run_script(*args, str(self.out))
                self.assertEqual(r.returncode, 1)
                self.assertFalse(self.out.exists())
                self.assertEqual(self.leftovers(), [])
                self.assertEqual(self.scratch_requests(), [])

    def test_a_refusal_with_no_folder_named_makes_no_default_folder(self):
        for args in (["--nope"], ["--test-port", "1;2"], ["--test-data", '/a"b']):
            with self.subTest(args=args):
                r = self.run_script(*args)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(self.leftovers(), [])
                self.assertEqual(self.scratch_requests(), [])

    def test_off_a_mac_or_without_osacompile_makes_nothing(self):
        # build_app.sh's check for a Mac and osacompile (test_build_app asserts the message; here: no folder, no scratch source)
        fake(self.bin, "uname", "echo Linux")
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertIn("osacompile (macOS) is needed", r.stderr)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(self.scratch_requests(), [])
        fake(self.bin, "uname", "echo Darwin")
        (self.bin / "osacompile").unlink()
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(self.scratch_requests(), [])

    def test_a_failing_osacompile_leaves_no_half_built_app(self):
        # osacompile that dies after starting to write the app
        fake(self.bin, "osacompile", 'mkdir -p "$2" && echo half > "$2/partial" && exit 3')
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertFalse((self.out / "clark.app").exists(), "a half-built clark.app was left behind")

    def test_a_failing_osacompile_is_reported_and_exits_1(self):
        # not under the expected failure above, so the exit code and the missing "Built" line are checked for real
        fake(self.bin, "osacompile", 'mkdir -p "$2" && echo half > "$2/partial" && exit 3')
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Built", r.stdout)
        self.assertNotIn("Built", r.stderr)
        self.assertIn("osacompile stopped", r.stderr)

    def test_a_failing_osacompile_removes_the_scratch_source(self):
        fake(self.bin, "osacompile", "exit 3")
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertNotIn("Built", r.stdout)
        # positive control: the scratch source WAS made, so the empty leftovers() below means it was removed
        self.assertEqual(len(self.scratch_requests()), 1)
        self.assertEqual(self.leftovers(), [])

    def test_an_existing_app_is_untouched_and_scratch_is_not_made(self):
        (self.out / "clark.app").mkdir(parents=True)
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(self.scratch_requests(), [])
        self.assertEqual(list((self.out / "clark.app").iterdir()), [])


if __name__ == "__main__":
    unittest.main()

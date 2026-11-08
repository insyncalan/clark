"""Row 836 mutation proof: tests that pin build_app.sh lines the first test file leaves loose (digit 9, carriage return, env of the
applet command, quoting, test-switch pairing, python 3.9 check, osacompile failure, default folder). Same fakes as test_build_app."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_build_app import SCRIPT, fake


class BuildAppMutProof(unittest.TestCase):
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

    def source(self):
        return (self.out / "clark.app" / "source.applescript").read_text()

    def test_a_port_with_every_digit_is_accepted(self):
        r = self.run_script("--test-data", str(self.tmp / "d"), "--test-port", "0123456789", str(self.out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--port 0123456789", self.source())

    def test_a_test_data_folder_with_a_carriage_return_is_refused(self):
        r = self.run_script("--test-data", "/tmp/a\rb", "--test-port", "8765", str(self.out))
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("--test-data", r.stderr)
        self.assertFalse((self.out / "clark.app").exists())

    def test_the_applet_command_sets_its_environment_and_quotes_the_folder(self):
        self.run_script(str(self.out))
        s = self.source()
        self.assertIn("export PYTHONDONTWRITEBYTECODE=1", s)
        self.assertIn("CLARK_TYPED='bash clark.command'", s)
        self.assertIn('if [ -d .app ]; then export PYTHONPATH=\\"$PWD/.app\\"; fi', s)
        self.assertIn("quoted form of clarkFolder", s)

    def test_the_python_check_wants_3_9(self):
        self.run_script(str(self.out))
        self.assertIn("sys.version_info < (3, 9)", self.source())

    def test_test_data_alone_still_makes_a_test_build(self):
        r = self.run_script("--test-data", str(self.tmp / "d"), str(self.out))
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.source()
        self.assertIn("--data", s)
        self.assertIn("CLARK_BROWSER=/usr/bin/true", s)

    def test_a_test_build_quotes_the_data_folder_and_the_report_path(self):
        self.run_script("--test-data", str(self.tmp / "my data"), "--test-port", "8765", str(self.out))
        s = self.source()
        self.assertIn('--data " & quoted form of "', s)
        self.assertIn('quoted form of "' + str(self.tmp / "my data") + '.applet-out.txt"', s)

    def test_a_failing_osacompile_stops_the_script(self):
        fake(self.bin, "osacompile", "exit 3")
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertIn("osacompile stopped", r.stderr)
        self.assertNotIn("Built", r.stdout)

    def test_the_output_folder_is_made_by_the_script_not_by_osacompile(self):
        fake(self.bin, "osacompile", 'mkdir "$2" && cp "$3" "$2/source.applescript"')  # no -p: the parent must already exist
        r = self.run_script(str(self.out / "deeper" / "still"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.out / "deeper" / "still" / "clark.app").is_dir())

    def test_with_no_folder_named_it_builds_into_a_new_scratch_folder(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        made = [p for p in self.tmp.iterdir() if p.name.startswith("clark-app.")]
        self.assertEqual(len(made), 1)
        self.assertTrue((made[0] / "clark.app").is_dir())
        self.assertIn(f"Built {made[0]}/clark.app", r.stdout)

    def test_header_comment_names_the_real_dialog_text_path(self):
        head = "".join(SCRIPT.read_text().splitlines(True)[:20])
        self.assertIn("FOLDER.applet-out.txt", head)
        self.assertNotIn("FOLDER/../applet-out.txt", head)


if __name__ == "__main__":
    unittest.main()

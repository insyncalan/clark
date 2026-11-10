"""Row 836 phase 1: dev/tools/build_app.sh builds clark.app (an osacompile applet). It only runs on a Mac, so these tests put a fake
uname and a fake osacompile first on PATH: nothing is compiled, no app is made, no dialog can open, nothing is started."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "dev" / "tools" / "build_app.sh"


def fake(bindir, name, body):
    p = Path(bindir) / name
    p.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


class BuildApp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.out = self.tmp / "out"
        # fake osacompile -o DEST SRC : copies the AppleScript source to DEST/source.applescript
        fake(self.bin, "osacompile", 'mkdir -p "$2" && cp "$3" "$2/source.applescript"')

    def run_script(self, *args, system="Darwin", with_osa=True):
        fake(self.bin, "uname", f"echo {system}")
        if not with_osa:
            (self.bin / "osacompile").unlink()
        path = f"{self.bin}:/usr/bin:/bin"
        if not with_osa:
            # a real /usr/bin/osacompile may exist (a Mac): hide it behind a tools dir holding only what the script needs
            tools = self.tmp / "tools"
            tools.mkdir(exist_ok=True)
            for name in ("mktemp", "mkdir", "rm", "cat", "dirname"):
                found = shutil.which(name, path="/usr/bin:/bin")
                if found and not (tools / name).exists():
                    (tools / name).symlink_to(found)
            path = f"{self.bin}:{tools}"
        env = dict(os.environ, PATH=path, TMPDIR=str(self.tmp))
        return subprocess.run(["/bin/bash", str(SCRIPT), *args], capture_output=True, text=True, env=env)

    def source(self):
        return (self.out / "clark.app" / "source.applescript").read_text(encoding="utf-8")

    def test_the_script_is_valid_shell(self):
        self.assertEqual(subprocess.run(["/bin/bash", "-n", str(SCRIPT)]).returncode, 0)

    def test_it_stops_off_a_mac(self):
        r = self.run_script(str(self.out), system="Linux")
        self.assertEqual(r.returncode, 1)
        self.assertIn("osacompile (macOS) is needed", r.stderr)
        self.assertFalse(self.out.exists())

    def test_it_stops_without_osacompile(self):
        r = self.run_script(str(self.out), with_osa=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("osacompile (macOS) is needed", r.stderr)
        self.assertFalse((self.out / "clark.app").exists())

    def test_it_builds_into_the_folder_named(self):
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"Built {self.out}/clark.app", r.stdout)
        self.assertTrue((self.out / "clark.app").is_dir())

    def test_it_will_not_overwrite_an_app(self):
        (self.out / "clark.app").mkdir(parents=True)
        (self.out / "clark.app" / "keep").write_text("mine", encoding="utf-8")
        r = self.run_script(str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertIn("already there", r.stderr)
        self.assertEqual((self.out / "clark.app" / "keep").read_text(encoding="utf-8"), "mine")

    def test_an_unknown_option_is_refused(self):
        r = self.run_script("--nope")
        self.assertEqual(r.returncode, 1)
        self.assertIn("unknown option", r.stderr)

    def test_the_applet_runs_the_launcher_hidden_beside_itself(self):
        self.run_script(str(self.out))
        s = self.source()
        self.assertIn("/usr/bin/python3 -m clark.launch", s)
        self.assertIn("path to me", s)
        self.assertIn("do shell script cmd", s)
        self.assertNotIn('tell application "Terminal"', s)

    def test_a_failure_is_shown_in_a_dialog_with_the_launchers_own_lines(self):
        self.run_script(str(self.out))
        s = self.source()
        self.assertIn("on error msg", s)
        self.assertIn("display dialog msg", s)
        self.assertIn("2>&1", s)  # the launcher's lines come back as the dialog text

    def test_the_python_check_uses_the_existing_words_only(self):
        self.run_script(str(self.out))
        self.assertIn("This Mac needs Python 3.9 or newer to run clark, and doesn't have it yet.", self.source())

    def test_a_shipped_build_has_no_test_switches(self):
        self.run_script(str(self.out))
        s = self.source()
        for bad in ("CLARK_BROWSER", "--data", "--port", "applet-out"):
            self.assertNotIn(bad, s)

    def test_a_test_build_bakes_a_scratch_folder_port_and_stub_browser(self):
        r = self.run_script("--test-data", str(self.tmp / "d"), "--test-port", "8765", str(self.out))
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.source()
        self.assertIn("--port 8765", s)
        self.assertIn("CLARK_BROWSER=/usr/bin/true", s)
        self.assertNotIn("display dialog msg", s)
        self.assertIn("applet-out.txt", s)

    def test_a_test_port_must_be_plain_ascii_digits(self):
        marker = self.tmp / "X"
        hostile = [f"1; touch {marker}", "87 65", "8765;", f"`touch {marker}`", f"$(touch {marker})", "87\n65",
                   "٨٧٦٥", "", "-1", "8765 ", "8765\n"]
        for n, port in enumerate(hostile):
            with self.subTest(port=port):
                out = self.tmp / f"o{n}"
                r = self.run_script("--test-data", str(self.tmp / "d"), "--test-port", port, str(out))
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("--test-port", r.stderr)
                self.assertIn("digits", r.stderr)
                self.assertFalse((out / "clark.app").exists())
                self.assertFalse(marker.exists())

    def test_a_test_port_injection_would_reach_the_applets_shell_command(self):
        # why the check matters: without it the text lands unquoted in the command the applet hands to the shell
        marker = self.tmp / "X"
        cmd = f"echo --port 1; touch {marker}"
        subprocess.run(["/bin/sh", "-c", cmd], capture_output=True)
        self.assertTrue(marker.exists())  # the shape of the hostile value does run when unquoted
        marker.unlink()
        r = self.run_script("--test-data", str(self.tmp / "d"), "--test-port", f"1; touch {marker}", str(self.out))
        self.assertEqual(r.returncode, 1)
        self.assertFalse(self.out.exists() and (self.out / "clark.app").exists())

    def test_a_test_data_folder_with_a_quote_or_backslash_is_refused(self):
        for n, data in enumerate(['/tmp/a"b', '/tmp/a\nb', "/tmp/a\\b", '"', '/tmp/x" & (do shell script "touch y") & "']):
            with self.subTest(data=data):
                out = self.tmp / f"d{n}"
                r = self.run_script("--test-data", data, "--test-port", "8765", str(out))
                self.assertEqual(r.returncode, 1, r.stdout)
                self.assertIn("--test-data", r.stderr)
                self.assertFalse((out / "clark.app").exists())

    def test_ordinary_test_data_with_spaces_is_still_built(self):
        r = self.run_script("--test-data", str(self.tmp / "my data"), "--test-port", "8765", str(self.out))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_script_writes_only_where_told(self):
        before = set(os.listdir(self.tmp))
        self.run_script(str(self.out))
        self.assertEqual(set(os.listdir(self.tmp)) - before, {"out"})


if __name__ == "__main__":
    unittest.main()

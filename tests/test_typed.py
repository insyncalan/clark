"""issue 694: the commands clark's messages tell a person to type (src/clark/typed.py). In a download, clark.command sets CLARK_TYPED and
the messages say `bash clark.command ...`; in a checkout (nothing sets it) they say `python3 -m clark ...`, as they always did.
Run: python3 dev/run_tests.py test_typed"""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401
from _paths import ROOT
from clark import __main__ as launcher, backup, doctor, typed

BASH = "bash clark.command"


def download():
    return mock.patch.dict(os.environ, {"CLARK_TYPED": BASH})


def checkout():
    return mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k != "CLARK_TYPED"}, clear=True)


class Words(unittest.TestCase):
    def test_a_download(self):
        with download():
            self.assertEqual(typed.clark(), "bash clark.command")
            self.assertEqual(typed.clark("restore NAME"), "bash clark.command restore NAME")
            self.assertEqual(typed.clark("--data FOLDER"), "bash clark.command --data FOLDER")
            self.assertEqual(typed.doctor(), "bash clark.command --check")

    def test_a_checkout(self):
        with checkout():
            self.assertEqual(typed.clark(), "python3 -m clark")
            self.assertEqual(typed.clark("restore NAME"), "python3 -m clark restore NAME")
            self.assertEqual(typed.doctor(), "python3 -m clark.doctor")

    def test_an_empty_value_counts_as_not_set_and_it_is_read_at_each_call(self):
        with mock.patch.dict(os.environ, {"CLARK_TYPED": ""}):
            self.assertEqual(typed.clark("--help"), "python3 -m clark --help")
        with checkout():
            self.assertEqual(typed.clark(), "python3 -m clark")
            os.environ["CLARK_TYPED"] = BASH
            self.assertEqual(typed.clark(), "bash clark.command")


class Backup(unittest.TestCase):
    def test_both_modes(self):
        with download():
            self.assertIn("\n    bash clark.command restore NAME\n", backup.restore_help())
            self.assertNotIn("python3", backup.restore_help())
            folder = Path(tempfile.mkdtemp(prefix="clark-typed-"))
            self.addCleanup(lambda: __import__("shutil").rmtree(folder, True))
            with self.assertRaises(backup.Invalid) as ctx:
                backup.valid_name(folder, "nope.db")
            self.assertTrue(str(ctx.exception).endswith("To see the backups, run:\n    bash clark.command restore"))
            with self.assertRaises(backup.Invalid) as ctx:
                backup.valid_name(folder, "nope.db", see=typed.clark("restore --from FOLDER"))
            self.assertTrue(str(ctx.exception).endswith("\n    bash clark.command restore --from FOLDER"))
        with checkout():
            self.assertIn("\n    python3 -m clark restore NAME\n", backup.restore_help())


class Launcher(unittest.TestCase):
    def test_both_modes(self):
        with download():
            self.assertEqual(launcher.hint(), "Run bash clark.command --help to see the options.")
            self.assertEqual(launcher.parser().prog, "bash clark.command")
            self.assertIn("bash clark.command restore --help", launcher.parser().epilog)
            self.assertEqual(launcher.restore_parser().prog, "bash clark.command restore")
        with checkout():
            self.assertEqual(launcher.hint(), "Run python3 -m clark --help to see the options.")
            self.assertEqual(launcher.parser().prog, "python3 -m clark")
            self.assertIn("python3 -m clark restore --help", launcher.parser().epilog)
            self.assertEqual(launcher.restore_parser().prog, "python3 -m clark restore")


class Shipped(unittest.TestCase):
    def test_the_module_is_in_the_download_and_imports_nothing_but_the_standard_library(self):
        import package
        self.assertIn("src/clark/typed.py", package.files("mac"))
        imports = [l for l in (ROOT / "src" / "clark" / "typed.py").read_text(encoding="utf-8").splitlines() if l.startswith(("import ", "from "))]
        self.assertEqual(["import os"], imports)


class LauncherScript(unittest.TestCase):
    command = ROOT / "clark.command"

    def test_it_sets_the_variable_before_anything_runs_and_stays_a_shell_script_that_parses(self):
        text = self.command.read_text(encoding="utf-8")
        self.assertIn('export CLARK_TYPED="bash clark.command"\n', text)
        self.assertLess(text.index("export CLARK_TYPED"), text.index("case \"$1\" in"))
        # git checks the file out as 0777 minus the caller's umask, so the on-disk group/other bits vary
        # (775 under umask 002, 755 under 022). What the product sets is the committed mode, and the owner bits.
        self.assertEqual(0o700, stat.S_IMODE(self.command.stat().st_mode) & 0o700)
        tracked = subprocess.run(["git", "ls-files", "-s", "clark.command"], cwd=str(ROOT), capture_output=True, text=True)
        if tracked.returncode == 0 and tracked.stdout:
            self.assertEqual("100755", tracked.stdout.split()[0])
        self.assertEqual(0, subprocess.run(["bash", "-n", str(self.command)], capture_output=True).returncode)

    def test_the_commands_it_forwards_say_bash_clark_command(self):
        env = {k: v for k, v in os.environ.items() if k not in ("CLARK_TYPED", "PYTHONPATH")}
        for args, usage in ((["restore", "--help"], "usage: bash clark.command restore"),
                            (["--check", "--help"], "usage: bash clark.command --check")):
            run = subprocess.run(["bash", "clark.command", *args], cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, run.returncode, run.stderr)
            self.assertIn(usage, run.stdout)


class UsageLine(unittest.TestCase):
    """issue 744: the usage line `--help` and a bad option print is the typed command, through a real process."""

    def run_clark(self, argv, typed_value, via_command=False):
        env = {k: v for k, v in os.environ.items() if k not in ("CLARK_TYPED", "PYTHONPATH")}
        if typed_value:
            env["CLARK_TYPED"] = typed_value
        if via_command:
            argv = ["bash", "clark.command", *argv]
        else:
            argv = ["python3", "-m", *argv]
            env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(argv, cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=60)

    def test_launch_help_in_both_modes(self):
        run = self.run_clark(["clark.launch", "--help"], BASH)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual("usage: bash clark.command [-h] [--data FOLDER] [--port N]", run.stdout.splitlines()[0])
        self.assertNotIn("python3 -m clark.launch", run.stdout)
        run = self.run_clark(["clark.launch", "--help"], "")
        self.assertEqual("usage: python3 -m clark.launch [-h] [--data FOLDER] [--port N]", run.stdout.splitlines()[0])

    def test_launch_bad_option_in_both_modes(self):
        run = self.run_clark(["clark.launch", "--nope"], BASH)
        self.assertEqual(2, run.returncode)
        self.assertEqual("usage: bash clark.command [-h] [--data FOLDER] [--port N]", run.stderr.splitlines()[0])
        self.assertNotIn("python3 -m clark.launch", run.stderr)
        run = self.run_clark(["clark.launch", "--nope"], "")
        self.assertEqual("usage: python3 -m clark.launch [-h] [--data FOLDER] [--port N]", run.stderr.splitlines()[0])

    def test_the_other_help_screens_in_both_modes(self):
        for argv, down, check in ((["clark", "--help"], "usage: bash clark.command ", "usage: python3 -m clark "),
                                  (["clark", "restore", "--help"], "usage: bash clark.command restore ", "usage: python3 -m clark restore "),
                                  (["clark.doctor", "--help"], "usage: bash clark.command --check ", "usage: python3 -m clark.doctor ")):
            self.assertTrue(self.run_clark(argv, BASH).stdout.startswith(down), argv)
            self.assertTrue(self.run_clark(argv, "").stdout.startswith(check), argv)

    def test_clark_command_forwards_help_to_the_launch_parser(self):
        run = self.run_clark(["--help"], "", via_command=True)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual("usage: bash clark.command [-h] [--data FOLDER] [--port N]", run.stdout.splitlines()[0])
        self.assertNotIn("python3 -m clark.launch", run.stdout)


if __name__ == "__main__":
    unittest.main()

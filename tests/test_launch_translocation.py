"""Row 836: the launcher finds its program files from where they really are, never from the folder it was double-clicked in.

Run: python3 dev/run_tests.py test_launch_translocation
Background. clark.app (the applet that runs the launcher with no Terminal) is a quarantined download. macOS may run such an
app from a read-only random copy, /private/var/folders/.../AppTranslocation/<id>/d/clark.app (App Translocation), not from
~/Downloads/clark where the person double-clicked it. Whatever sits BESIDE the app in Downloads is not beside the copy. The fix
the plan names is to put the program files INSIDE the bundle (Contents/Resources), so the only safe way for the launcher to
find its program files is from its own file, never from the working folder, and never from the folder the person opened.

What is pinned here, on the launcher that exists today (src/clark/launch.py, clark/__main__.py, clark.command):
- the launcher's SRC is read from its own file; the server it starts gets exactly that as PYTHONPATH
- the working folder (a Downloads folder with a decoy clark in it) changes nothing about which program files are used
- a copy of the program files laid out as clark.app/Contents/Resources/{clark.command,.app} under an AppTranslocation-shaped
  path runs from that copy: clark.command from its own folder, the Python launcher from the bundle's .app, with the Downloads
  decoy untouched
Nothing real is started or opened: a fake python3 for clark.command, and fakes for starting clark and the port check. The
data folder is always a temporary one. No dialog can open: PATH=/tmp/nodialog:$PATH is assumed, as everywhere.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC

from clark import launch
from test_launcher import Fakes, as_the_mac

BASH = "/bin/bash"
PY3 = sys.executable
TRANSLOCATED = Path("private/var/folders/k9/x9d2v3kd1nq9c0w1j4m8gz6r0000gn/T/AppTranslocation/7A1D7C7E-2F6B-4A8C-9B0D-1E2F3A4B5C6D/d")
DECOY_LINE = "raise SystemExit('the decoy in Downloads must never run')\n"


def decoy_clark(folder):
    """A Downloads-shaped clark folder: everything the launcher could wrongly pick up if it looked beside the double-clicked
    file or in the working folder. Every Python file in it stops at once, so a wrong import is loud."""
    for rel in ("clark/__init__.py", "clark/__main__.py", "clark/launch.py", "src/clark/__init__.py", "src/clark/launch.py",
                ".app/clark/__init__.py", ".app/clark/__main__.py", ".app/clark/launch.py", ".app/src/clark/__init__.py",
                ".app/src/clark/launch.py"):
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DECOY_LINE, encoding="utf-8")
    shutil.copy2(ROOT / "clark.command", folder / "clark.command")
    return folder


class FromItsOwnFile(unittest.TestCase):
    """The resolution the Python launcher does today, in this process."""

    def setUp(self):
        as_the_mac(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="clark translocation ")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.downloads = decoy_clark(self.tmp / "Users" / "someone" / "Downloads" / "clark")
        self.data = self.tmp / "clark-data"
        self.data.mkdir()
        was = os.getcwd()
        self.addCleanup(os.chdir, was)
        os.chdir(self.downloads)            # as if started from the folder the person opened

    def test_src_is_the_folder_above_the_launchers_own_file(self):
        self.assertEqual(launch.SRC, Path(launch.__file__).resolve().parents[1])
        self.assertEqual(launch.SRC, SRC.resolve())
        self.assertTrue((launch.SRC / "clark" / "launch.py").is_file())

    def test_the_server_is_given_the_launchers_own_program_files_not_the_working_folders(self):
        f = Fakes([launch.NOTHING, launch.OURS])
        self.assertEqual(0, launch.launch(8800, self.data, **f.kw()))
        (argv, env, log, cwd), = f.started
        self.assertEqual(str(launch.SRC), env["PYTHONPATH"])
        self.assertNotIn(str(self.downloads), env["PYTHONPATH"])
        self.assertNotIn("Downloads", env["PYTHONPATH"])
        self.assertEqual(argv[1:], ["-m", "clark", "--data", str(self.data), "--port", "8800"])
        self.assertEqual(str(self.data), cwd, "the server runs in the data folder, never in the folder the person opened")

    def test_the_working_folder_is_never_asked(self):
        """Mutation guard: a launcher that read Path.cwd() or os.getcwd() would pass in Downloads; it must not."""
        text = (SRC / "clark" / "launch.py").read_text(encoding="utf-8")
        for wrong in ("getcwd", "Path.cwd", "os.curdir", 'Path(".")', "Path('.')"):
            self.assertNotIn(wrong, text, f"launch.py must not find its files from the working folder ({wrong})")

    def test_the_stand_in_package_finds_src_and_vendor_from_its_own_file(self):
        """clark/__main__.py is what `python3 -m clark.launch` runs first in a checkout; a download has the same file in .app."""
        spec = importlib.util.spec_from_file_location("clark_stand_in_for_test", ROOT / "clark" / "__main__.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)      # defines TOP, SRC, VENDOR and the functions; prepare() is not called
        self.assertEqual(ROOT.resolve(), module.TOP)
        self.assertEqual(str(ROOT.resolve() / "src"), module.SRC)
        self.assertEqual(str(ROOT.resolve() / "vendor"), module.VENDOR)
        self.assertNotIn(str(self.downloads), module.SRC)


def bundle_with_program_files(root):
    """clark.app/Contents/Resources holding clark.command and .app (the download's program files), under an AppTranslocation-
    shaped path: the layout the plan names so the applet needs nothing beside it. A real copy, not links: a link would resolve
    back to the checkout and prove nothing."""
    resources = root / TRANSLOCATED / "clark.app" / "Contents" / "Resources"
    hidden = resources / ".app"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", ".page-build-lock*")
    shutil.copytree(ROOT / "clark", hidden / "clark", ignore=ignore)
    shutil.copytree(ROOT / "src" / "clark", hidden / "src" / "clark", ignore=ignore)
    shutil.copytree(ROOT / "vendor", hidden / "vendor", ignore=ignore)
    shutil.copy2(ROOT / "clark.command", resources / "clark.command")
    return resources


DRIVER = """\
import json, os, sys
from pathlib import Path
from unittest import mock
import clark.launch as stand_in            # found through PYTHONPATH, as `python3 -m clark.launch` finds it in a download
stand_in.prepare()
from clark import __version__, appfiles, launch, platform as pl
started = []
def start(argv, env, log, cwd=None):
    started.append({"argv": argv, "pythonpath": env["PYTHONPATH"], "cwd": cwd, "log": str(log)})
    return type("Process", (), {"poll": lambda s: None})()
answers = iter([launch.NOTHING, launch.OURS, launch.OURS, launch.OURS])
with mock.patch.object(pl, "system", return_value=pl.MAC):
    code = launch.launch(8801, Path(sys.argv[1]), say=lambda s: None, environ={"HOME": sys.argv[2], "PATH": "/bin"},
                         start=start, health=lambda port, mark: next(answers),
                         wait=lambda port, mark, process, health=None: launch.OURS,
                         find_chrome=lambda env: "/stub/browser", open_window=lambda u, c: None, open_browser=lambda u: None,
                         free=lambda p: False, identity=lambda port, mark: (__version__, appfiles.code_mark()), page=lambda p: 200)
print(json.dumps({"code": code, "cwd": os.getcwd(), "stand_in": stand_in.__file__, "launch": launch.__file__,
                  "src": str(launch.SRC), "started": started}))
"""


@unittest.skipUnless(Path(BASH).is_file(), "needs bash")
class InsideTheBundleAtATranslocatedPath(unittest.TestCase):
    """The program files copied into clark.app/Contents/Resources, run from an AppTranslocation-shaped path while the working
    folder is a Downloads folder with a decoy clark in it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark bundle ")).resolve()
        cls.resources = bundle_with_program_files(cls.tmp)
        cls.downloads = decoy_clark(cls.tmp / "Users" / "someone" / "Downloads" / "clark")
        cls.bin = cls.tmp / "bin"
        cls.bin.mkdir()
        cls.driver = cls.tmp / "driver" / "run_launcher.py"      # neither in the bundle nor in Downloads
        cls.driver.parent.mkdir()
        cls.driver.write_text(DRIVER, encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def decoy_bytes(self):
        return {p: p.read_bytes() for p in self.downloads.rglob("*") if p.is_file()}

    def test_the_layout_is_the_one_the_plan_names(self):
        self.assertIn("AppTranslocation", str(self.resources))
        self.assertEqual(["Resources"], os.listdir(self.resources.parent))
        self.assertEqual(sorted([".app", "clark.command"]), sorted(os.listdir(self.resources)))
        for needed in ("clark/__main__.py", "clark/launch.py", "src/clark/launch.py", "src/clark/__main__.py", "vendor/manifest.json"):
            self.assertTrue((self.resources / ".app" / needed).is_file(), needed)
        self.assertFalse(any(p.is_symlink() for p in self.resources.rglob("*")), "a real copy, so paths prove where files are")

    def test_clark_command_inside_the_bundle_runs_from_its_own_folder_and_points_python_at_the_bundles_dot_app(self):
        out = self.tmp / "ran.txt"
        py = self.bin / "python3"
        py.write_text('#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\n'
                      f'{{ pwd; echo "$PYTHONPATH"; echo "$@"; }} > "{out}"\nexit 0\n', encoding="utf-8")
        py.chmod(0o755)
        before = self.decoy_bytes()
        done = subprocess.run([BASH, str(self.resources / "clark.command"), "--port", "8801"], cwd=str(self.downloads),
                              env={"PATH": str(self.bin), "HOME": str(self.tmp / "Users" / "someone")},
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        pwd, pythonpath, args = out.read_text(encoding="utf-8").splitlines()
        self.assertEqual(self.resources, Path(pwd).resolve())
        self.assertEqual(str(self.resources / ".app"), pythonpath)
        self.assertNotIn(str(self.downloads), pwd + pythonpath)
        self.assertEqual("-m clark.launch --port 8801", args)
        self.assertEqual(before, self.decoy_bytes(), "nothing in Downloads was touched")

    def test_the_python_launcher_run_from_the_bundle_uses_the_bundles_program_files_and_never_the_downloads_decoy(self):
        """The real stand-in and the real launcher from the copy, started the way clark.command starts them (PYTHONPATH to the
        bundle's .app), with the working folder being the Downloads decoy. The start is faked and recorded."""
        data = self.tmp / "clark-data"
        data.mkdir(exist_ok=True)
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "CLARK_PORT", "CLARK_DATA_DIR")}
        env.update(PYTHONPATH=str(self.resources / ".app"), PYTHONDONTWRITEBYTECODE="1", CLARK_TYPED="bash clark.command")
        before = self.decoy_bytes()
        done = subprocess.run([PY3, str(self.driver), str(data), str(self.tmp / "Users" / "someone")], cwd=str(self.downloads),
                              env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertNotIn("decoy", done.stdout + done.stderr)
        seen = json.loads(done.stdout.splitlines()[-1])
        hidden = self.resources / ".app"
        self.assertEqual(0, seen["code"])
        self.assertEqual(str(self.downloads), seen["cwd"], "the working folder really was the Downloads decoy")
        self.assertEqual(hidden / "clark" / "launch.py", Path(seen["stand_in"]).resolve())
        self.assertEqual(hidden / "src" / "clark" / "launch.py", Path(seen["launch"]).resolve())
        self.assertEqual(hidden / "src", Path(seen["src"]))
        (started,) = seen["started"]
        self.assertEqual(str(hidden / "src"), started["pythonpath"])
        self.assertEqual(started["argv"][1:], ["-m", "clark", "--data", str(data), "--port", "8801"])
        self.assertEqual(str(data), started["cwd"])
        for value in (seen["stand_in"], seen["launch"], seen["src"], started["pythonpath"]):
            self.assertIn("AppTranslocation", value)
            self.assertNotIn("Downloads", value)
        self.assertEqual(before, self.decoy_bytes(), "nothing in Downloads was touched")
        self.assertEqual([], list(hidden.rglob("__pycache__")), "no bytecode was written into the bundle")


if __name__ == "__main__":
    unittest.main()

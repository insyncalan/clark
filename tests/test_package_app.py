"""clark.app, the applet dev/tools/package.py builds with osacompile (row 836: a start with no Terminal window).

osacompile is a Mac program. It is never run here: every test puts a fake `osacompile` first on the PATH (RULES rule 14), a
small script that writes the bundle layout the real one writes (Contents/Info.plist, Contents/MacOS/applet,
Contents/Resources/Scripts/main.scpt), and records what it was asked. /tmp/nodialog's stubs (osascript, open) stay ahead of
the real PATH too, so nothing can show a window. Builds into temporary folders only and downloads nothing.
Run: python3 dev/run_tests.py test_package_app
"""
import contextlib
import io
import json
import os
import plistlib
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from _paths import ROOT
import package

NODIALOG = "/tmp/nodialog"

# What osacompile writes for `osacompile -o X.app source`, as the fake writes it. The Info.plist keys are the ones the real tool
# gives an applet (identifier, name and version are the ones package.py must then set).
FAKE_OSACOMPILE = r'''#!/bin/sh
# a stand-in for macOS's osacompile: writes an applet bundle without compiling anything
out=""; src=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    *) src="$1"; shift ;;
  esac
done
printf '%s\t%s\t%s\t%s\n' "$0" -o "$out" "$src" >> "$FAKE_OSACOMPILE_LOG"
[ -n "$FAKE_OSACOMPILE_FAIL" ] && { echo "fake osacompile: syntax error" >&2; exit 1; }
[ -f "$src" ] || { echo "fake osacompile: no source" >&2; exit 1; }
mkdir -p "$out/Contents/MacOS" "$out/Contents/Resources/Scripts" "$out/Contents/Resources/description.rtfd"
printf 'applet stand-in\n' > "$out/Contents/MacOS/applet"
chmod 755 "$out/Contents/MacOS/applet"
cp "$src" "$out/Contents/Resources/Scripts/main.scpt"
printf 'icns\n' > "$out/Contents/Resources/applet.icns"
printf 'rsrc\n' > "$out/Contents/Resources/applet.rsrc"
printf 'APPLaplt' > "$out/Contents/PkgInfo"
cat > "$out/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleAllowMixedLocalizations</key>
	<true/>
	<key>CFBundleDevelopmentRegion</key>
	<string>English</string>
	<key>CFBundleExecutable</key>
	<string>applet</string>
	<key>CFBundleIconFile</key>
	<string>applet</string>
	<key>CFBundleIdentifier</key>
	<string>com.apple.ScriptEditor.id.clark</string>
	<key>CFBundleInfoDictionaryVersion</key>
	<string>6.0</string>
	<key>CFBundleName</key>
	<string>clark</string>
	<key>CFBundlePackageType</key>
	<string>APPL</string>
	<key>CFBundleShortVersionString</key>
	<string>1.0</string>
	<key>CFBundleSignature</key>
	<string>aplt</string>
	<key>LSMinimumSystemVersionByArchitecture</key>
	<dict>
		<key>x86_64</key>
		<string>10.6</string>
	</dict>
	<key>LSRequiresCarbon</key>
	<true/>
</dict>
</plist>
PLIST
exit 0
'''


class FakeTool:
    """A folder holding the fake osacompile, put first on the PATH for the test; its log of calls. `cleanup` is the test's
    addCleanup (or addClassCleanup), so the folder and the PATH go when the test does."""

    def __init__(self, cleanup, fail=False):
        self.folder = Path(tempfile.mkdtemp(prefix="clark fake osacompile "))
        cleanup(shutil.rmtree, self.folder, True)
        tool = self.folder / "osacompile"
        tool.write_text(FAKE_OSACOMPILE, encoding="utf-8")
        tool.chmod(0o755)
        self.log = self.folder / "calls.log"
        env = {"PATH": f"{self.folder}{os.pathsep}{NODIALOG}{os.pathsep}{os.environ.get('PATH', '')}",
               "FAKE_OSACOMPILE_LOG": str(self.log), "FAKE_OSACOMPILE_FAIL": "1" if fail else ""}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        cleanup(patch.stop)

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []


def tree(folder):
    """{relative path: (sha256 or None for a folder, mode)} of everything under `folder`."""
    import hashlib
    out = {}
    for path in sorted(Path(folder).rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_dir():
            out[rel] = (None, stat.S_IMODE(path.stat().st_mode))
        else:
            out[rel] = (hashlib.sha256(path.read_bytes()).hexdigest(), stat.S_IMODE(path.stat().st_mode))
    return out


class AppletSourceTest(unittest.TestCase):
    """The AppleScript source kept in the repo: what the applet does when double-clicked, read from the text."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / package.APPLET_SOURCE).read_text(encoding="utf-8")

    def test_the_source_is_tracked_and_named_from_package_py(self):
        self.assertEqual(Path("dev") / "tools" / "clark_applet.applescript", Path(package.APPLET_SOURCE))
        out = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", str(package.APPLET_SOURCE)],
                             capture_output=True, text=True)
        self.assertEqual(0, out.returncode, "the applet source is committed, the built clark.app never is")

    def test_the_applet_hands_over_to_the_clark_command_inside_the_bundle(self):
        """The hand-off: the applet runs the clark.command it carries (Contents/Resources, beside the program files), through bash,
        from the bundle's own path (path to me), so a quarantined download run from a copy elsewhere still finds everything."""
        self.assertIn('set here to POSIX path of (path to me)', self.source)
        self.assertIn('set launcher to here & "Contents/Resources/clark.command"', self.source)
        self.assertIn('do shell script "/bin/bash " & quoted form of launcher & " 1>&2"', self.source)
        code = "\n".join(ln for ln in self.source.splitlines() if not ln.lstrip().startswith("--"))
        self.assertNotIn("python3", code, "the launcher's checks are clark.command's, not repeated here")
        self.assertNotIn("Terminal", code)
        self.assertEqual(1, code.count("do shell script"), "one hand-off, nothing else is run")

    def test_a_failure_shows_only_what_clark_command_said(self):
        """No new dialog text: the one dialog shows the words clark.command and the launcher printed (`said`), and the only
        string literals in the source are the path, the bash call, the redirect and macOS's own button word."""
        self.assertIn("on error said", self.source)
        self.assertIn('display dialog said buttons {"OK"} default button "OK"', self.source)
        literals = re.findall(r'"([^"]*)"', "\n".join(ln for ln in self.source.splitlines() if not ln.lstrip().startswith("--")))
        self.assertEqual({"Contents/Resources/clark.command", "/bin/bash ", " 1>&2", "OK"}, set(literals), literals)
        self.assertEqual(1, self.source.count("display dialog"))
        self.assertNotIn("display alert", self.source)
        self.assertNotIn("display notification", self.source)

    def test_the_source_has_no_name_and_lf_endings(self):
        self.assertNotIn("\r", self.source)
        self.assertTrue(self.source.endswith("\n"))
        self.assertNotIn("@", self.source)


class BuildAppTest(unittest.TestCase):
    """package.build_app with the fake osacompile, on the real tree (dirty, like MacZipTest)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="clark app ")
        cls.addClassCleanup(shutil.rmtree, cls.tmp, True)
        cls.fake = FakeTool(cls.addClassCleanup)
        cls.app = package.build_app(Path(cls.tmp) / "one", dirty=True)
        cls.resources = cls.app / "Contents" / "Resources"
        cls.zip = package.build("mac", Path(cls.tmp) / "zip", dirty=True)

    def test_osacompile_is_called_with_the_repo_source_and_the_bundle_path(self):
        """Every build in this class is one osacompile call: `osacompile -o <part>/clark.app <repo>/dev/tools/clark_applet.applescript`."""
        calls = self.fake.calls()
        self.assertGreaterEqual(len(calls), 1, calls)
        for call in calls:
            with self.subTest(call=call):
                tool, _o, out, src = call.split("\t")
                self.assertEqual(str(self.fake.folder / "osacompile"), tool)
                self.assertEqual("-o", _o)
                self.assertEqual("clark.app", Path(out).name)
                self.assertEqual(str(ROOT / package.APPLET_SOURCE), src)

    def test_the_bundle_is_called_clark_app_and_has_the_applet_layout(self):
        self.assertEqual("clark.app", self.app.name)
        self.assertEqual(Path(self.tmp) / "one", self.app.parent)
        self.assertTrue((self.app / "Contents" / "Info.plist").is_file())
        self.assertTrue(os.access(self.app / "Contents" / "MacOS" / "applet", os.X_OK))
        self.assertEqual((ROOT / package.APPLET_SOURCE).read_bytes(), (self.resources / "Scripts" / "main.scpt").read_bytes(),
                         "the compiled script is made from the repo source (the fake copies it)")

    def test_info_plist_has_the_bundle_id_and_the_version(self):
        info = plistlib.loads((self.app / "Contents" / "Info.plist").read_bytes())
        self.assertEqual(package.BUNDLE_ID, info["CFBundleIdentifier"])
        self.assertEqual("local.clark.app", package.BUNDLE_ID)
        self.assertEqual(package.version(), info["CFBundleShortVersionString"])
        self.assertEqual(package.version(), info["CFBundleVersion"])
        self.assertEqual("clark", info["CFBundleName"])
        self.assertEqual("applet", info["CFBundleExecutable"], "what osacompile wrote is kept")
        self.assertEqual("APPL", info["CFBundlePackageType"])
        self.assertNotIn("com.apple.ScriptEditor", info["CFBundleIdentifier"])

    def test_resources_hold_the_clark_folder_as_the_zip_unzips_it(self):
        """clark.command and the program files (.app/, with clark-release.json beside them) sit in Contents/Resources, byte for
        byte what the zip holds below its top folder, so clark.command's own rules (the .app folder beside it, row 760's
        manifest check) hold unchanged; the applet needs nothing beside the bundle."""
        with zipfile.ZipFile(self.zip) as z:
            held = {i.filename[len("clark/"):]: (z.read(i), stat.S_IMODE(i.external_attr >> 16)) for i in z.infolist()}
        for rel, (data, mode) in held.items():
            with self.subTest(rel=rel):
                path = self.resources / rel
                self.assertTrue(path.is_file(), rel)
                self.assertEqual(data, path.read_bytes())
                self.assertEqual(mode, stat.S_IMODE(path.stat().st_mode))
        self.assertIn("clark.command", held)
        self.assertIn(".app/src/clark/launch.py", held)
        self.assertIn(package.MANIFEST, held)
        self.assertTrue(os.access(self.resources / "clark.command", os.X_OK))

    def test_nothing_else_is_put_in_resources(self):
        """Only what osacompile wrote and the clark folder: no scratch file, no dist, no second copy."""
        from clark import release_files
        with zipfile.ZipFile(self.zip) as z:
            from_zip = {i.filename[len("clark/"):].split("/")[0] for i in z.infolist()}
        top = {p.name for p in self.resources.iterdir()}
        self.assertEqual(from_zip | {"Scripts", "applet.icns", "applet.rsrc", "description.rtfd"}, top)
        self.assertFalse([n for n in top if n.startswith(".") and n != release_files.HIDDEN], top)

    def test_the_manifest_inside_matches_the_files_beside_it(self):
        """same_version reads clark-release.json beside .app on start: every program file it lists is there with that hash."""
        import hashlib
        doc = json.loads((self.resources / package.MANIFEST).read_text(encoding="utf-8"))
        self.assertEqual(package.version(), doc["version"])
        for rel, row in doc["files"].items():
            with self.subTest(rel=rel):
                self.assertEqual(row["sha256"], hashlib.sha256((self.resources / rel).read_bytes()).hexdigest())

    def test_two_builds_give_the_same_tree(self):
        again = package.build_app(Path(self.tmp) / "two", dirty=True)
        self.assertEqual(tree(self.app), tree(again))

    def test_building_again_into_the_same_folder_replaces_the_bundle(self):
        where = Path(self.tmp) / "again"
        first = package.build_app(where, dirty=True)
        (first / "Contents" / "Resources" / "stale.txt").write_text("old\n", encoding="utf-8")
        second = package.build_app(where, dirty=True)
        self.assertEqual(first, second)
        self.assertFalse((second / "Contents" / "Resources" / "stale.txt").exists())
        self.assertEqual([package.APP_NAME], os.listdir(where), "no part folder is left behind")


class RefusalsTest(unittest.TestCase):
    def out_folder(self):
        tmp = tempfile.mkdtemp(prefix="clark app refusal ")
        self.addCleanup(shutil.rmtree, tmp, True)
        return Path(tmp) / "out"

    def test_a_missing_osacompile_is_refused_in_the_existing_words_and_nothing_is_written(self):
        """A box without osacompile (Linux, or a PATH without it) refuses before any file is read or written. The sentence is
        package.py's own missing-file one, not a new one."""
        out = self.out_folder()
        with mock.patch.dict(os.environ, {"PATH": str(out.parent)}):          # a PATH with nothing on it
            self.assertIsNone(shutil.which("osacompile"))
            with mock.patch.object(package.subprocess, "run", side_effect=AssertionError("nothing may be run")):
                with self.assertRaises(package.Refused) as said:
                    package.build_app(out, dirty=True)
        self.assertEqual("A file the download needs is missing: osacompile. Restore it, then build again.", str(said.exception))
        self.assertFalse(out.exists())

    def test_a_failing_osacompile_is_refused_and_leaves_no_bundle(self):
        fake = FakeTool(self.addCleanup, fail=True)
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertEqual("clark.app could not be built, so nothing was written: fake osacompile: syntax error", str(said.exception))
        self.assertEqual(1, len(fake.calls()))
        self.assertFalse((out / package.APP_NAME).exists())
        self.assertEqual([], [p for p in out.iterdir()] if out.exists() else [], "no part folder is left behind")

    def test_a_tool_that_writes_no_bundle_is_refused(self):
        fake = FakeTool(self.addCleanup)
        (fake.folder / "osacompile").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertIn("clark.app could not be built, so nothing was written", str(said.exception))
        self.assertFalse((out / package.APP_NAME).exists())

    def test_the_zip_s_own_refusals_come_first(self):
        """The bundle is the same content as the zip, so the zip's rules (uncommitted changes, a missing listed file) refuse it too."""
        FakeTool(self.addCleanup)
        out = self.out_folder()
        with mock.patch.object(package, "uncommitted", return_value=" M README.md"):
            with self.assertRaises(package.Refused) as said:
                package.build_app(out)
        self.assertIn("aren't committed", str(said.exception))
        self.assertFalse(out.exists())


class CommandTest(unittest.TestCase):
    def run_main(self, *argv):
        err, out = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            code = package.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_mac_with_app_builds_the_zip_and_the_bundle(self):
        FakeTool(self.addCleanup)
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self.run_main("mac", "--app", "--out", tmp, "--dirty")
            self.assertEqual(0, code, err)
            self.assertEqual(sorted([package.zip_name("mac"), package.APP_NAME]), sorted(os.listdir(tmp)))
            lines = out.strip().splitlines()
            self.assertEqual(2, len(lines), out)
            self.assertTrue(lines[0].startswith("Built the Mac download: "), lines[0])
            self.assertIn(package.zip_name("mac"), lines[0])
            self.assertTrue(lines[1].startswith("Built the Mac download: "), lines[1])
            self.assertIn(package.APP_NAME, lines[1])
            self.assertTrue(lines[1].endswith(package.audience(package.ROOT)), lines[1])

    def test_without_app_no_bundle_is_built_and_osacompile_is_not_asked_for(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"PATH": f"{NODIALOG}{os.pathsep}{os.environ.get('PATH', '')}"}):
            code, out, err = self.run_main("mac", "--out", tmp, "--dirty")
            self.assertEqual(0, code, err)
            self.assertEqual([package.zip_name("mac")], os.listdir(tmp))

    def test_app_without_osacompile_refuses_before_the_zip_is_written(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"PATH": tmp}):          # a PATH with nothing on it
            code, out, err = self.run_main("mac", "--app", "--out", tmp, "--dirty")
            self.assertEqual(1, code)
            self.assertEqual("A file the download needs is missing: osacompile. Restore it, then build again.", err.strip())
            self.assertEqual("", out)
            self.assertEqual([], os.listdir(tmp))

    def test_help_names_the_flag(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as held:
            package.main(["--help"])
        self.assertIn("--app", held.getvalue())
        self.assertIn("clark.app", held.getvalue())


if __name__ == "__main__":
    unittest.main()

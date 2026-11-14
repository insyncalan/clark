"""clark.app, the applet dev/tools/package.py builds with osacompile (row 836: a start with no Terminal window).

osacompile and codesign are Mac programs. They are never run here: every test puts a fake `osacompile` and a fake `codesign`
first on the PATH (RULES rule 14), small scripts that write the bundle layout the real compiler writes (Contents/Info.plist,
Contents/MacOS/applet, Contents/Resources/Scripts/main.scpt) and record what they were asked, raw and in order. /tmp/nodialog's
stubs (osascript, open) stay ahead of the real PATH too, so nothing can show a window. Builds into temporary folders only and
downloads nothing.
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
# gives an applet (identifier, name and version are the ones package.py must then set). Like the real tool (BSD getopt) the
# fake reads options only up to the first operand: `osacompile source -o X.app` would take all three as source files and fail.
FAKE_OSACOMPILE = r'''#!/bin/sh
# a stand-in for macOS's osacompile: writes an applet bundle without compiling anything
{ printf '%s' "$0"; for a in "$@"; do printf '\t%s' "$a"; done; printf '\n'; } >> "$FAKE_OSACOMPILE_LOG"
printf 'osacompile\n' >> "$FAKE_TOOL_ORDER"
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -*) echo "fake osacompile: unknown option $1" >&2; exit 1 ;;
    *) break ;;
  esac
done
[ $# -eq 1 ] || { echo "fake osacompile: expected one source file, got $#" >&2; exit 1; }
src="$1"
[ -n "$FAKE_OSACOMPILE_FAIL" ] && { echo "fake osacompile: syntax error" >&2; exit 1; }
[ -n "$out" ] && [ -f "$src" ] || { echo "fake osacompile: no source" >&2; exit 1; }
mkdir -p "$out/Contents/MacOS" "$out/Contents/Resources/Scripts" "$out/Contents/Resources/description.rtfd"
[ -n "$FAKE_OSACOMPILE_EXTRA" ] && printf 'x\n' > "$out/Contents/Resources/$FAKE_OSACOMPILE_EXTRA"
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

# A stand-in for macOS's codesign: records its arguments and, so a test can see what it was handed, a copy of the bundle as it
# was at that moment (its last argument, like the real tool's).
FAKE_CODESIGN = r'''#!/bin/sh
{ printf '%s' "$0"; for a in "$@"; do printf '\t%s' "$a"; done; printf '\n'; } >> "$FAKE_CODESIGN_LOG"
printf 'codesign\n' >> "$FAKE_TOOL_ORDER"
for last in "$@"; do :; done
case " $* " in
  *" --verify "*) [ -n "$FAKE_CODESIGN_VERIFY_FAIL" ] && { echo "fake codesign: $last: invalid signature" >&2; exit 1; }
                  [ -d "$last" ] || exit 1; exit 0 ;;
esac
[ -n "$FAKE_CODESIGN_FAIL" ] && { echo "fake codesign: no identity found" >&2; exit 1; }
[ -d "$last" ] || { echo "fake codesign: $last: No such file or directory" >&2; exit 1; }
rm -rf "$FAKE_CODESIGN_SNAPSHOT"
cp -Rp "$last" "$FAKE_CODESIGN_SNAPSHOT"
exit 0
'''


class FakeTool:
    """A folder holding the fake osacompile and codesign, put first on the PATH for the test; their logs of calls. `cleanup`
    is the test's addCleanup (or addClassCleanup), so the folder and the PATH go when the test does. `extra` makes the fake
    osacompile put a file of that name in Contents/Resources (what a tool that clashes with ours would do); `codesign=False`
    leaves codesign out of the folder."""

    def __init__(self, cleanup, fail=False, codesign=True, codesign_fail=False, extra="", verify_fail=False):
        self.folder = Path(tempfile.mkdtemp(prefix="clark fake osacompile "))
        cleanup(shutil.rmtree, self.folder, True)
        for name, text in (("osacompile", FAKE_OSACOMPILE), ("codesign", FAKE_CODESIGN)):
            if name == "codesign" and not codesign:
                continue
            tool = self.folder / name
            tool.write_text(text, encoding="utf-8")
            tool.chmod(0o755)
        self.log = self.folder / "calls.log"
        self.codesign_log = self.folder / "codesign.log"
        self.order_log = self.folder / "order.log"
        self.snapshot = self.folder / "signed.app"
        env = {"PATH": f"{self.folder}{os.pathsep}{NODIALOG}{os.pathsep}{os.environ.get('PATH', '')}",
               "FAKE_OSACOMPILE_LOG": str(self.log), "FAKE_OSACOMPILE_FAIL": "1" if fail else "", "FAKE_OSACOMPILE_EXTRA": extra,
               "FAKE_CODESIGN_LOG": str(self.codesign_log), "FAKE_CODESIGN_FAIL": "1" if codesign_fail else "",
               "FAKE_CODESIGN_VERIFY_FAIL": "1" if verify_fail else "",
               "FAKE_CODESIGN_SNAPSHOT": str(self.snapshot), "FAKE_TOOL_ORDER": str(self.order_log)}
        patch = mock.patch.dict(os.environ, env)
        patch.start()
        cleanup(patch.stop)

    @staticmethod
    def _lines(path):
        return path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    def calls(self):
        return self._lines(self.log)

    def codesign_calls(self):
        return self._lines(self.codesign_log)

    def order(self):
        return self._lines(self.order_log)


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
        """Every build in this class is one osacompile call, its arguments in exactly this order (the real tool reads options
        only up to the first operand): `osacompile -o <part>/clark.app <repo>/dev/tools/clark_applet.applescript`."""
        calls = self.fake.calls()
        self.assertGreaterEqual(len(calls), 1, calls)
        for call in calls:
            with self.subTest(call=call):
                argv = call.split("\t")
                self.assertEqual(4, len(argv), argv)
                self.assertEqual([str(self.fake.folder / "osacompile"), "-o"], argv[:2])
                self.assertEqual("clark.app", Path(argv[2]).name)
                self.assertEqual(str(ROOT / package.APPLET_SOURCE), argv[3])

    def test_the_fake_osacompile_refuses_a_swapped_order_like_the_real_one(self):
        """The fake is only worth something if `osacompile source -o X.app` fails on it as it does on a Mac."""
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([str(self.fake.folder / "osacompile"), str(ROOT / package.APPLET_SOURCE), "-o", f"{tmp}/x.app"],
                                  capture_output=True, text=True)
        self.assertNotEqual(0, done.returncode)
        self.assertIn("expected one source file", done.stderr)

    def test_the_bundle_is_ad_hoc_signed_last_with_codesign(self):
        """After Info.plist is rewritten and Contents/Resources filled, `codesign --force --deep -s - <bundle>` seals the bundle
        (ad hoc, no account): an applet stub signed by Apple would otherwise carry a broken signature, and Gatekeeper calls such
        a download damaged with no Open Anyway. The fake codesign keeps a copy of what it was handed: the finished bundle."""
        fake = FakeTool(self.addCleanup)
        out = Path(self.tmp) / "signed"
        app = package.build_app(out, dirty=True)
        self.assertEqual(["osacompile", "codesign", "codesign"], fake.order(), "compile, sign, then verify")
        calls = fake.codesign_calls()
        self.assertEqual(2, len(calls), calls)
        argv = calls[0].split("\t")
        self.assertEqual([str(fake.folder / "codesign"), "--force", "--deep", "-s", "-"], argv[:5])
        self.assertEqual(6, len(argv), argv)
        signed = Path(argv[5])
        self.assertEqual(package.APP_NAME, signed.name)
        self.assertEqual(out, signed.parent.parent, "signed where it was built, then moved into place")
        self.assertTrue(signed.parent.name.startswith(".clark.app."), signed)
        check = calls[1].split("\t")
        self.assertEqual([str(fake.folder / "codesign"), "--verify", "--deep", "--strict", argv[5]], check)
        self.assertEqual(tree(app), tree(fake.snapshot), "codesign saw the finished bundle, nothing changed after it")
        info = plistlib.loads((fake.snapshot / "Contents" / "Info.plist").read_bytes())
        self.assertEqual(package.BUNDLE_ID, info["CFBundleIdentifier"])
        self.assertTrue((fake.snapshot / "Contents" / "Resources" / "clark.command").is_file())

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
        self.assertEqual(package.MISSING_FILE.format(what=package.OSACOMPILE), str(said.exception), "one constant, not a second copy")
        self.assertFalse(out.exists())

    def test_a_missing_codesign_is_refused_in_the_same_words_and_nothing_is_run(self):
        """codesign is checked with osacompile, before anything is read or written, in the same sentence with its own name."""
        fake = FakeTool(self.addCleanup, codesign=False)
        out = self.out_folder()
        with mock.patch.dict(os.environ, {"PATH": str(fake.folder)}):           # osacompile alone on the PATH
            self.assertIsNotNone(shutil.which("osacompile"))
            self.assertIsNone(shutil.which("codesign"))
            with mock.patch.object(package.subprocess, "run", side_effect=AssertionError("nothing may be run")):
                with self.assertRaises(package.Refused) as said:
                    package.build_app(out, dirty=True)
        self.assertEqual("A file the download needs is missing: codesign. Restore it, then build again.", str(said.exception))
        self.assertEqual([], fake.calls())
        self.assertFalse(out.exists())

    def test_a_failing_codesign_is_refused_and_leaves_no_bundle(self):
        fake = FakeTool(self.addCleanup, codesign_fail=True)
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertEqual("clark.app could not be built, so nothing was written: fake codesign: no identity found", str(said.exception))
        self.assertEqual(1, len(fake.codesign_calls()))
        self.assertEqual([], os.listdir(out) if out.exists() else [], "no bundle, no part folder")

    def test_a_signature_that_does_not_verify_is_refused_and_leaves_no_bundle(self):
        fake = FakeTool(self.addCleanup, verify_fail=True)
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertEqual("clark.app could not be built, so nothing was written: fake codesign: "
                         f"{fake.codesign_calls()[1].split(chr(9))[-1]}: invalid signature", str(said.exception))
        self.assertEqual(2, len(fake.codesign_calls()))
        self.assertEqual([], os.listdir(out) if out.exists() else [])

    def test_a_folder_that_is_not_our_bundle_is_never_deleted(self):
        """dist/clark.app that the tool did not make (no Info.plist with our bundle id) is refused and left as it is."""
        FakeTool(self.addCleanup)
        for label, plist in (("no plist", None), ("another id", plistlib.dumps({"CFBundleIdentifier": "com.example.other"})),
                             ("not a plist", b"junk")):
            with self.subTest(label):
                out = self.out_folder()
                target = out / package.APP_NAME
                (target / "Contents").mkdir(parents=True)
                (target / "mine.txt").write_text("keep\n", encoding="utf-8")
                if plist is not None:
                    (target / "Contents" / "Info.plist").write_bytes(plist)
                with self.assertRaises(package.Refused) as said:
                    package.build_app(out, dirty=True)
                self.assertTrue(str(said.exception).startswith("clark.app could not be built, so nothing was written: "), str(said.exception))
                self.assertEqual("keep\n", (target / "mine.txt").read_text(encoding="utf-8"))
                self.assertEqual([package.APP_NAME], os.listdir(out), "no part folder is left behind")

    def test_a_folder_that_cannot_be_made_is_refused_in_the_could_not_build_words(self):
        """An OSError before the bundle is started (the part folder here) is the bundle's own refusal too."""
        FakeTool(self.addCleanup)
        out = self.out_folder()
        with mock.patch.object(package.tempfile, "mkdtemp", side_effect=PermissionError(13, "Permission denied")):
            with self.assertRaises(package.Refused) as said:
                package.build_app(out, dirty=True)
        self.assertTrue(str(said.exception).startswith("clark.app could not be built, so nothing was written: "), str(said.exception))

    def test_a_tool_that_does_not_finish_is_refused_like_one_that_fails(self):
        """A hung osacompile ends in the could-not-build sentence, not a traceback, and leaves nothing."""
        FakeTool(self.addCleanup)
        out = self.out_folder()

        def hangs(argv, **kw):
            raise subprocess.TimeoutExpired(argv, kw.get("timeout"))

        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True, run=hangs)
        self.assertEqual(f"clark.app could not be built, so nothing was written: osacompile did not finish in {package.TOOL_TIMEOUT} s",
                         str(said.exception))
        self.assertEqual([], os.listdir(out) if out.exists() else [])

    def test_a_tool_whose_own_files_clash_with_ours_is_refused(self):
        """osacompile's files and the clark folder never mix: a Resources entry that matches one of ours (by name, case aside)
        is refused before anything of ours is written there."""
        FakeTool(self.addCleanup, extra="CLARK.COMMAND")
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertEqual("clark.app could not be built, so nothing was written: osacompile already put clark.command in Contents/Resources",
                         str(said.exception))
        self.assertEqual([], os.listdir(out) if out.exists() else [])

    def test_a_plain_file_where_the_bundle_goes_is_refused_in_the_could_not_build_words(self):
        """An OSError on the way (here: dist/clark.app is a file, so the bundle can't take its place) is the bundle's own
        refusal, not a traceback and not the release-notes sentence; the file is left as it was."""
        FakeTool(self.addCleanup)
        out = self.out_folder()
        out.mkdir(parents=True)
        (out / package.APP_NAME).write_text("not a bundle\n", encoding="utf-8")
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertTrue(str(said.exception).startswith("clark.app could not be built, so nothing was written: "), str(said.exception))
        self.assertEqual("not a bundle\n", (out / package.APP_NAME).read_text(encoding="utf-8"))
        self.assertEqual([package.APP_NAME], os.listdir(out), "no part folder is left behind")

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


class PinnedSurvivorsTest(unittest.TestCase):
    """Behaviours the mutation proof found unpinned: the tool timeout, the applet-folder check, a clash that differs only in
    case, which stream a failure is read from, --dirty on the zip and bundle paths, the name guard on the bundle, and the
    injected tool lookup. Fake tools only; temporary folders only."""

    def out_folder(self):
        tmp = tempfile.mkdtemp(prefix="clark app pin ")
        self.addCleanup(shutil.rmtree, tmp, True)
        return Path(tmp) / "out"

    def test_every_tool_run_is_given_a_timeout_of_300_seconds(self):
        FakeTool(self.addCleanup)
        seen = []

        def spy(argv, **kw):
            seen.append((Path(argv[0]).name, kw.get("timeout", "absent")))
            return subprocess.run(argv, **kw)

        package.build_app(self.out_folder(), dirty=True, run=spy)
        self.assertEqual(["osacompile", "codesign", "codesign"], [n for n, _ in seen])
        self.assertEqual([300, 300, 300], [t for _, t in seen])

    def test_a_failure_is_read_from_stderr_before_stdout(self):
        def run(argv, **kw):
            return subprocess.CompletedProcess(argv, 1, stdout="said on stdout\n", stderr="first\nsaid on stderr\n")

        with self.assertRaises(package.Refused) as said:
            package._tool(run, ["/x/osacompile"])
        self.assertEqual("clark.app could not be built, so nothing was written: said on stderr", str(said.exception))

        def only_out(argv, **kw):
            return subprocess.CompletedProcess(argv, 1, stdout="a\nonly stdout\n", stderr="")

        with self.assertRaises(package.Refused) as said:
            package._tool(only_out, ["/x/osacompile"])
        self.assertTrue(str(said.exception).endswith("only stdout"), str(said.exception))

    def test_an_applet_with_a_plist_but_no_macos_folder_is_refused(self):
        fake = FakeTool(self.addCleanup)
        text = (fake.folder / "osacompile").read_text(encoding="utf-8").replace(
            'mkdir -p "$out/Contents/MacOS" ', 'mkdir -p ').replace(
            "printf 'applet stand-in\\n' > \"$out/Contents/MacOS/applet\"\nchmod 755 \"$out/Contents/MacOS/applet\"\n", "")
        self.assertNotIn("Contents/MacOS", text)
        (fake.folder / "osacompile").write_text(text, encoding="utf-8")
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertEqual("clark.app could not be built, so nothing was written: osacompile wrote no applet bundle", str(said.exception))
        self.assertFalse((out / package.APP_NAME).exists())

    def test_a_clash_that_differs_from_our_name_only_in_case_is_refused(self):
        """Our top-level README.md against the tool's readme.md: the two are one file on a Mac's disk."""
        FakeTool(self.addCleanup, extra="readme.md")
        out = self.out_folder()
        with self.assertRaises(package.Refused) as said:
            package.build_app(out, dirty=True)
        self.assertEqual("clark.app could not be built, so nothing was written: osacompile already put README.md in Contents/Resources",
                         str(said.exception))

    def test_dirty_builds_the_zip_the_bundle_and_both_from_uncommitted_files(self):
        FakeTool(self.addCleanup)
        with mock.patch.object(package, "uncommitted", return_value=" M README.md"):
            with self.assertRaises(package.Refused):
                package.build("mac", self.out_folder())                      # control: without --dirty it is refused
            self.assertTrue(package.build("mac", self.out_folder(), dirty=True).is_file())
            self.assertTrue(package.build_app(self.out_folder(), dirty=True).is_dir())
            tmp = self.out_folder()
            err, out = io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                code = package.main(["mac", "--app", "--out", str(tmp), "--dirty"])
            self.assertEqual(0, code, err.getvalue())
            self.assertEqual(sorted([package.zip_name("mac"), package.APP_NAME]), sorted(os.listdir(tmp)))
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(1, package.main(["mac", "--app", "--out", str(self.out_folder())]))

    def test_the_bundle_for_a_client_is_refused_for_a_name_in_a_file(self):
        from test_package import ForClientTest
        from test_no_real_names import FICTIONAL
        helper = ForClientTest("run_main")
        self.addCleanup(helper.doCleanups)
        FakeTool(self.addCleanup)
        root = helper.snapshot({"src/clark/notes.py": "# Prepared for Northwind Traders\nx = 1\n",
                                "dev/tools/clark_applet.applescript": "-- applet\n"})
        out = self.out_folder()
        with mock.patch.object(package, "SHARED", ("README.md", "src/clark/")), \
                mock.patch.object(package, "SYSTEMS", {"mac": ("clark.command",)}), \
                mock.patch.object(package, "APPLET_SOURCE", Path("dev") / "tools" / "clark_applet.applescript"):
            with self.assertRaises(package.Refused) as said:
                package.build_app(out, root=root, for_client=True, banned=FICTIONAL)
        self.assertIn("the name guard found one in: src/clark/notes.py.", str(said.exception))
        self.assertFalse(out.exists() and (out / package.APP_NAME).exists())

    def test_the_tool_lookup_that_is_passed_in_is_the_one_used(self):
        fake = FakeTool(self.addCleanup)
        elsewhere = Path(tempfile.mkdtemp(prefix="clark other tools "))
        self.addCleanup(shutil.rmtree, elsewhere, True)
        for name in ("osacompile", "codesign"):
            shutil.copy2(fake.folder / name, elsewhere / name)
        asked = []

        def which(name):
            asked.append(name)
            return str(elsewhere / name)

        package.build_app(self.out_folder(), dirty=True, which=which)
        self.assertEqual(["osacompile", "codesign"], asked)
        self.assertEqual([str(elsewhere / "osacompile")], [c.split("\t")[0] for c in fake.calls()])
        with self.assertRaises(package.Refused):
            package.build_app(self.out_folder(), dirty=True, which=lambda name: None)   # the PATH has both; the lookup says no


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

    def test_app_without_codesign_refuses_before_the_zip_is_written(self):
        fake = FakeTool(self.addCleanup, codesign=False)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"PATH": str(fake.folder)}):
            code, out, err = self.run_main("mac", "--app", "--out", tmp, "--dirty")
            self.assertEqual(1, code)
            self.assertEqual("A file the download needs is missing: codesign. Restore it, then build again.", err.strip())
            self.assertEqual("", out)
            self.assertEqual([], os.listdir(tmp))

    def test_a_failing_run_leaves_an_earlier_zip_exactly_as_it_was(self):
        """The zip of an earlier good run is replaced only when the whole run succeeded."""
        fake = FakeTool(self.addCleanup, fail=True)
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / package.zip_name("mac")
            zip_path.write_bytes(b"an earlier good zip")
            code, out, err = self.run_main("mac", "--app", "--out", tmp, "--dirty")
            self.assertEqual(1, code)
            self.assertEqual(b"an earlier good zip", zip_path.read_bytes())
            self.assertEqual([package.zip_name("mac")], os.listdir(tmp), "no staging folder is left behind")

    def test_a_successful_run_replaces_an_earlier_zip(self):
        FakeTool(self.addCleanup)
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / package.zip_name("mac")
            zip_path.write_bytes(b"an earlier zip")
            code, out, err = self.run_main("mac", "--app", "--out", tmp, "--dirty")
            self.assertEqual(0, code, err)
            self.assertEqual(sorted([package.zip_name("mac"), package.APP_NAME]), sorted(os.listdir(tmp)))
            self.assertTrue(zipfile.is_zipfile(zip_path))

    def test_the_zip_with_app_is_the_zip_without_it(self):
        FakeTool(self.addCleanup)
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self.assertEqual(0, self.run_main("mac", "--out", one, "--dirty")[0])
            self.assertEqual(0, self.run_main("mac", "--app", "--out", two, "--dirty")[0])
            name = package.zip_name("mac")
            self.assertEqual((Path(one) / name).read_bytes(), (Path(two) / name).read_bytes())

    def test_an_os_error_before_the_bundle_is_the_could_not_build_sentence_and_keeps_the_zip(self):
        FakeTool(self.addCleanup)
        real = tempfile.mkdtemp

        def deny(*a, **kw):
            if kw.get("prefix") == ".clark.app.":
                raise PermissionError(13, "Permission denied")
            return real(*a, **kw)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(package.tempfile, "mkdtemp", side_effect=deny):
            zip_path = Path(tmp) / package.zip_name("mac")
            zip_path.write_bytes(b"an earlier good zip")
            code, out, err = self.run_main("mac", "--app", "--out", tmp, "--dirty")
            self.assertEqual(1, code)
            self.assertTrue(err.startswith("clark.app could not be built, so nothing was written: "), err)
            self.assertNotIn("release notes", err)
            self.assertEqual(b"an earlier good zip", zip_path.read_bytes())
            self.assertEqual([package.zip_name("mac")], os.listdir(tmp))

    def test_a_bundle_that_fails_leaves_no_zip_behind(self):
        """--app is all or nothing: when the bundle can't be built the sentence says nothing was written, and that is true of
        the zip too."""
        FakeTool(self.addCleanup, fail=True)
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = self.run_main("mac", "--app", "--out", tmp, "--dirty")
            self.assertEqual(1, code)
            self.assertEqual("clark.app could not be built, so nothing was written: fake osacompile: syntax error", err.strip())
            self.assertEqual("", out)
            self.assertEqual([], os.listdir(tmp))

    def test_help_names_the_flag(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()) as held:
            package.main(["--help"])
        self.assertIn("--app", held.getvalue())
        self.assertIn("clark.app", held.getvalue())


if __name__ == "__main__":
    unittest.main()

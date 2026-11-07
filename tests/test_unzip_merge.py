"""Unzipping a newer download over an older one's folder (issue 746): two versions' files merge in one folder.

The download unzips to one folder called clark with the program files in the hidden .app (issue 694), so a person who unzips a
newer download into the same place as an older install (`unzip -o`, or `ditto`) gets a folder that holds both versions' files:
the new ones win where both have a file, and the older version's other files stay. These tests build a small two-version pair
(the real current download as the newer one; the older one is made from it with a lower version, a file the newer lacks, a
changed file and a missing one), extract the second over the first, and say what is true of the merged folder today.

Where the behaviour is a gap, the test states what happens NOW and names the gap in a comment ("GAP issue 746"), so a later
fix makes that line fail and the line is then turned round. Row 760 closed the gap for a partly overwritten .app: clark now
checks its files against clark-release.json on start and refuses a mixed folder (src/clark/same_version.py); those tests pin
the refusal. Nothing here changes a guarded file. Finder's own Archive Utility
puts a second unzip in "clark 2" instead of merging; the merge is `unzip -o`, `ditto -x -k`, or a copy of one folder over another.
Run: python3 dev/run_tests.py test_unzip_merge
"""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from _paths import ROOT
import package
from clark import release_files, same_version, updates

BASH, UNZIP, DITTO = shutil.which("bash"), shutil.which("unzip"), shutil.which("ditto")
PY3 = shutil.which("python3")
MAC = sys.platform == "darwin"
OLDV = "0.8.1"
TOP = release_files.TOP
VISIBLE = ["README.md", "START-HERE.txt", "clark-release.json", "clark.command", "docker"]
# What only the older version has (a file the newer one dropped, and a whole folder), and one file both have, differently.
OLD_ONLY = {".app/src/clark/old_report_helper.py": b"HELPER = 'only in the older version'\n",
            ".app/vendor/old_lib/__init__.py": b"OLD_LIB = 1\n",
            "docker/old-compose-notes.txt": b"older notes\n"}
PERSONS = {"system/branding/tokens.css": b":root { --merge-brand: 746; }\n", "data/clark.db": b"made-up database bytes"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_zip(path):
    """{name below the top folder: (bytes, mode)} of a zip."""
    out = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            if not info.is_dir():
                out[info.filename.split("/", 1)[1]] = (z.read(info), (info.external_attr >> 16) & 0o777)
    return out


def write_release(path, files, version, base_manifest):
    """A zip of {name below clark/: (bytes, mode)} with a clark-release.json written from exactly those files."""
    files = {n: v for n, v in files.items() if n != package.MANIFEST}
    doc = dict(base_manifest, version=version,
               files={n: {"sha256": sha(d), "size": len(d), "mode": format(m, "o")} for n, (d, m) in sorted(files.items())})
    files[package.MANIFEST] = ((json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8"), 0o644)
    with zipfile.ZipFile(path, "w") as z:
        for name in sorted(files):
            data, mode = files[name]
            z.writestr(package.entry(f"{TOP}/{name}", mode), data)
    return doc


def extract_over(zip_path, into, how):
    """Extract a download into `into` the way a person's tool does: files that exist are overwritten, others are added."""
    into = Path(into)
    if how == "unzip -o":
        subprocess.run([UNZIP, "-q", "-o", str(zip_path), "-d", str(into)], check=True, timeout=120)
    elif how == "unzip -n":                         # "never overwrite": a tool that keeps what is there
        subprocess.run([UNZIP, "-q", "-n", str(zip_path), "-d", str(into)], check=True, timeout=120)
    elif how == "ditto":
        subprocess.run([DITTO, "-x", "-k", str(zip_path), str(into)], check=True, timeout=120)
    else:                                           # "overwrite": what a merging copy does, in Python
        with zipfile.ZipFile(zip_path) as z:
            for info in z.infolist():
                dest = into / info.filename
                if info.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    dest.unlink()
                dest.write_bytes(z.read(info))
                dest.chmod((info.external_attr >> 16) & 0o777)


METHODS = ["overwrite"] + (["unzip -o"] if UNZIP else []) + (["ditto"] if DITTO else [])


def tree(folder):
    """{name: bytes} of every file under `folder`, "/" names, links not followed."""
    base = Path(folder)
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in base.rglob("*") if p.is_file() and not p.is_symlink()}


def clean_env(home):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "CLARK_PORT", "CLARK_DATA_DIR")}
    env.update(HOME=str(home), PYTHONDONTWRITEBYTECODE="1")
    return env


def running(folder, home):
    """What `import clark` finds when python starts in `folder` the way clark.command starts it: the current folder first (as
    `python3 -m` does), .app on PYTHONPATH. Returns (version, file the package came from)."""
    env = clean_env(home)
    if (Path(folder) / ".app").is_dir():
        env["PYTHONPATH"] = str(Path(folder) / ".app")
    code = "from clark.__main__ import prepare; prepare(); import clark; print(clark.__version__); print(clark.__file__)"
    done = subprocess.run([PY3, "-c", code], cwd=str(folder), env=env, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    version, where = done.stdout.splitlines()
    return version, Path(where)


REFUSAL = ("These clark files are not all from the same version, so clark will not start. "
           "Move the clark folder aside (rename it) and unzip the download again.")


def start_demo(folder, home):
    """Run the real start (`python3 -m clark`, as clark.command does) in `folder`. --demo is used so that no data folder, and on
    Linux no OneDrive finder, is needed. Returns (exit code, stdout, stderr, whether anything listened on its port after)."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = clean_env(home)
    if (Path(folder) / ".app").is_dir():
        env["PYTHONPATH"] = str(Path(folder) / ".app")
    done = subprocess.run([PY3, "-m", "clark", "--demo", "--port", str(port)], cwd=str(folder), env=env, capture_output=True,
                          text=True, timeout=60, stdin=subprocess.DEVNULL)
    with socket.socket() as probe:
        probe.settimeout(0.5)
        listening = probe.connect_ex(("127.0.0.1", port)) == 0
    return done.returncode, done.stdout, done.stderr, listening


@unittest.skipUnless(PY3, "needs python3")
class Merge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark merge ")).resolve()
        cls.new_zip = package.build("mac", cls.tmp / "dist", dirty=True)
        cls.new = read_zip(cls.new_zip)
        cls.new_manifest = json.loads(cls.new[package.MANIFEST][0])
        cls.newv = cls.new_manifest["version"]
        base = {k: v for k, v in cls.new_manifest.items() if k not in ("files", "version")}
        # The older placed release: lower version, a changed file, a file the newer one has added, and OLD_ONLY.
        old = dict(cls.new)
        init = ".app/src/clark/__init__.py"
        old[init] = (old[init][0].replace(cls.newv.encode(), OLDV.encode()), 0o644)
        old["README.md"] = (b"the older readme\n", 0o644)
        added = [n for n in sorted(old) if n.startswith(".app/src/clark/") and n.endswith(".py") and n != init][0]
        cls.added_in_new = added
        del old[added]
        old.update({n: (d, 0o644) for n, d in OLD_ONLY.items()})
        cls.old_zip = cls.tmp / f"clark-{OLDV}-mac.zip"
        write_release(cls.old_zip, old, OLDV, base)
        cls.old = read_zip(cls.old_zip)
        # The older release as it was built before issue 694: program files flat at the top, a stand-in clark/ beside them.
        flat = {release_files.unplace(n): v for n, v in old.items()}
        flat["clark/__init__.py"] = (b"import sys\nsys.dont_write_bytecode = True\n", 0o644)
        for stand_in in ("__main__.py", "launch.py", "doctor.py"):
            flat["clark/" + stand_in] = (cls.new[".app/clark/" + stand_in][0], 0o644)
        cls.flat_zip = cls.tmp / f"flat-{OLDV}-mac.zip"
        write_release(cls.flat_zip, flat, OLDV, base)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def install_old_then_new(self, how, name="merged"):
        where = Path(tempfile.mkdtemp(prefix=name + " ", dir=str(self.tmp)))
        extract_over(self.old_zip, where, "overwrite")
        folder = where / TOP
        for rel, data in PERSONS.items():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_bytes(data)
        extract_over(self.new_zip, where, how)
        return where, folder

    def leftovers(self, folder):
        return sorted(n for n in tree(folder) if n not in self.new and n not in PERSONS)

    def test_the_two_releases_differ_in_the_ways_the_tests_rely_on(self):
        self.assertNotEqual(self.newv, OLDV)
        self.assertEqual(sorted(OLD_ONLY), sorted(n for n in self.old if n not in self.new))
        self.assertIn(self.added_in_new, self.new)
        self.assertNotIn(self.added_in_new, self.old)
        self.assertNotEqual(self.old["README.md"], self.new["README.md"])

    def test_after_the_merge_the_older_versions_other_files_stay_and_everything_else_is_the_newer(self):
        for how in METHODS:
            with self.subTest(how=how):
                _, folder = self.install_old_then_new(how)
                on_disk = tree(folder)
                self.assertEqual(sorted(OLD_ONLY), self.leftovers(folder))       # exactly the older version's extras stay
                for rel, (data, _) in self.new.items():
                    self.assertEqual(data, on_disk[rel], f"{rel} is the newer version's bytes")
                self.assertEqual(self.newv, json.loads(on_disk[package.MANIFEST])["version"])
                self.assertEqual(sorted(VISIBLE + [".app", "system", "data"]), sorted(os.listdir(folder)))
                self.assertTrue(os.access(folder / "clark.command", os.X_OK), "clark.command stays runnable")

    def test_the_new_version_is_what_starts_when_the_older_one_was_the_same_shape(self):
        for how in METHODS:
            with self.subTest(how=how):
                where, folder = self.install_old_then_new(how)
                version, came_from = running(folder, where)
                self.assertEqual(self.newv, version)
                self.assertEqual((folder / ".app" / "src" / "clark" / "__init__.py").resolve(), came_from.resolve())

    def test_a_complete_merge_passes_the_start_check_and_the_older_versions_extras_are_ignored(self):
        # Row 760, on purpose: a file only the older version had is not in the newer record, so it is ignored. A complete
        # unzip -o passes; the check catches a folder that was only partly overwritten (the next tests).
        for how in METHODS:
            with self.subTest(how=how):
                _, folder = self.install_old_then_new(how)
                self.assertEqual(sorted(OLD_ONLY), self.leftovers(folder))
                self.assertFalse(same_version._mixed(folder / ".app"))

    def test_the_persons_system_and_data_are_untouched_and_the_zips_hold_neither(self):
        for how in METHODS:
            with self.subTest(how=how):
                _, folder = self.install_old_then_new(how)
                for rel, data in PERSONS.items():
                    self.assertEqual(data, (folder / rel).read_bytes())
        for z in (self.old_zip, self.new_zip, self.flat_zip):
            with zipfile.ZipFile(z) as zf:
                self.assertEqual([], [n for n in zf.namelist() if n.split("/")[1:2] in (["system"], ["data"])])

    def test_the_updater_takes_the_merged_folder_as_a_clark_folder_and_sees_no_difference_in_the_newer_files(self):
        _, folder = self.install_old_then_new("overwrite")
        updates.check_app_folder(folder)                    # no refusal: it has a record and no links
        plan = updates.plan(SimpleNamespace(files=self.new_manifest["files"]), folder)
        self.assertEqual(([], [], []), (plan.added, plan.replaced, plan.by_hand))     # the folder equals the newer release...
        # GAP issue 746: ...except that the older version's extras are now "left", the person's own, and no later update will
        # remove them: the newer record never listed them, and the older record that did is gone.
        self.assertEqual(sorted(OLD_ONLY), plan.left)
        self.assertEqual([], plan.removed)

    def test_a_third_release_that_drops_a_newer_file_removes_it_but_never_the_older_versions_extras(self):
        _, folder = self.install_old_then_new("overwrite")
        files = dict(self.new_manifest["files"])
        del files[self.added_in_new]
        plan = updates.plan(SimpleNamespace(files=files), folder)
        self.assertEqual([self.added_in_new], plan.removed)
        self.assertEqual(sorted(OLD_ONLY), plan.left)       # GAP issue 746: stale files of the older version stay for good

    @unittest.skipUnless(UNZIP, "needs unzip -n")
    def test_a_tool_that_keeps_existing_files_leaves_the_older_version_whole_and_consistent(self):
        where, folder = self.install_old_then_new("unzip -n")
        # unzip -n skips every name that exists, the record too: the record on disk is the older one, so the folder matches it.
        self.assertEqual(self.old["README.md"][0], (folder / "README.md").read_bytes())
        self.assertEqual(OLDV, json.loads((folder / package.MANIFEST).read_text(encoding="utf-8"))["version"])
        version, _ = running(folder, where)
        self.assertEqual(OLDV, version)
        plan = updates.plan(SimpleNamespace(files=self.new_manifest["files"]), folder)
        self.assertIn("README.md", plan.replaced)           # the updater would replace the stale file at the next update
        self.assertEqual([], plan.by_hand)                  # and the folder matches its own (older) record

    def test_a_mixed_tree_whose_record_is_the_newer_one_is_refused_by_the_start_and_the_updater_names_the_stale_file(self):
        where, folder = self.install_old_then_new("overwrite")
        stale = ".app/src/clark/__init__.py"
        (folder / stale).write_bytes(self.old[stale][0])    # one file stayed the older version's
        # Row 760 (was GAP issue 746): the start checks the files against clark-release.json and refuses.
        code, out, err, listening = start_demo(folder, where)
        self.assertEqual(1, code, (out, err))
        self.assertEqual(REFUSAL + "\n", err)
        self.assertFalse(listening, "no server was started")
        plan = updates.plan(SimpleNamespace(files=self.new_manifest["files"]), folder)
        self.assertEqual([stale], plan.replaced)
        self.assertEqual([stale], plan.by_hand)             # the updater names it too

    @unittest.skipUnless(UNZIP, "needs unzip")
    def test_two_real_zips_unzipped_over_each_other_with_the_newer_record_missing_are_refused(self):
        """The mixed folder as unzip -o leaves it when it stops early: the older release is in place, then the newer one is
        unzipped over it, every file but the record (the newer record was not written). Built with the real tool, not by hand."""
        where = Path(tempfile.mkdtemp(prefix="stopped ", dir=str(self.tmp)))
        extract_over(self.old_zip, where, "unzip -o")
        subprocess.run([UNZIP, "-q", "-o", str(self.new_zip), "-x", f"{TOP}/{package.MANIFEST}", "-d", str(where)],
                       check=True, timeout=120)
        folder = where / TOP
        self.assertEqual(OLDV, json.loads((folder / package.MANIFEST).read_text(encoding="utf-8"))["version"])
        self.assertEqual(self.new[".app/src/clark/__init__.py"][0], (folder / ".app/src/clark/__init__.py").read_bytes())
        code, out, err, listening = start_demo(folder, where)
        self.assertEqual(1, code, (out, err))
        self.assertEqual(REFUSAL + "\n", err)
        self.assertFalse(listening)

    @unittest.skipUnless(UNZIP, "needs unzip")
    def test_two_real_zips_where_the_newer_unzip_stopped_after_the_record_are_refused(self):
        """The other order: the newer record is in, but part of the newer files are not (unzip -o of only .app/vendor)."""
        where = Path(tempfile.mkdtemp(prefix="halfway ", dir=str(self.tmp)))
        extract_over(self.old_zip, where, "unzip -o")
        subprocess.run([UNZIP, "-q", "-o", str(self.new_zip), f"{TOP}/{package.MANIFEST}", f"{TOP}/.app/vendor/*", "-d", str(where)],
                       check=True, timeout=120)
        folder = where / TOP
        self.assertEqual(self.newv, json.loads((folder / package.MANIFEST).read_text(encoding="utf-8"))["version"])
        code, out, err, listening = start_demo(folder, where)
        self.assertEqual(1, code, (out, err))
        self.assertEqual(REFUSAL + "\n", err)
        self.assertFalse(listening)

    def test_the_start_path_now_reads_the_record(self):
        """Was test_nothing_in_the_start_path_reads_the_record (the reason for the GAP). Row 760: the check reads the record, and
        both the launcher and the stand-ins call it, so a fix that drops it shows here."""
        self.assertIn("clark-release.json", (ROOT / "src/clark/same_version.py").read_text(encoding="utf-8"))
        for name in ("src/clark/launch.py", "src/clark/__main__.py", "clark/launch.py", "clark/__main__.py", "clark/doctor.py"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertTrue("same_version" in text or "mixed(" in text, name)

    def test_an_older_flat_folder_merged_under_the_new_download_starts_the_older_version(self):
        where = Path(tempfile.mkdtemp(prefix="flat ", dir=str(self.tmp)))
        extract_over(self.flat_zip, where, "overwrite")
        folder = where / TOP
        for rel, data in PERSONS.items():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_bytes(data)
        extract_over(self.new_zip, where, "overwrite")
        self.assertTrue((folder / ".app").is_dir() and (folder / "src").is_dir(), "both shapes are now in one folder")
        version, came_from = running(folder, where)
        # GAP issue 746, STILL OPEN after row 760: the older stand-in clark/ at the top of the folder is found first (the current
        # folder leads sys.path for `python3 -m`), so the older flat src/ starts and the new .app is never used; nothing says so.
        # The check lives in the newer files, and with a really old stand-in none of them runs, so it cannot catch this. (This
        # fixture's flat zip carries the NEWER stand-ins, so running() here only does prepare(); a real start refuses, next test.)
        self.assertEqual(OLDV, version)
        self.assertEqual((folder / "src" / "clark" / "__init__.py").resolve(), came_from.resolve())
        updates.check_app_folder(folder)                    # and the updater still takes the folder
        plan = updates.plan(SimpleNamespace(files=self.new_manifest["files"]), folder)
        self.assertIn("src/clark/__init__.py", plan.left)   # the older flat files are listed as the person's own
        for rel, data in PERSONS.items():
            self.assertEqual(data, (folder / rel).read_bytes())

    @unittest.skipUnless(BASH, "needs bash")
    def test_the_flat_plus_app_folder_is_refused_by_clark_command_before_python_starts(self):
        """Row 760 (the GAP above): .app with src beside it is refused by the bash launcher, whichever stand-in is there."""
        where = Path(tempfile.mkdtemp(prefix="flat2 ", dir=str(self.tmp)))
        extract_over(self.flat_zip, where, "overwrite")
        extract_over(self.new_zip, where, "overwrite")
        stub = self.tmp / "stub-bin"
        stub.mkdir(exist_ok=True)
        (stub / "python3").write_text("#!/bin/sh\necho STUB-PYTHON-RAN >&2\nexit 0\n", encoding="utf-8")
        (stub / "python3").chmod(0o755)
        for args in ([], ["--check"]):
            with self.subTest(args=args):
                env = clean_env(where)
                env["PATH"] = str(stub) + os.pathsep + env["PATH"]
                done = subprocess.run([BASH, str(where / TOP / "clark.command")] + args, cwd=str(where), env=env,
                                      stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
                self.assertEqual(1, done.returncode, (done.stdout, done.stderr))
                self.assertEqual(REFUSAL + "\n", done.stderr)       # and the stub python (which would say so) never ran

    def run_check(self, where, folder, data):
        done = subprocess.run([BASH, str(folder / "clark.command"), "--check", "--data", str(data), "--port", "1"],
                              cwd=str(where), env=clean_env(where), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              timeout=120)
        self.assertNotIn("Traceback", done.stdout + done.stderr)
        return done

    @unittest.skipUnless(BASH, "needs bash")
    def test_clark_command_does_not_put_a_set_aside_folder_back_over_the_merged_app(self):
        """The recovery in clark.command only puts back a MISSING .app. After a merge .app is there, so a set-aside folder that
        an old update marker names is left where it is. (--check runs the doctor and exits.)"""
        where, folder = self.install_old_then_new("overwrite")
        data = where / "data folder"
        (data / "updates").mkdir(parents=True)
        (data / "updates" / ".installing.json").write_text(json.dumps({"stamp": "20261101T120000Z"}), encoding="utf-8")
        aside = folder / ".clark-old-20261101T120000Z" / ".app"
        aside.mkdir(parents=True)
        (aside / "marker.txt").write_text("the set-aside older program", encoding="utf-8")
        before = tree(folder / ".app")
        self.run_check(where, folder, data)
        self.assertEqual(before, tree(folder / ".app"))
        self.assertTrue((aside / "marker.txt").is_file(), "the set-aside folder was not moved over the new .app")
        for rel, body in PERSONS.items():
            self.assertEqual(body, (folder / rel).read_bytes())

    @unittest.skipUnless(BASH, "needs bash")
    def test_clark_command_puts_back_a_missing_app_only_from_the_stamp_the_marker_names(self):
        where, folder = self.install_old_then_new("overwrite")
        shutil.rmtree(folder / ".app")                      # as if an update stopped between its two moves
        data = where / "data folder"
        (data / "updates").mkdir(parents=True)
        (data / "updates" / ".installing.json").write_text(json.dumps({"stamp": "20261101T120000Z"}), encoding="utf-8")
        for stamp, text in (("20261101T120000Z", "named"), ("20260101T000000Z", "older leftover")):
            (folder / f".clark-old-{stamp}" / ".app").mkdir(parents=True)
            (folder / f".clark-old-{stamp}" / ".app" / "which.txt").write_text(text, encoding="utf-8")
        self.run_check(where, folder, data)
        self.assertEqual("named", (folder / ".app" / "which.txt").read_text(encoding="utf-8"))

    @unittest.skipUnless(BASH and UNZIP, "needs bash and unzip")
    def test_check_refuses_the_mixed_folder_too_instead_of_saying_ready(self):
        where = Path(tempfile.mkdtemp(prefix="doctor ", dir=str(self.tmp)))
        extract_over(self.old_zip, where, "unzip -o")
        subprocess.run([UNZIP, "-q", "-o", str(self.new_zip), "-x", f"{TOP}/{package.MANIFEST}", "-d", str(where)],
                       check=True, timeout=120)
        done = self.run_check(where, where / TOP, where / "d")
        self.assertEqual(1, done.returncode, (done.stdout, done.stderr))
        self.assertEqual(REFUSAL + "\n", done.stderr)
        self.assertNotIn("Ready", done.stdout)

    @unittest.skipUnless(MAC and BASH, "the real start through clark.command and the doctor's own checks are the Mac's; run it on "
                                       "a Mac before a release")
    def test_check_runs_the_doctor_on_the_merged_folder(self):
        where, folder = self.install_old_then_new("overwrite")
        done = self.run_check(where, folder, where / "d")
        self.assertIn("Checking what clark needs on this computer...", done.stdout)


if __name__ == "__main__":
    unittest.main()

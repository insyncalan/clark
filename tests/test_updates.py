"""Checking an update file and planning an install (#109, steps 1 and 2): src/clark/updates.py.

Every refusal has a test pinned to its exact sentence. Builds fake downloads in temporary folders; reads only, no network.
Run: python3 dev/run_tests.py test_updates
"""
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
import unittest
import zipfile
from pathlib import Path

from _paths import ROOT
import package
from clark import release_files, updates
from clark.updates import UpdateError

SYSTEM = "mac"


def listed_files(version="0.3.1"):
    """One small file for every item in the list, as a download holds them: {name without the top folder: bytes}."""
    files = {}
    for item in release_files.listed(SYSTEM):
        files[item + "x.py" if item.endswith("/") else item] = f"# fictional {item}\n".encode()
    files["src/clark/__init__.py"] = f'__version__ = "{version}"\n'.encode()
    files["START-HERE.txt"] = b"Getting started.\n"
    return files


def make_zip(folder, version="0.3.1", files=None, manifest=None, system=SYSTEM, name=None, top=None, tweak=None,
             modes=None, schema=2, min_from="0.0.0", notes="Fixes a typo.\n", extra=None, skip_manifest=False, rows=None):
    """Write a fake download into `folder`; its path. `tweak(files)` changes the member bytes AFTER the manifest has been
    made (so a hash then differs); `extra` adds raw members (name -> bytes); `rows(files_doc)` changes the manifest rows."""
    files = dict(listed_files(version) if files is None else files)
    modes = modes or {}
    doc = {"product": "clark", "version": version, "system": system, "released": "2026-10-27", "notes": notes,
           "schema_version": schema, "min_from": min_from,
           "files": {rel: {"sha256": hashlib.sha256(b).hexdigest(), "size": len(b),
                           "mode": "755" if rel in release_files.RUN_BIT else "644"} for rel, b in files.items()}}
    if rows:
        rows(doc["files"])
    if manifest:
        manifest(doc)
    if tweak:
        tweak(files)
    top = top or f"clark-{version}"
    name = name or f"clark-{version}-{system}.zip"
    path = Path(folder) / name
    with zipfile.ZipFile(path, "w") as z:
        def put(member, data, mode=0o100644, create_system=3):
            info = zipfile.ZipInfo(member, date_time=(2000, 1, 1, 0, 0, 0))
            info.create_system = create_system
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
        for rel in sorted(files):
            default = 0o100755 if rel in release_files.RUN_BIT else 0o100644
            put(f"{top}/{rel}", files[rel], modes.get(rel, default))
        for member, data in (extra or {}).items():
            put(member, data)
        if not skip_manifest:
            put(f"{top}/{updates.MANIFEST}", (json.dumps(doc, indent=2) + "\n").encode())
    return path


def real_download(case, schema=2):
    """A download built by package.py itself from a tiny repo (so its manifest is the real one), version 0.3.1."""
    import subprocess
    from unittest import mock
    root = Path(tempfile.mkdtemp(prefix="clark repo "))
    case.addCleanup(shutil.rmtree, root, True)
    for rel, text in {"README.md": "A fictional readme.\n", "src/clark/__init__.py": '__version__ = "0.3.1"\n',
                      "src/clark/store.py": f"SCHEMA_VERSION = {schema}\n", "clark.command": "#!/bin/bash\n"}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    small = ("README.md", "src/clark/")
    for patch in (mock.patch.object(package, "SHARED", small), mock.patch.object(release_files, "SHARED", small)):
        patch.start()           # the small list stays the list while the test reads the download back
        case.addCleanup(patch.stop)
    return package.build("mac", Path(case.tmp) / "out", root=root, dirty=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="clark updates ")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def read(self, path, installed="0.3.0", schema=2, **kw):
        return updates.read_release(path, SYSTEM, installed, schema, **kw)

    def refuses(self, path, key, sentence=None, **kw):
        with self.assertRaises(UpdateError) as said:
            self.read(path, **kw)
        self.assertEqual(key, said.exception.key, said.exception.detail)
        if sentence is not None:
            self.assertEqual(sentence, said.exception.message)
        return said.exception


class GoodFileTest(Base):
    def test_a_good_update_reads(self):
        r = self.read(make_zip(self.tmp))
        self.assertEqual(("0.3.1", "mac", "2026-10-27", "Fixes a typo.\n", 2), (r.version, r.system, r.released, r.notes, r.schema_version))
        self.assertIn("src/clark/__init__.py", r.files)

    def test_a_download_built_by_package_py_reads(self):
        built = real_download(self)
        r = updates.read_release(built, "mac", "0.3.0", 2)
        self.assertEqual("0.3.1", r.version)
        self.assertEqual("755", r.files["clark.command"]["mode"])

    def test_a_browsers_copy_suffix_is_accepted_for_a_chosen_file_only(self):
        path = make_zip(self.tmp, name="clark-0.3.1-mac (1).zip")
        self.assertEqual("0.3.1", self.read(path, chosen=True).version)
        self.refuses(path, "name")

    def test_the_latest_of_many_is_found_by_version_not_by_text(self):
        for v in ("0.9.0", "0.10.0", "0.2.0"):
            make_zip(self.tmp, version=v)
        (Path(self.tmp) / "clark-0.99.0-windows.zip").write_bytes(b"x")
        (Path(self.tmp) / "clark-1.0.0.zip").write_bytes(b"x")
        (Path(self.tmp) / "clark-0.3.1-mac (1).zip").write_bytes(b"x")
        self.assertEqual("clark-0.10.0-mac.zip", updates.newest_in(self.tmp, "mac").name)
        self.assertIsNone(updates.newest_in(Path(self.tmp) / "nowhere", "mac"))

    def test_newest_in_ignores_a_folder_or_link_with_the_name(self):
        (Path(self.tmp) / "clark-5.0.0-mac.zip").mkdir()
        os.symlink(make_zip(self.tmp, version="0.2.0"), Path(self.tmp) / "clark-7.0.0-mac.zip")
        self.assertEqual("clark-0.2.0-mac.zip", updates.newest_in(self.tmp, "mac").name)


class NameTest(Base):
    def test_wrong_names(self):
        for name in ("update.zip", "clark-1.2-mac.zip", "clark-1.2.3-mac.zip.zip", "clark-01.2.3-mac.zip", "clark-1.2.3-mac.tar",
                     "clark-1.2.3-beos.zip", "CLARK-1.2.3-mac.zip", "clark-\u0661.2.3-mac.zip", "clark-1.2.3-mac (1).zip"):
            with self.subTest(name=name):
                path = Path(self.tmp) / name
                path.write_bytes(b"x")
                e = self.refuses(path, "name")
                self.assertEqual("That isn't a clark update. Choose the update file from the clark releases page. "
                                 "Its name looks like clark-1.2.3-mac.", e.message)

    def test_githubs_source_zip_by_name(self):
        path = Path(self.tmp) / "clark-0.3.1.zip"
        path.write_bytes(b"x")
        self.refuses(path, "source", "That is the whole source code, not an update. On the releases page, download the file "
                                    "under Assets whose name ends in -mac.")

    def test_a_renamed_source_zip_has_no_manifest(self):
        path = make_zip(self.tmp, skip_manifest=True, top="clark-0.3.1")
        self.refuses(path, "source")

    def test_wrong_system_by_name_and_by_manifest(self):
        path = make_zip(self.tmp, system="windows")
        self.refuses(path, "system", "This update is for Windows. Download the one for Mac from the clark releases page.")
        path = make_zip(self.tmp, name="clark-0.3.1-mac.zip", system="linux")
        self.refuses(path, "system", "This update is for Linux. Download the one for Mac from the clark releases page.")

    def test_not_a_file_a_link_or_missing(self):
        real = make_zip(self.tmp)
        link = Path(self.tmp) / "clark-0.4.0-mac.zip"
        os.symlink(real, link)
        self.refuses(link, "unreadable")
        self.refuses(Path(self.tmp) / "clark-0.5.0-mac.zip", "unreadable")
        folder = Path(self.tmp) / "clark-0.6.0-mac.zip"
        folder.mkdir()
        self.refuses(folder, "unreadable")

    def test_not_a_zip_and_too_big(self):
        path = Path(self.tmp) / "clark-0.3.1-mac.zip"
        path.write_bytes(b"this is not a zip")
        self.refuses(path, "damaged", "This update file is damaged or has been changed. Download it again.")
        self.refuses(make_zip(self.tmp, version="0.3.2"), "damaged", max_zip=100)


class ManifestTest(Base):
    def test_wrong_product(self):
        self.refuses(make_zip(self.tmp, manifest=lambda d: d.update(product="other")), "name")

    def test_bad_versions_and_fields(self):
        for change in (lambda d: d.update(version="0.3"), lambda d: d.update(version="0.3.1.dev1"),
                       lambda d: d.update(min_from="x"), lambda d: d.update(released="27-10-2026"),
                       lambda d: d.update(schema_version="2"), lambda d: d.update(schema_version=True),
                       lambda d: d.update(files=[]), lambda d: d.pop("notes"), lambda d: d.update(system=5)):
            with self.subTest(change=change):
                shutil.rmtree(self.tmp)
                os.mkdir(self.tmp)
                self.refuses(make_zip(self.tmp, manifest=change), "damaged")

    def test_bad_rows(self):
        for change in (lambda r: r["README.md"].update(sha256="abc"), lambda r: r["README.md"].update(size=-1),
                       lambda r: r["README.md"].update(mode="600"), lambda r: r.update({"x": "y"})):
            with self.subTest(change=change):
                shutil.rmtree(self.tmp)
                os.mkdir(self.tmp)
                self.refuses(make_zip(self.tmp, rows=change), "damaged")

    def test_manifest_not_json(self):
        path = make_zip(self.tmp)
        shutil.copy(path, Path(self.tmp) / "keep.bin")
        with zipfile.ZipFile(path) as old, zipfile.ZipFile(Path(self.tmp) / "new.zip", "w") as new:
            for i in old.infolist():
                new.writestr(i, b"{not json" if i.filename.endswith(updates.MANIFEST) else old.read(i))
        os.replace(Path(self.tmp) / "new.zip", path)
        self.refuses(path, "damaged")

    def test_top_folder_name_and_version_must_agree(self):
        self.refuses(make_zip(self.tmp, top="clark-0.3.0"), "damaged")
        self.refuses(make_zip(self.tmp, version="0.3.2", name="clark-0.3.1-mac.zip"), "damaged")
        self.refuses(make_zip(self.tmp, version="0.3.3", top="clarks"), "damaged")

    def test_version_inside_the_files_must_match(self):
        files = listed_files()
        files["src/clark/__init__.py"] = b'__version__ = "0.3.9"\n'
        self.refuses(make_zip(self.tmp, files=files), "damaged")


class MemberTest(Base):
    def refuses_with(self, extra, key, **kw):
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        return self.refuses(make_zip(self.tmp, **kw, extra=extra), key)

    def test_missing_file_and_missing_folder(self):
        files = listed_files()
        del files["README.md"]
        self.refuses(make_zip(self.tmp, files=files), "incomplete", "This update file is incomplete. Download it again.")
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        files = listed_files()
        del files["vendor/openpyxl/x.py"]
        self.refuses(make_zip(self.tmp, files=files), "incomplete")
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        files = listed_files()
        del files["START-HERE.txt"]
        self.refuses(make_zip(self.tmp, files=files), "incomplete")

    def test_extra_file_outside_the_list_is_unsafe(self):
        files = listed_files()
        files["tests/test_x.py"] = b"x"
        self.refuses(make_zip(self.tmp, files=files), "unsafe",
                     "This update would change things outside clark's own files, so it wasn't installed. "
                     "Download it again from the clark releases page.")

    def test_manifest_lists_something_the_zip_lacks_or_the_reverse(self):
        self.refuses(make_zip(self.tmp, rows=lambda r: r.update({"src/clark/ghost.py": dict(r["README.md"])})), "incomplete")
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.refuses(make_zip(self.tmp, rows=lambda r: r.pop("src/clark/x.py")), "incomplete")

    def test_unsafe_paths_one_by_one(self):
        bad = {
            "dotdot": "src/../../evil.py", "dot": "src/./a.py", "empty part": "src//a.py", "backslash": "src\\a.py",
            "drive": "C:/evil.py", "colon": "src/a:b.py", "trailing dot": "src/a.py.", "trailing space": "src/a.py ",
            "reserved": "src/con.txt", "reserved com": "src/COM1", "reserved spaced": "src/nul .x", "reserved sup": "src/LPT\u00b2.txt",
            "question mark": "src/a?.py", "star": "src/a*.py", "quote": 'src/a".py', "pipe": "src/a|.py", "lt": "src/a<.py",
            "control": "src/a\x01.py", "delete": "src/a\x7f.py", "long part": "src/" + "a" * 256,
            "not NFC": "src/clark/e" + "\u0301.py", "absolute": "/etc/passwd",
        }
        for label, member in bad.items():
            with self.subTest(label=label):
                shutil.rmtree(self.tmp)
                os.mkdir(self.tmp)
                top_member = member if member.startswith("/") else f"clark-0.3.1/{member}"
                e = self.refuses(make_zip(self.tmp, extra={top_member: b"x"}), "unsafe")
                self.assertNotIn("zip", e.message.lower())

    def test_a_member_outside_the_one_top_folder(self):
        self.refuses(make_zip(self.tmp, extra={"other/evil.py": b"x"}), "unsafe")

    def test_path_problem_directly(self):
        self.assertIsNone(updates.path_problem("src/clark/page/page.html"))
        self.assertIsNone(updates.path_problem("vendor/fonts/Inter 400.woff2"))
        for bad in ("", "a/../b", "/a", "a\\b", "C:x", "a/b:c", "a./b", "a/CON.x/b", "a/\u0663\u0000"):
            with self.subTest(bad=bad):
                self.assertIsNotNone(updates.path_problem(bad))

    def test_case_and_accent_collisions(self):
        a = "src/clark/Café.py"
        b = unicodedata.normalize("NFC", "src/clark/CAFÉ.py")
        self.assertNotEqual(a, b)
        self.assertEqual(sorted([a, b]), updates.collisions([a, b]))
        self.assertEqual(["src/Clark/a.py", "src/clark/A.py"], updates.collisions(["src/clark/A.py", "src/Clark/a.py"]))
        self.assertEqual([], updates.collisions(["src/clark/a.py", "src/clark/b.py"]))
        self.assertEqual(["Src"], updates.collisions(["Src", "src/a.py"]))      # a file beside a folder of the same name

    def test_a_clash_in_a_download_is_unsafe(self):
        files = listed_files()
        files["src/clark/Readme.txt"] = b"a"
        files["src/clark/README.txt"] = b"b"
        self.refuses(make_zip(self.tmp, files=files), "unsafe")
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        files = listed_files()
        files["src/clark/Thing"] = b"a"
        files["src/clark/thing/x.py"] = b"b"
        self.refuses(make_zip(self.tmp, files=files), "unsafe")

    def test_link_member_encrypted_dir_duplicate_and_odd_modes(self):
        self.refuses(make_zip(self.tmp, modes={"README.md": 0o120777}), "unsafe")
        for label, modes in (("setuid", {"README.md": 0o104755}), ("group write", {"README.md": 0o100664}),
                             ("device", {"README.md": 0o060644})):
            with self.subTest(label=label):
                shutil.rmtree(self.tmp)
                os.mkdir(self.tmp)
                self.refuses(make_zip(self.tmp, modes=modes), "damaged")

    def test_dir_duplicate_encrypted_and_non_unix_members(self):
        base = make_zip(self.tmp)

        def rewrite(change):
            out = Path(self.tmp) / "clark-0.3.1-mac.zip"
            data = Path(self.tmp) / "src.zip"
            shutil.copy(base, data)
            with zipfile.ZipFile(data) as old, zipfile.ZipFile(out, "w") as new:
                change(old, new)
            os.remove(data)
            return out

        def with_dir(old, new):
            for i in old.infolist():
                new.writestr(i, old.read(i))
            d = zipfile.ZipInfo("clark-0.3.1/src/", date_time=(2000, 1, 1, 0, 0, 0))
            d.create_system = 3
            d.external_attr = (0o040755 << 16)
            new.writestr(d, b"")
        self.refuses(rewrite(with_dir), "damaged")

        def with_dup(old, new):
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for i in old.infolist():
                    new.writestr(i, old.read(i))
                first = old.infolist()[0]
                new.writestr(first, old.read(first))
        self.refuses(rewrite(with_dup), "damaged")

        def with_windows_made(old, new):
            for n, i in enumerate(old.infolist()):
                i.create_system = 0 if n == 0 else 3
                new.writestr(i, old.read(i))
        self.refuses(rewrite(with_windows_made), "damaged")

        def with_flag(old, new):
            for n, i in enumerate(old.infolist()):
                new.writestr(i, old.read(i))
                if n == 0:
                    new.filelist[-1].flag_bits |= 0x1
        self.refuses(rewrite(with_flag), "damaged")

    def test_duplicate_names_are_refused_by_our_own_check(self):
        """Newer Pythons also notice overlapping entries, older ones don't: the check must not depend on that."""
        def info(name):
            i = zipfile.ZipInfo(name)
            i.create_system, i.external_attr = 3, 0o100644 << 16
            return i
        with self.assertRaises(UpdateError) as said:
            updates._check_structure([info("clark-1.0.0/a"), info("clark-1.0.0/b"), info("clark-1.0.0/a")], 10 ** 9)
        self.assertEqual("damaged", said.exception.key)
        self.assertIn("clark-1.0.0/a", said.exception.detail)
        updates._check_structure([info("clark-1.0.0/a"), info("clark-1.0.0/b")], 10 ** 9)

    def test_odd_compression(self):
        base = make_zip(self.tmp)
        bz = Path(self.tmp) / "bz.zip"
        with zipfile.ZipFile(base) as old, zipfile.ZipFile(bz, "w", compression=zipfile.ZIP_BZIP2) as new:
            for i in old.infolist():
                j = zipfile.ZipInfo(i.filename, date_time=i.date_time)
                j.create_system, j.external_attr, j.compress_type = 3, i.external_attr, zipfile.ZIP_BZIP2
                new.writestr(j, old.read(i))
        os.replace(bz, base)
        self.refuses(base, "damaged")

    def test_total_size_cap_and_a_member_bigger_than_it_says(self):
        self.refuses(make_zip(self.tmp), "damaged", max_total=10)

        def lying(r):
            r["README.md"]["size"] = 2
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.refuses(make_zip(self.tmp, rows=lying), "damaged")

    def test_a_bad_hash_size_or_mode_is_damaged(self):
        def flip(files):
            files["README.md"] = b"changed after the hash was taken\n"
        self.refuses(make_zip(self.tmp, tweak=flip), "damaged", "This update file is damaged or has been changed. Download it again.")
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.refuses(make_zip(self.tmp, rows=lambda r: r["clark.command"].update(mode="644")), "damaged")
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.refuses(make_zip(self.tmp, rows=lambda r: r["README.md"].update(sha256="0" * 64)), "damaged")

    def test_reading_counts_against_the_declared_size(self):
        path = make_zip(self.tmp)
        with zipfile.ZipFile(path) as z:
            info = z.getinfo("clark-0.3.1/README.md")
            info.file_size = 1                              # declared smaller than the real bytes
            with self.assertRaises(UpdateError) as said:
                updates._read_counted(z, info)
        self.assertEqual("damaged", said.exception.key)


class VersionRuleTest(Base):
    def test_version_compare_is_by_numbers(self):
        self.assertGreater(updates.version_key("0.10.0"), updates.version_key("0.9.0"))
        self.assertGreater(updates.version_key("1.0.0"), updates.version_key("0.99.99"))
        self.assertGreater(updates.version_key("0.1.0"), updates.version_key("0.1.0.dev0"), "a release beats its dev copy")
        self.assertGreater(updates.version_key("0.1.0.dev3"), updates.version_key("0.0.9"))
        for bad in ("0.1", "a.b.c", "1.2.3.4", "01.2.3", "1.2.3-rc1"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                updates.version_key(bad)

    def test_older_refused(self):
        self.refuses(make_zip(self.tmp, version="0.2.0"), "older",
                     "Version 0.2.0 is older than the one you have (0.3.0). Choose Install again only if you want it anyway.")

    def test_equal_refused_unless_reinstalling(self):
        path = make_zip(self.tmp, version="0.3.0")
        self.refuses(path, "same", "Version 0.3.0 is the one you have already. Choose Install again only if you want it anyway.")
        self.assertTrue(self.read(path, reinstall=True).reinstall)

    def test_older_allowed_when_reinstalling(self):
        self.assertEqual("0.2.0", self.read(make_zip(self.tmp, version="0.2.0"), reinstall=True).version)

    def test_a_source_copy_may_update_to_its_release(self):
        self.assertEqual("0.1.0", self.read(make_zip(self.tmp, version="0.1.0"), installed="0.1.0.dev0").version)

    def test_min_from(self):
        self.refuses(make_zip(self.tmp, min_from="0.3.0"), "min_from",
                     "This update can only be installed over version 0.3.0 or newer. Install that version first, then this one.",
                     installed="0.2.0")
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.assertEqual("0.3.1", self.read(make_zip(self.tmp, min_from="0.3.0"), installed="0.3.0").version)

    def test_a_change_to_the_data_layout_is_refused_for_now(self):
        said = "This update needs a newer clark than the one you have, because it changes how your data is kept. " \
               "It can't install itself. Download it again and install it by hand. Nothing was changed."
        self.refuses(make_zip(self.tmp, schema=3), "layout", said)
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.refuses(make_zip(self.tmp, schema=1), "layout", said)
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.refuses(make_zip(self.tmp, schema=3), "layout", said, reinstall=True)
        shutil.rmtree(self.tmp)
        os.mkdir(self.tmp)
        self.assertEqual(2, self.read(make_zip(self.tmp, schema=2)).schema_version)

    def test_a_layout_change_is_refused_for_a_real_download_too(self):
        built = real_download(self, schema=3)
        with self.assertRaises(UpdateError) as said:
            updates.read_release(built, "mac", "0.3.0", 2)
        self.assertEqual("layout", said.exception.key)


def install_to(folder, version="0.3.0", files=None):
    """A fake installed app folder: the files of a download, and its record (its manifest) beside them."""
    files = listed_files(version) if files is None else files
    folder = Path(folder)
    for rel, data in files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_bytes(data)
    doc = {"product": "clark", "version": version, "files": {
        rel: {"sha256": hashlib.sha256(b).hexdigest(), "size": len(b), "mode": "644"} for rel, b in files.items()}}
    (folder / updates.INSTALLED_RECORD).write_text(json.dumps(doc), encoding="utf-8")
    return folder


class AppFolderTest(Base):
    def folder(self):
        return install_to(Path(self.tmp) / "clark-0.3.0")

    def test_a_good_folder_passes(self):
        updates.check_app_folder(self.folder())

    def test_a_git_folder_is_refused_in_plain_words(self):
        folder = self.folder()
        (folder / ".git").mkdir()
        with self.assertRaises(UpdateError) as said:
            updates.check_app_folder(folder)
        self.assertEqual("This copy of clark runs from its source code, so it can't update itself. "
                         "Download the latest release instead.", said.exception.message)
        self.assertEqual("git", said.exception.key)

    def test_a_git_file_counts_too(self):
        folder = self.folder()
        (folder / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        with self.assertRaises(UpdateError) as said:
            updates.check_app_folder(folder)
        self.assertEqual("git", said.exception.key)

    def test_git_is_checked_before_anything_else(self):
        folder = Path(self.tmp) / "empty"
        (folder / ".git").mkdir(parents=True)
        with self.assertRaises(UpdateError) as said:
            updates.check_app_folder(folder)
        self.assertEqual("git", said.exception.key, "no record AND .git says the source-code line")

    def test_no_record(self):
        folder = self.folder()
        (folder / updates.INSTALLED_RECORD).unlink()
        with self.assertRaises(UpdateError) as said:
            updates.check_app_folder(folder)
        self.assertEqual("norecord", said.exception.key)

    def test_a_link_inside(self):
        folder = self.folder()
        os.symlink(folder / "README.md", folder / "shortcut")
        with self.assertRaises(UpdateError) as said:
            updates.check_app_folder(folder)
        self.assertEqual("link", said.exception.key)
        self.assertIn("shortcut", said.exception.detail)

    def test_a_windows_junction_counts_as_a_link(self):
        folder = self.folder()
        real = os.lstat
        class St:
            def __init__(self, st): self.st = st
            def __getattr__(self, n): return getattr(self.st, n)
        def fake(path, *a, **k):
            st = real(path, *a, **k)
            if str(path).endswith("vendor"):
                s = St(st)
                s.st_file_attributes = updates.FILE_ATTRIBUTE_REPARSE_POINT
                return s
            return st
        from unittest import mock
        with mock.patch.object(updates.os, "lstat", fake), self.assertRaises(UpdateError) as said:
            updates.check_app_folder(folder)
        self.assertEqual("link", said.exception.key)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can write anywhere")
    def test_read_only_folder(self):
        folder = self.folder()
        os.chmod(folder, 0o555)
        self.addCleanup(os.chmod, folder, 0o755)
        with self.assertRaises(UpdateError) as said:
            updates.check_app_folder(folder)
        self.assertEqual("readonly", said.exception.key)

    def test_a_good_check_leaves_nothing_behind(self):
        folder = self.folder()
        before = sorted(os.listdir(folder))
        updates.check_app_folder(folder)
        self.assertEqual(before, sorted(os.listdir(folder)))


class LongPathTest(unittest.TestCase):
    def test_arithmetic_for_every_place_a_file_will_be(self):
        app = "C:\\" + "d" * 200
        rels = ["a/b.py", "x/" + "y" * 40 + ".py"]
        self.assertEqual([], updates.too_deep("/t/a", rels, limit=260))
        # in the app folder itself: len(app) + 1 + len(rel) + 1 (the NUL)
        self.assertEqual(["x/" + "y" * 40 + ".py"], updates.too_deep("/" + "d" * 200, rels, limit=260 - 4))
        # the staging folder is longer than the app folder, and is the longest place
        in_app = len(os.path.join("/" + "d" * 200, "a", "b.py")) + 1
        staging = len(os.path.join("/" + "d" * 200, ".clark-update-" + "0" * 16, "a", "b.py")) + 1
        self.assertGreater(staging, in_app)
        self.assertEqual(["a/b.py"], updates.too_deep("/" + "d" * 200, ["a/b.py"], limit=staging))
        self.assertEqual([], updates.too_deep("/" + "d" * 200, ["a/b.py"], limit=staging + 1))
        # the backup under the data folder can be the longest of all
        far = updates.too_deep("/a", ["a/b.py"], data_dir="/" + "e" * 220, limit=260)
        self.assertEqual(["a/b.py"], far)
        self.assertEqual([], updates.too_deep("/a", ["a/b.py"], data_dir="/e", limit=260))


class PlanTest(Base):
    def setUp(self):
        super().setUp()
        self.app = install_to(Path(self.tmp) / "app", "0.3.0")

    def release(self, version="0.3.1", change=None, add=None, drop=None):
        files = listed_files(version)
        if change:
            files.update(change)
        files.update(add or {})
        for d in drop or ():
            del files[d]
        shutil.rmtree(Path(self.tmp) / "zips", ignore_errors=True)
        os.mkdir(Path(self.tmp) / "zips")
        return self.read(make_zip(Path(self.tmp) / "zips", version=version, files=files))

    def test_added_replaced_removed_left(self):
        installed = listed_files("0.3.0")
        installed["src/clark/old.py"] = b"old\n"
        install_to(self.app, "0.3.0", installed)
        (self.app / "my notes.txt").write_text("mine", encoding="utf-8")
        (self.app / "src" / "clark" / "mine.py").write_text("mine", encoding="utf-8")
        r = self.release(change={"README.md": b"new readme\n"}, add={"src/clark/new.py": b"n\n"}, drop=["README.md"] and [])
        r2 = self.release(change={"README.md": b"new readme\n"}, add={"src/clark/new.py": b"n\n"})
        p = updates.plan(r2, self.app)
        self.assertEqual(["src/clark/new.py"], p.added)
        self.assertIn("README.md", p.replaced)
        self.assertIn("src/clark/__init__.py", p.replaced)
        self.assertEqual(["src/clark/old.py"], p.removed, "recorded as shipped, gone from the update")
        self.assertEqual(["my notes.txt", "src/clark/mine.py"], p.left, "the person's own files are left alone")
        self.assertNotIn("README.md", p.removed)
        self.assertIsNotNone(r)

    def test_a_file_the_person_added_is_never_removed_even_in_a_folder_the_update_owns(self):
        (self.app / "vendor" / "openpyxl" / "mine.py").write_text("mine", encoding="utf-8")
        p = updates.plan(self.release(), self.app)
        self.assertEqual([], p.removed)
        self.assertIn("vendor/openpyxl/mine.py", p.left)

    def test_before_the_first_recorded_install_nothing_is_removed(self):
        (self.app / updates.INSTALLED_RECORD).write_text(json.dumps({"files": {}}), encoding="utf-8")
        (self.app / "src" / "clark" / "stray.py").write_text("x", encoding="utf-8")
        p = updates.plan(self.release(), self.app)
        self.assertEqual([], p.removed)
        self.assertIn("src/clark/stray.py", p.left)

    def test_changed_by_hand(self):
        (self.app / "README.md").write_text("edited by hand", encoding="utf-8")
        p = updates.plan(self.release(change={"README.md": b"same as installed? no, new\n"}), self.app)
        self.assertEqual(["README.md"], p.by_hand)
        self.assertIn("README.md", p.replaced)

    def test_same_files_means_nothing_replaced(self):
        r = self.release(version="0.3.0") if False else None
        files = listed_files("0.3.0")
        shutil.rmtree(Path(self.tmp) / "zips", ignore_errors=True)
        os.mkdir(Path(self.tmp) / "zips")
        r = self.read(make_zip(Path(self.tmp) / "zips", version="0.3.0", files=files), reinstall=True)
        p = updates.plan(r, self.app)
        self.assertEqual(([], [], []), (p.added, p.replaced, p.removed))

    def test_plan_writes_nothing(self):
        def snapshot():
            return {str(p.relative_to(self.app)): (p.read_bytes(), p.stat().st_mtime_ns)
                    for p in self.app.rglob("*") if p.is_file()}
        before = snapshot()
        updates.plan(self.release(), self.app)
        updates.check_app_folder(self.app)
        self.assertEqual(before, snapshot())
        self.assertEqual([], [n for n in os.listdir(self.app) if n.startswith(".clark")])

    def test_data_and_projects_are_not_in_the_app_folder_so_not_in_the_plan(self):
        data = Path(self.tmp) / "data"
        (data / "reports").mkdir(parents=True)
        (data / "clark.db").write_bytes(b"db")
        (data / "reports" / "r.docx").write_bytes(b"r")
        p = updates.plan(self.release(), self.app)
        every = p.added + p.replaced + p.removed + p.left
        self.assertFalse([n for n in every if n.startswith(("reports", "clark.db"))])
        self.assertEqual(b"db", (data / "clark.db").read_bytes())

    def test_links_and_cache_are_skipped_in_the_walk(self):
        (self.app / "src" / "clark" / "__pycache__").mkdir()
        (self.app / "src" / "clark" / "__pycache__" / "a.pyc").write_bytes(b"x")
        (self.app / ".clark-update-20261029T120000Z").mkdir()
        (self.app / ".clark-update-20261029T120000Z" / "stray").write_bytes(b"x")
        (self.app / ".DS_Store").write_bytes(b"x")
        files, links = updates.walk_app(self.app)
        self.assertEqual([], links)
        self.assertFalse([f for f in files if "pycache" in f or f.startswith(".clark-") or f == ".DS_Store"])


class ReviewTest(Base):
    def test_review_is_plain(self):
        app = install_to(Path(self.tmp) / "app", "0.3.0")
        zips = Path(self.tmp) / "zips"
        zips.mkdir()
        files = listed_files("0.3.1")
        files["src/clark/new.py"] = b"n\n"
        r = self.read(make_zip(zips, version="0.3.1", files=files, notes="Fixes a typo.\nAdds a thing.\n"))
        text = updates.review(r, updates.plan(r, app), "0.3.0")
        self.assertEqual("Version 0.3.0 \u2192 0.3.1. Released 27-10-2026.", text["heading"])
        self.assertEqual("Fixes a typo.\nAdds a thing.\n", text["notes"])
        self.assertEqual("Added (1 file)", text["added"]["label"])
        self.assertEqual(["src/clark/new.py"], text["added"]["names"])
        self.assertEqual("Removed (0 files)", text["removed"]["label"])
        self.assertEqual("Replaced (1 file)", text["replaced"]["label"])        # only __init__.py's version line differs
        self.assertEqual("Your projects, settings and published reports are kept. A copy of your data is made first.", text["kept"])
        self.assertIsNone(text["by_hand"])
        self.assertFalse(text["reinstall"])

    def test_by_hand_line_and_reinstall(self):
        app = install_to(Path(self.tmp) / "app", "0.3.0")
        (app / "README.md").write_text("edited", encoding="utf-8")
        zips = Path(self.tmp) / "zips"
        zips.mkdir()
        r = self.read(make_zip(zips, version="0.3.0"), reinstall=True)
        text = updates.review(r, updates.plan(r, app), "0.3.0")
        self.assertEqual("1 file in the clark folder was changed by hand and will be replaced.", text["by_hand"])
        self.assertTrue(text["reinstall"])
        (app / "src" / "clark" / "x.py").write_text("also edited", encoding="utf-8")
        text = updates.review(r, updates.plan(r, app), "0.3.0")
        self.assertEqual("2 files in the clark folder were changed by hand and will be replaced.", text["by_hand"])

    def test_date_text(self):
        self.assertEqual("05-01-2027", updates.date_text("2027-01-05"))


class WordsTest(unittest.TestCase):
    BANNED = re.compile(r"\b(zip|manifest|sha|sha-256|path|vault|tracker|database|sweep|proposal|stage|apply|extract|refused|valid|invalid)\b",
                        re.I)

    def test_no_sentence_starts_with_the_product_name_or_uses_machine_words(self):
        for key, text in updates.MESSAGES.items():
            with self.subTest(key=key):
                self.assertFalse(text.lstrip().lower().startswith("clark"), text)
                self.assertIsNone(self.BANNED.search(text), text)
                self.assertTrue(text.rstrip().endswith("."), text)
                self.assertNotIn("\\", text)
                self.assertNotIn("/", text.replace("{", ""), "no file path on screen")

    def test_every_failure_has_a_next_step(self):
        nothing_to_do = {"layout", "git"}       # the next step is in the sentence ("by hand", "Download the latest release")
        steps = ("Download", "Choose", "Move", "Install", "Close", "try again")
        for key, text in updates.MESSAGES.items():
            with self.subTest(key=key):
                self.assertTrue(any(s.lower() in text.lower() for s in steps) or key in nothing_to_do, text)

    def test_detail_never_reaches_the_message(self):
        e = UpdateError("damaged", detail="hash of src/clark/a.py differs")
        self.assertNotIn("src", e.message)
        self.assertIn("src", e.detail)

    def test_only_five_names_in_the_log(self):
        text = updates.names_for_log([f"f{n}" for n in range(9)])
        self.assertEqual("f0, f1, f2, f3, f4 and 4 more", text)

    def test_every_key_used_in_the_code_has_a_sentence(self):
        source = (ROOT / "src" / "clark" / "updates.py").read_text(encoding="utf-8")
        for key in set(re.findall(r'UpdateError\("([a-z_]+)"', source)):
            self.assertIn(key, updates.MESSAGES)


if __name__ == "__main__":
    unittest.main()

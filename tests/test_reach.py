"""#47b: src/clark/reach.py, the one place that decides what ask clark may read. Copied from creaite's reach.py (v2.6.9) and changed
from a deny list to an allow list over the project's saved source folders. The tests are re-made from creaite's test_reach.py
(the never rows, a link judged by where it points, `..`, names in another case, the operation check, the OneDrive placeholder) and
test_file_access.py / test_onedrive_projects.py, and add clark's own: the allow list, a second project, secret names at any depth,
the "skipped for safety" count, read_bytes with O_NOFOLLOW, and the attacks (links, hard links, pipes, NUL, long paths, a
swap between the check and the open).

Run: python3 dev/run_tests.py test_reach
A temporary home folder, temporary source folders and fictional names only; nothing real is read or changed. The tests make no
Mac-only assumption (the platform layer is told it is on a Mac); a test that needs a case-insensitive or Unicode-normalising
volume probes the temporary folder and skips with its reason.
"""
import ast
import os
import shutil
import signal
import socket
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC
from clark import platform as pl
from clark import reach

SECRET_TEXT = b"TOPSECRET"


def touch(path, data=b"x"):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
    return path


class Reach(unittest.TestCase):
    """A fake home folder; project ABC saves two folders, project XYZ saves another; clark's data folder is in the home folder."""

    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-reach-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.src = self.home / "Projects" / "ABC Example Programme" / "Source"
        self.notes = self.home / "Projects" / "ABC Example Programme" / "Notes"
        self.other = self.home / "Projects" / "XYZ Example Programme" / "Source"
        self.outside = self.tmp / "outside"
        self.data = self.home / "Library" / "Application Support" / "clark"
        for d in (self.src, self.notes, self.other, self.outside, self.data):
            d.mkdir(parents=True)
        self.report = touch(self.src / "report.txt", "weekly report")
        self.secret = touch(self.outside / "secret.txt", SECRET_TEXT)
        self.db = touch(self.data / "clark.db", b"SQLite format 3")
        self.folders = [str(self.src), str(self.notes)]

    def c(self, path, folders=None):
        return reach.classify(path, "read", self.folders if folders is None else folders, str(self.data), home_dir=self.home)

    def kind(self, path, folders=None):
        return self.c(path, folders)[0]

    def rdt(self, path, limit=1000, folders=None):
        """read_bytes as it answers: (bytes, truncated)."""
        return reach.read_bytes(path, self.folders if folders is None else folders, str(self.data), limit, home_dir=self.home)

    def rd(self, path, limit=1000, folders=None):
        return self.rdt(path, limit, folders)[0]

    def never(self, path, reason=None, folders=None):
        kind, why = self.c(path, folders)
        self.assertEqual(kind, "never", f"{path}: {why}")
        if reason is not None:
            self.assertEqual(why, reason, str(path))
        with self.assertRaises(reach.Never, msg=str(path)):
            self.rd(path, folders=folders)

    def ok(self, path, folders=None):
        self.assertEqual(self.c(path, folders), ("ordinary", ""), str(path))


class AllowList(Reach):
    def test_inside_a_saved_folder_is_ordinary_and_the_rest_of_the_home_folder_is_never(self):
        self.ok(self.report)
        self.ok(touch(self.notes / "deep" / "er" / "n.md"))
        self.never(touch(self.home / "Documents" / "plan.md"), reach.OUTSIDE)   # creaite's verdict here is "ordinary": a deny list
        self.never(self.home, reach.OUTSIDE)
        self.never(self.tmp / "elsewhere.txt", reach.OUTSIDE)

    def test_with_no_saved_folders_everything_is_never(self):
        for f in ([], [str(self.tmp / "gone")], ["", "relative", 5, None, "a\0b"]):
            self.never(self.report, reach.OUTSIDE, folders=f)

    def test_another_projects_folder_and_a_sibling_folder_are_never(self):
        other_file = touch(self.other / "x.txt")
        sibling = touch(self.src.parent / "Source2" / "y.txt")
        self.never(other_file, reach.OUTSIDE)
        self.never(sibling, reach.OUTSIDE)
        self.ok(other_file, folders=[str(self.other)])                  # it is that project's own
        self.never(self.report, reach.OUTSIDE, folders=[str(self.other)])
        self.assertEqual(self.rd(self.report, 5), b"weekly"[:5])
        with self.assertRaises(reach.Never):
            self.rd(other_file)

    def test_a_saved_folder_that_is_the_home_folder_still_keeps_the_never_places(self):
        touch(self.home / ".ssh" / "id_rsa", SECRET_TEXT)
        touch(self.home / "Documents" / "plan.md")
        self.ok(self.home / "Documents" / "plan.md", folders=[str(self.home)])
        self.never(self.home / ".ssh" / "id_rsa", reach.SECRET, folders=[str(self.home)])
        self.never(self.db, reach.DATA, folders=[str(self.home)])

    def test_operations_are_checked(self):
        self.assertEqual(reach.OPERATIONS, ("read",))
        for op in ("create", "change", "move", "delete", "wipe", "", None):
            with self.assertRaises(ValueError, msg=str(op)):
                reach.classify(str(self.report), op, self.folders, str(self.data))

    def test_without_a_data_folder_everything_is_never(self):
        for data in (None, "", 5):
            self.assertEqual(reach.classify(str(self.report), "read", self.folders, data), ("never", reach.NO_DATA))


# creaite v2.6.9 reach.NEVER, the rows that bar reading: 29 below the home folder, 10 system folders (golden list)
GOLDEN_ROWS = (
    ("home", ".ssh"), ("home", ".aws"), ("home", ".gnupg"), ("home", ".config/gcloud"), ("home", ".config/gh"),
    ("home", ".config/op"), ("home", ".kube"), ("home", ".docker"), ("home", ".netrc"), ("home", ".git-credentials"),
    ("home", ".npmrc"), ("home", ".pypirc"), ("home", ".password-store"), ("home", "Library/Keychains"),
    ("home", "Library/Group Containers/*1password*"), ("home", "Library/Application Support/1Password"),
    ("home", "Library/Application Support/Bitwarden"), ("home", "Library/Application Support/Google/Chrome"),
    ("home", "Library/Application Support/Firefox"), ("home", "Library/Application Support/Microsoft Edge"),
    ("home", "Library/Application Support/BraveSoftware"), ("home", "Library/Application Support/Arc"),
    ("home", "Library/Safari"), ("home", "Library/Containers/com.apple.Safari"), ("home", "Library/Cookies"),
    ("home", ".mozilla"), ("home", ".config/google-chrome"), ("home", ".claude.json"), ("home", ".claude/.credentials.json"),
    ("abs", "/System"), ("abs", "/Library"), ("abs", "/usr"), ("abs", "/bin"), ("abs", "/sbin"), ("abs", "/etc"),
    ("abs", "/private/etc"), ("abs", "/opt"), ("abs", "/Applications"), ("abs", "/dev"))


class NeverRows(Reach):
    def test_the_rows_are_the_39_that_bar_reading_and_none_that_only_bar_writing(self):
        rows = reach.never_rows()
        self.assertEqual(len(rows), 39)
        self.assertEqual([(b, p) for b, p, _o, _r in rows], list(GOLDEN_ROWS))
        self.assertEqual({o for _b, _p, o, _r in rows}, {"all"})
        self.assertEqual({r for _b, _p, _o, r in rows}, {reach.SECRET, reach.SYSTEM})
        self.assertEqual(sum(1 for r in rows if r[3] == reach.SECRET), 29)
        for _b, pattern, _o, _r in rows:                                 # the 41 write-only rows would over-refuse reading
            self.assertNotIn("system/scripts", pattern)
            self.assertNotIn(".zshrc", pattern)

    def test_every_row_of_the_never_list(self):
        for base, pattern, _ops, reason in reach.never_rows():
            concrete = pattern.replace("*1password*", "2BUA8C4S2C.com.1password")
            path = (self.home / concrete / "inside.txt") if base == "home" else (Path(concrete) / "inside.txt")
            for folders in (self.folders, [str(self.home)]):
                kind, why = self.c(path, folders)
                self.assertEqual(kind, "never", f"{pattern}")
                self.assertEqual(why, reason, pattern)
                with self.assertRaises(reach.Never):
                    self.rd(path, folders=folders)

    def test_the_rows_move_with_the_platform_layer_and_windows_is_not_built(self):
        self.assertEqual(reach.never_rows()[0][:2], ("home", ".ssh"))
        with mock.patch.object(pl, "system", return_value=pl.WINDOWS):
            with self.assertRaises(pl.NotBuiltYet):
                reach.never_rows()
            with self.assertRaises(pl.NotBuiltYet):
                self.c(self.report)

    def test_names_in_another_case_are_the_same_place(self):
        touch(self.home / ".ssh" / "config")
        for spelled in (".SSH/config", ".Ssh/CONFIG", "library/keychains/login.keychain-db", "LIBRARY/KEYCHAINS/x"):
            self.never(self.home / spelled, reach.SECRET, folders=[str(self.home)])
        self.never("/ETC/hosts", reach.SYSTEM)
        self.never("/system/library/x", reach.SYSTEM)

    def test_the_data_folder_is_never_wherever_the_source_folder_is(self):
        touch(self.data / "clark.db-wal")
        touch(self.data / "clark.db-shm")
        touch(self.data / "backups" / "clark-2026-10-28.db")
        touch(self.data / "settings.json", "{}")
        touch(self.data / "logs" / "clark.log")
        parents = [str(self.home), str(self.home / "Library"), str(self.home / "Library" / "Application Support"), str(self.data)]
        for folders in ([p] for p in parents):
            for rel in ("clark.db", "clark.db-wal", "clark.db-shm", "backups/clark-2026-10-28.db", "settings.json", "logs/clark.log"):
                self.never(self.data / rel, reach.DATA, folders=folders)
        self.never(self.data / "CLARK.DB", reach.DATA, folders=[str(self.home)])        # another spelling of the same place

    def test_a_link_to_the_database_or_the_data_folder_is_never(self):
        (self.src / "db").symlink_to(self.db)
        (self.src / "datadir").symlink_to(self.data)
        self.never(self.src / "db", reach.DATA)
        self.never(self.src / "datadir" / "clark.db", reach.DATA)

    def test_the_reasons_are_plain_words_and_never_hold_the_path(self):
        cases = [self.report.parent / ".." / ".." / "x" / "secret-folder-name", self.db, self.home / ".ssh" / "key-name-zz",
                 "relative-zz/x", self.src / "no-such-file-zz"]
        for path in cases:
            kind, why = self.c(path)
            if kind == "never":
                self.assertNotIn("zz", why)
                self.assertNotIn(str(self.tmp), why)
                self.assertTrue(why[0].islower(), why)         # "it ...", "the path ..."
        for text in (reach.SECRET, reach.SYSTEM, reach.DATA, reach.OUTSIDE, reach.NOT_FILE, reach.LINKED, reach.ONLINE, reach.LINK):
            self.assertNotRegex(text, r"[A-Z]:|/|\\|ENOENT|errno")


# the names that hold secrets, at any depth inside a saved folder: pattern -> a real name that matches it (golden list)
SECRET_SAMPLES = {
    ".git": ".git", ".ssh": ".ssh", ".gnupg": ".gnupg", ".aws": ".aws", ".kube": ".kube", ".docker": ".docker",
    ".azure": ".azure", ".password-store": ".password-store",
    ".terraform": ".terraform", ".oci": ".oci", ".bundle": ".bundle",
    ".env*": ".env.local", "*.env": "prod.env", "*.pem*": "server.pem", "*.key*": "tls.key",
    "*.p12": "sign.p12", "*.pfx": "sign.pfx", "*.p8": "AuthKey.p8", "*.asc": "signing.asc", "*.gpg": "vault.gpg",
    "*.pgp": "mail.pgp", "*.kdbx": "passwords.kdbx", "*.keychain*": "login.keychain-db",
    "*.ppk": "putty.ppk", "*.jks": "store.jks", "*.keystore": "app.keystore", "*.tfstate*": "main.tfstate.backup",
    "*.tfvars*": "prod.tfvars.json", "id_rsa*": "id_rsa", "id_dsa*": "id_dsa",
    "id_ecdsa*": "id_ecdsa", "id_ed25519*": "id_ed25519", ".netrc": ".netrc", "_netrc": "_netrc", ".npmrc": ".npmrc",
    ".pypirc": ".pypirc", ".pgpass*": ".pgpass.bak", ".git-credentials": ".git-credentials", ".htpasswd": ".htpasswd",
    "kubeconfig": "kubeconfig", "client_secret*.json": "client_secret_123.apps.json",
    "service-account*.json": "service-account-prod.json", "secrets.*": "secrets.yaml", "credentials": "credentials",
    "credentials*.json": "credentials-prod.json", ".dockercfg": ".dockercfg", ".vault_pass*": ".vault_pass.txt",
    "service_account*.json": "service_account_prod.json", "serviceAccountKey.json": "serviceAccountKey.json",
    "*credentials*": "aws-credentials.bak", "*secret*.json": "app_secret.json", ".boto": ".boto", ".s3cfg": ".s3cfg",
    ".my.cnf": ".my.cnf", ".vault*": ".vault-token", "token*.json": "token-1.json", "oauth.json": "oauth.json",
    "private_key.json": "private_key.json", "secret_key_base": "secret_key_base", ".gitconfig": ".gitconfig"}
EXTRA_SAMPLES = (".env.production", ".env", ".envrc", ".envelope", "id_rsa.pub", "id_ed25519.pub", "credentials.json", "my.keychain",
                 "x.PEM", ".ENV", "ID_RSA", "Credentials.JSON", ".Git-Credentials", "cert.pem.bak", "tls.key.old", "KUBECONFIG",
                 "Secrets.JSON", "terraform.tfstate", "Prod.TFVARS", "id_rsa ", "id_rsa.", ".env. .", "credentials.json ", ".netrc..", ".vault_pass", ".VAULT_PASS_prod",
                 "serviceaccountkey.JSON", "Token.json", "my-credentials.docx", "db.tfvars.json", ".Pgpass2")
SAFE_NAMES = ("environment.md", "keyboard.txt", "monkey.txt", ".gitignore", ".gitattributes", "credits.docx",
              "keys.docx", "pem.txt", "idea_rsa.txt", "my id_rsa.txt", "report.txt", ".github", "gitlab",
              "secret.txt", "kubeconfig.md", "client.json", "service.json", "asc.txt")


class SecretNames(Reach):
    """"""

    def test_the_pattern_set_is_the_golden_list(self):
        self.assertEqual(set(reach.SECRET_NAMES), set(SECRET_SAMPLES))
        self.assertEqual(len(reach.SECRET_NAMES), len(set(reach.SECRET_NAMES)))
        for pattern, sample in SECRET_SAMPLES.items():
            self.assertEqual(reach.secret_name([sample]), sample, pattern)         # the sample really matches its own pattern
        self.assertEqual(reach.secret_name([]), None)

    def test_each_pattern_at_depth_0_and_depth_3(self):
        for pattern, name in SECRET_SAMPLES.items():
            for rel in (name, f"a/b/c/{name}"):
                if pattern in reach.SECRET_FOLDERS:
                    path = touch(self.src / rel / "inside.txt")
                    inner = touch(self.src / rel / "x" / "deeper" / "more.txt")      # anything inside, however deep
                    self.never(inner, reach.SECRET)
                else:
                    path = touch(self.src / rel, SECRET_TEXT)
                self.never(path, reach.SECRET)
                self.assertEqual(self.c(path, [str(self.src)]), ("never", reach.SECRET), f"{pattern} at {rel}")

    def test_more_spellings_and_cases(self):
        for name in EXTRA_SAMPLES:
            for rel in (name, f"a/b/c/{name}"):
                self.never(touch(self.src / rel), reach.SECRET)

    def test_the_private_key_and_its_public_key_are_both_barred(self):
        self.never(touch(self.src / "keys" / "id_rsa"), reach.SECRET)
        self.never(touch(self.src / "keys" / "id_rsa.pub"), reach.SECRET)       # decided: id_rsa* bars both (see the module header)

    def test_a_secret_inside_the_second_saved_folder_is_barred_too(self):
        self.never(touch(self.notes / "x" / ".env"), reach.SECRET)

    def test_a_saved_folder_that_is_itself_a_secret_name_is_never(self):
        d = self.tmp / "work" / ".aws"
        f = touch(d / "notes.txt")
        self.never(f, reach.SECRET, folders=[str(d)])

    def test_a_secret_folder_above_the_saved_folder_bars_everything_in_it(self):
        """M1: the names ABOVE the saved folder were not looked at."""
        for secret in (".git/modules/x", ".kube/cache", ".aws/sso", ".docker/contexts/meta", ".ssh", "a/.gnupg/b"):
            d = self.tmp / "work" / secret
            f = touch(d / "notes.txt")
            self.never(f, reach.SECRET, folders=[str(d)])
            self.never(f, reach.SECRET, folders=[str(d.parent)])
            self.assertEqual(reach.readable_files([str(d)], str(self.data), home_dir=self.home), ([], 1, False), secret)
        reasons = {}
        reach.readable_files([str(self.tmp / "work" / ".kube" / "cache")], str(self.data), reasons, home_dir=self.home)
        self.assertEqual(reasons, {reach.SECRET: 1})                 # the saved folder once, not each thing in it

    def test_never_inside_names_a_secret_folder_on_the_way_to_the_folder(self):
        for secret, name in ((".git/modules/x", ".git"), (".kube/cache", ".kube"), ("p/.AWS/q", ".AWS"), (".docker", ".docker")):
            d = self.tmp / "work" / secret
            d.mkdir(parents=True, exist_ok=True)
            self.assertEqual(reach.never_inside(str(d), str(self.data), home_dir=self.home), name)
        self.assertEqual(reach.never_inside(str(self.tmp / "work" / "p"), str(self.data), home_dir=self.home), None)

    def test_a_folder_above_the_saved_folder_named_like_a_secret_file_is_no_secret(self):
        """
        secret FOLDER name counts."""
        for above in ("dev.env", "work.env", "Plans.key", "secrets.2026", "a/.envrc/b", "x.pem/y"):
            d = self.tmp / "work" / above / "project"
            f = touch(d / "notes.txt", "weekly notes")
            self.assertEqual(self.c(f, [str(d)]), ("ordinary", ""), above)
            self.assertEqual(self.rd(f, folders=[str(d)]), b"weekly notes", above)
            self.assertEqual(reach.readable_files([str(d)], str(self.data), home_dir=self.home)[0], [Path(f)], above)
            self.assertEqual(reach.never_inside(str(d), str(self.data), home_dir=self.home), None, above)
            self.never(touch(d / "sub" / "x.env"), reach.SECRET, folders=[str(d)])          # at and below, everything still counts
            self.never(touch(d / "sub" / ".git" / "config"), reach.SECRET, folders=[str(d)])

    def test_a_secret_folder_above_the_saved_folder_is_still_refused_among_file_like_names(self):
        for above in (".git", ".kube", "dev.env/.git", "work.env/.kube/x"):
            d = self.tmp / "work" / above / "project"
            f = touch(d / "notes.txt")
            self.never(f, reach.SECRET, folders=[str(d)])
            self.assertIn(reach.never_inside(str(d), str(self.data), home_dir=self.home), (".git", ".kube"), above)

    def test_the_saved_folder_itself_named_like_a_secret_is_refused(self):
        for name in ("x.env", "prod.key", "secrets.2026", ".git", ".env.d"):
            d = self.tmp / "work" / name
            f = touch(d / "notes.txt")
            self.never(f, reach.SECRET, folders=[str(d)])
            self.assertEqual(reach.readable_files([str(d)], str(self.data), home_dir=self.home), ([], 1, False), name)
            self.assertEqual(reach.never_inside(str(d), str(self.data), home_dir=self.home), name)

    def test_trailing_spaces_and_dots_are_dropped_before_matching(self):
        for name in ("id_rsa ", "id_rsa.", ".git ", ".git.", ".ssh. .", "credentials ", "credentials.json ", ".netrc..", "tls.key   "):
            self.assertEqual(reach.secret_name(["x", name]), name, repr(name))
        for name in ("report.txt.", "report.txt ", "...", " ", ""):
            self.assertEqual(reach.secret_name([name]), None, repr(name))
        self.never(touch(self.src / "keys" / "id_rsa "), reach.SECRET)
        self.never(touch(self.src / ".git." / "config"), reach.SECRET)

    def test_ordinary_names_that_only_look_alike_are_readable(self):
        for name in SAFE_NAMES:
            for rel in (name, f"a/b/c/{name}"):
                if name in (".github", "gitlab"):
                    rel += "/readme.md"
                self.ok(touch(self.src / rel))

    def test_a_link_with_an_innocent_name_to_a_secret_is_judged_by_its_target(self):
        env = touch(self.src / "config" / ".env", SECRET_TEXT)
        (self.src / "notes.txt").symlink_to(env)
        self.never(self.src / "notes.txt", reach.SECRET)
        os.link(env, self.src / "readme.txt")                                    # a second name for it on disk
        self.never(self.src / "readme.txt", reach.LINKED)
        self.never(env, reach.SECRET)

    def test_read_bytes_never_returns_a_secret(self):
        touch(self.src / "deep" / ".env", SECRET_TEXT)
        with self.assertRaises(reach.Never) as cm:
            self.rd(self.src / "deep" / ".env")
        self.assertEqual(cm.exception.reason, reach.SECRET)

    def test_never_inside_names_the_place(self):
        self.assertEqual(reach.never_inside(str(self.home), str(self.data), home_dir=self.home), "~/.ssh")
        self.assertEqual(reach.never_inside(str(self.home / ".ssh" / "keys"), str(self.data), home_dir=self.home), "~/.ssh")
        self.assertEqual(reach.never_inside("/", home_dir=self.home), "~/.ssh")       # the first place it holds
        mine = self.tmp / "holder" / "mydata"
        (mine / "sub").mkdir(parents=True)
        for folder in (mine.parent, mine, mine / "sub"):                          # holding the data folder, being it, inside it
            self.assertEqual(reach.never_inside(str(folder), str(mine), home_dir=self.home), "clark's data folder")
        self.assertEqual(reach.never_inside(str(self.src), str(self.data), home_dir=self.home), None)
        self.assertEqual(reach.never_inside("a\0b", str(self.data), home_dir=self.home), "a\0b")


class Skipped(Reach):
    """readable_files: (files, skipped_count, stopped) so the page can say how many were skipped for safety."""

    def build(self):
        for rel in ("a.txt", "sub/b.md", "sub/deeper/c.docx"):
            touch(self.src / rel)
        touch(self.notes / "n.md")
        touch(self.src / ".env")
        touch(self.src / "sub" / "tls.key")
        touch(self.src / "sub" / "id_rsa.pub")
        touch(self.src / ".git" / "config")
        touch(self.src / ".git" / "objects" / "ab" / "cdef")
        touch(self.src / "sub" / ".aws" / "credentials")
        touch(self.src / ".DS_Store")
        touch(self.src / "~$Plan.xlsx")
        touch(self.src / "._a.txt")

    def test_the_files_and_the_count(self):
        self.build()
        reasons = {}
        files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual(files, sorted([self.report, self.src / "a.txt", self.src / "sub" / "b.md", self.src / "sub" / "deeper" / "c.docx",
                                        self.notes / "n.md"]))
        self.assertEqual(skipped, 5)              # .env, tls.key, id_rsa.pub, the .git folder (once), the .aws folder (once)
        self.assertEqual(reasons, {reach.SECRET: 5})
        self.assertEqual(reach.readable_files(self.folders, str(self.data), home_dir=self.home), (files, 5, False))

    def test_noise_is_left_out_and_not_counted(self):
        touch(self.src / ".DS_Store")
        touch(self.src / "~$Plan.xlsx")
        touch(self.src / ".Trash" / "old.txt")
        touch(self.src / "Thumbs.db")
        files, skipped, stopped = reach.readable_files(self.folders, str(self.data), home_dir=self.home)
        self.assertEqual((files, skipped), ([self.report], 0))
        for name in (".DS_Store", "~$Plan.xlsx", "._x", ".Trash", "Thumbs.db", "desktop.ini", ".~lock.a.odt#"):
            self.assertTrue(reach.is_noise(name), name)
        self.assertFalse(reach.is_noise("report.txt"))

    def test_links_pipes_hard_links_placeholders_and_the_data_folder_are_counted(self):
        (self.src / "out").symlink_to(self.outside)                      # a link to a folder is not followed
        (self.src / "outfile.txt").symlink_to(self.secret)
        os.link(self.secret, self.src / "hard.txt")
        os.mkfifo(self.src / "pipe")
        touch(self.src / "cloud.txt", b"1234567")
        d = self.src / "mydata"
        d.mkdir()
        reasons = {}
        real_online = reach.online_only_stat
        with mock.patch.object(reach, "online_only_stat", lambda st: st.st_size == 7 or real_online(st)):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual(files, [self.report])
        self.assertEqual(reasons, {reach.LINK: 1, reach.OUTSIDE: 1, reach.LINKED: 1, reach.NOT_FILE: 1, reach.ONLINE: 1})
        self.assertEqual(skipped, 5)

    def test_a_data_folder_inside_a_saved_folder_is_skipped_once(self):
        reasons = {}
        files, skipped, stopped = reach.readable_files([str(self.home / "Library")], str(self.data), reasons, home_dir=self.home)
        self.assertEqual(files, [])
        self.assertEqual(skipped, 1)
        self.assertEqual(reasons, {reach.DATA: 1})

    def test_a_file_in_two_saved_folders_or_by_a_link_is_listed_once(self):
        (self.src / "again.txt").symlink_to(touch(self.notes / "n.md"))
        files, skipped, stopped = reach.readable_files(self.folders + [str(self.src)], str(self.data), home_dir=self.home)
        self.assertEqual(files, sorted([self.report, self.notes / "n.md"]))
        self.assertEqual(skipped, 0)

    def test_a_folder_that_cannot_be_opened_is_counted(self):
        d = self.src / "locked"
        touch(d / "x.txt")
        os.chmod(d, 0)
        self.addCleanup(os.chmod, d, 0o755)
        reasons = {}
        files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        if os.access(d, os.R_OK):
            self.skipTest("this user can read a folder with no permissions (root)")
        self.assertEqual(files, [self.report])
        self.assertEqual(skipped, 1)

    def test_nothing_is_read_or_opened_while_listing(self):
        self.build()
        with mock.patch.object(reach.os, "open", side_effect=AssertionError("opened a file")):
            reach.readable_files(self.folders, str(self.data), home_dir=self.home)


class Adversarial(Reach):
    def test_dotdot_is_resolved_first(self):
        self.never(f"{self.src}/sub/../../Source2/x", reach.OUTSIDE)
        self.never(f"{self.src}/a/../../b", reach.OUTSIDE)
        self.never(f"{self.src}/..", reach.OUTSIDE)
        self.never(f"{self.src}/../../../outside/secret.txt", reach.OUTSIDE)
        self.never(f"{self.src}/../../../../home/.ssh/config", reach.SECRET)
        touch(self.src / "sub" / "ok.txt")
        self.ok(f"{self.src}/sub/../sub/ok.txt")                           # a `..` that stays inside is fine
        self.never(f"{self.src}/folder/..", reach.NOT_FILE)

    def test_relative_and_odd_inputs(self):
        for bad in ("./../x", "../x", "x", "", "folder/..", "~nosuchuser-zz/x", b"/etc/hosts", None, 5, 1.5, ["a"], "a\0b",
                    str(self.src) + "\0/report.txt", str(self.src / "report.txt") + "\0"):
            kind, why = self.c(bad)
            self.assertEqual(kind, "never", repr(bad))
            self.assertNotIn("zz", why)
            with self.assertRaises(reach.Never):
                self.rd(bad)

    def test_a_relative_path_is_never_resolved_against_the_working_folder(self):
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.src)
        self.assertEqual(self.c("report.txt"), ("never", "the path is not an absolute path"))
        self.assertEqual(self.c("./report.txt")[0], "never")

    def test_other_users_homes_and_system_paths(self):
        for p in ("~root/x", "~root/.ssh/id_rsa", "/etc/hosts", "/private/etc/hosts", "/System/Library/x", "/usr/bin/python3",
                  "/", "/tmp", str(self.tmp)):
            self.never(p)

    def test_url_encoded_dots_are_literal_names_not_decoded(self):
        self.never(f"{self.src}/%2e%2e/outside/secret.txt", reach.NOT_THERE)
        self.never(f"{self.src}/..%2foutside%2fsecret.txt", reach.NOT_THERE)
        literal = touch(self.src / "..%2fnotes.txt", "literal")
        self.assertEqual(self.rd(literal), b"literal")                      # a real file with that literal name is read as itself

    def test_odd_names_are_read_as_themselves_checked_path_equals_opened_path(self):
        names = ["-rf", "-", "--help", "a\\b.txt", "line\nbreak.txt", "tab\tname.txt", " lead.txt", "emoji \u2603.txt", "100%.txt", "a b.txt"]
        for n in names:
            f = touch(self.src / n, n)
            self.ok(f)
            self.assertEqual(self.rd(f), n.encode("utf-8"), repr(n))
        self.never(f"{self.src}/report.txt.", reach.NOT_THERE)               # a trailing dot or space is another name, not this file
        self.never(f"{self.src}/report.txt ", reach.NOT_THERE)
        self.assertEqual(self.rd(f"{self.src}/report.txt/"), b"weekly report")      # a trailing slash resolves to the file itself
        self.assertEqual(self.rd(f"{self.src}//report.txt"), b"weekly report")

    def test_a_backslash_is_not_a_separator(self):
        touch(self.outside / "x.txt")
        self.never(f"{self.src}\\..\\..\\outside\\x.txt")
        self.never(f"{self.src}/..\\outside/x.txt")

    def test_nul_bytes_are_never_and_nothing_escapes(self):
        with mock.patch.object(reach.os, "open", side_effect=AssertionError("opened")):
            for bad in (str(self.report) + "\0", "\0", str(self.src) + "\0/report.txt", f"{self.src}/re\0port.txt"):
                self.assertEqual(self.c(bad)[0], "never")
                with self.assertRaises(reach.Never):
                    self.rd(bad)
            self.never(self.report, folders=["a\0b", str(self.tmp / "x\0y")])       # NUL in the list: left out, no exception
        self.ok(self.report, folders=["a\0b", str(self.src)])                              # and the good entry still works

    def test_very_long_paths_are_never_and_nothing_is_opened(self):
        longs = [str(self.src / ("a" * 300)), str(self.src) + "/" + ("d" * 100 + "/") * 11 + "x.txt", f"{self.src}/" + "x/" * 2500 + "f",
                 str(self.src) + "/" + "b" * 5000]
        with mock.patch.object(reach.os, "open", side_effect=AssertionError("opened")):
            for p in longs:
                kind, why = self.c(p)
                self.assertEqual(kind, "never", p[:40])
                self.assertEqual(why, "the path is too long")
                with self.assertRaises(reach.Never):
                    self.rd(p)
        self.assertEqual(self.c(str(self.src / ("a" * 255)))[1], reach.NOT_THERE)         # 255 is the longest name; this one is allowed to be asked about

    def test_a_very_long_but_real_folder_depth_is_read(self):
        d = self.src
        for _ in range(30):
            d = d / "level"
        f = touch(d / "deep.txt", "deep")
        self.assertLess(len(os.fsencode(str(f))), 1024)
        self.assertEqual(self.rd(f), b"deep")


class Links(Reach):
    def test_a_file_link_and_a_folder_link_pointing_out_are_never(self):
        (self.src / "file-link").symlink_to(self.secret)
        (self.src / "dir-link").symlink_to(self.outside, target_is_directory=True)
        self.never(self.src / "file-link", reach.OUTSIDE)
        self.never(self.src / "dir-link" / "secret.txt", reach.OUTSIDE)
        self.never(self.src / "dir-link", reach.OUTSIDE)
        self.never(self.src / "dir-link" / ".." / "outside" / "secret.txt", reach.OUTSIDE)

    def test_a_chain_of_three_is_judged_by_where_it_ends(self):
        (self.src / "l3").symlink_to(self.secret)
        (self.src / "l2").symlink_to(self.src / "l3")
        (self.src / "l1").symlink_to(self.src / "l2")
        self.never(self.src / "l1", reach.OUTSIDE)
        inner = touch(self.src / "real.txt", "inner")
        (self.src / "i3").symlink_to(inner)
        (self.src / "i2").symlink_to(self.src / "i3")
        (self.src / "i1").symlink_to(self.src / "i2")
        self.ok(self.src / "i1")
        self.assertEqual(self.rd(self.src / "i1"), b"inner")

    def test_a_link_to_a_secret_is_a_secret(self):
        key = touch(self.home / ".ssh" / "id_rsa", SECRET_TEXT)
        (self.src / "innocent.txt").symlink_to(key)
        self.never(self.src / "innocent.txt", reach.SECRET)
        self.never(self.src / "innocent.txt", reach.SECRET, folders=[str(self.src), str(self.home)])

    def test_a_link_to_another_saved_folder_of_the_same_project_is_judged_by_its_target(self):
        n = touch(self.notes / "n.md", "notes")
        (self.src / "to-notes.md").symlink_to(n)
        self.ok(self.src / "to-notes.md")
        self.assertEqual(self.rd(self.src / "to-notes.md"), b"notes")
        self.never(self.src / "to-notes.md", reach.OUTSIDE, folders=[str(self.src)])        # not saved for this project: out

    def test_dangling_loops_and_self_links(self):
        (self.src / "dangling").symlink_to(self.src / "nothing-here")
        (self.src / "a").symlink_to(self.src / "b")
        (self.src / "b").symlink_to(self.src / "a")
        (self.src / "me").symlink_to(self.src / "me")
        for n in ("dangling", "a", "b", "me"):
            kind, _why = self.c(self.src / n)
            self.assertEqual(kind, "never", n)
            with self.assertRaises(reach.Never):
                self.rd(self.src / n)

    def test_a_link_in_the_saved_folder_path_itself_is_followed_by_the_check_not_the_open(self):
        link = self.tmp / "shortcut"
        link.symlink_to(self.src, target_is_directory=True)
        self.ok(link / "report.txt")                                          # the saved folder is reached by a link: same folder
        self.assertEqual(self.rd(link / "report.txt"), b"weekly report")
        self.ok(self.report, folders=[str(link)])
        self.assertEqual(self.rd(self.report, folders=[str(link)]), b"weekly report")

    def test_hard_links_are_refused_with_their_own_reason(self):
        os.link(self.secret, self.src / "hard.txt")
        os.link(self.db, self.src / "hard.db")
        for n in ("hard.txt", "hard.db"):
            self.never(self.src / n, reach.LINKED)
        os.link(self.report, self.src / "report-2.txt")                       # both names of a file with two names are refused
        self.never(self.report, reach.LINKED)
        self.never(self.src / "report-2.txt", reach.LINKED)
        self.assertIn("more than one name on disk", reach.LINKED)

    def test_directories_pipes_sockets_and_devices_are_never_and_do_not_hang(self):
        signal.alarm(5)
        self.addCleanup(signal.alarm, 0)
        os.mkfifo(self.src / "pipe")
        self.never(self.src / "pipe", reach.NOT_FILE)
        self.never(self.src, reach.NOT_FILE)
        self.never(self.src / "nothing", reach.NOT_THERE)
        (self.src / "null").symlink_to("/dev/null")
        self.never(self.src / "null", reach.SYSTEM)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.src)
        try:
            s = socket.socket(socket.AF_UNIX)
            self.addCleanup(s.close)
            s.bind("sock")
        except OSError:
            pass
        else:
            self.never(self.src / "sock", reach.NOT_FILE)


class Volumes(Reach):
    """Case and Unicode spellings: a name is one place only where the volume says so. Probes the temporary volume."""

    def volume(self, name):
        probe = self.tmp / "probe"
        probe.mkdir(exist_ok=True)
        if name == "case":
            touch(probe / "Case")
            return (probe / "case").exists()
        touch(probe / "\u00e9")
        return (probe / "e\u0301").exists()

    def test_on_a_case_insensitive_volume_another_spelling_of_the_folder_is_inside(self):
        if not self.volume("case"):
            self.skipTest("this temporary volume is case-sensitive")
        self.ok(self.src.parent.parent / "ABC EXAMPLE PROGRAMME" / "source" / "report.txt")
        self.assertEqual(self.rd(self.src.parent.parent / "abc example programme" / "SOURCE" / "report.txt"), b"weekly report")

    def test_on_a_case_sensitive_volume_a_sibling_in_another_case_is_not_inside(self):
        if self.volume("case"):
            self.skipTest("this temporary volume is case-insensitive")
        touch(self.src.parent / "source" / "x.txt")
        self.never(self.src.parent / "source" / "x.txt", reach.OUTSIDE)
        self.never(self.src.parent / "SOURCE" / "report.txt")

    def test_a_decomposed_spelling_of_a_composed_folder_name_is_inside(self):
        if not self.volume("unicode"):
            self.skipTest("this temporary volume keeps two spellings of a name apart")
        composed = self.tmp / "Pr\u00fcfung"
        touch(composed / "a.txt", "pruefung")
        decomposed = self.tmp / "Pru\u0308fung"
        self.ok(decomposed / "a.txt", folders=[str(composed)])
        self.assertEqual(self.rd(decomposed / "a.txt", folders=[str(composed)]), b"pruefung")
        self.ok(composed / "a.txt", folders=[str(decomposed)])

    def test_another_unicode_spelling_of_the_home_folder_does_not_hide_a_never_place(self):
        if not self.volume("unicode"):
            self.skipTest("this temporary volume keeps two spellings of a name apart")
        home = self.tmp / "Zo\u00eb"
        touch(home / ".ssh" / "id_rsa", SECRET_TEXT)
        touch(home / "doc.txt")
        spelled = self.tmp / "Zoe\u0308"
        kind = reach.classify(str(spelled / ".ssh" / "id_rsa"), "read", [str(home)], str(self.data), home_dir=home)
        self.assertEqual(kind, ("never", reach.SECRET))
        self.assertEqual(reach.classify(str(spelled / "doc.txt"), "read", [str(home)], str(self.data), home_dir=home)[0], "ordinary")

    def test_inside_is_identity_not_a_name_comparison(self):
        same = lambda a, b: str(a) == str(b)             # a volume where every spelling is its own name
        with mock.patch.object(reach.os.path, "samefile", same):
            self.assertTrue(reach.inside("/a/Source/x", "/a/Source"))
            self.assertFalse(reach.inside("/a/source/x", "/a/Source"))
            self.assertFalse(reach.inside("/a", "/a/Source"))
            self.assertFalse(reach.inside("/a/Source2/x", "/a/Source"))
        with mock.patch.object(reach.os.path, "samefile", side_effect=OSError):
            self.assertFalse(reach.inside("/a/Source/x", "/a/Source"))
        with mock.patch.object(reach.os.path, "samefile", side_effect=ValueError):
            self.assertFalse(reach.inside("/a/Source/x", "/a/Source"))
        self.assertFalse(reach.inside("/a/b", ""))


class Folding(Reach):
    """H1: names are matched as the Mac's disk compares them (NFKC and case folding), not just lower-cased: APFS reads a long s
    as an s and a sharp s as "ss". Non-ASCII is written as \\u escapes. The first tests need no particular volume."""

    LONG_S, SHARP_S = "\u017f", "\u00df"

    def test_secret_names_are_found_whichever_spelling_the_disk_folds(self):
        for spelled, plain in ((f"id_r{self.LONG_S}a", "id_rsa"), (f".{self.SHARP_S}h", ".ssh"), (f".{self.LONG_S}sh", ".ssh"),
                               (f"credential{self.LONG_S}.j{self.LONG_S}on", "credentials.json"),
                               (f".g\u0069t", ".git"), ("\uff49\uff44_rsa", "id_rsa"),             # a full-width i d
                               (f"{self.LONG_S}ecret{self.LONG_S}.yaml", "secrets.yaml"), (f"tls.k\u0065y", "tls.key")):
            self.assertEqual(reach.secret_name([spelled]), spelled, plain)
        self.assertEqual(reach.secret_name([f"cre{self.SHARP_S}.txt"]), None)
        self.assertEqual(reach.fold(f"{self.SHARP_S}"), "ss")
        self.assertEqual(reach.fold("Pru\u0308fung"), reach.fold("Pr\u00fcfung"))

    def test_the_never_rows_are_folded_on_both_sides(self):
        self.assertTrue(reach.matches([f".{self.LONG_S}sh", "k"], ".ssh"))
        self.assertTrue(reach.matches([f".{self.SHARP_S}h"], ".ssh"))
        self.assertTrue(reach.matches(["Library", f"Keychain{self.LONG_S}", "login"], "Library/Keychains"))
        self.assertTrue(reach.matches([".ssh"], f".{self.LONG_S}sh"))                       # the pattern side too
        self.assertTrue(reach.matches(["LIBRARY", "Application Support", "1Password"], "Library/Application Support/1Password"))
        self.assertFalse(reach.matches([".sh"], ".ssh"))
        self.assertEqual(reach.parts_under("/A/Pru\u0308fung/x", "/a/pr\u00fcfung"), ["x"])

    def test_a_never_place_in_another_spelling_is_never_even_where_it_does_not_exist(self):
        for rel in (f".{self.LONG_S}sh/k", f".{self.SHARP_S}h/k", f".aw{self.LONG_S}/credentials", f"Library/Keychain{self.LONG_S}/login.keychain-db",
                    f".config/{self.LONG_S}ch/hosts.yml".replace(f"{self.LONG_S}ch", "gh")):
            kind, why = self.c(self.home / rel, folders=[str(self.home)])
            self.assertEqual((kind, why), ("never", reach.SECRET), rel)
        self.assertEqual(self.c(f"/{self.LONG_S}ystem/Library/x")[1], reach.SYSTEM)
        self.assertEqual(self.c(f"/{self.LONG_S}ystem/Library/x", folders=["/"])[1], reach.SYSTEM)

    def folds(self, plain, spelled):
        """Whether this temporary volume reads `spelled` as `plain` (APFS does for a long s and a sharp s)."""
        probe = self.tmp / "probe-fold"
        probe.mkdir(exist_ok=True)
        touch(probe / plain)
        return (probe / spelled).exists()

    def test_read_bytes_of_a_folded_spelling_of_a_secret_returns_nothing(self):
        """A secret planted under its real name and asked for in a spelling the disk folds to it is refused, not read."""
        tried = 0
        for planted, asked in (("id_rsa", f"id_r{self.LONG_S}a"), (".ssh/k", f".{self.LONG_S}sh/k"), (".ssh/k", f".{self.SHARP_S}h/k"),
                               ("credentials.json", f"credential{self.LONG_S}.j{self.LONG_S}on")):
            plain, spelled = planted.split("/")[0], asked.split("/")[0]
            if not self.folds(plain, spelled):
                continue
            tried += 1
            with self.subTest(asked=asked):
                touch(self.src / planted, SECRET_TEXT)
                self.assertTrue((self.src / asked).exists())                # the disk says it is the same file
                self.never(self.src / asked, reach.SECRET)
                with self.assertRaises(reach.Never) as cm:
                    self.rd(self.src / asked)
                self.assertEqual(cm.exception.reason, reach.SECRET)
        if not tried:
            self.skipTest("this temporary volume does not fold a long s or a sharp s")

    def test_the_name_judged_is_the_one_the_disk_holds_even_if_the_comparison_is_the_old_lower(self):
        """The disk name is judged too (os.scandir entry with the same inode and device): with fold made the old lower(),
        a long-s spelling still reaches a planted id_rsa and is refused because the disk calls it id_rsa."""
        if not self.folds("s", self.LONG_S):
            self.skipTest("this temporary volume does not fold a long s")
        touch(self.src / "id_rsa", SECRET_TEXT)
        asked = self.src / f"id_r{self.LONG_S}a"
        self.assertTrue(asked.exists())
        with mock.patch.object(reach, "fold", lambda name: name.lower()):
            self.assertEqual(self.c(asked), ("ordinary", ""))                  # the given name alone is not enough ...
            with self.assertRaises(reach.Never) as cm:
                self.rd(asked)                                                 # ... but the name on the disk is judged
            self.assertEqual(cm.exception.reason, reach.SECRET)
        folder = self.src / "ok"
        touch(folder / "x.txt", "fine")
        with mock.patch.object(reach, "fold", lambda name: name.lower()):
            self.assertEqual(self.rd(folder / "x.txt"), b"fine")                # an ordinary file is still read

    def test_disk_name_is_the_entry_with_the_same_inode(self):
        f = touch(self.src / "Real-Name.TXT", "x")
        fd = os.open(self.src, os.O_RDONLY)
        self.addCleanup(os.close, fd)
        self.assertEqual(reach._disk_name(fd, "other-spelling", os.stat(f)), "Real-Name.TXT")
        self.assertEqual(reach._disk_name(fd, "kept", os.stat(self.report.parent)), "kept")        # no entry of this folder is it
        with mock.patch.object(reach.os, "scandir", side_effect=OSError):
            self.assertEqual(reach._disk_name(fd, "kept", os.stat(f)), "kept")                     # a folder that can't be listed


class Caps(Reach):
    """L2: read_bytes says whether the file was cut; readable_files stops at its caps and counts what it left."""

    def test_read_bytes_says_when_the_file_held_more(self):
        self.assertEqual(self.rdt(self.report, 13), (b"weekly report", False))          # exactly the limit is not cut
        self.assertEqual(self.rdt(self.report, 12), (b"weekly repor", True))
        self.assertEqual(self.rdt(self.report, 1000), (b"weekly report", False))
        self.assertEqual(self.rdt(self.report, 0), (b"", True))
        self.assertEqual(self.rdt(touch(self.src / "empty.txt", b""), 0), (b"", False))
        touch(self.src / "big.txt", b"0123456789" * 20000)
        data, cut = self.rdt(self.src / "big.txt", 70000)
        self.assertEqual((len(data), cut), (70000, True))
        self.assertEqual(self.rdt(self.src / "big.txt", 200000)[1], False)
        self.assertEqual(self.rdt(self.src / "big.txt", 199999)[1], True)

    def test_a_file_that_grows_after_the_check_is_cut_and_said_to_be(self):
        f = touch(self.src / "grow.txt", b"12345")
        real_fstat = os.fstat

        def fstat(fd):
            st = real_fstat(fd)
            with open(f, "ab") as more:
                more.write(b"x" * 100000)
            return st
        with mock.patch.object(reach.os, "fstat", fstat):
            self.assertEqual(self.rdt(f, 8), (b"12345xxx", True))

    def test_the_caps_have_sane_defaults(self):
        self.assertGreaterEqual(reach.MAX_FILES, 1000)
        self.assertGreaterEqual(reach.MAX_TOTAL_BYTES, 10 ** 9)
        self.assertGreaterEqual(reach.MAX_DEPTH, 32)
        self.assertGreaterEqual(reach.MAX_ENTRIES, reach.MAX_FILES)
        self.assertTrue(10 <= reach.TIME_BUDGET <= 600)

    def test_too_many_files_stops_the_listing_and_counts_once(self):
        for n in range(5):
            touch(self.src / f"f{n}.txt")
        reasons = {}
        with mock.patch.object(reach, "MAX_FILES", 3):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual(len(files), 3)
        self.assertEqual((skipped, stopped, reasons), (1, True, {reach.TOO_MANY: 1}))

    def test_too_many_bytes_stops_the_listing_and_counts_once(self):
        touch(self.src / "a.txt", b"12345")
        touch(self.src / "b.txt", b"12345")
        touch(self.src / "c.txt", b"12345")
        reasons = {}
        with mock.patch.object(reach, "MAX_TOTAL_BYTES", 12):              # a and b (10 bytes) fit, c would make 15
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual((files, skipped, reasons), ([self.src / "a.txt", self.src / "b.txt"], 1, {reach.TOO_BIG: 1}))
        self.assertTrue(stopped)
        reasons = {}
        with mock.patch.object(reach, "MAX_TOTAL_BYTES", 17):              # 5 + 5 + 5 fits, the 13 does not on top
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual((files, skipped, reasons), ([self.src / "a.txt", self.src / "b.txt", self.src / "c.txt"], 1, {reach.TOO_BIG: 1}))

    def test_a_walk_stopped_in_the_first_folder_does_not_go_on_to_the_second(self):
        touch(self.notes / "n.md")
        reasons = {}
        with mock.patch.object(reach, "MAX_FILES", 1):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual((len(files), skipped, stopped), (1, 1, True))

    def test_folders_nested_deeper_than_the_cap_are_not_entered_and_counted(self):
        touch(self.src / "a" / "one.txt")
        touch(self.src / "a" / "b" / "two.txt")
        touch(self.src / "a" / "b" / "c" / "three.txt")
        touch(self.src / "a" / "b" / "c" / "d" / "four.txt")
        reasons = {}
        with mock.patch.object(reach, "MAX_DEPTH", 2):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual(files, sorted([self.report, self.src / "a" / "one.txt", self.src / "a" / "b" / "two.txt"]))
        self.assertEqual((skipped, reasons), (1, {reach.TOO_DEEP: 1}))                 # c, once; d is never looked at
        self.assertTrue(stopped)

    def test_many_empty_folders_stop_the_listing_and_count_once(self):
        """Attacker LOW: 60,000 empty folders took 109 s and counted nothing, because only passed files were capped."""
        for n in range(30):
            (self.src / f"d{n:02d}").mkdir()
        (self.notes / "n").mkdir()
        reasons = {}
        with mock.patch.object(reach, "MAX_ENTRIES", 10):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual((skipped, stopped, reasons), (1, True, {reach.TOO_MANY_ENTRIES: 1}))     # once, not once per folder
        self.assertLessEqual(len(files), 1)                                     # the walk did not go on to the second folder

    def test_entries_include_the_files_that_are_skipped(self):
        for n in range(12):
            touch(self.src / f"s{n:02d}.env")
        reasons = {}
        with mock.patch.object(reach, "MAX_ENTRIES", 5):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual((files, stopped), ([self.report], True))      # report.txt sorts before the s*.env files
        self.assertEqual(reasons[reach.TOO_MANY_ENTRIES], 1)

    def test_a_listing_that_takes_too_long_stops_and_counts_once(self):
        for n in range(20):
            (self.src / f"d{n:02d}").mkdir()
        ticks = iter(range(10 ** 6))                                              # a clock that moves one second a look
        reasons = {}
        with mock.patch.object(reach, "CLOCK", lambda: next(ticks)), mock.patch.object(reach, "TIME_BUDGET", 4):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual((skipped, stopped, reasons), (1, True, {reach.TOO_SLOW: 1}))

    def test_a_listing_inside_its_time_and_entries_is_complete(self):
        touch(self.src / "a" / "one.txt")
        ticks = iter(range(10 ** 6))
        with mock.patch.object(reach, "CLOCK", lambda: next(ticks) / 1000.0):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), home_dir=self.home)
        self.assertEqual((len(files), skipped, stopped), (2, 0, False))

    def test_a_complete_listing_is_not_stopped(self):
        touch(self.src / "a" / "one.txt")
        touch(self.src / ".env")                                           # skipped for safety, but the list is complete
        files, skipped, stopped = reach.readable_files(self.folders, str(self.data), home_dir=self.home)
        self.assertEqual((len(files), skipped, stopped), (2, 1, False))
        self.assertEqual(reach.readable_files(self.folders, str(self.data), home_dir=self.home).stopped, False)
        self.assertEqual(reach.readable_files([], str(self.data), home_dir=self.home), ([], 0, False))


class Mounts(Reach):
    """L3: a folder or file on another device (st_dev) than the saved folder is not walked into or read."""

    def fake_dev(self, target):
        """os.lstat answers a different st_dev for `target` (a unit test: the temporary volume has no second mount)."""
        real = os.lstat

        def lstat(p, *a, **kw):
            st = real(p, *a, **kw)
            if str(p) != str(target):
                return st
            fake = types.SimpleNamespace(**{k: getattr(st, k) for k in dir(st) if k.startswith("st_")})
            fake.st_dev += 1
            return fake
        return mock.patch.object(reach.os, "lstat", lstat)

    def test_a_file_or_folder_on_another_device_is_never(self):
        mnt = self.src / "mnt"
        f = touch(mnt / "x.txt")
        self.ok(f)
        with self.fake_dev(mnt):
            self.assertEqual(reach._judge(mnt, "read", self.folders, str(self.data), self.home, "folder")[:2], ("never", reach.MOUNT))
        with self.fake_dev(f):
            self.never(f, reach.MOUNT)

    def test_readable_files_does_not_walk_into_another_device(self):
        mnt = self.src / "mnt"
        touch(mnt / "x.txt")
        touch(mnt / "deeper" / "y.txt")
        reasons = {}
        with self.fake_dev(mnt):
            files, skipped, stopped = reach.readable_files(self.folders, str(self.data), reasons, home_dir=self.home)
        self.assertEqual((files, skipped, reasons), ([self.report], 1, {reach.MOUNT: 1}))

    def test_read_bytes_checks_the_open_file_is_on_the_saved_folders_device(self):
        real_fstat = os.fstat

        def fstat(fd):
            st = real_fstat(fd)
            if not stat_is_reg(st):
                return st
            fake = types.SimpleNamespace(**{k: getattr(st, k) for k in dir(st) if k.startswith("st_")})
            fake.st_dev += 1
            return fake
        with mock.patch.object(reach.os, "fstat", fstat), mock.patch.object(reach.os, "read", side_effect=AssertionError("read")):
            with self.assertRaises(reach.Never) as cm:
                self.rd(self.report)
        self.assertEqual(cm.exception.reason, reach.MOUNT)


def stat_is_reg(st):
    import stat
    return stat.S_ISREG(st.st_mode)


class OneDrive(Reach):
    def test_the_dataless_flag_and_size_with_no_blocks_are_placeholders_and_an_empty_file_is_not(self):
        st = lambda **kw: types.SimpleNamespace(**kw)
        flagged = st(st_flags=0x40000000, st_size=10, st_blocks=8)
        no_blocks = st(st_flags=0, st_size=10, st_blocks=0)
        empty = st(st_flags=0, st_size=0, st_blocks=0)
        normal = st(st_flags=0, st_size=10, st_blocks=8)
        no_flags_field = st(st_size=10, st_blocks=8)
        self.assertEqual([reach.online_only_stat(x) for x in (flagged, no_blocks, empty, normal, no_flags_field)],
                         [True, True, False, False, False])           # creaite's expected [False, True, True, False], in this order
        self.assertFalse(reach.online_only(self.tmp / "no-such-file"))

    def test_a_placeholder_is_never_and_never_opened(self):
        with mock.patch.object(reach, "online_only_stat", return_value=True):
            self.never(self.report, reach.ONLINE)
        with mock.patch.object(reach, "online_only_stat", return_value=True), \
                mock.patch.object(reach.os, "open", side_effect=AssertionError("a placeholder was opened")):
            with self.assertRaises(reach.Never) as cm:
                self.rd(self.report)
            self.assertEqual(cm.exception.reason, reach.ONLINE)
            self.assertEqual(reach.readable_files(self.folders, str(self.data), home_dir=self.home), ([], 1, False))

    def test_a_file_that_becomes_a_placeholder_after_the_check_is_not_read(self):
        calls = []
        real_fstat = os.fstat

        def fstat(fd):
            st = real_fstat(fd)
            calls.append(fd)
            return types.SimpleNamespace(st_mode=st.st_mode, st_nlink=st.st_nlink, st_flags=0x40000000, st_size=st.st_size,
                                         st_blocks=0, st_dev=st.st_dev, st_ino=st.st_ino)
        with mock.patch.object(reach.os, "fstat", fstat), mock.patch.object(reach.os, "read", side_effect=AssertionError("read")):
            with self.assertRaises(reach.Never) as cm:
                self.rd(self.report)
        self.assertEqual(cm.exception.reason, reach.ONLINE)

    # A placeholder FOLDER (a dataless directory) needs a real OneDrive volume: not determined here; it is on the hand-check list.


class ListingCost(Reach):
    """The names the disk holds are listed for the saved folder and below it only, not for every folder from "/"."""

    def scandirs_for_read(self, folder):
        f = touch(folder / "a" / "notes.txt", "weekly notes")
        calls = []
        real_scandir = os.scandir

        def scandir(*a, **kw):
            calls.append(a)
            return real_scandir(*a, **kw)
        with mock.patch.object(reach.os, "scandir", scandir):
            self.assertEqual(self.rd(f, folders=[str(folder)]), b"weekly notes")
        return len(calls)

    def test_the_number_of_listings_does_not_grow_with_the_depth_above_the_saved_folder(self):
        shallow = self.scandirs_for_read(self.tmp / "s")
        deep = self.scandirs_for_read(self.tmp.joinpath(*"abcdefghij") / "s")
        deeper = self.scandirs_for_read(self.tmp.joinpath(*"abcdefghijklmnopqrst") / "s")
        self.assertEqual(shallow, deep)
        self.assertEqual(shallow, deeper)
        self.assertLessEqual(shallow, 3)                                  # the saved folder's name, "a" and the file


class ReadBytes(Reach):
    def test_limit_is_honoured_and_a_whole_number(self):
        touch(self.src / "big.txt", b"0123456789" * 20000)
        self.assertEqual(len(self.rd(self.src / "big.txt", 10)), 10)
        self.assertEqual(self.rd(self.src / "big.txt", 10), b"0123456789")
        self.assertEqual(len(self.rd(self.src / "big.txt", 70000)), 70000)         # more than one chunk
        self.assertEqual(self.rd(self.src / "big.txt", 0), b"")
        self.assertEqual(self.rd(self.report, 10 ** 9), b"weekly report")
        for bad in (-1, 1.5, "5", None, True):
            with self.assertRaises(ValueError):
                self.rd(self.report, bad)

    def test_a_file_that_grows_after_the_check_is_still_cut_at_the_limit(self):
        f = touch(self.src / "grow.txt", b"12345")
        real_fstat = os.fstat

        def fstat(fd):
            st = real_fstat(fd)
            with open(f, "ab") as more:
                more.write(b"x" * 100000)
            return st
        with mock.patch.object(reach.os, "fstat", fstat):
            self.assertEqual(len(self.rd(f, 8)), 8)

    def test_bytes_that_are_not_utf8_come_back_as_bytes(self):
        f = touch(self.src / "latin.txt", b"caf\xe9 \xff\xfe")
        self.assertEqual(self.rd(f), b"caf\xe9 \xff\xfe")

    def test_an_empty_file_and_a_file_in_the_second_folder(self):
        self.assertEqual(self.rd(touch(self.src / "empty.txt", b"")), b"")
        self.assertEqual(self.rd(touch(self.notes / "n.md", "n")), b"n")

    def test_the_reason_travels_with_the_refusal_and_holds_no_path(self):
        with self.assertRaises(reach.Never) as cm:
            self.rd(self.secret)
        self.assertEqual(cm.exception.reason, reach.OUTSIDE)
        self.assertNotIn(str(self.tmp), str(cm.exception))

    def test_a_missing_file_is_refused_not_an_error(self):
        with self.assertRaises(reach.Never) as cm:
            self.rd(self.src / "gone.txt")
        self.assertEqual(cm.exception.reason, reach.NOT_THERE)


class Swapped(Reach):
    """A change between the check and the open (TOCTOU). The open is O_NOFOLLOW, one folder at a time."""

    def swapping(self, name, action):
        """os.open wrapper: when `name` is opened relative to a folder, run `action()` first, once."""
        real_open = os.open
        done = []

        def opener(path, flags, *a, **kw):
            if path == name and kw.get("dir_fd") is not None and not done:
                done.append(1)
                action()
            return real_open(path, flags, *a, **kw)
        return mock.patch.object(reach.os, "open", opener)

    def swap_file_for_link(self):
        os.unlink(self.report)
        os.symlink(self.secret, self.report)

    def test_a_file_swapped_for_a_link_after_the_check_is_refused(self):
        with self.swapping("report.txt", self.swap_file_for_link):
            with self.assertRaises(reach.Never) as cm:
                self.rd(self.report)
        self.assertNotIn("TOPSECRET", cm.exception.reason)
        self.assertTrue(self.report.is_symlink())                                  # the swap did happen

    def test_a_folder_on_the_way_swapped_for_a_link_after_the_check_is_refused(self):
        touch(self.src / "sub" / "f.txt", "inner")
        touch(self.outside / "f.txt", SECRET_TEXT)

        def swap():
            os.rename(self.src / "sub", self.src / "sub.old")
            os.symlink(self.outside, self.src / "sub")
        with self.swapping("sub", swap):
            with self.assertRaises(reach.Never):
                self.rd(self.src / "sub" / "f.txt")
        self.assertTrue((self.src / "sub").is_symlink())

    def test_a_second_name_made_after_the_check_is_refused(self):
        with self.swapping("report.txt", lambda: os.link(self.report, self.src / "alias.txt")):
            with self.assertRaises(reach.Never) as cm:
                self.rd(self.report)
        self.assertEqual(cm.exception.reason, reach.LINKED)

    def test_a_file_swapped_for_a_pipe_after_the_check_is_refused_and_does_not_hang(self):
        signal.alarm(5)
        self.addCleanup(signal.alarm, 0)

        def swap():
            os.unlink(self.report)
            os.mkfifo(self.report)
        with self.swapping("report.txt", swap):
            with self.assertRaises(reach.Never) as cm:
                self.rd(self.report)
        self.assertEqual(cm.exception.reason, reach.NOT_FILE)

    def test_without_the_no_follow_flag_the_swapped_link_is_read(self):
        """The mutant that proves the test above bites: remove O_NOFOLLOW and the secret comes out."""
        flags = reach.FILE_FLAGS & ~os.O_NOFOLLOW
        with mock.patch.object(reach, "FILE_FLAGS", flags), self.swapping("report.txt", self.swap_file_for_link):
            self.assertEqual(self.rd(self.report), SECRET_TEXT)


class Mutants(Reach):
    """creaite's habit: each safeguard removed in turn must turn a named check red."""

    def refuses_a_link_out(self):
        (self.src / "mut-link").symlink_to(self.outside, target_is_directory=True)
        return self.kind(self.src / "mut-link" / "secret.txt") == "never"

    def refuses_a_sibling_by_identity(self):
        with mock.patch.object(reach.os.path, "samefile", lambda a, b: str(a) == str(b)):
            return not reach.inside("/a/source/x", "/a/Source")

    def refuses_every_row(self):
        for base, pattern in GOLDEN_ROWS:
            path = (self.home / pattern.replace("*1password*", "x1passwordx") if base == "home" else Path(pattern)) / "f"
            if base == "home":
                touch(path)                       # a file that isn't there is refused anyway; the row is what must refuse it
            if self.kind(path, [str(self.home)]) != "never":
                return False
        return True

    def refuses_a_placeholder(self):
        real = os.lstat

        def lstat(p, *a, **kw):
            st = real(p, *a, **kw)
            if str(p) != str(self.report):
                return st
            return types.SimpleNamespace(st_mode=st.st_mode, st_nlink=1, st_flags=0x40000000, st_size=st.st_size, st_blocks=8,
                                         st_dev=st.st_dev, st_ino=st.st_ino)
        with mock.patch.object(reach.os, "lstat", lstat):
            return self.kind(self.report) == "never"

    def refuses_a_swapped_link(self):
        real_open, done = os.open, []

        def opener(path, flags, *a, **kw):
            if path == "report.txt" and kw.get("dir_fd") is not None and not done:
                done.append(1)
                os.unlink(self.report)
                os.symlink(self.secret, self.report)
            return real_open(path, flags, *a, **kw)
        try:
            with mock.patch.object(reach.os, "open", opener):
                self.rd(self.report)
        except reach.Never:
            return True
        return False

    def refuses_a_secret_name(self):
        return self.kind(touch(self.src / "x" / ".env")) == "never"

    def refuses_a_hard_link(self):
        os.link(self.secret, self.src / "mut-hard")
        return self.kind(self.src / "mut-hard") == "never"

    def test_the_checks_pass_as_written(self):
        for check in (self.refuses_a_link_out, self.refuses_a_sibling_by_identity, self.refuses_every_row, self.refuses_a_placeholder,
                      self.refuses_a_swapped_link, self.refuses_a_secret_name, self.refuses_a_hard_link):
            self.assertTrue(check(), check.__name__)

    def test_realpath_replaced_by_abspath_lets_a_link_out(self):
        with mock.patch.object(reach.os.path, "realpath", os.path.abspath):
            self.assertFalse(self.refuses_a_link_out())

    def test_a_case_folded_compare_in_place_of_identity_lets_a_sibling_in(self):
        with mock.patch.object(reach, "inside", lambda p, r: reach.parts_under(p, r) is not None):
            self.assertFalse(self.refuses_a_sibling_by_identity())

    def test_dropping_one_never_row_turns_the_row_check_red(self):
        path = touch(self.home / ".config" / "gh" / "hosts.yml")
        self.assertEqual(self.kind(path, [str(self.home)]), "never")
        rows = tuple(r for r in reach.never_rows() if r[1] != ".config/gh")
        with mock.patch.object(reach, "never_rows", lambda: rows):
            self.assertEqual(self.kind(path, [str(self.home)]), "ordinary")       # the row was what held it back
            self.assertFalse(self.refuses_every_row())

    def test_dropping_the_placeholder_check_lets_a_placeholder_in(self):
        self.assertTrue(self.refuses_a_placeholder())
        with mock.patch.object(reach, "online_only_stat", lambda st: False):
            self.assertFalse(self.refuses_a_placeholder())

    def test_opening_without_no_follow_lets_a_swapped_link_in(self):
        flags = reach.FILE_FLAGS & ~os.O_NOFOLLOW
        with mock.patch.object(reach, "FILE_FLAGS", flags):
            self.assertFalse(self.refuses_a_swapped_link())

    def test_dropping_the_secret_names_lets_a_dotenv_in(self):
        with mock.patch.object(reach, "SECRET_NAMES", ()):
            self.assertFalse(self.refuses_a_secret_name())

    def test_dropping_the_hard_link_check_lets_a_hard_link_in(self):
        real = os.lstat

        def lstat(p, *a, **kw):
            st = real(p, *a, **kw)
            return types.SimpleNamespace(st_mode=st.st_mode, st_nlink=1, st_flags=getattr(st, "st_flags", 0), st_size=st.st_size,
                                         st_blocks=getattr(st, "st_blocks", 1), st_dev=st.st_dev, st_ino=st.st_ino)
        with mock.patch.object(reach.os, "lstat", lstat):
            self.assertFalse(self.refuses_a_hard_link())

    def test_dropping_the_data_row_lets_the_database_in(self):
        self.assertEqual(self.kind(self.db, [str(self.home)]), "never")
        kind = reach.classify(str(self.db), "read", [str(self.home)], str(self.tmp / "somewhere-else"), home_dir=self.home)[0]
        self.assertEqual(kind, "ordinary")                                      # a data folder that isn't passed is what the row guards


class Source(unittest.TestCase):
    """The copies are standard library only, touch no database, write nothing, and are recorded."""

    FILES = ("reach.py", "edit_ai.py", "confusables.py")
    FORBIDDEN_IMPORTS = {"tracker", "store", "paths", "sqlite3", "subprocess", "socket", "urllib", "http", "ssl", "ctypes", "settings",
                         "requests", "shutil", "tempfile", "permissions", "notes", "log"}
    WRITES = {"remove", "unlink", "rename", "renames", "replace", "rmdir", "removedirs", "mkdir", "makedirs", "symlink", "link", "write",
              "truncate", "ftruncate", "chmod", "chown", "utime", "mkfifo", "mknod", "O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC",
              "O_APPEND", "O_EXCL"}
    WRITE_METHODS = {"write_text", "write_bytes", "unlink", "rmdir", "touch", "mkdir", "rename", "symlink_to", "hardlink_to"}

    def trees(self):
        for name in self.FILES:
            path = SRC / "clark" / name
            yield name, ast.parse(path.read_text(encoding="utf-8"))

    def test_only_the_standard_library_and_clark_platform(self):
        for name, tree in self.trees():
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                for m in mods:
                    self.assertNotIn(m.split(".")[0], self.FORBIDDEN_IMPORTS, f"{name}: imports {m}")
                    if m.startswith("clark"):
                        self.assertIn(m, ("clark", "clark.platform", "clark.confusables", "clark.edit_ai"), f"{name}: imports {m}")
                if isinstance(node, ast.ImportFrom) and node.module == "clark":
                    for a in node.names:
                        self.assertIn(a.name, ("platform", "confusables", "edit_ai"), f"{name}: imports clark.{a.name}")

    def test_nothing_writes_removes_or_renames(self):
        for name, tree in self.trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os":
                    self.assertNotIn(node.attr, self.WRITES, f"{name}:{node.lineno}: os.{node.attr}")
                if isinstance(node, ast.Attribute) and node.attr in self.WRITE_METHODS:
                    self.fail(f"{name}:{node.lineno}: .{node.attr}")
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
                    mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else "r"
                    self.assertFalse(set(str(mode)) & set("wax+"), f"{name}:{node.lineno}: open() in write mode")

    def test_no_system_folder_text_outside_platform_py(self):
        for name, tree in self.trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    for text in ("Library/Application Support", "~/Library", "osascript"):
                        self.assertNotIn(text, node.value, name)

    def test_no_sql(self):
        for name, tree in self.trees():
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    self.assertFalse(node.value.lstrip().upper().startswith(("SELECT ", "INSERT ", "UPDATE ", "DELETE ")), name)

    def test_the_copies_are_recorded(self):
        text = (ROOT / "docs" / "REUSE-FROM-CREAITE.md").read_text(encoding="utf-8")
        for path, where in (("system/scripts/reach.py", "src/clark/reach.py"), ("system/scripts/edit_ai.py", "src/clark/edit_ai.py"),
                            ("system/scripts/confusables.py", "src/clark/confusables.py")):
            row = next((line for line in text.splitlines() if f"`{path}`" in line and line.startswith("|")), "")
            self.assertIn("db5adb2", row, path)
            self.assertIn(where, row, path)
        reach_row = next(line for line in text.splitlines() if "`system/scripts/reach.py`" in line and line.startswith("|"))
        edit_row = next(line for line in text.splitlines() if "`system/scripts/edit_ai.py`" in line and line.startswith("|"))
        for row in (reach_row, edit_row):
            self.assertIn("Yes", row)
            self.assertIn("Full review (#47b)", row)
        conf_row = next(line for line in text.splitlines() if "`system/scripts/confusables.py`" in line and line.startswith("|"))
        self.assertIn("No", conf_row)
        self.assertIn("is_online_only", reach_row)
        self.assertIn("never_read_places", reach_row)
        self.assertIn("v2.6.11", reach_row)                                       # the later fold was considered and met by identity
        self.assertIn("O_NOFOLLOW", reach_row)


if __name__ == "__main__":
    unittest.main()

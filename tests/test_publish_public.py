"""#94: the tool that publishes a clean public copy (dev/tools/publish_public.py) refuses what it must and pushes one
neutral commit.

Run: python3 dev/run_tests.py test_publish_public
Everything here uses temporary git repos on this machine: the "private" repo is a folder, the "public" repo is a bare
folder, and nothing touches the network. The test runner and the `gh` check are faked. Names are fictional (the name
guard is given a fictional banned list); secrets are built from pieces at run time, so this file holds none.
Your git settings are made hostile on purpose (a real-looking identity, signing on, a pre-push hook, another time zone)
to show none of it reaches the published commit.
"""
import base64
import io
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _paths  # noqa: F401  (puts dev/tools/ on the path)
import publish_public as pp
from test_no_real_names import FICTIONAL

HANDOVER = pp.reveal("qbpf/UNAQBIRE-EBZNABSS.zq")                    # file names that hold a person's name: kept ROT13, as in the tool
HANDOVER_OTHER = pp.reveal("qbpf/ABGRF-SBE-GUR-BGURE-EBZNABSS.zq")
OWNER, REPO_NAME = "example-owner", "sample-repo"          # a fictional private repo: its name is only ever built here
ORIGIN = "https://github.com/%s/%s.git" % (OWNER, REPO_NAME)
NOW = 1_700_000_000
SAFE = {"PATH": os.environ.get("PATH", os.defpath), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test Author", "GIT_COMMITTER_EMAIL": "test@example.invalid"}


def sh(*args, cwd=None):
    proc = subprocess.run(["git"] + list(args), cwd=cwd, env=dict(SAFE, HOME=str(cwd or tempfile.gettempdir())),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError("git %s: %s" % (" ".join(args), proc.stderr.decode()))
    return proc.stdout.decode("utf-8", "replace").strip()


def office(xml, name="word/document.xml"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, xml)
    return buf.getvalue()


def secrets():
    """Fake secrets, assembled here so no source file holds one."""
    return {
        "key": "-----BEGIN " + "OPENSSH PRIVATE KEY-----\nAAAA\n",
        "github": "token ghp_" + "A1b2C3d4" * 5,
        "pat": "github_pat_" + "11ABCDEFG0" * 4,
        "aws": "AKIA" + "ABCDEFGHIJKLMNOP",
        "slack": "xoxb-" + "1234567890-abcdefghij",
        "jwt": "eyJ" + "hbGciOiJIUzI1" + "." + "eyJzdWIiOiIxMjM0" + "." + "abcdefghijklmnop",
        "generic": 'api_key = "' + "k9" * 12 + '"',
    }


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.home = self.tmp / "home"
        self.hooks = self.tmp / "hooks"
        self.marker = self.tmp / "hook-ran"
        self.home.mkdir()
        self.hooks.mkdir()
        hook = self.hooks / "pre-push"
        hook.write_text("#!/bin/sh\ntouch '%s'\nexit 1\n" % self.marker, encoding="utf-8")
        hook.chmod(0o755)
        self.gitconfig = self.home / ".gitconfig"
        self.gitconfig.write_text("[user]\n\tname = Real Person\n\temail = real.person@corp.example\n[commit]\n"
                                  "\tgpgsign = true\n[core]\n\thooksPath = %s\n" % self.hooks, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=str(self.home), TZ="Pacific/Auckland", GIT_AUTHOR_NAME="Env Person",
                   GIT_AUTHOR_EMAIL="env.person@corp.example", GIT_COMMITTER_NAME="Env Person",
                   GIT_COMMITTER_EMAIL="env.person@corp.example")
        patch = mock.patch.dict(os.environ, env, clear=True)
        patch.start()
        self.addCleanup(patch.stop)
        self.public = self.tmp / "public.git"
        sh("init", "-q", "--bare", str(self.public))
        self.runs = []
        self.gh_asked = []

    # --- the private repo
    def make_private(self, files, ignored=None, forced=None, origin=ORIGIN, name="private"):
        root = self.tmp / name
        root.mkdir()
        sh("init", "-q", cwd=root)
        sh("symbolic-ref", "HEAD", "refs/heads/main", cwd=root)
        everything = dict({".gitignore": "comms/\nsystem/branding/\n"}, **files)
        for rel, data in list(everything.items()) + list((ignored or {}).items()) + list((forced or {}).items()):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        sh("add", "-A", cwd=root)
        for rel in forced or {}:
            sh("add", "-f", rel, cwd=root)
        sh("commit", "-q", "-m", "work", cwd=root)
        sh("update-ref", "refs/remotes/origin/main", "HEAD", cwd=root)
        if origin:
            sh("remote", "add", "origin", origin, cwd=root)
        self.private = root
        return root

    def commit_more(self, files, message="more"):
        for rel, data in files.items():
            (self.private / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.private / rel).write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        sh("add", "-A", cwd=self.private)
        sh("commit", "-q", "-m", message, cwd=self.private)
        sh("update-ref", "refs/remotes/origin/main", "HEAD", cwd=self.private)

    # --- running the tool
    def fake_tests(self, python, checkout):
        self.runs.append((python, sorted(p.relative_to(checkout).as_posix() for p in Path(checkout).rglob("*")
                                         if p.is_file() and ".git/" not in p.as_posix())))
        return python != "bad", {"old": "3.9", "new": "3.15", "bad": "3.12", "same": "3.9"}.get(python, "3.9")

    def fake_gh(self, owner, name):
        self.gh_asked.append((owner, name))
        return getattr(self, "gh_says_public", True)

    def go(self, *flags, ref="main", target=None, banned=FICTIONAL, local=True, run_tests=None, spy=None):
        argv = [] if target is False else ["--target=" + (str(self.public) if target is None else target)]
        argv += ["--pythons", "old,new"] + (["--allow-local-target"] if local else []) + list(flags) + ["--", ref]
        lines = []
        kwargs = dict(repo=self.private, run_tests=run_tests or self.fake_tests, is_public=self.fake_gh, banned=banned,
                      out=lines.append, now=lambda: NOW)
        if spy is None:
            code = pp.run(pp.parse_args(argv), **kwargs)
        else:
            real = subprocess.run

            def recording(cmd, *a, **kw):
                spy.append((list(cmd), kw))
                return real(cmd, *a, **kw)

            with mock.patch.object(pp.subprocess, "run", recording):
                code = pp.run(pp.parse_args(argv), **kwargs)
        return code, "\n".join(lines)

    # --- looking at the public repo
    def heads(self):
        return sh("for-each-ref", "--format=%(refname)", cwd=self.public).split()

    def commits(self, branch="clark-public"):
        out = sh("rev-list", branch, cwd=self.public)
        return out.split()

    def tree(self, branch="clark-public"):
        return sh("ls-tree", "-r", "--name-only", branch, cwd=self.public).splitlines()

    def refused(self, *flags, **kw):
        code, out = self.go(*flags, **kw)
        self.assertEqual(code, 1, out)
        self.assertEqual(self.heads(), [], "something was pushed")
        self.assertIn("REFUSED", out)
        return out


PRIVATE_README = "# demo (private)\nPrivate repo.\n"
PUBLIC_README = "# demo\nThe public text.\n"
GOOD = {"README.md": PRIVATE_README, "docs/public/README.md": PUBLIC_README, "src/app.py": "print('hi')\n",
        "docs/RULES.md": "rules\n"}
NOTES = {"dev/HEAD-LOG.md": "log", "docs/DECISIONS.md": "d", HANDOVER: "h",
         HANDOVER_OTHER: "n", "docs/TEAM-AND-ROLES.md": "t", ".claude/settings.json": "{}",
         ".claude/skills/x/SKILL.md": "s"}
KEPT = {"docs/handoff/a.md": "a", "docs/handoff/sub/b.md": "b"}          # the tests read docs/handoff/: it is published


class TheExclusionList(Base):
    def test_the_list_is_pinned_to_the_issue(self):
        self.assertEqual(pp.EXCLUDED, ("dev/HEAD-LOG.md", "docs/DECISIONS.md", HANDOVER,
                                       HANDOVER_OTHER, "docs/TEAM-AND-ROLES.md", ".claude/",
                                       "comms/", "system/branding/"))
        self.assertEqual((pp.PUBLIC_README_SOURCE, pp.PUBLIC_README, pp.PUBLIC_SOURCE_DIR),
                         ("docs/public/README.md", "README.md", "docs/public/"))

    def test_what_matches(self):
        for path in ("dev/HEAD-LOG.md", "docs/DECISIONS.md", ".claude/settings.json", ".claude/skills/x/SKILL.md",
                     ".CLAUDE/x", "docs/TEAM-AND-ROLES.md", "docs/team-and-roles.md", "comms/a.md",
                     "comms/x/y/z.pptx", "system/branding/logo.png", "system/branding/a/b", "Comms/Notes.md",
                     "SYSTEM/Branding/x", "docs/decisions.md", HANDOVER,
                     "docs/public/README.md", "docs/public/x/y.md", "Docs/Public/a"):
            self.assertTrue(pp.is_excluded(path), path)
        for path in ("docs/handoff/a.md", "docs/handoff/x/y.md", "docs/handoff.md", "docs/publicity.md", "docs/public.md",
                     "src/docs/public/a", "x.claude/a", "claude/a", "src/.claude/a", "docs/handoffs/a.md", "xcomms/a.md",
                     "docs/DECISIONS.md.bak", "dev/HEAD-LOG.mdx",
                     "system/brandingx/a", "system/prototype/branding/a", "docs/RULES.md", "src/comms/a.py"):
            self.assertFalse(pp.is_excluded(path), path)

    def test_excluded_files_are_absent_whether_ignored_or_force_added(self):
        self.make_private(dict(GOOD, **dict(NOTES, **KEPT)),
                          ignored={"system/branding/logo.png": "x", "comms/plan.md": "x"})
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.tree(), [".gitignore", "README.md", "docs/RULES.md", "docs/handoff/a.md", "docs/handoff/sub/b.md",
                                       "src/app.py"])

    def test_a_force_added_file_under_comms_or_branding_is_a_refusal_not_a_removal(self):
        for forced in ({"comms/forced.md": "x"}, {"system/branding/forced.css": "x"}, {"Comms/Upper.md": "x"},
                       {"comms/deep/er/f.md": "x", "system/branding/a.png": "y"}):
            with self.subTest(sorted(forced)):
                self.setUp()
                self.make_private(dict(GOOD, **NOTES), forced=forced)
                self.assertIn(sorted(forced)[0], sh("ls-files", cwd=self.private))   # the force-add worked in the setup
                for flags in ((), ("--dry-run",)):
                    code, out = self.go(*flags)
                    self.assertEqual(code, 1, out)
                    self.assertEqual(self.heads(), [])
                    self.assertIn("REFUSED  nothing private is tracked", out)
                    self.assertRegex(out, r"file #\d+ is tracked under comms/ or system/branding/")
                    for name in forced:
                        self.assertNotIn(name, out.split("Checks:")[1])
                    self.assertNotIn("Traceback", out)
                self.assertEqual(self.runs, [])

    def test_the_notes_files_are_still_removed_quietly(self):
        self.make_private(dict(GOOD, **NOTES))
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS     nothing private is tracked", out)

    def test_docs_handoff_is_published_because_the_tests_read_it(self):
        self.make_private(dict(GOOD, **KEPT))
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(sh("show", "clark-public:docs/handoff/a.md", cwd=self.public), "a")
        self.assertFalse([r for r in pp.EXCLUDED if r.startswith("docs/handoff")])

    def test_the_how_to_names_every_excluded_path(self):
        how_to = (Path(__file__).resolve().parents[1] / "docs" / "publishing-the-public-copy.md").read_text(encoding="utf-8")
        for rule in pp.EXCLUDED + (pp.PUBLIC_README_SOURCE, pp.PUBLIC_SOURCE_DIR):
            if not pp.names_listed_word(rule):                     # a file name that holds a person's name is not written in the how-to
                self.assertIn(rule, how_to)
        self.assertIn("docs/handoff/` is published", how_to)
        for words in ("refuses", "worktree", "SIGTERM", "comms/", "system/branding/"):
            self.assertIn(words, how_to)

    def test_the_private_repos_name_is_not_written_in_the_published_files(self):
        here = Path(__file__).resolve().parents[1]
        origin = subprocess.run(["git", "-C", str(here), "config", "--get", "remote.origin.url"], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE).stdout.decode().strip()
        parsed = pp.parse_target(origin) if origin else None
        if not parsed or parsed[0] != "url":
            self.skipTest("no origin here (this is the public copy, or a bare checkout)")
        for rel in ("dev/tools/publish_public.py", "docs/publishing-the-public-copy.md", "docs/public/README.md",
                    "tests/test_publish_public.py"):
            path = here / rel
            if path.exists():
                self.assertNotIn(parsed[2], path.read_text(encoding="utf-8").lower(), rel)
        self.assertFalse(hasattr(pp, "PRIVATE_REPOS"))


class ThePublicReadme(Base):
    def test_the_snapshots_readme_is_the_public_one_and_its_source_folder_is_absent(self):
        self.make_private(dict(GOOD, **{"docs/public/extra.md": "x", "docs/public/sub/y.md": "y"}))
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertEqual(sh("cat-file", "blob", "clark-public:README.md", cwd=self.public), PUBLIC_README.strip())
        self.assertEqual(sh("rev-parse", "clark-public:README.md", cwd=self.public),
                         sh("rev-parse", "HEAD:docs/public/README.md", cwd=self.private))
        self.assertNotEqual(sh("rev-parse", "clark-public:README.md", cwd=self.public),
                            sh("rev-parse", "HEAD:README.md", cwd=self.private))
        self.assertEqual(self.tree(), [".gitignore", "README.md", "docs/RULES.md", "src/app.py"])

    def test_the_bytes_are_the_same_even_with_odd_line_endings(self):
        raw = b"# demo\r\nline\r\n\xc3\xa9 no final newline"
        self.make_private(dict(GOOD, **{"docs/public/README.md": raw}))
        self.assertEqual(self.go()[0], 0)
        got = subprocess.run(["git", "cat-file", "blob", "clark-public:README.md"], cwd=str(self.public),
                             stdout=subprocess.PIPE, env=dict(SAFE)).stdout
        self.assertEqual(got, raw)

    def test_a_commit_without_a_private_readme_still_gets_the_public_one(self):
        files = dict(GOOD)
        del files["README.md"]
        self.make_private(files)
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(sh("show", "clark-public:README.md", cwd=self.public), PUBLIC_README.strip())

    def test_a_readme_in_another_letter_case_does_not_stay_beside_it(self):
        files = dict(GOOD, **{"Readme.md": "# other\n"})
        del files["README.md"]
        self.make_private(files)
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(self.tree(), [".gitignore", "README.md", "docs/RULES.md", "src/app.py"])

    def test_without_the_public_readme_it_refuses_plainly_and_pushes_nothing(self):
        files = dict(GOOD)
        del files["docs/public/README.md"]
        self.make_private(files)
        out = self.refused()
        self.assertIn("REFUSED  public README", out)
        self.assertIn("docs/public/README.md is missing", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(self.runs, [])
        code, out = self.go("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("docs/public/README.md is missing", out)

    def test_a_linked_public_readme_is_not_accepted(self):
        files = dict(GOOD)
        del files["docs/public/README.md"]
        self.make_private(files)
        (self.private / "docs" / "public").mkdir(parents=True)
        (self.private / "docs" / "public" / "README.md").symlink_to("../../README.md")
        sh("add", "-A", cwd=self.private)
        sh("commit", "-q", "-m", "link", cwd=self.private)
        sh("update-ref", "refs/remotes/origin/main", "HEAD", cwd=self.private)
        self.assertIn("public README", self.refused())

    def test_the_name_guard_reads_the_public_readme_and_points_at_its_source(self):
        self.make_private(dict(GOOD, **{"docs/public/README.md": "# demo\nBy Zoe Quill\n"}))
        out = self.refused()
        number = int(re.search(r"file #(\d+) line 2", out).group(1))
        listing = sh("ls-tree", "-r", "--name-only", "HEAD", cwd=self.private).splitlines()
        self.assertEqual(listing[number - 1], "docs/public/README.md")
        self.assertNotRegex(out.lower(), r"zoe|quill")

    def test_the_real_public_readme_in_this_repo_is_plain(self):
        here = Path(__file__).resolve().parents[1] / "docs" / "public" / "README.md"
        if not here.exists():
            self.skipTest("this is the public copy: docs/public/ is not in it")
        text = here.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# clark\n"))
        self.assertIn("python3 dev/run_tests.py", text)
        self.assertIn("## Licence", text)                                       # the LICENSE file is in the repo and the README points to it
        self.assertIn("`LICENSE`", text)
        self.assertNotIn("no licence yet", text)
        self.assertIn("python3 -m clark --demo", text)                          # the launcher is on main
        self.assertNotIn("holds one snapshot", text)                            # each publish adds one snapshot on top of the last
        self.assertNotIn("with no history", text)


class TheOddPaths(Base):
    ODD = ("sp ace.md", "quo\"te.md", "\"starts-with-quote.md", "caf\u00e9/\u00fcber.md", "\u4e2d\u6587.md", "+plus.md", "-dash.md",
           "back\\slash.md", "dir with space/f g.md", "tab\there.md")

    def names_z(self, branch="clark-public"):
        out = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", branch], cwd=str(self.public), env=dict(SAFE),
                             stdout=subprocess.PIPE).stdout
        return sorted(p.decode("utf-8") for p in out.split(b"\0") if p)

    def test_paths_with_spaces_quotes_and_non_ascii_come_through_unchanged(self):
        odd = [p for p in self.ODD if "\\" not in p and "\t" not in p]
        self.make_private(dict(GOOD, **{p: "content of " + p for p in odd}))
        sh("config", "core.quotepath", "true", cwd=self.private)
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.names_z(), sorted([".gitignore", "README.md", "docs/RULES.md", "src/app.py"] + odd))
        for p in odd:
            shown = subprocess.run(["git", "cat-file", "blob", "clark-public:" + p], cwd=str(self.public), env=dict(SAFE),
                                   stdout=subprocess.PIPE).stdout.decode()
            self.assertEqual(shown, "content of " + p)

    def test_the_quotepath_setting_changes_nothing(self):
        files = dict(GOOD, **{"caf\u00e9.md": "x", "\"q\".md": "y"})
        for value in ("true", "false"):
            self.setUp()
            self.make_private(files)
            sh("config", "core.quotepath", value, cwd=self.private)
            self.assertEqual(self.go()[0], 0)
            self.assertIn("caf\u00e9.md", self.names_z())
            self.assertIn("\"q\".md", self.names_z())

    def test_a_path_with_a_newline_or_control_character_is_refused_without_printing_it(self):
        for bad in ("two\nlines.md", "bell\x07.md"):
            with self.subTest(bad):
                self.setUp()
                self.make_private(dict(GOOD, **{bad: "x"}))
                out = self.refused()
                self.assertIn("has an unsafe path", out)
                self.assertNotIn("lines.md", out)
                self.assertNotIn("Traceback", out)

    def test_hash_object_is_given_paths_as_arguments_not_as_a_quoted_list(self):
        seen = []
        real = pp.git

        def watching(args, **kw):
            if "hash-object" in args:
                seen.append(list(args))
                self.assertNotIn("--stdin-paths", args)
            return real(args, **kw)

        self.make_private(dict(GOOD, **{"\"q.md": "x", "+p.md": "y"}))
        with mock.patch.object(pp, "git", watching):
            self.assertEqual(self.go()[0], 0)
        self.assertTrue(seen)
        self.assertTrue(all("--" in a for a in seen))
        self.assertIn('"q.md', [x for a in seen for x in a])

    def test_many_files_are_hashed_in_chunks(self):
        self.make_private(dict(GOOD, **{"many/f%03d.md" % i: "n%d" % i for i in range(pp.HASH_CHUNK * 2 + 3)}))
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(len([n for n in self.tree() if n.startswith("many/")]), pp.HASH_CHUNK * 2 + 3)


class TheWriteFailures(Base):
    def test_a_file_with_the_name_of_a_folder_is_refused_plainly(self):
        self.make_private(GOOD)
        blob = sh("rev-parse", "HEAD:src/app.py", cwd=self.private)
        for path in ("a", "A/b"):                                               # one folder in git's eyes, a clash on a Mac
            sh("update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, path), cwd=self.private)
        sh("commit", "-q", "-m", "clash", cwd=self.private)
        sh("update-ref", "refs/remotes/origin/main", "HEAD", cwd=self.private)
        out = self.refused()
        self.assertIn("has the same name as a folder holding other files", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(self.runs, [])

    def test_a_disk_error_while_writing_is_a_plain_refusal_not_a_traceback(self):
        entries = [pp.Entry(1, "100644", "0" * 40, 1, "a"), pp.Entry(2, "100644", "1" * 40, 1, "a/b")]
        with self.assertRaises(pp.TargetError) as caught:
            pp.write_repo(self.tmp / "w", entries, [b"x", b"y"], dict(SAFE), [])
        self.assertIn("could not be written out", str(caught.exception))
        self.assertNotIn("a/b", str(caught.exception))

    def test_a_disk_error_anywhere_in_a_run_is_reported_plainly(self):
        self.make_private(GOOD)
        boom = OSError(28, "No space left on device", "/secret/Some-Name.md")
        for target in ("read_blobs", "write_repo"):
            with self.subTest(target):
                lines = []
                with mock.patch.object(pp, target, side_effect=boom):
                    code = pp.run(pp.parse_args(["--target", str(self.public), "--allow-local-target", "--pythons", "old,new", "main"]),
                                  repo=self.private, run_tests=self.fake_tests, is_public=self.fake_gh, banned=FICTIONAL,
                                  out=lines.append, now=lambda: NOW)
                out = "\n".join(lines)
                self.assertEqual(code, 1, out)
                self.assertIn("REFUSED", out)
                self.assertIn("No space left on device", out)
                self.assertNotIn("Some-Name", out)
                self.assertEqual(self.heads(), [])


class ThePushFailure(Base):
    def fail_with(self, stderr):
        fake = subprocess.CompletedProcess([], 1, b"", stderr)
        lines = []
        with mock.patch.object(pp, "git", return_value=fake):
            code = pp.push(pp.parse_args(["main"]), self.tmp, "x", lines.append)
        return code, "\n".join(lines)

    def test_git_output_is_never_printed(self):
        leaks = ("ghp_" + "A1b2C3d4" * 5, "https://user:" "hunter2@github.com/some-owner/some-repo.git", "some-owner/some-repo",
                 "/Users/someone/secret-folder", "Some Person")
        bodies = (
            "remote: Invalid username or password for '%s'\nfatal: Authentication failed for '%s'\n%s %s",
            " ! [rejected]        HEAD -> clark-public (fetch first)\nerror: failed to push some refs to '%s'\n%s %s %s",
            "remote: error: GH006: Protected branch update failed for refs/heads/main %s %s %s %s",
            "fatal: unable to access '%s': Could not resolve host %s %s %s",
            "something odd happened at %s %s %s %s",
        )
        for body in bodies:
            with self.subTest(body[:30]):
                code, out = self.fail_with(body.replace("%s", " ".join(leaks)).encode())
                self.assertEqual(code, 1)
                self.assertIn("PUSH FAILED: nothing was changed on the target", out)
                self.assertEqual(len(out.splitlines()), 1, out)
                for leak in leaks + ("hunter2", "https://", "ghp_", "fatal", "remote:"):
                    self.assertNotIn(leak, out)

    def test_the_reason_is_plain(self):
        for text_, word in (("! [rejected] (fetch first)", "moved on"), ("remote: Permission denied", "sign-in"),
                            ("remote: error: GH006 protected branch hook declined", "refused the push"),
                            ("fatal: unable to access: Could not resolve host", "could not be reached"), ("???", "not shown")):
            self.assertIn(word, self.fail_with(text_.encode())[1], text_)

    def test_a_real_failed_push_prints_no_address_and_no_path(self):
        self.make_private(GOOD)
        objects = self.public / "objects"
        os.chmod(str(objects), 0o555)                                           # git cannot write there
        self.addCleanup(os.chmod, str(objects), 0o755)
        if os.access(str(objects), os.W_OK):
            self.skipTest("this account can write anywhere (root)")
        code, out = self.go()
        self.assertEqual(code, 1, out)
        self.assertIn("PUSH FAILED", out)
        self.assertNotIn(str(self.public), out)
        self.assertNotIn("error:", out)
        self.assertNotIn("fatal", out)
        self.assertEqual(self.heads(), [])


class ThePublish(Base):
    def test_one_commit_by_clark_with_the_files_exactly_as_they_are(self):
        crlf = b"line one\r\nline two\r\n"
        self.make_private(dict(GOOD, **{"keep.bat": crlf, "run.sh": "#!/bin/sh\n"}))
        sh("update-index", "--chmod=+x", "run.sh", cwd=self.private)
        sh("commit", "-q", "-m", "x", cwd=self.private)
        sh("update-ref", "refs/remotes/origin/main", "HEAD", cwd=self.private)
        sh("tag", "v0.1.0", cwd=self.private)
        calls = []
        code, out = self.go(ref="v0.1.0", spy=calls)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.heads(), ["refs/heads/clark-public"])
        self.assertEqual(len(self.commits()), 1)
        raw = sh("cat-file", "commit", "clark-public", cwd=self.public)
        short = sh("rev-parse", "--short=7", "v0.1.0^{commit}", cwd=self.private)
        ident = "clark <clark@users.noreply.github.com> %d +0000" % NOW
        self.assertEqual(raw.split("\n", 1)[1], "author %s\ncommitter %s\n\nclark v0.1.0 (%s)" % (ident, ident, short))
        self.assertEqual(sh("tag", "-l", cwd=self.public), "")
        self.assertEqual(sh("show", "clark-public:keep.bat", cwd=self.public), crlf.decode().strip())
        for rel in ("keep.bat", "run.sh"):
            same = sh("rev-parse", "HEAD:" + rel, cwd=self.private) == sh("rev-parse", "clark-public:" + rel, cwd=self.public)
            self.assertTrue(same, rel)
        self.assertEqual(sh("rev-parse", "HEAD:docs/public/README.md", cwd=self.private),
                         sh("rev-parse", "clark-public:README.md", cwd=self.public))
        self.assertEqual(sh("ls-tree", "clark-public", "run.sh", cwd=self.public).split()[0], "100755")
        self.assertFalse(self.marker.exists(), "the pre-push hook from your settings ran")

    def test_nothing_of_the_local_settings_reaches_the_commit(self):
        self.make_private(GOOD)
        before = self.gitconfig.read_bytes()
        config = (self.private / ".git" / "config").read_bytes()
        code, out = self.go()
        self.assertEqual(code, 0, out)
        everything = sh("cat-file", "commit", "clark-public", cwd=self.public) + sh("log", "--format=raw", "clark-public", cwd=self.public)
        for leak in ("Real Person", "real.person", "Env Person", "env.person", "corp.example", "Test Author", "example.invalid",
                     "gpgsig", "+1300", "+1200", "encoding"):
            self.assertNotIn(leak, everything)
        self.assertEqual(self.gitconfig.read_bytes(), before)
        self.assertEqual((self.private / ".git" / "config").read_bytes(), config)
        self.assertFalse(self.marker.exists())

    def test_the_identity_can_only_change_by_flags(self):
        self.make_private(GOOD)
        code, out = self.go("--author-name", "someone", "--author-email", "s@example.invalid")
        self.assertEqual(code, 0, out)
        self.assertIn("someone <s@example.invalid> %d +0000" % NOW, sh("cat-file", "commit", "clark-public", cwd=self.public))

    def test_a_second_publish_goes_on_top_and_an_unchanged_tree_publishes_nothing(self):
        self.make_private(GOOD)
        self.assertEqual(self.go()[0], 0)
        first = self.commits()
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertIn("Nothing to publish", out)
        self.assertEqual(self.commits(), first)
        self.commit_more({"docs/new.md": "more\n"})
        calls = []
        code, out = self.go(spy=calls)
        self.assertEqual(code, 0, out)
        both = self.commits()
        self.assertEqual(len(both), 2)
        self.assertEqual(both[1], first[0])                                     # a chain of snapshots
        self.assertEqual(sh("rev-list", "--count", "clark-public", cwd=self.public), "2")
        self.assertIn("docs/new.md", self.tree())
        self.assertEqual(sh("log", "--format=%an|%cn", "clark-public", cwd=self.public).split("\n"), ["clark|clark"] * 2)

    def test_the_old_tests_are_not_run_when_there_is_nothing_new(self):
        self.make_private(GOOD)
        self.go()
        self.runs.clear()
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(self.runs, [])

    def test_never_a_force_a_tag_a_mirror_or_a_delete(self):
        self.make_private(GOOD)
        calls = []
        self.assertEqual(self.go(spy=calls)[0], 0)
        self.commit_more({"b.md": "b"})
        self.assertEqual(self.go(spy=calls)[0], 0)
        git_calls = [c for c, kw in calls if c[0] == "git"]
        self.assertTrue(git_calls)
        for cmd in git_calls:
            for arg in cmd:
                self.assertNotIn(arg, pp.FORBIDDEN_GIT_ARGS | {"--force", "-f", "--mirror", "--tags", "--delete"}, cmd)
                self.assertFalse(arg.startswith("+") or arg.startswith(":") or arg.startswith("--force"), cmd)
        pushes = [c for c in git_calls if "push" in c]
        self.assertEqual(len(pushes), 2)
        for cmd in pushes:
            self.assertEqual(cmd[-3:], ["--porcelain", str(self.public.resolve()), "HEAD:refs/heads/clark-public"])
        for cmd, kw in calls:
            self.assertFalse(kw.get("shell"), cmd)
            self.assertIsInstance(cmd, list)

    def test_the_tool_itself_refuses_a_dangerous_git_command(self):
        for bad in (["push", "--force", "x"], ["push", "-f"], ["push", "--mirror"], ["push", "--tags"], ["push", "--delete"],
                    ["push", "x", "+HEAD:refs/heads/a"], ["push", "x", ":refs/heads/a"], ["push", "--force-with-lease"]):
            with self.assertRaises(pp.Unsafe):
                pp.git(bad, env={})

    def test_main_needs_its_flag(self):
        self.make_private(GOOD)
        self.assertIn("--publish-main", self.refused("--branch", "main"))
        code, out = self.go("--branch", "main", "--publish-main")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.heads(), ["refs/heads/main"])

    def test_a_release_gate_branch(self):
        self.make_private(GOOD)
        code, out = self.go("--branch", "release-0.1.0")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.heads(), ["refs/heads/release-0.1.0"])

    def test_other_branch_names_are_refused(self):
        self.make_private(GOOD)
        for bad in ("feature/x", "release-1.0", "release-1.0.0.1", "release-1.0.x", "Main", "master", "release-1.0.0/x",
                    "clark-public2", "--delete"):
            self.refused("--branch=" + bad)

    def test_a_trailing_newline_or_other_scripts_digits_are_not_a_release_branch(self):
        self.make_private(GOOD)
        for bad in ("release-1.2.3\n", "release-1.2.3\r", "release-1.2.3 ", "release-\u0661.\u0662.\u0663", "release-1.2.\u0663",
                    "release-\uff11.\uff12.\uff13", "release-1.2.3\n\n"):
            with self.subTest(repr(bad)):
                out = self.refused("--branch=" + bad)
                self.assertIn("REFUSED  branch name", out)
        for good in ("release-1.2.3", "release-10.20.30", "release-0.0.0"):
            report = pp.Report()
            pp.check_branch(pp.parse_args(["--branch", good, "--", "main"]), report)
            self.assertEqual(report.status("branch name"), pp.PASS, good)

    def test_temporary_folders_are_removed(self):
        self.make_private(GOOD)
        made = []
        real = tempfile.mkdtemp

        def spying(*a, **kw):
            made.append(real(*a, **kw))
            return made[-1]

        with mock.patch.object(pp.tempfile, "mkdtemp", spying):
            self.go()
            self.go("--dry-run")
            self.go("--branch", "bad")
        self.assertEqual(len(made), 3)
        self.assertFalse(any(os.path.exists(p) for p in made))

    def test_the_real_name_guard_is_the_one_used_by_default(self):
        self.make_private(GOOD)
        code, out = self.go(banned=None)
        self.assertEqual(code, 0, out)


class TheDryRun(Base):
    def test_it_pushes_nothing_and_shows_the_files_and_the_checks(self):
        self.make_private(dict(GOOD, **NOTES))
        calls = []
        code, out = self.go("--dry-run", spy=calls)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.heads(), [])
        self.assertEqual(self.runs, [])
        self.assertFalse([c for c, kw in calls if c[0] == "git" and ("push" in c)])
        for path in ("README.md", "src/app.py", "docs/RULES.md"):
            self.assertIn(" " + path, out)
        for gone in ("HEAD-LOG.md", "DECISIONS.md", ".claude/", "docs/public/"):
            self.assertNotIn(gone, out.split("Checks:")[0])
        for check in ("PASS     branch name", "PASS     no real names", "PASS     no secrets", "PASS     no file over 5 MB",
                      "SKIPPED  tests pass on both Pythons", "Would commit: parent none", "author and committer clark <"):
            self.assertIn(check, out)
        self.assertIn("Nothing was pushed", out)

    def test_it_can_run_the_tests_on_request(self):
        self.make_private(GOOD)
        code, out = self.go("--dry-run", "--with-tests")
        self.assertEqual(code, 0, out)
        self.assertEqual([r[0] for r in self.runs], ["old", "new"])
        self.assertEqual(self.heads(), [])
        names = self.runs[0][1]
        self.assertIn("src/app.py", names)

    def test_it_shows_the_parent_it_would_use(self):
        self.make_private(GOOD)
        self.go()
        tip = self.commits()[0]
        self.commit_more({"x.md": "x"})
        code, out = self.go("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("parent " + tip[:7], out)
        self.assertEqual(self.commits(), [tip])

    def test_it_fails_when_a_check_fails(self):
        self.make_private(dict(GOOD, **{".env": "A=1"}))
        code, out = self.go("--dry-run")
        self.assertEqual(code, 1)
        self.assertIn("REFUSED  no secrets", out)
        self.assertEqual(self.heads(), [])

    def test_a_dry_run_that_fails_the_name_check_lists_numbers_not_paths(self):
        self.make_private(dict(GOOD, **{"docs/Northwind notes.md": "ok"}))
        code, out = self.go("--dry-run")
        self.assertEqual(code, 1)
        self.assertNotIn("src/app.py", out)
        self.assertNotIn("docs/RULES.md", out)
        self.assertRegex(out, r"(?m)^  #\d+$")
        self.assertNotIn("Would commit: parent none (a new branch), author and committer clark <clark@users.noreply.github.com>, message: clark", out)
        self.assertNotRegex(out.lower(), "northwind")

    def test_it_creates_nothing_outside_its_temporary_folder(self):
        self.make_private(GOOD)
        before = sorted(p.name for p in self.tmp.iterdir())
        pycache = Path(pp.__file__).resolve().parents[2] / "tests" / "__pycache__"
        existed = pycache.exists()
        self.go("--dry-run")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), before)
        self.assertEqual(pycache.exists(), existed)
        self.assertEqual(sh("status", "--porcelain", cwd=self.private), "")


class TheNameGuard(Base):
    def test_a_name_in_a_file_refuses_and_is_never_printed(self):
        self.make_private(dict(GOOD, **{"docs/a.md": "fine\nOwner: Zoë Quill\n"}))
        out = self.refused()
        self.assertIn("REFUSED  no real names", out)
        self.assertRegex(out, r"file #\d+ line 2")
        self.assertNotRegex(out.lower(), r"zo[eë]|quill|[0-9a-f]{64}")
        self.assertNotIn("docs/a.md", out)

    def test_a_name_in_a_path_refuses(self):
        self.make_private(dict(GOOD, **{"docs/Northwind_Traders-report.md": "fine"}))
        out = self.refused()
        self.assertIn("(its name)", out)
        self.assertNotIn("orthwind", out)

    def test_a_name_in_an_office_part_refuses(self):
        self.make_private(dict(GOOD, **{"docs/report.docx": office("<w:t>Prepared for North</w:t><w:t>wind</w:t>")}))
        out = self.refused()
        self.assertIn("part #1", out)
        self.assertNotIn("orthwind", out)

    def test_a_name_in_the_commit_message_refuses(self):
        self.make_private(GOOD)
        sh("branch", "northwind-fix", cwd=self.private)
        sh("update-ref", "refs/remotes/origin/main", "HEAD", cwd=self.private)
        out = self.refused(ref="northwind-fix")
        self.assertIn("the commit", out)
        self.assertNotIn("orthwind", out)

    def test_the_place_numbers_are_the_refs_own(self):
        self.make_private(dict(GOOD, **{"docs/a.md": "x", "zzz.md": "Zoe Quill"}))
        out = self.refused()
        listing = sh("ls-tree", "-r", "--name-only", "HEAD", cwd=self.private).splitlines()
        number = int(re.search(r"file #(\d+) line 1", out).group(1))
        self.assertEqual(listing[number - 1], "zzz.md")

    def test_an_empty_banned_list_refuses(self):
        self.make_private(GOOD)
        self.assertIn("banned-name list is empty", self.refused(banned=frozenset()))


class TheSecretsScan(Base):
    def test_a_planted_env_file_refuses(self):
        for name in (".env", "config/.env", ".env.local", "keys/server.pem", "a/b.key", "id_rsa", "id_rsa.pub", "x.p12", "x.pfx",
                     ".netrc"):
            with self.subTest(name):
                self.setUp()
                self.make_private(dict(GOOD, **{name: "harmless"}))
                out = self.refused()
                self.assertIn("a file name that holds secrets", out)

    def test_planted_secrets_refuse_and_are_never_printed(self):
        for kind, value in secrets().items():
            with self.subTest(kind):
                self.setUp()
                self.make_private(dict(GOOD, **{"src/settings.py": "x = 1\n" + value + "\n"}))
                out = self.refused()
                self.assertRegex(out, r"file #\d+: ")
                self.assertNotIn(value.split()[-1][:12], out)
                self.assertNotIn("settings.py", out.split("Checks:")[1])

    def test_a_secret_inside_an_office_part_refuses(self):
        self.make_private(dict(GOOD, **{"docs/x.docx": office("<t>" + secrets()["github"] + "</t>")}))
        self.assertRegex(self.refused(), r"file #\d+ part #1: a GitHub token")

    def test_what_is_not_a_secret_passes(self):
        digest = "a" * 32 + "9" * 32
        self.make_private(dict(GOOD, **{
            "tests/hashes.py": 'BANNED = frozenset({"%s"})\n' % digest,
            "src/s.py": 'password = "changeme"\ntoken = "abcdefghijklmnopqrstuvwxyz"\nsecret = get_secret_from_keychain()\n',
            "docs/a.md": "Set the token in the environment, never in the file. api_key: from the keychain.\n"}))
        code, out = self.go()
        self.assertEqual(code, 0, out)

    def test_the_findings_by_kind(self):
        entries = [pp.Entry(i, "100644", "0" * 40, 1, "f%d" % i) for i in range(1, 8)]
        got = pp.secret_findings(entries, [v.encode() for v in secrets().values()])
        self.assertEqual(got, ["file #1: a private key", "file #2: a GitHub token", "file #3: a GitHub token",
                               "file #4: an AWS access key", "file #5: a Slack token", "file #6: a JSON web token",
                               "file #7: a password, key or token value"])


def wider_secrets():
    """More fake secrets, each built from pieces here (a literal would be refused by the scan of this repo's own tree)."""
    return {
        "anthropic": "key " + "sk-" + "ant-api03-" + "Ab1Cd2Ef3Gh4Ij5Kl6",
        "openai": "key " + "sk-" + "proj-" + "Ab1Cd2Ef3Gh4Ij5Kl6Mn7",
        "stripe": "key " + "sk_" + "live_" + "51Abc123Def456Ghi",
        "google": "key " + "AI" + "za" + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6",
        "env line": "export API_KEY=" + "q7" * 10,
        "yaml password": "password: " + "hunter2hunter2",
        "npmrc": "//registry.npmjs.org/:_authToken=" + "npm_" + "A1b2C3d4" * 4,
        "npmrc other": "_authToken=" + "A1b2C3d4" * 4,
        "address": "git clone https://user:" + "pw123456@" + "example.invalid/r.git",
        "bearer": "Authorization: Bearer " + "A1b2C3d4E5f6",
        "pypirc": "[pypi]\npassword = " + "pypi-" + "AgEIcHlwaS5vcmc" * 3,
    }


class TheWiderSecretsScan(Base):
    """#94, the reviewers' round: vendor prefixes, unquoted values, headers, other encodings and nested files."""

    def kinds(self, data):
        return pp.scan_secrets_in(data if isinstance(data, bytes) else data.encode("utf-8"))

    def test_each_wider_secret_is_found(self):
        for name, value in wider_secrets().items():
            with self.subTest(name):
                self.assertTrue(self.kinds("x = 1\n" + value + "\n"), name)

    def test_they_refuse_a_publish_and_the_secret_is_never_printed(self):
        for name, value in wider_secrets().items():
            with self.subTest(name):
                self.setUp()
                self.make_private(dict(GOOD, **{"src/conf.txt": "x = 1\n" + value + "\n"}))
                out = self.refused()
                self.assertRegex(out, r"REFUSED  no secrets\n\s+file #\d+: ")
                for piece in value.replace("=", " ").replace(":", " ").split()[-1:]:
                    self.assertNotIn(piece[:12], out)
                self.assertNotIn("conf.txt", out.split("Checks:")[1])

    def test_ordinary_text_is_not_refused(self):
        for text in ("password: from the keychain", "token: abc", "export API_KEY=$API_KEY_FROM_VAULT",
                     "password: <your password>", "secret: ${SECRET_VALUE_FILE}", "api_key: get_key(name)",
                     "Authorization: Bearer <token>", "see https://example.com/a:b and user@example.com",
                     "git@github.com:owner/repo.git", "ssh://git@github.com/owner/repo.git",
                     "-----BEGIN " + "CERTIFICATE-----\nMIIB\n", "sk-learn is a library", "the AIza prefix", "_authToken=${NPM_TOKEN}"):
            with self.subTest(text):
                self.assertEqual(self.kinds(text + "\n"), set())

    def test_the_certificate_and_the_public_key_file_behave_as_before(self):
        self.assertEqual(self.kinds("-----BEGIN " + "CERTIFICATE-----\nMIIBkTCB\n-----END CERTIFICATE-----\n"), set())
        entry = pp.Entry(1, "100644", "0" * 40, 1, "keys/id_rsa.pub")
        self.assertEqual(pp.secret_findings([entry], [b"ssh-rsa AAAA"]),
                         ["file #1: a file name that holds secrets (.env, key, credentials or certificate file)"])

    def test_more_file_names_are_refused(self):
        for name in (".git-credentials", "home/.git-credentials", "credentials.json", "app/Credentials.JSON", "release.keystore",
                     "android/debug.keystore"):
            with self.subTest(name):
                entry = pp.Entry(1, "100644", "0" * 40, 1, name)
                self.assertIn("file #1: a file name that holds secrets", pp.secret_findings([entry], [b"{}"])[0])
        for name in ("credentials.md", "docs/credentials.jsonl", "keystore.md", "my-credentials.json"):
            with self.subTest(name):
                entry = pp.Entry(1, "100644", "0" * 40, 1, name)
                self.assertEqual(pp.secret_findings([entry], [b"{}"]), [])

    def test_utf16_text_is_read(self):
        token = "token " + "ghp_" + "A1b2C3d4" * 5 + "\n"
        for label, data in (("with a mark", token.encode("utf-16")), ("little endian", token.encode("utf-16-le")),
                            ("big endian", token.encode("utf-16-be")), ("big endian, marked", b"\xfe\xff" + token.encode("utf-16-be"))):
            with self.subTest(label):
                self.assertEqual(self.kinds(data), {"a GitHub token"})
        self.assertEqual(self.kinds(("password: " + "hunter2hunter2\n").encode("utf-16")), {"a password, key or token value"})
        self.assertEqual(self.kinds("nothing here\n".encode("utf-16")), set())

    def test_a_zip_inside_a_docx_is_read(self):
        inner = office("<t>" + secrets()["key"] + "</t>", "word/embeddings/secret.txt")
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("word/document.xml", "<t>fine</t>")
            z.writestr("word/embeddings/oleObject1.bin", inner)
        entry = pp.Entry(7, "100644", "0" * 40, 1, "docs/a.docx")
        self.assertEqual(pp.secret_findings([entry], [outer.getvalue()]), ["file #7 part #2.1: a private key"])

    def test_nested_zips_have_a_depth_cap_and_a_size_cap(self):
        data = b"-----BEGIN " + b"PRIVATE KEY-----"
        for _ in range(pp.MAX_ZIP_DEPTH + 2):
            data = self.pack(data)
        entry = pp.Entry(3, "100644", "0" * 40, 1, "a.docx")
        got = pp.secret_findings([entry], [data])
        self.assertTrue(any("nested too deep" in f for f in got), got)
        self.assertNotIn("PRIVATE", " ".join(got))
        with mock.patch.object(pp, "MAX_ZIP_BYTES", 100):
            got = pp.secret_findings([entry], [self.pack(b"x" * 500)])
        self.assertEqual(got, ["file #3 part #1: can't be read, so it can't be checked"])

    @staticmethod
    def pack(data):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("inner.zip", data)
        return buf.getvalue()

    def test_a_private_key_header_in_base64_is_found_at_any_alignment(self):
        header = ("-----BEGIN " + "OPENSSH PRIVATE KEY-----\nAAAA\n").encode()
        for prefix in ("", "a", "ab", "abc"):
            for plain in (header, b"padding to move it " + header):
                with self.subTest((prefix, len(plain))):
                    text = '{"k": "' + prefix + base64.b64encode(plain).decode() + '"}'
                    self.assertEqual(self.kinds(text), {"a private key (base64)"})
        urlsafe = base64.urlsafe_b64encode(b"\xfb\xff" + header).decode()
        self.assertEqual(self.kinds(urlsafe), {"a private key (base64)"})
        self.assertEqual(self.kinds(base64.b64encode(b"-----BEGIN " + b"CERTIFICATE-----\n" + b"x" * 40).decode()), set())

    def test_a_token_in_base64_is_found_and_plain_base64_is_not_refused(self):
        token = ("ghp_" + "A1b2C3d4" * 5).encode()
        self.assertEqual(self.kinds(base64.b64encode(b"token=" + token)), {"a token (base64)"})
        self.assertEqual(self.kinds(base64.b64encode(b"just some ordinary words, nothing secret in here at all")), set())
        self.assertEqual(self.kinds("a" * 64 + "/" * 5 + "b" * 40), set())

    def test_a_base64_key_inside_a_nested_office_part_refuses_with_a_number_only(self):
        header = ("-----BEGIN " + "RSA PRIVATE KEY-----\n").encode()
        files = {"docs/x.docx": self.pack(office("<t>" + base64.b64encode(header).decode() + "</t>"))}
        self.make_private(dict(GOOD, **files))
        out = self.refused()
        self.assertRegex(out, r"file #\d+ part #1\.1: a private key \(base64\)")
        self.assertNotIn(base64.b64encode(header).decode()[:20], out)


class TheSize(Base):
    def test_a_file_over_5_mb_refuses_but_exactly_5_mb_is_fine(self):
        self.make_private(dict(GOOD, **{"data/big.bin": b"\0" * (5 * 1024 * 1024 + 1)}))
        out = self.refused()
        self.assertIn("is over 5 MB", out)
        self.assertNotIn("big.bin", out)
        self.setUp()
        self.make_private(dict(GOOD, **{"data/ok.bin": b"\0" * (5 * 1024 * 1024)}))
        self.assertEqual(self.go()[0], 0)

    def test_a_big_file_on_the_exclusion_list_does_not_count(self):
        self.make_private(dict(GOOD, **{".claude/big.bin": b"\0" * (6 * 1024 * 1024)}))
        self.assertEqual(self.go()[0], 0)
        self.assertNotIn(".claude/big.bin", self.tree())

    def test_links_and_submodules_refuse(self):
        self.make_private(GOOD)
        (self.private / "link").symlink_to("README.md")
        sh("add", "link", cwd=self.private)
        sh("update-index", "--add", "--cacheinfo", "160000,%s,mod" % ("1" * 40), cwd=self.private)
        sh("commit", "-q", "-m", "l", cwd=self.private)
        sh("update-ref", "refs/remotes/origin/main", "HEAD", cwd=self.private)
        out = self.refused()
        self.assertEqual(out.count("is a link or submodule"), 2)


def private_variants(owner, name):
    """Every way to write the address of the private repo (built from the fake origin, never written out)."""
    return (
        "https://github.com/%s/%s" % (owner, name), "https://github.com/%s/%s.git" % (owner, name),
        "https://github.com/%s/%s/" % (owner, name), "https://GitHub.com/%s/%s.git" % (owner.title(), name.title()),
        "http://github.com/%s/%s" % (owner, name), "https://www.github.com/%s/%s.git" % (owner, name),
        "git@github.com:%s/%s.git" % (owner, name), "git@github.com:%s/%s" % (owner, name),
        "ssh://git@github.com/%s/%s.git" % (owner, name), "ssh://git@github.com:22/%s/%s" % (owner, name),
        "ssh://git@ssh.github.com:443/%s/%s.git" % (owner, name), "git://github.com/%s/%s.git" % (owner, name),
        "github.com:%s/%s.git" % (owner, name), "https://github.com/%s/./%s.git" % (owner, name),
        "https://github.com/%s/x/../%s" % (owner, name), "https://github.com/%s/%%%02x%s.git" % (owner, ord(name[0]), name[1:]),
        "https://mirror.example/%s/%s.git" % (owner, name),
        "https://github.com/%s/%s.git.git" % (owner, name), "https://github.com/%s/%s.git.git/" % (owner, name),
        "https://github.com/%s/%s.GIT.Git.git" % (owner, name), "https://github.com/%s/%s.git/.git/" % (owner, name),
        "https://github.com/%s/%s.git//.git" % (owner, name), "git@github.com:%s/%s.git.git" % (owner, name),
        "ssh://git@github.com/%s/%s.git.git/" % (owner, name), "https://github.com/%s/%s/.git" % (owner, name),
        "https://github.com/%s/%s%%2egit%%2eGIT" % (owner, name),
        "https://GitHub.com/%s/%s.GIT/" % (owner.title(), name.upper()), "https://github.com/%s/%s.GIT" % (owner, name),
        "https://github.com/%s/%s.Git" % (owner, name.upper()), "git@github.com:%s/%s.GIT" % (owner, name),
    )


class TheTarget(Base):
    PRIVATE_VARIANTS = private_variants(OWNER, REPO_NAME)

    def test_the_private_repo_in_every_variant_is_refused(self):
        self.make_private(GOOD)
        for url in self.PRIVATE_VARIANTS:
            with self.subTest(url):
                out = self.refused(target=url, local=False)
                self.assertIn("REFUSED  target is not the private repo", out)
        self.assertEqual(self.gh_asked, [], "the target must be refused before it is asked about")

    def test_the_private_repos_name_is_read_from_origin_whatever_it_is(self):
        self.make_private(GOOD, origin="git@github.com:Other-Owner/Other-Name.git")
        for url in private_variants("other-owner", "other-name"):
            with self.subTest(url):
                self.refused(target=url, local=False)
        self.assertEqual(self.gh_asked, [])
        self.assertFalse(hasattr(pp, "PRIVATE_REPOS"))

    def test_a_name_that_is_not_the_origins_is_not_refused_for_its_name(self):
        self.make_private(GOOD, origin="git@github.com:other-owner/other-name.git")
        report = pp.Report()
        args = pp.parse_args(["main", "--target", "https://github.com/%s/%s" % (OWNER, REPO_NAME)])
        self.assertIsNotNone(pp.check_target(args, self.private, report, self.fake_gh))
        self.assertTrue(report.ok, report.lines())

    def test_origin_is_compared_whatever_its_name(self):
        self.make_private(GOOD, origin="git@github.com:someone/else.git")
        self.refused(target="https://github.com/Someone/Else", local=False)
        self.refused(target="https://www.github.com/someone/else.git/", local=False)

    def test_a_folder_that_is_the_private_repo_or_its_origin_is_refused(self):
        self.make_private(GOOD, origin=str(self.public))
        self.assertIn("same as", self.refused())
        self.setUp()
        self.make_private(GOOD, origin="https://github.com/o/r.git")
        self.refused(target=str(self.private))
        self.refused(target=str(self.private / ".git"))

    def test_every_remote_of_the_private_repo_is_compared_not_only_origin(self):
        self.make_private(GOOD, origin="https://github.com/o/r.git")
        sh("remote", "add", "backup", "git@github.com:Second-Owner/Second-Name.git", cwd=self.private)
        sh("remote", "add", "mirror", "https://github.com/third/one.git", cwd=self.private)
        sh("remote", "set-url", "--push", "mirror", "ssh://git@github.com/fourth/push-only", cwd=self.private)
        sh("config", "--add", "remote.backup.url", "https://github.com/fifth/second-url.git", cwd=self.private)
        for url in ("https://github.com/second-owner/second-name", "https://www.github.com/SECOND-OWNER/second-name.git/",
                    "https://github.com/third/one", "git@github.com:fourth/push-only.git",
                    "https://github.com/fifth/second-url.git", "https://example.invalid/second-owner/second-name"):
            with self.subTest(url):
                out = self.refused(target=url, local=False)
                self.assertIn("REFUSED  target is not the private repo", out)
                self.assertIn("other remote", out)
        self.assertEqual(self.gh_asked, [])
        report = pp.Report()
        args = pp.parse_args(["main", "--target", "https://github.com/unrelated/public-copy"])
        self.assertIsNotNone(pp.check_target(args, self.private, report, self.fake_gh))

    def test_a_remote_that_is_a_local_folder_is_compared_too(self):
        self.make_private(GOOD, origin="https://github.com/o/r.git")
        sh("remote", "add", "local", str(self.public), cwd=self.private)
        self.assertIn("other remote", self.refused())

    def test_remote_addresses_lists_them_all(self):
        self.make_private(GOOD, origin="https://github.com/o/r.git")
        sh("remote", "add", "b.c", "https://github.com/x/y.git", cwd=self.private)
        sh("remote", "set-url", "--push", "b.c", "https://github.com/x/z.git", cwd=self.private)
        got = pp.remote_addresses(self.private, pp.neutral_env(self.tmp, "x", "x@x", 0))
        self.assertEqual(sorted(got), [("b.c", "https://github.com/x/y.git"), ("b.c", "https://github.com/x/z.git"),
                                       ("origin", "https://github.com/o/r.git")])

    def test_a_repo_with_no_origin_cannot_be_published_from(self):
        self.make_private(GOOD, origin=None)
        self.assertIn("no origin", self.refused())

    def test_a_target_the_checker_says_is_private_is_refused(self):
        self.make_private(GOOD)
        self.gh_says_public = False
        out = self.refused(target="https://github.com/someone/public-copy.git", local=False)
        self.assertIn("gh could not show that the repo is public", out)
        self.assertEqual(self.gh_asked, [("someone", "public-copy")])

    def test_only_github_can_be_checked(self):
        self.make_private(GOOD)
        self.assertIn("only GitHub", self.refused(target="https://git.example.invalid/a/b.git", local=False))

    def test_a_public_github_target_passes_the_target_checks(self):
        self.make_private(GOOD)
        report = pp.Report()
        args = pp.parse_args(["main", "--target", "git@github.com:Someone/Public-Copy.git"])
        target = pp.check_target(args, self.private, report, self.fake_gh)
        self.assertIsNotNone(target)
        self.assertTrue(report.ok, report.lines())
        self.assertEqual(self.gh_asked, [("someone", "public-copy")])

    def test_the_default_gh_check_needs_exactly_false(self):
        for stdout, code, expected in ((b"false\n", 0, True), (b"true\n", 0, False), (b"", 0, False), (b"false\n", 1, False)):
            fake = subprocess.CompletedProcess([], code, stdout, b"")
            with mock.patch.object(pp.subprocess, "run", return_value=fake) as run:
                self.assertEqual(pp.gh_is_public("o", "r"), expected)
                self.assertEqual(run.call_args[0][0], ["gh", "api", "repos/o/r", "--jq", ".private"])
        with mock.patch.object(pp.subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(pp.gh_is_public("o", "r"))
        with mock.patch.object(pp.subprocess, "run") as run:
            self.assertFalse(pp.gh_is_public("--x", "r"))
            run.assert_not_called()

    def test_a_password_in_the_address_is_refused_and_never_printed(self):
        self.make_private(GOOD)
        for url in ("https://user:" "hunter2@github.com/o/r.git", "https://hunter2@github.com/o/r.git",
                    "ssh://git:" "hunter2@github.com/o/r.git", "http://u:" "hunter2@example.invalid/x"):
            with self.subTest(url):
                out = self.refused(target=url, local=False)
                self.assertIn("password", out)
                self.assertNotIn("hunter2", out)
        self.assertEqual(self.gh_asked, [])

    def test_no_target_is_refused_and_nothing_is_built_in(self):
        self.make_private(GOOD)
        self.assertIsNone(pp.DEFAULT_PUBLIC_REMOTE)
        self.assertIn("--target", self.refused(target=False))

    def test_a_folder_needs_the_flag(self):
        self.make_private(GOOD)
        self.assertIn("--allow-local-target", self.refused(local=False))
        self.assertEqual(self.gh_asked, [])

    def test_a_git_rewrite_rule_that_could_redirect_the_push_is_refused(self):
        self.make_private(GOOD)
        for key in ("insteadOf", "pushInsteadOf"):
            self.gitconfig.write_text('[url "%s"]\n\t%s = %s\n' % (self.tmp / "elsewhere.git", key, self.public.resolve()),
                                      encoding="utf-8")
            self.assertIn("insteadOf", self.refused())

    def test_a_malformed_address_is_a_plain_refusal_not_a_traceback(self):
        self.make_private(GOOD)
        for bad in ("https://[::1/o/r", "https://[::1]:notaport/o/r", "ssh://host:99999999999/o/r", "https://[/o/r"):
            with self.subTest(bad):
                out = self.refused(target=bad, local=False)
                self.assertIn("REFUSED  target is a plain address", out)
                self.assertIn("not a plain URL", out)
                self.assertNotIn("Traceback", out)
                self.assertNotIn("ValueError", out)
        with self.assertRaises(pp.TargetError):
            pp.parse_target("https://[::1/o/r")

    def test_unusable_targets(self):
        self.make_private(GOOD)
        for bad in ("", "  ", "-x", "not a url", "ftp://github.com/o/r", "https:///x"):
            with self.subTest(bad):
                self.refused(target=bad, local=False)

    def test_scrub_hides_a_password(self):
        self.assertEqual(pp.hide_password("push https://u:" "p@h.example/x and ssh://g@h/x"), "push https://***@h.example/x and ssh://***@h/x")

    def test_the_target_is_never_contacted_when_refused(self):
        self.make_private(GOOD)
        calls = []
        self.go(target=ORIGIN, local=False, spy=calls)
        self.assertEqual([c for c, kw in calls if c[0] == "git" and any(a in c for a in ("fetch", "push", "ls-remote"))], [])


class TheLocalTargetThatSharesTheRepo(Base):
    def test_another_worktree_of_the_private_repo_is_refused(self):
        self.make_private(GOOD)
        other = self.tmp / "other-worktree"
        sh("worktree", "add", "-q", "-b", "wt", str(other), cwd=self.private)
        out = self.refused(target=str(other))
        self.assertIn("REFUSED  target is not the private repo", out)
        self.assertIn("shares this repo's git store", out)

    def test_the_main_checkout_seen_from_a_worktree_is_refused(self):
        self.make_private(GOOD)
        other = self.tmp / "other-worktree"
        sh("worktree", "add", "-q", "-b", "wt", str(other), cwd=self.private)
        self.private, main_checkout = other, self.private                       # now run from the worktree
        self.assertIn("REFUSED  target is not the private repo", self.refused(target=str(main_checkout)))

    def test_a_bare_repo_or_folder_inside_the_private_git_store_is_refused(self):
        self.make_private(GOOD)
        for inside in (self.private / ".git", self.private / ".git" / "refs"):
            self.assertIn("REFUSED  target is not the private repo", self.refused(target=str(inside)))

    def test_a_folder_inside_the_working_tree_is_refused(self):
        self.make_private(GOOD)
        (self.private / "out").mkdir()
        self.assertIn("inside, or around", self.refused(target=str(self.private / "out")))
        self.assertIn("inside, or around", self.refused(target=str(self.private / "src")))

    def test_a_folder_that_contains_the_private_repo_is_refused(self):
        self.make_private(GOOD)
        self.assertIn("inside, or around", self.refused(target=str(self.tmp)))
        self.assertIn("inside, or around", self.refused(target=str(self.tmp.parent)))

    def test_a_bare_clone_with_its_own_store_is_allowed(self):
        self.make_private(GOOD)
        clone = self.tmp / "clone.git"
        sh("clone", "-q", "--bare", "--no-hardlinks", str(self.private), str(clone))
        code, out = self.go(target=str(clone))
        self.assertEqual(code, 0, out)
        self.assertEqual(sh("for-each-ref", "--format=%(refname)", "refs/heads/clark-public", cwd=clone), "refs/heads/clark-public")

    def test_a_plain_clone_with_its_own_store_is_allowed(self):
        self.make_private(GOOD)
        clone = self.tmp / "clone"
        sh("clone", "-q", "--no-hardlinks", str(self.private), str(clone))
        code, out = self.go(target=str(clone))
        self.assertEqual(code, 0, out)


class TheLocalTargetInAnotherLetterCase(Base):
    """On a case-insensitive disk (APFS) one folder has many spellings; the target is compared by inode, not by text."""

    def flipped(self, path):
        other = str(path).swapcase()
        try:
            same = os.path.samefile(str(path), other)
        except OSError:
            same = False
        if not same:
            self.skipTest("this disk is case-sensitive: a letter-case spelling is a different folder")
        self.assertNotEqual(other, str(path))
        return other

    def test_the_private_folder_in_another_case_is_refused(self):
        self.make_private(GOOD)
        out = self.refused(target=self.flipped(self.private))
        self.assertIn("REFUSED  target is not the private repo", out)
        self.assertIn("own folder", out)

    def test_its_git_folder_in_another_case_is_refused(self):
        self.make_private(GOOD)
        for inside in (self.private / ".git", self.private / ".git" / "refs"):
            self.assertIn("REFUSED  target is not the private repo", self.refused(target=self.flipped(inside)))
        self.assertIn("REFUSED  target is not the private repo", self.refused(target=str(self.private / ".GIT")))

    def test_a_folder_inside_or_around_it_in_another_case_is_refused(self):
        self.make_private(GOOD)
        (self.private / "out").mkdir()
        self.assertIn("inside, or around", self.refused(target=self.flipped(self.private / "out")))
        self.assertIn("inside, or around", self.refused(target=self.flipped(self.tmp)))

    def test_a_worktree_or_the_main_checkout_in_another_case_is_refused(self):
        self.make_private(GOOD)
        other = self.tmp / "other-worktree"
        sh("worktree", "add", "-q", "-b", "wt", str(other), cwd=self.private)
        self.assertIn("shares this repo's git store", self.refused(target=self.flipped(other)))
        self.private, main_checkout = other, self.private
        self.assertIn("REFUSED  target is not the private repo", self.refused(target=self.flipped(main_checkout)))

    def test_an_origin_that_is_a_folder_is_compared_by_inode_too(self):
        self.make_private(GOOD, origin=str(self.public))
        self.assertIn("same as", self.refused(target=self.flipped(self.public)))

    def test_a_separate_clone_is_still_allowed_in_any_case(self):
        self.make_private(GOOD)
        clone = self.tmp / "clone.git"
        sh("clone", "-q", "--bare", "--no-hardlinks", str(self.private), str(clone))
        code, out = self.go(target=self.flipped(clone))
        self.assertEqual(code, 0, out)

    def test_the_inode_helpers(self):
        self.make_private(GOOD)
        self.assertIsNone(pp.file_id(str(self.tmp / "nothing-here")))
        self.assertEqual(pp.file_id(str(self.private)), pp.file_id(str(self.private / "src" / "..")))
        self.assertEqual(pp.id_chain(""), [])
        self.assertIn(pp.file_id(str(self.tmp)), pp.id_chain(str(self.private / "not" / "made" / "yet")))


class TheSignals(Base):
    """Run the script as a process against local repos, stop it half way, and look for temporary folders left behind."""

    def make_fake_private(self):
        here = Path(__file__).resolve().parents[1]
        files = dict(GOOD)
        files["dev/tools/publish_public.py"] = (here / "dev" / "tools" / "publish_public.py").read_bytes()
        for name in ("test_no_real_names.py", "_paths.py"):
            files["tests/" + name] = (here / "tests" / name).read_bytes()
        # the "tests" of the snapshot: say they have started, then wait (the test sends the signal now)
        files["dev/run_tests.py"] = ("import os, time\nopen(os.path.join(os.environ['TMPDIR'], 'tests-started'), 'w').close()\n"
                                     "time.sleep(300)\n")
        self.make_private(files)

    def run_and_signal(self, signum):
        import signal
        import sys
        import time
        private_tmp = self.tmp / "ptmp"
        private_tmp.mkdir()
        env = dict(os.environ, TMPDIR=str(private_tmp))
        proc = subprocess.Popen([sys.executable, str(self.private / "dev" / "tools" / "publish_public.py"), "main",
                                 "--target", str(self.public), "--allow-local-target", "--pythons", sys.executable + "," + sys.executable],
                                cwd=str(self.private), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        deadline = time.time() + 120
        while not (private_tmp / "tests-started").exists():
            if proc.poll() is not None:
                self.fail("the script ended early: " + proc.stdout.read().decode())
            self.assertLess(time.time(), deadline, "the fake tests never started")
            time.sleep(0.2)
        self.assertTrue([p for p in private_tmp.iterdir() if p.name.startswith("clark-publish-")], "no temporary folder yet")
        proc.send_signal(getattr(signal, signum))
        out = proc.communicate(timeout=60)[0].decode()
        return proc.returncode, out, sorted(p.name for p in private_tmp.iterdir())

    def test_sigterm_and_sighup_remove_the_temporary_folders_and_exit_non_zero(self):
        for signum in ("SIGTERM", "SIGHUP"):
            with self.subTest(signum):
                self.setUp()
                self.make_fake_private()
                code, out, left = self.run_and_signal(signum)
                self.assertNotEqual(code, 0, out)
                self.assertIn("INTERRUPTED", out)
                self.assertNotIn("Traceback", out)
                self.assertEqual([n for n in left if n.startswith("clark-publish-")], [], out)
                self.assertEqual(self.heads(), [], "nothing was pushed")

    def test_the_old_handlers_are_put_back_and_cleanup_is_not_interrupted(self):
        import signal
        self.make_private(GOOD)
        before = {n: signal.getsignal(getattr(signal, n)) for n in ("SIGTERM", "SIGHUP")}
        self.assertEqual(self.go()[0], 0)
        self.assertEqual({n: signal.getsignal(getattr(signal, n)) for n in before}, before)
        # a signal during the run becomes KeyboardInterrupt, and run() answers 130 and still cleans up
        made = []
        real = tempfile.mkdtemp

        def spying(*a, **kw):
            made.append(real(*a, **kw))
            return made[-1]

        def signalling(*a, **kw):
            os.kill(os.getpid(), signal.SIGTERM)
            raise AssertionError("the signal handler should have raised")

        with mock.patch.object(pp.tempfile, "mkdtemp", spying), mock.patch.object(pp, "resolve_ref", signalling):
            code, out = self.go()
        self.assertEqual(code, 130, out)
        self.assertIn("INTERRUPTED", out)
        self.assertFalse(any(os.path.exists(p) for p in made))
        self.assertEqual({n: signal.getsignal(getattr(signal, n)) for n in before}, before)

    def test_a_second_signal_while_the_folder_is_being_removed_does_not_leave_it(self):
        import signal
        self.make_private(GOOD)
        made = []
        real_mkdtemp, real_rmtree = tempfile.mkdtemp, shutil.rmtree

        def spying(*a, **kw):
            made.append(real_mkdtemp(*a, **kw))
            return made[-1]

        def rmtree_with_signals(path, *a, **kw):
            for name in ("SIGINT", "SIGTERM", "SIGHUP"):                 # a second Ctrl-C, kill and hang-up, all at once
                os.kill(os.getpid(), getattr(signal, name))
            return real_rmtree(path, *a, **kw)

        before = {n: signal.getsignal(getattr(signal, n)) for n in ("SIGINT", "SIGTERM", "SIGHUP")}

        def first(*a, **kw):
            os.kill(os.getpid(), signal.SIGTERM)                         # the first one: stops the run
            raise AssertionError("the signal handler should have raised")

        with mock.patch.object(pp.tempfile, "mkdtemp", spying), mock.patch.object(pp, "resolve_ref", first), \
                mock.patch.object(pp.shutil, "rmtree", rmtree_with_signals):
            code, out = self.go()
        self.assertEqual(code, 130, out)
        self.assertIn("INTERRUPTED", out)
        self.assertFalse(any(os.path.exists(p) for p in made), "the temporary folder was left behind")
        self.assertEqual({n: signal.getsignal(getattr(signal, n)) for n in before}, before)

    def test_an_interrupt_that_gets_in_first_makes_the_removal_start_again(self):
        import signal
        self.make_private(GOOD)
        made, calls = [], []
        real_mkdtemp, real_rmtree = tempfile.mkdtemp, shutil.rmtree

        def spying(*a, **kw):
            made.append(real_mkdtemp(*a, **kw))
            return made[-1]

        def flaky(path, *a, **kw):
            calls.append(path)
            if len(calls) < 3:
                real_rmtree(os.path.join(path, "home"), ignore_errors=True)       # part of it goes, then the signal lands
                raise KeyboardInterrupt()
            return real_rmtree(path, *a, **kw)

        before = signal.getsignal(signal.SIGINT)
        with mock.patch.object(pp.tempfile, "mkdtemp", spying), mock.patch.object(pp.shutil, "rmtree", flaky):
            code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 3)
        self.assertFalse(any(os.path.exists(p) for p in made))
        self.assertIs(signal.getsignal(signal.SIGINT), before)


class TheRef(Base):
    def test_a_commit_that_is_not_on_main_is_refused(self):
        self.make_private(GOOD)
        sh("checkout", "-q", "-b", "side", cwd=self.private)
        self.commit_more({"side.md": "s"})
        sh("update-ref", "refs/remotes/origin/main", "main", cwd=self.private)
        self.assertIn("only a commit that is on origin/main", self.refused(ref="side"))

    def test_main_that_cannot_be_found_is_refused(self):
        self.make_private(GOOD)
        sh("update-ref", "-d", "refs/remotes/origin/main", cwd=self.private)
        self.assertIn("git fetch origin", self.refused())

    def test_an_unknown_or_odd_ref_is_refused(self):
        self.make_private(GOOD)
        for ref in ("nothing-here", "v9.9.9", "--upload-pack=x", "a b", "-x"):
            with self.subTest(ref):
                code, out = self.go(ref=ref)
                self.assertEqual(code, 1, out)
                self.assertEqual(self.heads(), [])


D = "-" * 2                                    # the launch flags are built here, never written (see publish_public.DASHES)
HEADLESS, PIPE = D + "headless=new", D + "remote-debugging-pipe"
MOCK, BASIC = D + "use-mock-keychain", D + "password-store=basic"


class TheChromeKeychainRule(unittest.TestCase):
    """#104: never run a tree's tests here when it starts Chrome without the keychain flags."""

    def tree(self, **files):
        d = Path(tempfile.mkdtemp(prefix="clark-pp-chrome-"))
        self.addCleanup(shutil.rmtree, d, True)
        for rel, text in files.items():
            name = rel.replace("__", "/") if "." in rel else rel.replace("__", "/") + ".py"
            f = d / name
            f.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(text, bytes):
                f.write_bytes(text)
            else:
                f.write_text(text, encoding="utf-8")
        return d

    def test_a_launch_without_both_flags_is_found_by_place_number(self):
        flags = '"%s", "%s", "%s", "%s"' % (HEADLESS, PIPE, MOCK, BASIC)
        d = self.tree(tests__a="x = [%s]\n" % flags, tests__b='x = ["%s", "%s"]\n' % (HEADLESS, PIPE),
                      tests__c='x = ["%s", "%s"]\n' % (HEADLESS, MOCK), tests__d="import run_support\n",
                      dev__e='x = ["%s"]\n' % PIPE)
        self.assertEqual(pp.chrome_without_keychain_flags(d), [2, 3, 5])

    def test_a_shell_string_that_starts_chrome_is_a_launch(self):
        d = self.tree(tests__a='run("google-chrome %s about:blank")\n' % HEADLESS,
                      tests__b='run("google-chrome %s %s %s")\n' % (HEADLESS, MOCK, BASIC),
                      tests__c='cmd = "chrom" "ium %s --x"\nother = "%s"\n' % (PIPE, MOCK),
                      tests__d='"""Docs: chrome %s is explained here."""\nx = 1\n' % HEADLESS,
                      tests__e='def f():\n    """Mentions %s."""\n    return 1\n' % HEADLESS,
                      tests__f='x = "headless mode, remote debugging, a-%s"\n' % (D + "headlessly"))
        self.assertEqual(pp.chrome_rule_problems(d), ([1, 3], []))

    def test_shell_scripts_and_src_are_checked_too(self):
        d = self.tree(**{"tests__run.sh": "#!/bin/sh\ngoogle-chrome %s about:blank\n" % HEADLESS,
                         "dev__ok.sh": "#!/bin/sh\nchrome %s %s %s\n" % (HEADLESS, MOCK, BASIC),
                         "dev__note.sh": "echo no browser here\n",
                         "src__clark__tool.py": 'argv = ["chrome", "%s"]\n' % PIPE,
                         "src__clark__good.py": 'argv = ["chrome", "%s", "%s", "%s"]\n' % (PIPE, MOCK, BASIC),
                         "system__x.bash": "chrome %s\n" % PIPE})
        bad, unreadable = pp.chrome_rule_problems(d)
        self.assertEqual(unreadable, [])
        self.assertEqual(bad, [1, 4, 6])           # tests/run.sh; dev/note.sh and dev/ok.sh pass; system/x.bash; src/good.py passes; src/tool.py
        self.assertEqual(pp.chrome_without_keychain_flags(d), [1, 4, 6])

    def test_a_script_that_cannot_be_parsed_or_read_fails_loudly(self):
        d = self.tree(tests__a="def broken(:\n", tests__b=b"x = '\xff\xfe'\n", tests__c="x = '\0'\n", tests__d="x = 1\n",
                      **{"tests__e.sh": b"echo \xff\n"})
        self.assertEqual(pp.chrome_rule_problems(d), ([], [1, 2, 3, 5]))
        report = pp.Report()
        args = mock.Mock(dry_run=False, with_tests=True, pythons="python3,/usr/bin/python3")
        ran = []
        pp.check_tests(args, d, lambda py, checkout: ran.append(py) or (True, "3." + str(len(ran))), report)
        self.assertEqual(ran, [], "no test was run")
        self.assertEqual(report.status("tests pass on both Pythons"), pp.REFUSED)
        self.assertIn("could not be read or parsed", " ".join(" ".join(r[2]) for r in report.rows))

    def test_a_snapshot_that_would_launch_chrome_unsafely_is_not_tested(self):
        d = self.tree(tests__bad='x = ["%s"]\n' % HEADLESS)
        report = pp.Report()
        args = mock.Mock(dry_run=False, with_tests=True, pythons="python3,/usr/bin/python3")
        ran = []
        pp.check_tests(args, d, lambda py, checkout: ran.append(py) or (True, "3." + str(len(ran))), report)
        self.assertEqual(ran, [], "no test was run")
        self.assertEqual(report.status("tests pass on both Pythons"), pp.REFUSED)
        self.assertIn("without the keychain flags", " ".join(" ".join(r[2]) for r in report.rows))

    def test_this_repository_s_own_tree_passes_the_rule(self):
        self.assertEqual(pp.chrome_rule_problems(Path(__file__).resolve().parents[1]), ([], []),
                         "every Chrome launch carries both keychain flags (or goes through the shared helper in dev/tools)")


class TheTests(Base):
    def test_failing_tests_on_one_python_refuse(self):
        self.make_private(GOOD)
        code, out = self.go(run_tests=self.fake_tests, ref="main", )
        self.assertEqual(code, 0, out)
        self.setUp()
        self.make_private(GOOD)
        argv = ["main", "--target", str(self.public), "--allow-local-target", "--pythons", "old,bad"]
        lines = []
        code = pp.run(pp.parse_args(argv), repo=self.private, run_tests=self.fake_tests, is_public=self.fake_gh,
                      banned=FICTIONAL, out=lines.append, now=lambda: NOW)
        self.assertEqual(code, 1)
        self.assertIn("failed or did not run with: bad", "\n".join(lines))
        self.assertEqual(self.heads(), [])

    def test_one_python_or_the_same_version_twice_is_not_both(self):
        self.make_private(GOOD)
        for pythons in ("old", "old,same"):
            lines = []
            code = pp.run(pp.parse_args(["main", "--target", str(self.public), "--allow-local-target", "--pythons", pythons]),
                          repo=self.private, run_tests=self.fake_tests, is_public=self.fake_gh, banned=FICTIONAL,
                          out=lines.append, now=lambda: NOW)
            self.assertEqual(code, 1, pythons)
            self.assertEqual(self.heads(), [])

    def test_the_tests_run_on_the_published_files_only(self):
        self.make_private(dict(GOOD, **dict(NOTES, **KEPT)))
        self.assertEqual(self.go()[0], 0)
        self.assertEqual([r[0] for r in self.runs], ["old", "new"])
        names = self.runs[0][1]
        self.assertIn("README.md", names)
        self.assertIn("docs/handoff/a.md", names)                                # the tests read docs/handoff/
        self.assertFalse([n for n in names if n.startswith((".claude", "docs/public")) or n.endswith("DECISIONS.md")])

    def test_the_tests_are_not_run_when_another_check_has_refused(self):
        self.make_private(dict(GOOD, **{".env": "A=1"}))
        self.refused()
        self.assertEqual(self.runs, [])

    def test_a_missing_interpreter_is_a_failure(self):
        passed, version = pp.default_run_tests("/nonexistent/python", self.tmp)
        self.assertFalse(passed)


class TheSnapshot(Base):
    def test_the_working_folder_is_never_read(self):
        self.make_private(GOOD, ignored={"comms/plan.md": "x"})
        (self.private / "docs" / "public" / "README.md").write_text("EDITED, not committed\n", encoding="utf-8")
        (self.private / "untracked.md").write_text("new file\n", encoding="utf-8")
        self.assertEqual(self.go()[0], 0)
        self.assertNotIn("untracked.md", self.tree())
        self.assertEqual(sh("show", "clark-public:README.md", cwd=self.public), PUBLIC_README.strip())

    def test_the_ref_is_what_is_published_not_the_branch_tip(self):
        self.make_private(GOOD)
        sh("tag", "v1", cwd=self.private)
        self.commit_more({"later.md": "x"})
        self.assertEqual(self.go(ref="v1")[0], 0)
        self.assertNotIn("later.md", self.tree())

    def test_attributes_in_the_tree_cannot_change_the_files(self):
        self.make_private(dict(GOOD, **{".gitattributes": "* export-ignore\n*.md text eol=crlf\n", "a.md": "one\ntwo\n"}))
        self.assertEqual(self.go()[0], 0)
        self.assertEqual(sh("rev-parse", "clark-public:a.md", cwd=self.public), sh("rev-parse", "HEAD:a.md", cwd=self.private))
        self.assertIn(".gitattributes", self.tree())


# Files at the top level, and under docs/ (apart from docs/handoff/, which is published as a folder), that the tool may
# publish. A tracked file in either place that is not listed forces a decision: add it here to publish it, or put it on
# EXCLUDED in dev/tools/publish_public.py to keep it private. (README.md is the public README, swapped in by the tool.)
KNOWN_PUBLIC = frozenset({
    ".gitattributes", ".gitignore", "LICENSE", "NOTICE.md", "README.md", "SECURITY.md", "clark.command",
    "docs/ARCHITECTURE.md", "docs/BRD.md", "docs/DESIGN-SYSTEM.md", "docs/PROJECT-BRIEF.md", "docs/REUSE-FROM-CREAITE.md", "docs/RULES.md",
    "docs/publishing-the-public-copy.md", "docs/testing-on-linux.md",
    # #93: the README's pictures, taken from the fictional demo data (the prototype and `python3 -m clark --demo`)
    "docs/img/app-work-items-dark.png", "docs/img/app-work-items-light.png", "docs/img/ask-clark.png",
    "docs/img/milestones-calendar.png", "docs/img/milestones-timeline.png", "docs/img/peek.png",
    "docs/img/published-page.png", "docs/img/report-dark.png", "docs/img/report-edit.png", "docs/img/report-light.png",
    "docs/img/work-items-board.png", "docs/img/work-items-dark.png", "docs/img/work-items-table.png",
})


def tracked_snapshot_entries():
    """What the tool would publish from this checkout's tracked files, as Entry objects (read from disk, so a file that
    is changed but not yet committed counts). Numbered as `git ls-files` lists them."""
    root = Path(__file__).resolve().parents[1]
    listing = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], stdout=subprocess.PIPE, check=True).stdout
    entries = [pp.Entry(i, "100644", "", 0, p) for i, p in enumerate(listing.decode("utf-8").split("\0"), 1) if p]
    report = pp.Report()
    if any(e.path == pp.PUBLIC_README_SOURCE for e in entries):
        entries = pp.use_public_readme(entries, report)
    kept, _ = pp.apply_exclusions(entries, report)
    blobs = []
    for e in kept:
        source = pp.PUBLIC_README_SOURCE if e.path == pp.PUBLIC_README and (root / pp.PUBLIC_README_SOURCE).exists() else e.path
        blobs.append((root / source).read_bytes() if (root / source).is_file() else b"")
    return kept, blobs


class TheTrackedTreeOfThisRepo(unittest.TestCase):
    """#94: the tool's own checks, run over this repo's tracked files in the normal suite, so a false positive or a new
    internal note shows here and not first on a real publish."""

    def test_the_secrets_scan_passes_over_every_file_the_tool_would_publish(self):
        kept, blobs = tracked_snapshot_entries()
        self.assertTrue(kept)
        self.assertEqual(pp.secret_findings(kept, blobs), [],
                         "the tool's secrets scan would stop a real publish at these places (file #N of the snapshot); "
                         "rename the planted value in the test (do not loosen the tool)")

    def test_a_new_top_level_or_docs_file_must_be_decided(self):
        kept, _ = tracked_snapshot_entries()
        unknown = [e.index for e in kept
                   if ("/" not in e.path or (e.path.startswith("docs/") and not e.path.startswith("docs/handoff/")))
                   and e.path not in KNOWN_PUBLIC]
        self.assertEqual(unknown, [], "file(s) #%s of the snapshot are at the top level or under docs/ and not in "
                                      "KNOWN_PUBLIC: add them there to publish them, or to EXCLUDED to keep them "
                                      "private" % unknown)

    def test_the_known_list_only_names_files_that_exist_or_are_the_public_readme(self):
        root = Path(__file__).resolve().parents[1]
        for path in KNOWN_PUBLIC:
            self.assertTrue((root / path).exists(), path)

    def test_the_planted_marker_in_the_glance_tests_is_not_a_secret_assignment(self):
        line = ('PLANTED_MARKER = "' + "INTERNAL-ONLY" + '-NOTE-7731"\n').encode()
        self.assertFalse(pp.scan_secrets_in(line))
        self.assertTrue(pp.scan_secrets_in(b'SECRET = "' + b"INTERNAL-ONLY-NOTE-7731" + b'"\n'),
                        "the tool still reads a secret assignment as a secret")


# --- #94: the public copy carries no private names. They are built here from the tool's ROT13 words, so this file holds none.
OWNER_N, HEAD_N, DESIGNER_N, LEAD_N = (pp.reveal(w) for w in ("Nyna", "Wneivf", "Jnaqn", "Ebznabss"))
BUILDER_N, BUILDER2_N = pp.reveal("Onaare"), pp.reveal("Ynat")
TEAM_REPO, PLAN_REPO, SECRET_REPO, PLAN_REPO2 = (pp.reveal(w) for w in ("Grnz-Niratref", "pynex-cyna", "pernvgr-pbasvqragvny",
                                                                        "pernvgr-cyna"))
HOST_N, BOX_N = pp.reveal("Urgmare"), pp.reveal("PNK41")
REUSE_N = pp.reveal("ERHFR-SEBZ-PERNVGR")
LISTED = (OWNER_N, HEAD_N, DESIGNER_N, LEAD_N, BUILDER_N, BUILDER2_N, TEAM_REPO, PLAN_REPO, SECRET_REPO, PLAN_REPO2, HOST_N, BOX_N)


def clean(path, text):
    return pp.scrub(path, text.encode("utf-8")).decode("utf-8")


def has_listed(text):
    return pp.names_listed_word(text) or any(w.lower() in text.lower() for w in pp.PEOPLE_ANY_CASE + pp.PRIVATE_NAMES + pp.HOSTING_WORDS)


class TheScrubRules(unittest.TestCase):
    def test_an_attribution_in_prose_is_rewritten_to_the_plain_rule(self):
        cases = (
            ("- **Mac first** (%s, 28-10-2026, relayed by %s: \"start with mac\")\n" % (OWNER_N, DESIGNER_N),
             "- **Mac first** (\"start with mac\")\n"),
            ("Decided (%s, 28-10-2026, relayed by %s): one writer.\n" % (OWNER_N, HEAD_N), "Decided: one writer.\n"),
            ("Agreed (%s, 11-10-2026).\n" % OWNER_N, "Agreed.\n"),
            ("%s, relayed by %s: \"keep it small\".\n" % (OWNER_N, DESIGNER_N), "\"keep it small\".\n"),
            ("| BR-11 | share | %s 28-10-2026, relayed by %s |\n" % (OWNER_N, DESIGNER_N), "| BR-11 | share |  |\n"),
            ("- **Q** (%s and %s, 27-10-2026): ok\n" % (OWNER_N, HEAD_N), "- **Q**: ok\n"),
            ("(%s through %s: \"in\")\n" % (OWNER_N, HEAD_N), "(\"in\")\n"),
            ("-- clark: on by default (%s, #24)\n" % OWNER_N, "-- clark: on by default\n"),
            ("filters work items (#69; %s, 28-10-2026): type\n" % OWNER_N, "filters work items (#69): type\n"),
            ("Then, the same day, relayed by %s: \"for team\"\n" % DESIGNER_N, "Then, the same day: \"for team\"\n"),
            ("revised after %s's ask, relayed by %s: \"ensure it\".\n" % (OWNER_N, DESIGNER_N), "revised after the owner's ask: \"ensure it\".\n"),
        )
        for before, after in cases:
            with self.subTest(after):
                self.assertEqual(clean("docs/a.md", before), after)

    def test_names_left_in_prose_become_roles_and_repos_become_plain_phrases(self):
        text = ("%s owns it. Ask %s or %s. %s's note and %s. Team %s builds; %s reviews.\nSee `insyncalan/%s` and %s, not %s or %s.\n" % (
            OWNER_N, HEAD_N, LEAD_N, DESIGNER_N, LEAD_N + "s", BUILDER_N, BUILDER2_N, TEAM_REPO, PLAN_REPO, SECRET_REPO, PLAN_REPO2))
        out = clean("docs/b.md", text)
        self.assertEqual(out, "The owner owns it. Ask the Head or the project lead. A teammate's note and the project leads. "
                              "A teammate builds; a teammate reviews.\nSee the team repo and the planning repo, not a private repo "
                              "or a private repo.\n")
        self.assertFalse(has_listed(out))
        self.assertEqual(clean("docs/b.md", "Written by %s (project lead), for the %s board.\n" % (LEAD_N, PLAN_REPO)),
                         "Written by the project lead, for the planning repo board.\n")
        self.assertEqual(clean("docs/b.md", "The %s board and `%s` too\n" % (PLAN_REPO, TEAM_REPO)), "The planning repo board and the team repo too\n")

    def test_first_names_and_full_names_in_prose_become_one_role_and_in_comments_are_dropped(self):
        full = lambda a, b: "%s %s" % (pp.reveal(a), pp.reveal(b))
        out = clean("docs/n.md", "By %s and %s. Asked %s, %s, %s and %s.\n" % (
            full("Angnfun", "Ebznabss"), full("Nyna", "Znuba"), full("Fpbgg", "Ynat"), full("Crgre", "Cnexre"), full("Gbal", "Fgnex"),
            full("Fgrir", "Ebtref")))
        self.assertEqual(out, "By the project lead and the owner. Asked teammates.\n")
        py = clean("src/n.py", 'x = 1  # %s\n# %s wrote it\ny = 2\n' % (full("Jnaqn", "Znkvzbss"), pp.reveal("Oehpr")))
        self.assertEqual(py, "x = 1\ny = 2\n")

    def test_the_hosting_detail_is_replaced(self):
        out = clean("docs/e.md", "**Not %s:** the two boxes are Arm Linux (%s), and %s Cloud has no Windows.\n" % (HOST_N, BOX_N, HOST_N))
        self.assertEqual(out, "**Not a Linux machine:** the two boxes are Arm Linux, and a Linux host has no Windows.\n")

    def test_the_reuse_record_links_go_and_nothing_dangles(self):
        text = ("Read `docs/%s.md`, or [the record](docs/%s.md) and [the doc](./%s.md).\nSee %s too. [Kept](docs/b.md) "
                "[Gone](docs/DECISIONS.md) [Web](https://example.invalid/x.md) [Top](#top)\n" % (REUSE_N, REUSE_N, REUSE_N, REUSE_N))
        out = pp.scrub("README.md", text.encode(), {"README.md", "docs/b.md"}).decode()
        self.assertEqual(out, "Read the reuse record, or the record and the doc.\nSee the reuse record too. [Kept](docs/b.md) "
                              "Gone [Web](https://example.invalid/x.md) [Top](#top)\n")
        self.assertNotIn(REUSE_N.lower(), out.lower())

    def test_a_person_s_file_name_in_prose_is_an_internal_note(self):
        out = clean("docs/f.md", "- `docs/HANDOVER-%s.md` and docs/NOTES-%s.md\n" % (LEAD_N.upper(), LEAD_N))
        self.assertEqual(out, "- an internal note and an internal note\n")

    def test_python_comments_and_docstrings_lose_the_lines_and_code_stays(self):
        src = ('"""Module docs.\n\nWritten for %s (builder).\nMore.\n"""\n'
               'X = 1  # %s said so\n'
               '# %s, 28-10-2026: whole line\n'
               '# kept comment\n'
               'def f():\n'
               '    """One line about %s."""\n'
               '    y = "%s stays in code"  # note\n'
               '    return y\n'
               'class C:\n'
               '    """Start\n    %s inside\n    end"""\n') % (BUILDER_N, OWNER_N, OWNER_N, HEAD_N, OWNER_N, LEAD_N)
        out = clean("src/m.py", src)
        compile(out, "m.py", "exec")
        self.assertIn("Module docs.", out)
        self.assertIn("More.", out)
        self.assertIn("X = 1\n", out)
        self.assertIn("# kept comment", out)
        self.assertIn('    """"""\n', out)
        self.assertIn("Start", out)
        self.assertIn("    end", out)
        self.assertEqual([l for l in out.splitlines() if has_listed(l)], ['    y = "%s stays in code"  # note' % OWNER_N])

    def test_javascript_css_sql_yaml_and_dotfiles(self):
        js = ("const u = 'https://example.invalid/a'; // %s wrote this\n/* %s: note\n   keep me */\n"
              "const t = `x ${a ? `// %s in a string` : ''} y`; /* %s */ let z = 1;\nconst r = /[/]%s/;\n") % (
            OWNER_N, HEAD_N, OWNER_N, LEAD_N, OWNER_N)
        out = clean("system/x.js", js)
        self.assertEqual(out, "const u = 'https://example.invalid/a';\n/*\n   keep me */\n"
                              "const t = `x ${a ? `// %s in a string` : ''} y`; /**/ let z = 1;\nconst r = /[/]%s/;\n" % (OWNER_N, OWNER_N))
        self.assertEqual(clean("a.css", "a { b: c } /* %s */\n/* %s */\n/* keep */\n" % (OWNER_N, OWNER_N)), "a { b: c } /**/\n/* keep */\n")
        self.assertEqual(clean("a.sql", "x INT, -- %s note\ny TEXT -- keep\n" % OWNER_N), "x INT,\ny TEXT -- keep\n")
        self.assertEqual(clean("a.sql", "-- %s: internal only fixture\nz INT -- internal only\n" % OWNER_N), "z INT\n")
        self.assertEqual(clean("a.yml", "a: 'x # %s'  # %s\nb: 1 # keep\n" % (OWNER_N, OWNER_N)), "a: 'x # %s'\nb: 1 # keep\n" % OWNER_N)
        self.assertEqual(clean(".gitignore", "# %s's materials\ncomms/\n" % OWNER_N), "comms/\n")

    # #94: the JavaScript scrub never publishes code it has cut. After scrubbing, the pinned esbuild must read the input and the
    # output as the same code (comments aside); if not, or if esbuild cannot run, the file is left as it was (the guard then refuses it).
    def js_ok(self, src, path="a.js"):
        """The scrubbed text must be refused (unchanged) or be the same code as the input with the comments of a listed name gone."""
        src = src.replace("NAME", OWNER_N)
        out = clean(path, src)
        if out != src:
            self.assertFalse(has_listed(out), out)
            self.assertEqual(pp._minified(src), pp._minified(out), out)
        return src, out

    def test_javascript_regex_forms_are_scrubbed_or_refused_never_cut(self):
        regex_forms = ("if (x) /a\\//.test(y); // NAME\nz();\n", "x = typeof /a\\//; // NAME\n", "if (a) {} else /\\//.test(b) // NAME\nq();\n",
                       "for (x of /\\//g) {} // NAME\n", "async function g(){ await /\\//.test(b) // NAME\n}\n",
                       "while (a) /\\//.test(1) // NAME\nz;\n", "do /\\//.test(1); while (0) // NAME\n",
                       "function* g(){ yield /\\//.test(1) // NAME\n}\n", "throw /\\//.test(1) // NAME\n", "void /\\//.test(1) // NAME\n",
                       "delete /\\//.x // NAME\n", "switch (a) { case /\\//.x: 1 // NAME\n}\n", "x = (a + b) / 2; // NAME\ny = 1;\n",
                       "x = a / b; // NAME\n")
        for src in regex_forms:
            with self.subTest(src=src):
                src, out = self.js_ok(src)
                self.assertNotIn(OWNER_N, out)                       # all of these are scrubbed, not refused
        self.assertEqual(clean("a.js", "if (x) /a\\//.test(y); // %s\nz();\n" % OWNER_N), "if (x) /a\\//.test(y);\nz();\n")

    def test_javascript_that_the_scrub_would_cut_is_refused(self):
        for src in ("function f(s){ return /^https?:\\/\\/.test(s); // NAME wrote this\n}\n", "x = a\n/\\//.test(b) // NAME\n"):
            with self.subTest(src=src):
                src, out = self.js_ok(src)
                self.assertEqual(out, src)
        for src in ('const e = <a href="http://x">// NAME</a>;\n', "const e = <p>a // b NAME</p>;\n"):
            with self.subTest(src=src):
                src, out = self.js_ok(src, "a.jsx")
                self.assertEqual(out, src)

    def test_javascript_is_refused_when_esbuild_is_missing_or_fails(self):
        src = "const a = 1; // %s\n" % OWNER_N
        self.assertNotIn(OWNER_N, clean("a.js", src))
        for broken in (lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("no esbuild")),
                       lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"boom")):
            with mock.patch("esbuild.run", broken):
                self.assertEqual(clean("a.js", src), src)
        self.assertEqual(clean("a.js", "const a = 1; // keep\n"), "const a = 1; // keep\n")        # nothing changed: esbuild is not needed

    def test_internal_only_is_dropped_from_fixture_comments_only(self):
        self.assertEqual(clean("tests/t.py", "x = 1  # internal only note\n# INTERNAL-ONLY fixture\ny = 2\n"), "x = 1\ny = 2\n")
        self.assertEqual(clean("src/t.py", "# internal only: never publish\ny = 2\n"), "# internal only: never publish\ny = 2\n")

    def test_it_is_deterministic_and_idempotent(self):
        text = "- (%s, 1-1-2026, relayed by %s: \"x\") %s\n" % (OWNER_N, HEAD_N, BUILDER_N)
        once = pp.scrub("docs/g.md", text.encode())
        self.assertEqual(once, pp.scrub("docs/g.md", text.encode()))
        self.assertEqual(pp.scrub("docs/g.md", once), once)
        real = subprocess.run(["git", "hash-object", "--stdin"], input=b"hello\n", stdout=subprocess.PIPE, env=dict(SAFE),
                              check=True).stdout.decode().strip()
        self.assertEqual(pp.git_blob_sha(b"hello\n"), real)

    def test_files_it_cannot_read_as_text_are_left_for_the_guard(self):
        raw = b"\xff\xfe" + ("%s\n" % OWNER_N).encode("utf-16-le")
        self.assertEqual(pp.scrub("docs/h.md", raw), raw)
        self.assertEqual(pp.scrub("data.json", ('{"a": "%s"}' % OWNER_N).encode()), ('{"a": "%s"}' % OWNER_N).encode())
        self.assertEqual(pp.scrub("x.png", b"\x89PNG" + OWNER_N.encode()), b"\x89PNG" + OWNER_N.encode())


class TheListedWordGuard(unittest.TestCase):
    def found(self, path, data):
        return pp.guard_findings([pp.Entry(5, "100644", "0" * 40, len(data), path)], [data])

    def test_case_quotes_and_possessives(self):
        for form in (OWNER_N.upper(), OWNER_N.lower(), OWNER_N + "'s", OWNER_N + "\u2019s", "(" + OWNER_N + ")", '"' + OWNER_N + '"'):
            with self.subTest(form):
                self.assertFalse(has_listed(clean("docs/c.md", "word %s word\n" % form)), form)
                self.assertTrue(pp.guard_kinds("docs/c.md", ("word %s word\n" % form).encode()), form)

    def test_common_words_count_only_when_capitalised_and_whole(self):
        for text in ("a %s ad\n" % BUILDER_N.lower(), "%ss and %s_x\n" % (BUILDER2_N, BUILDER_N.lower()), "%sx\n" % BUILDER_N,
                     "capture %s\n" % pp.reveal("Pnc").lower(), "the %s\n" % pp.reveal("Cnexre").upper()):
            with self.subTest(text):
                self.assertEqual(pp.guard_kinds("docs/d.md", text.encode()), set(), text)
        for text in ("a %s ad\n" % BUILDER_N, "%s's\n" % BUILDER2_N, "(%s)\n" % pp.reveal("Fgnex")):
            with self.subTest(text):
                self.assertEqual(pp.guard_kinds("docs/d.md", text.encode()), {"a person's name"}, text)

    def test_a_name_in_python_code_is_a_failure_while_the_comment_is_dropped(self):
        out = clean("src/m.py", 'y = "%s"  # %s\n' % (OWNER_N, OWNER_N))
        self.assertEqual(out, 'y = "%s"\n' % OWNER_N)
        self.assertEqual(pp.guard_kinds("src/m.py", out.encode()), {"a person's name"})

    def test_a_name_anywhere_is_refused_by_file_number_only(self):
        for label, path, data in (("code", "src/a.py", 'x = "%s"\n' % OWNER_N), ("json", "d.json", '{"k": "%s"}' % LEAD_N),
                                  ("path", "docs/%s-notes.txt" % OWNER_N.lower(), "fine"), ("repo", "a.txt", "see %s" % PLAN_REPO.upper()),
                                  ("host", "a.sh", "ssh %s" % HOST_N.lower()), ("zero-width", "a.txt", OWNER_N[:2] + "\u200b" + OWNER_N[2:]),
                                  ("soft hyphen", "a.txt", OWNER_N[:2] + "\u00ad" + OWNER_N[2:]),
                                  ("utf-16", "a.txt", ("name: %s\n" % OWNER_N).encode("utf-16")),
                                  ("utf-16 no mark", "a.txt", ("name: %s\n" % OWNER_N).encode("utf-16-le")),
                                  ("NULs", "a.bin", b"\0\0" + OWNER_N.encode() + b"\0\0")):
            with self.subTest(label):
                got = self.found(path, data if isinstance(data, bytes) else data.encode("utf-8"))
                self.assertTrue(got, label)
                self.assertTrue(all(g.startswith("file #5") for g in got))
                self.assertFalse(has_listed(" ".join(got)), got)

    def test_a_name_in_a_binary_office_file_or_a_nested_zip_is_refused(self):
        inner = office("<w:t>by %s</w:t>" % OWNER_N, "word/document.xml")
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as z:
            z.writestr("a/inner.docx", inner)
        for label, data in (("docx", inner), ("nested", nested.getvalue()),
                            ("part name", office("fine", "word/%s.xml" % OWNER_N)),
                            ("utf-16 part", office(("by %s" % OWNER_N).encode("utf-16"), "word/d.xml"))):
            with self.subTest(label):
                got = self.found("docs/x.docx", data)
                self.assertTrue(got and all(g.startswith("file #5") for g in got), got)
                self.assertFalse(has_listed(" ".join(got)))
        self.assertEqual(self.found("docs/x.docx", office("<w:t>fine</w:t>")), [])

    def test_the_allowed_product_word_is_pinned_by_count(self):
        path = "system/prototype/help.js"
        one = "['%s', 'Open the report with a message', 'Full'],\n" % BUILDER_N
        self.assertEqual(self.found(path, one.encode()), [])
        self.assertTrue(self.found(path, (one + one).encode()))
        self.assertTrue(self.found("system/prototype/other.js", one.encode()))
        self.assertTrue(self.found(path, ("%s said\n" % OWNER_N).encode()))

    FIRST_NAMES_ANY_CASE = ("Angnfun", "Ebznabss", "Jnaqn", "Znkvzbss", "Wneivf", "Nyna", "Znuba")                 # ROT13
    FIRST_NAMES_CAPITALISED = ("Fpbgg", "Crgre", "Cnexre", "Oehpr", "Onaare", "Gbal", "Fgnex", "Fgrir", "Ebtref", "Pnc", "Ynat")
    FULL_NAMES = (("Angnfun", "Ebznabss"), ("Jnaqn", "Znkvzbss"), ("Fpbgg", "Ynat"), ("Crgre", "Cnexre"), ("Oehpr", "Onaare"),
                  ("Gbal", "Fgnex"), ("Fgrir", "Ebtref"), ("Nyna", "Znuba"))

    def test_every_team_first_name_and_persona_name_is_on_the_list(self):
        for rot in self.FIRST_NAMES_ANY_CASE:
            word = pp.reveal(rot)
            self.assertIn(word, pp.PEOPLE_ANY_CASE)
            for form in (word, word.lower(), word.upper(), word + "'s"):
                with self.subTest(form):
                    self.assertTrue(self.found("docs/a.md", ("see %s here\n" % form).encode()), form)
        for rot in self.FIRST_NAMES_CAPITALISED:
            word = pp.reveal(rot)
            self.assertIn(word, pp.PEOPLE_CAPITALISED)
            with self.subTest(word):
                self.assertTrue(self.found("docs/a.md", ("see %s here\n" % word).encode()), word)
                self.assertTrue(self.found("docs/a.md", ("see %s's here\n" % word).encode()), word)
                for plain in (word.lower(), word.upper(), word + "x", "x" + word.lower(), word + "s"):
                    self.assertEqual(self.found("docs/a.md", ("see %s here\n" % plain).encode()), [], plain)
        self.assertEqual(len(pp.PEOPLE_ANY_CASE) + len(pp.PEOPLE_CAPITALISED), 18)

    def test_first_names_and_full_names_are_refused_by_file_number_in_every_kind_of_file(self):
        for first, last in self.FULL_NAMES:
            full = "%s %s" % (pp.reveal(first), pp.reveal(last))
            for label, path, data in (("md", "docs/a.md", "by %s\n" % full), ("py code", "src/a.py", 'WHO = "%s"\n' % full),
                                      ("js code", "a.js", "const w = '%s';\n" % full), ("json", "a.json", '{"w": "%s"}' % full),
                                      ("utf-16", "a.txt", ("by %s\n" % full).encode("utf-16")),
                                      ("zip", "docs/a.docx", office("<w:t>%s</w:t>" % full))):
                with self.subTest((full, label)):
                    got = self.found(path, data if isinstance(data, bytes) else data.encode("utf-8"))
                    self.assertTrue(got and all(g.startswith("file #5") for g in got), got)
                    self.assertFalse(has_listed(" ".join(got)))
            for one in (first, last):
                with self.subTest(pp.reveal(one)):
                    self.assertTrue(self.found("src/a.py", ('WHO = "%s"\n' % pp.reveal(one)).encode()))

    def test_the_allowance_is_for_the_product_word_only(self):
        path = "system/prototype/help.js"
        product = "['%s', 'Open the report with a message', 'Full'],\n" % BUILDER_N
        self.assertEqual(self.found(path, product.encode()), [])
        self.assertTrue(self.found(path, (product + "// %s\n" % pp.reveal("Fpbgg")).encode()))
        self.assertTrue(self.found(path, (product + "x = '%s'\n" % pp.reveal("Gbal")).encode()))

    TEMPLATE_PATHS = ("src/clark/page/src/help/helpContent.json", "tests/test_help_content.py", "tests/test_help_shown.py")

    def test_the_template_name_is_allowed_in_its_own_files_at_its_count(self):
        self.assertEqual(sorted(pp.TEMPLATE_NAME_PATHS), sorted(self.TEMPLATE_PATHS))
        for path in self.TEMPLATE_PATHS:
            with self.subTest(path):
                self.assertEqual(pp.TEMPLATE_NAME_PATHS[path], 1)
                self.assertEqual(self.found(path, ('"%s", "Open with a message"\n' % BUILDER_N).encode()), [])

    def test_the_template_name_in_any_other_file_is_refused_by_file_number(self):
        for path in ("src/clark/page/src/logic/templates.js", "docs/other.md", "tests/test_other.py", "src/clark/page/src/help/other.json",
                     "system/prototype/other.js"):
            with self.subTest(path):
                got = self.found(path, ('"%s", "Open with a message"\n' % BUILDER_N).encode())
                self.assertEqual(got, ["file #5: a person's name"])
                self.assertFalse(has_listed(" ".join(got)))

    def test_one_more_than_the_count_is_refused_in_each_allowed_file(self):
        for path in self.TEMPLATE_PATHS:
            with self.subTest(path):
                one = '"%s", "Open with a message"\n' % BUILDER_N
                self.assertTrue(self.found(path, (one + one).encode()))
                self.assertTrue(self.found(path, (one + "see %s's note\n" % BUILDER_N).encode()))

    def test_a_second_use_in_an_allowed_file_names_the_limit_and_the_next_step(self):
        for path in self.TEMPLATE_PATHS:
            with self.subTest(path):
                one = '"%s", "Open with a message"\n' % BUILDER_N
                got = self.found(path, (one + one).encode())
                self.assertEqual(got, ["file #5: " + pp.TEMPLATE_LIMIT_KIND])
                self.assertIn("Remove the extra use", got[0])
                self.assertIn("raised", got[0])
                self.assertFalse(has_listed(" ".join(got)))

    def test_the_word_in_mixed_encodings_in_an_allowed_file_is_refused_as_over_the_limit(self):
        word = BUILDER_N
        mixed = word.encode() + b"\0\0" + word.encode("utf-16-le")
        for path in self.TEMPLATE_PATHS:
            with self.subTest(path):
                self.assertEqual(self.found(path, mixed), ["file #5: " + pp.TEMPLATE_LIMIT_KIND])
                self.assertEqual(self.found(path, ('"%s", "x"\n' % word).encode()), [])

    def test_the_template_allowance_covers_that_one_word_only(self):
        for path in self.TEMPLATE_PATHS:
            for other in (OWNER_N, LEAD_N, BUILDER2_N, pp.reveal("Fpbgg"), pp.reveal("Gbal")):
                with self.subTest((path, other)):
                    data = ('"%s", "x"\nwho: %s\n' % (BUILDER_N, other)).encode()
                    self.assertEqual(self.found(path, data), ["file #5: a person's name"])
            with self.subTest((path, "repo")):
                self.assertTrue(self.found(path, ('"%s"\nsee %s\n' % (BUILDER_N, PLAN_REPO)).encode()))

    def test_clean_files_pass(self):
        self.assertEqual(self.found("docs/a.md", b"nothing to see here, a banner of text? no: a banner.\n"), [])
        self.assertEqual(self.found("a.png", b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"), [])


def spelled(name, sep):
    return sep.join(name.split("-"))


class ThePrivateNamesInEverySpelling(unittest.TestCase):
    """A private repo or board name is found whatever sits between its words (round 3, finding 1)."""
    SEPARATORS = ("-", " ", "_", ".", "  ", "\u00a0", " - ",
                  "\u2011", "\u2013", "\u2014", "\u2212", "\\-", "\\_", "**-**", "`-`", "+", "/", "\u2010", "\u2015")

    def test_the_guard_finds_every_separator_and_case(self):
        for name in (TEAM_REPO, PLAN_REPO, SECRET_REPO, PLAN_REPO2):
            for sep in self.SEPARATORS:
                for form in (spelled(name, sep), spelled(name, sep).upper(), "the " + spelled(name, sep)):
                    with self.subTest(sep=repr(sep), name=name[:2]):
                        self.assertEqual(pp.guard_kinds("docs/x.md", ("see %s now\n" % form).encode()),
                                         {"a private repo or board name"})

    def test_the_scrub_rewrites_every_spelling_to_the_plain_phrase(self):
        for name, phrase in ((TEAM_REPO, "the team repo"), (PLAN_REPO, "the planning repo"), (SECRET_REPO, "a private repo"),
                             (PLAN_REPO2, "a private repo")):
            for sep in self.SEPARATORS:
                with self.subTest(sep=repr(sep), name=name[:2]):
                    out = clean("docs/x.md", "Use %s today.\n" % spelled(name, sep))
                    self.assertEqual(out, "Use %s today.\n" % phrase)
                    self.assertFalse(has_listed(out))
        self.assertEqual(clean("docs/x.md", "In `insyncalan/%s`.\n" % spelled(PLAN_REPO, "_")), "In the planning repo.\n")

    def test_a_comment_in_code_names_a_plain_phrase_and_code_is_refused(self):
        self.assertEqual(clean("src/a.py", "x = 1\n# see %s\ny = 2\n" % spelled(PLAN_REPO, " ")), "x = 1\n# see the planning repo\ny = 2\n")
        self.assertEqual(pp.guard_kinds("src/a.py", ('x = "%s"\n' % spelled(TEAM_REPO, "_")).encode()), {"a private repo or board name"})

    def test_ordinary_words_are_left_alone(self):
        for text in ("a plan for the team", "clark is a tool\n", "avengers assemble\n", "the plan of the client\n"):
            self.assertEqual(pp.guard_kinds("docs/x.md", text.encode()), set(), text)


class TheRepoNameEndsAtAWordEnd(unittest.TestCase):
    """Round 3 review: a private repo's name inside a longer word is not the name (it was cut: 'planning' became 'reponing')."""
    def test_a_longer_word_is_left_whole_by_the_scrub_and_the_guard(self):
        for name in (TEAM_REPO, PLAN_REPO):
            for tail in ("ning doc", "s are", "ner", "2 here", "x"):
                with self.subTest(name[:2], tail=tail):
                    text = "See %s%s now.\n" % (name, tail)
                    self.assertEqual(clean("docs/x.md", text), text)
                    self.assertEqual(pp.guard_kinds("docs/x.md", text.encode()), set())

    def test_the_name_alone_or_before_punctuation_is_still_found(self):
        for end in (" doc", ".", ",", ")", "`", "'s", "\n", ""):
            with self.subTest(end=end):
                self.assertEqual(pp.guard_kinds("docs/x.md", ("see %s%s" % (PLAN_REPO, end)).encode()), {"a private repo or board name"})
        self.assertEqual(clean("docs/x.md", "In %s planning.\n" % PLAN_REPO), "In the planning repo planning.\n")


class ThePythonStaysValid(unittest.TestCase):
    """Round 3 review: if scrubbing a .py file would leave it unable to run, the original bytes are kept and the guard refuses."""
    BROKEN_BY_THE_SCRUB = "x = 1 \\\n  # %s\n" % OWNER_N

    def test_the_example_is_valid_python_until_the_comment_is_dropped(self):
        import ast
        ast.parse(self.BROKEN_BY_THE_SCRUB)
        self.assertEqual(pp.scrub_text("a.py", self.BROKEN_BY_THE_SCRUB), "x = 1 \\\n")

    def test_a_file_the_scrub_would_break_keeps_its_original_bytes_and_is_refused_by_number(self):
        data = self.BROKEN_BY_THE_SCRUB.encode()
        self.assertEqual(pp.scrub("src/a.py", data), data)
        entry = pp.Entry(9, "100644", "0" * 40, len(data), "src/a.py")
        self.assertEqual(pp.guard_findings([entry], [pp.scrub("src/a.py", data)]), ["file #9: a person's name"])

    def test_a_valid_result_is_still_scrubbed(self):
        self.assertEqual(clean("src/a.py", "x = 1\n# %s\ny = 2\n" % OWNER_N), "x = 1\ny = 2\n")

    def test_other_files_are_not_parsed(self):
        self.assertEqual(clean("docs/a.md", "x = 1 \\\n  %s\n" % OWNER_N), "x = 1 \\\n  The owner\n")


class TheVeryLongLine(unittest.TestCase):
    """Round 3 review: a line over MAX_LINE characters is not read by the prose rules (a 40,000-character run took half a minute);
    it is left as it is and the guard, which is fast, refuses it by file number if it holds a listed word."""
    def test_a_long_run_is_quick_in_the_scrub_and_the_guard(self):
        import time
        for unit in ("a", "a-", " ", " and ", "-_ ", "a/"):
            data = ((unit * (40000 // len(unit))) + "\n").encode()
            start = time.time()
            pp.scrub("docs/x.md", data)
            pp.guard_kinds("docs/x.md", data)
            self.assertLess(time.time() - start, 5, repr(unit))

    def test_a_listed_word_on_a_long_line_is_left_by_the_scrub_and_refused_by_the_guard(self):
        line = ("word " * (pp.MAX_LINE // 5 + 1)) + OWNER_N + "\n"
        self.assertGreater(len(line), pp.MAX_LINE)
        data = ("short %s line\n%s" % (OWNER_N, line)).encode()
        out = pp.scrub("docs/x.md", data).decode()
        self.assertEqual(out.split("\n")[1], line.rstrip("\n"))                  # the long line is untouched
        self.assertNotIn("short %s" % OWNER_N, out)                              # the short line is still scrubbed
        entry = pp.Entry(4, "100644", "0" * 40, len(out), "docs/x.md")
        self.assertEqual(pp.guard_findings([entry], [out.encode()]), ["file #4: a person's name"])

    def test_lines_at_the_limit_are_still_scrubbed(self):
        line = "x" * (pp.MAX_LINE - len(OWNER_N) - 1) + " " + OWNER_N
        self.assertEqual(len(line), pp.MAX_LINE)
        self.assertNotIn(OWNER_N, clean("docs/x.md", "top\n" + line + "\n"))


class TheNamePairIsDropped(unittest.TestCase):
    """The lower-case pair of names (round 3, finding 2) is dropped from a Markdown line and from a Python comment."""
    PAIR = "%s and %s" % (pp.reveal("Onaare").lower(), pp.reveal("Ynat").lower())

    def test_a_markdown_line_holding_only_a_pair_is_dropped(self):
        self.assertEqual(clean("docs/d.md", "Handled by %s today.\nnext line\n" % self.PAIR), "next line\n")

    def test_a_python_comment_holding_a_pair_is_dropped(self):
        self.assertEqual(clean("src/a.py", "x = 1\n# done by %s\ny = 2\n" % self.PAIR), "x = 1\ny = 2\n")

    def test_a_pair_in_python_code_is_refused(self):
        self.assertEqual(pp.guard_kinds("src/a.py", ('x = "%s"\n' % self.PAIR).encode()), {"a person's name"})


class TheTeamBranchesAndLowerCaseNames(unittest.TestCase):
    """A team's branch name and a lower-case pair of names are scrubbed and guarded (round 3, finding 2)."""
    NAMES = [pp.reveal(w) for w in ("Onaare", "Ynat", "Fgnex", "Cnexre", "Pnc", "Nyna", "Jnaqn")]

    def test_a_branch_keeps_its_shape_with_a_plain_word_in_prose_and_comments(self):
        for name in self.NAMES:
            for form in (name.lower(), name.upper(), name):
                with self.subTest(name[:2], form=form[:2]):
                    md = clean("docs/h.md", "From `origin/team-%s-31-store` and team_%s-3.\n" % (form, form))
                    self.assertEqual(md, "From `origin/team-a-31-store` and team_a-3.\n")
                    self.assertEqual(clean("src/e.py", "x = 1\n# on team-%s-35-page-shell\n" % form), "x = 1\n# on team-a-35-page-shell\n")
                    self.assertFalse(has_listed(md))

    def test_the_guard_refuses_a_branch_in_code_or_any_file(self):
        for name in self.NAMES:
            for path, data in (("tests/t.py", 'B = ("main", "team-%s-70-tiers")\n' % name.lower()), ("d.json", '{"b": "Team_%s"}' % name),
                               ("a.txt", "team.%s." % name.upper())):
                with self.subTest(name[:2], path=path):
                    self.assertEqual(pp.guard_kinds(path, data.encode()), {"a person's name"})

    def test_words_that_only_look_like_it_pass(self):
        for text in ("team-a-31-store\n", "team-%slike\n" % self.NAMES[0].lower(), "the team will be ready\n", "team-<name>-<issue>\n",
                     "teammate-%s\n" % self.NAMES[1].lower()):
            with self.subTest(text):
                self.assertEqual(pp.guard_kinds("docs/x.md", text.encode()), set(), text)

    def test_a_lower_case_pair_of_names_is_refused_and_a_quoted_one_is_dropped(self):
        a, b = self.NAMES[0].lower(), self.NAMES[1].lower()
        for text in ("so %s and %s do it\n" % (a, b), "%s, %s\n" % (a, b), "%s/%s\n" % (a, b), "%s & %s\n" % (a, b)):
            with self.subTest(text[:3]):
                self.assertEqual(pp.guard_kinds("docs/x.md", text.encode()), {"a person's name"})
        out = clean("docs/m.md", 'Teams are X (%s, 28-10-2026: "team will be %s and %s. I\'ll onboard them"). Next.\n' % (OWNER_N, a, b))
        self.assertEqual(out, "Teams are X. Next.\n")
        self.assertFalse(has_listed(out))
        self.assertEqual(pp.guard_kinds("docs/x.md", b"one name alone, %s, passes\n" % a.encode()), set())

    def test_this_repos_own_files_hold_no_team_branch(self):
        root = Path(__file__).resolve().parents[1]
        for path in ("tests/test_workflow.py", "src/clark/excel_colours.py"):
            text = (root / path).read_text(encoding="utf-8")
            self.assertIsNone(pp._TEAM_BRANCH.search(pp.rewrite_region(text)) if path.endswith("colours.py") else pp._TEAM_BRANCH.search(text), path)


class TheRefusalPrintsNoName(Base):
    """Round 3, finding 3: nothing printed holds a listed word, whichever name check refused."""
    def test_the_removed_notes_line_gives_counts_not_file_names(self):
        self.make_private(dict(GOOD, **{HANDOVER: "x\n", HANDOVER_OTHER: "y\n", "dev/HEAD-LOG.md": "z\n"}))
        for flags in ((), ("--dry-run",)):
            code, out = self.go(*flags)
            line = out.split("internal notes removed")[1].split("\n")[1]
            self.assertRegex(line, r"^\s+\d+ file\(s\) taken out by \d+ rule\(s\) on the exclusion list$")
            self.assertFalse(has_listed(out), "a listed word was printed")
            self.assertNotIn("HEAD-LOG", out)

    def test_no_path_is_printed_while_either_name_check_has_failed_and_the_removal_line_is_clean(self):
        for label, files in (("private name left", {"docs/%s-x.txt" % PLAN_REPO: "fine"}),
                             ("a person in a path", {"docs/%s.txt" % OWNER_N.upper(): "fine"})):
            with self.subTest(label):
                self.setUp()
                self.make_private(dict(GOOD, **dict(files, **{HANDOVER: "x\n"})))
                code, out = self.go("--dry-run")
                self.assertEqual(code, 1, out)
                self.assertFalse(has_listed(out), "a listed word was printed")
                self.assertRegex(out, r"(?m)^  #\d+$")


class TheCommitMessage(unittest.TestCase):
    """Round 3, finding 4: a listed word in a ref name never reaches the public commit message."""
    def message(self, ref):
        import argparse
        return pp.commit_message(argparse.Namespace(ref=ref), "abcdef0123456789")

    def test_a_plain_ref_is_kept_and_a_ref_with_a_listed_word_falls_back_to_the_short_sha(self):
        self.assertEqual(self.message("release-0.1.0"), "clark release-0.1.0 (abcdef0)")
        for ref in ("release-%s" % OWNER_N, "release-%s" % OWNER_N.lower(), "x/%s-fix" % LEAD_N.upper(), "b/%s" % PLAN_REPO,
                    "team-%s-31-store" % BUILDER_N.lower(), "v1-%s" % HOST_N):
            with self.subTest(ref[:4]):
                self.assertEqual(self.message(ref), "clark abcdef0 (abcdef0)")
                self.assertFalse(has_listed(self.message(ref)))


class TheVariantSpellings(unittest.TestCase):
    """Round 3, finding 5: a listed word written in a disguised form is still found."""
    def kinds(self, text, path="a.txt"):
        return pp.guard_kinds(path, text if isinstance(text, bytes) else text.encode("utf-8"))

    def test_invisible_and_format_characters_anywhere_inside_a_word(self):
        for ch in ("\u2062", "\u202a", "\u202e", "\u034f", "\ufe0f", "\u200d", "\u2060", "\ufeff", "\u00ad", "\U000e0100", "\u180e"):
            for word in (OWNER_N, DESIGNER_N, PLAN_REPO):
                with self.subTest(ch=repr(ch), w=word[:2]):
                    self.assertTrue(self.kinds(word[:2] + ch + word[2:]))

    def test_compatibility_forms(self):
        wide = "".join(chr(ord(c) + 0xFEE0) if c.isascii() and c.isalpha() else c for c in OWNER_N)
        self.assertTrue(self.kinds(wide))
        self.assertTrue(self.kinds(wide.upper()))

    def test_entities_percent_encoding_and_escapes(self):
        w = DESIGNER_N
        forms = ("&#%d;%s" % (ord(w[0]), w[1:]), "&#x%x;%s" % (ord(w[0]), w[1:]), "%%%02X%s" % (ord(w[0]), w[1:]), "%%%02x%s" % (ord(w[0]), w[1:]),
                 "\\u%04x%s" % (ord(w[0]), w[1:]), "\\x%02x%s" % (ord(w[0]), w[1:]), "&amp;#%d;%s" % (ord(w[0]), w[1:]),
                 "%%25%02X%s" % (ord(w[0]), w[1:]), "%s%%20%s" % (PLAN_REPO[:5], PLAN_REPO[6:]))
        for form in forms:
            with self.subTest(form[:8]):
                self.assertTrue(self.kinds(form))

    def test_a_name_split_over_markup(self):
        w = HEAD_N
        for part in ("</w:t></w:r><w:r><w:t>", "<b></b>", "<w:br/>"):
            with self.subTest(part):
                self.assertTrue(self.kinds(w[:3] + part + w[3:]))
                self.assertTrue(pp.guard_findings([pp.Entry(7, "100644", "0" * 40, 1, "d.docx")], [office("<w:t>%s</w:t>" % (w[:3] + part + w[3:]))]))

    def test_the_long_names_are_found_inside_a_longer_word_and_the_short_ones_are_not(self):
        for name in (HEAD_N, DESIGNER_N, LEAD_N):
            for text in ("%sBot" % name, "%s2" % name, "x%sy" % name.lower(), "my_%s_id" % name):
                with self.subTest(text[:3]):
                    self.assertEqual(self.kinds(text), {"a person's name"})
                    self.assertFalse(has_listed(clean("docs/w.md", text + "\n")))
        self.assertEqual(clean("docs/w.md", "%sBot is on.\n" % HEAD_N), "The Head Bot is on.\n")
        self.assertEqual(self.kinds("%sx and %s2\n" % (OWNER_N, OWNER_N)), set())          # the four-letter name stays a whole word

    def test_plain_text_still_passes(self):
        for text in ("Work items, owners and a plan.\n", "caf\u00e9 \u2014 100%% done &amp; dusted\n", "ZWJ \u200d emoji \U0001f468\u200d\U0001f469\n"):
            self.assertEqual(self.kinds(text), set(), text)


class TheScrubReadsWell(unittest.TestCase):
    """Round 3, finding 6: what the scrub leaves is plain text, not a cut sentence or a stutter."""
    def test_team_and_a_name_is_one_role(self):
        n, m = BUILDER_N, BUILDER2_N
        cases = (("Written by Team %s's agent, 28-10-2026, as groundwork.\n" % n, "Written by a teammate's agent, 28-10-2026, as groundwork.\n"),
                 ("(#10 Team %s, #11 Team %s: their reserved channels)\n" % (n, m), "(#10 a teammate, #11 a teammate: their reserved channels)\n"),
                 ("Team %s builds; %s reviews.\n" % (n, m), "A teammate builds; a teammate reviews.\n"),
                 ("Teams are %s and %s.\n" % (n, m), "Teams are teammates.\n"),
                 ("%s, %s and %s took it.\n" % (n, m, OWNER_N), "Teammates and the owner took it.\n"),
                 ("%s keeps it.\n" % spelled(TEAM_REPO, " "), "The team repo keeps it.\n"))
        for before, after in cases:
            with self.subTest(after):
                self.assertEqual(clean("docs/t.md", before), after)

    def test_a_list_of_the_same_private_repo_says_it_once(self):
        a, b, c = SECRET_REPO, PLAN_REPO2, TEAM_REPO
        self.assertEqual(clean("docs/r.md", "nothing from creaite's private repos (%s, %s, %s) is copied.\n" % (a, b, c)),
                         "nothing from creaite's private repos (a private repo, the team repo) is copied.\n")
        self.assertEqual(clean("docs/r.md", "see %s and %s.\n" % (a, b)), "see a private repo.\n")
        self.assertEqual(clean("docs/r.md", "the %s repo and %s repository\n" % (PLAN_REPO, c)), "The planning repo and the team repo repository\n")

    def test_a_repo_name_with_a_path_in_it_and_a_comment_stay_whole_sentences(self):
        out = clean(".github/workflows/t.yml", "# Run (#70: copied and adapted; the rules are\n# %s Projects/clark/testing-and-ci.md). Actions\n" % TEAM_REPO)
        self.assertEqual(out, "# Run (#70: copied and adapted; the rules are\n# the team repo). Actions\n")
        self.assertFalse(has_listed(out))
        self.assertEqual(clean("docs/p.md", "In %s docs/x.md and `%s`.\n" % (PLAN_REPO, TEAM_REPO)), "In the planning repo and the team repo.\n")

    def test_the_real_tree_leaves_no_team_stutter(self):
        root = Path(__file__).resolve().parents[1]
        known = set(subprocess.run(["git", "ls-files"], cwd=root, stdout=subprocess.PIPE, text=True).stdout.split("\n"))
        stutter = re.compile(r"(?i)\bteams? (?:a teammate|the owner|the head|the project lead)|a teammate(?:,| and) a teammate|"
                             r"(?:the team|the planning|a private) repo (?:repo\b|,\s*(?:the team|the planning|a private) repo)")
        for path in sorted(known):
            if pp.is_excluded(path) or not path.endswith((".md", ".yml", ".py", ".js")) or path.startswith(("tests/test_publish", "dev/tools/publish")):
                continue
            out = pp.scrub(path, (root / path).read_bytes(), known).decode("utf-8", "replace")
            self.assertIsNone(stutter.search(out), path)


class TheScrubInThePublish(Base):
    def planted(self):
        return dict(GOOD, **{
            "docs/RULES.md": "Rules (%s, 28-10-2026, relayed by %s: \"be kind\").\nSee `docs/%s.md` and %s.\n" % (OWNER_N, HEAD_N, REUSE_N, PLAN_REPO),
            "docs/public/README.md": "# demo\nThe public text, by %s.\n" % LEAD_N,
            "src/app.py": '"""App, for %s."""\nprint("hi")  # %s\n' % (BUILDER_N, OWNER_N)})

    def test_the_public_copy_is_scrubbed_and_the_private_repo_is_untouched(self):
        self.make_private(self.planted())
        before = sh("rev-parse", "HEAD:docs/RULES.md", "HEAD:src/app.py", "HEAD:docs/public/README.md", cwd=self.private)
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertEqual(sh("status", "--porcelain", cwd=self.private), "")
        self.assertEqual(sh("rev-parse", "HEAD:docs/RULES.md", "HEAD:src/app.py", "HEAD:docs/public/README.md", cwd=self.private), before)
        self.assertEqual((self.private / "docs" / "RULES.md").read_text(encoding="utf-8"), self.planted()["docs/RULES.md"])
        for name in ("docs/RULES.md", "src/app.py", "README.md"):
            shown = sh("show", "clark-public:" + name, cwd=self.public)
            self.assertFalse(has_listed(shown), name)
        self.assertEqual(sh("show", "clark-public:README.md", cwd=self.public), "# demo\nThe public text, by a teammate.".replace(
            "a teammate", "the project lead"))
        self.assertEqual(sh("show", "clark-public:docs/RULES.md", cwd=self.public),
                         "Rules (\"be kind\").\nSee the reuse record and the planning repo.")
        self.assertEqual(sh("show", "clark-public:src/app.py", cwd=self.public), '""""""\nprint("hi")')
        self.assertIn("PASS     private names scrubbed", out)

    def test_the_published_blob_is_the_scrubbed_bytes_and_a_second_run_publishes_nothing(self):
        self.make_private(self.planted())
        self.assertEqual(self.go()[0], 0)
        want = pp.scrub("docs/RULES.md", self.planted()["docs/RULES.md"].encode(), None)
        self.assertEqual(sh("rev-parse", "clark-public:docs/RULES.md", cwd=self.public), pp.git_blob_sha(want))
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertIn("Nothing to publish", out)
        self.assertEqual(len(self.commits()), 1)

    def test_the_tests_of_the_snapshot_get_the_scrubbed_files(self):
        self.make_private(self.planted())
        seen = []

        def look(python, checkout):
            seen.append((Path(checkout) / "docs" / "RULES.md").read_text(encoding="utf-8"))
            return True, "3.%d" % len(seen)

        self.go("--dry-run", "--with-tests", run_tests=look)
        self.assertEqual(len(seen), 2)
        self.assertFalse(any(has_listed(t) for t in seen))


class TheGuardInThePublish(Base):
    def test_a_clean_publish_passes_the_guard(self):
        self.make_private(dict(GOOD, **{"docs/RULES.md": "Rules (%s, 28-10-2026: \"be kind\").\n" % OWNER_N}))
        code, out = self.go()
        self.assertEqual(code, 0, out)
        self.assertIn("PASS     no private names left", out)

    def test_a_name_in_code_refuses_the_publish_by_file_number(self):
        self.make_private(dict(GOOD, **{"src/app.py": 'NAME = "%s"\n' % OWNER_N, "data/people.json": '{"n": "%s"}' % LEAD_N}))
        out = self.refused()
        self.assertIn("REFUSED  no private names left", out)
        self.assertRegex(out, r"file #\d+: a person\'s name")
        self.assertFalse(has_listed(out.split("Checks:")[1]), "a word was printed")
        self.assertEqual(self.runs, [])
        code, dry = self.go("--dry-run")
        self.assertEqual(code, 1)
        self.assertFalse(has_listed(dry.split("Checks:")[1]))

    def test_a_path_with_a_listed_word_is_never_printed_only_its_number(self):
        words = [pp.reveal(w) for w in ("Nyna", "Angnfun", "Znuba", "Wneivf", "Onaare", "Fpbgg", "Gbal", "Ebtref")] + [
            PLAN_REPO, TEAM_REPO, SECRET_REPO, PLAN_REPO2, HOST_N, BOX_N, "%s-%s" % (pp.reveal("Crgre"), pp.reveal("Cnexre"))]
        for word in words:
            with self.subTest(word):
                self.setUp()
                self.make_private(dict(GOOD, **{"docs/%s-notes.txt" % word: "fine", "src/ok.py": "x = 1\n"}))
                for flags in ((), ("--dry-run",)):
                    code, out = self.go(*flags)
                    self.assertEqual(code, 1, out)
                    self.assertNotIn(word.lower(), out.lower(), "a path with a listed word was printed")
                    self.assertIn("REFUSED  no private names left", out)
                    self.assertRegex(out, r"Snapshot: \d+ file\(s\) \(listed by number only")
                    self.assertRegex(out, r"(?m)^  #\d+$")
                    self.assertNotIn("src/ok.py", out.split("Checks:")[0])

    def test_the_paths_are_listed_again_when_both_name_checks_pass(self):
        self.make_private(GOOD)
        code, out = self.go("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("  #", out)
        self.assertIn("src/app.py", out.split("Checks:")[0])
        self.assertTrue(pp.names_clear(self._report(pp.PASS, pp.PASS)))
        self.assertFalse(pp.names_clear(self._report(pp.PASS, pp.REFUSED)))
        self.assertFalse(pp.names_clear(self._report(pp.REFUSED, pp.PASS)))
        self.assertFalse(pp.names_clear(self._report(pp.PASS, None)))

    @staticmethod
    def _report(names, private):
        report = pp.Report()
        report.add("no real names", names)
        if private:
            report.add("no private names left", private)
        return report

    def test_a_name_in_a_path_a_zip_or_utf16_refuses(self):
        for label, files in (("path", {"docs/%s-notes.txt" % OWNER_N: "fine"}),
                             ("zip", {"docs/a.docx": office("by %s" % OWNER_N)}),
                             ("utf-16", {"docs/a.txt": ("by %s" % OWNER_N).encode("utf-16")})):
            with self.subTest(label):
                self.setUp()
                self.make_private(dict(GOOD, **files))
                out = self.refused()
                self.assertIn("REFUSED  no private names left", out)
                self.assertFalse(has_listed(out.split("Checks:")[1]))


if __name__ == "__main__":
    unittest.main()


class TheAuthorFlagsAreChecked(Base):
    """Review of fb9b5a0: --author-name and --author-email were committed and echoed with a listed word in them. They are read
    with the scrub's own list and refused by flag number, never printed or committed."""
    def refused(self, *flags):
        self.make_private(GOOD)
        code, out = self.go(*flags)
        self.assertEqual(code, 1, out)
        self.assertFalse(has_listed(out), "a listed word was printed")
        self.assertRegex(out, r"REFUSED +author and message are clear")
        self.assertEqual(self.heads(), [], "nothing is pushed")
        return out

    def test_a_listed_name_as_the_author_name_is_refused_by_flag_number(self):
        out = self.refused("--author-name", OWNER_N)
        self.assertIn("flag #1", out)
        self.assertNotIn("flag #2", out)

    def test_a_listed_name_in_the_author_email_is_refused_by_flag_number(self):
        out = self.refused("--author-email", "%s@x.io" % HEAD_N.lower())
        self.assertIn("flag #2", out)

    def test_spellings_and_the_dry_run_are_refused_too(self):
        for flag, value in (("--author-name", OWNER_N.upper()), ("--author-name", "the %s" % OWNER_N.lower()),
                            ("--author-email", "%s.smith@x.io" % LEAD_N.lower()), ("--author-name", PLAN_REPO)):
            with self.subTest(flag=flag):
                self.setUp()
                self.refused("--dry-run", flag, value)

    def test_a_clear_identity_still_works(self):
        self.make_private(GOOD)
        code, out = self.go("--author-name", "someone", "--author-email", "s@example.invalid")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"PASS +author and message are clear")


class TheScrubHasALimit(Base):
    """Review of fb9b5a0: a million newlines, a million '<', or 500 long lines took the scrub over 40 s and the dry run over 100 s, and
    some Python files raised MemoryError. Each of those is now quick (or refused by file number) and never a traceback."""
    def quick(self, path, data, seconds=4):
        import signal
        import time

        def too_slow(_signum, _frame):
            raise AssertionError("still reading after %d seconds" % (seconds * 4))
        old = signal.signal(signal.SIGALRM, too_slow)        # a regression must fail the test, not hang it
        signal.alarm(seconds * 4)
        try:
            start = time.time()
            pp.scrub(path, data)
            pp.guard_kinds(path, data)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        self.assertLess(time.time() - start, seconds)

    def test_a_million_newlines_is_refused_by_file_number_without_being_read(self):
        data = b"\n" * 1000000
        self.quick("docs/x.md", data)
        entry = pp.Entry(7, "100644", "0" * 40, len(data), "docs/x.md")
        self.assertEqual(pp.scrub_limit_findings([entry], [data]), ["file #7: too long to scrub safely (over %d lines or %d KB)"
                                                                      % (pp.MAX_SCRUB_LINES, pp.MAX_SCRUB_BYTES // 1024)])
        self.assertEqual(pp.scrub("docs/x.md", data), data)

    def test_the_line_count_and_the_size_each_make_the_limit(self):
        many = b"a\n" * (pp.MAX_SCRUB_LINES + 1)
        big = b"a" * (pp.MAX_SCRUB_BYTES + 1)
        for name, data in (("lines", many), ("bytes", big)):
            entry = pp.Entry(1, "100644", "0" * 40, len(data), "docs/x.md")
            self.assertEqual(len(pp.scrub_limit_findings([entry], [data])), 1, name)
        fine = b"a\n" * pp.MAX_SCRUB_LINES
        self.assertEqual(pp.scrub_limit_findings([pp.Entry(1, "100644", "0" * 40, len(fine), "docs/x.md")], [fine]), [])
        other = pp.Entry(1, "100644", "0" * 40, len(big), "data.bin")
        self.assertEqual(pp.scrub_limit_findings([other], [big]), [])             # only the files the scrub would read

    def test_a_file_over_the_limit_is_refused_in_a_publish_and_nothing_is_pushed(self):
        self.make_private(dict(GOOD, **{"docs/long.md": "\n" * (pp.MAX_SCRUB_LINES + 5)}))
        for flags in ((), ("--dry-run",)):
            code, out = self.go(*flags)
            self.assertEqual(code, 1, out)
            self.assertRegex(out, r"file #\d+: too long to scrub safely")
            self.assertFalse(has_listed(out))
        self.assertEqual(self.heads(), [])

    def test_a_run_of_angle_brackets_is_quick_in_the_scrub_and_the_guard(self):
        self.quick("docs/x.md", b"<" * 900000)

    def test_a_run_of_square_brackets_is_quick(self):
        self.quick("docs/x.md", b"[" * 900000)

    def test_the_repo_name_and_a_hyphen_over_and_over_is_quick(self):
        self.quick("docs/x.md", (PLAN_REPO.split("-")[0] + "-").encode() * 100000)

    def test_many_long_lines_are_quick(self):
        for unit in ("a", " ", "x  ", "the  x", "-_ ", " and ", "[", "<", "[x](", "(", "`", "*"):
            with self.subTest(unit=repr(unit)):
                line = (unit * (1990 // len(unit) + 1))[:1990] + "\n"
                self.quick("docs/x.md", (line * 100).encode())

    def test_long_runs_of_white_space_are_left_alone_and_a_name_beside_one_is_still_scrubbed(self):
        self.assertEqual(clean("docs/x.md", "a%sb %s here\n" % (" " * 100, OWNER_N)), "a%sb the owner here\n" % (" " * 100))

    def test_real_sized_files_are_scrubbed_as_before(self):
        text = "".join("line %d by %s\n" % (n, OWNER_N) for n in range(5000))
        self.assertNotIn(OWNER_N, clean("docs/x.md", text))

    def test_python_that_runs_out_of_memory_or_depth_is_left_to_the_guard_not_a_crash(self):
        import ast
        for error in (MemoryError, RecursionError):
            with self.subTest(error=error.__name__), mock.patch.object(ast, "parse", side_effect=error):
                self.assertIsNone(pp.python_spans("x = 1  # note\n"))
                data = ("x = 1  # %s\n" % OWNER_N).encode()
                self.assertEqual(pp.scrub("src/a.py", data), data)

    def test_the_real_python_repros_do_not_crash(self):
        for text in ((OWNER_N + " ") * 143000, "-" * 1000000, "the  x " * 140000):
            self.quick("src/a.py", text.encode(), seconds=8)

    def test_a_statement_too_deep_to_parse_is_left_alone_without_calling_the_parser(self):
        import ast
        deep = ("x = " + "-" * (pp.MAX_LOGICAL_TOKENS + 5) + "1  # " + OWNER_N + "\n")
        with mock.patch.object(ast, "parse", side_effect=AssertionError("parsed")):
            self.assertIsNone(pp.python_spans(deep))
            self.assertEqual(pp.scrub("src/a.py", deep.encode()), deep.encode())
        self.assertTrue(pp._runaway_statement(deep))
        self.assertFalse(pp._runaway_statement("x = [\n" + "1,\n" * 3000 + "]\n"))          # a long list is not deep
        self.assertEqual(clean("src/a.py", "y = (1,\n" + "     2,\n" * 9000 + ")  # " + OWNER_N + "\n").count(OWNER_N), 0)

    def test_a_memory_error_anywhere_in_a_run_is_a_refusal_not_a_traceback(self):
        self.make_private(GOOD)
        with mock.patch.object(pp, "scrub_entries", side_effect=MemoryError):
            code, out = self.go()
        self.assertEqual(code, 1, out)
        self.assertIn("REFUSED: a file was too large", out)
        self.assertNotIn("Traceback", out)

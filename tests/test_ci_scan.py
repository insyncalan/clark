"""The CI scan (0.2.1): dev/tools/ci_scan.py refuses what it must, passes a clean change and never prints a matched word;
.github/workflows/scan.yml keeps the safety rules (read-only, no secrets, pull_request, pinned SHAs, off until switched on).

Run: python3 dev/run_tests.py test_ci_scan   (quick tier)
"""
import contextlib
import io
import os
import re
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from _paths import ROOT

import ci_scan
import publish_public as pp

WORKFLOW = ROOT / ".github" / "workflows" / "scan.yml"
NOREPLY = "t@users.noreply.github.com"
SECRET = "ghp_" + "a1B2c3D4" * 3
LISTED = pp.reveal("Znuba")                      # a listed first name, built here so this file does not carry it


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png():
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(b"\0\0")) + _chunk(b"IEND", b""))


def png_with_text(kind=b"tEXt", payload=b"Comment\0hello"):
    """A well-formed PNG that also carries one of the text chunks, where bytes of any kind can be hidden."""
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
            + _chunk(kind, payload) + _chunk(b"IDAT", zlib.compress(b"\0\0")) + _chunk(b"IEND", b""))


def jpeg():
    return (b"\xff\xd8" + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            + b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00" + b"\x12\xff\x00\x34\xff\xd0\x56" + b"\xff\xd9")


def gif():
    return (b"GIF89a" + b"\x01\x00\x01\x00\x80\x00\x00" + b"\0" * 6 + b"\x21\xf9\x04\x00\x00\x00\x00\x00"
            + b"\x2c" + b"\0" * 8 + b"\x00" + b"\x02" + b"\x02\x4c\x01\x00" + b";")


def webp():
    body = b"WEBPVP8L" + struct.pack("<I", 2) + b"\0\0"
    return b"RIFF" + struct.pack("<I", len(body)) + body


def woff(magic=b"wOFF"):
    return magic + b"\x00\x01\x00\x00" + struct.pack(">I", 40) + b"\0" * 28


def ico():
    return b"\0\0\1\0" + struct.pack("<H", 1) + b"\1\1\0\0\1\0\x20\0" + struct.pack("<II", 4, 22) + b"\0\0\0\0"


def zip_ending_like(tail):
    """A tiny zip whose end-of-archive comment is `tail`, so the file as a whole can end with those bytes."""
    return b"PK\x03\x04" + b"\0" * 26 + b"PK\x05\x06" + b"\0" * 16 + struct.pack("<H", len(tail)) + tail


PICTURE_MAKERS = {"a.png": png, "a.jpg": jpeg, "a.jpeg": jpeg, "a.gif": gif, "a.webp": webp, "a.woff": woff,
                  "a.woff2": lambda: woff(b"wOF2"), "a.ico": ico}


class Repo:
    """A scratch git repository with a base commit (README.md and any `files` given); change() commits a change on top of it."""

    def __init__(self, files=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = self._tmp.name
        self.git("init", "-q")
        self.write("README.md", "hello\n")
        for name, text in (files or {}).items():
            self.write(name, text)
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args, email=NOREPLY, msg_env=None):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL=email, GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL=email,
                   GIT_CONFIG_NOSYSTEM="1", HOME=self.path)
        out = subprocess.run(["git", "-C", self.path] + list(args), env=env, capture_output=True, text=True, check=True)
        return out.stdout

    def write(self, name, data, mode="w"):
        p = Path(self.path, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        if "b" in mode:
            with open(p, "wb") as f:
                f.write(data)
        else:
            with open(p, "w", encoding="utf-8") as f:
                f.write(data)

    def commit(self, msg, email=NOREPLY):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg, email=email)

    def scan(self, fork=False):
        out = io.StringIO()
        argv = ["--repo", self.path, "--base", self.base] + (["--fork"] if fork else [])
        with contextlib.redirect_stdout(out):
            rc = ci_scan.main(argv)
        return rc, out.getvalue()

    def close(self):
        self._tmp.cleanup()


class Scan(unittest.TestCase):
    def repo(self):
        r = Repo()
        self.addCleanup(r.close)
        return r

    def refused(self, r, needle, fork=False, absent=()):
        rc, out = r.scan(fork)
        self.assertEqual(rc, 1, out)
        self.assertIn(needle, out)
        for word in absent:
            self.assertNotIn(word, out, "the scan printed a matched word")
        return out

    def test_a_clean_change_passes(self):
        r = self.repo()
        r.write("docs/a.md", "Plain words.\n")
        r.write("src/x.py", "print('hi')\n")
        r.commit("add")
        rc, out = r.scan()
        self.assertEqual((rc, out.count("REFUSED")), (0, 0), out)
        self.assertIn("2 added or changed", out)

    def test_nothing_changed_passes(self):
        self.assertEqual(self.repo().scan()[0], 0)

    def test_a_secret_is_refused_and_not_printed(self):
        r = self.repo()
        r.write("docs/n.txt", 'token = "%s"\n' % SECRET)
        r.commit("add")
        self.refused(r, "a GitHub token", absent=(SECRET, "a1B2c3D4"))

    def test_a_secret_file_name_is_refused(self):
        r = self.repo()
        r.write(".env", "X=1\n")
        r.commit("add")
        self.refused(r, "a file name that holds secrets")

    def test_a_listed_word_is_refused_and_not_printed_even_in_the_path(self):
        r = self.repo()
        r.write("docs/n.md", "Written by %s.\n" % LISTED)
        r.write("docs/%s.md" % LISTED, "ok\n")
        r.commit("add")
        out = self.refused(r, "a person's name", absent=(LISTED, LISTED.lower()))
        self.assertIn("a listed word in its path", out)

    def test_an_oversize_file_is_refused(self):
        r = self.repo()
        r.write("docs/big.txt", "a" * 2000)
        r.commit("add")
        old, pp.MAX_BYTES = pp.MAX_BYTES, 1000
        try:
            self.refused(r, "is over 5 MB")
        finally:
            pp.MAX_BYTES = old

    def test_a_symlink_is_refused(self):
        r = self.repo()
        os.symlink("/etc/hosts", os.path.join(r.path, "docs-link"))
        r.commit("add")
        self.refused(r, "is a link or submodule")

    def test_archives_programs_and_unlisted_binaries_are_refused(self):
        for name, data in (("a.zip", b"PK\x03\x04rest"), ("b.dat", b"ab\x00cd"), ("c", b"\x7fELF\x00"), ("d.png", b"just text")):
            with self.subTest(name):
                r = self.repo()
                r.write(name, data, "wb")
                r.commit("add")
                self.refused(r, "file #1")

    def test_an_allowed_picture_passes(self):
        r = self.repo()
        r.write("img/a.png", png(), "wb")
        r.commit("add")
        self.assertEqual(r.scan()[0], 0)

    def test_every_allowed_picture_and_font_type_passes_when_well_formed(self):
        for name, make in PICTURE_MAKERS.items():
            with self.subTest(name):
                r = self.repo()
                r.write("img/" + name, make(), "wb")
                r.commit("add")
                rc, out = r.scan()
                self.assertEqual(rc, 0, out)

    def test_a_picture_must_match_its_extension_and_end_where_its_format_ends(self):
        trailing = zip_ending_like(b"")
        bad = {"a.png": [png() + trailing, png() + zip_ending_like(png()[-12:]), jpeg(), b"\x89PNG\r\n\x1a\n" + b"\0" * 8],
               "a.jpg": [jpeg() + trailing, jpeg() + zip_ending_like(b"\xff\xd9"), png(), jpeg()[:-2]],
               "a.gif": [gif() + trailing, gif() + zip_ending_like(b";"), png()],
               "a.webp": [webp() + trailing, png()],
               "a.woff": [woff() + trailing, woff(b"wOF2")],
               "a.woff2": [woff(b"wOF2") + trailing, woff()],
               "a.ico": [ico() + trailing, png()]}
        for name, variants in bad.items():
            for n, data in enumerate(variants):
                with self.subTest("%s #%d" % (name, n)):
                    r = self.repo()
                    r.write("img/" + name, data, "wb")
                    r.commit("add")
                    self.refused(r, "not a well-formed one, or has data after its end")

    def test_a_private_only_path_is_refused(self):
        r = self.repo()
        r.write("comms/note.md", "x\n")
        r.commit("add")
        self.refused(r, "is in a folder kept private")

    def test_a_commit_address_that_is_not_a_noreply_one_is_refused_or_noted(self):
        r = self.repo()
        r.write("a.md", "x\n")
        r.commit("add", email="someone@example.org")
        self.refused(r, "not GitHub no-reply addresses", absent=("someone@example.org",))
        os.environ["CI_SCAN_IDENTITY"] = "warn"
        self.addCleanup(os.environ.pop, "CI_SCAN_IDENTITY", None)
        rc, out = r.scan()
        self.assertEqual(rc, 0, out)
        self.assertIn("notice:", out)

    def test_a_listed_word_in_a_commit_message_is_refused(self):
        r = self.repo()
        r.write("a.md", "x\n")
        r.commit("thanks to %s" % LISTED)
        self.refused(r, "listed word in a name, an address or a message", absent=(LISTED,))

    def test_workflow_rules_for_a_changed_workflow(self):
        bad = {"pull_request_target": "on:\n  pull_request_target:\n", "secret": "env:\n  K: ${{ secrets.K }}\n",
               "unpinned": "steps:\n  - uses: actions/checkout@v5\n", "write": "permissions:\n  contents: write\n",
               "injection": "steps:\n  - run: echo ${{ github.event.pull_request.title }}\n"}
        for key, text in bad.items():
            with self.subTest(key):
                r = self.repo()
                r.write(".github/workflows/x.yml", text)
                r.commit("add")
                self.refused(r, "file #1:")

    def test_a_safe_changed_workflow_is_a_notice_for_a_branch_and_a_refusal_for_a_fork(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        r = self.repo()
        r.write(".github/workflows/t.yml", text)
        r.commit("add")
        rc, out = r.scan()
        self.assertEqual(rc, 0, out)
        self.assertIn("notice:", out)
        self.refused(r, "must read it", fork=True)

    def test_changing_the_scan_itself_is_refused_for_a_fork(self):
        r = self.repo()
        r.write("dev/tools/ci_scan.py", "# changed\n")
        r.commit("add")
        self.assertEqual(r.scan()[0], 0)
        self.refused(r, "must read it", fork=True)

    # --- a protected file that is deleted or moved is still "touched" ---------------------------------------------------

    GUARDED = {".github/workflows/x.yml": "name: x\n", "dev/tools/publish_public.py": "# tool\n",
               "tests/test_no_real_names.py": "# test\n"}

    def test_deleting_a_protected_file_is_a_notice_for_a_branch_and_a_refusal_for_a_fork(self):
        for name in self.GUARDED:
            with self.subTest(name):
                r = Repo(self.GUARDED)
                self.addCleanup(r.close)
                r.git("rm", "-q", name)
                r.commit("remove")
                rc, out = r.scan()
                self.assertEqual(rc, 0, out)
                self.assertIn("notice: a deleted file (%s)" % name, out)
                self.refused(r, "must read it", fork=True)

    def test_moving_a_protected_file_away_is_refused_for_a_fork(self):
        for name in self.GUARDED:
            with self.subTest(name):
                r = Repo(self.GUARDED)
                self.addCleanup(r.close)
                r.git("mv", name, "docs-moved.txt")
                r.commit("move")
                self.assertEqual(r.scan()[0], 0)
                self.refused(r, "a deleted file (%s)" % name, fork=True)

    def test_deleting_an_unprotected_file_is_not_a_guard_change(self):
        r = Repo({"docs/a.md": "x\n"})
        self.addCleanup(r.close)
        r.git("rm", "-q", "docs/a.md")
        r.commit("remove")
        rc, out = r.scan(fork=True)
        self.assertEqual(rc, 0, out)
        self.assertIn("1 deleted", out)

    def test_a_deleted_protected_file_whose_name_holds_a_listed_word_is_not_named(self):
        r = Repo({".github/%s.yml" % LISTED: "name: x\n"})
        self.addCleanup(r.close)
        r.git("rm", "-q", ".github/%s.yml" % LISTED)
        r.commit("remove")
        out = self.refused(r, "a deleted file is part of", fork=True, absent=(LISTED, LISTED.lower()))
        self.assertNotIn("a deleted file (", out)

    # --- commit records ---------------------------------------------------------------------------------------------------

    def test_a_control_character_in_a_message_hides_nothing_after_it(self):
        for key, msg, needle in (("word", "hello\x01 thanks to %s" % LISTED, "listed word in a name, an address or a message"),
                                 ("address", "hello\x01 mail me at someone@example.org", "not GitHub no-reply addresses"),
                                 ("two", "a\x01b\x01c\x01 %s" % LISTED, "listed word")):
            with self.subTest(key):
                r = self.repo()
                r.write("a.md", "x\n")
                r.commit(msg)
                self.refused(r, needle, absent=(LISTED, "someone@example.org"))

    def test_a_message_with_a_control_character_but_nothing_wrong_passes_with_the_right_count(self):
        r = self.repo()
        r.write("a.md", "x\n")
        r.commit("hello\x01 there")
        r.write("b.md", "y\n")
        r.commit("second")
        rc, out = r.scan()
        self.assertEqual(rc, 0, out)
        self.assertIn("2 commit(s) checked", out)

    def test_a_record_count_that_differs_from_gits_is_not_a_pass(self):
        r = self.repo()
        r.write("a.md", "x\n")
        r.commit("add")
        real = ci_scan.Scan.git

        def fewer(self, *args):
            return b"" if args[0] == "log" else real(self, *args)

        with mock.patch.object(ci_scan.Scan, "git", fewer):
            rc, out = r.scan()
        self.assertEqual(rc, 2, out)
        self.assertIn("could not run", out)

    def test_git_output_that_is_not_fully_read_is_not_a_pass(self):
        r = self.repo()
        r.write("a.md", "x\n")
        r.commit("add")
        real = ci_scan.Scan.git

        def extra(self, *args):
            return real(self, *args) + (b"stray\0" if args[0] == "diff" else b"")

        with mock.patch.object(ci_scan.Scan, "git", extra):
            rc, out = r.scan()
        self.assertEqual(rc, 2, out)

    # --- merge commits ----------------------------------------------------------------------------------------------------

    def merged(self, email):
        r = self.repo()
        r.git("checkout", "-q", "-b", "side")
        r.write("side.md", "s\n")
        r.commit("side")
        r.git("checkout", "-q", "-")
        r.write("main.md", "m\n")
        r.commit("main")
        r.git("merge", "--no-ff", "-q", "side", "-m", "Merge side", email=email)
        return r

    def test_a_merge_commit_with_a_private_address_is_refused(self):
        self.refused(self.merged("someone@example.org"), "not GitHub no-reply addresses", absent=("someone@example.org",))

    def test_a_merge_commit_made_by_github_passes_and_is_counted(self):
        rc, out = self.merged("noreply@github.com").scan()
        self.assertEqual(rc, 0, out)
        self.assertIn("3 commit(s) checked", out)

    # --- addresses and trailers ---------------------------------------------------------------------------------------------

    def test_a_listed_word_in_an_address_is_refused_and_not_printed(self):
        r = self.repo()
        r.write("a.md", "x\n")
        r.commit("add", email="%s@users.noreply.github.com" % LISTED.lower())
        self.refused(r, "listed word in a name, an address or a message", absent=(LISTED, LISTED.lower()))

    def test_the_assistant_co_author_trailer_is_allowed_but_no_other_address(self):
        r = self.repo()
        r.write("a.md", "x\n")
        r.commit("add\n\nCo-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>")
        rc, out = r.scan()
        self.assertEqual(rc, 0, out)
        r.write("b.md", "y\n")
        r.commit("more\n\nCo-Authored-By: Someone <someone@example.org>")
        self.refused(r, "not GitHub no-reply addresses", absent=("someone@example.org",))

    # --- magic bytes ------------------------------------------------------------------------------------------------------------

    def test_text_that_merely_starts_like_a_program_or_archive_is_not_refused(self):
        for name, text in (("a.md", "MZ ratio notes\n"), ("b.md", "BZh is a codec name\n"), ("c.md", "Rar! was shouted\n"),
                           ("d.md", "MZ\n")):
            with self.subTest(name):
                r = self.repo()
                r.write(name, text)
                r.commit("add")
                rc, out = r.scan()
                self.assertEqual(rc, 0, out)

    def test_real_program_and_archive_signatures_are_still_refused_with_or_without_a_name(self):
        for name, data in (("a", b"MZ\x90\x00\x03\x00\x00\x00"), ("b", b"BZh91AY&SY\x01\x02"), ("c", b"Rar!\x1a\x07\x00rest"),
                           ("d.bz2", b"BZh91AY&SY"), ("e.exe", b"MZ text only"), ("f", b"\x1f\x8b\x08\x08rest")):
            with self.subTest(name):
                r = self.repo()
                r.write(name, data, "wb")
                r.commit("add")
                self.refused(r, "file #1")

    # --- the 5 MB boundary --------------------------------------------------------------------------------------------------------

    def test_a_file_of_exactly_the_limit_passes_and_one_byte_more_is_refused(self):
        old, pp.MAX_BYTES = pp.MAX_BYTES, 1000
        self.addCleanup(setattr, pp, "MAX_BYTES", old)
        r = self.repo()
        r.write("docs/exact.txt", "a" * 1000)
        r.commit("add")
        rc, out = r.scan()
        self.assertEqual(rc, 0, out)
        r.write("docs/over.txt", "a" * 1001)
        r.commit("add")
        self.refused(r, "is over 5 MB")

    # --- #211: pictures that could carry other data, and padding that is normal ----------------------------------------

    def test_a_picture_carrying_a_text_chunk_is_refused(self):
        for kind, payload in ((b"tEXt", b"Comment\0hello"),
                              (b"zTXt", b"Comment\0\0" + zlib.compress(b"PK\x03\x04 hidden")),
                              (b"iTXt", b"Comment\0\0\0\0\0hello")):
            with self.subTest(kind.decode()):
                r = self.repo()
                r.write("img/a.png", png_with_text(kind, payload), "wb")
                r.commit("add")
                self.refused(r, "not a well-formed one, or has data after its end")

    def test_a_little_padding_at_the_end_of_a_font_or_webp_is_allowed_but_more_is_not(self):
        for name, make in (("a.webp", webp), ("a.woff", woff), ("a.woff2", lambda: woff(b"wOF2"))):
            for pad in range(0, 4):
                with self.subTest("%s pad %d" % (name, pad)):
                    r = self.repo()
                    r.write("img/" + name, make() + b"\0" * pad, "wb")
                    r.commit("add")
                    rc, out = r.scan()
                    self.assertEqual(rc, 0, out)
            with self.subTest("%s pad 4" % name):
                r = self.repo()
                r.write("img/" + name, make() + b"\0" * 4, "wb")
                r.commit("add")
                self.refused(r, "not a well-formed one, or has data after its end")

    def test_padding_that_is_not_zero_bytes_is_still_refused(self):
        r = self.repo()
        r.write("img/a.webp", webp() + b"PK\x03", "wb")
        r.commit("add")
        self.refused(r, "not a well-formed one, or has data after its end")

    def test_a_file_over_the_limit_is_refused_without_being_read(self):
        """#211(e): an over-size file must not be pulled into memory just to be refused."""
        old, pp.MAX_BYTES = pp.MAX_BYTES, 1000
        self.addCleanup(setattr, pp, "MAX_BYTES", old)
        r = self.repo()
        r.write("docs/big.txt", "a" * 4000)
        r.commit("add")
        scan = ci_scan.Scan(r.path, r.base, "HEAD", False)
        scan.load()
        big = [(e, d) for e, d in zip(scan.entries, scan.blobs) if e.path == "docs/big.txt"]
        self.assertEqual(len(big), 1)
        self.assertEqual(big[0][1], b"", "the over-size file was read into memory before being refused")
        self.refused(r, "is over 5 MB")

    def test_a_scan_that_cannot_run_is_not_a_pass(self):
        r = self.repo()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = ci_scan.main(["--repo", r.path, "--base", "0" * 40])
        self.assertEqual(rc, 2)
        self.assertIn("could not run", out.getvalue())


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = WORKFLOW.read_text(encoding="utf-8")
        cls.raw = raw
        cls.text = "\n".join(re.sub(r"\s+#\s.*$", "", ln) for ln in raw.splitlines() if not ln.lstrip().startswith("#"))

    def test_safety_rules(self):
        self.assertIn("pull_request:", self.text)
        for word in ("pull_request_target", "workflow_run", "secrets.", "secrets:", "write", "self-hosted", "ubuntu-latest"):
            self.assertNotIn(word, self.text, word)
        self.assertRegex(self.text, r"(?m)^permissions:\n  contents: read\n")
        self.assertEqual(self.text.count("permissions:"), 1)
        self.assertEqual(self.text.count("persist-credentials: false"), self.text.count("actions/checkout@"))
        self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", self.text)
        self.assertRegex(self.text, r"timeout-minutes: \d+")

    def test_every_action_is_pinned_with_its_tag_in_a_comment(self):
        lines = [ln for ln in self.raw.splitlines() if re.match(r"^\s*-?\s*uses:", ln)]
        self.assertGreaterEqual(len(lines), 3)
        for ln in lines:
            self.assertRegex(ln, r"@[0-9a-f]{40} # v\d+", ln)

    def test_it_is_off_until_the_variable_is_set_and_runs_the_base_branchs_scan(self):
        self.assertIn("if: vars.CLARK_PUBLIC_SCAN == 'true'", self.text)
        self.assertIn("path: trusted", self.text)
        self.assertIn("github.event.pull_request.base.sha", self.text)
        self.assertIn('python3 -I "$SCAN" --repo pr', self.text)

    def expression(self, key):
        return re.search(r"^\s*%s: \$\{\{ (.+?) \}\}\s*$" % key, self.text, re.M).group(1)

    def evaluate(self, expr, **values):
        """The workflow's own `a && b || c` expression, run on made-up values (None for a missing one)."""
        names = {"github.event_name": "event", "github.event.pull_request.head.repo.full_name": "head_repo",
                 "github.repository": "repo"}
        for dotted in sorted(names, key=len, reverse=True):
            expr = expr.replace(dotted, names[dotted])
        expr = expr.replace("&&", " and ").replace("||", " or ")
        return eval(expr, {"__builtins__": {}}, dict({"event": None, "head_repo": None, "repo": "o/clark"}, **values))

    def test_only_a_pull_request_from_another_repository_is_a_fork(self):
        expr = self.expression("CI_SCAN_FORK")
        self.assertEqual(self.evaluate(expr, event="push"), "")
        self.assertEqual(self.evaluate(expr, event="pull_request", head_repo="o/clark"), "")
        self.assertEqual(self.evaluate(expr, event="pull_request", head_repo="x/clark"), "1")
        self.assertEqual(self.evaluate(expr, event="pull_request", head_repo=None), "1")      # a deleted fork is still a fork

    def test_only_a_pull_request_run_is_ever_cancelled_by_a_newer_one(self):
        expr = self.expression("cancel-in-progress")
        self.assertIs(self.evaluate(expr, event="push"), False)
        self.assertIs(self.evaluate(expr, event="pull_request"), True)
        self.assertRegex(self.text, r"group: scan-\$\{\{ github\.event\.pull_request\.number \|\| github\.sha \}\}")

    def test_the_python_version_is_pinned(self):
        """#211(c): "3.x" would change the scan's own behaviour on the day a new Python ships."""
        version = re.search(r'python-version: "([^"]+)"', self.text).group(1)
        self.assertNotIn("x", version, "pin the version, do not track the newest")
        self.assertRegex(version, r"^3\.\d+(\.\d+)?$")

    def test_the_header_says_what_the_scan_does_not_stop(self):
        head = self.raw.split("\nname: Scan", 1)[0]
        self.assertNotIn("cannot weaken", head)
        self.assertIn(".github/**", head)
        self.assertIn("maintainer's review", head)
        self.assertRegex(head, r"SKIPPED.*required check")

    def test_a_base_branch_without_the_scan_stops_and_never_runs_the_pull_requests_own_copy(self):
        script = self.raw.split("        run: |\n", 1)[1]
        script = "\n".join(ln[10:] for ln in script.splitlines() if ln.startswith(" " * 10))
        with tempfile.TemporaryDirectory() as tmp:
            trap = Path(tmp, "pr", "dev", "tools", "ci_scan.py")
            trap.parent.mkdir(parents=True)
            trap.write_text("print('RAN THE PULL REQUEST COPY')\n", encoding="utf-8")
            done = subprocess.run(["bash", "-c", script], cwd=tmp, env=dict(os.environ, BASE="1" * 40, CI_SCAN_FORK=""),
                                  capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn("RAN THE PULL REQUEST COPY", done.stdout + done.stderr)
        self.assertIn("no scan program", done.stdout)

    def test_codeowners_names_an_owner_for_every_file_the_scan_protects(self):
        owned = {}
        for ln in (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8").splitlines():
            if ln.strip() and not ln.startswith("#"):
                path, *owners = ln.split()
                owned[path] = owners
        for path in ci_scan.PROTECTED:
            with self.subTest(path):
                self.assertTrue(owned.get("/" + path), "%s has no owner in .github/CODEOWNERS" % path)

    def test_the_workflow_passes_the_scan_s_own_rules(self):
        r = Repo()
        self.addCleanup(r.close)
        r.write(".github/workflows/scan.yml", self.raw)
        r.commit("add")
        rc, out = r.scan(fork=False)
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()

"""The release-asset check (dev/tools/check_release_assets.py) and the checklist line that names it."""
import contextlib
import importlib.util
import io
import json
import re
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_release_assets", ROOT / "dev" / "tools" / "check_release_assets.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def good(tag="v0.5.0", **over):
    """A release that follows every rule: pre-release, (Beta) title, Beta and a digest in the text, zip attached before publishing."""
    v = tag.lstrip("v")
    rel = {"tag_name": tag, "name": f"clark {v} (Beta), Mac", "prerelease": True, "draft": False,
           "body": f"# clark {v} (Beta), Mac\nclark is Beta until version 1.0.\n" + "a1" * 32,
           "published_at": "2026-11-02T10:00:00Z",
           "assets": [{"name": f"clark-{v}-mac.zip", "size": 5, "created_at": "2026-11-02T09:00:00Z"}]}
    rel.update(over)
    return rel


class Check(unittest.TestCase):
    def test_a_release_without_its_zip_fails(self):
        out = mod.problems([{"tag_name": "v0.4.0", "assets": []}])
        self.assertEqual(len(out), 1)
        self.assertIn("clark-0.4.0-mac.zip", out[0])

    def test_a_release_with_its_zip_passes(self):
        self.assertEqual(mod.problems([good("v0.2.1")]), [])
        self.assertEqual(mod.problems([good("v0.5.0")]), [])

    def test_each_failure_says_what_is_wrong_and_how_to_put_it_right(self):
        empty = mod.problems([{"tag_name": "v0.3.0", "assets": [{"name": "clark-0.3.0-mac.zip", "size": 0}]}])[0]
        self.assertIn("is on the release but it is empty", empty)
        misnamed = mod.problems([{"tag_name": "v0.3.0", "assets": [{"name": "clark-0.3.0.zip", "size": 9}]}])[0]
        self.assertIn("no file named clark-0.3.0-mac.zip; it has clark-0.3.0.zip", misnamed)
        missing = mod.problems([{"tag_name": "v0.3.0", "assets": []}])[0]
        self.assertIn("the release has no download", missing)
        for line in (empty, misnamed, missing):
            self.assertIn("python3 dev/tools/package.py mac --release --notes dev/release-notes/0.3.0-plain.md --out", line)
            self.assertIn("dev/RELEASING.md", line)

    def test_drafts_and_other_tags_are_left_alone(self):
        rels = [{"tag_name": "v0.5.0", "draft": True, "assets": []}, {"tag_name": "v0.4.0", "assets": []},
                {"tag_name": "v0.3.0", "assets": []}]
        self.assertEqual(len(mod.problems(rels, {"v0.3.0"})), 1)
        self.assertIn("v0.3.0:", mod.problems(rels, {"v0.3.0"})[0])
        self.assertEqual(len(mod.problems(rels[:2])), 1)

    def test_a_tag_that_matches_no_published_release_fails(self):
        rels = [{"tag_name": "v0.5.0", "draft": True, "assets": []},
                good("v0.4.0")]
        for tag in ("v0.9.9", "v0.5.0"):            # a typo, and a release that is still a draft
            out = mod.problems(rels, {tag})
            self.assertEqual(len(out), 1)
            self.assertIn(f"No published release named {tag} was found", out[0])
        self.assertEqual(mod.problems(rels, {"v0.4.0"}), [])

    def test_a_release_that_is_not_a_pre_release_fails(self):
        out = mod.problems([good("v0.5.0", prerelease=False)])
        self.assertEqual(len(out), 1)
        self.assertIn("not marked Pre-release", out[0])
        self.assertIn("tick Pre-release", out[0])

    def test_a_release_not_titled_beta_fails(self):
        for name in ("clark 0.5.0, Mac", "", None):
            out = mod.problems([good("v0.5.0", name=name)])
            self.assertEqual(len(out), 1, name)
            self.assertIn("the title does not say (Beta)", out[0])

    def test_a_release_text_that_does_not_say_beta_fails(self):
        out = mod.problems([good("v0.5.0", body="Notes. " + "a1" * 32)])
        self.assertEqual(len(out), 1)
        self.assertIn("does not say clark is Beta", out[0])

    def test_a_release_without_its_digest_fails_from_0_5_0_on(self):
        for body in ("Beta, no digest", "Beta " + "a1" * 31, "Beta " + "a1" * 33):   # none, too short, too long
            out = mod.problems([good("v0.5.0", body=body)])
            self.assertEqual(len(out), 1, body)
            self.assertIn("no SHA-256", out[0])
        self.assertEqual(mod.problems([good("v0.4.0", body="Beta, no digest")]), [])    # older releases are not asked for it

    def _with_digest(self, digest, body_digest, tag="v0.5.0"):
        v = tag.lstrip("v")
        return good(tag, body=f"clark is Beta until version 1.0.\n{body_digest}",
                    assets=[{"name": f"clark-{v}-mac.zip", "size": 5, "created_at": "2026-11-02T09:00:00Z", "digest": digest}])

    def test_the_digest_in_the_text_must_be_the_zips_own(self):
        real = "ab12" * 16
        notes = []
        self.assertEqual(mod.problems([self._with_digest("sha256:" + real, real)], None, notes), [])
        self.assertEqual(notes, [])                                                        # a real comparison: nothing to say
        self.assertEqual(mod.problems([self._with_digest("sha256:" + real, "To check: " + real.upper())]), [])   # case does not matter

    def test_a_wrong_digest_in_the_text_fails_with_a_plain_line(self):
        real = "ab12" * 16
        wrong = real[:-1] + "f"                                                            # one character different
        out = mod.problems([self._with_digest("sha256:" + real, wrong)])
        self.assertEqual(len(out), 1)
        self.assertIn("the SHA-256 in the release text is not the zip's", out[0])
        self.assertIn(real, out[0])
        self.assertIn("dev/RELEASING.md step 9", out[0])
        out = mod.problems([self._with_digest("sha256:" + real, "a1" * 32)])               # some other 64-hex string
        self.assertEqual(len(out), 1)
        self.assertIn("not the zip's", out[0])

    def test_no_digest_in_the_text_still_says_so_when_github_gives_a_digest(self):
        out = mod.problems([self._with_digest("sha256:" + "ab12" * 16, "none here")])
        self.assertEqual(len(out), 1)
        self.assertIn("no SHA-256", out[0])

    def test_a_missing_digest_field_falls_back_to_the_loose_check_and_says_so(self):
        notes = []
        self.assertEqual(mod.problems([good("v0.5.0")], None, notes), [])                  # the fixture's asset has no digest field
        self.assertEqual(len(notes), 1)
        self.assertIn("GitHub gives no SHA-256", notes[0])
        self.assertIn("compare it with the release text yourself", notes[0])
        for bad in (None, "", "md5:" + "ab" * 16, "sha256:short"):                         # not a usable sha256 digest either
            notes = []
            rel = self._with_digest(bad, "a1" * 32)
            self.assertEqual(mod.problems([rel], None, notes), [], bad)
            self.assertEqual(len(notes), 1, bad)
        nobody = good("v0.5.0", body="Beta, no digest")                                    # the fallback still needs a digest in the text
        self.assertEqual(len(mod.problems([nobody], None, [])), 1)

    def test_the_command_prints_the_fallback_note(self):
        code, said = self._main([good("v0.5.0")], ["v0.5.0"])
        self.assertEqual(code, 0)
        self.assertIn("Note: v0.5.0: GitHub gives no SHA-256", said)
        self.assertIn("Every published release has its download attached.", said)

    def test_a_zip_attached_after_publishing_fails_from_0_5_0_on(self):
        late = [{"name": "clark-0.5.0-mac.zip", "size": 5, "created_at": "2026-11-02T10:30:00Z"}]
        out = mod.problems([good("v0.5.0", assets=late)])
        self.assertEqual(len(out), 1)
        self.assertIn("attached after the release was published", out[0])
        self.assertIn("steps 8 to 19", out[0])
        late04 = [{"name": "clark-0.4.0-mac.zip", "size": 5, "created_at": "2026-11-02T10:30:00Z"}]
        self.assertEqual(mod.problems([good("v0.4.0", assets=late04)]), [])            # the 0.3.0 and 0.4.0 gap is history

    def test_the_command_reads_every_page_of_releases(self):
        pages = [mock.Mock(returncode=0, stdout=json.dumps([good(f"v0.5.{i}") for i in range(100)])),
                 mock.Mock(returncode=0, stdout=json.dumps([good("v0.4.0")]))]
        with mock.patch.object(mod.subprocess, "run", side_effect=pages) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(mod.main(["v0.4.0"]), 0)
        self.assertEqual(run.call_count, 2)

    def _main(self, releases, argv):
        run = mock.Mock(returncode=0, stdout=json.dumps(releases))
        out = io.StringIO()
        with mock.patch.object(mod.subprocess, "run", return_value=run), contextlib.redirect_stdout(out):
            return mod.main(argv), out.getvalue()

    def test_the_command_exits_non_zero_for_a_tag_that_matches_nothing(self):
        rels = [good("v0.4.0")]
        code, said = self._main(rels, ["v0.9.9"])
        self.assertEqual(code, 1)
        self.assertIn("No published release named v0.9.9 was found", said)
        self.assertNotIn("Every published release has its download attached.", said)
        code, said = self._main(rels, ["v0.4.0"])
        self.assertEqual((code, said.strip()), (0, "Every published release has its download attached."))

    def test_the_checklist_builds_attaches_downloads_launches_and_only_then_publishes(self):
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        marks = ["dev/tools/package.py mac --release", "**Attach the zip.**", "**Download it back.**",
                 "**Compare the digest.**", "Archive Utility", "com.apple.quarantine", "-m clark.doctor", "double-click `clark.command`", "/health", "It is already running",
                 "**Publish the release.**", "dev/tools/check_release_assets.py"]
        spots = [text.index(m) for m in marks]
        self.assertEqual(spots, sorted(spots))
        self.assertNotIn("unzip clark-", text)  # the unzip command drops the download's quarantine mark
        self.assertNotIn("8791", text)  # the doctor and the launch use the same port

    def test_the_checklist_says_beta_and_pre_release(self):
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        self.assertIn("clark X.Y.Z (Beta), Mac", text)
        self.assertIn("Tick Pre-release", text)
        self.assertIn("# clark X.Y.Z (Beta), Mac", text)
        self.assertIn("Every clark release is Beta and a pre-release until version 1.0", text)

    def test_the_checklist_says_what_the_check_looks_at(self):
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        step = [l for l in text.splitlines() if l.startswith("20. ")][0]
        for word in ("Pre-release", "(Beta)", "SHA-256", "before the release was published"):
            self.assertIn(word, step)

    def test_every_step_says_what_you_should_see(self):
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        steps = [l for l in text.splitlines() if l[:1].isdigit() and ". **" in l[:6]]
        self.assertGreaterEqual(len(steps), 20)
        for step in steps:
            self.assertIn("You should see", step, step[:40])
        for word in ("DIR", "Papers", "radar", "ticket PR"):
            self.assertNotIn(word, text)

    def _exit(self, **run_kwargs):
        err = io.StringIO()
        with mock.patch.object(mod.subprocess, "run", **run_kwargs), contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()):
            return mod.main([]), err.getvalue()

    def test_gh_exiting_non_zero_exits_2_with_a_plain_line(self):
        code, said = self._exit(return_value=mock.Mock(returncode=1, stdout="", stderr="HTTP 401"))
        self.assertEqual(code, 2)
        self.assertIn("The releases can't be read (is gh signed in?)", said)
        self.assertIn("gh auth login", said)

    def test_gh_missing_from_the_path_exits_2_with_a_plain_line_not_a_traceback(self):
        code, said = self._exit(side_effect=FileNotFoundError(2, "No such file or directory: 'gh'"))
        self.assertEqual(code, 2)
        self.assertIn("the gh command was not found", said)
        self.assertNotIn("Traceback", said)

    def test_an_answer_that_is_not_json_exits_2(self):
        code, said = self._exit(return_value=mock.Mock(returncode=0, stdout="<html>"))
        self.assertEqual(code, 2)
        self.assertIn("can't be read", said)

    def test_every_github_step_in_the_checklist_names_the_repository(self):
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        steps = [ln for ln in text.splitlines() if re.match(r"\d+\. ", ln) and ("GitHub" in ln or "github.com" in ln or "the draft" in ln)]
        self.assertGreaterEqual(len(steps), 6)
        for ln in steps:
            self.assertIn("insyncalan/clark", ln, ln[:60])


    def _calls(self, argv):
        """The repositories main() asks gh about for this command line, and its exit code and what it printed."""
        run = mock.Mock(returncode=0, stdout=json.dumps([good("v0.5.0")]))
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(mod.subprocess, "run", return_value=run) as call, contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(err):
            code = mod.main(argv)
        return code, [c.args[0][2] for c in call.call_args_list], out.getvalue() + err.getvalue()

    def test_the_repository_is_an_argument_and_defaults_to_insyncalan_clark(self):
        code, asked, _ = self._calls(["v0.5.0"])
        self.assertEqual((code, asked), (0, ["repos/insyncalan/clark/releases?per_page=100&page=1"]))
        code, asked, _ = self._calls(["--repo", "someone/else", "v0.5.0"])
        self.assertEqual((code, asked), (0, ["repos/someone/else/releases?per_page=100&page=1"]))
        code, asked, _ = self._calls(["v0.5.0", "--repo=someone/else"])
        self.assertEqual((code, asked), (0, ["repos/someone/else/releases?per_page=100&page=1"]))

    def test_a_repository_that_is_not_owner_slash_name_exits_2_and_asks_gh_nothing(self):
        for argv in (["--repo"], ["--repo", "clark"], ["--repo", "a/b/c"], ["--repo", "a/b?x=1"], ["--repo", "../x"]):
            code, asked, said = self._calls(argv)
            self.assertEqual((code, asked), (2, []), argv)
            self.assertIn("--repo", said)
            self.assertIn("owner/name", said)

    def test_the_checklist_and_the_tool_say_the_repository_can_be_given(self):
        text = (ROOT / "dev" / "RELEASING.md").read_text(encoding="utf-8")
        step = [l for l in text.splitlines() if l.startswith("20. ")][0]
        self.assertIn("--repo owner/name", step)
        self.assertIn("--repo owner/name", mod.__doc__)


if __name__ == "__main__":
    unittest.main()

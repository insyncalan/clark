"""The release-asset check (dev/tools/check_release_assets.py) and the checklist line that names it."""
import contextlib
import importlib.util
import io
import json
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
                 "**Compare the digest.**", "-m clark.doctor", "./clark.command", "/health", "It is already running",
                 "**Publish the release.**", "dev/tools/check_release_assets.py"]
        spots = [text.index(m) for m in marks]
        self.assertEqual(spots, sorted(spots))

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


if __name__ == "__main__":
    unittest.main()

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


class Check(unittest.TestCase):
    def test_a_release_without_its_zip_fails(self):
        out = mod.problems([{"tag_name": "v0.4.0", "assets": []}])
        self.assertEqual(len(out), 1)
        self.assertIn("clark-0.4.0-mac.zip", out[0])

    def test_a_release_with_its_zip_passes(self):
        rel = {"tag_name": "v0.2.1", "assets": [{"name": "clark-0.2.1-mac.zip", "size": 5}]}
        self.assertEqual(mod.problems([rel]), [])

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
                {"tag_name": "v0.4.0", "assets": [{"name": "clark-0.4.0-mac.zip", "size": 5}]}]
        for tag in ("v0.9.9", "v0.5.0"):            # a typo, and a release that is still a draft
            out = mod.problems(rels, {tag})
            self.assertEqual(len(out), 1)
            self.assertIn(f"No published release named {tag} was found", out[0])
        self.assertEqual(mod.problems(rels, {"v0.4.0"}), [])

    def _main(self, releases, argv):
        run = mock.Mock(returncode=0, stdout=json.dumps(releases))
        out = io.StringIO()
        with mock.patch.object(mod.subprocess, "run", return_value=run), contextlib.redirect_stdout(out):
            return mod.main(argv), out.getvalue()

    def test_the_command_exits_non_zero_for_a_tag_that_matches_nothing(self):
        rels = [{"tag_name": "v0.4.0", "assets": [{"name": "clark-0.4.0-mac.zip", "size": 5}]}]
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

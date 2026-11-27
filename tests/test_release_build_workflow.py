"""The release build workflow (.github/workflows/release-build.yml, Bifrost 2.0 P8 slice 2b): text checks only, no YAML parser.
A pushed tag v* builds the Mac zip on the macOS runner, takes its digest and uploads both as an artifact. It is READ-ONLY (no write permission, no secret): the tag, the
draft, the attach, the asset check and the publish are done by Dum-E's hands from the artifact, so ci_scan stays as it is. A Mac that is off or times out gives no artifact = "not run".

Run: python3 dev/run_tests.py test_release_build_workflow"""
import re
import unittest

from _paths import ROOT

WF = ROOT / ".github" / "workflows" / "release-build.yml"


def text():
    return WF.read_text(encoding="utf-8")


def code():
    return "\n".join(l for l in text().splitlines() if not l.lstrip().startswith("#"))


class ReleaseBuild(unittest.TestCase):
    def test_a_pushed_version_tag_is_the_only_trigger(self):
        c = code()
        self.assertRegex(c, r"(?m)^on:\n  push:\n    tags: \['v\*'\]\n")
        for other in ("pull_request", "schedule", "workflow_dispatch", "branches"):
            self.assertNotIn(other, c)

    def test_it_is_read_only_no_write_no_secret_no_id_token(self):
        c = code()
        self.assertRegex(c, r"(?m)^permissions:\n  contents: read\n")
        self.assertEqual(len(re.findall(r"(?m)^\s*permissions:", c)), 1)
        self.assertNotRegex(c, r"secrets\.|\bwrite\b|write-all|id-token")

    def test_the_zip_is_built_from_the_tag_on_macos_with_release_flags_and_the_digest_is_taken(self):
        c = code()
        self.assertIn("runs-on: macos-latest", c)
        self.assertRegex(c, r"actions/checkout@[0-9a-f]{40}")
        self.assertIn("ref: ${{ github.ref }}", c)                       # the exact tagged commit, never a later one
        self.assertIn("python3 dev/tools/package.py mac --release", c)
        self.assertRegex(c, r"shasum -a 256 .*clark-\$\{VERSION\}-mac\.zip")

    def test_the_zip_and_digest_are_uploaded_as_one_artifact_named_by_the_tag(self):
        c = code()
        self.assertRegex(c, r"actions/upload-artifact@[0-9a-f]{40}")
        self.assertIn("name: release-${{ github.ref_name }}", c)
        self.assertIn("if-no-files-found: error", c)                      # no zip = a red job = "not run", never an empty artifact

    def test_the_job_has_a_timeout_so_a_stuck_mac_runner_is_not_run_not_hung(self):
        self.assertRegex(code(), r"timeout-minutes: \d+")


if __name__ == "__main__":
    unittest.main()

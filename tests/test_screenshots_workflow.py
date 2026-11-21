"""The Screenshots workflow (.github/workflows/screenshots.yml): text checks only, no YAML parser.

Run: python3 dev/run_tests.py test_screenshots_workflow"""
import re
import subprocess
import unittest

from _paths import ROOT

WF = ROOT / ".github" / "workflows" / "screenshots.yml"
TESTS = ROOT / ".github" / "workflows" / "tests.yml"


def text():
    return WF.read_text(encoding="utf-8")


def code_lines():
    return [l for l in text().splitlines() if not l.lstrip().startswith("#")]


def steps():
    """[(step name, [its lines])] of the steps list, split at lines starting a step."""
    out, cur = [], None
    for l in code_lines():
        if re.match(r"^      - ", l):
            cur = [l]
            out.append(cur)
        elif cur is not None:
            cur.append(l)
    named = []
    for block in out:
        m = re.search(r"name:\s*(.+)", "\n".join(block))
        named.append((m.group(1).strip() if m else "", block))
    return named


class Workflow(unittest.TestCase):
    def test_push_to_main_uploads_the_baseline(self):
        t = text()
        self.assertRegex(t, r"(?m)^  push:\n    branches: \[main\]")
        self.assertRegex(t, r"group: screenshots-\$\{\{ github\.event\.pull_request\.number \|\| github\.sha \}\}")

    def test_pull_request_not_target(self):
        t = "\n".join(code_lines())
        self.assertRegex(t, r"(?m)^  pull_request:")
        self.assertNotIn("pull_request_target", text())

    def test_permissions_are_contents_read_only(self):
        lines = code_lines()
        i = lines.index("permissions:")
        block = []
        for l in lines[i + 1:]:
            if not l.startswith("  "):
                break
            block.append(l.strip())
        self.assertEqual(block, ["contents: read"])
        self.assertEqual(sum(1 for l in lines if l.strip().startswith("permissions:")), 1)

    def test_the_secret_is_once_and_only_in_the_upload_step_env(self):
        self.assertEqual(text().count("secrets.ARGOS_TOKEN"), 1)
        self.assertEqual(text().count("secrets."), 1)
        holders = [(n, b) for n, b in steps() if any("secrets.ARGOS_TOKEN" in l for l in b)]
        self.assertEqual(len(holders), 1)
        name, block = holders[0]
        self.assertTrue(name.startswith("Upload to Argos"), name)
        joined = "\n".join(block)
        self.assertRegex(joined, r"(?m)^        env:\n          ARGOS_TOKEN: \$\{\{ secrets\.ARGOS_TOKEN \}\}$")
        shots = [b for n, b in steps() if "screenshots" in n.lower() and not n.startswith("Upload")]
        self.assertTrue(shots)
        for b in shots:
            self.assertNotIn("ARGOS_TOKEN", "\n".join(b))

    def test_the_cli_is_pinned_to_an_exact_version(self):
        found = re.findall(r"@argos-ci/cli@(\S+)", text())
        self.assertTrue(found)
        for v in found:
            self.assertRegex(v, r"^\d+\.\d+\.\d+$")
        self.assertNotRegex(text(), r"@argos-ci/cli(?!@)|@argos-ci/cli@(latest|[\^~])")

    def test_job_only_for_this_repository_and_never_blocking(self):
        t = text()
        self.assertRegex(t, r"(?m)^    if: \$\{\{ github\.event_name == 'push' \|\| github\.event\.pull_request\.head\.repo\.full_name == github\.repository \}\}$")
        self.assertRegex(t, r"(?m)^    continue-on-error: true$")

    def test_every_uses_is_a_full_sha_with_a_tag_comment(self):
        uses = [l for l in code_lines() if re.search(r"\buses:", l)]
        self.assertTrue(uses)
        for l in uses:
            self.assertRegex(l, r"uses:\s*[\w.-]+/[\w.-]+@[0-9a-f]{40}\s+# \S+", l)
        self.assertEqual(len(uses), len(re.findall(r"\buses:", "\n".join(code_lines()))))

    def test_the_one_to_forty_count_check_is_there(self):
        t = text()
        self.assertIn("-lt 1", t)
        self.assertIn("-gt 40", t)


class TestsYml(unittest.TestCase):
    def test_tests_yml_has_no_secrets(self):
        self.assertNotIn("secrets.", TESTS.read_text(encoding="utf-8"))

    def test_the_one_secret_is_the_allowed_one_in_a_step_env_and_the_scan_passes_it(self):
        import ci_scan
        code = "\n".join(code_lines()) + "\n"
        self.assertEqual(re.findall(r"secrets\.(\w+)", code), ["ARGOS_TOKEN"])
        self.assertTrue(ci_scan.secret_in_step_env(code, "ARGOS_TOKEN"))


if __name__ == "__main__":
    unittest.main()

"""Row 1382 (v1.3, delta 1577): the audit workflow (.github/workflows/audit.yml) stays pinned and report only.
Run: python3 dev/run_tests.py test_audit_workflow_1382   (quick tier)

Read as text (standard library only, no YAML library), the way tests/test_workflow.py reads tests.yml: the four tools pinned to exact versions,
the Python minor pinned, no push trigger (hand and schedule only, never pull_request or pull_request_target), report only (the job cannot fail
a run; each of the four commands ends in `|| true` or `--exit-zero`; the output is uploaded for 30 days), and requirements-audit.txt in the repo.
The workflow file is only read here, never edited.
"""
import re
import unittest

from _paths import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "audit.yml"
REQUIREMENTS = ROOT / "requirements-audit.txt"
TOOLS = ("pip-audit", "bandit", "mypy", "ruff")
RUNS = ("pip-audit", "bandit", "ruff", "mypy")


def code(text):
    """The workflow without its comments (a rule written in a comment doesn't count)."""
    return "\n".join(re.sub(r"\s+#\s.*$", "", ln) for ln in text.splitlines() if not ln.lstrip().startswith("#"))


def block(text, key, indent=0):
    """The lines under `key:` at `indent` spaces, up to the next key at that indent (text, without the key's own line)."""
    out, inside = [], False
    for ln in text.splitlines():
        if inside:
            if ln.strip() and len(ln) - len(ln.lstrip()) <= indent:
                break
            out.append(ln)
        elif re.match(rf"^{' ' * indent}{re.escape(key)}:", ln):
            inside = True
            out.append(ln.split(":", 1)[1])
    return "\n".join(out)


def tool_problems(text):
    """What is wrong with the tool pins in a workflow text (code() form); an empty list means all four are exact."""
    bad = []
    install = re.findall(r"python -m pip install ([^\n]*)", text)
    if len(install) != 1:
        return [f"{len(install)} install lines, not 1"]
    words = install[0].split()
    for tool in TOOLS:
        got = [w for w in words if re.match(rf"{re.escape(tool)}(?![\w-])", w)]
        if len(got) != 1 or not re.fullmatch(rf"{re.escape(tool)}==\d+(\.\d+)+", got[0]):
            bad.append(f"{tool} is not pinned with == to an exact version: {got}")
    if len(words) != len(TOOLS):
        bad.append(f"{len(words)} words in the install line, not {len(TOOLS)}")
    return bad


def python_problems(text):
    """What is wrong with the Python pin: one `python-version`, a quoted major.minor."""
    found = re.findall(r"python-version:\s*(\S+)", text)
    if len(found) != 1:
        return [f"{len(found)} python-version lines, not 1"]
    return [] if re.fullmatch(r'"\d+\.\d+"', found[0]) else [f"python-version {found[0]} is not a quoted major.minor"]


def trigger_problems(text):
    """What is wrong with the triggers: exactly workflow_dispatch and a schedule, no push, pull_request or pull_request_target."""
    on = block(text, "on")
    events = re.findall(r"^  ([\w]+):", on, re.M)
    bad = [] if sorted(events) == ["schedule", "workflow_dispatch"] else [f"events are {events}"]
    if "cron:" not in block(on, "schedule", 2):
        bad.append("the schedule has no cron")
    bad += [f"{e} appears in the text" for e in ("push", "pull_request", "pull_request_target") if re.search(rf"^\s*{e}:", on, re.M) or re.search(rf"\b{e}\b", on)]
    return bad


def report_problems(text):
    """What is wrong with the report-only rule: continue-on-error on the job, each run ends harmless, the output is uploaded for 30 days."""
    bad = []
    if not re.search(r"^    continue-on-error: true\s*$", text, re.M):
        bad.append("the job has no continue-on-error: true")
    for tool in RUNS:
        line = next((ln for ln in text.splitlines() if re.match(rf"^\s+{re.escape(tool)}\s", ln)), None)
        if line is None:
            bad.append(f"no {tool} command")
        elif not (line.rstrip().endswith("|| true") or "--exit-zero" in line):
            bad.append(f"{tool} can fail the run: {line.strip()}")
    if not re.search(r"upload-artifact@[0-9a-f]{40}", text) or not re.search(r"path: audit-out/", text) or not re.search(r"retention-days: 30\b", text):
        bad.append("the output is not uploaded from audit-out/ for 30 days")
    return bad


class Audit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = code(WORKFLOW.read_text(encoding="utf-8"))

    def test_the_four_audit_tools_are_pinned_to_exact_versions(self):
        self.assertEqual(tool_problems(self.text), [])
        self.assertIn("python -m pip install bandit==1.9.4 mypy==2.4.1 ruff==0.17.0 pip-audit==2.10.1", self.text)

    def test_the_python_minor_version_is_pinned(self):
        self.assertEqual(python_problems(self.text), [])
        self.assertEqual(re.findall(r"python-version:\s*(\S+)", self.text), ['"3.12"'])

    def test_there_is_no_push_trigger_only_manual_and_schedule(self):
        self.assertEqual(trigger_problems(self.text), [])
        on = block(self.text, "on")
        self.assertIn('cron: "0 23 * * 6"', on)
        self.assertEqual(len(re.findall(r"^  \w+:", on, re.M)), 2)
        self.assertNotIn("pull_request_target", self.text)

    def test_the_audit_is_report_only_and_uploads_its_output(self):
        self.assertEqual(report_problems(self.text), [])
        self.assertIn("continue-on-error: true", self.text)
        self.assertIn("retention-days: 30", self.text)

    def test_requirements_audit_txt_exists_and_pins_the_two_packages(self):
        self.assertTrue(REQUIREMENTS.is_file(), "the file pip-audit reads is in the repo")
        self.assertIn("-r requirements-audit.txt", self.text)
        self.assertEqual(REQUIREMENTS.read_text(encoding="utf-8").split(), ["openpyxl==3.1.5", "et_xmlfile==2.0.0"])

    def test_undoing_a_pin_or_the_report_only_rule_is_caught(self):
        for check, old, new in (
                (tool_problems, "ruff==0.17.0", "ruff"),                                   # a bare tool
                (tool_problems, "mypy==2.4.1", "mypy>=2.4"),                               # a floor, not a pin
                (python_problems, 'python-version: "3.12"', 'python-version: "3.x"'),      # a floating minor
                (trigger_problems, "  workflow_dispatch:", "  push:\n  workflow_dispatch:"),
                (trigger_problems, "  workflow_dispatch:", "  pull_request_target:\n  workflow_dispatch:"),
                (report_problems, "bandit -r src/clark -q -f txt -o audit-out/bandit.txt || true", "bandit -r src/clark -q -f txt -o audit-out/bandit.txt"),
                (report_problems, "    continue-on-error: true", "    continue-on-error: false"),
                (report_problems, "retention-days: 30", "retention-days: 1")):
            with self.subTest(old=old, new=new):
                self.assertEqual(check(self.text), [], "the real file passes")
                self.assertIn(old, self.text)
                self.assertTrue(check(self.text.replace(old, new, 1)), f"{old!r} -> {new!r} must be caught")


if __name__ == "__main__":
    unittest.main()

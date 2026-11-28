"""P12-14: no Tests run on a push to main, pinned in every trigger form

Run: python3 dev/run_tests.py test_workflow_push_main_p12_14   (quick tier)

tests/test_workflow.py test_triggers pins this with assertNotRegex(on, r"^  push:") and no re.M flag, so `^` matches only
the start of the whole block and a `  push:` line inside `on:` passes. This file reads the top-level `on:` of every workflow
(block form, flow list, flow map, plain string; comments stripped; standard library only, no YAML library) and fails on a
`push` trigger of any kind in tests.yml or in any workflow that runs the suite. scan.yml and screenshots.yml push to main on
purpose and do not run the suite; test 2 states that.
"""
import re
import unittest

from _paths import ROOT

WORKFLOWS = ROOT / ".github" / "workflows"
TESTS_YML = WORKFLOWS / "tests.yml"


def strip_comments(text):
    """The text without whole-line comments and without ` # ...` endings (no workflow here has a # inside a quoted value)."""
    out = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("#"):
            continue
        out.append(re.sub(r"\s+#.*$", "", ln).rstrip())
    return out


def on_block(text):
    """(inline, body): what follows `on:` on its own line and the indented lines under it, comments stripped."""
    lines = strip_comments(text)
    for i, ln in enumerate(lines):
        m = re.match(r"""^["']?on["']?\s*:\s*(.*)$""", ln)
        if m:
            body = []
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt[0].isspace():
                    break
                body.append(nxt)
            return m.group(1).strip(), [b for b in body if b.strip()]
    return None, []


def flow_items(s):
    """The names at the top level of a flow list `[a, b: {..}]` or flow map `{a: .., b: ..}` (depth 1 entries)."""
    names, depth, cur = [], 0, ""
    for ch in s:
        if ch in "[{":
            depth += 1
            if depth > 1:
                cur += ch
        elif ch in "]}":
            depth -= 1
            if depth >= 1:
                cur += ch
        elif ch == "," and depth == 1:
            names.append(cur)
            cur = ""
        else:
            cur += ch
    names.append(cur)
    return {re.split(r":", n.strip(), 1)[0].strip().strip("'\"") for n in names if n.strip()}


def triggers(text):
    """The set of event names under the top-level `on:` (None-safe: an absent `on:` gives the empty set)."""
    inline, body = on_block(text)
    if inline is None:
        return set()
    if inline[:1] in ("[", "{"):
        return flow_items(inline)
    if inline:
        return {inline.strip("'\"")}
    if not body:
        return set()
    base = min(len(b) - len(b.lstrip()) for b in body)
    found = set()
    for b in body:
        if len(b) - len(b.lstrip()) != base:
            continue
        m = re.match(r"""^\s*(?:-\s*)?["']?([A-Za-z_][\w-]*)["']?\s*(?::|$)""", b)
        if m:
            found.add(m.group(1))
    return found


def name_of(text):
    for ln in strip_comments(text):
        m = re.match(r"""^name\s*:\s*["']?([^"']*?)["']?\s*$""", ln)
        if m:
            return m.group(1)
    return None


def read(path):
    return path.read_text(encoding="utf-8")


class PushToMainTest(unittest.TestCase):
    def test_tests_yml_has_no_push_trigger_in_any_form(self):
        found = triggers(read(TESTS_YML))
        self.assertNotIn("push", found)
        self.assertEqual(found, {"workflow_dispatch", "pull_request", "schedule", "merge_group"})

    def test_no_workflow_that_runs_the_suite_has_a_push_trigger(self):
        files = sorted(WORKFLOWS.glob("*.yml"))
        suite = [f.name for f in files if "run_tests.py" in read(f) or name_of(read(f)) == "Tests"]
        self.assertIn("tests.yml", suite)
        for name in suite:
            self.assertNotIn("push", triggers(read(WORKFLOWS / name)), name)
        # scan.yml and screenshots.yml push to main on purpose; that is allowed only because they do not run the suite
        for name in ("scan.yml", "screenshots.yml"):
            self.assertNotIn(name, suite)
            self.assertNotIn("run_tests.py", read(WORKFLOWS / name))
            self.assertNotEqual(name_of(read(WORKFLOWS / name)), "Tests")

    def test_the_parser_sees_a_push_trigger_where_there_is_one(self):
        self.assertIn("push", triggers(read(WORKFLOWS / "scan.yml")))
        self.assertIn("push", triggers(read(WORKFLOWS / "screenshots.yml")))
        cases = {
            "block": "name: X\non:\n  pull_request:\n  push:\n    branches: [main]\njobs:\n  a: {}\n",
            "flow list": "on: [push, pull_request]\njobs:\n  a: {}\n",
            "flow map": "on: {push: {branches: [main]}, pull_request: {}}\njobs:\n  a: {}\n",
            "string": "on: push\njobs:\n  a: {}\n",
            "quoted key": "\"on\":\n  push:\n    tags: ['v*']\n",
            "list items": "on:\n  - push\n  - pull_request\n",
        }
        for label, text in cases.items():
            self.assertIn("push", triggers(text), label)
        self.assertEqual(triggers(cases["flow list"]), {"push", "pull_request"})
        self.assertEqual(triggers(cases["flow map"]), {"push", "pull_request"})
        self.assertEqual(triggers(cases["block"]), {"push", "pull_request"})
        # a push written only in a comment or deeper in the file is not a trigger
        self.assertEqual(triggers("on:\n  pull_request:\n    # push:\n  schedule:\n    - cron: \"0 1 * * *\"  # push:\njobs:\n  push:\n    runs-on: x\n"),
                         {"pull_request", "schedule"})

    def test_no_filter_widens_the_tests_triggers(self):
        inline, body = on_block(read(TESTS_YML))
        self.assertEqual(inline, "")
        filters = [b.strip() for b in body if re.match(r"^\s*(?:-\s*)?(branches|branches-ignore|paths|paths-ignore|tags|tags-ignore)\s*:", b)]
        self.assertEqual(filters, [])
        text = "\n".join(body)
        self.assertEqual(re.findall(r"^  pull_request:\n    types: (\[[^\]]*\])$", text, re.M),
                         ["[opened, synchronize, reopened, labeled, unlabeled]"])
        self.assertEqual(re.findall(r"^  merge_group:\n    types: (\[[^\]]*\])$", text, re.M), ["[checks_requested]"])

    def test_pull_request_and_merge_group_still_there(self):
        found = triggers(read(TESTS_YML))
        self.assertEqual(sorted(found & {"pull_request", "merge_group", "schedule", "workflow_dispatch"}),
                         ["merge_group", "pull_request", "schedule", "workflow_dispatch"])
        self.assertEqual(len(found), 4)


if __name__ == "__main__":
    unittest.main()

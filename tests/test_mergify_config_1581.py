"""Row 1581 (AP1 to AP3): the Mergify merge-queue config at the repo root.

Run: python3 dev/run_tests.py test_mergify_config_1581
The file is read as text: PyYAML is not installed on the CI runners, and the file is a flat list of queue rules.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ["Tests passed", "bifrost-closes-guard", "bifrost-point-map", "bifrost-test-exists", "bifrost-read-approved"]


def read():
    return (ROOT / ".mergify.yml").read_text(encoding="utf-8")


def code_lines():
    return [ln.rstrip() for ln in read().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]


def list_under(key):
    """The '- item' lines directly under `key:` inside the queue rule."""
    lines, out, on = code_lines(), [], False
    for ln in lines:
        if re.match(r"^    \S", ln):
            on = ln.strip() == key + ":"
            continue
        m = re.match(r"^      - (.*)$", ln)
        if on and m:
            out.append(m.group(1))
    return out


class MergifyConfig(unittest.TestCase):
    def test_mergify_yml_parses_and_has_queue_rule_default(self):
        lines = code_lines()
        self.assertEqual(lines[0], "queue_rules:")
        names = [re.sub(r"^\s*- name:\s*", "", ln) for ln in lines if re.match(r"^  - name:", ln)]
        self.assertEqual(names, ["default"], "queue_rules holds exactly one rule, named default")
        self.assertTrue(all(ln.startswith(" ") for ln in lines[1:]), "every line after the key is inside queue_rules")
        self.assertNotIn("\t", read(), "YAML takes no tab characters")

    def test_queue_conditions_are_the_label_and_the_four_required_check_names(self):
        self.assertEqual(list_under("queue_conditions"),
                         ["label = queue", "base = main", "-draft"] + ["check-success = " + c for c in CHECKS])
        self.assertEqual(list_under("merge_conditions"), ["check-success = " + c for c in CHECKS])

    def test_queue_squashes_in_batches_of_3_and_waits_1_minute(self):
        lines = code_lines()
        for want in ("    merge_method: squash", "    batch_size: 3", "    batch_max_wait_time: 1 minute"):
            self.assertEqual(lines.count(want), 1, want)


if __name__ == "__main__":
    unittest.main()

"""A label change does not cancel a Tests run in flight (clark#2507, 27-11: the Mergify queue's own labels queued/dequeued restarted the PR's run, the
cancelled run left "Tests passed" cancelled and Mergify dequeued with "checks interrupted"). Reads .github/workflows/tests.yml as text, evaluates the
cancel-in-progress expression by hand (no YAML library, no eval).
Run: python3 dev/run_tests.py test_tests_yml_label_does_not_cancel"""
import re
import unittest
from pathlib import Path

TEXT = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")


def cancel_in_progress(event, action=None):
    expr = re.search(r"^  cancel-in-progress: \$\{\{ (.*) \}\}\s*$", TEXT, re.M).group(1)
    values = {"github.event_name": event, "github.event.action": action}
    for atom in expr.split(" && "):
        left, op, right = re.fullmatch(r"(\S+) (==|!=) '([^']*)'", atom.strip()).groups()
        if (values[left] == right) != (op == "=="):
            return False
    return True


class LabelDoesNotCancel(unittest.TestCase):
    def test_a_label_or_unlabel_event_never_cancels_a_run_in_flight(self):
        self.assertIs(cancel_in_progress("pull_request", "labeled"), False)
        self.assertIs(cancel_in_progress("pull_request", "unlabeled"), False)

    def test_a_new_commit_still_cancels_the_older_pull_request_run(self):
        for action in ("opened", "synchronize", "reopened"):
            self.assertIs(cancel_in_progress("pull_request", action), True)

    def test_a_queue_nightly_or_hand_run_is_still_never_cancelled(self):
        for event in ("merge_group", "schedule", "workflow_dispatch", "push"):
            self.assertIs(cancel_in_progress(event), False)


if __name__ == "__main__":
    unittest.main()

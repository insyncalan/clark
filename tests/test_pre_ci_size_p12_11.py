"""P12-11: pre-CI logs the size of the change in its record and the size never blocks (dev/tools/pre_ci.py).

The size is `git diff --shortstat` as {files, additions, deletions}. It is recorded, it is not one of the seven checks, and a
very large change gets the same checks and the same result as a small one.

Run: python3 dev/run_tests.py test_pre_ci_size_p12_11   (quick tier)
"""
import json
import unittest

from _paths import ROOT  # noqa: F401  (puts dev/tools on the path)
from test_pre_ci import FEATURE, FEATURE_TEST, HAVE_39, NAMES, TICKET, Fixture, results

BIG_LINES = 5000
SMALL_DOCS = 77          # one-line files beside the big one; with mod.py, test_mod.py and big.py: 80 files


def numstat_sum(pr, head):
    adds = dels = files = 0
    for ln in pr.git("diff", "--numstat", pr.base, head).splitlines():
        a, d, _ = ln.split("\t", 2)
        adds, dels, files = adds + int(a), dels + int(d), files + 1
    return {"files": files, "additions": adds, "deletions": dels}


def small_change(pr):
    """Three files: a line of mod.py is replaced (a deletion), a test is added, and a note is added."""
    pr.write("src/clark/mod.py", FEATURE.replace("return n * 2", "return n + n"))
    pr.write("tests/test_mod.py", FEATURE_TEST)
    pr.write("docs/size/note.txt", "one\ntwo\n")
    return pr.commit("small change with a deletion")


def large_change(pr):
    """80 files and 5084 added lines, all named by the ticket so that only the size differs from the small change."""
    pr.write("src/clark/mod.py", FEATURE)
    pr.write("tests/test_mod.py", FEATURE_TEST)
    pr.write("src/clark/big.py", "".join("X%d = %d\n" % (i, i) for i in range(BIG_LINES)))
    for i in range(SMALL_DOCS):
        pr.write("docs/size/f%d.txt" % i, "line %d\n" % i)
    return pr.commit("large change")


def name_everything(pr):
    ticket = dict(TICKET, files=TICKET["files"] + ["src/clark/big.py", "docs/size/"])
    pr.ticket.write_text(json.dumps(ticket), encoding="utf-8")


def expected_code():
    return 0 if HAVE_39 else 1


def not_passing(doc):
    return {k: v for k, v in results(doc).items() if v != "pass"}


class PreCiSizeTest(unittest.TestCase):
    def run_small(self):
        with Fixture() as pr:
            name_everything(pr)
            head = small_change(pr)
            code, out = pr.pre_ci()
            self.log = [json.loads(ln) for ln in (pr.records / "log.jsonl").read_text(encoding="utf-8").splitlines()]
            return code, out, pr.record(head), numstat_sum(pr, head)

    def run_large(self):
        with Fixture() as pr:
            name_everything(pr)
            head = large_change(pr)
            code, out = pr.pre_ci()
            self.log = [json.loads(ln) for ln in (pr.records / "log.jsonl").read_text(encoding="utf-8").splitlines()]
            return code, out, pr.record(head), numstat_sum(pr, head)

    def test_size_equals_git_numstat_for_a_change_with_a_deletion(self):
        code, out, doc, counted = self.run_small()
        self.assertEqual(code, expected_code(), out)
        self.assertEqual(doc["size"], counted)
        self.assertEqual(doc["size"], {"files": 3, "additions": 10, "deletions": 1})
        self.assertGreaterEqual(doc["size"]["deletions"], 1)
        self.assertNotEqual(doc["size"]["additions"], doc["size"]["deletions"])
        self.assertIn("3 files, +10 -1", out)

    def test_a_large_change_records_the_big_size_and_adds_no_failing_check(self):
        s_code, _, small, _ = self.run_small()
        code, out, doc, counted = self.run_large()
        self.assertEqual(doc["size"], counted)
        self.assertEqual(doc["size"], {"files": 80, "additions": 5000 + 7 + SMALL_DOCS, "deletions": 0})
        self.assertNotIn("size", results(doc))
        self.assertEqual(code, s_code)
        self.assertEqual(code, expected_code(), out)
        self.assertEqual(doc["result"], small["result"])
        self.assertEqual(doc["result"], "pass" if HAVE_39 else "fail")
        self.assertEqual(not_passing(doc), not_passing(small))
        self.assertEqual(not_passing(doc), {} if HAVE_39 else {"Python 3.9 compile": "not checked"})
        self.assertIn("80 files, +5084 -0", out)

    def test_the_log_line_carries_the_size(self):
        keys = {"head", "base", "ticket", "result", "finished", "seconds", "checks", "size"}
        code, _, doc, _ = self.run_small()
        self.assertEqual(len(self.log), 1)
        self.assertEqual(set(self.log[0]), keys)
        self.assertEqual(self.log[0]["size"], doc["size"])
        self.assertEqual(self.log[0]["size"], {"files": 3, "additions": 10, "deletions": 1})
        self.assertEqual(self.log[0]["head"], doc["head"])
        self.assertEqual(self.log[0]["result"], doc["result"])
        code, _, doc, _ = self.run_large()
        self.assertEqual(len(self.log), 1)
        self.assertEqual(set(self.log[0]), keys)
        self.assertEqual(self.log[0]["size"], doc["size"])
        self.assertEqual(self.log[0]["size"], {"files": 80, "additions": 5084, "deletions": 0})
        self.assertNotIn("size", self.log[0]["checks"])

    def test_size_is_never_a_check_name(self):
        for _, _, doc, _ in (self.run_small(), self.run_large()):
            self.assertEqual([c["name"] for c in doc["checks"]], NAMES)
            self.assertEqual(len(doc["checks"]), 7)
            for c in doc["checks"]:
                self.assertNotIn("size", c["command"].lower(), c["name"])
                self.assertNotIn("size", c["name"].lower())


if __name__ == "__main__":
    unittest.main()

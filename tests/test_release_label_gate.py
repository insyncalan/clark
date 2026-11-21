"""Tests for .github/bifrost/release_label_gate.py . Run: python3 dev/run_tests.py test_release_label_gate"""
import json, os, sys, tempfile, unittest, io, contextlib
from types import SimpleNamespace as NS
from _paths import ROOT
sys.path.insert(0, str(ROOT / ".github" / "bifrost"))
try:
    import release_label_gate as g
finally:
    sys.path.remove(str(ROOT / ".github" / "bifrost"))

def run(issues, full, commits, argv_extra=()):
    """issues: list of dicts; commits: set of issue numbers that a reachable commit names."""
    def fake(cmd):
        if cmd[0] == "gh" and "timeline" in cmd[2]:
            return NS(returncode=0, stdout="[]", stderr="")
        if cmd[0] == "gh":
            return NS(returncode=0, stdout=json.dumps(issues), stderr="")
        # git log ... --grep PATTERN -1
        import re
        pat = cmd[cmd.index("--grep") + 1]
        hit = any(re.search(pat, "Row %d: x" % n, re.I) for n in commits)
        return NS(returncode=0, stdout="abc subject\n" if hit else "", stderr="")
    f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False); f.write("\n".join(map(str, full))); f.close()
    old, olda = g.sh, sys.argv
    g.sh = fake; sys.argv = ["x", "--tag", "v1.3.5", "--repo", "r/r", "--code-repo", ".", "--full-file", f.name]
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out): code = g.main()
    finally:
        g.sh, sys.argv = old, olda; os.unlink(f.name)
    return code, out.getvalue()

def iss(n, state="closed"): return {"number": n, "state": state}

class T(unittest.TestCase):
    def test_all_good(self):
        code, out = run([iss(1296), iss(1305)], [1296, 1305], {1296, 1305})
        self.assertEqual(code, 0); self.assertIn("OK", out)
    def test_open_issue_with_the_label_fails(self):
        code, out = run([iss(1463, "open")], [1463], {1463})
        self.assertEqual(code, 1); self.assertIn("FAIL #1463: open issue carries v1.3.5", out)
    def test_partial_row_not_in_full_list_fails(self):
        code, out = run([iss(1346)], [1296], {1346})
        self.assertEqual(code, 1); self.assertIn("not FULL", out)
    def test_no_commit_in_the_tag_fails(self):
        code, out = run([iss(1296)], [1296], set())
        self.assertEqual(code, 1); self.assertIn("no commit naming this row", out)
    def test_a_longer_number_does_not_match(self):
        code, out = run([iss(129)], [129], {1296})
        self.assertEqual(code, 1)
    def test_full_row_without_label_warns_not_fails(self):
        code, out = run([iss(1296)], [1296, 1399], {1296})
        self.assertEqual(code, 0); self.assertIn("WARN #1399", out)
    def test_plan_repo_reference_in_commit_subject_matches(self):
        import re
        pat = None
        def fake(cmd):
            nonlocal pat
            if cmd[0] == "gh": return NS(returncode=0, stdout="[]" if "timeline" in cmd[2] else json.dumps([iss(7)]), stderr="")
            pat = cmd[cmd.index("--grep") + 1]
            return NS(returncode=0, stdout="x\n" if re.search(pat, "plan-x#7 done", re.I) else "", stderr="")
        f = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False); f.write("7"); f.close()
        old, olda = g.sh, sys.argv
        g.sh = fake; sys.argv = ["x", "--tag", "v1", "--repo", "o/plan-x", "--code-repo", ".", "--full-file", f.name]
        try:
            with contextlib.redirect_stdout(io.StringIO()): code = g.main()
        finally:
            g.sh, sys.argv = old, olda; os.unlink(f.name)
        self.assertEqual(code, 0)
if __name__ == "__main__": unittest.main()

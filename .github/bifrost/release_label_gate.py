#!/usr/bin/env python3
"""Release label only on released, fully verified items (owner's rule).
Run by the report-only job bifrost-release-label in .github/workflows/bifrost-checks.yml. Read-only: uses `gh api` (GET) and `git`, changes nothing.

Usage: release_label_gate.py --tag v1.3.5 --repo <owner>/<plan-repo> --code-repo /path/to/clark \
                             --full-file verify-1-3-5/FULL.txt
Fails (exit 1) when an issue labelled with the tag
  (a) is not closed, or
  (b) has no commit reachable from the tag that names the row (linked-PR merge commit or 'Row N:' subject), or
  (c) is not listed in --full-file (rows the code check marked FULL, one number per line).
Also reports FULL rows in the tag that lack the label (warning only).
"""
import argparse, json, re, subprocess, sys

def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def main():
    a = argparse.ArgumentParser()
    a.add_argument("--tag", required=True); a.add_argument("--repo", required=True)
    a.add_argument("--code-repo", required=True); a.add_argument("--full-file", required=True)
    o = a.parse_args()
    full = {int(x) for x in open(o.full_file).read().split() if x.strip().isdigit()}
    r = sh(["gh", "api", "repos/%s/issues?labels=%s&state=all&per_page=100" % (o.repo, o.tag), "--paginate"])
    if r.returncode:
        print("NOT CHECKED: gh failed:", r.stderr.strip()); return 2
    bad = []; seen = set()
    for i in json.loads(r.stdout):
        if "pull_request" in i: continue
        n = i["number"]; seen.add(n)
        if i["state"] != "closed": bad.append((n, "open issue carries " + o.tag))
        if n not in full: bad.append((n, "not FULL in the code check (partial rows are held)"))
        t = sh(["gh", "api", "repos/%s/issues/%d/timeline" % (o.repo, n), "--paginate"])
        shas = set()
        if t.returncode == 0:
            for e in json.loads(t.stdout):
                s = (e.get("source") or {}).get("issue") or {}
                if "pull_request" in s: shas.add(s["number"])
        # merge-commit ancestry is checked from PR numbers in the code repo log
        found = False
        for pr in shas:
            g = sh(["git", "-C", o.code_repo, "log", o.tag, "--oneline", "--grep", "#%d" % pr, "-1"])
            if g.stdout.strip(): found = True; break
        if not found:
            # code PRs live in another repo, so the issue timeline has no link; the commit subject says "Row N:" / "Rows 1, N"
            pat = r"(^|[^0-9])(row|rows)[^:]{0,40}[^0-9]%d([^0-9]|$)|%s#%d([^0-9]|$)" % (n, re.sub(r"([.^$*+?(){}\[\]|\\])", r"\\\1", o.repo.split("/")[-1]), n)
            g = sh(["git", "-C", o.code_repo, "log", o.tag, "--oneline", "-E", "-i", "--grep", pat, "-1"])
            found = bool(g.stdout.strip())
        if not found: bad.append((n, "no commit naming this row is reachable from " + o.tag))
    for n in sorted(full - seen): print("WARN #%d: FULL row without the %s label (GitHub label lists can lag)" % (n, o.tag))
    for n, why in sorted(bad): print("FAIL #%d: %s" % (n, why))
    print("OK" if not bad else "%d problem(s)" % len(bad))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())

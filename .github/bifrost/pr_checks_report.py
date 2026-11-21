#!/usr/bin/env python3
"""pr_checks_report.py: report-only PR checks (playbook 4.1, 4.3, 5.2). Plain stdlib.

Checks per open PR of insyncalan/clark: point-map, closes-guard, test-exists.
Result per check: PASS, FAIL or LEGACY (PR written before the Point map format
existed: no `## Point map` heading and no `points_version:` line in the body).
Reads GitHub with `gh api` GET only. Never comments, labels, closes or pushes.

Usage: pr_checks_report.py [--repo insyncalan/clark] [--plan-repo OWNER/PLAN]
                           [--pr N ...] [--json] [--out DIR] [--no-write]
Exit 0 always unless a run error (report-only).
"""
import argparse, base64, json, os, re, subprocess, sys, time
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import ticket_lint as _tl
except Exception:  # in progress or absent: fall back to plain regex
    _tl = None

CHECKS = ["point-map", "closes-guard", "test-exists"]
STATUSES = ("Covered", "Partial", "Not here")
HEADER_RE = re.compile(r"^\|\s*AP\s*\|\s*Status\s*\|\s*Where[^|]*\|\s*Test[^|]*\|\s*$", re.I)
REF_RE = re.compile(r"(?im)^\s*(Part of|Closes|Fixes|Resolves)\s+(?:([\w.-]+/[\w.-]+))?#(\d+)\s*$")
CLOSE_KW = re.compile(r"(?i)\b(close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+(?:[\w.-]+/[\w.-]+)?#(\d+)")
FILELINE = re.compile(r"[\w./\-]+\.\w+:\d+")


# ---------- GitHub (GET only) ----------
def gh_json(path, raw=False):
    cmd = ["gh", "api", path]
    if raw:
        cmd = ["gh", "api", "-H", "Accept: application/vnd.github.raw", path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("gh api GET failed: " + path + ": " + r.stderr.strip()[:150])
    return r.stdout if raw else json.loads(r.stdout)


class GH:
    """Fetcher; tests replace it with a fake exposing the same four methods."""
    def __init__(self, repo, plan_repo):
        self.repo, self.plan = repo, plan_repo
        self._blobs = {}

    def open_prs(self):
        out, page = [], 1
        while True:
            d = gh_json(f"repos/{self.repo}/pulls?state=open&per_page=100&page={page}")
            out += d
            if len(d) < 100:
                return out
            page += 1

    def ticket_body(self, repo, num):
        return gh_json(f"repos/{repo}/issues/{num}").get("body") or ""

    def test_files(self, sha):
        """dict path -> text for test files at sha (cached by blob sha)."""
        t = gh_json(f"repos/{self.repo}/git/trees/{sha}?recursive=1")
        out = {}
        for e in t.get("tree", []):
            p = e["path"]
            if e["type"] == "blob" and re.match(r"(^|.*/)(tests?|__tests__)/", p) and \
               re.search(r"\.(py|js|ts|mjs)$", p):
                if e["sha"] not in self._blobs:
                    self._blobs[e["sha"]] = gh_json(f"repos/{self.repo}/git/blobs/{e['sha']}", raw=True)
                out[p] = self._blobs[e["sha"]]
        return out


# ---------- parsing ----------
def parse_body(body):
    body = (body or "").replace("\r\n", "\n")
    res = {"ref": None, "kw": None, "pv": None, "has_map": False, "rows": [], "errors": [],
           "has_oos": bool(re.search(r"(?im)^## Out of scope", body))}
    m = REF_RE.search(body)
    if m:
        res["kw"], res["ref"] = m.group(1), (m.group(2), int(m.group(3)))
    m = re.search(r"(?im)^\s*points_version:\s*(\S+)\s*$", body)
    if m:
        res["pv"] = m.group(1)
    mm = re.search(r"(?im)^## Point map\s*$", body)
    res["has_map"] = bool(mm)
    res["has_pv_line"] = m is not None
    if mm:
        lines = body[mm.end():].split("\n")
        i = 0
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines) or not HEADER_RE.match(lines[i].strip()):
            res["errors"].append("table header is not '| AP | Status | Where (file:line at this head) | Test (name) |'")
            return res
        i += 1
        if i >= len(lines) or not re.match(r"^\|[\s\-|:]+\|$", lines[i].strip()):
            res["errors"].append("table separator row missing")
            return res
        i += 1
        while i < len(lines) and lines[i].strip().startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if len(cells) != 4:
                res["errors"].append(f"row has {len(cells)} cells, need 4: {lines[i].strip()[:50]}")
            else:
                res["rows"].append(cells)
            i += 1
    return res


def ticket_points(body):
    """Return (set of AP numbers, points_hash8 or None)."""
    if _tl is not None:
        try:
            pts = _tl.parse_points(body)
            secs, _ = _tl.split_sections(body)
            h = _tl.points_hash(secs)[:8] if secs.get("points") else None
            nums = {p[0] for p in pts}
            if nums:
                return nums, h
        except Exception:
            pass
    nums = {int(x) for x in re.findall(r"(?m)^\s*\|?\s*[*`_]*AP\s*(\d+)[*`_]*\s*[|:.)]", body)}
    return nums, None


def is_legacy(p):
    return not p["has_map"] and not p["has_pv_line"]


# ---------- checks ----------
def check_point_map(body, get_ticket):
    p = parse_body(body)
    if is_legacy(p):
        return "LEGACY", "no Point map section and no points_version line (written before the format)"
    if not p["has_map"]:
        return "FAIL", "points_version present but no '## Point map' section"
    if p["errors"]:
        return "FAIL", p["errors"][0]
    if p["kw"] is None:
        return "FAIL", "no 'Part of <repo>#N' line naming the ticket"
    if not p["pv"] or not re.fullmatch(r"[0-9a-f]{8}", p["pv"]):
        return "FAIL", "points_version missing or not 8 hex characters"
    if not p["rows"]:
        return "FAIL", "Point map has no rows"
    if not p["has_oos"]:
        return "FAIL", "no '## Out of scope' section"
    seen = []
    for ap, status, where, test in p["rows"]:
        m = re.fullmatch(r"AP(\d+)", ap)
        if not m:
            return "FAIL", f"bad AP cell '{ap[:20]}'"
        n = int(m.group(1))
        if n in seen:
            return "FAIL", f"AP{n} listed twice"
        seen.append(n)
        if status not in STATUSES:
            return "FAIL", f"AP{n} status '{status[:20]}' not Covered/Partial/Not here"
        if status == "Covered" and (not FILELINE.search(where) or test in ("", "-")):
            return "FAIL", f"AP{n} Covered needs both file:line and a test"
        if status == "Partial" and len(where) < 3 and len(test) < 3:
            return "FAIL", f"AP{n} Partial does not say what is missing"
        if status == "Not here" and test in ("", "-"):
            return "FAIL", f"AP{n} Not here does not say where the point goes"
    if seen != sorted(seen):
        return "FAIL", "rows are not in AP order (no renumbering)"
    repo, num = p["ref"]
    try:
        tbody = get_ticket(repo, num)
    except Exception as e:
        return "FAIL", f"cannot read ticket #{num}: {str(e)[:80]}"
    aps, h = ticket_points(tbody)
    if not aps:
        return "FAIL", f"ticket #{num} has no AP points to map"
    extra = [n for n in seen if n not in aps]
    if extra:
        return "FAIL", f"AP{extra[0]} is not on ticket #{num}"
    missing = sorted(aps - set(seen))
    if missing:
        return "FAIL", f"ticket #{num} point AP{missing[0]} has no row"
    if h and p["pv"] != h:
        return "FAIL", f"points_version {p['pv']} is not the ticket's current {h}"
    return "PASS", "ok"


def check_closes_guard(body):
    p = parse_body(body)
    kws = [(m.group(1).lower(), m.group(2)) for m in CLOSE_KW.finditer(body or "")]
    closing = [k for k in kws]
    if not closing:
        return "PASS", "no closing keyword"
    first = f"{closing[0][0]} #{closing[0][1]}"
    if is_legacy(p):
        return "LEGACY", f"'{first}' with no Point map (written before the format)"
    if not p["rows"]:
        return "FAIL", f"'{first}' but no readable map rows"
    bad = [r[0] for r in p["rows"] if r[1] != "Covered"]
    if bad:
        return "FAIL", f"'{first}' while {bad[0]} is not Covered (use Part of)"
    return "PASS", "Closes with every point Covered (merged-PR coverage and read miss=none not checked here)"


def _decl(text, name):
    """Return (found, skipped) for a test name in a source text."""
    lines = text.split("\n")
    pat = re.compile(r"^\s*(?:async\s+)?def\s+" + re.escape(name) + r"\b")
    js = re.compile(r"""\b(?:it|test)(\.skip|\.fixme|\.fail)?\s*\(\s*['"`]""" + re.escape(name) + r"""['"`]""")
    xjs = re.compile(r"""\b(?:xit|xtest)\s*\(\s*['"`]""" + re.escape(name) + r"""['"`]""")
    for i, ln in enumerate(lines):
        if pat.match(ln):
            indent = len(ln) - len(ln.lstrip())
            deco, j = [], i - 1
            while j >= 0 and (lines[j].lstrip().startswith("@") or not lines[j].strip()
                              or lines[j].lstrip().startswith("#")):
                if lines[j].lstrip().startswith("@"):
                    deco.append(lines[j])
                j -= 1
            # class decorators
            k = i - 1
            while k >= 0 and not re.match(r"^class\s", lines[k]):
                k -= 1
            if k >= 0:
                c = k - 1
                while c >= 0 and lines[c].lstrip().startswith("@"):
                    deco.append(lines[c])
                    c -= 1
            body = []
            for ln2 in lines[i + 1:i + 6]:
                body.append(ln2)
            sk = any(re.search(r"(?i)skip|expectedFailure|xfail", d) for d in deco) or \
                any(re.search(r"self\.skipTest\(|pytest\.skip\(", b) for b in body[:2])
            return True, sk
        if js.search(ln):
            return True, bool(js.search(ln).group(1))
        if xjs.search(ln):
            return True, True
    return False, False


def check_test_exists(body, get_tests):
    p = parse_body(body)
    if is_legacy(p):
        return "LEGACY", "no Point map section (written before the format)"
    names = []
    for ap, status, where, test in p["rows"]:
        if status == "Not here" or test in ("", "-"):
            continue
        if status == "Covered" or status == "Partial":
            for t in re.findall(r"[A-Za-z_][\w.]*", test):
                if re.match(r"(?i)test", t.split(".")[-1]):
                    names.append((ap, t.split(".")[-1]))
    if not names:
        return ("FAIL", "no test names in the map") if p["rows"] else ("FAIL", "no map rows")
    try:
        files = get_tests()
    except Exception as e:
        return "FAIL", f"cannot read tests at head: {str(e)[:80]}"
    for ap, name in names:
        found = skipped = False
        for path, txt in files.items():
            f, s = _decl(txt, name)
            if f:
                found, skipped = True, s
                if not s:
                    break
        if not found:
            return "FAIL", f"{ap} test {name} not found at head"
        if skipped:
            return "FAIL", f"{ap} test {name} is skipped or expected-fail"
    return "PASS", f"{len(names)} test name(s) found, none skipped"


def run_pr(pr, gh):
    body = pr.get("body") or ""
    sha = pr["head"]["sha"]
    cache = {}

    def tests():
        if "t" not in cache:
            cache["t"] = gh.test_files(sha)
        return cache["t"]
    out = {"number": pr["number"], "title": pr["title"], "sha": sha[:8], "checks": {}}
    for name, res in (("point-map", check_point_map(body, gh.ticket_body)),
                      ("closes-guard", check_closes_guard(body)),
                      ("test-exists", check_test_exists(body, tests))):
        out["checks"][name] = {"result": res[0], "reason": res[1]}
    return out


def render(rows, stamp):
    tot = {c: {"PASS": 0, "FAIL": 0, "LEGACY": 0} for c in CHECKS}
    for r in rows:
        for c in CHECKS:
            tot[c][r["checks"][c]["result"]] += 1
    L = [f"# PR checks report (report-only) {stamp}", "",
         f"Open PRs: {len(rows)}. LEGACY = PR body written before the Point map format; not a failure.", "",
         "| Check | PASS | FAIL | LEGACY |", "|---|---|---|---|"]
    for c in CHECKS:
        L.append(f"| {c} | {tot[c]['PASS']} | {tot[c]['FAIL']} | {tot[c]['LEGACY']} |")
    L += ["", "| PR | head | point-map | closes-guard | test-exists | first reason |", "|---|---|---|---|---|---|"]
    for r in rows:
        ch = r["checks"]
        first = next((f"{c}: {ch[c]['reason']}" for c in CHECKS if ch[c]["result"] in ("FAIL", "LEGACY")),
                     "all pass")
        first = first.replace("|", "/")
        L.append(f"| #{r['number']} | {r['sha']} | " + " | ".join(ch[c]["result"] for c in CHECKS) + f" | {first[:140]} |")
    return "\n".join(L) + "\n", tot


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="insyncalan/clark")
    ap.add_argument("--plan-repo", default=os.environ.get("BIFROST_PLAN_REPO", ""))
    ap.add_argument("--pr", type=int, action="append")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default=HERE)
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    gh = GH(a.repo, a.plan_repo)
    prs = gh.open_prs()
    if a.pr:
        prs = [p for p in prs if p["number"] in a.pr]
    rows = [run_pr(p, gh) for p in sorted(prs, key=lambda x: x["number"])]
    stamp = datetime.now(ZoneInfo("Asia/Dubai")).strftime("%d-%m-%H%M")
    text, tot = render(rows, stamp)
    if a.json:
        print(json.dumps({"stamp": stamp, "totals": tot, "prs": rows}, indent=1))
    else:
        print(text)
    if not a.no_write:
        path = os.path.join(a.out, f"report-{stamp}.md")
        with open(path, "w") as f:
            f.write(text)
        print("wrote " + path, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Quarantine a test file that was flaky in two runs (development only; standard library only).

    python3 dev/tools/flaky_quarantine.py --results DIR [--list dev/tools/quarantine.txt] [--tickets OUT.json] [--write]

DIR holds the result files CI uploads (dev/run_tests.py --results), each saved as <run id>__<anything>.json. A FLAKE is a file
that failed and then passed alone; the runner already tells it from a DEFECT (failed twice), which is never quarantined. A
file that is a FLAKE in two different runs is added to the quarantine list, and one ticket per file is written to OUT.json
for filing (board Release "Tech Debt - Priority", ledger release none). dev/run_tests.py leaves a quarantined file out of an
ordinary run and says so; the nightly runs it (--with-quarantined). A file leaves the list by a pull request that fixes it.

Without --write it only reports. Exit 0: done. Exit 2: a results file could not be read (not checked is never "no flake").

It files nothing itself and needs no token: the collector saves the result files and files the tickets it writes.

LIMIT: it counts whole test files, as the runner classes them, not single test functions.
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LIST = ROOT / "dev" / "tools" / "quarantine.txt"
AT = 2                                   # different runs with a FLAKE
RELEASE = "Tech Debt - Priority"


def read_list(text):
    """The test files on the quarantine list: one a line, `#` starts a comment."""
    return [ln.split("#")[0].strip() for ln in text.splitlines() if ln.split("#")[0].strip()]


def flaky_runs(docs):
    """{test file: the run ids it was a FLAKE in, in order} from {"<run id>__<job>.json": result}."""
    seen = {}
    for name in sorted(docs):
        run = name.split("__")[0]
        for f in (docs[name].get("flakes") or {}):
            if run not in seen.setdefault(f, []):
                seen[f].append(run)
    return seen


def to_quarantine(runs, already):
    return {f: ids for f, ids in sorted(runs.items()) if len(ids) >= AT and f not in already}


def ticket(name, runs):
    return {"file": name, "runs": list(runs), "release": RELEASE, "ledger_release": "none",
            "title": "Flaky test quarantined: %s" % name,
            "body": "%s failed and then passed alone in %d runs (%s), so it is on dev/tools/quarantine.txt and no longer runs on a "
                    "pull request. The nightly still runs it. Fix the test or the code, show it steady (dev/run_tests.py --repeat), "
                    "and take its line off the list in the same pull request." % (name, len(runs), ", ".join(runs))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", required=True, metavar="DIR")
    ap.add_argument("--list", default=str(LIST))
    ap.add_argument("--tickets", default="", metavar="OUT.json")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    docs, unread = {}, []
    for p in sorted(Path(a.results).glob("*.json")):
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                raise ValueError
            docs[p.name] = doc
        except (OSError, ValueError):
            unread.append(p.name)
    for name in unread:
        print("not checked: %s (it does not read)" % name)
    path = Path(a.list)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    new = to_quarantine(flaky_runs(docs), set(read_list(text)))
    for name, runs in new.items():
        print("quarantined: %s (runs %s)" % (name, ", ".join(runs)))
    if a.write:
        if new:
            day = datetime.now(timezone(timedelta(hours=4))).strftime("%d-%m-%Y")
            lines = ["%s  # runs %s; %s" % (name, ", ".join(runs), day) for name, runs in new.items()]
            path.write_text(text + ("" if text.endswith("\n") or not text else "\n") + "\n".join(lines) + "\n", encoding="utf-8")
        if a.tickets:
            Path(a.tickets).write_text(json.dumps([ticket(n, r) for n, r in new.items()], indent=1) + "\n", encoding="utf-8")
    print("Flaky quarantine: %d result files read, %d new on the list%s" % (len(docs), len(new), "" if a.write else " (report only)"))
    return 2 if unread else 0


if __name__ == "__main__":
    sys.exit(main())

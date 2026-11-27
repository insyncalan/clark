"""The scope script: every file a change touches is one the ticket names (development only; standard library only).

    python3 dev/tools/scope_check.py --base BASE --ticket TICKET.json [--head HEAD] [--repo PATH] [--json]

The ticket file is JSON: {"ticket": "1712", "files": ["src/clark/x.py", "docs/help/", "src/clark/page/*.css"],
"named_tests": ["test_x.XTest.test_a"]}. A file is named when it is listed exactly, lies under a listed folder (a name that
ends with "/"), matches a listed pattern, or is the file of a named test. Added, changed and deleted files all count, and a
moved file counts under both names.

It reads the two commits with git and nothing else. Exit 0: every changed file is named. Exit 1: an extra file (each is
printed; in QA an extra file makes the read required). Exit 2: it could not check (not checked is never a pass).

LIMIT: it compares names. It does not know whether a change inside a named file belongs to the ticket.
"""
import argparse
import fnmatch
import json
import subprocess
import sys


class CannotCheck(Exception):
    pass


def test_file(named_test):
    """The file of a named test: "test_x.XTest.test_a", "test_x", "test_x.py" and "tests/test_x.py" are all tests/test_x.py."""
    name = named_test.strip()
    if name.startswith("tests/"):
        name = name[len("tests/"):]
    if name.endswith(".py"):
        name = name[:-len(".py")]
    return "tests/%s.py" % name.split(".")[0]


def is_named(path, named):
    for entry in named:
        if path == entry or (entry.endswith("/") and path.startswith(entry)):
            return True
        if any(ch in entry for ch in "*?[") and fnmatch.fnmatchcase(path, entry):
            return True
    return False


def named_by(ticket):
    return list(ticket.get("files") or []) + [test_file(t) for t in ticket.get("named_tests") or []]


def changed(repo, base, head):
    def git(*args):
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
        if r.returncode:
            raise CannotCheck("git %s failed" % args[0])
        return r.stdout.decode("utf-8", "replace")
    mb = git("merge-base", base, head).strip()
    return sorted(p for p in git("diff", "--name-only", "--no-renames", "-z", mb, head).split("\0") if p)


def check(repo, base, head, ticket):
    """{"ok", "ticket", "changed", "extra"}. Raises CannotCheck."""
    files = changed(repo, base, head)
    named = named_by(ticket)
    extra = [p for p in files if not is_named(p, named)]
    return {"ok": not extra, "ticket": str(ticket.get("ticket", "")), "changed": files, "extra": extra}


def load_ticket(path):
    try:
        with open(path, encoding="utf-8") as f:
            ticket = json.load(f)
    except (OSError, ValueError) as exc:
        raise CannotCheck("the ticket file cannot be read: %s" % type(exc).__name__)
    if not isinstance(ticket, dict):
        raise CannotCheck("the ticket file is not an object")
    return ticket


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--ticket", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        result = check(a.repo, a.base, a.head, load_ticket(a.ticket))
    except CannotCheck as exc:
        print("Scope: not checked (%s)" % exc)
        return 2
    if a.json:
        print(json.dumps(result, indent=1))
        return 0 if result["ok"] else 1
    for path in result["extra"]:
        print("not named by the ticket: " + path)
    n = len(result["changed"])
    print("Scope: %s (%d changed file%s, ticket %s)" % ("passed" if result["ok"] else "FAILED", n, "" if n == 1 else "s",
                                                       result["ticket"] or "not given"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
